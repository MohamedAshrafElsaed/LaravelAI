'use client';

import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
    Plus, Search, RefreshCw, Folder, FolderOpen, Trash2, ExternalLink,
    GitBranch, Clock, FileCode, AlertCircle, CheckCircle, Loader2,
    ChevronRight, X, Github, Shield, Zap, Database
} from 'lucide-react';
import { projectsApi, githubApi, getErrorMessage, Project, GitHubRepo } from '@/lib/api';

// ============================================================================
// Types
// ============================================================================

interface ProjectWithMeta extends Project {
    isDeleting?: boolean;
}

type ViewMode = 'grid' | 'list';
type FilterStatus = 'all' | 'ready' | 'indexing' | 'error';

// ============================================================================
// Status Badge Component
// ============================================================================

function StatusBadge({ status }: { status: string }) {
    const config: Record<string, { color: string; bg: string; icon: React.ReactNode; label: string }> = {
        ready: {
            color: 'text-emerald-400',
            bg: 'bg-emerald-400/10',
            icon: <CheckCircle className="w-3 h-3" />,
            label: 'Ready'
        },
        indexing: {
            color: 'text-blue-400',
            bg: 'bg-blue-400/10',
            icon: <Loader2 className="w-3 h-3 animate-spin" />,
            label: 'Indexing'
        },
        cloning: {
            color: 'text-blue-400',
            bg: 'bg-blue-400/10',
            icon: <Loader2 className="w-3 h-3 animate-spin" />,
            label: 'Cloning'
        },
        scanning: {
            color: 'text-amber-400',
            bg: 'bg-amber-400/10',
            icon: <Loader2 className="w-3 h-3 animate-spin" />,
            label: 'Scanning'
        },
        analyzing: {
            color: 'text-purple-400',
            bg: 'bg-purple-400/10',
            icon: <Loader2 className="w-3 h-3 animate-spin" />,
            label: 'Analyzing'
        },
        error: {
            color: 'text-red-400',
            bg: 'bg-red-400/10',
            icon: <AlertCircle className="w-3 h-3" />,
            label: 'Error'
        },
        pending: {
            color: 'text-gray-400',
            bg: 'bg-gray-400/10',
            icon: <Clock className="w-3 h-3" />,
            label: 'Pending'
        },
    };

    const { color, bg, icon, label } = config[status] || config.pending;

    return (
        <span className={`inline-flex items-center gap-1.5 px-2 py-1 rounded-full text-xs font-medium ${color} ${bg}`}>
            {icon}
            {label}
        </span>
    );
}

// ============================================================================
// Health Score Badge
// ============================================================================

