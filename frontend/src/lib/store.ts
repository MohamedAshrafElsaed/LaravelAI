import {create} from 'zustand';
import {createJSONStorage, persist} from 'zustand/middleware';

// ============== USER TYPE ==============
interface User {
    id: string;
    username: string;
    email: string | null;
    avatar_url: string | null;
    name?: string;
}

// ============== PROJECT TYPE ==============
interface Project {
    id: string;
    name?: string;
    repo_full_name: string;
    repo_url: string;
    default_branch?: string;
    status: 'pending' | 'cloning' | 'indexing' | 'scanning' | 'analyzing' | 'ready' | 'error';
    indexed_files_count: number;
    laravel_version: string | null;
    health_score?: number;
    error_message?: string | null;
}

// ============== AUTH STORE ==============
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
                set({token, user, isAuthenticated: true});
            },
            logout: () => {
                localStorage.removeItem('auth_token');
                set({token: null, user: null, isAuthenticated: false});
            },
            setHydrated: () => set({isHydrated: true}),
        }),
        {
            name: 'auth-storage',
            storage: createJSONStorage(() => localStorage),
            partialize: (state) => ({
                token: state.token,
                user: state.user,
                isAuthenticated: state.isAuthenticated,
            }),
            onRehydrateStorage: () => (state) => {
                if (typeof window !== 'undefined') {
                    const storedToken = localStorage.getItem('auth_token');
                    if (state && !storedToken) {
                        state.logout();
                    }
                }
                state?.setHydrated();
            },
        }
    )
);

// ============== PROJECTS STORE ==============
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
    setProjects: (projects) => set({projects}),
    selectProject: (project) => set({selectedProject: project}),
    addProject: (project) =>
        set((state) => ({projects: [...state.projects, project]})),
    updateProject: (id, updates) =>
        set((state) => ({
            projects: state.projects.map((p) =>
                p.id === id ? {...p, ...updates} : p
            ),
        })),
}));

// ============== THEME STORE ==============
type Theme = 'light' | 'dark';

interface ThemeState {
    theme: Theme;
    setTheme: (theme: Theme) => void;
    toggleTheme: () => void;
}

export const useThemeStore = create<ThemeState>()(
    persist(
        (set, get) => ({
            theme: 'dark',
            setTheme: (theme) => {
                if (typeof window !== 'undefined') {
                    document.documentElement.classList.remove('light', 'dark');
                    document.documentElement.classList.add(theme);
                    document.documentElement.setAttribute('data-theme', theme);
                }
                set({theme});
            },
            toggleTheme: () => {
                const newTheme = get().theme === 'dark' ? 'light' : 'dark';
                get().setTheme(newTheme);
            },
        }),
        {
            name: 'theme-storage',
            storage: createJSONStorage(() => localStorage),
            onRehydrateStorage: () => (state) => {
                if (state && typeof window !== 'undefined') {
                    document.documentElement.classList.remove('light', 'dark');
                    document.documentElement.classList.add(state.theme);
                    document.documentElement.setAttribute('data-theme', state.theme);
                }
            },
        }
    )
);