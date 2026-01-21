import axios, {AxiosError, AxiosResponse, InternalAxiosRequestConfig} from 'axios';

// ============================================================================
// Configuration
// ============================================================================

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
const DEFAULT_TIMEOUT = 30000;
const UPLOAD_TIMEOUT = 120000;

// ============================================================================
// Retry Configuration
// ============================================================================

interface RetryConfig {
    retries: number;
    retryDelay: number;
    retryCondition: (error: AxiosError) => boolean;
}

interface ExtendedAxiosConfig extends InternalAxiosRequestConfig {
    __retryCount?: number;
    __skipRetry?: boolean;
}

const DEFAULT_RETRY_CONFIG: RetryConfig = {
    retries: 2,
    retryDelay: 1000,
    retryCondition: (error: AxiosError) => {
        if (!error.response) {
            const config = error.config as ExtendedAxiosConfig;
            return (config?.__retryCount || 0) < 1;
        }
        const status = error.response.status;
        return status === 429 || status === 503 || status === 502;
    },
};

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

async function retryRequest(
    config: InternalAxiosRequestConfig,
    error: AxiosError,
    retryCount: number,
    maxRetries: number,
    baseDelay: number
): Promise<AxiosResponse> {
    if (retryCount >= maxRetries) throw error;

    const delay = baseDelay * Math.pow(2, retryCount);
    if (process.env.NODE_ENV === 'development') {
        console.log(`Retrying request (${retryCount + 1}/${maxRetries}) after ${delay}ms...`);
    }

    await sleep(delay);
    const retryConfig = {...config, __retryCount: retryCount + 1} as ExtendedAxiosConfig;
    return api.request(retryConfig);
}

// ============================================================================
// Error Types
// ============================================================================

export interface ApiErrorDetail {
    code: string;
    message: string;
    field?: string;
    details?: Record<string, unknown>;
}

export interface ApiErrorResponse {
    success: false;
    error?: ApiErrorDetail;
    detail?: string;
    request_id?: string;
}

export class ApiError extends Error {
    code: string;
    status: number;
    field?: string;
    details?: Record<string, unknown>;
    requestId?: string;
    isNetworkError: boolean;
    isTimeout: boolean;
    isUnauthorized: boolean;
    isNotFound: boolean;
    isServerError: boolean;
    isRateLimited: boolean;

    constructor(
        message: string,
        code: string,
        status: number,
        field?: string,
        details?: Record<string, unknown>,
        requestId?: string
    ) {
        super(message);
        this.name = 'ApiError';
        this.code = code;
        this.status = status;
        this.field = field;
        this.details = details;
        this.requestId = requestId;
        this.isNetworkError = code === 'NETWORK_ERROR';
        this.isTimeout = code === 'TIMEOUT';
        this.isUnauthorized = status === 401;
        this.isNotFound = status === 404;
        this.isServerError = status >= 500;
        this.isRateLimited = status === 429;
    }

    static fromAxiosError(error: AxiosError<ApiErrorResponse>): ApiError {
        if (error.code === 'ECONNABORTED') {
            return new ApiError('Request timeout - please try again', 'TIMEOUT', 0);
        }

        if (!error.response) {
            return new ApiError(
                'Network error - please check your connection',
                'NETWORK_ERROR',
                0
            );
        }

        const {status, data} = error.response;

        if (data?.error) {
            const {code, message, field, details} = data.error;
            return new ApiError(message, code, status, field, details, data.request_id);
        }

        if (data?.detail) {
            return new ApiError(data.detail, `HTTP_${status}`, status, undefined, undefined, data.request_id);
        }

        const statusMessages: Record<number, string> = {
            400: 'Invalid request',
            401: 'Authentication required',
            403: 'Access denied',
            404: 'Resource not found',
            429: 'Too many requests - please slow down',
            500: 'Server error - please try again later',
            502: 'Service temporarily unavailable',
            503: 'Service temporarily unavailable',
        };

        return new ApiError(
            statusMessages[status] || 'An error occurred',
            `HTTP_${status}`,
            status
        );
    }
}

// ============================================================================
// Axios Instance
// ============================================================================

export const api = axios.create({
    baseURL: API_URL,
    headers: {'Content-Type': 'application/json'},
    timeout: DEFAULT_TIMEOUT,
});

