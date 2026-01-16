'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useAuthStore } from '@/lib/store';

export default function Home() {
  const { isAuthenticated, user } = useAuthStore();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

  return (
    <div className="flex flex-col items-center justify-center px-4 py-16">
      {/* Hero Section */}
      <div className="mx-auto max-w-3xl text-center">
        <h1 className="bg-gradient-to-r from-blue-400 via-purple-500 to-pink-500 bg-clip-text text-5xl font-extrabold tracking-tight text-transparent sm:text-6xl">
          Laravel AI
        </h1>
        <p className="mt-6 text-xl text-gray-400">
          Modify your Laravel codebase using natural language.
          Connect your GitHub repo, describe what you want, and let AI do the work.
        </p>

        {/* CTA Buttons */}
        <div className="mt-10 flex flex-col items-center justify-center gap-4 sm:flex-row">
          {mounted && isAuthenticated ? (
            <>
              <span className="text-sm text-gray-400">
                Welcome back, {user?.username}!
              </span>
              <Link
                href="/dashboard"
                className="inline-flex h-11 items-center justify-center rounded-md bg-blue-600 px-8 text-sm font-medium text-white transition-colors hover:bg-blue-700"
              >
                Go to Dashboard
              </Link>
            </>
          ) : (
            <>
              <a
                href={`${apiUrl}/auth/github`}
                className="inline-flex h-11 items-center justify-center gap-2 rounded-md bg-white px-8 text-sm font-medium text-gray-900 transition-colors hover:bg-gray-100"
              >
                <svg className="h-5 w-5" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z" />
                </svg>
                Connect with GitHub
              </a>
              <Link
                href="/demo"
                className="inline-flex h-11 items-center justify-center rounded-md border border-gray-700 bg-transparent px-8 text-sm font-medium text-gray-300 transition-colors hover:bg-gray-800"
              >
                View Demo
              </Link>
            </>
          )}
        </div>
      </div>

      {/* Features Section */}
      <div className="mx-auto mt-24 max-w-5xl px-4">
        <h2 className="text-center text-3xl font-bold text-white">How It Works</h2>
        <div className="mt-12 grid gap-8 sm:grid-cols-3">
          {/* Feature 1 */}
          <div className="rounded-lg border border-gray-800 p-6 bg-gray-900">
            <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-blue-500/10 text-blue-500">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
              </svg>
            </div>
            <h3 className="mt-4 text-lg font-semibold text-white">1. Connect Repository</h3>
            <p className="mt-2 text-sm text-gray-400">
              Link your Laravel GitHub repository. We&apos;ll index your codebase to understand its structure.
            </p>
          </div>

          {/* Feature 2 */}
          <div className="rounded-lg border border-gray-800 p-6 bg-gray-900">
            <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-blue-500/10 text-blue-500">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
              </svg>
            </div>
            <h3 className="mt-4 text-lg font-semibold text-white">2. Describe Changes</h3>
            <p className="mt-2 text-sm text-gray-400">
              Tell the AI what you want to change in plain English. &quot;Add soft deletes to User model&quot;
            </p>
          </div>

          {/* Feature 3 */}
          <div className="rounded-lg border border-gray-800 p-6 bg-gray-900">
            <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-blue-500/10 text-blue-500">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <h3 className="mt-4 text-lg font-semibold text-white">3. Review & Apply</h3>
            <p className="mt-2 text-sm text-gray-400">
              Review the proposed changes with a visual diff. Apply them directly or create a pull request.
            </p>
          </div>
        </div>
      </div>

      {/* Example Section */}
      <div className="mx-auto mt-24 max-w-3xl px-4">
        <h2 className="text-center text-3xl font-bold text-white">Example Prompts</h2>
        <div className="mt-8 space-y-4">
          {[
            'Add a new API endpoint for user profile updates',
            'Create a migration to add "status" column to orders table',
            'Add validation to the StoreProductRequest',
            'Implement soft deletes on the Comment model',
            'Create a service class for payment processing',
          ].map((prompt, i) => (
            <div
              key={i}
              className="rounded-lg border border-gray-800 bg-gray-900 p-4 text-sm text-gray-400"
            >
              <span className="text-blue-500">&gt;</span> {prompt}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}