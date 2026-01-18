'use client';

import {useCallback, useEffect, useState} from 'react';
import {
    AlertCircle,
    ChevronDown,
    ChevronRight,
    Clock,
    ExternalLink,
    FileCode,
    FileEdit,
    FilePlus,
    FileX,
    GitBranch,
    GitCommit,
    GitMerge,
    GitPullRequest,
    History,
    Loader2,
    Play,
    RotateCcw,
    Trash2,
    Upload,
    X,
} from 'lucide-react';
import {GitChange, GitChangeFile, gitChangesApi} from '@/lib/api';

interface GitChangesTrackerProps {
    projectId: string;
    conversationId?: string;
    defaultBranch?: string;
    onChangeSelect?: (change: GitChange) => void;
    compact?: boolean;
}

const STATUS_CONFIG: Record<string, { label: string; color: string; icon: React.ReactNode; bgColor: string }> = {
    pending: {
        label: 'Pending',
        color: 'text-yellow-400',
        bgColor: 'bg-yellow-500/20',
        icon: <Clock className="h-3.5 w-3.5"/>,
    },
    applied: {
        label: 'Applied',
        color: 'text-blue-400',
        bgColor: 'bg-blue-500/20',
        icon: <GitCommit className="h-3.5 w-3.5"/>,
    },
    pushed: {
        label: 'Pushed',
        color: 'text-purple-400',
        bgColor: 'bg-purple-500/20',
        icon: <Upload className="h-3.5 w-3.5"/>,
    },
    pr_created: {
        label: 'PR Created',
        color: 'text-cyan-400',
        bgColor: 'bg-cyan-500/20',
        icon: <GitPullRequest className="h-3.5 w-3.5"/>,
    },
    pr_merged: {
        label: 'PR Merged',
        color: 'text-green-400',
        bgColor: 'bg-green-500/20',
        icon: <GitMerge className="h-3.5 w-3.5"/>,
    },
    merged: {
        label: 'Merged',
        color: 'text-green-400',
        bgColor: 'bg-green-500/20',
        icon: <GitMerge className="h-3.5 w-3.5"/>,
    },
    rolled_back: {
        label: 'Rolled Back',
        color: 'text-orange-400',
        bgColor: 'bg-orange-500/20',
        icon: <RotateCcw className="h-3.5 w-3.5"/>,
    },
    discarded: {
        label: 'Discarded',
        color: 'text-gray-400',
        bgColor: 'bg-gray-500/20',
        icon: <Trash2 className="h-3.5 w-3.5"/>,
    },
};

function getFileIcon(action: string) {
    switch (action) {
        case 'create':
            return <FilePlus className="h-3.5 w-3.5 text-green-400"/>;
        case 'modify':
            return <FileEdit className="h-3.5 w-3.5 text-yellow-400"/>;
        case 'delete':
            return <FileX className="h-3.5 w-3.5 text-red-400"/>;
        default:
            return <FileCode className="h-3.5 w-3.5 text-gray-400"/>;
    }
}

function formatDate(dateString: string) {
    const date = new Date(dateString);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);

    if (minutes < 1) return 'Just now';
    if (minutes < 60) return `${minutes}m ago`;
    if (hours < 24) return `${hours}h ago`;
    if (days < 7) return `${days}d ago`;
    return date.toLocaleDateString();
}

