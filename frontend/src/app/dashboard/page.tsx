'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import { Menu, RefreshCw, FileCode, Copy, Check, X } from 'lucide-react';
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

// Helper to get language from file path
const getLanguageFromPath = (path: string): string => {
    const ext = path.split('.').pop()?.toLowerCase() || '';
    const langMap: Record<string, string> = {
        php: 'php', js: 'javascript', ts: 'typescript', jsx: 'jsx', tsx: 'tsx',
        json: 'json', css: 'css', scss: 'scss', yaml: 'yaml', yml: 'yaml',
        md: 'markdown', sql: 'sql', vue: 'vue', blade: 'blade',
    };
    return langMap[ext] || 'plaintext';
};

export default function DashboardPage() {
    const router = useRouter();
    const { isAuthenticated, isHydrated } = useAuthStore();
    const { theme } = useThemeStore();

    const [activeTab, setActiveTab] = useState('dashboard');
    const [mobileOpen, setMobileOpen] = useState(false);
    const [mounted, setMounted] = useState(false);

    // ✅ NEW: File viewer state
    const [selectedFile, setSelectedFile] = useState<string | null>(null);
    const [fileContent, setFileContent] = useState<string>('');
    const [copied, setCopied] = useState(false);

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

    // ✅ NEW: Handle file selection from DevFileExplorer
    const handleFileSelect = (filePath: string, content: string) => {
        console.log('[Dashboard] File selected:', filePath);
        setSelectedFile(filePath);
        setFileContent(content);
    };

    // ✅ NEW: Handle copy
    const handleCopy = async () => {
        try {
            await navigator.clipboard.writeText(fileContent);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        } catch (err) {
            console.error('Failed to copy:', err);
        }
    };

    // ✅ NEW: Handle close file
    const handleCloseFile = () => {
        setSelectedFile(null);
        setFileContent('');
    };

    // Clear selected file when switching projects
    useEffect(() => {
        setSelectedFile(null);
        setFileContent('');
    }, [selectedProject?.id]);

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

    // File content lines for line numbers
    const lines = fileContent.split('\n');
    const fileName = selectedFile?.split('/').pop() || '';

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

                    {/* ✅ FIXED: Files View with proper file content display */}
                    {activeTab === 'files' && (
                        <motion.div
                            key="files"
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            className="flex-1 flex h-full overflow-hidden"
                        >
                            {/* File Tree Sidebar */}
                            <div className="w-64 flex-shrink-0 border-r border-[var(--color-border-subtle)] overflow-hidden">
                                {selectedProject?.id ? (
                                    <DevFileExplorer
                                        projectId={selectedProject.id}
                                        onFileSelect={handleFileSelect}
                                        selectedFile={selectedFile}
                                    />
                                ) : (
                                    <div className="flex items-center justify-center h-full p-4">
                                        <EmptyState type="generic" message="Select a project first" />
                                    </div>
                                )}
                            </div>

                            {/* File Content Viewer */}
                            <div className="flex-1 flex flex-col bg-[var(--color-bg-surface)] overflow-hidden">
                                {selectedFile ? (
                                    <>
                                        {/* File Header */}
                                        <div className="flex items-center justify-between px-4 py-2 bg-[var(--color-bg-primary)] border-b border-[var(--color-border-subtle)]">
                                            <div className="flex items-center gap-2 min-w-0">
                                                <FileCode className="h-4 w-4 text-[var(--color-text-muted)]" />
                                                <span className="text-sm font-medium text-[var(--color-text-primary)]">
                                                    {fileName}
                                                </span>
                                                <span className="text-xs text-[var(--color-text-dimmer)] truncate">
                                                    {selectedFile}
                                                </span>
                                            </div>
                                            <div className="flex items-center gap-1">
                                                <span className="px-2 py-0.5 text-xs bg-[var(--color-bg-hover)] text-[var(--color-text-muted)] rounded">
                                                    {getLanguageFromPath(selectedFile)}
                                                </span>
                                                <button
                                                    onClick={handleCopy}
                                                    className="p-1.5 hover:bg-[var(--color-bg-hover)] rounded transition-colors"
                                                    title="Copy"
                                                >
                                                    {copied ? (
                                                        <Check className="h-4 w-4 text-green-400" />
                                                    ) : (
                                                        <Copy className="h-4 w-4 text-[var(--color-text-muted)]" />
                                                    )}
                                                </button>
                                                <button
                                                    onClick={handleCloseFile}
                                                    className="p-1.5 hover:bg-[var(--color-bg-hover)] rounded transition-colors"
                                                    title="Close"
                                                >
                                                    <X className="h-4 w-4 text-[var(--color-text-muted)]" />
                                                </button>
                                            </div>
                                        </div>

                                        {/* Code Content */}
                                        <div className="flex-1 overflow-auto">
                                            <div className="flex min-h-full">
                                                {/* Line Numbers */}
                                                <div className="flex-shrink-0 py-4 pr-2 pl-4 bg-[var(--color-bg-primary)] border-r border-[var(--color-border-subtle)] select-none sticky left-0">
                                                    {lines.map((_, i) => (
                                                        <div
                                                            key={i}
                                                            className="text-right text-xs font-mono text-[var(--color-text-dimmer)] leading-6 px-2"
                                                        >
                                                            {i + 1}
                                                        </div>
                                                    ))}
                                                </div>
                                                {/* Code */}
                                                <pre className="flex-1 p-4 overflow-x-auto font-mono text-sm leading-6 text-[var(--color-text-primary)]">
                                                    <code>{fileContent}</code>
                                                </pre>
                                            </div>
                                        </div>

                                        {/* Footer */}
                                        <div className="px-4 py-2 bg-[var(--color-bg-primary)] border-t border-[var(--color-border-subtle)] text-xs text-[var(--color-text-dimmer)]">
                                            {lines.length} lines • {(fileContent.length / 1024).toFixed(1)} KB • UTF-8
                                        </div>
                                    </>
                                ) : (
                                    <div className="flex-1 flex items-center justify-center">
                                        <EmptyState type="files" message="Select a file to view contents" />
                                    </div>
                                )}
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