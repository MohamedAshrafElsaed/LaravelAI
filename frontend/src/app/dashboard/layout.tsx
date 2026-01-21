'use client';

import { useState, useEffect } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { Menu } from 'lucide-react';
import { useAuthStore, useThemeStore } from '@/lib/store';
import DevSidebar from '@/components/dashboard/DevSidebar';

export default function DashboardLayout({
                                            children,
                                        }: {
    children: React.ReactNode;
}) {
    const router = useRouter();
    const pathname = usePathname();
    const { isAuthenticated, isHydrated } = useAuthStore();
    const { theme } = useThemeStore();

    const [mobileOpen, setMobileOpen] = useState(false);
    const [mounted, setMounted] = useState(false);

    // Get active tab from pathname
    const getActiveTab = () => {
        const segments = pathname.split('/');
        const tab = segments[2]; // /dashboard/[tab]
        return tab || 'dashboard';
    };

    const activeTab = getActiveTab();

    // Handle tab change - navigate to route
    const handleTabChange = (tab: string) => {
        if (tab === 'dashboard') {
            router.push('/dashboard');
        } else {
            router.push(`/dashboard/${tab}`);
        }
        setMobileOpen(false);
    };

    useEffect(() => {
        setMounted(true);
    }, []);

    useEffect(() => {
        if (mounted) {
            document.documentElement.classList.remove('light', 'dark');
            document.documentElement.classList.add(theme);
            document.documentElement.setAttribute('data-theme', theme);
        }
    }, [theme, mounted]);

    // Auth check
    useEffect(() => {
        if (isHydrated && !isAuthenticated) {
            router.push('/');
        }
    }, [isHydrated, isAuthenticated, router]);

    if (!mounted) {
        return (
            <div className="flex h-screen items-center justify-center bg-[var(--color-bg-primary)]">
                <div className="h-8 w-8 animate-spin rounded-full border-4 border-[var(--color-primary)]/30 border-t-[var(--color-primary)]" />
            </div>
        );
    }

    return (
        <div className="flex h-screen w-full bg-[var(--color-bg-primary)] text-[var(--color-text-primary)] overflow-hidden font-sans selection:bg-[var(--color-primary)] selection:text-white">
            <DevSidebar
                activeTab={activeTab}
                setActiveTab={handleTabChange}
                mobileOpen={mobileOpen}
                onCloseMobile={() => setMobileOpen(false)}
            />

            <main className="flex-1 flex flex-col min-w-0">
                {/* Mobile Header */}
                <div className="lg:hidden flex items-center h-14 px-4 border-b border-[var(--color-border-subtle)] bg-[var(--color-bg-surface)]">
                    <button
                        onClick={() => setMobileOpen(true)}
                        className="p-2 rounded-lg hover:bg-[var(--color-bg-hover)]"
                    >
                        <Menu className="h-5 w-5 text-[var(--color-text-muted)]" />
                    </button>
                    <span className="ml-3 font-semibold text-[var(--color-text-primary)]">
                        MAESTRO AI
                    </span>
                </div>

                {/* Page Content */}
                {children}
            </main>
        </div>
    );
}