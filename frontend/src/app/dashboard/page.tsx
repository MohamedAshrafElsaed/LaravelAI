'use client';

import { useState, useMemo } from 'react';
import Sidebar from '@/components/dashboard/Sidebar';
import WelcomeScreen from '@/components/dashboard/WelcomeScreen';
import SessionView from '@/components/dashboard/SessionView';

export interface Repo {
  name: string;
  owner: string;
  selected: boolean;
}

export interface Branch {
  name: string;
  selected: boolean;
}

export interface Session {
  id: string;
  title: string;
  project: string;
  time: string;
  active: boolean;
  metrics: { additions: number; deletions: number } | null;
}

export interface Workspace {
  name: string;
  plan: string;
  selected: boolean;
}

export interface User {
  email: string;
  name: string;
  workspaces: Workspace[];
}

export default function DashboardPage() {
  const appName = 'Maestro AI';
  const [currentView, setCurrentView] = useState<'welcome' | 'session'>('welcome');
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const [repos, setRepos] = useState<Repo[]>([
    { name: 'ab', owner: 'MohamedAshrafElsaed', selected: true },
    { name: 'AIBuilder', owner: 'MohamedAshrafElsaed', selected: false },
    { name: 'ConvertedOrders', owner: 'convertedin', selected: false },
  ]);

  const [branches, setBranches] = useState<Branch[]>([
    { name: 'main', selected: true },
    { name: 'develop', selected: false },
  ]);

  const [sessions, setSessions] = useState<Session[]>([
    { id: '1', title: 'Update app color scheme to match design', project: 'ab', time: 'Wed', active: false, metrics: null },
    { id: '2', title: 'Update Welcome page and app colors', project: 'ab', time: 'Wed', active: false, metrics: null },
    { id: '3', title: 'Fix critical production bugs', project: 'ConvertedOrders', time: 'Wed', active: false, metrics: { additions: 0, deletions: 27 } },
  ]);

  const [user] = useState<User>({
    email: 'm.ashraf@converted.in',
    name: 'Mohamed Ashraf',
    workspaces: [
      { name: 'Convertedin', plan: 'Team plan', selected: true },
      { name: 'Personal', plan: 'Free plan', selected: false },
    ],
  });

  const selectedRepo = useMemo(() => repos.find((r) => r.selected), [repos]);

  const selectSession = (id: string) => {
    setSessions((prev) => prev.map((s) => ({ ...s, active: s.id === id })));
    setCurrentView('session');
  };

  const selectRepo = (name: string) => {
    setRepos((prev) => prev.map((r) => ({ ...r, selected: r.name === name })));
  };

  const selectBranch = (name: string) => {
    setBranches((prev) => prev.map((b) => ({ ...b, selected: b.name === name })));
  };

  const handleSuggestionClick = (suggestion: string) => {
    console.log('Suggestion clicked:', suggestion);
    setCurrentView('session');
  };

  return (
    <div className="flex h-screen w-full overflow-hidden bg-[#141414]">
      {/* Mobile backdrop */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/60 lg:hidden transition-opacity"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <Sidebar
        appName={appName}
        repos={repos}
        branches={branches}
        sessions={sessions}
        user={user}
        mobileOpen={sidebarOpen}
        onCloseMobile={() => setSidebarOpen(false)}
        onSelectSession={selectSession}
        onSelectRepo={selectRepo}
        onSelectBranch={selectBranch}
      />

      {/* Main content */}
      <main className="relative flex flex-1 flex-col overflow-hidden">
        {/* Mobile header */}
        <header className="flex h-12 items-center gap-3 border-b border-[#2b2b2b] bg-[#1b1b1b] px-4 lg:hidden">
          <button
            className="flex h-8 w-8 items-center justify-center rounded-md text-[#a1a1aa] transition-colors hover:bg-white/5"
            onClick={() => setSidebarOpen(true)}
          >
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
          <span className="text-sm font-medium text-[#f3f4f6]">{appName}</span>
        </header>

        {/* Content area */}
        <div className="flex-1 overflow-y-auto">
          {currentView === 'welcome' ? (
            <WelcomeScreen selectedRepo={selectedRepo} onSuggestionClick={handleSuggestionClick} />
          ) : (
            <SessionView />
          )}
        </div>
      </main>
    </div>
  );
}