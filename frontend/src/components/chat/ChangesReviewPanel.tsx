// frontend/src/components/chat/ChangesReviewPanel.tsx
'use client';

import React, { useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
    GitBranch, GitPullRequest, FileCode, Plus, Minus, Edit3, X,
    ChevronDown, ChevronRight, Check, Copy, ExternalLink, Loader2,
    AlertCircle, Download, Play
} from 'lucide-react';
import { gitApi, gitChangesApi } from '@/lib/api';
import type { GitChangeFile } from './types';

// ============== CHANGES REVIEW PANEL ==============
interface ChangesReviewPanelProps {
    projectId: string;
    conversationId: string | null;
    changes: GitChangeFile[];
    onClose: () => void;
    onApplied?: (branchName: string) => void;
    onPRCreated?: (prUrl: string) => void;
}

export function ChangesReviewPanel({
                                       projectId,
                                       conversationId,
                                       changes,
                                       onClose,
                                       onApplied,
                                       onPRCreated,
                                   }: ChangesReviewPanelProps) {
    const [expandedFiles, setExpandedFiles] = useState<Set<string>>(new Set([changes[0]?.file]));
    const [isApplying, setIsApplying] = useState(false);
    const [isCreatingPR, setIsCreatingPR] = useState(false);
    const [appliedBranch, setAppliedBranch] = useState<string | null>(null);
    const [prUrl, setPrUrl] = useState<string | null>(null);
    const [trackedChangeId, setTrackedChangeId] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [copied, setCopied] = useState<string | null>(null);

    // PR form state
    const [showPRForm, setShowPRForm] = useState(false);
    const [prTitle, setPrTitle] = useState(`AI: ${changes.length} file${changes.length !== 1 ? 's' : ''} modified`);
    const [prDescription, setPrDescription] = useState('');

    // Stats
    const stats = useMemo(() => ({
        total: changes.length,
        created: changes.filter(c => c.action === 'create').length,
        modified: changes.filter(c => c.action === 'modify').length,
        deleted: changes.filter(c => c.action === 'delete').length,
    }), [changes]);

    const toggleFile = (file: string) => {
        setExpandedFiles(prev => {
            const newSet = new Set(prev);
            if (newSet.has(file)) {
                newSet.delete(file);
            } else {
                newSet.add(file);
            }
            return newSet;
        });
    };

    const handleCopy = async (content: string, file: string) => {
        await navigator.clipboard.writeText(content);
        setCopied(file);
        setTimeout(() => setCopied(null), 2000);
    };

    const handleApplyChanges = async () => {
        setIsApplying(true);
        setError(null);

        try {
            const fileChanges = changes.map(c => ({
                file: c.file,
                action: c.action,
                content: c.content,
            }));

            const response = await gitApi.applyChanges(projectId, {
                changes: fileChanges,
                commit_message: `AI changes: ${changes.length} file(s) modified`,
            });

            setAppliedBranch(response.data.branch_name);
            onApplied?.(response.data.branch_name);

            // Track the change in database
            if (conversationId) {
                try {
                    const changeResponse = await gitChangesApi.createChange(projectId, {
                        conversation_id: conversationId,
                        branch_name: response.data.branch_name,
                        title: `AI changes: ${changes.length} file(s) modified`,
                        files_changed: changes,
                        change_summary: `Modified ${changes.length} file(s)`,
                    });

                    await gitChangesApi.updateChange(projectId, changeResponse.data.id, {
                        status: 'applied',
                        commit_hash: response.data.commit_hash,
                    });

                    setTrackedChangeId(changeResponse.data.id);
                } catch (trackErr) {
                    console.warn('Failed to track change:', trackErr);
                }
            }

            setShowPRForm(true);
        } catch (err: any) {
            console.error('Failed to apply changes:', err);
            setError(err.response?.data?.detail || 'Failed to apply changes');
        } finally {
            setIsApplying(false);
        }
    };

    const handleCreatePR = async () => {
        if (!appliedBranch || !prTitle.trim()) return;

        setIsCreatingPR(true);
        setError(null);

        try {
            const filesChanged = changes.map(c => c.file);

            const response = await gitApi.createPR(projectId, {
                branch_name: appliedBranch,
                title: prTitle,
                description: prDescription || undefined,
                ai_summary: `Modified ${filesChanged.length} file(s):\n${filesChanged.map(f => `- ${f}`).join('\n')}`,
            });

            setPrUrl(response.data.url);
            onPRCreated?.(response.data.url);
            setShowPRForm(false);

            // Update tracked change
            if (trackedChangeId) {
                try {
                    await gitChangesApi.updateChange(projectId, trackedChangeId, {
                        status: 'pr_created',
                        pr_number: response.data.number,
                        pr_url: response.data.url,
                        pr_state: response.data.state,
                        title: prTitle,
                        description: prDescription,
                    });
                } catch (trackErr) {
                    console.warn('Failed to update change tracking:', trackErr);
                }
            }
        } catch (err: any) {
            console.error('Failed to create PR:', err);
            setError(err.response?.data?.detail || 'Failed to create pull request');
        } finally {
            setIsCreatingPR(false);
        }
    };

    const handleDownloadPatch = () => {
        const patchContent = changes
            .map(c => `# ${c.action}: ${c.file}\n${c.diff || c.content || ''}`)
            .join('\n\n');

        const blob = new Blob([patchContent], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'changes.patch';
        a.click();
        URL.revokeObjectURL(url);
    };

    const getActionIcon = (action: string) => {
        switch (action) {
            case 'create':
                return <Plus className="h-4 w-4 text-green-400" />;
            case 'modify':
                return <Edit3 className="h-4 w-4 text-amber-400" />;
            case 'delete':
                return <Minus className="h-4 w-4 text-red-400" />;
            default:
                return <FileCode className="h-4 w-4 text-gray-400" />;
        }
    };

    const getActionColor = (action: string) => {
        switch (action) {
            case 'create':
                return 'bg-green-500/10 border-green-500/20 text-green-400';
            case 'modify':
                return 'bg-amber-500/10 border-amber-500/20 text-amber-400';
            case 'delete':
                return 'bg-red-500/10 border-red-500/20 text-red-400';
            default:
                return 'bg-gray-500/10 border-gray-500/20 text-gray-400';
        }
    };

    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            className="rounded-xl border border-[var(--color-border-subtle)] bg-[var(--color-bg-elevated)] overflow-hidden"
        >
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3 bg-[var(--color-bg-surface)] border-b border-[var(--color-border-subtle)]">
                <div className="flex items-center gap-3">
                    <div className="p-2 rounded-lg bg-purple-500/20">
                        <GitBranch className="h-5 w-5 text-purple-400" />
                    </div>
                    <div>
                        <h3 className="font-semibold text-[var(--color-text-primary)]">Review Changes</h3>
                        <div className="flex items-center gap-3 text-xs text-[var(--color-text-muted)]">
                            <span>{stats.total} files</span>
                            {stats.created > 0 && <span className="text-green-400">+{stats.created} new</span>}
                            {stats.modified > 0 && <span className="text-amber-400">{stats.modified} modified</span>}
                            {stats.deleted > 0 && <span className="text-red-400">-{stats.deleted} deleted</span>}
                        </div>
                    </div>
                </div>
                <button
                    onClick={onClose}
                    className="p-2 rounded-lg hover:bg-[var(--color-bg-hover)] text-[var(--color-text-muted)]"
                >
                    <X className="h-5 w-5" />
                </button>
            </div>

            {/* Success banner */}
            {prUrl && (
                <div className="px-4 py-3 bg-green-500/10 border-b border-green-500/20 flex items-center justify-between">
                    <div className="flex items-center gap-2 text-green-400">
                        <Check className="h-5 w-5" />
                        <span className="text-sm font-medium">Pull Request created successfully!</span>
                    </div>
                    <a
                        href={prUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-green-500 text-white text-sm font-medium hover:bg-green-400 transition-colors"
                    >
                        <ExternalLink className="h-4 w-4" />
                        View PR
                    </a>
                </div>
            )}

            {/* Applied branch info */}
            {appliedBranch && !prUrl && (
                <div className="px-4 py-2 bg-purple-500/10 border-b border-purple-500/20 flex items-center gap-2 text-sm text-purple-400">
                    <GitBranch className="h-4 w-4" />
                    <span>Changes applied to branch: <strong>{appliedBranch}</strong></span>
                </div>
            )}

            {/* PR Form */}
            <AnimatePresence>
                {showPRForm && !prUrl && (
                    <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: 'auto', opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        className="border-b border-[var(--color-border-subtle)] bg-[var(--color-bg-surface)]"
                    >
                        <div className="px-4 py-3 space-y-3">
                            <h4 className="text-sm font-medium text-[var(--color-text-primary)] flex items-center gap-2">
                                <GitPullRequest className="h-4 w-4 text-purple-400" />
                                Create Pull Request
                            </h4>
                            <input
                                type="text"
                                value={prTitle}
                                onChange={(e) => setPrTitle(e.target.value)}
                                placeholder="PR title"
                                className="w-full px-3 py-2 rounded-lg bg-[var(--color-bg-elevated)] border border-[var(--color-border-subtle)] text-sm text-[var(--color-text-primary)] placeholder-[var(--color-text-muted)] focus:outline-none focus:border-purple-500"
                            />
                            <textarea
                                value={prDescription}
                                onChange={(e) => setPrDescription(e.target.value)}
                                placeholder="Description (optional)"
                                rows={2}
                                className="w-full px-3 py-2 rounded-lg bg-[var(--color-bg-elevated)] border border-[var(--color-border-subtle)] text-sm text-[var(--color-text-primary)] placeholder-[var(--color-text-muted)] focus:outline-none focus:border-purple-500 resize-none"
                            />
                            <div className="flex items-center gap-2">
                                <button
                                    onClick={handleCreatePR}
                                    disabled={isCreatingPR || !prTitle.trim()}
                                    className="flex items-center gap-2 px-4 py-2 rounded-lg bg-purple-500 text-white text-sm font-medium hover:bg-purple-400 disabled:opacity-50 transition-colors"
                                >
                                    {isCreatingPR ? (
                                        <Loader2 className="h-4 w-4 animate-spin" />
                                    ) : (
                                        <GitPullRequest className="h-4 w-4" />
                                    )}
                                    Create PR
                                </button>
                                <button
                                    onClick={() => setShowPRForm(false)}
                                    className="px-4 py-2 rounded-lg text-sm text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-bg-hover)] transition-colors"
                                >
                                    Cancel
                                </button>
                            </div>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* Error */}
            {error && (
                <div className="px-4 py-3 bg-red-500/10 border-b border-red-500/20 flex items-center gap-2 text-red-400 text-sm">
                    <AlertCircle className="h-4 w-4" />
                    <span>{error}</span>
                    <button onClick={() => setError(null)} className="ml-auto hover:text-red-300">
                        <X className="h-4 w-4" />
                    </button>
                </div>
            )}

            {/* File list */}
            <div className="max-h-96 overflow-y-auto divide-y divide-[var(--color-border-subtle)]">
                {changes.map((change) => (
                    <div key={change.file} className="border-l-2 border-transparent hover:border-purple-500/50">
                        {/* File header */}
                        <button
                            onClick={() => toggleFile(change.file)}
                            className="w-full flex items-center gap-3 px-4 py-3 hover:bg-[var(--color-bg-hover)] transition-colors text-left"
                        >
                            {expandedFiles.has(change.file) ? (
                                <ChevronDown className="h-4 w-4 text-[var(--color-text-muted)]" />
                            ) : (
                                <ChevronRight className="h-4 w-4 text-[var(--color-text-muted)]" />
                            )}
                            {getActionIcon(change.action)}
                            <span className="flex-1 truncate text-sm text-[var(--color-text-primary)]">
                {change.file}
              </span>
                            <span className={`px-2 py-0.5 rounded text-xs font-medium ${getActionColor(change.action)}`}>
                {change.action}
              </span>
                        </button>

                        {/* File content */}
                        <AnimatePresence>
                            {expandedFiles.has(change.file) && (change.content || change.diff) && (
                                <motion.div
                                    initial={{ height: 0, opacity: 0 }}
                                    animate={{ height: 'auto', opacity: 1 }}
                                    exit={{ height: 0, opacity: 0 }}
                                    className="border-t border-[var(--color-border-subtle)] bg-black/20"
                                >
                                    <div className="relative">
                                        <button
                                            onClick={() => handleCopy(change.content || change.diff || '', change.file)}
                                            className="absolute top-2 right-2 p-1.5 rounded bg-black/40 hover:bg-black/60 text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)] transition-colors z-10"
                                            title="Copy code"
                                        >
                                            {copied === change.file ? (
                                                <Check className="h-4 w-4 text-green-400" />
                                            ) : (
                                                <Copy className="h-4 w-4" />
                                            )}
                                        </button>
                                        <CodeBlock
                                            code={change.diff || change.content || ''}
                                            maxHeight="300px"
                                        />
                                    </div>
                                </motion.div>
                            )}
                        </AnimatePresence>
                    </div>
                ))}
            </div>

            {/* Actions */}
            <div className="flex items-center justify-between px-4 py-3 bg-[var(--color-bg-surface)] border-t border-[var(--color-border-subtle)]">
                <button
                    onClick={handleDownloadPatch}
                    className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-bg-hover)] transition-colors"
                >
                    <Download className="h-4 w-4" />
                    Download Patch
                </button>

                <div className="flex items-center gap-2">
                    {!appliedBranch && (
                        <button
                            onClick={handleApplyChanges}
                            disabled={isApplying}
                            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[var(--color-primary)] text-white text-sm font-medium hover:bg-[var(--color-primary-hover)] disabled:opacity-50 transition-colors"
                        >
                            {isApplying ? (
                                <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                                <Play className="h-4 w-4" />
                            )}
                            Apply Changes
                        </button>
                    )}
                    {appliedBranch && !prUrl && !showPRForm && (
                        <button
                            onClick={() => setShowPRForm(true)}
                            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-purple-500 text-white text-sm font-medium hover:bg-purple-400 transition-colors"
                        >
                            <GitPullRequest className="h-4 w-4" />
                            Create PR
                        </button>
                    )}
                </div>
            </div>
        </motion.div>
    );
}

