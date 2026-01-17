import axios, { AxiosError, AxiosResponse, InternalAxiosRequestConfig } from 'axios';

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
  retries: 3,
  retryDelay: 1000, // Start with 1 second
  retryCondition: (error: AxiosError) => {
    // Retry on network errors or 5xx server errors
    if (!error.response) return true; // Network error
    const status = error.response.status;
    return status >= 500 || status === 429; // Server error or rate limited
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
  const retryConfig = { ...config };
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
      const { code, message, field, details } = error.response.data.error;
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
    const { retries, retryDelay, retryCondition } = DEFAULT_RETRY_CONFIG;

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
 * Extract user-friendly error message from any error
 */
export function getErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  if (typeof error === 'string') {
    return error;
  }
  return 'An unexpected error occurred';
}

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
    api.post('/projects', { github_repo_id: githubRepoId }),

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
    api.get(`/projects/${id}/issues`, { params }),

  // Update issue status
  updateIssueStatus: (projectId: string, issueId: string, status: string) =>
    api.patch(`/projects/${projectId}/issues/${issueId}`, null, { params: { status_update: status } }),
};

export const githubApi = {
  // List user's GitHub repos (filtered to PHP/Laravel)
  listRepos: () => api.get('/github/repos'),

  // Get specific repo by ID
  getRepo: (repoId: number) => api.get(`/github/repos/${repoId}`),
};

export const chatApi = {
  // List conversations for a project
  listConversations: (projectId: string) =>
    api.get(`/projects/${projectId}/conversations`),

  // Get messages for a conversation
  getMessages: (projectId: string, conversationId: string) =>
    api.get(`/projects/${projectId}/conversations/${conversationId}`),

  // Delete a conversation
  deleteConversation: (projectId: string, conversationId: string) =>
    api.delete(`/projects/${projectId}/conversations/${conversationId}`),

  // Chat endpoint URL (for SSE)
  getChatUrl: (projectId: string) => `${API_URL}/projects/${projectId}/chat`,
};

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
    api.post(`/projects/${projectId}/reset`, null, { params: { branch } }),

  // Get diff
  getDiff: (projectId: string, baseBranch?: string) =>
    api.get(`/projects/${projectId}/diff`, { params: { base_branch: baseBranch } }),
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
  listProjectChanges: (projectId: string, params?: { status?: string; conversation_id?: string; limit?: number; offset?: number }) =>
    api.get<GitChange[]>(`/projects/${projectId}/changes`, { params }),

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
    api.post<GitChange>(`/projects/${projectId}/changes/${changeId}/create-pr`, null, { params }),

  // Rollback a change
  rollbackChange: (projectId: string, changeId: string, force?: boolean) =>
    api.post<RollbackResponse>(`/projects/${projectId}/changes/${changeId}/rollback`, { force }),

  // Delete a change record
  deleteChange: (projectId: string, changeId: string) =>
    api.delete(`/projects/${projectId}/changes/${changeId}`),
};

export default api;