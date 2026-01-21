import {create} from 'zustand';
import {persist} from 'zustand/middleware';

export interface TeamMember {
    id: string;
    team_id: string;
    user_id: string | null;
    github_id: number | null;
    github_username: string | null;
    github_avatar_url: string | null;
    invited_email: string | null;
    role: 'owner' | 'admin' | 'member' | 'viewer';
    status: 'pending' | 'active' | 'inactive' | 'declined';
    joined_at: string | null;
    invited_at: string;
    last_active_at: string | null;
}

export interface Team {
    id: string;
    name: string;
    slug: string;
    description: string | null;
    avatar_url: string | null;
    owner_id: string;
    is_personal: boolean;
    github_org_name: string | null;
    member_count: number;
    project_count: number;
    created_at: string;
    updated_at: string;
}

interface TeamState {
    teams: Team[];
    currentTeam: Team | null;
    members: TeamMember[];
    loading: boolean;
    error: string | null;

    // Actions
    setTeams: (teams: Team[]) => void;
    setCurrentTeam: (team: Team | null) => void;
    setMembers: (members: TeamMember[]) => void;
    addTeam: (team: Team) => void;
    updateTeam: (id: string, updates: Partial<Team>) => void;
    removeTeam: (id: string) => void;
    addMember: (member: TeamMember) => void;
    updateMember: (id: string, updates: Partial<TeamMember>) => void;
    removeMember: (id: string) => void;
    setLoading: (loading: boolean) => void;
    setError: (error: string | null) => void;
    reset: () => void;
}

const initialState = {
    teams: [],
    currentTeam: null,
    members: [],
    loading: false,
    error: null,
};

export const useTeamStore = create<TeamState>()(
    persist(
        (set) => ({
            ...initialState,

            setTeams: (teams) => set({teams}),

            setCurrentTeam: (team) => set({currentTeam: team}),

            setMembers: (members) => set({members}),

            addTeam: (team) => set((state) => ({
                teams: [...state.teams, team],
            })),

            updateTeam: (id, updates) => set((state) => ({
                teams: state.teams.map((t) =>
                    t.id === id ? {...t, ...updates} : t
                ),
                currentTeam: state.currentTeam?.id === id
                    ? {...state.currentTeam, ...updates}
                    : state.currentTeam,
            })),

            removeTeam: (id) => set((state) => ({
                teams: state.teams.filter((t) => t.id !== id),
                currentTeam: state.currentTeam?.id === id ? null : state.currentTeam,
            })),

            addMember: (member) => set((state) => ({
                members: [...state.members, member],
            })),

            updateMember: (id, updates) => set((state) => ({
                members: state.members.map((m) =>
                    m.id === id ? {...m, ...updates} : m
                ),
            })),

            removeMember: (id) => set((state) => ({
                members: state.members.filter((m) => m.id !== id),
            })),

            setLoading: (loading) => set({loading}),

            setError: (error) => set({error}),

            reset: () => set(initialState),
        }),
        {
            name: 'team-storage',
            partialize: (state) => ({
                currentTeam: state.currentTeam,
            }),
        }
    )
);