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
  // Send message
  send: (projectId: string, message: string, conversationId?: string) =>
    api.post('/chat', { project_id: projectId, message, conversation_id: conversationId }),

  // Get conversation messages
  getMessages: (conversationId: string) =>
    api.get(`/chat/${conversationId}/messages`),

  // Stream response (for SSE)
  streamUrl: (projectId: string) => `${API_URL}/chat/stream`,
};

export default api;