import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios';

// API base URL from environment
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

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

// Response interceptor - handle errors
api.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      // Clear token and redirect to login
      if (typeof window !== 'undefined') {
        localStorage.removeItem('auth_token');
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

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