'use client';

import { useEffect, useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import Link from 'next/link';
import { AnimatePresence, motion } from 'framer-motion';
import {
    FileCode,
    FolderKanban,
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
    MessageSquare,
} from 'lucide-react';
import { useThemeStore } from '@/lib/store';

interface NavItem {
    id: string;
    label: string;
    icon: React.ComponentType<{ size?: number; className?: string }>;
    shortcut: string;
    href: string;
}

interface DevSidebarProps {
    activeTab?: string;
    setActiveTab?: (tab: string) => void;
    mobileOpen?: boolean;
    onCloseMobile?: () => void;
}

export default function DevSidebar({
                                       activeTab: propActiveTab,
                                       setActiveTab,
                                       mobileOpen = false,
                                       onCloseMobile,
                                   }: DevSidebarProps) {
    const pathname = usePathname();
    const router = useRouter();
    const { theme, toggleTheme } = useThemeStore();
    const [collapsed, setCollapsed] = useState(false);

    // Navigation items with routes
    const navItems: NavItem[] = [
        { id: 'dashboard', label: 'Overview', icon: LayoutDashboard, shortcut: '⌘1', href: '/dashboard' },
        { id: 'projects', label: 'Projects', icon: FolderKanban, shortcut: '⌘2', href: '/dashboard/projects' },
        { id: 'chat', label: 'AI Chat', icon: MessageSquare, shortcut: '⌘3', href: '/dashboard/chat' },
        { id: 'files', label: 'Explorer', icon: FileCode, shortcut: '⌘4', href: '/dashboard/files' },
        { id: 'git', label: 'Source Control', icon: GitBranch, shortcut: '⌘5', href: '/dashboard/git' },
        { id: 'terminal', label: 'Terminal', icon: Terminal, shortcut: '⌘6', href: '/dashboard/terminal' },
    ];

    // Determine active tab from pathname or props
    const getActiveTab = () => {
        if (propActiveTab) return propActiveTab;
        const segments = pathname.split('/');
        const tab = segments[2];
        return tab || 'dashboard';
    };

    const activeTab = getActiveTab();

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

    // Keyboard shortcuts
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if ((e.metaKey || e.ctrlKey) && e.key >= '1' && e.key <= '6') {
                e.preventDefault();
                const index = parseInt(e.key) - 1;
                if (navItems[index]) {
                    router.push(navItems[index].href);
                    onCloseMobile?.();
                }
            }
            if ((e.metaKey || e.ctrlKey) && e.key === 'b') {
                e.preventDefault();
                setCollapsed(!collapsed);
            }
        };

        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [collapsed, router, onCloseMobile]);

    // Handle navigation
    const handleNavClick = (item: NavItem) => {
        if (setActiveTab) {
            setActiveTab(item.id);
        }
        onCloseMobile?.();
    };

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
                animate={{ width: collapsed ? 64 : 256 }}
                transition={{ duration: 0.2, ease: 'easeInOut' }}
                className={`
                    fixed inset-y-0 left-0 z-50
                    bg-[var(--color-bg-primary)] 
                    border-r border-[var(--color-border-subtle)]
                    flex flex-col h-full
                    transform transition-transform duration-300 ease-in-out
                    lg:relative lg:translate-x-0
                    ${mobileOpen ? 'translate-x-0' : '-translate-x-full'}
                `}
            >
                {/* Logo */}
                <div className="h-14 flex items-center justify-between px-4 border-b border-[var(--color-border-subtle)]">
                    <AnimatePresence mode="wait">
                        {!collapsed ? (
                            <motion.div
                                initial={{ opacity: 0 }}
                                animate={{ opacity: 1 }}
                                exit={{ opacity: 0 }}
                                className="flex items-center gap-2"
                            >
                                <Link href="/dashboard" className="flex items-center gap-2">
                                    <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-[var(--color-primary)] to-[var(--color-primary)]/70 flex items-center justify-center">
                                        <span className="text-white font-bold text-sm">M</span>
                                    </div>
                                    <div>
                                        <span className="font-bold text-[var(--color-text-primary)] tracking-tight">
                                            MAESTRO
                                        </span>
                                        <span className="text-[10px] ml-1 text-[var(--color-primary)] font-medium">
                                            AI
                                        </span>
                                    </div>
                                </Link>
                            </motion.div>
                        ) : (
                            <Link href="/dashboard">
                                <motion.div
                                    initial={{ opacity: 0 }}
                                    animate={{ opacity: 1 }}
                                    exit={{ opacity: 0 }}
                                    className="w-8 h-8 rounded-lg bg-gradient-to-br from-[var(--color-primary)] to-[var(--color-primary)]/70 flex items-center justify-center mx-auto"
                                >
                                    <span className="text-white font-bold text-sm">M</span>
                                </motion.div>
                            </Link>
                        )}
                    </AnimatePresence>

                    {/* Mobile close button */}
                    <button
                        onClick={onCloseMobile}
                        className="lg:hidden p-1.5 rounded-md hover:bg-[var(--color-bg-surface)] text-[var(--color-text-muted)]"
                    >
                        <X size={18} />
                    </button>
                </div>

                {/* Search - expanded */}
                <AnimatePresence>
                    {!collapsed && (
                        <motion.div
                            initial={{ opacity: 0, height: 0 }}
                            animate={{ opacity: 1, height: 'auto' }}
                            exit={{ opacity: 0, height: 0 }}
                            className="px-3 py-3 border-b border-[var(--color-border-subtle)]"
                        >
                            <button className="w-full flex items-center gap-2 px-3 py-2 text-sm text-[var(--color-text-dimmer)] bg-[var(--color-bg-surface)] border border-[var(--color-border-subtle)] rounded-lg hover:border-[var(--color-border-default)] hover:text-[var(--color-text-muted)] transition-colors">
                                <Search size={14} />
                                <span className="truncate">Search...</span>
                                <span className="ml-auto font-mono text-xs text-[var(--color-text-dimmer)] border border-[var(--color-border-subtle)] rounded px-1 flex-shrink-0">
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
                            <Search
                                size={18}
                                className="text-[var(--color-text-muted)] group-hover:text-[var(--color-primary)] transition-colors"
                            />
                        </button>
                    </div>
                )}

                {/* Navigation */}
                <nav className="flex-1 px-2 py-2 space-y-0.5 overflow-y-auto">
                    {navItems.map((item, index) => {
                        const isActive = activeTab === item.id;
                        return (
                            <motion.div
                                key={item.id}
                                initial={{ opacity: 0, x: -10 }}
                                animate={{ opacity: 1, x: 0 }}
                                transition={{ delay: index * 0.05 }}
                            >
                                <Link
                                    href={item.href}
                                    onClick={() => handleNavClick(item)}
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
                                            initial={{ opacity: 0 }}
                                            animate={{ opacity: 1 }}
                                        />
                                    )}
                                    <item.icon
                                        size={collapsed ? 20 : 16}
                                        className={`flex-shrink-0 ${collapsed ? '' : 'mr-3'} ${
                                            isActive
                                                ? 'text-[var(--color-primary)]'
                                                : 'text-[var(--color-text-dimmer)] group-hover:text-[var(--color-text-muted)]'
                                        }`}
                                    />
                                    <AnimatePresence>
                                        {!collapsed && (
                                            <>
                                                <motion.span
                                                    initial={{ opacity: 0 }}
                                                    animate={{ opacity: 1 }}
                                                    exit={{ opacity: 0 }}
                                                    className="truncate"
                                                >
                                                    {item.label}
                                                </motion.span>
                                                <motion.span
                                                    initial={{ opacity: 0 }}
                                                    animate={{ opacity: 1 }}
                                                    exit={{ opacity: 0 }}
                                                    className={`ml-auto font-mono text-[10px] flex-shrink-0 ${
                                                        isActive
                                                            ? 'text-[var(--color-primary)]/70'
                                                            : 'text-[var(--color-text-dimmer)]'
                                                    }`}
                                                >
                                                    {item.shortcut}
                                                </motion.span>
                                            </>
                                        )}
                                    </AnimatePresence>
                                </Link>
                            </motion.div>
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
                        title={collapsed ? 'Expand sidebar (⌘B)' : 'Collapse sidebar (⌘B)'}
                    >
                        {collapsed ? (
                            <PanelLeft size={20} className="text-[var(--color-text-dimmer)]" />
                        ) : (
                            <>
                                <PanelLeftClose size={16} className="mr-3 text-[var(--color-text-dimmer)]" />
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
                                <Sun
                                    size={collapsed ? 20 : 16}
                                    className={`${collapsed ? '' : 'mr-3'} text-[var(--color-text-dimmer)]`}
                                />
                                {!collapsed && <span>Light Mode</span>}
                            </>
                        ) : (
                            <>
                                <Moon
                                    size={collapsed ? 20 : 16}
                                    className={`${collapsed ? '' : 'mr-3'} text-[var(--color-text-dimmer)]`}
                                />
                                {!collapsed && <span>Dark Mode</span>}
                            </>
                        )}
                    </button>

                    {/* Settings */}
                    <Link
                        href="/dashboard/settings"
                        className={`w-full flex items-center px-3 py-2 text-sm text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)] rounded-sm hover:bg-[var(--color-bg-surface)] transition-colors ${
                            collapsed ? 'justify-center' : ''
                        } ${activeTab === 'settings' ? 'text-[var(--color-primary)] bg-[var(--color-primary-subtle)]' : ''}`}
                        title={collapsed ? 'Settings' : undefined}
                    >
                        <Settings
                            size={collapsed ? 20 : 16}
                            className={`${collapsed ? '' : 'mr-3'} text-[var(--color-text-dimmer)]`}
                        />
                        {!collapsed && <span>Settings</span>}
                    </Link>

                    {/* Status */}
                    <div
                        className={`mt-4 flex items-center text-[10px] text-[var(--color-text-dimmer)] font-mono px-3 ${
                            collapsed ? 'justify-center' : ''
                        }`}
                    >
                        <span className="w-2 h-2 rounded-full bg-emerald-400 mr-2 animate-pulse" />
                        {!collapsed && <span>System Online</span>}
                    </div>
                </div>
            </motion.aside>
        </>
    );
}