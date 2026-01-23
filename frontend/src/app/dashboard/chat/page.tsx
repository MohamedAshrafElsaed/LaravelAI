// frontend/src/app/dashboard/chat/page.tsx
'use client';

import React, {useCallback, useEffect, useRef, useState} from 'react';
import {useRouter} from 'next/navigation';
import {AlertCircle, Bot, Clock, FolderOpen, Loader2, MessageSquare, Plus, Search, Trash2} from 'lucide-react';
import {useAuthStore} from '@/lib/store';
import type {Conversation, Project} from '@/lib/api';
import {chatApi, getErrorMessage, projectsApi} from '@/lib/api';
import {ChatModule, type ChatModuleRef} from '@/components/chat';

export default function DashboardChatPage() {
    const router = useRouter();
    const {isAuthenticated, isHydrated} = useAuthStore();
    const chatRef = useRef<ChatModuleRef>(null);

    // State
    const [mounted, setMounted] = useState(false);
    const [projects, setProjects] = useState<Project[]>([]);
    const [projectsLoading, setProjectsLoading] = useState(true);
    const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
    const [conversations, setConversations] = useState<Conversation[]>([]);
    const [conversationsLoading, setConversationsLoading] = useState(false);
    const [currentConversationId, setCurrentConversationId] = useState<string | null>(null);
    const [searchQuery, setSearchQuery] = useState('');
    const [deleteLoading, setDeleteLoading] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        setMounted(true);
    }, []);

    // Auth check
    useEffect(() => {
        if (isHydrated && !isAuthenticated) {
            router.push('/');
        }
    }, [isHydrated, isAuthenticated, router]);

    // Load projects
    useEffect(() => {
        async function loadProjects() {
            console.log('[ChatPage] Loading projects...');
            try {
                const response = await projectsApi.list();
                console.log('[ChatPage] All projects:', response.data?.length || 0);

                const readyProjects = response.data.filter(p => p.status === 'ready');
                console.log('[ChatPage] Ready projects:', readyProjects.length);

                if (readyProjects.length === 0) {
                    console.log('[ChatPage] No ready projects found. Project statuses:',
                        response.data.map(p => ({name: p.name, status: p.status}))
                    );
                }

                setProjects(readyProjects);

                // Auto-select first ready project or restore from localStorage
                const savedProjectId = localStorage.getItem('chat_selected_project');
                console.log('[ChatPage] Saved project ID:', savedProjectId);

                if (savedProjectId && readyProjects.find(p => p.id === savedProjectId)) {
                    console.log('[ChatPage] Restoring saved project');
                    setSelectedProjectId(savedProjectId);
                } else if (readyProjects.length > 0) {
                    console.log('[ChatPage] Selecting first ready project:', readyProjects[0].id);
                    setSelectedProjectId(readyProjects[0].id);
                }
            } catch (err) {
                console.error('[ChatPage] Failed to load projects:', err);
                setError(getErrorMessage(err));
            } finally {
                setProjectsLoading(false);
            }
        }

        if (isAuthenticated) {
            loadProjects();
        }
    }, [isAuthenticated]);

    // Load conversations when project changes
    const loadConversations = useCallback(async (projectId: string) => {
        console.log('[ChatPage] Loading conversations for project:', projectId);

        // Debug: Show the full URL being called
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
        console.log('[ChatPage] API URL:', apiUrl);
        console.log('[ChatPage] Full conversations URL:', `${apiUrl}/projects/${projectId}/conversations`);

        setConversationsLoading(true);
        setError(null);

        try {
            const response = await chatApi.listConversations(projectId);
            console.log('[ChatPage] Loaded conversations:', response.data?.length || 0);
            setConversations(response.data || []);
        } catch (err: any) {
            // Log the full error for debugging
            console.error('[ChatPage] Failed to load conversations:', {
                error: err,
                message: err?.message,
                status: err?.status || err?.response?.status,
                code: err?.code,
                data: err?.response?.data,
            });

            // Check if it's a 404 - might mean the endpoint doesn't exist on backend
            if (err?.status === 404 || err?.response?.status === 404 || err?.code === 'HTTP_404') {
                console.warn('[ChatPage] 404 error - The conversations endpoint may not exist on your backend.');
                console.warn('[ChatPage] Expected endpoint: GET /projects/{project_id}/conversations');
            }

            // Don't show error - just start with empty conversations
            // This allows the chat to work even if conversations endpoint has issues
            setConversations([]);
        } finally {
            setConversationsLoading(false);
        }
    }, []);

    useEffect(() => {
        if (selectedProjectId) {
            console.log('[ChatPage] Project changed to:', selectedProjectId);
            localStorage.setItem('chat_selected_project', selectedProjectId);
            loadConversations(selectedProjectId);
            // Reset conversation when project changes
            setCurrentConversationId(null);
            // Only reset chat if ref is available
            if (chatRef.current) {
                chatRef.current.startNewChat();
            }
        }
    }, [selectedProjectId, loadConversations]);

    // Handle conversation change from ChatModule
    const handleConversationChange = useCallback((id: string | null) => {
        setCurrentConversationId(id);
        if (id && selectedProjectId) {
            loadConversations(selectedProjectId);
        }
    }, [selectedProjectId, loadConversations]);

    // Select conversation
    const selectConversation = (convId: string) => {
        setCurrentConversationId(convId);
    };

    // Start new chat
    const handleNewChat = () => {
        chatRef.current?.startNewChat();
        setCurrentConversationId(null);
    };

    // Delete conversation
    const handleDeleteConversation = async (convId: string, e: React.MouseEvent) => {
        e.stopPropagation();
        if (!selectedProjectId) return;
        if (!confirm('Delete this conversation?')) return;

        setDeleteLoading(convId);
        try {
            await chatApi.deleteConversation(selectedProjectId, convId);
            setConversations(prev => prev.filter(c => c.id !== convId));
            if (currentConversationId === convId) {
                handleNewChat();
            }
        } catch (err) {
            console.error('Failed to delete conversation:', err);
        } finally {
            setDeleteLoading(null);
        }
    };

    // Filter conversations
    const filteredConversations = searchQuery
        ? conversations.filter(c =>
            c.title?.toLowerCase().includes(searchQuery.toLowerCase()) ||
            c.last_message?.toLowerCase().includes(searchQuery.toLowerCase())
        )
        : conversations;

    // Format time
    const formatTime = (dateStr: string) => {
        const date = new Date(dateStr);
        const now = new Date();
        const diffMs = now.getTime() - date.getTime();
        const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

        if (diffDays === 0) {
            return date.toLocaleTimeString('en-US', {hour: '2-digit', minute: '2-digit'});
        } else if (diffDays === 1) {
            return 'Yesterday';
        } else if (diffDays < 7) {
            return date.toLocaleDateString('en-US', {weekday: 'short'});
        } else {
            return date.toLocaleDateString('en-US', {month: 'short', day: 'numeric'});
        }
    };

    const selectedProject = projects.find(p => p.id === selectedProjectId);

    if (!mounted || !isHydrated) {
        return (
            <div className="flex h-full items-center justify-center bg-[var(--color-bg-primary)]">
                <Loader2 className="h-8 w-8 animate-spin text-[var(--color-primary)]"/>
            </div>
        );
    }

    if (projectsLoading) {
        return (
            <div className="flex h-full items-center justify-center bg-[var(--color-bg-primary)]">
                <div className="text-center">
                    <Loader2 className="h-8 w-8 animate-spin text-[var(--color-primary)] mx-auto mb-4"/>
                    <p className="text-[var(--color-text-muted)]">Loading projects...</p>
                </div>
            </div>
        );
    }

    if (projects.length === 0) {
        return (
            <div className="flex h-full items-center justify-center bg-[var(--color-bg-primary)]">
                <div className="text-center max-w-md px-4">
                    <FolderOpen className="h-16 w-16 text-[var(--color-text-muted)] mx-auto mb-4"/>
                    <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-2">
                        No Projects Ready
                    </h2>
                    <p className="text-[var(--color-text-muted)] mb-6">
                        You need at least one indexed project to start chatting with the AI.
                    </p>
                    <button
                        onClick={() => router.push('/dashboard/projects')}
                        className="px-4 py-2 rounded-lg bg-[var(--color-primary)] text-white font-medium hover:bg-[var(--color-primary-hover)] transition-colors"
                    >
                        Go to Projects
                    </button>
                </div>
            </div>
        );
    }

    return (
        <div className="flex h-full bg-[var(--color-bg-primary)] text-[var(--color-text-primary)]">
            {/* Sidebar */}
            <aside
                className="w-72 flex-shrink-0 flex flex-col border-r border-[var(--color-border-subtle)] bg-[var(--color-bg-surface)]">
                {/* Project Selector */}
                <div className="p-3 border-b border-[var(--color-border-subtle)]">
                    <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-2">
                        Project
                    </label>
                    <select
                        value={selectedProjectId || ''}
                        onChange={(e) => setSelectedProjectId(e.target.value)}
                        className="w-full px-3 py-2 rounded-lg bg-[var(--color-bg-elevated)] border border-[var(--color-border-subtle)] text-sm text-[var(--color-text-primary)] focus:outline-none focus:border-[var(--color-primary)]"
                    >
                        {projects.map(p => (
                            <option key={p.id} value={p.id}>
                                {p.name}
                            </option>
                        ))}
                    </select>
                    {selectedProject && (
                        <p className="mt-1 text-xs text-[var(--color-text-muted)]">
                            {selectedProject.indexed_files_count} files indexed
                        </p>
                    )}
                </div>

                {/* New Chat Button */}
                <div className="p-3 border-b border-[var(--color-border-subtle)]">
                    <button
                        onClick={handleNewChat}
                        className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-[var(--color-primary)] text-white font-medium hover:bg-[var(--color-primary-hover)] transition-colors"
                    >
                        <Plus className="h-4 w-4"/>
                        New Chat
                    </button>
                </div>

                {/* Search */}
                <div className="px-3 py-2">
                    <div className="relative">
                        <Search
                            className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[var(--color-text-muted)]"/>
                        <input
                            type="text"
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            placeholder="Search conversations..."
                            className="w-full pl-9 pr-3 py-2 rounded-lg bg-[var(--color-bg-elevated)] border border-[var(--color-border-subtle)] text-sm text-[var(--color-text-primary)] placeholder-[var(--color-text-muted)] focus:outline-none focus:border-[var(--color-primary)]"
                        />
                    </div>
                </div>

                {/* Conversations List */}
                <div className="flex-1 overflow-y-auto px-2 py-1">
                    {conversationsLoading ? (
                        <div className="flex items-center justify-center py-8">
                            <Loader2 className="h-5 w-5 animate-spin text-[var(--color-text-muted)]"/>
                        </div>
                    ) : filteredConversations.length === 0 ? (
                        <div className="flex flex-col items-center justify-center py-8 px-4 text-center">
                            <Bot className="h-10 w-10 text-[var(--color-text-muted)] mb-2"/>
                            <p className="text-sm text-[var(--color-text-muted)]">
                                {searchQuery ? 'No matching conversations' : 'No conversations yet'}
                            </p>
                            <p className="text-xs text-[var(--color-text-dimmer)] mt-1">
                                Start a new chat to begin
                            </p>
                        </div>
                    ) : (
                        <div className="space-y-1">
                            {filteredConversations.map((conv) => (
                                <div
                                    key={conv.id}
                                    onClick={() => selectConversation(conv.id)}
                                    role="button"
                                    tabIndex={0}
                                    onKeyDown={(e) => e.key === 'Enter' && selectConversation(conv.id)}
                                    className={`w-full flex items-start gap-3 p-3 rounded-lg text-left transition-colors group cursor-pointer ${
                                        currentConversationId === conv.id
                                            ? 'bg-[var(--color-primary)]/10 border border-[var(--color-primary)]/30'
                                            : 'hover:bg-[var(--color-bg-hover)] border border-transparent'
                                    }`}
                                >
                                    <MessageSquare className={`h-4 w-4 mt-0.5 flex-shrink-0 ${
                                        currentConversationId === conv.id
                                            ? 'text-[var(--color-primary)]'
                                            : 'text-[var(--color-text-muted)]'
                                    }`}/>
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center justify-between gap-2">
                <span className={`text-sm font-medium truncate ${
                    currentConversationId === conv.id
                        ? 'text-[var(--color-primary)]'
                        : 'text-[var(--color-text-primary)]'
                }`}>
                    {conv.title || 'New conversation'}
                </span>
                                            <span className="text-xs text-[var(--color-text-muted)] flex-shrink-0">
                    {formatTime(conv.updated_at)}
                </span>
                                        </div>
                                        <p className="text-xs text-[var(--color-text-muted)] truncate mt-0.5">
                                            {conv.last_message || 'No messages'}
                                        </p>
                                        <span className="text-[10px] text-[var(--color-text-dimmer)]">
                {conv.message_count} message{conv.message_count !== 1 ? 's' : ''}
            </span>
                                    </div>
                                    <button
                                        onClick={(e) => handleDeleteConversation(conv.id, e)}
                                        className="p-1 rounded opacity-0 group-hover:opacity-100 hover:bg-red-500/20 text-[var(--color-text-muted)] hover:text-red-400 transition-all"
                                        title="Delete conversation"
                                    >
                                        {deleteLoading === conv.id ? (
                                            <Loader2 className="h-4 w-4 animate-spin"/>
                                        ) : (
                                            <Trash2 className="h-4 w-4"/>
                                        )}
                                    </button>
                                </div>
                            ))}
                        </div>
                    )}
                </div>

                {/* Footer */}
                <div className="p-3 border-t border-[var(--color-border-subtle)]">
                    <div className="flex items-center gap-2 text-xs text-[var(--color-text-muted)]">
                        <Clock className="h-3.5 w-3.5"/>
                        <span>{conversations.length} conversation{conversations.length !== 1 ? 's' : ''}</span>
                    </div>
                </div>
            </aside>

            {/* Main Chat Area */}
            <main className="flex-1 flex flex-col min-w-0">
                {selectedProjectId ? (
                    <ChatModule
                        ref={chatRef}
                        projectId={selectedProjectId}
                        initialConversationId={currentConversationId}
                        onConversationChange={handleConversationChange}
                        requirePlanApproval={true}
                        className="flex-1"
                    />
                ) : (
                    <div className="flex-1 flex items-center justify-center">
                        <div className="text-center">
                            <AlertCircle className="h-12 w-12 text-amber-400 mx-auto mb-4"/>
                            <p className="text-[var(--color-text-muted)]">Select a project to start chatting</p>
                        </div>
                    </div>
                )}
            </main>
        </div>
    );
}