export function GitChangesTracker({
                                      projectId,
                                      conversationId,
                                      defaultBranch = 'main',
                                      onChangeSelect,
                                      compact = false,
                                  }: GitChangesTrackerProps) {
    const [changes, setChanges] = useState<GitChange[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [expandedChanges, setExpandedChanges] = useState<Set<string>>(new Set());
    const [actionLoading, setActionLoading] = useState<string | null>(null);
    const [showAll, setShowAll] = useState(false);

    const loadChanges = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            let response;
            if (conversationId) {
                response = await gitChangesApi.listConversationChanges(projectId, conversationId);
            } else {
                response = await gitChangesApi.listProjectChanges(projectId, {limit: showAll ? 100 : 10});
            }
            setChanges(response.data);
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to load changes');
        } finally {
            setLoading(false);
        }
    }, [projectId, conversationId, showAll]);

    useEffect(() => {
        loadChanges();
    }, [loadChanges]);

    const toggleExpand = (changeId: string) => {
        setExpandedChanges((prev) => {
            const newSet = new Set(prev);
            if (newSet.has(changeId)) {
                newSet.delete(changeId);
            } else {
                newSet.add(changeId);
            }
            return newSet;
        });
    };

    const handleApply = async (change: GitChange) => {
        setActionLoading(change.id);
        try {
            await gitChangesApi.applyChange(projectId, change.id);
            await loadChanges();
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to apply changes');
        } finally {
            setActionLoading(null);
        }
    };

    const handlePush = async (change: GitChange) => {
        setActionLoading(change.id);
        try {
            await gitChangesApi.pushChange(projectId, change.id);
            await loadChanges();
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to push changes');
        } finally {
            setActionLoading(null);
        }
    };

    const handleCreatePR = async (change: GitChange) => {
        setActionLoading(change.id);
        try {
            await gitChangesApi.createPRForChange(projectId, change.id);
            await loadChanges();
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to create PR');
        } finally {
            setActionLoading(null);
        }
    };

    const handleRollback = async (change: GitChange, force = false) => {
        if (!force && change.status === 'pr_created') {
            if (!confirm('This change has an open PR. Rolling back will not close the PR. Continue?')) {
                return;
            }
            force = true;
        }

        setActionLoading(change.id);
        try {
            await gitChangesApi.rollbackChange(projectId, change.id, force);
            await loadChanges();
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to rollback');
        } finally {
            setActionLoading(null);
        }
    };

    const handleDelete = async (change: GitChange) => {
        if (!confirm('Are you sure you want to delete this change record?')) {
            return;
        }

        setActionLoading(change.id);
        try {
            await gitChangesApi.deleteChange(projectId, change.id);
            await loadChanges();
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to delete change');
        } finally {
            setActionLoading(null);
        }
    };

    const renderActions = (change: GitChange) => {
        const isLoading = actionLoading === change.id;

        if (isLoading) {
            return <Loader2 className="h-4 w-4 animate-spin text-gray-400"/>;
        }

        const actions: React.ReactNode[] = [];

        switch (change.status) {
            case 'pending':
                actions.push(
                    <button
                        key="apply"
                        onClick={() => handleApply(change)}
                        className="flex items-center gap-1 rounded px-2 py-1 text-xs bg-blue-500/20 text-blue-400 hover:bg-blue-500/30"
                        title="Apply changes"
                    >
                        <Play className="h-3 w-3"/>
                        Apply
                    </button>
                );
                actions.push(
                    <button
                        key="discard"
                        onClick={() => handleRollback(change)}
                        className="flex items-center gap-1 rounded px-2 py-1 text-xs bg-gray-500/20 text-gray-400 hover:bg-gray-500/30"
                        title="Discard changes"
                    >
                        <Trash2 className="h-3 w-3"/>
                    </button>
                );
                break;

            case 'applied':
                actions.push(
                    <button
                        key="push"
                        onClick={() => handlePush(change)}
                        className="flex items-center gap-1 rounded px-2 py-1 text-xs bg-purple-500/20 text-purple-400 hover:bg-purple-500/30"
                        title="Push to remote"
                    >
                        <Upload className="h-3 w-3"/>
                        Push
                    </button>
                );
                actions.push(
                    <button
                        key="rollback"
                        onClick={() => handleRollback(change)}
                        className="flex items-center gap-1 rounded px-2 py-1 text-xs bg-orange-500/20 text-orange-400 hover:bg-orange-500/30"
                        title="Rollback changes"
                    >
                        <RotateCcw className="h-3 w-3"/>
                    </button>
                );
                break;

            case 'pushed':
                actions.push(
                    <button
                        key="pr"
                        onClick={() => handleCreatePR(change)}
                        className="flex items-center gap-1 rounded px-2 py-1 text-xs bg-cyan-500/20 text-cyan-400 hover:bg-cyan-500/30"
                        title="Create PR"
                    >
                        <GitPullRequest className="h-3 w-3"/>
                        Create PR
                    </button>
                );
                actions.push(
                    <button
                        key="rollback"
                        onClick={() => handleRollback(change)}
                        className="flex items-center gap-1 rounded px-2 py-1 text-xs bg-orange-500/20 text-orange-400 hover:bg-orange-500/30"
                        title="Rollback changes"
                    >
                        <RotateCcw className="h-3 w-3"/>
                    </button>
                );
                break;

            case 'pr_created':
                if (change.pr_url) {
                    actions.push(
                        <a
                            key="view-pr"
                            href={change.pr_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="flex items-center gap-1 rounded px-2 py-1 text-xs bg-cyan-500/20 text-cyan-400 hover:bg-cyan-500/30"
                            title="View PR"
                        >
                            <ExternalLink className="h-3 w-3"/>
                            PR #{change.pr_number}
                        </a>
                    );
                }
                actions.push(
                    <button
                        key="rollback"
                        onClick={() => handleRollback(change, true)}
                        className="flex items-center gap-1 rounded px-2 py-1 text-xs bg-orange-500/20 text-orange-400 hover:bg-orange-500/30"
                        title="Rollback (PR will remain open)"
                    >
                        <RotateCcw className="h-3 w-3"/>
                    </button>
                );
                break;

            case 'rolled_back':
            case 'discarded':
                actions.push(
                    <button
                        key="delete"
                        onClick={() => handleDelete(change)}
                        className="flex items-center gap-1 rounded px-2 py-1 text-xs bg-red-500/20 text-red-400 hover:bg-red-500/30"
                        title="Delete record"
                    >
                        <Trash2 className="h-3 w-3"/>
                    </button>
                );
                break;

            case 'pr_merged':
            case 'merged':
                if (change.pr_url) {
                    actions.push(
                        <a
                            key="view-pr"
                            href={change.pr_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="flex items-center gap-1 rounded px-2 py-1 text-xs bg-green-500/20 text-green-400 hover:bg-green-500/30"
                            title="View merged PR"
                        >
                            <ExternalLink className="h-3 w-3"/>
                            PR #{change.pr_number}
                        </a>
                    );
                }
                break;
        }

        return <div className="flex items-center gap-1">{actions}</div>;
    };

    if (compact) {
        // Compact view for sidebar
        const activeChanges = changes.filter(
            (c) => !['rolled_back', 'discarded', 'pr_merged', 'merged'].includes(c.status)
        );

        if (activeChanges.length === 0) {
            return null;
        }

        return (
            <div className="rounded-lg border border-gray-800 bg-gray-900/50 p-3">
                <div className="flex items-center gap-2 mb-2">
                    <History className="h-4 w-4 text-purple-400"/>
                    <span className="text-sm font-medium text-white">
            {activeChanges.length} Active Change{activeChanges.length !== 1 ? 's' : ''}
          </span>
                </div>
                <div className="space-y-2">
                    {activeChanges.slice(0, 3).map((change) => {
                        const status = STATUS_CONFIG[change.status];
                        return (
                            <div
                                key={change.id}
                                className="flex items-center justify-between text-xs"
                                onClick={() => onChangeSelect?.(change)}
                            >
                                <div className="flex items-center gap-2 min-w-0">
                                    <span className={status.color}>{status.icon}</span>
                                    <span className="text-gray-300 truncate">{change.title || change.branch_name}</span>
                                </div>
                                <span className={`${status.bgColor} ${status.color} px-1.5 py-0.5 rounded`}>
                  {status.label}
                </span>
                            </div>
                        );
                    })}
                </div>
            </div>
        );
    }

    return (
        <div className="rounded-lg border border-gray-800 bg-gray-900/50 overflow-hidden">
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800">
                <div className="flex items-center gap-2">
                    <History className="h-4 w-4 text-purple-400"/>
                    <span className="font-medium text-white">Git Changes History</span>
                    <span className="text-xs text-gray-500">({changes.length})</span>
                </div>
                <button
                    onClick={loadChanges}
                    disabled={loading}
                    className="text-gray-400 hover:text-white"
                    title="Refresh"
                >
                    <Loader2 className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`}/>
                </button>
            </div>

            {/* Error */}
            {error && (
                <div
                    className="px-4 py-2 bg-red-500/10 border-b border-red-500/20 flex items-center gap-2 text-sm text-red-400">
                    <AlertCircle className="h-4 w-4 shrink-0"/>
                    <span>{error}</span>
                    <button onClick={() => setError(null)} className="ml-auto">
                        <X className="h-4 w-4"/>
                    </button>
                </div>
            )}

            {/* Changes list */}
            <div className="divide-y divide-gray-800 max-h-96 overflow-y-auto">
                {loading && changes.length === 0 ? (
                    <div className="flex items-center justify-center py-8">
                        <Loader2 className="h-6 w-6 animate-spin text-gray-500"/>
                    </div>
                ) : changes.length === 0 ? (
                    <div className="px-4 py-8 text-center text-gray-500">
                        <History className="h-8 w-8 mx-auto mb-2 opacity-50"/>
                        <p>No changes recorded yet</p>
                    </div>
                ) : (
                    changes.map((change) => {
                        const status = STATUS_CONFIG[change.status];
                        const isExpanded = expandedChanges.has(change.id);
                        const filesCount = change.files_changed?.length || 0;

                        return (
                            <div key={change.id} className="bg-gray-900/30">
                                {/* Change header */}
                                <div
                                    className="flex items-center gap-3 px-4 py-3 cursor-pointer hover:bg-gray-800/50"
                                    onClick={() => toggleExpand(change.id)}
                                >
                                    {isExpanded ? (
                                        <ChevronDown className="h-4 w-4 text-gray-500 shrink-0"/>
                                    ) : (
                                        <ChevronRight className="h-4 w-4 text-gray-500 shrink-0"/>
                                    )}

                                    <div className="flex items-center gap-2 min-w-0 flex-1">
                                        <span className={status.color}>{status.icon}</span>
                                        <div className="min-w-0">
                                            <div className="flex items-center gap-2">
                        <span className="text-sm text-white truncate">
                          {change.title || change.branch_name}
                        </span>
                                                <span
                                                    className={`text-[10px] px-1.5 py-0.5 rounded ${status.bgColor} ${status.color}`}>
                          {status.label}
                        </span>
                                            </div>
                                            <div className="flex items-center gap-2 text-xs text-gray-500">
                                                <GitBranch className="h-3 w-3"/>
                                                <span>{change.branch_name}</span>
                                                {filesCount > 0 && (
                                                    <>
                                                        <span>|</span>
                                                        <span>{filesCount} file{filesCount !== 1 ? 's' : ''}</span>
                                                    </>
                                                )}
                                                <span>|</span>
                                                <span>{formatDate(change.created_at)}</span>
                                            </div>
                                        </div>
                                    </div>

                                    <div onClick={(e) => e.stopPropagation()}>{renderActions(change)}</div>
                                </div>

                                {/* Expanded details */}
                                {isExpanded && (
                                    <div className="px-4 pb-3 pl-11 space-y-3">
                                        {/* Branch info */}
                                        <div className="flex items-center gap-4 text-xs text-gray-400">
                                            <div className="flex items-center gap-1">
                                                <GitBranch className="h-3.5 w-3.5"/>
                                                <span>{change.base_branch}</span>
                                                <span className="text-gray-600">{'→'}</span>
                                                <span className="text-purple-400">{change.branch_name}</span>
                                            </div>
                                            {change.commit_hash && (
                                                <div className="flex items-center gap-1">
                                                    <GitCommit className="h-3.5 w-3.5"/>
                                                    <span
                                                        className="font-mono">{change.commit_hash.substring(0, 8)}</span>
                                                </div>
                                            )}
                                        </div>

                                        {/* Description */}
                                        {change.description && (
                                            <p className="text-xs text-gray-400">{change.description}</p>
                                        )}

                                        {/* Files changed */}
                                        {change.files_changed && change.files_changed.length > 0 && (
                                            <div className="space-y-1">
                                                <span className="text-xs text-gray-500">Files changed:</span>
                                                <div className="space-y-0.5 max-h-32 overflow-y-auto">
                                                    {change.files_changed.map((file: GitChangeFile, index: number) => (
                                                        <div
                                                            key={index}
                                                            className="flex items-center gap-2 text-xs text-gray-400 py-0.5"
                                                        >
                                                            {getFileIcon(file.action)}
                                                            <span className="truncate">{file.file}</span>
                                                        </div>
                                                    ))}
                                                </div>
                                            </div>
                                        )}

                                        {/* Timestamps */}
                                        <div className="flex flex-wrap gap-3 text-[10px] text-gray-500">
                                            {change.applied_at && (
                                                <span>Applied: {formatDate(change.applied_at)}</span>
                                            )}
                                            {change.pushed_at && (
                                                <span>Pushed: {formatDate(change.pushed_at)}</span>
                                            )}
                                            {change.pr_created_at && (
                                                <span>PR Created: {formatDate(change.pr_created_at)}</span>
                                            )}
                                            {change.merged_at && (
                                                <span>Merged: {formatDate(change.merged_at)}</span>
                                            )}
                                            {change.rolled_back_at && (
                                                <span>
                          Rolled back: {formatDate(change.rolled_back_at)}
                                                    {change.rolled_back_from_status && ` (from ${change.rolled_back_from_status})`}
                        </span>
                                            )}
                                        </div>

                                        {/* Rollback info */}
                                        {change.rollback_commit && (
                                            <div className="flex items-center gap-2 text-xs text-orange-400">
                                                <RotateCcw className="h-3.5 w-3.5"/>
                                                <span>Rollback commit: {change.rollback_commit.substring(0, 8)}</span>
                                            </div>
                                        )}
                                    </div>
                                )}
                            </div>
                        );
                    })
                )}
            </div>

            {/* Show more */}
            {!conversationId && changes.length >= 10 && !showAll && (
                <div className="px-4 py-2 border-t border-gray-800">
                    <button
                        onClick={() => setShowAll(true)}
                        className="w-full text-center text-xs text-purple-400 hover:text-purple-300"
                    >
                        Show all changes
                    </button>
                </div>
            )}
        </div>
    );
}
