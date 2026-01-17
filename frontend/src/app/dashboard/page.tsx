'use client';

import { useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore, useProjectsStore } from '@/lib/store';
import { projectsApi, githubApi, getErrorMessage } from '@/lib/api';
import { useToast } from '@/components/Toast';
import { SkeletonProjectCard } from '@/components/ui/Skeleton';
import { Button } from '@/components/ui/Button';
import { IndexingBadge } from '@/components/IndexingProgress';
import { Loader2, Plus, Trash2, RefreshCw } from 'lucide-react';

interface Project {
  id: string;
  name?: string;
  repo_full_name: string;
  repo_url: string;
  status: 'pending' | 'cloning' | 'indexing' | 'scanning' | 'analyzing' | 'ready' | 'error';
  indexed_files_count: number;
  laravel_version: string | null;
  error_message?: string | null;
}

interface GitHubRepo {
  id: number;
  name: string;
  full_name: string;
  default_branch: string;
  private: boolean;
  updated_at: string;
  html_url: string;
  description: string | null;
  language: string | null;
}

export default function Dashboard() {
  const router = useRouter();
  const toast = useToast();
  const { isAuthenticated, user, logout, isHydrated } = useAuthStore();
  const { projects, setProjects, addProject } = useProjectsStore();
  const [loading, setLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Modal state
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [repos, setRepos] = useState<GitHubRepo[]>([]);
  const [reposLoading, setReposLoading] = useState(false);
  const [reposError, setReposError] = useState<string | null>(null);
  const [addingRepoId, setAddingRepoId] = useState<number | null>(null);
  const [deletingProjectId, setDeletingProjectId] = useState<string | null>(null);

  const [loadError, setLoadError] = useState<string | null>(null);

  const fetchProjects = useCallback(async (showRefreshToast = false) => {
    try {
      setLoadError(null);
      const response = await projectsApi.list();
      setProjects(response.data);
      if (showRefreshToast) {
        toast.success('Projects refreshed');
      }
    } catch (error) {
      console.error('Failed to fetch projects:', error);
      const message = getErrorMessage(error);
      setLoadError(message);
      if (!showRefreshToast) {
        // Only show toast on manual refresh, not initial load
        // to avoid double error display
      } else {
        toast.error('Failed to load projects', message);
      }
    } finally {
      setLoading(false);
      setIsRefreshing(false);
    }
  }, [setProjects, toast]);

  // Wait for hydration before checking authentication
  useEffect(() => {
    if (!isHydrated) return; // Wait for store to hydrate from localStorage

    if (!isAuthenticated) {
      router.push('/');
      return;
    }

    fetchProjects();
  }, [isHydrated, isAuthenticated, router, fetchProjects]);

  const handleRefresh = useCallback(() => {
    setIsRefreshing(true);
    fetchProjects(true);
  }, [fetchProjects]);

  // Polling for in-progress projects (cloning or indexing)
  const { updateProject } = useProjectsStore();
  const [pollErrorCount, setPollErrorCount] = useState(0);

  useEffect(() => {
    // Check if there are any projects in progress
    const inProgressProjects = projects.filter(
      (p) => p.status === 'cloning' || p.status === 'indexing' || p.status === 'scanning' || p.status === 'analyzing'
    );

    if (inProgressProjects.length === 0 || !isHydrated || !isAuthenticated) {
      return;
    }

    // Back off polling when errors occur
    // Base interval is 3 seconds, increases with errors (max 30 seconds)
    const pollInterval = Math.min(3000 * Math.pow(2, pollErrorCount), 30000);
    let isPolling = false; // Prevent overlapping polls

    const poll = async () => {
      if (isPolling) return; // Skip if previous poll is still running
      isPolling = true;

      let hasError = false;
      for (const project of inProgressProjects) {
        try {
          const response = await projectsApi.get(project.id);
          const updatedProject = response.data;

          // Update project state
          updateProject(project.id, {
            status: updatedProject.status,
            indexed_files_count: updatedProject.indexed_files_count,
            laravel_version: updatedProject.laravel_version,
            error_message: updatedProject.error_message,
          });
        } catch (error) {
          console.error(`Failed to poll project ${project.id}:`, error);
          hasError = true;
        }
      }

      // Reset or increment error count based on success/failure
      if (hasError) {
        setPollErrorCount(c => Math.min(c + 1, 5)); // Cap at 5 (30s interval)
      } else {
        setPollErrorCount(0); // Reset on success
      }

      isPolling = false;
    };

    const intervalId = setInterval(poll, pollInterval);

    return () => clearInterval(intervalId);
  }, [projects, isHydrated, isAuthenticated, updateProject, pollErrorCount]);

  const fetchGitHubRepos = useCallback(async () => {
    setReposLoading(true);
    setReposError(null);
    try {
      const response = await githubApi.listRepos();
      setRepos(response.data);
    } catch (error) {
      console.error('Failed to fetch GitHub repos:', error);
      const message = getErrorMessage(error);
      setReposError(message);
      toast.error('Failed to load repositories', message);
    } finally {
      setReposLoading(false);
    }
  }, [toast]);

  const openModal = useCallback(() => {
    setIsModalOpen(true);
    fetchGitHubRepos();
  }, [fetchGitHubRepos]);

  const closeModal = useCallback(() => {
    setIsModalOpen(false);
    setRepos([]);
    setReposError(null);
    setAddingRepoId(null);
  }, []);

  const handleAddProject = useCallback(async (repo: GitHubRepo) => {
    setAddingRepoId(repo.id);
    try {
      const response = await projectsApi.create(repo.id);
      addProject(response.data);
      toast.success('Project added', `${repo.name} has been connected`);
      closeModal();
    } catch (error: any) {
      console.error('Failed to add project:', error);
      const message = error.code === 'RES_ALREADY_EXISTS' || error.status === 409
        ? 'This repository is already connected.'
        : getErrorMessage(error);
      setReposError(message);
      toast.error('Failed to add project', message);
    } finally {
      setAddingRepoId(null);
    }
  }, [addProject, closeModal, toast]);

  const handleDeleteProject = useCallback(async (projectId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm('Are you sure you want to delete this project?')) return;

    setDeletingProjectId(projectId);
    try {
      await projectsApi.delete(projectId);
      setProjects(projects.filter(p => p.id !== projectId));
      toast.success('Project deleted');
    } catch (error) {
      console.error('Failed to delete project:', error);
      toast.error('Failed to delete project', getErrorMessage(error));
    } finally {
      setDeletingProjectId(null);
    }
  }, [projects, setProjects, toast]);

  // Check if repo is already added
  const isRepoAdded = useCallback((repoId: number) => {
    return projects.some(p => p.repo_full_name === repos.find(r => r.id === repoId)?.full_name);
  }, [projects, repos]);

  // Show loading while hydrating
  if (!isHydrated) {
    return (
      <div className="container mx-auto max-w-6xl px-4 py-8">
        <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <SkeletonProjectCard key={i} />
          ))}
        </div>
      </div>
    );
  }

  const getStatusBadge = (status: Project['status']) => {
    return <IndexingBadge status={status} />;
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  };

  return (
    <div className="container mx-auto max-w-6xl px-4 py-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white">Dashboard</h1>
          <p className="mt-1 text-gray-400">
            Welcome back, {user?.username}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="md"
            onClick={handleRefresh}
            loading={isRefreshing}
            leftIcon={<RefreshCw className="h-4 w-4" />}
            aria-label="Refresh projects"
          >
            <span className="sr-only sm:not-sr-only">Refresh</span>
          </Button>
          <Button
            variant="primary"
            size="md"
            onClick={openModal}
            leftIcon={<Plus className="h-4 w-4" />}
          >
            Connect Repository
          </Button>
          <Button
            variant="outline"
            size="md"
            onClick={logout}
          >
            Logout
          </Button>
        </div>
      </div>

      {/* Projects Grid */}
      <div className="mt-8">
        <h2 className="text-xl font-semibold text-white">Your Projects</h2>

        {loading ? (
          <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <SkeletonProjectCard key={i} />
            ))}
          </div>
        ) : loadError ? (
          <div className="mt-6 rounded-lg border border-red-900/50 bg-red-900/20 p-8 text-center">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="mx-auto h-12 w-12 text-red-500"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
              />
            </svg>
            <h3 className="mt-4 text-lg font-medium text-red-400">Failed to load projects</h3>
            <p className="mt-2 text-sm text-gray-400">{loadError}</p>
            <p className="mt-1 text-xs text-gray-500">Make sure the backend server is running.</p>
            <Button
              variant="outline"
              size="md"
              onClick={handleRefresh}
              loading={isRefreshing}
              leftIcon={<RefreshCw className="h-4 w-4" />}
              className="mt-4"
            >
              Try Again
            </Button>
          </div>
        ) : projects.length === 0 ? (
          <div className="mt-6 rounded-lg border-2 border-dashed border-gray-700 p-12 text-center">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="mx-auto h-12 w-12 text-gray-500"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1}
                d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"
              />
            </svg>
            <h3 className="mt-4 text-lg font-medium text-white">No projects yet</h3>
            <p className="mt-2 text-sm text-gray-400">
              Connect your first Laravel repository to get started
            </p>
            <button
              onClick={openModal}
              className="mt-4 inline-flex h-10 items-center justify-center rounded-md bg-blue-600 px-4 text-sm font-medium text-white transition-colors hover:bg-blue-700"
            >
              + Connect Repository
            </button>
          </div>
        ) : (
          <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {projects.map((project) => (
              <div
                key={project.id}
                className="group cursor-pointer rounded-lg border border-gray-800 bg-gray-900 p-6 transition-colors hover:border-blue-500/50"
                onClick={() => router.push(`/project/${project.id}`)}
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-500/10">
                      <svg
                        xmlns="http://www.w3.org/2000/svg"
                        className="h-5 w-5 text-blue-500"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"
                        />
                      </svg>
                    </div>
                    <div>
                      <h3 className="font-semibold text-white group-hover:text-blue-500">
                        {project.name || project.repo_full_name.split('/')[1]}
                      </h3>
                      <p className="text-xs text-gray-500">
                        {project.repo_full_name}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {getStatusBadge(project.status)}
                    <button
                      onClick={(e) => handleDeleteProject(project.id, e)}
                      disabled={deletingProjectId === project.id}
                      className="rounded p-1 text-gray-500 opacity-0 transition-opacity hover:bg-gray-800 hover:text-red-500 group-hover:opacity-100 disabled:opacity-100 disabled:cursor-wait"
                      title="Delete project"
                    >
                      {deletingProjectId === project.id ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Trash2 className="h-4 w-4" />
                      )}
                    </button>
                  </div>
                </div>

                {project.error_message && project.status === 'error' && (
                  <p className="mt-2 text-xs text-red-400 line-clamp-2">
                    {project.error_message}
                  </p>
                )}

                <div className="mt-4 flex items-center gap-4 text-sm text-gray-500">
                  <span>{project.indexed_files_count} files</span>
                  {project.laravel_version && (
                    <span>Laravel {project.laravel_version}</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Connect Repository Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70">
          <div className="relative w-full max-w-2xl max-h-[80vh] overflow-hidden rounded-lg border border-gray-700 bg-gray-900 shadow-xl">
            {/* Modal Header */}
            <div className="flex items-center justify-between border-b border-gray-700 px-6 py-4">
              <h2 className="text-xl font-semibold text-white">Connect Repository</h2>
              <button
                onClick={closeModal}
                className="rounded p-1 text-gray-400 hover:bg-gray-800 hover:text-white"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  className="h-6 w-6"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M6 18L18 6M6 6l12 12"
                  />
                </svg>
              </button>
            </div>

            {/* Modal Body */}
            <div className="overflow-y-auto px-6 py-4" style={{ maxHeight: 'calc(80vh - 130px)' }}>
              {reposLoading ? (
                <div className="flex items-center justify-center py-12">
                  <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-500 border-t-transparent" />
                </div>
              ) : reposError ? (
                <div className="py-8 text-center">
                  <p className="text-red-400">{reposError}</p>
                  <button
                    onClick={fetchGitHubRepos}
                    className="mt-4 text-blue-500 hover:underline"
                  >
                    Try again
                  </button>
                </div>
              ) : repos.length === 0 ? (
                <div className="py-8 text-center text-gray-400">
                  <p>No PHP/Laravel repositories found.</p>
                  <p className="mt-2 text-sm">
                    Make sure you have PHP repositories in your GitHub account.
                  </p>
                </div>
              ) : (
                <div className="space-y-2">
                  <p className="mb-4 text-sm text-gray-400">
                    Select a repository to connect. Showing PHP repositories only.
                  </p>
                  {repos.map((repo) => {
                    const alreadyAdded = projects.some(p =>
                      p.repo_full_name === repo.full_name
                    );

                    return (
                      <div
                        key={repo.id}
                        className={`flex items-center justify-between rounded-lg border p-4 transition-colors ${
                          alreadyAdded
                            ? 'border-gray-800 bg-gray-800/50 opacity-60'
                            : 'border-gray-700 bg-gray-800 hover:border-blue-500/50'
                        }`}
                      >
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <h3 className="font-medium text-white truncate">
                              {repo.name}
                            </h3>
                            {repo.private && (
                              <span className="rounded bg-gray-700 px-1.5 py-0.5 text-xs text-gray-300">
                                Private
                              </span>
                            )}
                            {repo.language && (
                              <span className="rounded bg-purple-500/20 px-1.5 py-0.5 text-xs text-purple-400">
                                {repo.language}
                              </span>
                            )}
                          </div>
                          <p className="text-sm text-gray-500 truncate">
                            {repo.full_name}
                          </p>
                          {repo.description && (
                            <p className="mt-1 text-sm text-gray-400 line-clamp-1">
                              {repo.description}
                            </p>
                          )}
                          <p className="mt-1 text-xs text-gray-500">
                            Updated {formatDate(repo.updated_at)}
                          </p>
                        </div>
                        <div className="ml-4">
                          {alreadyAdded ? (
                            <span className="text-sm text-gray-500">Connected</span>
                          ) : (
                            <button
                              onClick={() => handleAddProject(repo)}
                              disabled={addingRepoId === repo.id}
                              className="inline-flex h-8 items-center justify-center rounded-md bg-blue-600 px-3 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:opacity-50"
                            >
                              {addingRepoId === repo.id ? (
                                <div className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
                              ) : (
                                'Add'
                              )}
                            </button>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Modal Footer */}
            <div className="flex justify-end border-t border-gray-700 px-6 py-4">
              <button
                onClick={closeModal}
                className="inline-flex h-10 items-center justify-center rounded-md border border-gray-700 bg-transparent px-4 text-sm font-medium text-gray-300 transition-colors hover:bg-gray-800"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
