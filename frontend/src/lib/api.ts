import axios, {AxiosError, AxiosResponse, InternalAxiosRequestConfig} from 'axios';

// API base URL from environment
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

// ============================================================================
// Retry Configuration
// ============================================================================

interface RetryConfig {
    retries: number;
    retryDelay: number;
    retryCondition: (error: AxiosError) => boolean;
}

const DEFAULT_RETRY_CONFIG: RetryConfig = {
    retries: 2, // Reduced from 3 to avoid long waits
    retryDelay: 1000, // Start with 1 second
    retryCondition: (error: AxiosError) => {
        // Don't retry if no response (network error) - usually means server is down
        // Retrying won't help if the server isn't responding
        if (!error.response) {
            // Only retry network errors once, not multiple times
            const config = error.config as InternalAxiosRequestConfig & { __retryCount?: number };
            return (config?.__retryCount || 0) < 1;
        }
        const status = error.response.status;
        // Only retry on 429 (rate limit) or 503 (service unavailable)
        // Don't retry on general 5xx as they're usually app errors
        return status === 429 || status === 503;
    },
};

// Sleep utility for retry delay
const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

// Retry logic with exponential backoff
async function retryRequest(
    config: InternalAxiosRequestConfig,
    error: AxiosError,
    retryCount: number,
    maxRetries: number,
    baseDelay: number
): Promise<AxiosResponse> {
    if (retryCount >= maxRetries) {
        throw error;
    }

    // Exponential backoff: delay * 2^retryCount (1s, 2s, 4s, ...)
    const delay = baseDelay * Math.pow(2, retryCount);
    console.log(`Retrying request (${retryCount + 1}/${maxRetries}) after ${delay}ms...`);

    await sleep(delay);

    // Create a new config to avoid mutation
    const retryConfig = {...config};
    // Mark this as a retry
    (retryConfig as any).__retryCount = retryCount + 1;

    return api.request(retryConfig);
}

// ============================================================================
// Error Types
// ============================================================================

export interface ApiErrorDetail {
    code: string;
    message: string;
    field?: string;
    details?: Record<string, any>;
}

export interface ApiErrorResponse {
    success: false;
    error: ApiErrorDetail;
    request_id?: string;
}

export class ApiError extends Error {
    code: string;
    status: number;
    field?: string;
    details?: Record<string, any>;
    requestId?: string;

    constructor(
        message: string,
        code: string,
        status: number,
        field?: string,
        details?: Record<string, any>,
        requestId?: string
    ) {
        super(message);
        this.name = 'ApiError';
        this.code = code;
        this.status = status;
        this.field = field;
        this.details = details;
        this.requestId = requestId;
    }

    static fromAxiosError(error: AxiosError<ApiErrorResponse>): ApiError {
        if (error.response?.data?.error) {
            const {code, message, field, details} = error.response.data.error;
            return new ApiError(
                message,
                code,
                error.response.status,
                field,
                details,
                error.response.data.request_id
            );
        }

        // Fallback for non-standard errors
        const status = error.response?.status || 0;
        const message = error.response?.data
            ? (typeof error.response.data === 'string' ? error.response.data : 'An error occurred')
            : error.message;

        return new ApiError(
            message,
            status === 0 ? 'NETWORK_ERROR' : `HTTP_${status}`,
            status
        );
    }
}

// ============================================================================
// Axios Instance
// ============================================================================

// Create axios instance
export const api = axios.create({
    baseURL: API_URL,
    headers: {
        'Content-Type': 'application/json',
    },
    timeout: 30000, // 30 seconds
});

