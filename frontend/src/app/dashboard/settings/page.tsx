// frontend/src/app/dashboard/settings/page.tsx
'use client';

import {motion} from 'framer-motion';
import {Bell, Database, LogOut, Moon, Shield, Sun, User} from 'lucide-react';
import {useAuthStore, useThemeStore} from '@/lib/store';
import {useRouter} from 'next/navigation';

export default function SettingsRoutePage() {
    const router = useRouter();
    const {user, logout} = useAuthStore();
    const {theme, toggleTheme} = useThemeStore();

    const handleLogout = () => {
        logout();
        router.push('/');
    };

    return (
        <motion.div
            initial={{opacity: 0}}
            animate={{opacity: 1}}
            exit={{opacity: 0}}
            className="flex-1 p-6 overflow-y-auto"
        >
            <div className="max-w-2xl mx-auto">
                {/* Header */}
                <div className="mb-8">
                    <h1 className="text-2xl font-bold text-[var(--color-text-primary)] mb-1">
                        Settings
                    </h1>
                    <p className="text-[var(--color-text-dimmer)] text-sm">
                        Manage your account and preferences
                    </p>
                </div>

                {/* Settings Sections */}
                <div className="space-y-6">
                    {/* Profile Section */}
                    <div
                        className="bg-[var(--color-bg-surface)] border border-[var(--color-border-subtle)] rounded-xl overflow-hidden">
                        <div className="px-6 py-4 border-b border-[var(--color-border-subtle)]">
                            <h2 className="text-sm font-semibold text-[var(--color-text-primary)] flex items-center gap-2">
                                <User className="w-4 h-4"/>
                                Profile
                            </h2>
                        </div>
                        <div className="p-6">
                            <div className="flex items-center gap-4">
                                {user?.avatar_url ? (
                                    <img
                                        src={user.avatar_url}
                                        alt={user.username}
                                        className="w-16 h-16 rounded-full border-2 border-[var(--color-border-subtle)]"
                                    />
                                ) : (
                                    <div
                                        className="w-16 h-16 rounded-full bg-[var(--color-primary-subtle)] flex items-center justify-center">
                                        <User className="w-8 h-8 text-[var(--color-primary)]"/>
                                    </div>
                                )}
                                <div>
                                    <p className="font-medium text-[var(--color-text-primary)]">
                                        {user?.name || user?.username || 'User'}
                                    </p>
                                    <p className="text-sm text-[var(--color-text-muted)]">
                                        @{user?.username}
                                    </p>
                                    {user?.email && (
                                        <p className="text-sm text-[var(--color-text-dimmer)]">
                                            {user.email}
                                        </p>
                                    )}
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Appearance Section */}
                    <div
                        className="bg-[var(--color-bg-surface)] border border-[var(--color-border-subtle)] rounded-xl overflow-hidden">
                        <div className="px-6 py-4 border-b border-[var(--color-border-subtle)]">
                            <h2 className="text-sm font-semibold text-[var(--color-text-primary)] flex items-center gap-2">
                                {theme === 'dark' ? <Moon className="w-4 h-4"/> : <Sun className="w-4 h-4"/>}
                                Appearance
                            </h2>
                        </div>
                        <div className="p-6">
                            <div className="flex items-center justify-between">
                                <div>
                                    <p className="font-medium text-[var(--color-text-primary)]">Theme</p>
                                    <p className="text-sm text-[var(--color-text-dimmer)]">
                                        Switch between light and dark mode
                                    </p>
                                </div>
                                <button
                                    onClick={toggleTheme}
                                    className="flex items-center gap-2 px-4 py-2 bg-[var(--color-bg-primary)] border border-[var(--color-border-subtle)] rounded-lg hover:bg-[var(--color-bg-hover)] transition-colors"
                                >
                                    {theme === 'dark' ? (
                                        <>
                                            <Sun className="w-4 h-4"/>
                                            <span>Light</span>
                                        </>
                                    ) : (
                                        <>
                                            <Moon className="w-4 h-4"/>
                                            <span>Dark</span>
                                        </>
                                    )}
                                </button>
                            </div>
                        </div>
                    </div>

                    {/* Notifications Section */}
                    <div
                        className="bg-[var(--color-bg-surface)] border border-[var(--color-border-subtle)] rounded-xl overflow-hidden">
                        <div className="px-6 py-4 border-b border-[var(--color-border-subtle)]">
                            <h2 className="text-sm font-semibold text-[var(--color-text-primary)] flex items-center gap-2">
                                <Bell className="w-4 h-4"/>
                                Notifications
                            </h2>
                        </div>
                        <div className="p-6">
                            <p className="text-sm text-[var(--color-text-dimmer)]">
                                Notification settings coming soon...
                            </p>
                        </div>
                    </div>

                    {/* Security Section */}
                    <div
                        className="bg-[var(--color-bg-surface)] border border-[var(--color-border-subtle)] rounded-xl overflow-hidden">
                        <div className="px-6 py-4 border-b border-[var(--color-border-subtle)]">
                            <h2 className="text-sm font-semibold text-[var(--color-text-primary)] flex items-center gap-2">
                                <Shield className="w-4 h-4"/>
                                Security
                            </h2>
                        </div>
                        <div className="p-6">
                            <p className="text-sm text-[var(--color-text-dimmer)]">
                                Connected via GitHub OAuth
                            </p>
                        </div>
                    </div>

                    {/* Data & Storage Section */}
                    <div
                        className="bg-[var(--color-bg-surface)] border border-[var(--color-border-subtle)] rounded-xl overflow-hidden">
                        <div className="px-6 py-4 border-b border-[var(--color-border-subtle)]">
                            <h2 className="text-sm font-semibold text-[var(--color-text-primary)] flex items-center gap-2">
                                <Database className="w-4 h-4"/>
                                Data & Storage
                            </h2>
                        </div>
                        <div className="p-6">
                            <p className="text-sm text-[var(--color-text-dimmer)]">
                                Data management settings coming soon...
                            </p>
                        </div>
                    </div>

                    {/* Logout Section */}
                    <div className="bg-[var(--color-bg-surface)] border border-red-500/20 rounded-xl overflow-hidden">
                        <div className="p-6">
                            <div className="flex items-center justify-between">
                                <div>
                                    <p className="font-medium text-[var(--color-text-primary)]">Sign Out</p>
                                    <p className="text-sm text-[var(--color-text-dimmer)]">
                                        Sign out of your account
                                    </p>
                                </div>
                                <button
                                    onClick={handleLogout}
                                    className="flex items-center gap-2 px-4 py-2 bg-red-500/10 text-red-400 border border-red-500/20 rounded-lg hover:bg-red-500/20 transition-colors"
                                >
                                    <LogOut className="w-4 h-4"/>
                                    <span>Sign Out</span>
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </motion.div>
    );
}