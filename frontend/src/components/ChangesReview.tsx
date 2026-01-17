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
} from 'lucide-react';
import { DiffViewer, DiffStats } from './DiffViewer';

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
  onDiscard: () => void;
}

export function ChangesReview({ results, projectId, onDiscard }: ChangesReviewProps) {
  const [selectedFile, setSelectedFile] = useState<string | null>(
    results.length > 0 ? results[0].file : null
  );
  const [expandedFiles, setExpandedFiles] = useState<Set<string>>(new Set());
  const [applyingAll, setApplyingAll] = useState(false);
  const [creatingPR, setCreatingPR] = useState(false);

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
    setApplyingAll(true);
    try {
      // TODO: Implement apply all changes to repo
      console.log('Applying all changes...', results);
      alert('Apply All feature coming soon!');
    } catch (error) {
      console.error('Failed to apply changes:', error);
    } finally {
      setApplyingAll(false);
    }
  };

  const handleCreatePR = async () => {
    setCreatingPR(true);
    try {
      // TODO: Implement PR creation
      console.log('Creating PR...', results);
      alert('Create PR feature coming soon!');
    } catch (error) {
      console.error('Failed to create PR:', error);
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
      <div className="flex items-center justify-between border-b border-gray-800 px-4 py-3">
        <div className="flex items-center gap-4">
          <h2 className="font-semibold text-white">Review Changes</h2>
          <div className="flex items-center gap-3 text-sm">
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
            Download
          </button>
          <button
            onClick={onDiscard}
            className="flex items-center gap-2 rounded-lg bg-gray-800 px-3 py-1.5 text-sm font-medium text-red-400 hover:bg-red-500/10"
          >
            <X className="h-4 w-4" />
            Discard
          </button>
          <button
            onClick={handleCreatePR}
            disabled={creatingPR || stats.failed > 0}
            className="flex items-center gap-2 rounded-lg bg-purple-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-purple-500 disabled:opacity-50"
          >
            <GitPullRequest className="h-4 w-4" />
            {creatingPR ? 'Creating...' : 'Create PR'}
          </button>
          <button
            onClick={handleApplyAll}
            disabled={applyingAll || stats.failed > 0}
            className="flex items-center gap-2 rounded-lg bg-green-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-green-500 disabled:opacity-50"
          >
            <Check className="h-4 w-4" />
            {applyingAll ? 'Applying...' : 'Apply All'}
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex flex-1 overflow-hidden">
        {/* File List */}
        <div className="w-80 border-r border-gray-800 overflow-y-auto">
          {results.map((result) => (
            <div key={result.file}>
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
