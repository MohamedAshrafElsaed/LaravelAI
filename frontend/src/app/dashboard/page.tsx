'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import { Menu, RefreshCw } from 'lucide-react';
import { useAuthStore, useThemeStore } from '@/lib/store';
import { useDashboard } from '@/hooks/useDashboardData';

// Components
import DevSidebar from '@/components/dashboard/DevSidebar';
import ActivityFeed from '@/components/dashboard/ActivityFeed';
import DataTable from '@/components/dashboard/DataTable';
import DevChatPanel from '@/components/dashboard/DevChatPanel';
import DiffPreview from '@/components/dashboard/DiffPreview';
import DevFileExplorer from '@/components/dashboard/DevFileExplorer';
import EmptyState from '@/components/dashboard/EmptyState';
import StatCard from '@/components/dashboard/StatCard';
import ProjectSelector from '@/components/dashboard/ProjectSelector';

export default function DashboardPage() {
    const router = useRouter();
    const { isAuthenticated, isHydrated } = useAuthStore();
    const { theme } = useThemeStore();

    const [activeTab, setActiveTab] = useState('dashboard');
    const [mobileOpen, setMobileOpen] = useState(false);
    const [mounted, setMounted] = useState(false);

    // Fetch dashboard data
    const {
        projects,
        selectedProject,
        stats,
        changes,
        activities,
        health,
        loading,
        changesLoading,
        activitiesLoading,
        setSelectedProjectId,
        refetch,
    } = useDashboard();

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

    // Transform git changes to deployments format for DataTable
    const deployments = changes.map(change => ({
        id: change.id,
        project: selectedProject?.name || 'Unknown',
        branch: change.branch_name,
        status: mapChangeStatus(change.status),
        commit: change.commit_hash?.slice(0, 6) || 'pending',
        age: formatTimeAgo(change.created_at),
        environment: change.base_branch === 'main' ? 'Production' : 'Preview',
    }));

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
                setActiveTab={setActiveTab}
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
            DEV_CONSOLE
          </span>
                </div>

                <AnimatePresence mode="wait">
                    {/* Dashboard View */}
                    {activeTab === 'dashboard' && (
                        <motion.div
                            key="dashboard"
                            initial={{ opacity: 0, y: 10 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -10 }}
                            className="flex-1 p-6 overflow-y-auto"
                        >
                            <div className="grid grid-cols-12 gap-6">
                                {/* Header */}
                                <div className="col-span-12 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-2">
                                    <div>
                                        <h1 className="text-2xl font-bold text-[var(--color-text-primary)] mb-1">
                                            Overview
                                        </h1>
                                        <p className="text-[var(--color-text-dimmer)] text-sm">
                                            System status and recent activity
                                        </p>
                                    </div>

                                    <div className="flex items-center gap-3">
                                        {/* Project Selector */}
                                        <ProjectSelector
                                            projects={projects}
                                            selectedProject={selectedProject}
                                            onSelect={setSelectedProjectId}
                                            loading={loading}
                                        />

                                        {/* Refresh Button */}
                                        <button
                                            onClick={refetch}
                                            disabled={loading}
                                            className="p-2 rounded-lg border border-[var(--color-border-subtle)] hover:bg-[var(--color-bg-surface)] transition-colors disabled:opacity-50"
                                            title="Refresh data"
                                        >
                                            <RefreshCw className={`h-4 w-4 text-[var(--color-text-muted)] ${loading ? 'animate-spin' : ''}`} />
                                        </button>
                                    </div>
                                </div>

                                {/* Main Content Area */}
                                <div className="col-span-12 lg:col-span-8 space-y-6">
                                    {/* Stat Cards */}
                                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                                        <StatCard
                                            label="Total Projects"
                                            value={projects.length.toString()}
                                            change={selectedProject ? `${selectedProject.indexed_files_count} files` : ''}
                                            changeType="neutral"
                                            delay={0}
                                        />
                                        <StatCard
                                            label="API Requests (Today)"
                                            value={stats?.today.requests.toString() || '0'}
                                            change={stats ? `$${stats.today.cost.toFixed(4)}` : '$0'}
                                            changeType="neutral"
                                            delay={0.1}
                                        />
                                        <StatCard
                                            label="Health Score"
                                            value={health?.score?.toString() || selectedProject?.health_score?.toString() || 'N/A'}
                                            change={health?.production_ready ? 'Production Ready' : 'Needs Review'}
                                            changeType={health?.production_ready ? 'positive' : 'neutral'}
                                            delay={0.2}
                                        />
                                    </div>

                                    {/* Data Table - Git Changes */}
                                    {changesLoading ? (
                                        <div className="flex items-center justify-center h-48 border border-[var(--color-border-subtle)] rounded-sm">
                                            <div className="h-6 w-6 animate-spin rounded-full border-2 border-[var(--color-primary)]/30 border-t-[var(--color-primary)]" />
                                        </div>
                                    ) : deployments.length > 0 ? (
                                        <DataTable deployments={deployments} title="Recent Changes" />
                                    ) : (
                                        <div className="border border-[var(--color-border-subtle)] rounded-sm p-8">
                                            <EmptyState type="generic" message="No code changes yet" />
                                        </div>
                                    )}

                                    {/* Diff Preview - Show latest change with files */}
                                    {changes.length > 0 && changes[0].files_changed && changes[0].files_changed.length > 0 && (
                                        <div>
                                            <h3 className="text-sm font-semibold text-[var(--color-text-primary)] mb-3">
                                                Latest Change
                                            </h3>
                                            <DiffPreview
                                                fileName={changes[0].files_changed[0].file}
                                                additions={changes[0].files_changed.filter(f => f.action === 'create' || f.action === 'modify').length}
                                                deletions={changes[0].files_changed.filter(f => f.action === 'delete').length}
                                            />
                                        </div>
                                    )}
                                </div>

                                {/* Right Sidebar */}
                                <div className="col-span-12 lg:col-span-4 flex flex-col gap-6">
                                    {/* Activity Feed */}
                                    <div className="bg-[var(--color-bg-surface)]/30 border border-[var(--color-border-subtle)] rounded-sm p-4 h-[400px]">
                                        {activitiesLoading ? (
                                            <div className="flex items-center justify-center h-full">
                                                <div className="h-6 w-6 animate-spin rounded-full border-2 border-[var(--color-primary)]/30 border-t-[var(--color-primary)]" />
                                            </div>
                                        ) : activities.length > 0 ? (
                                            <ActivityFeed activities={activities} />
                                        ) : (
                                            <EmptyState type="generic" message="No recent activity" />
                                        )}
                                    </div>

                                    {/* Chat Panel */}
                                    <div className="border border-[var(--color-border-subtle)] rounded-sm overflow-hidden h-[350px]">
                                        <DevChatPanel projectId={selectedProject?.id} />
                                    </div>
                                </div>
                            </div>
                        </motion.div>
                    )}

                    {/* Files View */}
                    {activeTab === 'files' && (
                        <motion.div
                            key="files"
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            className="flex-1 flex h-full"
                        >
                            <div className="w-64 border-r border-[var(--color-border-subtle)]">
                                <DevFileExplorer projectId={selectedProject?.id} />
                            </div>
                            <div className="flex-1 flex items-center justify-center bg-[var(--color-bg-surface)]">
                                <EmptyState type="files" message="Select a file to view contents" />
                            </div>
                        </motion.div>
                    )}

                    {/* Git / Terminal View */}
                    {(activeTab === 'git' || activeTab === 'terminal') && (
                        <motion.div
                            key="other"
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            className="flex-1 flex items-center justify-center"
                        >
                            <EmptyState
                                type="generic"
                                message={activeTab === 'git' ? 'Source Control not connected' : 'Terminal not available'}
                                action={{
                                    label: activeTab === 'git' ? 'Connect Repository' : 'Open Terminal',
                                    onClick: () => console.log(`${activeTab} action clicked`),
                                }}
                            />
                        </motion.div>
                    )}
                </AnimatePresence>
            </main>
        </div>
    );
}

// Helper functions
function mapChangeStatus(status: string): 'ready' | 'building' | 'error' | 'queued' {
    switch (status) {
        case 'merged':
        case 'pr_merged':
        case 'applied':
            return 'ready';
        case 'pending':
        case 'pr_created':
            return 'building';
        case 'rolled_back':
        case 'discarded':
            return 'error';
        default:
            return 'queued';
    }
}

function formatTimeAgo(dateString: string): string {
    const date = new Date(dateString);
    const now = new Date();
    const seconds = Math.floor((now.getTime() - date.getTime()) / 1000);

    if (seconds < 60) return `${seconds}s ago`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
    return `${Math.floor(seconds / 86400)}d ago`;
}