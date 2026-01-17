'use client';

import { useState, useEffect, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import {
  Panel,
  PanelGroup,
  PanelResizeHandle,
} from 'react-resizable-panels';
import {
  RefreshCw,
  GitBranch,
  ArrowLeft,
  MessageSquare,
  Code,
  FileText,
} from 'lucide-react';

import { projectsApi } from '@/lib/api';
import { useAuthStore } from '@/lib/store';
import { FileTree } from '@/components/FileTree';
import { Chat } from '@/components/Chat';
import { CodeViewer } from '@/components/CodeViewer';
import { ProgressTracker } from '@/components/ProgressTracker';
import { ChangesReview } from '@/components/ChangesReview';

interface Project {
  id: string;
  name: string;
  repo_full_name: string;
  repo_url: string;
  default_branch: string;
  status: 'pending' | 'cloning' | 'indexing' | 'ready' | 'error';
  indexed_files_count: number;
  laravel_version: string | null;
  error_message: string | null;
}

type ViewMode = 'chat' | 'code' | 'changes';

export default function ProjectPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params.id as string;

  const { isAuthenticated } = useAuthStore();
  const [project, setProject] = useState<Project | null>(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [viewMode, setViewMode] = useState<ViewMode>('chat');
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [selectedFileContent, setSelectedFileContent] = useState<string>('');

  // AI processing state
  const [isProcessing, setIsProcessing] = useState(false);
  const [processingEvents, setProcessingEvents] = useState<any[]>([]);
  const [executionResults, setExecutionResults] = useState<any[]>([]);

  // Fetch project
  const fetchProject = useCallback(async () => {
    try {
      const response = await projectsApi.get(projectId);
      setProject(response.data);
    } catch (error) {
      console.error('Failed to fetch project:', error);
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    if (!isAuthenticated) {
      router.push('/');
      return;
    }
    fetchProject();
  }, [isAuthenticated, router, fetchProject]);

  // Sync project (re-clone and re-index)
  const handleSync = async () => {
    if (!project || syncing) return;
    setSyncing(true);
    try {
      await projectsApi.startCloning(projectId);
      await fetchProject();
    } catch (error) {
      console.error('Failed to sync project:', error);
    } finally {
      setSyncing(false);
    }
  };

  // Handle file selection from tree
  const handleFileSelect = async (filePath: string, content: string) => {
    setSelectedFile(filePath);
    setSelectedFileContent(content);
    setViewMode('code');
  };

  // Handle AI processing events
  const handleProcessingEvent = (event: any) => {
    setProcessingEvents((prev) => [...prev, event]);

    if (event.event === 'complete' && event.data?.execution_results) {
      setExecutionResults(event.data.execution_results);
      if (event.data.execution_results.length > 0) {
        setViewMode('changes');
      }
    }
  };

  // Handle processing start/end
  const handleProcessingStart = () => {
    setIsProcessing(true);
    setProcessingEvents([]);
    setExecutionResults([]);
  };

  const handleProcessingEnd = () => {
    setIsProcessing(false);
  };

  // Status badge
  const getStatusBadge = (status: Project['status']) => {
    const styles: Record<string, string> = {
      pending: 'bg-yellow-500/10 text-yellow-500',
      cloning: 'bg-purple-500/10 text-purple-500',
      indexing: 'bg-blue-500/10 text-blue-500',
      ready: 'bg-green-500/10 text-green-500',
      error: 'bg-red-500/10 text-red-500',
    };
    const isInProgress = status === 'cloning' || status === 'indexing';
    return (
      <span className={`rounded-full px-2 py-1 text-xs font-medium ${styles[status]} flex items-center gap-1`}>
        {isInProgress && (
          <div className="h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent" />
        )}
        {status}
      </span>
    );
  };

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-gray-950">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
      </div>
    );
  }

  if (!project) {
    return (
      <div className="flex h-screen flex-col items-center justify-center bg-gray-950 text-white">
        <h1 className="text-2xl font-bold">Project not found</h1>
        <button
          onClick={() => router.push('/dashboard')}
          className="mt-4 text-blue-500 hover:underline"
        >
          Back to Dashboard
        </button>
      </div>
    );
  }

  const isReady = project.status === 'ready';

  return (
    <div className="flex h-screen flex-col bg-gray-950 text-white">
      {/* Header */}
      <header className="flex items-center justify-between border-b border-gray-800 px-4 py-3">
        <div className="flex items-center gap-4">
          <button
            onClick={() => router.push('/dashboard')}
            className="text-gray-400 hover:text-white"
          >
            <ArrowLeft className="h-5 w-5" />
          </button>
          <div>
            <h1 className="text-lg font-semibold">{project.name}</h1>
            <div className="flex items-center gap-2 text-sm text-gray-400">
              <GitBranch className="h-4 w-4" />
              <span>{project.default_branch}</span>
              <span>•</span>
              <span>{project.indexed_files_count} files indexed</span>
              {project.laravel_version && (
                <>
                  <span>•</span>
                  <span>Laravel {project.laravel_version}</span>
                </>
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {getStatusBadge(project.status)}
          <button
            onClick={handleSync}
            disabled={syncing || !isReady}
            className="flex items-center gap-2 rounded-lg bg-gray-800 px-3 py-1.5 text-sm font-medium hover:bg-gray-700 disabled:opacity-50"
          >
            <RefreshCw className={`h-4 w-4 ${syncing ? 'animate-spin' : ''}`} />
            Sync
          </button>
        </div>
      </header>

      {/* Main Content */}
      {isReady ? (
        <PanelGroup direction="horizontal" className="flex-1">
          {/* File Tree Sidebar */}
          <Panel defaultSize={20} minSize={15} maxSize={35}>
            <div className="h-full border-r border-gray-800 bg-gray-900/50">
              <FileTree
                projectId={projectId}
                onFileSelect={handleFileSelect}
                selectedFile={selectedFile}
              />
            </div>
          </Panel>

          <PanelResizeHandle className="w-1 bg-gray-800 hover:bg-blue-500 transition-colors" />

          {/* Main Area */}
          <Panel defaultSize={80}>
            <div className="flex h-full flex-col">
              {/* View Mode Tabs */}
              <div className="flex border-b border-gray-800 bg-gray-900/30">
                <button
                  onClick={() => setViewMode('chat')}
                  className={`flex items-center gap-2 px-4 py-2 text-sm font-medium transition-colors ${
                    viewMode === 'chat'
                      ? 'border-b-2 border-blue-500 text-blue-500'
                      : 'text-gray-400 hover:text-white'
                  }`}
                >
                  <MessageSquare className="h-4 w-4" />
                  Chat
                </button>
                <button
                  onClick={() => setViewMode('code')}
                  className={`flex items-center gap-2 px-4 py-2 text-sm font-medium transition-colors ${
                    viewMode === 'code'
                      ? 'border-b-2 border-blue-500 text-blue-500'
                      : 'text-gray-400 hover:text-white'
                  }`}
                >
                  <Code className="h-4 w-4" />
                  Code
                </button>
                {executionResults.length > 0 && (
                  <button
                    onClick={() => setViewMode('changes')}
                    className={`flex items-center gap-2 px-4 py-2 text-sm font-medium transition-colors ${
                      viewMode === 'changes'
                        ? 'border-b-2 border-blue-500 text-blue-500'
                        : 'text-gray-400 hover:text-white'
                    }`}
                  >
                    <FileText className="h-4 w-4" />
                    Changes
                    <span className="rounded-full bg-blue-500/20 px-2 py-0.5 text-xs text-blue-400">
                      {executionResults.length}
                    </span>
                  </button>
                )}
              </div>

              {/* View Content */}
              <div className="flex-1 overflow-hidden">
                {viewMode === 'chat' && (
                  <div className="flex h-full">
                    {/* Chat Area */}
                    <div className={`flex-1 ${isProcessing ? 'w-1/2' : 'w-full'}`}>
                      <Chat
                        projectId={projectId}
                        onProcessingStart={handleProcessingStart}
                        onProcessingEnd={handleProcessingEnd}
                        onProcessingEvent={handleProcessingEvent}
                      />
                    </div>

                    {/* Progress Tracker (when processing) */}
                    {isProcessing && (
                      <div className="w-1/2 border-l border-gray-800">
                        <ProgressTracker events={processingEvents} />
                      </div>
                    )}
                  </div>
                )}

                {viewMode === 'code' && (
                  <CodeViewer
                    filePath={selectedFile}
                    content={selectedFileContent}
                  />
                )}

                {viewMode === 'changes' && (
                  <ChangesReview
                    results={executionResults}
                    projectId={projectId}
                    onDiscard={() => {
                      setExecutionResults([]);
                      setViewMode('chat');
                    }}
                  />
                )}
              </div>
            </div>
          </Panel>
        </PanelGroup>
      ) : (
        /* Not Ready State */
        <div className="flex flex-1 items-center justify-center">
          <div className="text-center">
            {project.status === 'error' ? (
              <>
                <div className="text-6xl mb-4">⚠️</div>
                <h2 className="text-xl font-semibold text-red-400">Error</h2>
                <p className="mt-2 text-gray-400">{project.error_message}</p>
                <button
                  onClick={handleSync}
                  className="mt-4 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium hover:bg-blue-500"
                >
                  Retry
                </button>
              </>
            ) : (
              <>
                <div className="h-12 w-12 mx-auto animate-spin rounded-full border-4 border-blue-500 border-t-transparent" />
                <h2 className="mt-4 text-xl font-semibold">
                  {project.status === 'cloning' ? 'Cloning Repository...' : 'Indexing Files...'}
                </h2>
                <p className="mt-2 text-gray-400">
                  This may take a few minutes depending on the repository size.
                </p>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