// Request interceptor
api.interceptors.request.use(
    (config: InternalAxiosRequestConfig) => {
        if (typeof window !== 'undefined') {
            const token = localStorage.getItem('auth_token');
            if (token && config.headers) {
                config.headers.Authorization = `Bearer ${token}`;
            }
        }
        return config;
    },
    (error) => Promise.reject(error)
);

// Response interceptor with retry logic
api.interceptors.response.use(
    (response) => response,
    async (error: AxiosError<ApiErrorResponse>) => {
        const config = error.config as ExtendedAxiosConfig;

        if (config?.__skipRetry) {
            return Promise.reject(ApiError.fromAxiosError(error));
        }

        const retryCount = config?.__retryCount || 0;
        const {retries, retryDelay, retryCondition} = DEFAULT_RETRY_CONFIG;

        if (config && retryCount < retries && retryCondition(error)) {
            try {
                return await retryRequest(config, error, retryCount, retries, retryDelay);
            } catch (retryError) {
                error = retryError as AxiosError<ApiErrorResponse>;
            }
        }

        if (error.response?.status === 401 && typeof window !== 'undefined') {
            const currentPath = window.location.pathname;
            if (!currentPath.includes('/login') && !currentPath.includes('/auth')) {
                localStorage.removeItem('auth_token');
                window.location.href = '/login';
            }
        }

        const apiError = ApiError.fromAxiosError(error);

        if (process.env.NODE_ENV === 'development') {
            console.error('[API Error]', {
                code: apiError.code,
                message: apiError.message,
                status: apiError.status,
                requestId: apiError.requestId,
                url: config?.url,
            });
        }

        return Promise.reject(apiError);
    }
);

// ============================================================================
// Helper Functions
// ============================================================================

export function isNetworkError(error: unknown): boolean {
    return error instanceof ApiError && error.isNetworkError;
}

export function isErrorCode(error: unknown, code: string): boolean {
    return error instanceof ApiError && error.code === code;
}

export function getErrorMessage(error: unknown): string {
    if (error instanceof ApiError) return error.message;
    if (error instanceof Error) return error.message;
    if (typeof error === 'string') return error;
    if (error && typeof error === 'object') {
        const e = error as Record<string, unknown>;
        if (typeof e.message === 'string') return e.message;
        if (e.response && typeof e.response === 'object') {
            const resp = e.response as Record<string, unknown>;
            if (resp.data && typeof resp.data === 'object') {
                const data = resp.data as Record<string, unknown>;
                if (typeof data.detail === 'string') return data.detail;
                if (typeof data.message === 'string') return data.message;
            }
        }
    }
    return 'An unexpected error occurred';
}

export function isRetryableError(error: unknown): boolean {
    if (!(error instanceof ApiError)) return false;
    return error.isNetworkError || error.isTimeout || error.isRateLimited || error.status === 503;
}

// ============================================================================
// Type Definitions
// ============================================================================

// --- Auth Types ---
export interface User {
    id: string;
    username: string;
    email: string | null;
    avatar_url: string | null;
    name?: string;
}

export interface AuthResponse {
    access_token: string;
    token_type: string;
    user: User;
}

export interface ExchangeCodeRequest {
    code: string;
}

// --- Health Types ---
export interface HealthResponse {
    status: 'healthy' | 'unhealthy';
    service: string;
}

// --- GitHub Types ---
export interface GitHubRepo {
    id: number;
    name: string;
    full_name: string;
    default_branch: string;
    private: boolean;
    updated_at: string;
    html_url: string;
    description: string | null;
    language: string | null;
}

// --- Project Types ---
export type ProjectStatus = 'pending' | 'cloning' | 'indexing' | 'scanning' | 'analyzing' | 'ready' | 'error';

export interface Project {
    id: string;
    name: string;
    repo_full_name: string;
    repo_url: string;
    default_branch: string;
    clone_path: string | null;
    status: ProjectStatus;
    indexed_files_count: number;
    laravel_version: string | null;
    error_message: string | null;
    last_indexed_at: string | null;
    created_at: string;
    updated_at: string;
    stack?: Record<string, unknown>;
    file_stats?: Record<string, unknown>;
    health_score?: number;
    scan_progress?: number;
    scan_message?: string | null;
    scanned_at?: string | null;
    php_version?: string | null;
    structure?: Record<string, unknown>;
    health_check?: Record<string, unknown>;
}

