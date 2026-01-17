import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';

// User type
interface User {
  id: string;
  username: string;
  email: string | null;
  avatar_url: string | null;
}

// Project type
interface Project {
  id: string;
  name?: string;
  repo_full_name: string;
  repo_url: string;
  status: 'pending' | 'cloning' | 'indexing' | 'ready' | 'error';
  indexed_files_count: number;
  laravel_version: string | null;
  error_message?: string | null;
}

// Auth store
interface AuthState {
  token: string | null;
  user: User | null;
  isAuthenticated: boolean;
  isHydrated: boolean;
  setAuth: (token: string, user: User) => void;
  logout: () => void;
  setHydrated: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      token: null,
      user: null,
      isAuthenticated: false,
      isHydrated: false,
      setAuth: (token, user) => {
        localStorage.setItem('auth_token', token);
        set({ token, user, isAuthenticated: true });
      },
      logout: () => {
        localStorage.removeItem('auth_token');
        set({ token: null, user: null, isAuthenticated: false });
      },
      setHydrated: () => set({ isHydrated: true }),
    }),
    {
      name: 'auth-storage',
      storage: createJSONStorage(() => localStorage),
      // Persist token, user, AND isAuthenticated
      partialize: (state) => ({
        token: state.token,
        user: state.user,
        isAuthenticated: state.isAuthenticated,
      }),
      // Called when state is rehydrated from storage
      onRehydrateStorage: () => (state) => {
        // Verify token still exists in localStorage (in case it was cleared elsewhere)
        if (typeof window !== 'undefined') {
          const storedToken = localStorage.getItem('auth_token');
          if (state && !storedToken) {
            // Token was cleared from localStorage, clear auth state
            state.logout();
          }
        }
        // Mark as hydrated
        state?.setHydrated();
      },
    }
  )
);

// Projects store
interface ProjectsState {
  projects: Project[];
  selectedProject: Project | null;
  setProjects: (projects: Project[]) => void;
  selectProject: (project: Project | null) => void;
  addProject: (project: Project) => void;
  updateProject: (id: string, updates: Partial<Project>) => void;
}

export const useProjectsStore = create<ProjectsState>((set) => ({
  projects: [],
  selectedProject: null,
  setProjects: (projects) => set({ projects }),
  selectProject: (project) => set({ selectedProject: project }),
  addProject: (project) =>
    set((state) => ({ projects: [...state.projects, project] })),
  updateProject: (id, updates) =>
    set((state) => ({
      projects: state.projects.map((p) =>
        p.id === id ? { ...p, ...updates } : p
      ),
    })),
}));