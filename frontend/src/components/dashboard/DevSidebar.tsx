'use client';

import {useEffect, useState} from 'react';
import {AnimatePresence, motion} from 'framer-motion';
import {
    FileCode,
    GitBranch,
    LayoutDashboard,
    Moon,
    PanelLeft,
    PanelLeftClose,
    Search,
    Settings,
    Sun,
    Terminal,
    X,
} from 'lucide-react';
import {useThemeStore} from '@/lib/store';

interface DevSidebarProps {
    activeTab: string;
    setActiveTab: (tab: string) => void;
    mobileOpen?: boolean;
    onCloseMobile?: () => void;
}

export default function DevSidebar({
                                       activeTab,
                                       setActiveTab,
                                       mobileOpen = false,
                                       onCloseMobile,
                                   }: DevSidebarProps) {
    const {theme, toggleTheme} = useThemeStore();
    const [collapsed, setCollapsed] = useState(false);

    // Persist collapsed state
    useEffect(() => {
        const saved = localStorage.getItem('sidebar-collapsed');
        if (saved) {
            setCollapsed(JSON.parse(saved));
        }
    }, []);

    useEffect(() => {
        localStorage.setItem('sidebar-collapsed', JSON.stringify(collapsed));
    }, [collapsed]);

    const navItems = [
        {id: 'dashboard', label: 'Overview', icon: LayoutDashboard, shortcut: '⌘1'},
        {id: 'files', label: 'Explorer', icon: FileCode, shortcut: '⌘2'},
        {id: 'git', label: 'Source Control', icon: GitBranch, shortcut: '⌘3'},
        {id: 'terminal', label: 'Terminal', icon: Terminal, shortcut: '⌘4'},
    ];

    const sidebarWidth = collapsed ? 'w-16' : 'w-64';

    return (
        <>
            {/* Mobile overlay */}
            {mobileOpen && (
                <div
                    className="fixed inset-0 z-40 bg-black/50 lg:hidden"
                    onClick={onCloseMobile}
                />
            )}

            <motion.aside
                initial={false}
                animate={{width: collapsed ? 64 : 256}}
                transition={{duration: 0.2, ease: 'easeInOut'}}
                className={`
          fixed inset-y-0 left-0 z-50
          bg-[var(--color-bg-primary)] 
          border-r border-[var(--color-border-subtle)]
          flex flex-col h-full
          transform transition-transform duration-300 ease-in-out
          lg:relative lg:translate-x-0
          ${mobileOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
        `}
            >
                {/* Header */}
                <div
                    className="h-14 flex items-center px-4 border-b border-[var(--color-border-subtle)] justify-between">
                    <div className="flex items-center overflow-hidden">
                        <div className="w-3 h-3 bg-[var(--color-primary)] rounded-sm flex-shrink-0"/>
                        <AnimatePresence>
                            {!collapsed && (
                                <motion.span
                                    initial={{opacity: 0, width: 0}}
                                    animate={{opacity: 1, width: 'auto'}}
                                    exit={{opacity: 0, width: 0}}
                                    transition={{duration: 0.2}}
                                    className="ml-2 font-bold text-[var(--color-text-primary)] tracking-tight whitespace-nowrap overflow-hidden"
                                >
                                    DEV_CONSOLE
                                </motion.span>
                            )}
                        </AnimatePresence>
                    </div>

                    <div className="flex items-center gap-1">
                        <AnimatePresence>
                            {!collapsed && (
                                <motion.span
                                    initial={{opacity: 0}}
                                    animate={{opacity: 1}}
                                    exit={{opacity: 0}}
                                    className="text-[10px] font-mono text-[var(--color-text-dimmer)]"
                                >
                                    v2.4.0
                                </motion.span>
                            )}
                        </AnimatePresence>

                        {/* Mobile close button */}
                        {onCloseMobile && (
                            <button
                                onClick={onCloseMobile}
                                className="lg:hidden p-1 rounded hover:bg-[var(--color-bg-hover)]"
                            >
                                <X className="h-5 w-5 text-[var(--color-text-muted)]"/>
                            </button>
                        )}
                    </div>
                </div>

                {/* Search - only show when expanded */}
                <AnimatePresence>
                    {!collapsed && (
                        <motion.div
                            initial={{opacity: 0, height: 0}}
                            animate={{opacity: 1, height: 'auto'}}
                            exit={{opacity: 0, height: 0}}
                            transition={{duration: 0.2}}
                            className="p-4 overflow-hidden"
                        >
                            <button
                                className="w-full bg-[var(--color-bg-surface)] border border-[var(--color-border-subtle)] text-[var(--color-text-muted)] px-3 py-2 rounded-sm flex items-center text-sm hover:border-[var(--color-border-default)] transition-colors group">
                                <Search size={14}
                                        className="mr-2 group-hover:text-[var(--color-primary)] transition-colors flex-shrink-0"/>
                                <span className="truncate">Search...</span>
                                <span
                                    className="ml-auto font-mono text-xs text-[var(--color-text-dimmer)] border border-[var(--color-border-subtle)] rounded px-1 flex-shrink-0">
                  ⌘K
                </span>
                            </button>
                        </motion.div>
                    )}
                </AnimatePresence>

                {/* Search icon when collapsed */}
                {collapsed && (
                    <div className="p-2">
                        <button
                            className="w-full p-3 flex justify-center rounded-sm hover:bg-[var(--color-bg-surface)] transition-colors group"
                            title="Search (⌘K)"
                        >
                            <Search size={18}
                                    className="text-[var(--color-text-muted)] group-hover:text-[var(--color-primary)] transition-colors"/>
                        </button>
                    </div>
                )}

                {/* Navigation */}
                <nav className="flex-1 px-2 py-2 space-y-0.5">
                    {navItems.map((item, index) => {
                        const isActive = activeTab === item.id;
                        return (
                            <motion.button
                                key={item.id}
                                initial={{opacity: 0, x: -10}}
                                animate={{opacity: 1, x: 0}}
                                transition={{delay: index * 0.05}}
                                onClick={() => setActiveTab(item.id)}
                                title={collapsed ? `${item.label} (${item.shortcut})` : undefined}
                                className={`w-full flex items-center px-3 py-2 text-sm rounded-sm transition-all relative group ${
                                    collapsed ? 'justify-center' : ''
                                } ${
                                    isActive
                                        ? 'text-[var(--color-primary)] bg-[var(--color-primary-subtle)]'
                                        : 'text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-bg-surface)]'
                                }`}
                            >
                                {isActive && (
                                    <motion.div
                                        layoutId="activeTab"
                                        className="absolute left-0 w-0.5 h-full bg-[var(--color-primary)]"
                                        initial={{opacity: 0}}
                                        animate={{opacity: 1}}
                                    />
                                )}
                                <item.icon
                                    size={collapsed ? 20 : 16}
                                    className={`flex-shrink-0 ${collapsed ? '' : 'mr-3'} ${
                                        isActive ? 'text-[var(--color-primary)]' : 'text-[var(--color-text-dimmer)] group-hover:text-[var(--color-text-muted)]'
                                    }`}
                                />
                                <AnimatePresence>
                                    {!collapsed && (
                                        <>
                                            <motion.span
                                                initial={{opacity: 0}}
                                                animate={{opacity: 1}}
                                                exit={{opacity: 0}}
                                                className="truncate"
                                            >
                                                {item.label}
                                            </motion.span>
                                            <motion.span
                                                initial={{opacity: 0}}
                                                animate={{opacity: 1}}
                                                exit={{opacity: 0}}
                                                className={`ml-auto font-mono text-[10px] flex-shrink-0 ${
                                                    isActive ? 'text-[var(--color-primary)]/70' : 'text-[var(--color-text-dimmer)]'
                                                }`}
                                            >
                                                {item.shortcut}
                                            </motion.span>
                                        </>
                                    )}
                                </AnimatePresence>
                            </motion.button>
                        );
                    })}
                </nav>

                {/* Footer */}
                <div className="p-2 border-t border-[var(--color-border-subtle)]">
                    {/* Collapse Toggle */}
                    <button
                        onClick={() => setCollapsed(!collapsed)}
                        className={`w-full flex items-center px-3 py-2 text-sm text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)] rounded-sm hover:bg-[var(--color-bg-surface)] transition-colors ${
                            collapsed ? 'justify-center' : ''
                        }`}
                        title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
                    >
                        {collapsed ? (
                            <PanelLeft size={20} className="text-[var(--color-text-dimmer)]"/>
                        ) : (
                            <>
                                <PanelLeftClose size={16} className="mr-3 text-[var(--color-text-dimmer)]"/>
                                <span>Collapse</span>
                            </>
                        )}
                    </button>

                    {/* Theme Toggle */}
                    <button
                        onClick={toggleTheme}
                        className={`w-full flex items-center px-3 py-2 text-sm text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)] rounded-sm hover:bg-[var(--color-bg-surface)] transition-colors ${
                            collapsed ? 'justify-center' : ''
                        }`}
                        title={collapsed ? (theme === 'dark' ? 'Light Mode' : 'Dark Mode') : undefined}
                    >
                        {theme === 'dark' ? (
                            <>
                                <Sun size={collapsed ? 20 : 16}
                                     className={`${collapsed ? '' : 'mr-3'} text-[var(--color-text-dimmer)]`}/>
                                {!collapsed && <span>Light Mode</span>}
                            </>
                        ) : (
                            <>
                                <Moon size={collapsed ? 20 : 16}
                                      className={`${collapsed ? '' : 'mr-3'} text-[var(--color-text-dimmer)]`}/>
                                {!collapsed && <span>Dark Mode</span>}
                            </>
                        )}
                    </button>

                    {/* Settings */}
                    <button
                        className={`w-full flex items-center px-3 py-2 text-sm text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)] rounded-sm hover:bg-[var(--color-bg-surface)] transition-colors ${
                            collapsed ? 'justify-center' : ''
                        }`}
                        title={collapsed ? 'Settings' : undefined}
                    >
                        <Settings size={collapsed ? 20 : 16}
                                  className={`${collapsed ? '' : 'mr-3'} text-[var(--color-text-dimmer)]`}/>
                        {!collapsed && <span>Settings</span>}
                    </button>

                    {/* Status */}
                    <div
                        className={`mt-4 flex items-center text-[10px] text-[var(--color-text-dimmer)] font-mono px-3 ${
                            collapsed ? 'justify-center' : 'justify-between'
                        }`}>
                        <div className="flex items-center">
                            <div className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse"/>
                            {!collapsed && <span className="ml-2">SYSTEM ONLINE</span>}
                        </div>
                        {!collapsed && <span>42ms</span>}
                    </div>
                </div>
            </motion.aside>
        </>
    );
}