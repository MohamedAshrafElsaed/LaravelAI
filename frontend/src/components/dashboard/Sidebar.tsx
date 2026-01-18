'use client';

import {ChevronDown, GitBranch, Plus, Search, Settings, X} from 'lucide-react';
import type {Branch, Repo, Session, User} from '@/app/dashboard/page';

interface SidebarProps {
    appName: string;
    repos: Repo[];
    branches: Branch[];
    sessions: Session[];
    user: User;
    mobileOpen: boolean;
    onCloseMobile: () => void;
    onSelectSession: (id: string) => void;
    onSelectRepo: (name: string) => void;
    onSelectBranch: (name: string) => void;
}

export default function Sidebar({
                                    appName,
                                    repos,
                                    branches,
                                    sessions,
                                    user,
                                    mobileOpen,
                                    onCloseMobile,
                                    onSelectSession,
                                    onSelectRepo,
                                    onSelectBranch,
                                }: SidebarProps) {
    const selectedRepo = repos.find((r) => r.selected);
    const selectedBranch = branches.find((b) => b.selected);
    const selectedWorkspace = user.workspaces.find((w) => w.selected);

    return (
        <aside
            className={`
        fixed inset-y-0 left-0 z-50 w-72 bg-[#1b1b1b] border-r border-[#2b2b2b] flex flex-col
        transform transition-transform duration-200 ease-in-out
        lg:relative lg:transform-none
        ${mobileOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
      `}
        >
            {/* Header */}
            <div className="flex h-12 items-center justify-between border-b border-[#2b2b2b] px-4">
                <div className="flex items-center gap-2">
                    <div
                        className="w-6 h-6 bg-gradient-to-br from-[#E07850] to-[#C65D3D] rounded-md flex items-center justify-center">
                        <svg className="w-4 h-4 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                             strokeWidth="2">
                            <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
                        </svg>
                    </div>
                    <span className="text-sm font-semibold text-[#f3f4f6]">{appName}</span>
                </div>
                <button
                    className="lg:hidden flex h-7 w-7 items-center justify-center rounded-md text-[#a1a1aa] hover:bg-white/5"
                    onClick={onCloseMobile}
                >
                    <X className="h-4 w-4"/>
                </button>
            </div>

            {/* Workspace selector */}
            <div className="p-3 border-b border-[#2b2b2b]">
                <button
                    className="w-full flex items-center justify-between rounded-lg bg-[#252525] px-3 py-2 text-left hover:bg-[#2a2a2a] transition-colors">
                    <div className="flex items-center gap-2">
                        <div
                            className="w-6 h-6 rounded-md bg-gradient-to-br from-[#E07850] to-[#C65D3D] flex items-center justify-center text-[10px] font-bold text-white">
                            {selectedWorkspace?.name.charAt(0)}
                        </div>
                        <div>
                            <p className="text-[12px] font-medium text-[#f3f4f6]">{selectedWorkspace?.name}</p>
                            <p className="text-[10px] text-[#666666]">{selectedWorkspace?.plan}</p>
                        </div>
                    </div>
                    <ChevronDown className="h-4 w-4 text-[#666666]"/>
                </button>
            </div>

            {/* Repository selector */}
            <div className="p-3 border-b border-[#2b2b2b]">
                <label
                    className="text-[10px] font-medium text-[#666666] uppercase tracking-wider mb-2 block">Repository</label>
                <button
                    className="w-full flex items-center justify-between rounded-lg border border-[#2b2b2b] bg-[#1b1b1b] px-3 py-2 text-left hover:border-[#3a3a3a] transition-colors">
          <span className="text-[12px] text-[#a1a1aa] truncate">
            {selectedRepo ? `${selectedRepo.owner}/${selectedRepo.name}` : 'Select repository'}
          </span>
                    <ChevronDown className="h-4 w-4 text-[#666666] flex-shrink-0"/>
                </button>

                <div className="flex items-center gap-2 mt-2">
                    <button
                        className="flex-1 flex items-center justify-center gap-1 rounded-lg border border-[#2b2b2b] px-2 py-1.5 text-[11px] text-[#a1a1aa] hover:bg-[#252525] transition-colors">
                        <GitBranch className="h-3 w-3"/>
                        {selectedBranch?.name || 'Branch'}
                    </button>
                    <button
                        className="flex items-center justify-center rounded-lg border border-[#2b2b2b] px-2 py-1.5 text-[#a1a1aa] hover:bg-[#252525] transition-colors">
                        <Settings className="h-3.5 w-3.5"/>
                    </button>
                </div>
            </div>

            {/* Search */}
            <div className="p-3 border-b border-[#2b2b2b]">
                <div className="relative">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-[#666666]"/>
                    <input
                        type="text"
                        placeholder="Search sessions..."
                        className="w-full rounded-lg border border-[#2b2b2b] bg-[#1b1b1b] pl-9 pr-3 py-2 text-[12px] text-[#f3f4f6] placeholder-[#666666] focus:border-[#E07850] focus:outline-none transition-colors"
                    />
                </div>
            </div>

            {/* Sessions list */}
            <div className="flex-1 overflow-y-auto">
                <div className="p-3">
                    <div className="flex items-center justify-between mb-2">
                        <span
                            className="text-[10px] font-medium text-[#666666] uppercase tracking-wider">Sessions</span>
                        <button
                            className="flex h-5 w-5 items-center justify-center rounded-md text-[#666666] hover:bg-white/5 hover:text-[#a1a1aa] transition-colors">
                            <Plus className="h-3.5 w-3.5"/>
                        </button>
                    </div>

                    <div className="space-y-1">
                        {sessions.map((session) => (
                            <button
                                key={session.id}
                                onClick={() => onSelectSession(session.id)}
                                className={`
                  w-full flex flex-col gap-1 rounded-lg px-3 py-2.5 text-left transition-colors
                  ${session.active ? 'bg-[#E07850]/10 border border-[#E07850]/30' : 'hover:bg-[#252525]'}
                `}
                            >
                <span
                    className={`text-[12px] font-medium truncate ${session.active ? 'text-[#E07850]' : 'text-[#f3f4f6]'}`}>
                  {session.title}
                </span>
                                <div className="flex items-center gap-2">
                                    <span className="text-[10px] text-[#666666]">{session.project}</span>
                                    <span className="text-[10px] text-[#666666]">•</span>
                                    <span className="text-[10px] text-[#666666]">{session.time}</span>
                                    {session.metrics && (
                                        <>
                                            <span className="text-[10px] text-[#666666]">•</span>
                                            <span
                                                className="text-[10px] text-[#22C55E]">+{session.metrics.additions}</span>
                                            <span
                                                className="text-[10px] text-[#EF4444]">-{session.metrics.deletions}</span>
                                        </>
                                    )}
                                </div>
                            </button>
                        ))}
                    </div>
                </div>
            </div>

            {/* User section */}
            <div className="border-t border-[#2b2b2b] p-3">
                <button
                    className="w-full flex items-center gap-3 rounded-lg px-2 py-2 hover:bg-[#252525] transition-colors">
                    <div
                        className="w-8 h-8 rounded-full bg-gradient-to-br from-[#E07850] to-[#C65D3D] flex items-center justify-center text-[12px] font-bold text-white">
                        {user.name.split(' ').map((n) => n[0]).join('')}
                    </div>
                    <div className="flex-1 text-left">
                        <p className="text-[12px] font-medium text-[#f3f4f6]">{user.name}</p>
                        <p className="text-[10px] text-[#666666] truncate">{user.email}</p>
                    </div>
                    <ChevronDown className="h-4 w-4 text-[#666666]"/>
                </button>
            </div>
        </aside>
    );
}