function HealthBadge({ score }: { score?: number }) {
    if (score === undefined || score === null) return null;

    const getColor = (s: number) => {
        if (s >= 80) return 'text-emerald-400 bg-emerald-400/10';
        if (s >= 60) return 'text-amber-400 bg-amber-400/10';
        return 'text-red-400 bg-red-400/10';
    };

    return (
        <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${getColor(score)}`}>
            <Shield className="w-3 h-3" />
            {score}%
        </span>
    );
}

// ============================================================================
// Project Card Component
// ============================================================================

interface ProjectCardProps {
    project: ProjectWithMeta;
    onSelect: (project: Project) => void;
    onDelete: (project: Project) => void;
    viewMode: ViewMode;
}

function ProjectCard({ project, onSelect, onDelete, viewMode }: ProjectCardProps) {
    const [showActions, setShowActions] = useState(false);

    const formatDate = (dateStr: string) => {
        const date = new Date(dateStr);
        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    };

    const formatTimeAgo = (dateStr: string) => {
        const seconds = Math.floor((Date.now() - new Date(dateStr).getTime()) / 1000);
        if (seconds < 60) return 'just now';
        if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
        if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
        return `${Math.floor(seconds / 86400)}d ago`;
    };

    if (viewMode === 'list') {
        return (
            <motion.div
                layout
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                className="group flex items-center gap-4 p-4 bg-[var(--color-bg-surface)] border border-[var(--color-border-subtle)] rounded-lg hover:border-[var(--color-border-default)] transition-all cursor-pointer"
                onClick={() => onSelect(project)}
                onMouseEnter={() => setShowActions(true)}
                onMouseLeave={() => setShowActions(false)}
            >
                <div className="p-2 rounded-lg bg-[var(--color-primary-subtle)]">
                    <Folder className="w-5 h-5 text-[var(--color-primary)]" />
                </div>

                <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                        <h3 className="font-medium text-[var(--color-text-primary)] truncate">
                            {project.name}
                        </h3>
                        <StatusBadge status={project.status} />
                        <HealthBadge score={project.health_score} />
                    </div>
                    <p className="text-sm text-[var(--color-text-dimmer)] truncate">
                        {project.repo_full_name}
                    </p>
                </div>

                <div className="hidden sm:flex items-center gap-6 text-sm text-[var(--color-text-muted)]">
                    <div className="flex items-center gap-1.5">
                        <FileCode className="w-4 h-4" />
                        <span>{project.indexed_files_count} files</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                        <GitBranch className="w-4 h-4" />
                        <span>{project.default_branch}</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                        <Clock className="w-4 h-4" />
                        <span>{formatTimeAgo(project.updated_at)}</span>
                    </div>
                </div>

                <AnimatePresence>
                    {showActions && (
                        <motion.div
                            initial={{ opacity: 0, scale: 0.9 }}
                            animate={{ opacity: 1, scale: 1 }}
                            exit={{ opacity: 0, scale: 0.9 }}
                            className="flex items-center gap-2"
                        >
                            <button
                                onClick={(e) => { e.stopPropagation(); window.open(project.repo_url, '_blank'); }}
                                className="p-2 rounded-lg hover:bg-[var(--color-bg-hover)] text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)] transition-colors"
                                title="Open in GitHub"
                            >
                                <ExternalLink className="w-4 h-4" />
                            </button>
                            <button
                                onClick={(e) => { e.stopPropagation(); onDelete(project); }}
                                disabled={project.isDeleting}
                                className="p-2 rounded-lg hover:bg-red-500/10 text-[var(--color-text-muted)] hover:text-red-400 transition-colors disabled:opacity-50"
                                title="Delete project"
                            >
                                {project.isDeleting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
                            </button>
                        </motion.div>
                    )}
                </AnimatePresence>

                <ChevronRight className="w-5 h-5 text-[var(--color-text-dimmer)] group-hover:text-[var(--color-primary)] transition-colors" />
            </motion.div>
        );
    }

    // Grid View
    return (
        <motion.div
            layout
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            whileHover={{ y: -2 }}
            className="group relative bg-[var(--color-bg-surface)] border border-[var(--color-border-subtle)] rounded-xl overflow-hidden hover:border-[var(--color-border-default)] hover:shadow-lg transition-all cursor-pointer"
            onClick={() => onSelect(project)}
        >
            {/* Header */}
            <div className="p-4 pb-3 border-b border-[var(--color-border-subtle)]">
                <div className="flex items-start justify-between gap-3">
                    <div className="flex items-center gap-3 min-w-0">
                        <div className="p-2 rounded-lg bg-[var(--color-primary-subtle)] group-hover:bg-[var(--color-primary)]/20 transition-colors">
                            <FolderOpen className="w-5 h-5 text-[var(--color-primary)]" />
                        </div>
                        <div className="min-w-0">
                            <h3 className="font-semibold text-[var(--color-text-primary)] truncate group-hover:text-[var(--color-primary)] transition-colors">
                                {project.name}
                            </h3>
                            <p className="text-xs text-[var(--color-text-dimmer)] truncate">
                                {project.repo_full_name}
                            </p>
                        </div>
                    </div>
                    <StatusBadge status={project.status} />
                </div>
            </div>

            {/* Stats */}
            <div className="p-4 space-y-3">
                <div className="grid grid-cols-2 gap-3">
                    <div className="flex items-center gap-2 text-sm">
                        <FileCode className="w-4 h-4 text-[var(--color-text-dimmer)]" />
                        <span className="text-[var(--color-text-muted)]">{project.indexed_files_count} files</span>
                    </div>
                    <div className="flex items-center gap-2 text-sm">
                        <GitBranch className="w-4 h-4 text-[var(--color-text-dimmer)]" />
                        <span className="text-[var(--color-text-muted)]">{project.default_branch}</span>
                    </div>
                </div>

                {project.laravel_version && (
                    <div className="flex items-center gap-2">
                        <span className="px-2 py-0.5 rounded bg-red-500/10 text-red-400 text-xs font-medium">
                            Laravel {project.laravel_version}
                        </span>
                        {project.health_score !== undefined && <HealthBadge score={project.health_score} />}
                    </div>
                )}

                {project.error_message && (
                    <p className="text-xs text-red-400 truncate" title={project.error_message}>
                        {project.error_message}
                    </p>
                )}
            </div>

            {/* Footer */}
            <div className="px-4 py-3 bg-[var(--color-bg-primary)]/50 border-t border-[var(--color-border-subtle)] flex items-center justify-between">
                <span className="text-xs text-[var(--color-text-dimmer)]">
                    Updated {formatTimeAgo(project.updated_at)}
                </span>
                <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button
                        onClick={(e) => { e.stopPropagation(); window.open(project.repo_url, '_blank'); }}
                        className="p-1.5 rounded hover:bg-[var(--color-bg-hover)] text-[var(--color-text-dimmer)] hover:text-[var(--color-text-primary)] transition-colors"
                    >
                        <ExternalLink className="w-3.5 h-3.5" />
                    </button>
                    <button
                        onClick={(e) => { e.stopPropagation(); onDelete(project); }}
                        disabled={project.isDeleting}
                        className="p-1.5 rounded hover:bg-red-500/10 text-[var(--color-text-dimmer)] hover:text-red-400 transition-colors disabled:opacity-50"
                    >
                        {project.isDeleting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Trash2 className="w-3.5 h-3.5" />}
                    </button>
                </div>
            </div>
        </motion.div>
    );
}

// ============================================================================
// Add Project Modal
// ============================================================================

interface AddProjectModalProps {
    isOpen: boolean;
    onClose: () => void;
    onAdd: (repoId: number) => Promise<void>;
}

function AddProjectModal({ isOpen, onClose, onAdd }: AddProjectModalProps) {
    const [repos, setRepos] = useState<GitHubRepo[]>([]);
    const [loading, setLoading] = useState(false);
    const [adding, setAdding] = useState<number | null>(null);
    const [search, setSearch] = useState('');
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (isOpen) {
            fetchRepos();
        }
    }, [isOpen]);

    const fetchRepos = async () => {
        setLoading(true);
        setError(null);
        try {
            const response = await githubApi.listRepos();
            setRepos(response.data);
        } catch (err) {
            setError(getErrorMessage(err));
        } finally {
            setLoading(false);
        }
    };

    const handleAdd = async (repoId: number) => {
        setAdding(repoId);
        try {
            await onAdd(repoId);
            onClose();
        } catch (err) {
            setError(getErrorMessage(err));
        } finally {
            setAdding(null);
        }
    };

    const filteredRepos = repos.filter(repo =>
        repo.full_name.toLowerCase().includes(search.toLowerCase()) ||
        repo.description?.toLowerCase().includes(search.toLowerCase())
    );

    if (!isOpen) return null;

    return (
        <AnimatePresence>
            <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
                onClick={onClose}
            >
                <motion.div
                    initial={{ opacity: 0, scale: 0.95, y: 20 }}
                    animate={{ opacity: 1, scale: 1, y: 0 }}
                    exit={{ opacity: 0, scale: 0.95, y: 20 }}
                    className="w-full max-w-2xl bg-[var(--color-bg-surface)] border border-[var(--color-border-subtle)] rounded-2xl shadow-2xl overflow-hidden"
                    onClick={e => e.stopPropagation()}
                >
                    {/* Header */}
                    <div className="flex items-center justify-between p-6 border-b border-[var(--color-border-subtle)]">
                        <div className="flex items-center gap-3">
                            <div className="p-2 rounded-lg bg-[var(--color-primary-subtle)]">
                                <Github className="w-5 h-5 text-[var(--color-primary)]" />
                            </div>
                            <div>
                                <h2 className="text-lg font-semibold text-[var(--color-text-primary)]">
                                    Connect Repository
                                </h2>
                                <p className="text-sm text-[var(--color-text-muted)]">
                                    Select a Laravel project from your GitHub
                                </p>
                            </div>
                        </div>
                        <button
                            onClick={onClose}
                            className="p-2 rounded-lg hover:bg-[var(--color-bg-hover)] text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)] transition-colors"
                        >
                            <X className="w-5 h-5" />
                        </button>
                    </div>

                    {/* Search */}
                    <div className="p-4 border-b border-[var(--color-border-subtle)]">
                        <div className="relative">
                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--color-text-dimmer)]" />
                            <input
                                type="text"
                                value={search}
                                onChange={(e) => setSearch(e.target.value)}
                                placeholder="Search repositories..."
                                className="w-full pl-10 pr-4 py-2.5 bg-[var(--color-bg-primary)] border border-[var(--color-border-subtle)] rounded-lg text-sm text-[var(--color-text-primary)] placeholder-[var(--color-text-dimmer)] focus:outline-none focus:border-[var(--color-primary)] transition-colors"
                            />
                        </div>
                    </div>

                    {/* Content */}
                    <div className="max-h-96 overflow-y-auto">
                        {loading ? (
                            <div className="flex flex-col items-center justify-center py-12 gap-3">
                                <Loader2 className="w-8 h-8 text-[var(--color-primary)] animate-spin" />
                                <p className="text-sm text-[var(--color-text-muted)]">Loading repositories...</p>
                            </div>
                        ) : error ? (
                            <div className="flex flex-col items-center justify-center py-12 gap-3">
                                <AlertCircle className="w-8 h-8 text-red-400" />
                                <p className="text-sm text-red-400">{error}</p>
                                <button
                                    onClick={fetchRepos}
                                    className="px-4 py-2 text-sm bg-[var(--color-bg-hover)] rounded-lg hover:bg-[var(--color-border-subtle)] transition-colors"
                                >
                                    Retry
                                </button>
                            </div>
                        ) : filteredRepos.length === 0 ? (
                            <div className="flex flex-col items-center justify-center py-12 gap-2">
                                <Folder className="w-8 h-8 text-[var(--color-text-dimmer)]" />
                                <p className="text-sm text-[var(--color-text-muted)]">
                                    {search ? 'No matching repositories found' : 'No PHP/Laravel repositories found'}
                                </p>
                            </div>
                        ) : (
                            <div className="divide-y divide-[var(--color-border-subtle)]">
                                {filteredRepos.map((repo) => (
                                    <div
                                        key={repo.id}
                                        className="flex items-center justify-between p-4 hover:bg-[var(--color-bg-hover)] transition-colors"
                                    >
                                        <div className="flex items-center gap-3 min-w-0">
                                            <div className="p-2 rounded-lg bg-[var(--color-bg-primary)]">
                                                <Folder className="w-4 h-4 text-[var(--color-text-muted)]" />
                                            </div>
                                            <div className="min-w-0">
                                                <div className="flex items-center gap-2">
                                                    <span className="font-medium text-[var(--color-text-primary)] truncate">
                                                        {repo.full_name}
                                                    </span>
                                                    {repo.private && (
                                                        <span className="px-1.5 py-0.5 text-[10px] bg-amber-500/10 text-amber-400 rounded">
                                                            Private
                                                        </span>
                                                    )}
                                                </div>
                                                {repo.description && (
                                                    <p className="text-xs text-[var(--color-text-dimmer)] truncate">
                                                        {repo.description}
                                                    </p>
                                                )}
                                                <div className="flex items-center gap-3 mt-1 text-xs text-[var(--color-text-dimmer)]">
                                                    <span className="flex items-center gap-1">
                                                        <GitBranch className="w-3 h-3" />
                                                        {repo.default_branch}
                                                    </span>
                                                    {repo.language && (
                                                        <span className="flex items-center gap-1">
                                                            <span className="w-2 h-2 rounded-full bg-blue-400" />
                                                            {repo.language}
                                                        </span>
                                                    )}
                                                </div>
                                            </div>
                                        </div>
                                        <button
                                            onClick={() => handleAdd(repo.id)}
                                            disabled={adding !== null}
                                            className="flex items-center gap-2 px-4 py-2 bg-[var(--color-primary)] text-white text-sm font-medium rounded-lg hover:bg-[var(--color-primary)]/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                                        >
                                            {adding === repo.id ? (
                                                <Loader2 className="w-4 h-4 animate-spin" />
                                            ) : (
                                                <Plus className="w-4 h-4" />
                                            )}
                                            Connect
                                        </button>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>

                    {/* Footer */}
                    <div className="p-4 bg-[var(--color-bg-primary)]/50 border-t border-[var(--color-border-subtle)]">
                        <p className="text-xs text-[var(--color-text-dimmer)] text-center">
                            Only PHP and Laravel repositories are shown. Connect a repository to start AI-powered development.
                        </p>
                    </div>
                </motion.div>
            </motion.div>
        </AnimatePresence>
    );
}

// ============================================================================
// Delete Confirmation Modal
// ============================================================================

interface DeleteModalProps {
    project: Project | null;
    onConfirm: () => void;
    onCancel: () => void;
    isDeleting: boolean;
}

function DeleteModal({ project, onConfirm, onCancel, isDeleting }: DeleteModalProps) {
    if (!project) return null;

    return (
        <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
            onClick={onCancel}
        >
            <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.95 }}
                className="w-full max-w-md bg-[var(--color-bg-surface)] border border-[var(--color-border-subtle)] rounded-2xl shadow-2xl overflow-hidden"
                onClick={e => e.stopPropagation()}
            >
                <div className="p-6">
                    <div className="flex items-center gap-4 mb-4">
                        <div className="p-3 rounded-full bg-red-500/10">
                            <Trash2 className="w-6 h-6 text-red-400" />
                        </div>
                        <div>
                            <h3 className="text-lg font-semibold text-[var(--color-text-primary)]">
                                Delete Project?
                            </h3>
                            <p className="text-sm text-[var(--color-text-muted)]">
                                This action cannot be undone
                            </p>
                        </div>
                    </div>
                    <p className="text-sm text-[var(--color-text-muted)] mb-6">
                        Are you sure you want to delete <span className="font-medium text-[var(--color-text-primary)]">{project.name}</span>?
                        All indexed data and conversations will be permanently removed.
                    </p>
                    <div className="flex gap-3">
                        <button
                            onClick={onCancel}
                            className="flex-1 px-4 py-2.5 text-sm font-medium text-[var(--color-text-primary)] bg-[var(--color-bg-primary)] border border-[var(--color-border-subtle)] rounded-lg hover:bg-[var(--color-bg-hover)] transition-colors"
                        >
                            Cancel
                        </button>
                        <button
                            onClick={onConfirm}
                            disabled={isDeleting}
                            className="flex-1 px-4 py-2.5 text-sm font-medium text-white bg-red-500 rounded-lg hover:bg-red-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
                        >
                            {isDeleting ? (
                                <>
                                    <Loader2 className="w-4 h-4 animate-spin" />
                                    Deleting...
                                </>
                            ) : (
                                <>
                                    <Trash2 className="w-4 h-4" />
                                    Delete
                                </>
                            )}
                        </button>
                    </div>
                </div>
            </motion.div>
        </motion.div>
    );
}

// ============================================================================
// Empty State Component
// ============================================================================

function ProjectsEmptyState({ onAdd }: { onAdd: () => void }) {
    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex flex-col items-center justify-center py-16 px-4"
        >
            <div className="p-4 rounded-2xl bg-[var(--color-primary-subtle)] mb-6">
                <Folder className="w-12 h-12 text-[var(--color-primary)]" />
            </div>
            <h3 className="text-xl font-semibold text-[var(--color-text-primary)] mb-2">
                No projects yet
            </h3>
            <p className="text-[var(--color-text-muted)] text-center max-w-md mb-6">
                Connect your first Laravel repository to start using AI-powered code generation and analysis.
            </p>
            <button
                onClick={onAdd}
                className="flex items-center gap-2 px-6 py-3 bg-[var(--color-primary)] text-white font-medium rounded-xl hover:bg-[var(--color-primary)]/90 transition-colors shadow-lg shadow-[var(--color-primary)]/25"
            >
                <Github className="w-5 h-5" />
                Connect Repository
            </button>

            {/* Features */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-12 w-full max-w-2xl">
                {[
                    { icon: Zap, title: 'AI Code Generation', desc: 'Generate Laravel code with natural language' },
                    { icon: Shield, title: 'Security Analysis', desc: 'Detect vulnerabilities and issues' },
                    { icon: Database, title: 'Smart Indexing', desc: 'Semantic search across your codebase' },
                ].map((feature, i) => (
                    <div key={i} className="p-4 bg-[var(--color-bg-surface)] border border-[var(--color-border-subtle)] rounded-xl">
                        <feature.icon className="w-5 h-5 text-[var(--color-primary)] mb-2" />
                        <h4 className="font-medium text-[var(--color-text-primary)] text-sm">{feature.title}</h4>
                        <p className="text-xs text-[var(--color-text-dimmer)] mt-1">{feature.desc}</p>
                    </div>
                ))}
            </div>
        </motion.div>
    );
}

// ============================================================================
// Main Projects Page Component
// ============================================================================

export default function ProjectsPage() {
    const [projects, setProjects] = useState<ProjectWithMeta[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [search, setSearch] = useState('');
    const [viewMode, setViewMode] = useState<ViewMode>('grid');
    const [filterStatus, setFilterStatus] = useState<FilterStatus>('all');
    const [showAddModal, setShowAddModal] = useState(false);
    const [deleteTarget, setDeleteTarget] = useState<Project | null>(null);
    const [isDeleting, setIsDeleting] = useState(false);

    const fetchProjects = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const response = await projectsApi.list();
            setProjects(response.data);
        } catch (err) {
            setError(getErrorMessage(err));
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchProjects();
    }, [fetchProjects]);

    const handleAddProject = async (repoId: number) => {
        const response = await projectsApi.create(repoId);
        setProjects(prev => [response.data, ...prev]);
    };

    const handleDeleteProject = async () => {
        if (!deleteTarget) return;

        setIsDeleting(true);
        try {
            await projectsApi.delete(deleteTarget.id);
            setProjects(prev => prev.filter(p => p.id !== deleteTarget.id));
            setDeleteTarget(null);
        } catch (err) {
            setError(getErrorMessage(err));
        } finally {
            setIsDeleting(false);
        }
    };

    const handleSelectProject = (project: Project) => {
        // Navigate to project or open in dashboard
        console.log('Selected project:', project.id);
        // router.push(`/dashboard?project=${project.id}`);
    };

    const filteredProjects = projects.filter(project => {
        const matchesSearch =
            project.name.toLowerCase().includes(search.toLowerCase()) ||
            project.repo_full_name.toLowerCase().includes(search.toLowerCase());

        const matchesStatus =
            filterStatus === 'all' ||
            (filterStatus === 'ready' && project.status === 'ready') ||
            (filterStatus === 'indexing' && ['indexing', 'cloning', 'scanning', 'analyzing'].includes(project.status)) ||
            (filterStatus === 'error' && project.status === 'error');

        return matchesSearch && matchesStatus;
    });

    const statusCounts = {
        all: projects.length,
        ready: projects.filter(p => p.status === 'ready').length,
        indexing: projects.filter(p => ['indexing', 'cloning', 'scanning', 'analyzing'].includes(p.status)).length,
        error: projects.filter(p => p.status === 'error').length,
    };

    return (
        <div className="flex-1 p-6 overflow-y-auto">
            {/* Header */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
                <div>
                    <h1 className="text-2xl font-bold text-[var(--color-text-primary)]">Projects</h1>
                    <p className="text-[var(--color-text-dimmer)] text-sm mt-1">
                        Manage your connected Laravel repositories
                    </p>
                </div>
                <div className="flex items-center gap-3">
                    <button
                        onClick={fetchProjects}
                        disabled={loading}
                        className="p-2.5 rounded-lg border border-[var(--color-border-subtle)] hover:bg-[var(--color-bg-surface)] transition-colors disabled:opacity-50"
                        title="Refresh"
                    >
                        <RefreshCw className={`w-4 h-4 text-[var(--color-text-muted)] ${loading ? 'animate-spin' : ''}`} />
                    </button>
                    <button
                        onClick={() => setShowAddModal(true)}
                        className="flex items-center gap-2 px-4 py-2.5 bg-[var(--color-primary)] text-white font-medium rounded-lg hover:bg-[var(--color-primary)]/90 transition-colors"
                    >
                        <Plus className="w-4 h-4" />
                        <span className="hidden sm:inline">Add Project</span>
                    </button>
                </div>
            </div>

            {/* Filters & Search */}
            {projects.length > 0 && (
                <div className="flex flex-col sm:flex-row gap-4 mb-6">
                    {/* Search */}
                    <div className="relative flex-1">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--color-text-dimmer)]" />
                        <input
                            type="text"
                            value={search}
                            onChange={(e) => setSearch(e.target.value)}
                            placeholder="Search projects..."
                            className="w-full pl-10 pr-4 py-2.5 bg-[var(--color-bg-surface)] border border-[var(--color-border-subtle)] rounded-lg text-sm text-[var(--color-text-primary)] placeholder-[var(--color-text-dimmer)] focus:outline-none focus:border-[var(--color-primary)] transition-colors"
                        />
                    </div>

                    {/* Status Filters */}
                    <div className="flex items-center gap-2">
                        {(['all', 'ready', 'indexing', 'error'] as FilterStatus[]).map((status) => (
                            <button
                                key={status}
                                onClick={() => setFilterStatus(status)}
                                className={`px-3 py-2 text-sm font-medium rounded-lg transition-colors ${
                                    filterStatus === status
                                        ? 'bg-[var(--color-primary-subtle)] text-[var(--color-primary)]'
                                        : 'text-[var(--color-text-muted)] hover:bg-[var(--color-bg-surface)]'
                                }`}
                            >
                                {status.charAt(0).toUpperCase() + status.slice(1)}
                                <span className="ml-1.5 text-xs opacity-70">({statusCounts[status]})</span>
                            </button>
                        ))}
                    </div>

                    {/* View Toggle */}
                    <div className="flex items-center gap-1 p-1 bg-[var(--color-bg-surface)] border border-[var(--color-border-subtle)] rounded-lg">
                        <button
                            onClick={() => setViewMode('grid')}
                            className={`p-2 rounded transition-colors ${
                                viewMode === 'grid'
                                    ? 'bg-[var(--color-primary-subtle)] text-[var(--color-primary)]'
                                    : 'text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)]'
                            }`}
                        >
                            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 16 16">
                                <path d="M1 2.5A1.5 1.5 0 0 1 2.5 1h3A1.5 1.5 0 0 1 7 2.5v3A1.5 1.5 0 0 1 5.5 7h-3A1.5 1.5 0 0 1 1 5.5v-3zm8 0A1.5 1.5 0 0 1 10.5 1h3A1.5 1.5 0 0 1 15 2.5v3A1.5 1.5 0 0 1 13.5 7h-3A1.5 1.5 0 0 1 9 5.5v-3zm-8 8A1.5 1.5 0 0 1 2.5 9h3A1.5 1.5 0 0 1 7 10.5v3A1.5 1.5 0 0 1 5.5 15h-3A1.5 1.5 0 0 1 1 13.5v-3zm8 0A1.5 1.5 0 0 1 10.5 9h3a1.5 1.5 0 0 1 1.5 1.5v3a1.5 1.5 0 0 1-1.5 1.5h-3A1.5 1.5 0 0 1 9 13.5v-3z"/>
                            </svg>
                        </button>
                        <button
                            onClick={() => setViewMode('list')}
                            className={`p-2 rounded transition-colors ${
                                viewMode === 'list'
                                    ? 'bg-[var(--color-primary-subtle)] text-[var(--color-primary)]'
                                    : 'text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)]'
                            }`}
                        >
                            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 16 16">
                                <path fillRule="evenodd" d="M2.5 12a.5.5 0 0 1 .5-.5h10a.5.5 0 0 1 0 1H3a.5.5 0 0 1-.5-.5zm0-4a.5.5 0 0 1 .5-.5h10a.5.5 0 0 1 0 1H3a.5.5 0 0 1-.5-.5zm0-4a.5.5 0 0 1 .5-.5h10a.5.5 0 0 1 0 1H3a.5.5 0 0 1-.5-.5z"/>
                            </svg>
                        </button>
                    </div>
                </div>
            )}

            {/* Content */}
            {loading && projects.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-16 gap-3">
                    <Loader2 className="w-8 h-8 text-[var(--color-primary)] animate-spin" />
                    <p className="text-sm text-[var(--color-text-muted)]">Loading projects...</p>
                </div>
            ) : error ? (
                <div className="flex flex-col items-center justify-center py-16 gap-3">
                    <AlertCircle className="w-8 h-8 text-red-400" />
                    <p className="text-sm text-red-400">{error}</p>
                    <button
                        onClick={fetchProjects}
                        className="px-4 py-2 text-sm bg-[var(--color-bg-surface)] border border-[var(--color-border-subtle)] rounded-lg hover:bg-[var(--color-bg-hover)] transition-colors"
                    >
                        Retry
                    </button>
                </div>
            ) : projects.length === 0 ? (
                <ProjectsEmptyState onAdd={() => setShowAddModal(true)} />
            ) : filteredProjects.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-16 gap-2">
                    <Search className="w-8 h-8 text-[var(--color-text-dimmer)]" />
                    <p className="text-[var(--color-text-muted)]">No projects match your search</p>
                    <button
                        onClick={() => { setSearch(''); setFilterStatus('all'); }}
                        className="text-sm text-[var(--color-primary)] hover:underline"
                    >
                        Clear filters
                    </button>
                </div>
            ) : (
                <AnimatePresence mode="popLayout">
                    <motion.div
                        layout
                        className={viewMode === 'grid'
                            ? 'grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4'
                            : 'space-y-3'
                        }
                    >
                        {filteredProjects.map((project) => (
                            <ProjectCard
                                key={project.id}
                                project={project}
                                viewMode={viewMode}
                                onSelect={handleSelectProject}
                                onDelete={setDeleteTarget}
                            />
                        ))}
                    </motion.div>
                </AnimatePresence>
            )}

            {/* Modals */}
            <AddProjectModal
                isOpen={showAddModal}
                onClose={() => setShowAddModal(false)}
                onAdd={handleAddProject}
            />

            <AnimatePresence>
                {deleteTarget && (
                    <DeleteModal
                        project={deleteTarget}
                        onConfirm={handleDeleteProject}
                        onCancel={() => setDeleteTarget(null)}
                        isDeleting={isDeleting}
                    />
                )}
            </AnimatePresence>
        </div>
    );
}