export interface CreateProjectRequest {
    github_repo_id: number;
}

// --- File Types ---
export interface FileNode {
    name: string;
    path: string;
    type: 'file' | 'directory';
    indexed?: boolean;
    children?: FileNode[];
}

export interface FileContentResponse {
    file_path: string;
    content: string;
    language?: string;
    indexed: boolean;
}

// --- Issue Types ---
export type IssueSeverity = 'critical' | 'warning' | 'info';
export type IssueStatus = 'open' | 'fixed' | 'ignored';
export type IssueCategory = 'security' | 'performance' | 'best_practices' | 'code_quality' | 'deprecation';

export interface ProjectIssue {
    id: string;
    category: IssueCategory;
    severity: IssueSeverity;
    title: string;
    description: string;
    file_path?: string;
    line_number?: number;
    suggestion?: string;
    auto_fixable: boolean;
    status: IssueStatus;
    created_at: string;
}

export interface IssueFilters {
    category?: IssueCategory;
    severity?: IssueSeverity;
    status_filter?: IssueStatus;
}

// --- Conversation Types ---
export interface Conversation {
    id: string;
    project_id: string;
    title: string | null;
    created_at: string;
    updated_at: string;
    message_count: number;
    last_message?: string | null;
}

export interface ConversationMessage {
    id: string;
    role: 'user' | 'assistant' | 'system';
    content: string;
    code_changes?: Record<string, unknown>;
    processing_data?: {
        intent?: unknown;
        plan?: unknown;
        execution_results?: unknown[];
        validation?: unknown;
        events?: unknown[];
        success?: boolean;
        error?: string;
        agent_timeline?: unknown;
    };
    created_at: string;
}

export interface ConversationListParams {
    limit?: number;
    offset?: number;
}

export type LogType = 'main' | 'json' | 'agents' | 'files';

// --- Chat Types ---
export interface ChatRequest {
    message: string;
    conversation_id?: string | null;
    interactive_mode?: boolean;
    require_plan_approval?: boolean;
}

export interface PlanStep {
    order: number;
    action: string;
    file: string;
    description: string;
}

export interface ModifiedPlan {
    summary: string;
    steps: PlanStep[];
}

export interface PlanApprovalRequest {
    conversation_id: string;
    approved: boolean;
    modified_plan?: ModifiedPlan;
    rejection_reason?: string;
}

export interface PlanApprovalResponse {
    success: boolean;
    message: string;
    approved: boolean;
}

export interface Agent {
    type: string;
    name: string;
    description: string;
    emoji: string;
}

export interface AgentsResponse {
    success: boolean;
    agents: Agent[];
}

// --- Git Types ---
export interface GitBranch {
    name: string;
    is_current: boolean;
    is_remote: boolean;
    commit: string;
    message?: string;
    author?: string;
    date?: string;
}

export interface FileChange {
    file: string;
    action: 'create' | 'modify' | 'delete';
    content?: string | null;
    diff?: string | null;
    original_content?: string | null;
}

export interface ApplyChangesRequest {
    changes: FileChange[];
    branch_name?: string;
    commit_message: string;
    base_branch?: string;
}

export interface ApplyChangesResponse {
    branch_name: string;
    commit_hash: string;
    files_changed: number;
    message: string;
}

export interface CreatePRRequest {
    branch_name: string;
    title: string;
    description?: string;
    base_branch?: string;
    ai_summary?: string;
}

export interface PRResponse {
    number: number;
    url: string;
    title: string;
    state: 'open' | 'closed' | 'merged';
    created_at: string;
}

export interface SyncResponse {
    success: boolean;
    message: string;
    had_changes: boolean;
}

// --- Git Changes Types ---
export type GitChangeStatus = 'pending' | 'applied' | 'pushed' | 'pr_created' | 'pr_merged' | 'merged' | 'rolled_back' | 'discarded';

export interface GitChange {
    id: string;
    conversation_id: string;
    project_id: string;
    message_id?: string;
    branch_name: string;
    base_branch: string;
    commit_hash?: string;
    status: GitChangeStatus;
    pr_number?: number;
    pr_url?: string;
    pr_state?: 'open' | 'closed' | 'merged';
    title?: string;
    description?: string;
    files_changed?: FileChange[];
    change_summary?: string;
    rollback_commit?: string;
    rolled_back_at?: string;
    rolled_back_from_status?: string;
    created_at: string;
    updated_at: string;
    applied_at?: string;
    pushed_at?: string;
    pr_created_at?: string;
    merged_at?: string;
}

