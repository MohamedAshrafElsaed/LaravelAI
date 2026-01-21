import {useCallback} from 'react';
import {useAuthStore} from '@/lib/store';
import {Team, TeamMember, useTeamStore} from '@/lib/teamStore';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

interface UseTeamsReturn {
    teams: Team[];
    currentTeam: Team | null;
    members: TeamMember[];
    loading: boolean;
    error: string | null;

    // Team operations
    fetchTeams: () => Promise<void>;
    createTeam: (name: string, description?: string) => Promise<Team>;
    updateTeam: (teamId: string, updates: Partial<Team>) => Promise<Team>;
    deleteTeam: (teamId: string) => Promise<void>;
    selectTeam: (team: Team) => void;

    // Member operations
    fetchMembers: (teamId: string) => Promise<void>;
    inviteMember: (teamId: string, data: {
        github_username?: string;
        email?: string;
        role?: string
    }) => Promise<TeamMember>;
    updateMemberRole: (teamId: string, memberId: string, role: string) => Promise<TeamMember>;
    removeMember: (teamId: string, memberId: string) => Promise<void>;

    // Sync operations
    syncCollaborators: (teamId: string, projectId: string) => Promise<any>;
}

export function useTeams(): UseTeamsReturn {
    const {token} = useAuthStore();
    const {
        teams,
        currentTeam,
        members,
        loading,
        error,
        setTeams,
        setCurrentTeam,
        setMembers,
        addTeam,
        updateTeam: updateTeamInStore,
        removeTeam,
        addMember,
        updateMember,
        removeMember: removeMemberFromStore,
        setLoading,
        setError,
    } = useTeamStore();

    const headers = useCallback(() => ({
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
    }), [token]);

    // Fetch all teams
    const fetchTeams = useCallback(async () => {
        setLoading(true);
        setError(null);

        try {
            const response = await fetch(`${API_BASE}/teams`, {
                headers: headers(),
            });

            if (!response.ok) {
                throw new Error('Failed to fetch teams');
            }

            const data = await response.json();
            setTeams(data);

            // Set current team to personal team if not set
            if (!currentTeam && data.length > 0) {
                const personalTeam = data.find((t: Team) => t.is_personal);
                setCurrentTeam(personalTeam || data[0]);
            }
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Unknown error');
        } finally {
            setLoading(false);
        }
    }, [headers, currentTeam, setTeams, setCurrentTeam, setLoading, setError]);

    // Create team
    const createTeam = useCallback(async (name: string, description?: string): Promise<Team> => {
        setLoading(true);
        setError(null);

        try {
            const response = await fetch(`${API_BASE}/teams`, {
                method: 'POST',
                headers: headers(),
                body: JSON.stringify({name, description}),
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to create team');
            }

            const team = await response.json();
            addTeam(team);
            return team;
        } catch (err) {
            const message = err instanceof Error ? err.message : 'Unknown error';
            setError(message);
            throw err;
        } finally {
            setLoading(false);
        }
    }, [headers, addTeam, setLoading, setError]);

    // Update team
    const updateTeam = useCallback(async (teamId: string, updates: Partial<Team>): Promise<Team> => {
        setLoading(true);
        setError(null);

        try {
            const response = await fetch(`${API_BASE}/teams/${teamId}`, {
                method: 'PATCH',
                headers: headers(),
                body: JSON.stringify(updates),
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to update team');
            }

            const team = await response.json();
            updateTeamInStore(teamId, team);
            return team;
        } catch (err) {
            const message = err instanceof Error ? err.message : 'Unknown error';
            setError(message);
            throw err;
        } finally {
            setLoading(false);
        }
    }, [headers, updateTeamInStore, setLoading, setError]);

    // Delete team
    const deleteTeam = useCallback(async (teamId: string): Promise<void> => {
        setLoading(true);
        setError(null);

        try {
            const response = await fetch(`${API_BASE}/teams/${teamId}`, {
                method: 'DELETE',
                headers: headers(),
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to delete team');
            }

            removeTeam(teamId);
        } catch (err) {
            const message = err instanceof Error ? err.message : 'Unknown error';
            setError(message);
            throw err;
        } finally {
            setLoading(false);
        }
    }, [headers, removeTeam, setLoading, setError]);

    // Select team
    const selectTeam = useCallback((team: Team) => {
        setCurrentTeam(team);
    }, [setCurrentTeam]);

    // Fetch members
    const fetchMembers = useCallback(async (teamId: string): Promise<void> => {
        setLoading(true);
        setError(null);

        try {
            const response = await fetch(`${API_BASE}/teams/${teamId}/members`, {
                headers: headers(),
            });

            if (!response.ok) {
                throw new Error('Failed to fetch members');
            }

            const data = await response.json();
            setMembers(data);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Unknown error');
        } finally {
            setLoading(false);
        }
    }, [headers, setMembers, setLoading, setError]);

    // Invite member
    const inviteMember = useCallback(async (
        teamId: string,
        data: { github_username?: string; email?: string; role?: string }
    ): Promise<TeamMember> => {
        setLoading(true);
        setError(null);

        try {
            const response = await fetch(`${API_BASE}/teams/${teamId}/members`, {
                method: 'POST',
                headers: headers(),
                body: JSON.stringify(data),
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to invite member');
            }

            const member = await response.json();
            addMember(member);
            return member;
        } catch (err) {
            const message = err instanceof Error ? err.message : 'Unknown error';
            setError(message);
            throw err;
        } finally {
            setLoading(false);
        }
    }, [headers, addMember, setLoading, setError]);

    // Update member role
    const updateMemberRole = useCallback(async (
        teamId: string,
        memberId: string,
        role: string
    ): Promise<TeamMember> => {
        setLoading(true);
        setError(null);

        try {
            const response = await fetch(`${API_BASE}/teams/${teamId}/members/${memberId}`, {
                method: 'PATCH',
                headers: headers(),
                body: JSON.stringify({role}),
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to update member role');
            }

            const member = await response.json();
            updateMember(memberId, member);
            return member;
        } catch (err) {
            const message = err instanceof Error ? err.message : 'Unknown error';
            setError(message);
            throw err;
        } finally {
            setLoading(false);
        }
    }, [headers, updateMember, setLoading, setError]);

    // Remove member
    const removeMember = useCallback(async (teamId: string, memberId: string): Promise<void> => {
        setLoading(true);
        setError(null);

        try {
            const response = await fetch(`${API_BASE}/teams/${teamId}/members/${memberId}`, {
                method: 'DELETE',
                headers: headers(),
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to remove member');
            }

            removeMemberFromStore(memberId);
        } catch (err) {
            const message = err instanceof Error ? err.message : 'Unknown error';
            setError(message);
            throw err;
        } finally {
            setLoading(false);
        }
    }, [headers, removeMemberFromStore, setLoading, setError]);

    // Sync collaborators from GitHub
    const syncCollaborators = useCallback(async (teamId: string, projectId: string): Promise<any> => {
        setLoading(true);
        setError(null);

        try {
            const response = await fetch(
                `${API_BASE}/teams/${teamId}/sync-collaborators?project_id=${projectId}`,
                {
                    method: 'POST',
                    headers: headers(),
                }
            );

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to sync collaborators');
            }

            const result = await response.json();

            // Refresh members after sync
            await fetchMembers(teamId);

            return result;
        } catch (err) {
            const message = err instanceof Error ? err.message : 'Unknown error';
            setError(message);
            throw err;
        } finally {
            setLoading(false);
        }
    }, [headers, fetchMembers, setLoading, setError]);

    return {
        teams,
        currentTeam,
        members,
        loading,
        error,
        fetchTeams,
        createTeam,
        updateTeam,
        deleteTeam,
        selectTeam,
        fetchMembers,
        inviteMember,
        updateMemberRole,
        removeMember,
        syncCollaborators,
    };
}
