'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore, useProjectsStore } from '@/lib/store';
import { projectsApi } from '@/lib/api';

interface Project {
  id: string;
  repo_full_name: string;
  repo_url: string;
  status: 'pending' | 'indexing' | 'ready' | 'error';
  indexed_files_count: number;
  laravel_version: string | null;
}

export default function Dashboard() {
  const router = useRouter();
  const { isAuthenticated, user, logout } = useAuthStore();
  const { projects, setProjects } = useProjectsStore();
  const [loading, setLoading] = useState(true);
  const [mounted, setMounted] = useState(false);

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

  if (!mounted) return null;

  const getStatusBadge = (status: Project['status']) => {
    const styles = {
      pending: 'bg-yellow-500/10 text-yellow-500',
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
            onClick={() => {/* TODO: Open connect modal */}}
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
              onClick={() => {/* TODO: Open connect modal */}}
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
                        {project.repo_full_name.split('/')[1]}
                      </h3>
                      <p className="text-xs text-gray-500">
                        {project.repo_full_name}
                      </p>
                    </div>
                  </div>
                  {getStatusBadge(project.status)}
                </div>

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
    </div>
  );
}