export interface CreateGitChangeRequest {
    conversation_id: string;
    message_id?: string;
    branch_name: string;
    base_branch?: string;
    title?: string;
    description?: string;
    files_changed?: FileChange[];
    change_summary?: string;
}

export interface UpdateGitChangeRequest {
    status?: GitChangeStatus;
    commit_hash?: string;
    pr_number?: number;
    pr_url?: string;
    pr_state?: string;
    title?: string;
    description?: string;
}

export interface GitChangesListParams {
    status_filter?: GitChangeStatus;
    conversation_id?: string;
    limit?: number;
    offset?: number;
}

export interface RollbackRequest {
    force?: boolean;
}

export interface RollbackResponse {
    success: boolean;
    message: string;
    rollback_commit?: string;
    previous_status: string;
}

export interface DeleteChangeResponse {
    success: boolean;
    message: string;
}

// --- Usage Types ---
export interface UsageSummary {
    total_requests: number;
    total_input_tokens: number;
    total_output_tokens: number;
    total_tokens: number;
    total_cost: number;
}

export interface ProviderUsage {
    requests: number;
    tokens: number;
    cost: number;
}

export interface ModelUsage extends ProviderUsage {
    provider: string;
}

export interface UsageSummaryResponse {
    summary: UsageSummary;
    by_provider: Record<string, ProviderUsage>;
    by_model: Record<string, ModelUsage>;
    today: {
        requests: number;
        cost: number;
    };
    period: {
        start: string;
        end: string;
    };
}

export interface DailyUsage {
    date: string;
    requests: number;
    input_tokens: number;
    output_tokens: number;
    cost: number;
    avg_latency_ms?: number;
}

export interface UsageHistoryItem {
    id: string;
    provider: string;
    model: string;
    request_type: string;
    input_tokens: number;
    output_tokens: number;
    total_tokens: number;
    total_cost: number;
    latency_ms: number;
    status: 'success' | 'error';
    error_message?: string;
    project_id?: string;
    created_at: string;
}

export interface UsageHistoryResponse {
    items: UsageHistoryItem[];
    total: number;
    page: number;
    limit: number;
    pages: number;
}

export interface UsageHistoryParams {
    page?: number;
    limit?: number;
    project_id?: string;
    provider?: string;
    request_type?: string;
}

export interface ProjectUsageResponse {
    project_id: string;
    total_requests: number;
    total_input_tokens: number;
    total_output_tokens: number;
    total_cost: number;
    by_request_type: Record<string, number>;
    period: {
        start: string;
        end: string;
    };
}

export interface ModelPricing {
    input_per_million: number;
    output_per_million: number;
}

export interface PricingResponse {
    providers: Record<string, Record<string, ModelPricing>>;
}

// ============================================================================
// API Modules
// ============================================================================

// --- Health API ---
export const healthApi = {
    check: () => api.get<HealthResponse>('/health'),
};

// --- Auth API ---
export const authApi = {
    getGitHubAuthUrl: () => `${API_URL}/auth/github`,

    exchangeCode: (code: string) =>
        api.post<AuthResponse>('/auth/exchange', {code}),

    getMe: () => api.get<User>('/auth/me'),

    handleCallback: async (code: string): Promise<AuthResponse> => {
        const response = await api.post<AuthResponse>('/auth/exchange', {code});
        return response.data;
    },
};

// --- GitHub API ---
export const githubApi = {
    listRepos: () => api.get<GitHubRepo[]>('/github/repos'),

    getRepo: (repoId: number) => api.get<GitHubRepo>(`/github/repos/${repoId}`),
};

