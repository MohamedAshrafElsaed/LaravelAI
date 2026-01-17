'use client';

import { useState, useEffect, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import {
  RefreshCw,
  GitBranch,
  ArrowLeft,
  MessageSquare,
  Code,
  FileText,
  PanelLeftClose,
  PanelLeft,
  Folder,
  GitPullRequest,
  ShieldCheck,
} from 'lucide-react';

import { projectsApi } from '@/lib/api';
import { useAuthStore } from '@/lib/store';
import { FileTree } from '@/components/FileTree';
import { Chat } from '@/components/Chat';
import { CodeViewer } from '@/components/CodeViewer';
import { ChangesReview } from '@/components/ChangesReview';
import { GitPanel } from '@/components/GitPanel';
import { GitChangesTracker } from '@/components/GitChangesTracker';
import { ProjectHealth, HealthScoreBadge } from '@/components/ProjectHealth';

interface Project {
  id: string;
  name: string;
  repo_full_name: string;
  repo_url: string;
  default_branch: string;
  clone_path?: string;
  status: 'pending' | 'cloning' | 'scanning' | 'analyzing' | 'indexing' | 'ready' | 'error';
  indexed_files_count: number;
  laravel_version: string | null;
  error_message: string | null;
  // Scanner fields
  stack?: any;
  file_stats?: any;
  health_score?: number;
  scan_progress?: number;
  scan_message?: string;
  scanned_at?: string;
}

type ViewMode = 'chat' | 'code' | 'changes' | 'git' | 'health';

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
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [mounted, setMounted] = useState(false);

  // AI execution results (for changes review)
  const [executionResults, setExecutionResults] = useState<any[]>([]);
  const [currentConversationId, setCurrentConversationId] = useState<string | null>(null);
  const [lastMessageId, setLastMessageId] = useState<string | null>(null);

  useEffect(() => {
    setMounted(true);
  }, []);

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
    if (mounted && !isAuthenticated) {
      router.push('/');
      return;
    }
    if (mounted) {
      fetchProject();
    }
  }, [mounted, isAuthenticated, router, fetchProject]);

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
    // Close sidebar on mobile after selection
    if (window.innerWidth < 768) {
      setSidebarOpen(false);
    }
  };

  // Handle AI processing events
  const handleProcessingEvent = (event: any) => {
    // Capture message_id if available
    if (event.data?.message_id) {
      setLastMessageId(event.data.message_id);
    }

    // Check for execution results in complete event
    if (event.event === 'complete' && event.data?.execution_results) {
      setExecutionResults(event.data.execution_results);
      if (event.data.execution_results.length > 0) {
        setViewMode('changes');
      }
    }
  };

  // Status badge
  const getStatusBadge = (status: Project['status']) => {
    const styles: Record<string, string> = {
      pending: 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30',
      cloning: 'bg-purple-500/20 text-purple-400 border border-purple-500/30',
      scanning: 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/30',
      analyzing: 'bg-orange-500/20 text-orange-400 border border-orange-500/30',
      indexing: 'bg-blue-500/20 text-blue-400 border border-blue-500/30',
      ready: 'bg-green-500/20 text-green-400 border border-green-500/30',
      error: 'bg-red-500/20 text-red-400 border border-red-500/30',
    };
    const isInProgress = status === 'cloning' || status === 'indexing' || status === 'scanning' || status === 'analyzing';
    return (
      <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${styles[status] || styles.pending}`}>
        {isInProgress && (
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-current opacity-75"></span>
            <span className="relative inline-flex h-2 w-2 rounded-full bg-current"></span>
          </span>
        )}
        {status.charAt(0).toUpperCase() + status.slice(1)}
      </span>
    );
  };

  if (!mounted) return null;

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gradient-to-b from-gray-900 to-gray-950">
        <div className="flex flex-col items-center gap-4">
          <div className="h-10 w-10 animate-spin rounded-full border-4 border-blue-500/30 border-t-blue-500" />
          <p className="text-sm text-gray-400">Loading project...</p>
        </div>
      </div>
    );
  }

  if (!project) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center bg-gradient-to-b from-gray-900 to-gray-950 px-4">
        <div className="rounded-2xl bg-gray-800/50 p-8 text-center backdrop-blur-sm border border-gray-700/50">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-red-500/10">
            <Folder className="h-8 w-8 text-red-400" />
          </div>
          <h1 className="text-xl font-semibold text-white">Project not found</h1>
          <p className="mt-2 text-gray-400">The project you're looking for doesn't exist.</p>
          <button
            onClick={() => router.push('/dashboard')}
            className="mt-6 inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-500"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Dashboard
          </button>
        </div>
      </div>
    );
  }

  const isReady = project.status === 'ready';

  return (
    <div className="flex h-screen flex-col bg-gray-950 text-white overflow-hidden">
      {/* Header */}
      <header className="flex-shrink-0 flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-gray-800 bg-gray-900/80 backdrop-blur-sm px-4 py-3">
        <div className="flex items-center gap-3 min-w-0">
          <button
            onClick={() => router.push('/dashboard')}
            className="flex-shrink-0 rounded-lg p-2 text-gray-400 transition-colors hover:bg-gray-800 hover:text-white"
            title="Back to Dashboard"
          >
            <ArrowLeft className="h-5 w-5" />
          </button>

          <div className="min-w-0 flex-1">
            <h1 className="truncate text-lg font-semibold">{project.name}</h1>
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-gray-400">
              <span className="inline-flex items-center gap-1">
                <GitBranch className="h-3.5 w-3.5" />
                {project.default_branch}
              </span>
              <span className="hidden sm:inline">•</span>
              <span>{project.indexed_files_count} files</span>
              {project.laravel_version && (
                <>
                  <span className="hidden sm:inline">•</span>
                  <span className="text-orange-400">Laravel {project.laravel_version}</span>
                </>
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2 flex-shrink-0">
          {project.health_score !== undefined && (
            <HealthScoreBadge score={project.health_score} />
          )}
          {getStatusBadge(project.status)}
          <button
            onClick={handleSync}
            disabled={syncing || !isReady}
            className="inline-flex items-center gap-2 rounded-lg bg-gray-800 px-3 py-2 text-sm font-medium transition-colors hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed border border-gray-700"
          >
            <RefreshCw className={`h-4 w-4 ${syncing ? 'animate-spin' : ''}`} />
            <span className="hidden sm:inline">Sync</span>
          </button>
        </div>
      </header>

      {/* Main Content */}
      {isReady ? (
        <div className="flex flex-1 overflow-hidden">
          {/* Sidebar Toggle for Mobile */}
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="md:hidden fixed bottom-4 left-4 z-50 flex h-12 w-12 items-center justify-center rounded-full bg-blue-600 text-white shadow-lg shadow-blue-500/25 transition-transform hover:scale-105"
          >
            {sidebarOpen ? <PanelLeftClose className="h-5 w-5" /> : <PanelLeft className="h-5 w-5" />}
          </button>

          {/* File Tree Sidebar */}
          <aside
            className={`
              ${sidebarOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}
              fixed md:relative inset-y-0 left-0 z-40 w-72 md:w-64 lg:w-72
              flex-shrink-0 border-r border-gray-800 bg-gray-900
              transition-transform duration-300 ease-in-out
              md:block
            `}
            style={{ top: 'auto', height: 'calc(100vh - 73px)' }}
          >
            <FileTree
              projectId={projectId}
              onFileSelect={handleFileSelect}
              selectedFile={selectedFile}
            />
          </aside>

          {/* Overlay for mobile */}
          {sidebarOpen && (
            <div
              className="fixed inset-0 z-30 bg-black/50 md:hidden"
              onClick={() => setSidebarOpen(false)}
            />
          )}

          {/* Main Area */}
          <main className="flex flex-1 flex-col overflow-hidden">
            {/* View Mode Tabs */}
            <div className="flex-shrink-0 flex items-center gap-1 border-b border-gray-800 bg-gray-900/50 px-2 overflow-x-auto">
              <button
                onClick={() => setViewMode('chat')}
                className={`flex items-center gap-2 px-4 py-3 text-sm font-medium transition-colors whitespace-nowrap ${
                  viewMode === 'chat'
                    ? 'border-b-2 border-blue-500 text-blue-400'
                    : 'text-gray-400 hover:text-white'
                }`}
              >
                <MessageSquare className="h-4 w-4" />
                Chat
              </button>
              <button
                onClick={() => setViewMode('code')}
                className={`flex items-center gap-2 px-4 py-3 text-sm font-medium transition-colors whitespace-nowrap ${
                  viewMode === 'code'
                    ? 'border-b-2 border-blue-500 text-blue-400'
                    : 'text-gray-400 hover:text-white'
                }`}
              >
                <Code className="h-4 w-4" />
                Code
              </button>
              {executionResults.length > 0 && (
                <button
                  onClick={() => setViewMode('changes')}
                  className={`flex items-center gap-2 px-4 py-3 text-sm font-medium transition-colors whitespace-nowrap ${
                    viewMode === 'changes'
                      ? 'border-b-2 border-blue-500 text-blue-400'
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
              <button
                onClick={() => setViewMode('git')}
                className={`flex items-center gap-2 px-4 py-3 text-sm font-medium transition-colors whitespace-nowrap ${
                  viewMode === 'git'
                    ? 'border-b-2 border-purple-500 text-purple-400'
                    : 'text-gray-400 hover:text-white'
                }`}
              >
                <GitPullRequest className="h-4 w-4" />
                Git
              </button>
              <button
                onClick={() => setViewMode('health')}
                className={`flex items-center gap-2 px-4 py-3 text-sm font-medium transition-colors whitespace-nowrap ${
                  viewMode === 'health'
                    ? 'border-b-2 border-green-500 text-green-400'
                    : 'text-gray-400 hover:text-white'
                }`}
              >
                <ShieldCheck className="h-4 w-4" />
                Health
                {project.health_score !== undefined && (
                  <span className={`rounded-full px-2 py-0.5 text-xs ${
                    project.health_score >= 80 ? 'bg-green-500/20 text-green-400' :
                    project.health_score >= 60 ? 'bg-yellow-500/20 text-yellow-400' :
                    'bg-red-500/20 text-red-400'
                  }`}>
                    {Math.round(project.health_score)}
                  </span>
                )}
              </button>
            </div>

            {/* View Content */}
            <div className="flex-1 overflow-hidden">
              {viewMode === 'chat' && (
                <Chat
                  projectId={projectId}
                  onProcessingEvent={handleProcessingEvent}
                  onConversationChange={setCurrentConversationId}
                />
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
                  conversationId={currentConversationId || undefined}
                  messageId={lastMessageId || undefined}
                  defaultBranch={project?.default_branch || 'main'}
                  onDiscard={() => {
                    setExecutionResults([]);
                    setViewMode('chat');
                  }}
                  onChangeTracked={(changeId) => {
                    console.log('Change tracked:', changeId);
                  }}
                />
              )}

              {viewMode === 'git' && (
                <div className="h-full overflow-y-auto p-4">
                  <div className="max-w-2xl mx-auto space-y-4">
                    <div className="text-center mb-6">
                      <h2 className="text-lg font-semibold text-white">Git Operations</h2>
                      <p className="text-sm text-gray-400 mt-1">
                        Manage branches, sync with remote, and create pull requests
                      </p>
                    </div>
                    <GitPanel
                      projectId={projectId}
                      defaultBranch={project?.default_branch || 'main'}
                      onPRCreated={(url) => {
                        console.log('PR created:', url);
                      }}
                    />
                    <GitChangesTracker
                      projectId={projectId}
                      conversationId={currentConversationId || undefined}
                      defaultBranch={project?.default_branch || 'main'}
                    />
                  </div>
                </div>
              )}

              {viewMode === 'health' && (
                <ProjectHealth
                  projectId={projectId}
                  clonePath={project?.clone_path}
                />
              )}
            </div>
          </main>
        </div>
      ) : (
        /* Not Ready State */
        <div className="flex flex-1 items-center justify-center p-4">
          <div className="max-w-md w-full rounded-2xl bg-gray-800/50 p-8 text-center backdrop-blur-sm border border-gray-700/50">
            {project.status === 'error' ? (
              <>
                <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-red-500/10">
                  <span className="text-3xl">⚠️</span>
                </div>
                <h2 className="text-xl font-semibold text-red-400">Something went wrong</h2>
                <p className="mt-3 text-gray-400">{project.error_message || 'An unexpected error occurred.'}</p>
                <button
                  onClick={handleSync}
                  className="mt-6 inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-500"
                >
                  <RefreshCw className="h-4 w-4" />
                  Try Again
                </button>
              </>
            ) : (
              <>
                <div className="relative mx-auto mb-6 h-16 w-16">
                  <div className="absolute inset-0 animate-spin rounded-full border-4 border-blue-500/30 border-t-blue-500" />
                  <div className="absolute inset-2 animate-pulse rounded-full bg-blue-500/10" />
                </div>
                <h2 className="text-xl font-semibold text-white">
                  {project.status === 'cloning' ? 'Cloning Repository' :
                   project.status === 'indexing' ? 'Indexing Files' : 'Preparing Project'}
                </h2>
                <p className="mt-3 text-gray-400">
                  {project.status === 'cloning'
                    ? 'Downloading your repository from GitHub...'
                    : 'Analyzing and indexing your Laravel codebase...'}
                </p>
                <div className="mt-6 flex items-center justify-center gap-2 text-sm text-gray-500">
                  <span className="relative flex h-2 w-2">
                    <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-blue-400 opacity-75"></span>
                    <span className="relative inline-flex h-2 w-2 rounded-full bg-blue-500"></span>
                  </span>
                  This may take a few minutes
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
