'use client';

import {useEffect, useState} from 'react';
import {
    ChevronDown,
    GitBranch,
    Loader2,
    LogOut,
    MessageSquare,
    MoreHorizontal,
    Plus,
    Settings,
    Trash2,
    X,
} from 'lucide-react';
import {chatApi} from '@/lib/api';

// ============== TYPES ==============
export interface Repo {
    name: string;
    owner: string;
    selected: boolean;
}

export interface Branch {
    name: string;
    selected: boolean;
}

export interface Session {
    id: string;
    title: string;
    project: string;
    time: string;
    active: boolean;
    metrics: { additions: number; deletions: number } | null;
}

export interface Workspace {
    name: string;
    plan: string;
    selected: boolean;
}

export interface User {
    email: string;
    name: string;
    workspaces: Workspace[];
}

interface SidebarProps {
    appName: string;
    repos: Repo[];
    branches: Branch[];
    sessions: Session[];
    user: User;
    mobileOpen: boolean;
    activeSessionId?: string | null;
    projectId?: string;
    onCloseMobile: () => void;
    onSelectSession: (id: string) => void;
    onSelectRepo: (name: string) => void;
    onSelectBranch: (name: string) => void;
    onNewChat?: () => void;
    onDeleteSession?: (id: string) => void;
}

// ============== SUB-COMPONENTS ==============

// Dropdown component for selections
function Dropdown({
                      label,
                      value,
                      options,
                      onSelect,
                      icon: Icon,
                  }: {
    label: string;
    value: string;
    options: { value: string; label: string; sublabel?: string }[];
    onSelect: (value: string) => void;
    icon?: React.ComponentType<{ className?: string }>;
}) {
    const [isOpen, setIsOpen] = useState(false);

    return (
        <div className="relative">
            <button
                onClick={() => setIsOpen(!isOpen)}
                className="flex w-full items-center justify-between rounded-lg border border-[#2b2b2b] bg-[#202020] px-3 py-2 text-left transition-colors hover:border-[#3a3a3a]"
            >
                <div className="flex items-center gap-2">
                    {Icon && <Icon className="h-4 w-4 text-[#a1a1aa]"/>}
                    <div>
                        <div className="text-[10px] uppercase tracking-wider text-[#666666]">{label}</div>
                        <div className="text-sm font-medium text-[#E0E0DE]">{value}</div>
                    </div>
                </div>
                <ChevronDown
                    className={`h-4 w-4 text-[#666666] transition-transform ${isOpen ? 'rotate-180' : ''}`}
                />
            </button>

            {isOpen && (
                <>
                    <div
                        className="fixed inset-0 z-10"
                        onClick={() => setIsOpen(false)}
                    />
                    <div
                        className="absolute left-0 right-0 top-full z-20 mt-1 rounded-lg border border-[#2b2b2b] bg-[#1b1b1b] py-1 shadow-xl">
                        {options.map((option) => (
                            <button
                                key={option.value}
                                onClick={() => {
                                    onSelect(option.value);
                                    setIsOpen(false);
                                }}
                                className={`flex w-full items-center px-3 py-2 text-left transition-colors hover:bg-white/5 ${
                                    option.value === value ? 'bg-white/5' : ''
                                }`}
                            >
                                <div>
                                    <div className="text-sm text-[#E0E0DE]">{option.label}</div>
                                    {option.sublabel && (
                                        <div className="text-xs text-[#666666]">{option.sublabel}</div>
                                    )}
                                </div>
                                {option.value === value && (
                                    <div className="ml-auto h-2 w-2 rounded-full bg-[#e07a5f]"/>
                                )}
                            </button>
                        ))}
                    </div>
                </>
            )}
        </div>
    );
}

