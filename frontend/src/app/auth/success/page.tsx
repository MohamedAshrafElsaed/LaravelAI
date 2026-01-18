'use client';

import {Suspense, useEffect, useState} from 'react';
import {useRouter, useSearchParams} from 'next/navigation';
import {useAuthStore} from '@/lib/store';
import {authApi} from '@/lib/api';

function AuthSuccessContent() {
    const router = useRouter();
    const searchParams = useSearchParams();
    const {setAuth} = useAuthStore();
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const handleAuth = async () => {
            const token = searchParams.get('token');

            if (!token) {
                setError('No authentication token received');
                return;
            }

            try {
                // Store token first
                localStorage.setItem('auth_token', token);

                // Fetch user info
                const response = await authApi.getMe();
                const user = response.data;

                // Update store
                setAuth(token, user);

                // Redirect to dashboard
                router.push('/dashboard');
            } catch (err) {
                console.error('Auth error:', err);
                setError('Failed to authenticate. Please try again.');
                localStorage.removeItem('auth_token');
            }
        };

        handleAuth();
    }, [searchParams, setAuth, router]);

    if (error) {
        return (
            <div className="flex min-h-[60vh] flex-col items-center justify-center">
                <div className="rounded-lg border border-red-500/50 bg-red-500/10 p-6 text-center">
                    <h1 className="text-xl font-semibold text-red-500">Authentication Failed</h1>
                    <p className="mt-2 text-gray-400">{error}</p>
                    <a
                        href="/"
                        className="mt-4 inline-block text-sm text-blue-500 hover:underline"
                    >
                        Return to Home
                    </a>
                </div>
            </div>
        );
    }

    return (
        <div className="flex min-h-[60vh] flex-col items-center justify-center">
            <div className="text-center">
                <div
                    className="mx-auto h-8 w-8 animate-spin rounded-full border-4 border-blue-500 border-t-transparent"/>
                <p className="mt-4 text-gray-400">Completing authentication...</p>
            </div>
        </div>
    );
}

export default function AuthSuccess() {
    return (
        <Suspense fallback={
            <div className="flex min-h-[60vh] flex-col items-center justify-center">
                <div
                    className="mx-auto h-8 w-8 animate-spin rounded-full border-4 border-blue-500 border-t-transparent"/>
            </div>
        }>
            <AuthSuccessContent/>
        </Suspense>
    );
}