'use client';

import { useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore, useProjectsStore } from '@/lib/store';
import { projectsApi, githubApi } from '@/lib/api';

interface Project {
  id: string;
  name: string;
  repo_full_name: string;
  repo_url: string;
  status: 'pending' | 'cloning' | 'indexing' | 'ready' | 'error';
  indexed_files_count: number;
  laravel_version: string | null;
  error_message: string | null;
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
  const { isAuthenticated, user, logout } = useAuthStore();
  const { projects, setProjects, addProject } = useProjectsStore();
  const [loading, setLoading] = useState(true);
  const [mounted, setMounted] = useState(false);

  // Modal state
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [repos, setRepos] = useState<GitHubRepo[]>([]);
  const [reposLoading, setReposLoading] = useState(false);
  const [reposError, setReposError] = useState<string | null>(null);
  const [addingRepoId, setAddingRepoId] = useState<number | null>(null);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (mounted && !isAuthenticated) {
      router.push('/');
      return;
    }

    const fetchProjects = async () => {
      try {
        const response = await projectsApi.list();
        setProjects(response.data);
      } catch (error) {
        console.error('Failed to fetch projects:', error);
      } finally {
        setLoading(false);
      }
    };

    if (mounted && isAuthenticated) {
      fetchProjects();
    }
  }, [mounted, isAuthenticated, router, setProjects]);

  const fetchGitHubRepos = useCallback(async () => {
    setReposLoading(true);
    setReposError(null);
    try {
      const response = await githubApi.listRepos();
      setRepos(response.data);
    } catch (error: any) {
      console.error('Failed to fetch GitHub repos:', error);
      setReposError(error.response?.data?.detail || 'Failed to fetch repositories');
    } finally {
      setReposLoading(false);
    }
  }, []);

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
      closeModal();
    } catch (error: any) {
      console.error('Failed to add project:', error);
      if (error.response?.status === 409) {
        setReposError('This repository is already connected.');
      } else {
        setReposError(error.response?.data?.detail || 'Failed to add project');
      }
    } finally {
      setAddingRepoId(null);
    }
  }, [addProject, closeModal]);

  const handleDeleteProject = useCallback(async (projectId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm('Are you sure you want to delete this project?')) return;

    try {
      await projectsApi.delete(projectId);
      setProjects(projects.filter(p => p.id !== projectId));
    } catch (error) {
      console.error('Failed to delete project:', error);
    }
  }, [projects, setProjects]);

  // Check if repo is already added
  const isRepoAdded = useCallback((repoId: number) => {
    return projects.some(p => p.repo_full_name === repos.find(r => r.id === repoId)?.full_name);
  }, [projects, repos]);

  if (!mounted) return null;

  const getStatusBadge = (status: Project['status']) => {
    const styles = {
      pending: 'bg-yellow-500/10 text-yellow-500',
      cloning: 'bg-purple-500/10 text-purple-500',
      indexing: 'bg-blue-500/10 text-blue-500',
      ready: 'bg-green-500/10 text-green-500',
      error: 'bg-red-500/10 text-red-500',
    };
    return (
      <span className={`rounded-full px-2 py-1 text-xs font-medium ${styles[status]}`}>
        {status}
      </span>
    );
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
        <div className="flex items-center gap-4">
          <button
            onClick={openModal}
            className="inline-flex h-10 items-center justify-center rounded-md bg-blue-600 px-4 text-sm font-medium text-white transition-colors hover:bg-blue-700"
          >
            + Connect Repository
          </button>
          <button
            onClick={logout}
            className="inline-flex h-10 items-center justify-center rounded-md border border-gray-700 bg-transparent px-4 text-sm font-medium text-gray-300 transition-colors hover:bg-gray-800"
          >
            Logout
          </button>
        </div>
      </div>

      {/* Projects Grid */}
      <div className="mt-8">
        <h2 className="text-xl font-semibold text-white">Your Projects</h2>

        {loading ? (
          <div className="mt-6 flex justify-center">
            <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-500 border-t-transparent" />
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
                      className="rounded p-1 text-gray-500 opacity-0 transition-opacity hover:bg-gray-800 hover:text-red-500 group-hover:opacity-100"
                      title="Delete project"
                    >
                      <svg
                        xmlns="http://www.w3.org/2000/svg"
                        className="h-4 w-4"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                        />
                      </svg>
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
