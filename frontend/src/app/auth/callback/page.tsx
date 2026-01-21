'use client';

import {Suspense, useEffect, useState} from 'react';
import {useRouter, useSearchParams} from 'next/navigation';
import {useAuthStore} from '@/lib/store';
import api from '@/lib/api';
import Link from "next/link";

function CallbackContent() {
    const router = useRouter();
    const searchParams = useSearchParams();
    const {setAuth} = useAuthStore();
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const handleCallback = async () => {
            const code = searchParams.get('code');

            if (!code) {
                setError('No authorization code received from GitHub');
                return;
            }

            try {
                // Exchange code for token via backend
                const response = await api.post('/auth/github/callback', {code});
                const {access_token, user} = response.data;

                // Store token
                localStorage.setItem('auth_token', access_token);

                // Update store
                setAuth(access_token, user);

                // Redirect to dashboard
                router.push('/dashboard');
            } catch (err: any) {
                console.error('OAuth callback error:', err);
                const message = err.response?.data?.detail || 'Failed to authenticate with GitHub';
                setError(message);
            }
        };

        handleCallback();
    }, [searchParams, setAuth, router]);

    if (error) {
        return (
            <div className="flex min-h-[60vh] flex-col items-center justify-center">
                <div className="rounded-lg border border-red-500/50 bg-red-500/10 p-6 text-center">
                    <h1 className="text-xl font-semibold text-red-500">Authentication Failed</h1>
                    <p className="mt-2 text-gray-400">{error}</p>
                    <Link
                        href="/"
                        className="mt-4 inline-block text-sm text-blue-500 hover:underline"
                    >
                        Return to Home
                    </Link>
                </div>
            </div>
        );
    }

    return (
        <div className="flex min-h-[60vh] flex-col items-center justify-center">
            <div className="text-center">
                <div
                    className="mx-auto h-8 w-8 animate-spin rounded-full border-4 border-blue-500 border-t-transparent"/>
                <p className="mt-4 text-gray-400">Authenticating with GitHub...</p>
            </div>
        </div>
    );
}

export default function AuthCallback() {
    return (
        <Suspense fallback={
            <div className="flex min-h-[60vh] flex-col items-center justify-center">
                <div
                    className="mx-auto h-8 w-8 animate-spin rounded-full border-4 border-blue-500 border-t-transparent"/>
            </div>
        }>
            <CallbackContent/>
        </Suspense>
    );
}