// Request interceptor - add auth token
api.interceptors.request.use(
    (config: InternalAxiosRequestConfig) => {
        // Get token from localStorage (client-side only)
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

// Response interceptor - handle errors with retry
api.interceptors.response.use(
    (response) => response,
    async (error: AxiosError<ApiErrorResponse>) => {
        const config = error.config as InternalAxiosRequestConfig & { __retryCount?: number };
        const retryCount = config?.__retryCount || 0;
        const {retries, retryDelay, retryCondition} = DEFAULT_RETRY_CONFIG;

        // Check if we should retry
        if (config && retryCount < retries && retryCondition(error)) {
            try {
                return await retryRequest(config, error, retryCount, retries, retryDelay);
            } catch (retryError) {
                // If retry fails, continue to error handling below
                error = retryError as AxiosError<ApiErrorResponse>;
            }
        }

        // Handle 401 - redirect to login
        if (error.response?.status === 401) {
            if (typeof window !== 'undefined') {
                localStorage.removeItem('auth_token');
                window.location.href = '/login';
            }
        }

        // Transform to ApiError for better error handling
        const apiError = ApiError.fromAxiosError(error);

        // Log error in development
        if (process.env.NODE_ENV === 'development') {
            console.error('[API Error]', {
                code: apiError.code,
                message: apiError.message,
                status: apiError.status,
                requestId: apiError.requestId,
            });
        }

        return Promise.reject(apiError);
    }
);

// ============================================================================
// Error Helper Functions
// ============================================================================

/**
 * Check if error is a network error
 */
export function isNetworkError(error: unknown): boolean {
    if (error instanceof ApiError) {
        return error.code === 'NETWORK_ERROR';
    }
    if (error instanceof AxiosError) {
        return !error.response;
    }
    return false;
}

/**
 * Check if error is a specific error code
 */
export function isErrorCode(error: unknown, code: string): boolean {
    return error instanceof ApiError && error.code === code;
}

// API helper functions
export const authApi = {
    // Get GitHub OAuth URL
    getGitHubAuthUrl: () => `${API_URL}/auth/github`,

    // Get current user
    getMe: () => api.get('/auth/me'),
};

export const projectsApi = {
    // List all projects
    list: () => api.get('/projects'),

    // Create new project (connect repo)
    create: (githubRepoId: number) =>
        api.post('/projects', {github_repo_id: githubRepoId}),

    // Get single project
    get: (id: string) => api.get(`/projects/${id}`),

    // Start indexing
    startIndexing: (id: string) => api.post(`/projects/${id}/index`),

    // Start cloning
    startCloning: (id: string) => api.post(`/projects/${id}/clone`),

    // Delete project
    delete: (id: string) => api.delete(`/projects/${id}`),

    // ========== Project Scanning ==========

    // Start a project scan
    startScan: (id: string) => api.post(`/projects/${id}/scan`),

    // Get scan status
    getScanStatus: (id: string) => api.get(`/projects/${id}/scan/status`),

    // Get project health details
    getHealth: (id: string) => api.get(`/projects/${id}/health`),

    // Get project issues
    getIssues: (id: string, params?: { category?: string; severity?: string; status?: string }) =>
        api.get(`/projects/${id}/issues`, {params}),

    // Update issue status
    updateIssueStatus: (projectId: string, issueId: string, status: string) =>
        api.patch(`/projects/${projectId}/issues/${issueId}`, null, {params: {status_update: status}}),
};

export const githubApi = {
    // List user's GitHub repos (filtered to PHP/Laravel)
    listRepos: () => api.get('/github/repos'),

    // Get specific repo by ID
    getRepo: (repoId: number) => api.get(`/github/repos/${repoId}`),
};

export interface PlanApprovalRequest {
    conversation_id: string;
    approved: boolean;
    modified_plan?: {
        summary: string;
        steps: Array<{
            order: number;
            action: string;
            file: string;
            description: string;
        }>;
    };
    rejection_reason?: string;
}

export interface FileChange {
    file: string;
    action: 'create' | 'modify' | 'delete';
    content?: string;
}

export interface ApplyChangesRequest {
    changes: FileChange[];
    branch_name?: string;
    commit_message: string;
    base_branch?: string;
}

export interface CreatePRRequest {
    branch_name: string;
    title: string;
    description?: string;
    base_branch?: string;
    ai_summary?: string;
}

export const gitApi = {
    // List all branches
    listBranches: (projectId: string) =>
        api.get(`/projects/${projectId}/branches`),

    // Apply changes to new branch
    applyChanges: (projectId: string, data: ApplyChangesRequest) =>
        api.post(`/projects/${projectId}/apply`, data),

    // Create pull request
    createPR: (projectId: string, data: CreatePRRequest) =>
        api.post(`/projects/${projectId}/pr`, data),

    // Sync with remote (pull latest)
    sync: (projectId: string) =>
        api.post(`/projects/${projectId}/sync`),

    // Reset to remote
    reset: (projectId: string, branch?: string) =>
        api.post(`/projects/${projectId}/reset`, null, {params: {branch}}),

    // Get diff
    getDiff: (projectId: string, baseBranch?: string) =>
        api.get(`/projects/${projectId}/diff`, {params: {base_branch: baseBranch}}),
};

// Git changes tracking types
export interface GitChangeFile {
    file: string;
    action: 'create' | 'modify' | 'delete';
    content?: string;
    diff?: string;
    original_content?: string;
}

export interface GitChange {
    id: string;
    conversation_id: string;
    project_id: string;
    message_id?: string;
    branch_name: string;
    base_branch: string;
    commit_hash?: string;
    status: 'pending' | 'applied' | 'pushed' | 'pr_created' | 'pr_merged' | 'merged' | 'rolled_back' | 'discarded';
    pr_number?: number;
    pr_url?: string;
    pr_state?: string;
    title?: string;
    description?: string;
    files_changed?: GitChangeFile[];
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
    files_changed?: GitChangeFile[];
    change_summary?: string;
}

export interface UpdateGitChangeRequest {
    status?: string;
    commit_hash?: string;
    pr_number?: number;
    pr_url?: string;
    pr_state?: string;
    title?: string;
    description?: string;
}

export interface RollbackResponse {
    success: boolean;
    message: string;
    rollback_commit?: string;
    previous_status: string;
}

export const gitChangesApi = {
    // List all changes for a project
    listProjectChanges: (projectId: string, params?: {
        status?: string;
        conversation_id?: string;
        limit?: number;
        offset?: number
    }) =>
        api.get<GitChange[]>(`/projects/${projectId}/changes`, {params}),

    // List changes for a conversation
    listConversationChanges: (projectId: string, conversationId: string) =>
        api.get<GitChange[]>(`/projects/${projectId}/conversations/${conversationId}/changes`),

    // Get a specific change
    getChange: (projectId: string, changeId: string) =>
        api.get<GitChange>(`/projects/${projectId}/changes/${changeId}`),

    // Create a new change record
    createChange: (projectId: string, data: CreateGitChangeRequest) =>
        api.post<GitChange>(`/projects/${projectId}/changes`, data),

    // Update a change
    updateChange: (projectId: string, changeId: string, data: UpdateGitChangeRequest) =>
        api.patch<GitChange>(`/projects/${projectId}/changes/${changeId}`, data),

    // Apply a pending change
    applyChange: (projectId: string, changeId: string) =>
        api.post<GitChange>(`/projects/${projectId}/changes/${changeId}/apply`),

    // Push an applied change
    pushChange: (projectId: string, changeId: string) =>
        api.post<GitChange>(`/projects/${projectId}/changes/${changeId}/push`),

    // Create PR for a change
    createPRForChange: (projectId: string, changeId: string, params?: { title?: string; description?: string }) =>
        api.post<GitChange>(`/projects/${projectId}/changes/${changeId}/create-pr`, null, {params}),

    // Rollback a change
    rollbackChange: (projectId: string, changeId: string, force?: boolean) =>
        api.post<RollbackResponse>(`/projects/${projectId}/changes/${changeId}/rollback`, {force}),

    // Delete a change record
    deleteChange: (projectId: string, changeId: string) =>
        api.delete(`/projects/${projectId}/changes/${changeId}`),
};

// Add these to your existing frontend/src/lib/api.ts file

// ============== TYPES ==============

export interface PlanApprovalRequest {
    conversation_id: string;
    approved: boolean;
    modified_plan?: {
        summary: string;
        steps: Array<{
            order: number;
            action: string;
            file: string;
            description: string;
        }>;
    };
    rejection_reason?: string;
}

export interface Conversation {
    id: string;
    project_id: string;
    title: string;
    created_at: string;
    updated_at: string;
    message_count: number;
}

export interface ConversationMessage {
    id: string;
    role: 'user' | 'assistant';
    content: string;
    created_at: string;
    processing_data?: {
        intent?: any;
        plan?: any;
        execution_results?: any[];
        validation?: any;
        events?: any[];
        success?: boolean;
        error?: string;
        agent_timeline?: any;
    };
}

// ============== CHAT API ==============

export const chatApi = {
    /**
     * List all conversations for a project
     */
    listConversations: (projectId: string) =>
        api.get<Conversation[]>(`/projects/${projectId}/conversations`),

    /**
     * Get messages for a specific conversation
     */
    getMessages: (projectId: string, conversationId: string) =>
        api.get<ConversationMessage[]>(`/projects/${projectId}/conversations/${conversationId}`),

    /**
     * Delete a conversation
     */
    deleteConversation: (projectId: string, conversationId: string) =>
        api.delete(`/projects/${projectId}/conversations/${conversationId}`),

    /**
     * Get the chat endpoint URL for SSE streaming
     */
    getChatUrl: (projectId: string) =>
        `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'}/projects/${projectId}/chat`,

    /**
     * Approve or reject a plan in interactive mode
     */
    approvePlan: (projectId: string, data: PlanApprovalRequest) =>
        api.post(`/projects/${projectId}/chat/approve-plan`, data),

    /**
     * Get available agents information
     */
    getAgents: () => api.get('/chat/agents'),
};

// ============== ERROR HANDLING ==============

/**
 * Extract error message from various error types
 */
export function getErrorMessage(error: unknown): string {
    if (error instanceof Error) {
        return error.message;
    }
    if (typeof error === 'string') {
        return error;
    }
    if (error && typeof error === 'object') {
        // Handle axios-style errors
        const axiosError = error as any;
        if (axiosError.response?.data?.detail) {
            return axiosError.response.data.detail;
        }
        if (axiosError.response?.data?.message) {
            return axiosError.response.data.message;
        }
        if (axiosError.message) {
            return axiosError.message;
        }
    }
    return 'An unexpected error occurred';
}

// ============== STORE TYPES (if using Zustand) ==============

// Add to frontend/src/lib/store.ts

interface Project {
    id: string;
    repo_name: string;
    repo_full_name: string;
    github_repo_id: number;
    status: string;
    indexed_at?: string;
    created_at: string;
    updated_at: string;
}

interface User {
    id: string;
    email: string;
    name?: string;
    username: string;
    avatar_url?: string;
}

interface AuthState {
    isAuthenticated: boolean;
    isHydrated: boolean;
    user: User | null;
    token: string | null;
    setAuth: (user: User, token: string) => void;
    clearAuth: () => void;
    setHydrated: () => void;
}

interface ProjectsState {
    projects: Project[];
    selectedProject: Project | null;
    setProjects: (projects: Project[]) => void;
    selectProject: (project: Project) => void;
    clearSelected: () => void;
}

// Example Zustand store implementation:
/*
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      isAuthenticated: false,
      isHydrated: false,
      user: null,
      token: null,
      setAuth: (user, token) => {
        localStorage.setItem('auth_token', token);
        set({ isAuthenticated: true, user, token });
      },
      clearAuth: () => {
        localStorage.removeItem('auth_token');
        set({ isAuthenticated: false, user: null, token: null });
      },
      setHydrated: () => set({ isHydrated: true }),
    }),
    {
      name: 'auth-storage',
      onRehydrateStorage: () => (state) => {
        state?.setHydrated();
      },
    }
  )
);

export const useProjectsStore = create<ProjectsState>()(
  persist(
    (set) => ({
      projects: [],
      selectedProject: null,
      setProjects: (projects) => set({ projects }),
      selectProject: (project) => set({ selectedProject: project }),
      clearSelected: () => set({ selectedProject: null }),
    }),
    {
      name: 'projects-storage',
    }
  )
);
*/

export default api;