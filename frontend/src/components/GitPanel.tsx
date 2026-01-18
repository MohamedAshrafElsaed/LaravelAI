'use client';

import {useCallback, useEffect, useState} from 'react';
import {
    AlertCircle,
    CheckCircle2,
    ChevronDown,
    ChevronRight,
    Clock,
    Copy,
    ExternalLink,
    FileDiff,
    GitBranch,
    GitPullRequest,
    Loader2,
    RefreshCw,
    RotateCcw,
    User,
    X,
} from 'lucide-react';
import {gitApi} from '@/lib/api';

interface Branch {
    name: string;
    is_current: boolean;
    is_remote?: boolean;
    commit: string;
    message: string;
    author: string;
    date: string;
}

interface DiffInfo {
    current_branch: string;
    base_branch: string;
    diff: string;
    files_changed: string[];
    file_count: number;
}

interface GitPanelProps {
    projectId: string;
    defaultBranch?: string;
    onPRCreated?: (prUrl: string) => void;
}

export function GitPanel({projectId, defaultBranch = 'main', onPRCreated}: GitPanelProps) {
    const [branches, setBranches] = useState<Branch[]>([]);
    const [loading, setLoading] = useState(false);
    const [syncing, setSyncing] = useState(false);
    const [resetting, setResetting] = useState(false);
    const [showBranches, setShowBranches] = useState(false);
    const [showDiff, setShowDiff] = useState(false);
    const [showPRForm, setShowPRForm] = useState(false);
    const [diffInfo, setDiffInfo] = useState<DiffInfo | null>(null);
    const [loadingDiff, setLoadingDiff] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState<string | null>(null);

    // PR form state
    const [prTitle, setPrTitle] = useState('');
    const [prDescription, setPrDescription] = useState('');
    const [prBranch, setPrBranch] = useState('');
    const [creatingPR, setCreatingPR] = useState(false);
    const [prUrl, setPrUrl] = useState<string | null>(null);

    // Load branches
    const loadBranches = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const response = await gitApi.listBranches(projectId);
            setBranches(response.data);
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to load branches');
        } finally {
            setLoading(false);
        }
    }, [projectId]);

    // Load diff
    const loadDiff = useCallback(async () => {
        setLoadingDiff(true);
        try {
            const response = await gitApi.getDiff(projectId, defaultBranch);
            setDiffInfo(response.data);
        } catch (err: any) {
            console.error('Failed to load diff:', err);
        } finally {
            setLoadingDiff(false);
        }
    }, [projectId, defaultBranch]);

    // Initial load
    useEffect(() => {
        loadBranches();
    }, [loadBranches]);

    // Sync with remote
    const handleSync = async () => {
        setSyncing(true);
        setError(null);
        setSuccess(null);
        try {
            const response = await gitApi.sync(projectId);
            setSuccess(response.data.message);
            loadBranches();
            setTimeout(() => setSuccess(null), 3000);
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to sync with remote');
        } finally {
            setSyncing(false);
        }
    };

    // Reset to remote
    const handleReset = async () => {
        if (!confirm('This will discard all local changes. Are you sure?')) return;

        setResetting(true);
        setError(null);
        setSuccess(null);
        try {
            const response = await gitApi.reset(projectId, defaultBranch);
            setSuccess(response.data.message);
            loadBranches();
            setTimeout(() => setSuccess(null), 3000);
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to reset');
        } finally {
            setResetting(false);
        }
    };

    // Create PR
    const handleCreatePR = async () => {
        if (!prTitle.trim() || !prBranch.trim()) return;

        setCreatingPR(true);
        setError(null);
        try {
            const response = await gitApi.createPR(projectId, {
                branch_name: prBranch,
                title: prTitle,
                description: prDescription,
                base_branch: defaultBranch,
                ai_summary: diffInfo?.files_changed
                    ? `Modified ${diffInfo.files_changed.length} file(s)`
                    : undefined,
            });

            setPrUrl(response.data.url);
            setSuccess(`PR #${response.data.number} created successfully!`);
            onPRCreated?.(response.data.url);
            setShowPRForm(false);
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to create PR');
        } finally {
            setCreatingPR(false);
        }
    };

    // Copy to clipboard
    const copyToClipboard = (text: string) => {
        navigator.clipboard.writeText(text);
    };

    const currentBranch = branches.find((b) => b.is_current);
    const hasChanges = diffInfo && diffInfo.file_count > 0;

    return (
        <div className="rounded-lg border border-gray-800 bg-gray-900/50 overflow-hidden">
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800">
                <div className="flex items-center gap-2">
                    <GitBranch className="h-4 w-4 text-purple-400"/>
                    <span className="font-medium text-white">Git</span>
                    {currentBranch && (
                        <span className="text-sm text-gray-400 ml-2">
              on <span className="text-purple-400">{currentBranch.name}</span>
            </span>
                    )}
                </div>
                <div className="flex items-center gap-2">
                    <button
                        onClick={handleSync}
                        disabled={syncing}
                        className="flex items-center gap-1.5 rounded px-2 py-1 text-xs text-gray-400 hover:bg-gray-800 hover:text-white transition-colors disabled:opacity-50"
                        title="Pull latest changes"
                    >
                        <RefreshCw className={`h-3.5 w-3.5 ${syncing ? 'animate-spin' : ''}`}/>
                        <span className="hidden sm:inline">Sync</span>
                    </button>
                    <button
                        onClick={handleReset}
                        disabled={resetting}
                        className="flex items-center gap-1.5 rounded px-2 py-1 text-xs text-gray-400 hover:bg-gray-800 hover:text-red-400 transition-colors disabled:opacity-50"
                        title="Reset to remote"
                    >
                        <RotateCcw className={`h-3.5 w-3.5 ${resetting ? 'animate-spin' : ''}`}/>
                        <span className="hidden sm:inline">Reset</span>
                    </button>
                </div>
            </div>

            {/* Status messages */}
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

            {success && (
                <div
                    className="px-4 py-2 bg-green-500/10 border-b border-green-500/20 flex items-center gap-2 text-sm text-green-400">
                    <CheckCircle2 className="h-4 w-4 shrink-0"/>
                    <span>{success}</span>
                </div>
            )}

            {/* PR URL */}
            {prUrl && (
                <div
                    className="px-4 py-2 bg-purple-500/10 border-b border-purple-500/20 flex items-center gap-2 text-sm">
                    <GitPullRequest className="h-4 w-4 text-purple-400 shrink-0"/>
                    <a
                        href={prUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-purple-400 hover:underline truncate flex-1"
                    >
                        {prUrl}
                    </a>
                    <button
                        onClick={() => copyToClipboard(prUrl)}
                        className="text-gray-400 hover:text-white"
                        title="Copy URL"
                    >
                        <Copy className="h-4 w-4"/>
                    </button>
                    <a
                        href={prUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-gray-400 hover:text-white"
                    >
                        <ExternalLink className="h-4 w-4"/>
                    </a>
                </div>
            )}

            {/* Branches section */}
            <div className="border-b border-gray-800">
                <button
                    onClick={() => {
                        setShowBranches(!showBranches);
                        if (!showBranches) loadBranches();
                    }}
                    className="w-full flex items-center justify-between px-4 py-2 text-sm text-gray-300 hover:bg-gray-800/50"
                >
          <span className="flex items-center gap-2">
            {showBranches ? (
                <ChevronDown className="h-4 w-4"/>
            ) : (
                <ChevronRight className="h-4 w-4"/>
            )}
              Branches
          </span>
                    <span className="text-xs text-gray-500">{branches.length}</span>
                </button>

                {showBranches && (
                    <div className="px-4 pb-3 space-y-1 max-h-48 overflow-y-auto">
                        {loading ? (
                            <div className="flex items-center justify-center py-4">
                                <Loader2 className="h-5 w-5 animate-spin text-gray-500"/>
                            </div>
                        ) : branches.length === 0 ? (
                            <p className="text-sm text-gray-500 py-2">No branches found</p>
                        ) : (
                            branches.map((branch) => (
                                <div
                                    key={branch.name}
                                    className={`flex items-center justify-between rounded px-2 py-1.5 text-xs ${
                                        branch.is_current
                                            ? 'bg-purple-500/20 text-purple-300'
                                            : 'text-gray-400 hover:bg-gray-800'
                                    }`}
                                >
                                    <div className="flex items-center gap-2 min-w-0">
                                        <GitBranch className="h-3.5 w-3.5 shrink-0"/>
                                        <span className="truncate">{branch.name}</span>
                                        {branch.is_current && (
                                            <span className="text-[10px] bg-purple-500/30 px-1 rounded">current</span>
                                        )}
                                        {branch.is_remote && (
                                            <span className="text-[10px] bg-gray-600/50 px-1 rounded">remote</span>
                                        )}
                                    </div>
                                    <span className="text-gray-600 shrink-0 ml-2">{branch.commit}</span>
                                </div>
                            ))
                        )}
                    </div>
                )}
            </div>

            {/* Diff section */}
            <div className="border-b border-gray-800">
                <button
                    onClick={() => {
                        setShowDiff(!showDiff);
                        if (!showDiff) loadDiff();
                    }}
                    className="w-full flex items-center justify-between px-4 py-2 text-sm text-gray-300 hover:bg-gray-800/50"
                >
          <span className="flex items-center gap-2">
            {showDiff ? (
                <ChevronDown className="h-4 w-4"/>
            ) : (
                <ChevronRight className="h-4 w-4"/>
            )}
              Changes
          </span>
                    {diffInfo && (
                        <span className={`text-xs ${hasChanges ? 'text-yellow-400' : 'text-gray-500'}`}>
              {diffInfo.file_count} file(s)
            </span>
                    )}
                </button>

                {showDiff && (
                    <div className="px-4 pb-3">
                        {loadingDiff ? (
                            <div className="flex items-center justify-center py-4">
                                <Loader2 className="h-5 w-5 animate-spin text-gray-500"/>
                            </div>
                        ) : diffInfo ? (
                            <div className="space-y-2">
                                <div className="flex items-center gap-2 text-xs text-gray-500">
                  <span>
                    Comparing <span className="text-purple-400">{diffInfo.current_branch}</span> to{' '}
                      <span className="text-gray-300">{diffInfo.base_branch}</span>
                  </span>
                                </div>

                                {diffInfo.files_changed.length > 0 ? (
                                    <div className="space-y-1 max-h-32 overflow-y-auto">
                                        {diffInfo.files_changed.map((file) => (
                                            <div
                                                key={file}
                                                className="flex items-center gap-2 text-xs text-gray-400 py-1"
                                            >
                                                <FileDiff className="h-3.5 w-3.5 text-yellow-500"/>
                                                <span className="truncate">{file}</span>
                                            </div>
                                        ))}
                                    </div>
                                ) : (
                                    <p className="text-sm text-gray-500">No changes</p>
                                )}

                                {hasChanges && (
                                    <button
                                        onClick={() => {
                                            setPrBranch(diffInfo.current_branch);
                                            setPrTitle(`AI changes from ${diffInfo.current_branch}`);
                                            setShowPRForm(true);
                                        }}
                                        className="mt-2 w-full flex items-center justify-center gap-2 rounded bg-purple-600 px-3 py-2 text-sm text-white hover:bg-purple-500 transition-colors"
                                    >
                                        <GitPullRequest className="h-4 w-4"/>
                                        Create Pull Request
                                    </button>
                                )}
                            </div>
                        ) : (
                            <p className="text-sm text-gray-500 py-2">Unable to load changes</p>
                        )}
                    </div>
                )}
            </div>

            {/* Create PR form */}
            {showPRForm && (
                <div className="p-4 border-b border-gray-800 bg-gray-800/30">
                    <div className="flex items-center justify-between mb-3">
                        <h3 className="text-sm font-medium text-white flex items-center gap-2">
                            <GitPullRequest className="h-4 w-4 text-purple-400"/>
                            Create Pull Request
                        </h3>
                        <button
                            onClick={() => setShowPRForm(false)}
                            className="text-gray-400 hover:text-white"
                        >
                            <X className="h-4 w-4"/>
                        </button>
                    </div>

                    <div className="space-y-3">
                        <div>
                            <label className="block text-xs text-gray-400 mb-1">Branch</label>
                            <input
                                type="text"
                                value={prBranch}
                                onChange={(e) => setPrBranch(e.target.value)}
                                className="w-full rounded bg-gray-800 px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:ring-1 focus:ring-purple-500"
                                placeholder="feature/my-changes"
                            />
                        </div>

                        <div>
                            <label className="block text-xs text-gray-400 mb-1">Title</label>
                            <input
                                type="text"
                                value={prTitle}
                                onChange={(e) => setPrTitle(e.target.value)}
                                className="w-full rounded bg-gray-800 px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:ring-1 focus:ring-purple-500"
                                placeholder="Add new feature"
                            />
                        </div>

                        <div>
                            <label className="block text-xs text-gray-400 mb-1">Description (optional)</label>
                            <textarea
                                value={prDescription}
                                onChange={(e) => setPrDescription(e.target.value)}
                                rows={3}
                                className="w-full rounded bg-gray-800 px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:ring-1 focus:ring-purple-500 resize-none"
                                placeholder="Describe your changes..."
                            />
                        </div>

                        <div className="flex items-center justify-between text-xs text-gray-500">
              <span>
                Merging into <span className="text-purple-400">{defaultBranch}</span>
              </span>
                        </div>

                        <button
                            onClick={handleCreatePR}
                            disabled={creatingPR || !prTitle.trim() || !prBranch.trim()}
                            className="w-full flex items-center justify-center gap-2 rounded bg-purple-600 px-3 py-2 text-sm text-white hover:bg-purple-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                        >
                            {creatingPR ? (
                                <>
                                    <Loader2 className="h-4 w-4 animate-spin"/>
                                    Creating...
                                </>
                            ) : (
                                <>
                                    <GitPullRequest className="h-4 w-4"/>
                                    Create Pull Request
                                </>
                            )}
                        </button>
                    </div>
                </div>
            )}

            {/* Quick info */}
            {currentBranch && (
                <div className="px-4 py-3 text-xs text-gray-500 space-y-1">
                    <div className="flex items-center gap-2">
                        <Clock className="h-3.5 w-3.5"/>
                        <span className="truncate">{currentBranch.message}</span>
                    </div>
                    <div className="flex items-center gap-2">
                        <User className="h-3.5 w-3.5"/>
                        <span>{currentBranch.author}</span>
                        <span className="text-gray-600">
              {new Date(currentBranch.date).toLocaleDateString()}
            </span>
                    </div>
                </div>
            )}
        </div>
    );
}
