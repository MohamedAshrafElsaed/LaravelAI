'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { Loader2, FileCode, CheckCircle, XCircle, RefreshCw } from 'lucide-react';
import { ProgressBar, CircularProgress } from './ui/ProgressBar';
import { Button } from './ui/Button';
import { projectsApi, getErrorMessage } from '@/lib/api';

interface IndexingProgressProps {
  projectId: string;
  status: 'pending' | 'cloning' | 'indexing' | 'ready' | 'error';
  errorMessage?: string | null;
  onStatusChange?: (status: string) => void;
  compact?: boolean;
}

interface IndexingStats {
  phase: string;
  current_file?: string;
  total_files: number;
  processed_files: number;
  total_chunks: number;
  progress: number;
}

export function IndexingProgress({
  projectId,
  status,
  errorMessage,
  onStatusChange,
  compact = false,
}: IndexingProgressProps) {
  const [stats, setStats] = useState<IndexingStats | null>(null);
  const [isRetrying, setIsRetrying] = useState(false);

  // Poll for indexing stats when indexing
  useEffect(() => {
    if (status !== 'indexing') return;

    const pollInterval = setInterval(async () => {
      try {
        const response = await projectsApi.get(projectId);
        const project = response.data;

        if (project.indexing_progress) {
          setStats(project.indexing_progress);
        }

        // Check if status changed
        if (project.status !== status) {
          onStatusChange?.(project.status);
        }
      } catch (error) {
        console.error('Failed to poll indexing stats:', error);
      }
    }, 1000);

    return () => clearInterval(pollInterval);
  }, [projectId, status, onStatusChange]);

  const handleRetry = useCallback(async () => {
    setIsRetrying(true);
    try {
      await projectsApi.startIndexing(projectId);
      onStatusChange?.('indexing');
    } catch (error) {
      console.error('Failed to retry indexing:', error);
    } finally {
      setIsRetrying(false);
    }
  }, [projectId, onStatusChange]);

  // Render based on status
  if (status === 'ready') {
    if (compact) return null;
    return (
      <div className="flex items-center gap-2 text-green-400">
        <CheckCircle className="h-4 w-4" />
        <span className="text-sm">Ready</span>
      </div>
    );
  }

  if (status === 'error') {
    return (
      <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-3">
        <div className="flex items-start gap-2">
          <XCircle className="h-4 w-4 shrink-0 text-red-400 mt-0.5" />
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-red-300">Indexing failed</p>
            {errorMessage && (
              <p className="mt-1 text-xs text-red-400/80 truncate">{errorMessage}</p>
            )}
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={handleRetry}
            loading={isRetrying}
            leftIcon={<RefreshCw className="h-3 w-3" />}
          >
            Retry
          </Button>
        </div>
      </div>
    );
  }

  if (status === 'pending') {
    return (
      <div className="flex items-center gap-2 text-yellow-400">
        <div className="h-2 w-2 rounded-full bg-yellow-400 animate-pulse" />
        <span className="text-sm">Pending</span>
      </div>
    );
  }

  if (status === 'cloning') {
    return (
      <div className={compact ? 'flex items-center gap-2' : 'space-y-2'}>
        <div className="flex items-center gap-2 text-purple-400">
          <Loader2 className="h-4 w-4 animate-spin" />
          <span className="text-sm">Cloning repository...</span>
        </div>
        {!compact && (
          <ProgressBar
            value={0}
            variant="default"
            size="sm"
            animated
            striped
          />
        )}
      </div>
    );
  }

  // Indexing status
  const progress = stats?.progress || 0;
  const phase = stats?.phase || 'Starting';
  const currentFile = stats?.current_file;
  const processedFiles = stats?.processed_files || 0;
  const totalFiles = stats?.total_files || 0;
  const totalChunks = stats?.total_chunks || 0;

  if (compact) {
    return (
      <div className="flex items-center gap-3">
        <CircularProgress
          value={progress}
          size={32}
          strokeWidth={3}
          variant="default"
        />
        <div className="text-sm">
          <span className="text-blue-400">{phase}</span>
          {totalFiles > 0 && (
            <span className="text-gray-500 ml-2">
              {processedFiles}/{totalFiles} files
            </span>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-3 rounded-lg border border-blue-500/30 bg-blue-500/10 p-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Loader2 className="h-4 w-4 animate-spin text-blue-400" />
          <span className="text-sm font-medium text-blue-300">Indexing in progress</span>
        </div>
        <span className="text-sm font-bold text-blue-400">{Math.round(progress)}%</span>
      </div>

      <ProgressBar
        value={progress}
        variant="default"
        size="md"
        animated
        striped
      />

      <div className="space-y-1">
        <div className="flex items-center justify-between text-xs text-gray-400">
          <span>Phase: <span className="text-blue-300">{phase}</span></span>
          {totalFiles > 0 && (
            <span>{processedFiles} / {totalFiles} files</span>
          )}
        </div>

        {currentFile && (
          <div className="flex items-center gap-1 text-xs text-gray-500">
            <FileCode className="h-3 w-3" />
            <span className="truncate">{currentFile}</span>
          </div>
        )}

        {totalChunks > 0 && (
          <div className="text-xs text-gray-500">
            {totalChunks} code chunks indexed
          </div>
        )}
      </div>
    </div>
  );
}

// Simpler inline progress indicator
export function IndexingBadge({
  status,
  progress,
}: {
  status: 'pending' | 'cloning' | 'indexing' | 'ready' | 'error';
  progress?: number;
}) {
  const styles = {
    pending: 'bg-yellow-500/10 text-yellow-500',
    cloning: 'bg-purple-500/10 text-purple-500',
    indexing: 'bg-blue-500/10 text-blue-500',
    ready: 'bg-green-500/10 text-green-500',
    error: 'bg-red-500/10 text-red-500',
  };

  const isInProgress = status === 'cloning' || status === 'indexing';

  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2 py-1 text-xs font-medium ${styles[status]}`}>
      {isInProgress && (
        <Loader2 className="h-3 w-3 animate-spin" />
      )}
      {status}
      {status === 'indexing' && progress !== undefined && (
        <span className="font-bold">{Math.round(progress)}%</span>
      )}
    </span>
  );
}