// --- Projects API ---
export const projectsApi = {
    list: () => api.get<Project[]>('/projects'),

    create: (githubRepoId: number) =>
        api.post<Project>('/projects', {github_repo_id: githubRepoId}),

    get: (id: string) => api.get<Project>(`/projects/${id}`),

    delete: (id: string) => api.delete(`/projects/${id}`),

    startIndexing: (id: string) => api.post(`/projects/${id}/index`),

    startCloning: (id: string) => api.post(`/projects/${id}/clone`),

    startScan: (id: string) => api.post(`/projects/${id}/scan`),

    getScanStatus: (id: string) => api.get(`/projects/${id}/scan/status`),

    getHealth: (id: string) => api.get(`/projects/${id}/health`),

    getIssues: (id: string, filters?: IssueFilters) =>
        api.get<ProjectIssue[]>(`/projects/${id}/issues`, {params: filters}),

    updateIssueStatus: (projectId: string, issueId: string, status: IssueStatus) =>
        api.patch<ProjectIssue>(`/projects/${projectId}/issues/${issueId}`, null, {
            params: {status_update: status}
        }),
};

// --- Files API ---
export const filesApi = {
    getFileTree: (projectId: string) =>
        api.get<FileNode[]>(`/projects/${projectId}/files`),

    getFileContent: (projectId: string, filePath: string) =>
        api.get<FileContentResponse>(`/projects/${projectId}/files/${encodeURIComponent(filePath)}`),
};

// --- Chat API ---
export const chatApi = {
    getChatUrl: (projectId: string) => `${API_URL}/projects/${projectId}/chat`,

    listConversations: (projectId: string, params?: ConversationListParams) =>
        api.get<Conversation[]>(`/projects/${projectId}/conversations`, {params}),

    getMessages: (projectId: string, conversationId: string) =>
        api.get<ConversationMessage[]>(`/projects/${projectId}/conversations/${conversationId}`),

    deleteConversation: (projectId: string, conversationId: string) =>
        api.delete<{message: string}>(`/projects/${projectId}/conversations/${conversationId}`),

    getLogs: (projectId: string, conversationId: string, logType: LogType = 'main') =>
        api.get<string>(`/projects/${projectId}/conversations/${conversationId}/logs`, {
            params: {log_type: logType}
        }),

    approvePlan: (projectId: string, data: PlanApprovalRequest) =>
        api.post<PlanApprovalResponse>(`/projects/${projectId}/chat/approve-plan`, data),

    getAgents: (projectId: string) =>
        api.get<AgentsResponse>(`/projects/${projectId}/chat/agents`),
};

// --- Git API ---
export const gitApi = {
    listBranches: (projectId: string) =>
        api.get<GitBranch[]>(`/projects/${projectId}/git/branches`),

    applyChanges: (projectId: string, data: ApplyChangesRequest) =>
        api.post<ApplyChangesResponse>(`/projects/${projectId}/git/apply`, data),

    createPR: (projectId: string, data: CreatePRRequest) =>
        api.post<PRResponse>(`/projects/${projectId}/git/pr`, data),

    sync: (projectId: string) =>
        api.post<SyncResponse>(`/projects/${projectId}/git/sync`),

    reset: (projectId: string, branch?: string) =>
        api.post(`/projects/${projectId}/git/reset`, null, {params: {branch}}),

    getDiff: (projectId: string, baseBranch?: string) =>
        api.get(`/projects/${projectId}/git/diff`, {params: {base_branch: baseBranch}}),
};

// --- Git Changes API ---
export const gitChangesApi = {
    listProjectChanges: (projectId: string, params?: GitChangesListParams) =>
        api.get<GitChange[]>(`/projects/${projectId}/changes`, {params}),

    listConversationChanges: (projectId: string, conversationId: string) =>
        api.get<GitChange[]>(`/projects/${projectId}/conversations/${conversationId}/changes`),

    getChange: (projectId: string, changeId: string) =>
        api.get<GitChange>(`/projects/${projectId}/changes/${changeId}`),

    createChange: (projectId: string, data: CreateGitChangeRequest) =>
        api.post<GitChange>(`/projects/${projectId}/changes`, data),

    updateChange: (projectId: string, changeId: string, data: UpdateGitChangeRequest) =>
        api.patch<GitChange>(`/projects/${projectId}/changes/${changeId}`, data),

    applyChange: (projectId: string, changeId: string) =>
        api.post<GitChange>(`/projects/${projectId}/changes/${changeId}/apply`),

    pushChange: (projectId: string, changeId: string) =>
        api.post<GitChange>(`/projects/${projectId}/changes/${changeId}/push`),

    createPRForChange: (projectId: string, changeId: string, params?: {title?: string; description?: string}) =>
        api.post<GitChange>(`/projects/${projectId}/changes/${changeId}/pr`, null, {params}),

    rollbackChange: (projectId: string, changeId: string, force?: boolean) =>
        api.post<RollbackResponse>(`/projects/${projectId}/changes/${changeId}/rollback`, {force}),

    deleteChange: (projectId: string, changeId: string) =>
        api.delete<DeleteChangeResponse>(`/projects/${projectId}/changes/${changeId}`),
};

