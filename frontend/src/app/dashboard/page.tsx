'use client';

import {useCallback, useEffect, useMemo, useRef, useState} from 'react';
import {useRouter} from 'next/navigation';
import {useAuthStore, useProjectsStore} from '@/lib/store';
import {githubApi, projectsApi} from '@/lib/api';
import Sidebar, {Branch, Repo, Session, User} from '@/components/dashboard/Sidebar';
import WelcomeScreen from '@/components/dashboard/WelcomeScreen';
import SessionView, {SessionViewRef} from '@/components/dashboard/SessionView';

export default function DashboardPage() {
    const router = useRouter();
    const {isAuthenticated, isHydrated, user: authUser} = useAuthStore();
    const {projects, selectedProject, setProjects, selectProject} = useProjectsStore();

    // Refs
    const chatRef = useRef<SessionViewRef>(null);

    // UI State
    const [sidebarOpen, setSidebarOpen] = useState(false);
    const [currentView, setCurrentView] = useState<'welcome' | 'session'>('welcome');
    const [activeSessionId, setActiveSessionId] = useState<string | null>(null);

    // Data State
    const [repos, setRepos] = useState<Repo[]>([]);
    const [branches, setBranches] = useState<Branch[]>([
        {name: 'main', selected: true},
        {name: 'develop', selected: false},
    ]);
    const [sessions, setSessions] = useState<Session[]>([]);
    const [isLoading, setIsLoading] = useState(true);

    // User data with workspaces
    const [user, setUser] = useState<User>({
        email: authUser?.email || '',
        name: authUser?.name || authUser?.username || 'User',
        workspaces: [
            {name: 'Personal', plan: 'Free plan', selected: true},
        ],
    });

    // Derived state
    const selectedRepo = useMemo(() => repos.find((r) => r.selected), [repos]);

    // Auth check
    useEffect(() => {
        if (isHydrated && !isAuthenticated) {
            router.push('/');
        }
    }, [isHydrated, isAuthenticated, router]);

    // Load initial data
    useEffect(() => {
        if (isAuthenticated) {
            loadInitialData();
        }
    }, [isAuthenticated]);

    // Update user when auth user changes
    useEffect(() => {
        if (authUser) {
            setUser((prev) => ({
                ...prev,
                email: authUser.email || prev.email,
                name: authUser.name || authUser.username || prev.name,
            }));
        }
    }, [authUser]);

    // Load initial data
    const loadInitialData = async () => {
        setIsLoading(true);
        try {
            await Promise.all([loadProjects(), loadRepos()]);
        } catch (err) {
            console.error('Failed to load initial data:', err);
        } finally {
            setIsLoading(false);
        }
    };

    // Load projects
    const loadProjects = async () => {
        try {
            const response = await projectsApi.list();
            setProjects(response.data);
        } catch (err) {
            console.error('Failed to load projects:', err);
        }
    };

    // Load GitHub repos
    const loadRepos = async () => {
        try {
            const response = await githubApi.listRepos();
            const repoList: Repo[] = response.data.map((repo: any, index: number) => ({
                name: repo.name,
                owner: repo.owner?.login || repo.full_name?.split('/')[0] || '',
                selected: index === 0, // Select first repo by default
            }));
            setRepos(repoList);
        } catch (err) {
            console.error('Failed to load repos:', err);
        }
    };

    // Handle repo selection
    const handleSelectRepo = useCallback((repoName: string) => {
        setRepos((prev) =>
            prev.map((r) => ({
                ...r,
                selected: r.name === repoName,
            }))
        );

        // Find corresponding project
        const repo = repos.find((r) => r.name === repoName);
        if (repo) {
            const project = projects.find(
                (p) => p.repo_name === repo.name || p.repo_full_name === `${repo.owner}/${repo.name}`
            );
            if (project) {
                selectProject(project);
            }
        }

        // Reset session when repo changes
        setActiveSessionId(null);
        setCurrentView('welcome');
    }, [repos, projects, selectProject]);

    // Handle branch selection
    const handleSelectBranch = useCallback((branchName: string) => {
        setBranches((prev) =>
            prev.map((b) => ({
                ...b,
                selected: b.name === branchName,
            }))
        );
    }, []);

    // Handle session selection
    const handleSelectSession = useCallback((sessionId: string) => {
        setActiveSessionId(sessionId);
        setCurrentView('session');
        setSidebarOpen(false); // Close sidebar on mobile
    }, []);

    // Handle conversation change from chat
    const handleConversationChange = useCallback((conversationId: string | null) => {
        setActiveSessionId(conversationId);
        if (conversationId) {
            setCurrentView('session');
        }
    }, []);

    // Handle new chat
    const handleNewChat = useCallback(() => {
        setActiveSessionId(null);
        setCurrentView('welcome');
        chatRef.current?.startNewChat();
    }, []);

    // Handle suggestion click from welcome screen
    const handleSuggestionClick = useCallback((prompt: string) => {
        setCurrentView('session');
        // Small delay to ensure view has switched
        setTimeout(() => {
            chatRef.current?.sendMessage(prompt);
        }, 100);
    }, []);

    // Handle session deletion
    const handleDeleteSession = useCallback((sessionId: string) => {
        if (sessionId === activeSessionId) {
            setActiveSessionId(null);
            setCurrentView('welcome');
        }
    }, [activeSessionId]);

    // Loading state
    if (!isHydrated || isLoading) {
        return (
            <div className="flex items-center justify-center h-screen bg-[#141414]">
                <div className="flex flex-col items-center gap-4">
                    <div
                        className="animate-spin h-10 w-10 border-4 border-[#e07a5f] border-t-transparent rounded-full"/>
                    <p className="text-[#a1a1aa] text-sm">Loading Maestro AI...</p>
                </div>
            </div>
        );
    }

    // Get project ID for chat
    const projectId = selectedProject?.id;

    return (
        <div className="flex h-screen w-full overflow-hidden bg-[#141414]">
            {/* Mobile backdrop */}
            {sidebarOpen && (
                <div
                    className="fixed inset-0 z-40 bg-black/60 lg:hidden transition-opacity"
                    onClick={() => setSidebarOpen(false)}
                />
            )}

            {/* Sidebar */}
            <Sidebar
                appName="Maestro AI"
                repos={repos}
                branches={branches}
                sessions={sessions}
                user={user}
                mobileOpen={sidebarOpen}
                activeSessionId={activeSessionId}
                projectId={projectId}
                onCloseMobile={() => setSidebarOpen(false)}
                onSelectSession={handleSelectSession}
                onSelectRepo={handleSelectRepo}
                onSelectBranch={handleSelectBranch}
                onNewChat={handleNewChat}
                onDeleteSession={handleDeleteSession}
            />

            {/* Main content */}
            <main className="relative flex flex-1 flex-col overflow-hidden">
                {/* Mobile header */}
                <header className="flex h-12 items-center gap-3 border-b border-[#2b2b2b] bg-[#1b1b1b] px-4 lg:hidden">
                    <button
                        className="flex h-8 w-8 items-center justify-center rounded-md text-[#a1a1aa] transition-colors hover:bg-white/5"
                        onClick={() => setSidebarOpen(true)}
                    >
                        <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth="2"
                                d="M4 6h16M4 12h16M4 18h16"
                            />
                        </svg>
                    </button>
                    <span className="text-sm font-medium text-[#f3f4f6]">Maestro AI</span>
                    {selectedRepo && (
                        <span className="ml-auto text-xs text-[#666666]">
              {selectedRepo.owner}/{selectedRepo.name}
            </span>
                    )}
                </header>

                {/* Content area */}
                <div className="flex-1 overflow-hidden">
                    {!projectId ? (
                        // No project selected
                        <div className="flex items-center justify-center h-full">
                            <div className="text-center">
                                <div
                                    className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-[#202020] mb-4">
                                    <svg
                                        className="w-8 h-8 text-[#666666]"
                                        fill="none"
                                        stroke="currentColor"
                                        viewBox="0 0 24 24"
                                    >
                                        <path
                                            strokeLinecap="round"
                                            strokeLinejoin="round"
                                            strokeWidth="1.5"
                                            d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"
                                        />
                                    </svg>
                                </div>
                                <h3 className="text-lg font-medium text-[#E0E0DE] mb-2">No project selected</h3>
                                <p className="text-sm text-[#666666] max-w-xs">
                                    Select a repository from the sidebar to connect a project and start coding with AI
                                </p>
                            </div>
                        </div>
                    ) : currentView === 'welcome' ? (
                        // Welcome screen with suggestions
                        <WelcomeScreen
                            selectedRepo={selectedRepo}
                            onSuggestionClick={handleSuggestionClick}
                        />
                    ) : (
                        // Chat session view
                        <SessionView
                            ref={chatRef}
                            projectId={projectId}
                            conversationId={activeSessionId}
                            onConversationChange={handleConversationChange}
                        />
                    )}
                </div>
            </main>
        </div>
    );
}