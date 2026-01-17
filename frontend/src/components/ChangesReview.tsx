'use client';

import { useState } from 'react';
import {
  FileCode,
  FilePlus,
  FileEdit,
  FileX,
  Check,
  X,
  GitPullRequest,
  Download,
  ChevronDown,
  ChevronRight,
  AlertCircle,
  CheckCircle2,
  ExternalLink,
  Loader2,
} from 'lucide-react';
import { DiffViewer, DiffStats } from './DiffViewer';
import { gitApi, gitChangesApi, GitChangeFile } from '@/lib/api';

interface ExecutionResult {
  file: string;
  action: 'create' | 'modify' | 'delete';
  content: string;
  diff: string;
  original_content?: string;
  success: boolean;
  error?: string;
}

interface ChangesReviewProps {
  results: ExecutionResult[];
  projectId: string;
  conversationId?: string;
  messageId?: string;
  defaultBranch?: string;
  onDiscard: () => void;
  onPRCreated?: (url: string) => void;
  onChangeTracked?: (changeId: string) => void;
}

export function ChangesReview({
  results,
  projectId,
  conversationId,
  messageId,
  defaultBranch = 'main',
  onDiscard,
  onPRCreated,
  onChangeTracked,
}: ChangesReviewProps) {
  const [selectedFile, setSelectedFile] = useState<string | null>(
    results.length > 0 ? results[0].file : null
  );
  const [expandedFiles, setExpandedFiles] = useState<Set<string>>(new Set());
  const [applyingAll, setApplyingAll] = useState(false);
  const [creatingPR, setCreatingPR] = useState(false);
  const [appliedBranch, setAppliedBranch] = useState<string | null>(null);
  const [prUrl, setPrUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showPRForm, setShowPRForm] = useState(false);
  const [prTitle, setPrTitle] = useState('AI-generated changes');
  const [prDescription, setPrDescription] = useState('');
  const [trackedChangeId, setTrackedChangeId] = useState<string | null>(null);

  const selectedResult = results.find((r) => r.file === selectedFile);

  const getActionIcon = (action: string) => {
    switch (action) {
      case 'create':
        return <FilePlus className="h-4 w-4 text-green-400" />;
      case 'modify':
        return <FileEdit className="h-4 w-4 text-yellow-400" />;
      case 'delete':
        return <FileX className="h-4 w-4 text-red-400" />;
      default:
        return <FileCode className="h-4 w-4 text-gray-400" />;
    }
  };

  const getActionBadge = (action: string) => {
    const styles: Record<string, string> = {
      create: 'bg-green-500/20 text-green-400',
      modify: 'bg-yellow-500/20 text-yellow-400',
      delete: 'bg-red-500/20 text-red-400',
    };
    return (
      <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${styles[action]}`}>
        {action}
      </span>
    );
  };

  const toggleExpand = (file: string) => {
    setExpandedFiles((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(file)) {
        newSet.delete(file);
      } else {
        newSet.add(file);
      }
      return newSet;
    });
  };

  // Stats
  const stats = {
    total: results.length,
    created: results.filter((r) => r.action === 'create').length,
    modified: results.filter((r) => r.action === 'modify').length,
    deleted: results.filter((r) => r.action === 'delete').length,
    failed: results.filter((r) => !r.success).length,
  };

  const handleApplyAll = async () => {
    if (appliedBranch) {
      // Already applied, show PR form
      setShowPRForm(true);
      return;
    }

    setApplyingAll(true);
    setError(null);
    try {
      // Convert execution results to file changes
      const changes = results
        .filter((r) => r.success)
        .map((r) => ({
          file: r.file,
          action: r.action,
          content: r.content,
        }));

      if (changes.length === 0) {
        setError('No successful changes to apply');
        return;
      }

      // Apply changes to a new branch
      const response = await gitApi.applyChanges(projectId, {
        changes,
        commit_message: `AI changes: ${changes.length} file(s) modified`,
        base_branch: defaultBranch,
      });

      setAppliedBranch(response.data.branch_name);

      // Track the change in the database if we have a conversation
      if (conversationId) {
        try {
          const filesChanged: GitChangeFile[] = results
            .filter((r) => r.success)
            .map((r) => ({
              file: r.file,
              action: r.action,
              content: r.content,
              diff: r.diff,
              original_content: r.original_content,
            }));

          const changeResponse = await gitChangesApi.createChange(projectId, {
            conversation_id: conversationId,
            message_id: messageId,
            branch_name: response.data.branch_name,
            base_branch: defaultBranch,
            title: `AI changes: ${changes.length} file(s) modified`,
            files_changed: filesChanged,
            change_summary: `Modified ${changes.length} file(s)`,
          });

          // Update the change status to applied
          await gitChangesApi.updateChange(projectId, changeResponse.data.id, {
            status: 'applied',
            commit_hash: response.data.commit_hash,
          });

          setTrackedChangeId(changeResponse.data.id);
          onChangeTracked?.(changeResponse.data.id);
        } catch (trackErr) {
          console.warn('Failed to track change:', trackErr);
          // Continue even if tracking fails
        }
      }

      setShowPRForm(true);
    } catch (err: any) {
      console.error('Failed to apply changes:', err);
      setError(err.response?.data?.detail || 'Failed to apply changes');
    } finally {
      setApplyingAll(false);
    }
  };

  const handleCreatePR = async () => {
    if (!appliedBranch) {
      // Need to apply changes first
      await handleApplyAll();
      return;
    }

    setCreatingPR(true);
    setError(null);
    try {
      const filesChanged = results.filter((r) => r.success).map((r) => r.file);

      const response = await gitApi.createPR(projectId, {
        branch_name: appliedBranch,
        title: prTitle,
        description: prDescription,
        base_branch: defaultBranch,
        ai_summary: `Modified ${filesChanged.length} file(s):\n${filesChanged.map(f => `- ${f}`).join('\n')}`,
      });

      setPrUrl(response.data.url);
      setShowPRForm(false);
      onPRCreated?.(response.data.url);

      // Update the tracked change with PR info
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
      setCreatingPR(false);
    }
  };

  const handleDownload = () => {
    // Download all changes as a patch file
    const patchContent = results
      .map((r) => `# ${r.action}: ${r.file}\n${r.diff}`)
      .join('\n\n');

    const blob = new Blob([patchContent], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'changes.patch';
    a.click();
    URL.revokeObjectURL(url);
  };

  if (results.length === 0) {
    return (
      <div className="flex h-full items-center justify-center text-gray-500">
        <p>No changes to review</p>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col bg-gray-950">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between border-b border-gray-800 px-4 py-3 gap-3">
        <div className="flex items-center gap-4">
          <h2 className="font-semibold text-white">Review Changes</h2>
          <div className="flex flex-wrap items-center gap-3 text-sm">
            <span className="text-gray-400">{stats.total} files</span>
            {stats.created > 0 && (
              <span className="text-green-400">+{stats.created} new</span>
            )}
            {stats.modified > 0 && (
              <span className="text-yellow-400">{stats.modified} modified</span>
            )}
            {stats.deleted > 0 && (
              <span className="text-red-400">-{stats.deleted} deleted</span>
            )}
            {stats.failed > 0 && (
              <span className="text-red-400 flex items-center gap-1">
                <AlertCircle className="h-3 w-3" />
                {stats.failed} failed
              </span>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleDownload}
            className="flex items-center gap-2 rounded-lg bg-gray-800 px-3 py-1.5 text-sm font-medium text-gray-300 hover:bg-gray-700"
          >
            <Download className="h-4 w-4" />
            <span className="hidden sm:inline">Download</span>
          </button>
          <button
            onClick={onDiscard}
            className="flex items-center gap-2 rounded-lg bg-gray-800 px-3 py-1.5 text-sm font-medium text-red-400 hover:bg-red-500/10"
          >
            <X className="h-4 w-4" />
            <span className="hidden sm:inline">Discard</span>
          </button>
          {!prUrl && (
            <button
              onClick={handleApplyAll}
              disabled={applyingAll || stats.failed === stats.total}
              className="flex items-center gap-2 rounded-lg bg-green-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-green-500 disabled:opacity-50"
            >
              {applyingAll ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Check className="h-4 w-4" />
              )}
              {applyingAll ? 'Applying...' : appliedBranch ? 'Create PR' : 'Apply & Create PR'}
            </button>
          )}
        </div>
      </div>

      {/* Error message */}
      {error && (
        <div className="px-4 py-2 bg-red-500/10 border-b border-red-500/20 flex items-center gap-2 text-sm text-red-400">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
          <button onClick={() => setError(null)} className="ml-auto">
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* PR URL success message */}
      {prUrl && (
        <div className="px-4 py-3 bg-green-500/10 border-b border-green-500/20 flex items-center gap-3 text-sm">
          <CheckCircle2 className="h-5 w-5 text-green-500 shrink-0" />
          <div className="flex-1 min-w-0">
            <p className="text-green-400 font-medium">Pull Request Created!</p>
            <a
              href={prUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="text-green-300 hover:underline truncate block"
            >
              {prUrl}
            </a>
          </div>
          <a
            href={prUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 rounded-lg bg-green-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-green-500"
          >
            <ExternalLink className="h-4 w-4" />
            View PR
          </a>
        </div>
      )}

      {/* Applied branch info */}
      {appliedBranch && !prUrl && (
        <div className="px-4 py-2 bg-purple-500/10 border-b border-purple-500/20 flex items-center gap-2 text-sm text-purple-400">
          <GitPullRequest className="h-4 w-4" />
          <span>
            Changes applied to branch: <strong>{appliedBranch}</strong>
          </span>
        </div>
      )}

      {/* PR Form */}
      {showPRForm && !prUrl && (
        <div className="px-4 py-3 bg-gray-800/50 border-b border-gray-800">
          <div className="max-w-xl space-y-3">
            <h3 className="text-sm font-medium text-white flex items-center gap-2">
              <GitPullRequest className="h-4 w-4 text-purple-400" />
              Create Pull Request
            </h3>
            <div>
              <input
                type="text"
                value={prTitle}
                onChange={(e) => setPrTitle(e.target.value)}
                placeholder="PR title"
                className="w-full rounded bg-gray-800 px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:ring-1 focus:ring-purple-500"
              />
            </div>
            <div>
              <textarea
                value={prDescription}
                onChange={(e) => setPrDescription(e.target.value)}
                placeholder="Description (optional)"
                rows={2}
                className="w-full rounded bg-gray-800 px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:ring-1 focus:ring-purple-500 resize-none"
              />
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={handleCreatePR}
                disabled={creatingPR || !prTitle.trim()}
                className="flex items-center gap-2 rounded-lg bg-purple-600 px-4 py-2 text-sm font-medium text-white hover:bg-purple-500 disabled:opacity-50"
              >
                {creatingPR ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <GitPullRequest className="h-4 w-4" />
                )}
                {creatingPR ? 'Creating...' : 'Create Pull Request'}
              </button>
              <button
                onClick={() => setShowPRForm(false)}
                className="px-4 py-2 text-sm text-gray-400 hover:text-white"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Content */}
      <div className="flex flex-1 overflow-hidden">
        {/* File List */}
        <div className="w-80 border-r border-gray-800 overflow-y-auto">
          {results.map((result, index) => (
            <div key={`${result.file}-${index}`}>
              <button
                onClick={() => {
                  setSelectedFile(result.file);
                  toggleExpand(result.file);
                }}
                className={`flex w-full items-center gap-2 px-4 py-3 text-left hover:bg-gray-800/50 ${
                  selectedFile === result.file ? 'bg-blue-500/10' : ''
                }`}
              >
                {/* Expand icon */}
                {expandedFiles.has(result.file) ? (
                  <ChevronDown className="h-4 w-4 text-gray-500 shrink-0" />
                ) : (
                  <ChevronRight className="h-4 w-4 text-gray-500 shrink-0" />
                )}

                {/* Status icon */}
                {result.success ? (
                  <CheckCircle2 className="h-4 w-4 text-green-500 shrink-0" />
                ) : (
                  <AlertCircle className="h-4 w-4 text-red-500 shrink-0" />
                )}

                {/* File info */}
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    {getActionIcon(result.action)}
                    <span className="truncate text-sm text-gray-300">
                      {result.file.split('/').pop()}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 mt-1">
                    {getActionBadge(result.action)}
                    {result.diff && <DiffStats diff={result.diff} />}
                  </div>
                </div>
              </button>

              {/* Expanded path */}
              {expandedFiles.has(result.file) && (
                <div className="px-4 py-2 bg-gray-800/30 border-b border-gray-800">
                  <p className="text-xs text-gray-500 font-mono truncate">
                    {result.file}
                  </p>
                  {result.error && (
                    <p className="text-xs text-red-400 mt-1">{result.error}</p>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Diff Viewer */}
        <div className="flex-1 overflow-hidden">
          {selectedResult ? (
            <DiffViewer
              diff={selectedResult.diff}
              fileName={selectedResult.file}
            />
          ) : (
            <div className="flex h-full items-center justify-center text-gray-500">
              <p>Select a file to view changes</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