// --- Usage API ---
export const usageApi = {
    getSummary: (days: number = 30) =>
        api.get<UsageSummaryResponse>('/usage/summary', {params: {days}}),

    getDaily: (days: number = 30) =>
        api.get<DailyUsage[]>('/usage/daily', {params: {days}}),

    getHistory: (params?: UsageHistoryParams) =>
        api.get<UsageHistoryResponse>('/usage/history', {params}),

    getProjectUsage: (projectId: string, days: number = 30) =>
        api.get<ProjectUsageResponse>(`/usage/project/${projectId}`, {params: {days}}),

    getPricing: () => api.get<PricingResponse>('/usage/pricing'),
};

// ============================================================================
// SSE Streaming Utilities
// ============================================================================

export type SSEEventType =
    | 'message_start'
    | 'intent'
    | 'context'
    | 'plan'
    | 'plan_approval_required'
    | 'execution_step'
    | 'validation'
    | 'answer_chunk'
    | 'complete'
    | 'error';

export interface SSEEvent {
    event: SSEEventType;
    data: unknown;
}

export interface SSEStreamOptions {
    onEvent: (event: SSEEvent) => void;
    onError?: (error: Error) => void;
    onClose?: () => void;
    signal?: AbortSignal;
}

export async function createChatStream(
    projectId: string,
    request: ChatRequest,
    options: SSEStreamOptions
): Promise<void> {
    const url = chatApi.getChatUrl(projectId);
    const token = typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null;

    try {
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...(token && {Authorization: `Bearer ${token}`}),
            },
            body: JSON.stringify(request),
            signal: options.signal,
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new ApiError(
                errorData.detail || `HTTP ${response.status}`,
                `HTTP_${response.status}`,
                response.status
            );
        }

        const reader = response.body?.getReader();
        if (!reader) throw new Error('No response body');

        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const {done, value} = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, {stream: true});
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';

            let currentEvent: string | null = null;
            let currentData = '';

            for (const line of lines) {
                if (line.startsWith('event:')) {
                    currentEvent = line.slice(6).trim();
                } else if (line.startsWith('data:')) {
                    currentData = line.slice(5).trim();
                } else if (line === '' && currentEvent && currentData) {
                    try {
                        const parsedData = JSON.parse(currentData);
                        options.onEvent({event: currentEvent as SSEEventType, data: parsedData});
                    } catch {
                        options.onEvent({event: currentEvent as SSEEventType, data: currentData});
                    }
                    currentEvent = null;
                    currentData = '';
                }
            }
        }

        options.onClose?.();
    } catch (error) {
        if (error instanceof Error && error.name === 'AbortError') {
            options.onClose?.();
            return;
        }
        options.onError?.(error instanceof Error ? error : new Error(String(error)));
    }
}

// ============================================================================
// Request Helpers
// ============================================================================

export async function withRetry<T>(
    fn: () => Promise<T>,
    maxRetries: number = 3,
    delayMs: number = 1000
): Promise<T> {
    let lastError: Error | null = null;

    for (let i = 0; i < maxRetries; i++) {
        try {
            return await fn();
        } catch (error) {
            lastError = error instanceof Error ? error : new Error(String(error));
            if (!isRetryableError(error) || i === maxRetries - 1) throw lastError;
            await sleep(delayMs * Math.pow(2, i));
        }
    }

    throw lastError;
}

export function createAbortController(timeoutMs?: number): {
    controller: AbortController;
    cleanup: () => void;
} {
    const controller = new AbortController();
    let timeoutId: NodeJS.Timeout | undefined;

    if (timeoutMs) {
        timeoutId = setTimeout(() => controller.abort(), timeoutMs);
    }

    return {
        controller,
        cleanup: () => {
            if (timeoutId) clearTimeout(timeoutId);
        },
    };
}

export default api;