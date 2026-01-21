import {useCallback, useState} from 'react';
import {useAuthStore} from '@/lib/store';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

export interface GitHubIssue {
    id: string;
    github_id: number;
    number: number;
    title: string;
    body: string | null;
    state: 'open' | 'closed';
    author_username: string | null;
    author_avatar_url: string | null;
    labels: Array<{ name: string; color: string }>;
    assignees: Array<{ login: string; avatar_url: string }>;
    comments_count: number;
    html_url: string;
    github_created_at: string;
    github_updated_at: string;
    synced_at: string;
}

export interface GitHubAction {
    id: string;
    github_id: number;
    workflow_name: string;
    run_number: number;
    status: string;
    conclusion: string | null;
    head_branch: string | null;
    actor_username: string | null;
    actor_avatar_url: string | null;
    html_url: string;
    github_created_at: string;
    synced_at: string;
}

export interface GitHubInsights {
    id: string;
    project_id: string;
    views_count: number;
    views_uniques: number;
    clones_count: number;
    clones_uniques: number;
    stars_count: number;
    forks_count: number;
    watchers_count: number;
    open_issues_count: number;
    languages: Record<string, { bytes: number; percentage: number }>;
    contributors: Array<{ login: string; avatar_url: string; total: number }>;
    synced_at: string;
}

interface UseGitHubDataReturn {
    issues: GitHubIssue[];
    actions: GitHubAction[];
    insights: GitHubInsights | null;
    loading: boolean;
    syncing: boolean;
    error: string | null;

    fetchIssues: (projectId: string, state?: string) => Promise<void>;
    fetchActions: (projectId: string) => Promise<void>;
    fetchInsights: (projectId: string) => Promise<void>;
    syncIssues: (projectId: string) => Promise<void>;
    syncActions: (projectId: string) => Promise<void>;
    syncInsights: (projectId: string) => Promise<void>;
    syncAll: (projectId: string) => Promise<void>;
}

export function useGitHubData(): UseGitHubDataReturn {
    const {token} = useAuthStore();
    const [issues, setIssues] = useState<GitHubIssue[]>([]);
    const [actions, setActions] = useState<GitHubAction[]>([]);
    const [insights, setInsights] = useState<GitHubInsights | null>(null);
    const [loading, setLoading] = useState(false);
    const [syncing, setSyncing] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const headers = useCallback(() => ({
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
    }), [token]);

    const fetchIssues = useCallback(async (projectId: string, state?: string) => {
        setLoading(true);
        setError(null);

        try {
            const url = new URL(`${API_BASE}/github-data/projects/${projectId}/issues`);
            if (state) url.searchParams.set('state', state);

            const response = await fetch(url.toString(), {headers: headers()});

            if (!response.ok) throw new Error('Failed to fetch issues');

            const data = await response.json();
            setIssues(data);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Unknown error');
        } finally {
            setLoading(false);
        }
    }, [headers]);

    const fetchActions = useCallback(async (projectId: string) => {
        setLoading(true);
        setError(null);

        try {
            const response = await fetch(
                `${API_BASE}/github-data/projects/${projectId}/actions`,
                {headers: headers()}
            );

            if (!response.ok) throw new Error('Failed to fetch actions');

            const data = await response.json();
            setActions(data);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Unknown error');
        } finally {
            setLoading(false);
        }
    }, [headers]);

    const fetchInsights = useCallback(async (projectId: string) => {
        setLoading(true);
        setError(null);

        try {
            const response = await fetch(
                `${API_BASE}/github-data/projects/${projectId}/insights`,
                {headers: headers()}
            );

            if (!response.ok) {
                if (response.status === 404) {
                    setInsights(null);
                    return;
                }
                throw new Error('Failed to fetch insights');
            }

            const data = await response.json();
            setInsights(data);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Unknown error');
        } finally {
            setLoading(false);
        }
    }, [headers]);

    const syncIssues = useCallback(async (projectId: string) => {
        setSyncing(true);
        setError(null);

        try {
            const response = await fetch(
                `${API_BASE}/github-data/projects/${projectId}/sync/issues`,
                {method: 'POST', headers: headers()}
            );

            if (!response.ok) throw new Error('Failed to sync issues');

            await fetchIssues(projectId);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Unknown error');
        } finally {
            setSyncing(false);
        }
    }, [headers, fetchIssues]);

    const syncActions = useCallback(async (projectId: string) => {
        setSyncing(true);
        setError(null);

        try {
            const response = await fetch(
                `${API_BASE}/github-data/projects/${projectId}/sync/actions`,
                {method: 'POST', headers: headers()}
            );

            if (!response.ok) throw new Error('Failed to sync actions');

            await fetchActions(projectId);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Unknown error');
        } finally {
            setSyncing(false);
        }
    }, [headers, fetchActions]);

    const syncInsights = useCallback(async (projectId: string) => {
        setSyncing(true);
        setError(null);

        try {
            const response = await fetch(
                `${API_BASE}/github-data/projects/${projectId}/sync/insights`,
                {method: 'POST', headers: headers()}
            );

            if (!response.ok) throw new Error('Failed to sync insights');

            const data = await response.json();
            setInsights(data);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Unknown error');
        } finally {
            setSyncing(false);
        }
    }, [headers]);

    const syncAll = useCallback(async (projectId: string) => {
        setSyncing(true);
        setError(null);

        try {
            const response = await fetch(
                `${API_BASE}/github-data/projects/${projectId}/sync/all`,
                {method: 'POST', headers: headers()}
            );

            if (!response.ok) throw new Error('Failed to sync all data');

            // Refresh all data
            await Promise.all([
                fetchIssues(projectId),
                fetchActions(projectId),
                fetchInsights(projectId),
            ]);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Unknown error');
        } finally {
            setSyncing(false);
        }
    }, [headers, fetchIssues, fetchActions, fetchInsights]);

    return {
        issues,
        actions,
        insights,
        loading,
        syncing,
        error,
        fetchIssues,
        fetchActions,
        fetchInsights,
        syncIssues,
        syncActions,
        syncInsights,
        syncAll,
    };
}