// Session item component
function SessionItem({
                         session,
                         isActive,
                         onClick,
                         onDelete,
                     }: {
    session: Session;
    isActive: boolean;
    onClick: () => void;
    onDelete?: () => void;
}) {
    const [showMenu, setShowMenu] = useState(false);

    return (
        <div className="group relative">
            <button
                onClick={onClick}
                className={`flex w-full items-start gap-3 rounded-lg px-3 py-2.5 text-left transition-colors ${
                    isActive
                        ? 'bg-[#e07a5f]/10 border border-[#e07a5f]/30'
                        : 'hover:bg-white/5 border border-transparent'
                }`}
            >
                <MessageSquare
                    className={`mt-0.5 h-4 w-4 flex-shrink-0 ${
                        isActive ? 'text-[#e07a5f]' : 'text-[#666666]'
                    }`}
                />
                <div className="min-w-0 flex-1">
                    <div
                        className={`truncate text-sm ${
                            isActive ? 'font-medium text-[#e07a5f]' : 'text-[#E0E0DE]'
                        }`}
                    >
                        {session.title}
                    </div>
                    <div className="flex items-center gap-2 text-xs text-[#666666]">
                        <span>{session.time}</span>
                        {session.metrics && (
                            <>
                                <span>•</span>
                                <span className="text-[#4ade80]">+{session.metrics.additions}</span>
                                <span className="text-[#f87171]">-{session.metrics.deletions}</span>
                            </>
                        )}
                    </div>
                </div>
            </button>

            {/* More options button */}
            <button
                onClick={(e) => {
                    e.stopPropagation();
                    setShowMenu(!showMenu);
                }}
                className="absolute right-2 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-white/10 transition-all"
            >
                <MoreHorizontal className="h-4 w-4 text-[#666666]"/>
            </button>

            {/* Context menu */}
            {showMenu && (
                <>
                    <div className="fixed inset-0 z-10" onClick={() => setShowMenu(false)}/>
                    <div
                        className="absolute right-0 top-full z-20 mt-1 rounded-lg border border-[#2b2b2b] bg-[#1b1b1b] py-1 shadow-xl min-w-[120px]">
                        {onDelete && (
                            <button
                                onClick={(e) => {
                                    e.stopPropagation();
                                    onDelete();
                                    setShowMenu(false);
                                }}
                                className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[#f87171] hover:bg-white/5"
                            >
                                <Trash2 className="h-4 w-4"/>
                                Delete
                            </button>
                        )}
                    </div>
                </>
            )}
        </div>
    );
}

// ============== MAIN COMPONENT ==============

export default function Sidebar({
                                    appName,
                                    repos,
                                    branches,
                                    sessions: initialSessions,
                                    user,
                                    mobileOpen,
                                    activeSessionId,
                                    projectId,
                                    onCloseMobile,
                                    onSelectSession,
                                    onSelectRepo,
                                    onSelectBranch,
                                    onNewChat,
                                    onDeleteSession,
                                }: SidebarProps) {
    const [sessions, setSessions] = useState<Session[]>(initialSessions);
    const [isLoadingSessions, setIsLoadingSessions] = useState(false);
    const [showUserMenu, setShowUserMenu] = useState(false);

    const selectedRepo = repos.find((r) => r.selected);
    const selectedBranch = branches.find((b) => b.selected);
    const selectedWorkspace = user.workspaces.find((w) => w.selected);

    // Load sessions from API when projectId changes
    useEffect(() => {
        if (projectId) {
            loadSessions(projectId);
        }
    }, [projectId]);

    const loadSessions = async (projId: string) => {
        setIsLoadingSessions(true);
        try {
            const response = await chatApi.listConversations(projId);
            const loadedSessions: Session[] = response.data.map((conv: any) => ({
                id: conv.id,
                title: conv.title || 'Untitled conversation',
                project: selectedRepo?.name || '',
                time: formatRelativeTime(new Date(conv.updated_at)),
                active: conv.id === activeSessionId,
                metrics: null,
            }));
            setSessions(loadedSessions);
        } catch (err) {
            console.error('Failed to load sessions:', err);
        } finally {
            setIsLoadingSessions(false);
        }
    };

    const handleDeleteSession = async (sessionId: string) => {
        if (!projectId) return;
        try {
            await chatApi.deleteConversation(projectId, sessionId);
            setSessions((prev) => prev.filter((s) => s.id !== sessionId));
            onDeleteSession?.(sessionId);
        } catch (err) {
            console.error('Failed to delete session:', err);
        }
    };

    // Format relative time
    function formatRelativeTime(date: Date): string {
        const now = new Date();
        const diffMs = now.getTime() - date.getTime();
        const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

        if (diffDays === 0) return 'Today';
        if (diffDays === 1) return 'Yesterday';
        if (diffDays < 7) return date.toLocaleDateString('en-US', {weekday: 'short'});
        return date.toLocaleDateString('en-US', {month: 'short', day: 'numeric'});
    }

    return (
        <aside
            className={`fixed inset-y-0 left-0 z-50 w-72 transform bg-[#1b1b1b] transition-transform duration-300 lg:relative lg:translate-x-0 ${
                mobileOpen ? 'translate-x-0' : '-translate-x-full'
            }`}
        >
            <div className="flex h-full flex-col">
                {/* Header */}
                <div className="flex h-14 items-center justify-between border-b border-[#2b2b2b] px-4">
                    <span className="text-lg font-semibold text-[#E0E0DE]">{appName}</span>
                    <button
                        onClick={onCloseMobile}
                        className="rounded-md p-1.5 text-[#a1a1aa] hover:bg-white/5 lg:hidden"
                    >
                        <X className="h-5 w-5"/>
                    </button>
                </div>

                {/* Repo & Branch Selection */}
                <div className="border-b border-[#2b2b2b] p-4 space-y-3">
                    <Dropdown
                        label="Repository"
                        value={selectedRepo ? `${selectedRepo.owner}/${selectedRepo.name}` : 'Select repo'}
                        options={repos.map((r) => ({
                            value: r.name,
                            label: r.name,
                            sublabel: r.owner,
                        }))}
                        onSelect={onSelectRepo}
                        icon={GitBranch}
                    />

                    <Dropdown
                        label="Branch"
                        value={selectedBranch?.name || 'Select branch'}
                        options={branches.map((b) => ({
                            value: b.name,
                            label: b.name,
                        }))}
                        onSelect={onSelectBranch}
                    />
                </div>

                {/* Sessions */}
                <div className="flex-1 overflow-y-auto">
                    <div className="p-4">
                        <div className="mb-3 flex items-center justify-between">
                            <h3 className="text-xs font-medium uppercase tracking-wider text-[#666666]">
                                Sessions
                            </h3>
                            {onNewChat && (
                                <button
                                    onClick={onNewChat}
                                    className="flex items-center gap-1 rounded-md px-2 py-1 text-xs text-[#a1a1aa] hover:bg-white/5 hover:text-[#E0E0DE] transition-colors"
                                    title="New Chat"
                                >
                                    <Plus className="h-3.5 w-3.5"/>
                                    New
                                </button>
                            )}
                        </div>

                        {isLoadingSessions ? (
                            <div className="flex items-center justify-center py-8">
                                <Loader2 className="h-5 w-5 animate-spin text-[#a1a1aa]"/>
                            </div>
                        ) : sessions.length === 0 ? (
                            <div className="py-8 text-center">
                                <MessageSquare className="mx-auto h-8 w-8 text-[#3a3a3a] mb-2"/>
                                <p className="text-sm text-[#666666]">No conversations yet</p>
                                <p className="text-xs text-[#4a4a4a] mt-1">Start a new chat to begin</p>
                            </div>
                        ) : (
                            <div className="space-y-1">
                                {sessions.map((session) => (
                                    <SessionItem
                                        key={session.id}
                                        session={session}
                                        isActive={session.id === activeSessionId}
                                        onClick={() => onSelectSession(session.id)}
                                        onDelete={() => handleDeleteSession(session.id)}
                                    />
                                ))}
                            </div>
                        )}
                    </div>
                </div>

                {/* User Profile */}
                <div className="border-t border-[#2b2b2b] p-4">
                    <div className="relative">
                        <button
                            onClick={() => setShowUserMenu(!showUserMenu)}
                            className="flex w-full items-center gap-3 rounded-lg px-2 py-2 hover:bg-white/5 transition-colors"
                        >
                            {/* Avatar */}
                            <div
                                className="flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-br from-[#e07a5f] to-[#9333EA]">
                <span className="text-sm font-medium text-white">
                  {user.name
                      .split(' ')
                      .map((n) => n[0])
                      .join('')
                      .toUpperCase()
                      .slice(0, 2)}
                </span>
                            </div>
                            <div className="flex-1 text-left">
                                <div className="text-sm font-medium text-[#E0E0DE]">{user.name}</div>
                                <div className="text-xs text-[#666666]">{selectedWorkspace?.name}</div>
                            </div>
                            <ChevronDown
                                className={`h-4 w-4 text-[#666666] transition-transform ${
                                    showUserMenu ? 'rotate-180' : ''
                                }`}
                            />
                        </button>

                        {/* User menu dropdown */}
                        {showUserMenu && (
                            <>
                                <div
                                    className="fixed inset-0 z-10"
                                    onClick={() => setShowUserMenu(false)}
                                />
                                <div
                                    className="absolute bottom-full left-0 right-0 z-20 mb-2 rounded-lg border border-[#2b2b2b] bg-[#1b1b1b] py-1 shadow-xl">
                                    {/* Workspaces */}
                                    <div className="px-3 py-2 border-b border-[#2b2b2b]">
                                        <div
                                            className="text-xs font-medium uppercase tracking-wider text-[#666666] mb-2">
                                            Workspaces
                                        </div>
                                        {user.workspaces.map((workspace) => (
                                            <button
                                                key={workspace.name}
                                                className={`flex w-full items-center justify-between px-2 py-1.5 rounded text-left hover:bg-white/5 ${
                                                    workspace.selected ? 'bg-white/5' : ''
                                                }`}
                                            >
                                                <div>
                                                    <div className="text-sm text-[#E0E0DE]">{workspace.name}</div>
                                                    <div className="text-xs text-[#666666]">{workspace.plan}</div>
                                                </div>
                                                {workspace.selected && (
                                                    <div className="h-2 w-2 rounded-full bg-[#e07a5f]"/>
                                                )}
                                            </button>
                                        ))}
                                    </div>

                                    {/* Actions */}
                                    <button
                                        className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[#a1a1aa] hover:bg-white/5">
                                        <Settings className="h-4 w-4"/>
                                        Settings
                                    </button>
                                    <button
                                        className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[#f87171] hover:bg-white/5">
                                        <LogOut className="h-4 w-4"/>
                                        Sign out
                                    </button>
                                </div>
                            </>
                        )}
                    </div>
                </div>
            </div>
        </aside>
    );
}