'use client';

import { useState, useEffect, useCallback } from 'react';
import {
    projectsApi,
    gitChangesApi,
    chatApi,
    GitChange,
    Conversation,
} from '@/lib/api';
import api from '@/lib/api';

// ============== TYPES ==============

export interface UsageStats {
    today: { requests: number; tokens: number; cost: number };
    this_week: { requests: number; tokens: number; cost: number };
    this_month: { requests: number; tokens: number; cost: number };
}

export interface Project {
    id: string;
    name: string;
    repo_full_name: string;
    repo_url: string;
    default_branch: string;
    status: string;
    indexed_files_count: number;
    laravel_version: string | null;
    health_score?: number;
    created_at: string;
    updated_at: string;
}

export interface Activity {
    id: string;
    type: 'commit' | 'pr' | 'alert' | 'deploy' | 'change';
    message: string;
    user: string;
    timestamp: string;
    meta: string;
    projectId?: string;
}

// ============== HOOKS ==============

/**
 * Hook to fetch all projects
 */
export function useProjects() {
    const [projects, setProjects] = useState<Project[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const fetchProjects = useCallback(async () => {
        try {
            setLoading(true);
            const response = await projectsApi.list();
            setProjects(response.data);
            setError(null);
        } catch (err: any) {
            console.error('Failed to fetch projects:', err);
            setError(err.message || 'Failed to fetch projects');
            setProjects([]);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchProjects();
    }, [fetchProjects]);

    return { projects, loading, error, refetch: fetchProjects };
}

/**
 * Hook to fetch usage statistics
 */
export function useUsageStats() {
    const [stats, setStats] = useState<UsageStats | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const fetchStats = useCallback(async () => {
        try {
            setLoading(true);
            const response = await api.get('/usage/stats');
            setStats(response.data);
            setError(null);
        } catch (err: any) {
            console.error('Failed to fetch usage stats:', err);
            setError(err.message || 'Failed to fetch usage stats');
            // Set default stats on error
            setStats({
                today: { requests: 0, tokens: 0, cost: 0 },
                this_week: { requests: 0, tokens: 0, cost: 0 },
                this_month: { requests: 0, tokens: 0, cost: 0 },
            });
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchStats();
    }, [fetchStats]);

    return { stats, loading, error, refetch: fetchStats };
}

/**
 * Hook to fetch git changes for a project
 */
export function useGitChanges(projectId: string | null) {
    const [changes, setChanges] = useState<GitChange[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const fetchChanges = useCallback(async () => {
        if (!projectId) {
            setChanges([]);
            return;
        }

        try {
            setLoading(true);
            const response = await gitChangesApi.listProjectChanges(projectId, { limit: 10 });
            setChanges(response.data);
            setError(null);
        } catch (err: any) {
            console.error('Failed to fetch changes:', err);
            setError(err.message || 'Failed to fetch changes');
            setChanges([]);
        } finally {
            setLoading(false);
        }
    }, [projectId]);

    useEffect(() => {
        fetchChanges();
    }, [fetchChanges]);

    return { changes, loading, error, refetch: fetchChanges };
}

/**
 * Hook to fetch conversations for a project
 */
export function useConversations(projectId: string | null) {
    const [conversations, setConversations] = useState<Conversation[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const fetchConversations = useCallback(async () => {
        if (!projectId) {
            setConversations([]);
            return;
        }

        try {
            setLoading(true);
            const response = await chatApi.listConversations(projectId);
            setConversations(response.data);
            setError(null);
        } catch (err: any) {
            console.error('Failed to fetch conversations:', err);
            setError(err.message || 'Failed to fetch conversations');
            setConversations([]);
        } finally {
            setLoading(false);
        }
    }, [projectId]);

    useEffect(() => {
        fetchConversations();
    }, [fetchConversations]);

    return { conversations, loading, error, refetch: fetchConversations };
}

/**
 * Hook to fetch combined activity feed from git changes
 */
export function useActivityFeed(projectId: string | null) {
    const [activities, setActivities] = useState<Activity[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const fetchActivities = useCallback(async () => {
        if (!projectId) {
            setActivities([]);
            return;
        }

        try {
            setLoading(true);

            // Fetch git changes
            const changesResponse = await gitChangesApi.listProjectChanges(projectId, { limit: 20 });

            // Transform git changes to activity items
            const changeActivities: Activity[] = changesResponse.data.map((change: GitChange) => {
                let type: Activity['type'] = 'change';
                if (change.status === 'pr_created' || change.status === 'pr_merged') {
                    type = 'pr';
                } else if (change.commit_hash) {
                    type = 'commit';
                }

                return {
                    id: change.id,
                    type,
                    message: change.title || change.change_summary || 'Code change',
                    user: 'AI Assistant',
                    timestamp: new Date(change.created_at).toLocaleTimeString('en-US', {
                        hour12: false,
                        hour: '2-digit',
                        minute: '2-digit',
                        second: '2-digit',
                    }),
                    meta: change.commit_hash?.slice(0, 7) || change.status,
                    projectId: change.project_id,
                };
            });

            setActivities(changeActivities.slice(0, 10));
            setError(null);
        } catch (err: any) {
            console.error('Failed to fetch activities:', err);
            setError(err.message || 'Failed to fetch activities');
            setActivities([]);
        } finally {
            setLoading(false);
        }
    }, [projectId]);

    useEffect(() => {
        fetchActivities();
    }, [fetchActivities]);

    return { activities, loading, error, refetch: fetchActivities };
}

/**
 * Hook to fetch project health
 */
export function useProjectHealth(projectId: string | null) {
    const [health, setHealth] = useState<any>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const fetchHealth = useCallback(async () => {
        if (!projectId) {
            setHealth(null);
            return;
        }

        try {
            setLoading(true);
            const response = await projectsApi.getHealth(projectId);
            setHealth(response.data);
            setError(null);
        } catch (err: any) {
            // Health might not be available if project not scanned - this is OK
            console.log('Health not available:', err.message);
            setHealth(null);
            setError(null);
        } finally {
            setLoading(false);
        }
    }, [projectId]);

    useEffect(() => {
        fetchHealth();
    }, [fetchHealth]);

    return { health, loading, error, refetch: fetchHealth };
}

/**
 * Main hook to manage all dashboard data
 */
export function useDashboard() {
    const { projects, loading: projectsLoading, refetch: refetchProjects } = useProjects();
    const { stats, loading: statsLoading, refetch: refetchStats } = useUsageStats();
    const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);

    // Auto-select first project when projects load
    useEffect(() => {
        if (projects.length > 0 && !selectedProjectId) {
            setSelectedProjectId(projects[0].id);
        }
    }, [projects, selectedProjectId]);

    const selectedProject = projects.find(p => p.id === selectedProjectId) || null;

    const { changes, loading: changesLoading, refetch: refetchChanges } = useGitChanges(selectedProjectId);
    const { activities, loading: activitiesLoading, refetch: refetchActivities } = useActivityFeed(selectedProjectId);
    const { health } = useProjectHealth(selectedProjectId);

    const refetchAll = useCallback(() => {
        refetchProjects();
        refetchStats();
        if (selectedProjectId) {
            refetchChanges();
            refetchActivities();
        }
    }, [refetchProjects, refetchStats, refetchChanges, refetchActivities, selectedProjectId]);

    return {
        // Data
        projects,
        selectedProject,
        stats,
        changes,
        activities,
        health,

        // Loading states
        loading: projectsLoading || statsLoading,
        changesLoading,
        activitiesLoading,

        // Actions
        setSelectedProjectId,
        refetch: refetchAll,
    };
}