// ============== CODE BLOCK COMPONENT ==============
interface CodeBlockProps {
    code: string;
    maxHeight?: string;
}

function CodeBlock({ code, maxHeight = '300px' }: CodeBlockProps) {
    const lines = code.split('\n');

    const getLineClass = (line: string): string => {
        if (line.startsWith('+') && !line.startsWith('+++')) {
            return 'text-green-400 bg-green-500/10';
        }
        if (line.startsWith('-') && !line.startsWith('---')) {
            return 'text-red-400 bg-red-500/10';
        }
        if (line.startsWith('@@')) {
            return 'text-cyan-400 bg-cyan-500/5';
        }
        if (line.startsWith('+++') || line.startsWith('---')) {
            return 'text-[var(--color-text-muted)]';
        }
        return 'text-[var(--color-text-secondary)]';
    };

    return (
        <div className="font-mono text-xs overflow-auto" style={{ maxHeight }}>
      <pre className="p-4 m-0">
        <code>
          {lines.map((line, i) => (
              <div key={i} className={`flex ${getLineClass(line)}`}>
              <span className="select-none text-[var(--color-text-dimmer)] w-8 flex-shrink-0 text-right pr-4">
                {i + 1}
              </span>
                  <span className="flex-1 whitespace-pre">{line || ' '}</span>
              </div>
          ))}
        </code>
      </pre>
        </div>
    );
}

export default ChangesReviewPanel;