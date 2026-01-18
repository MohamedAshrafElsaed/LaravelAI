'use client';

import React, {Component, ErrorInfo, ReactNode} from 'react';
import {AlertTriangle, Home, RefreshCw} from 'lucide-react';

interface Props {
    children: ReactNode;
    fallback?: ReactNode;
    onError?: (error: Error, errorInfo: ErrorInfo) => void;
}

interface State {
    hasError: boolean;
    error: Error | null;
    errorInfo: ErrorInfo | null;
}

export class ErrorBoundary extends Component<Props, State> {
    constructor(props: Props) {
        super(props);
        this.state = {
            hasError: false,
            error: null,
            errorInfo: null,
        };
    }

    static getDerivedStateFromError(error: Error): Partial<State> {
        return {hasError: true, error};
    }

    componentDidCatch(error: Error, errorInfo: ErrorInfo) {
        this.setState({errorInfo});

        // Log to console in development
        console.error('ErrorBoundary caught an error:', error, errorInfo);

        // Call optional error handler
        this.props.onError?.(error, errorInfo);

        // In production, you could log to an error reporting service here
        // e.g., Sentry, LogRocket, etc.
    }

    handleRetry = () => {
        this.setState({hasError: false, error: null, errorInfo: null});
    };

    handleGoHome = () => {
        window.location.href = '/dashboard';
    };

    render() {
        if (this.state.hasError) {
            // Custom fallback UI
            if (this.props.fallback) {
                return this.props.fallback;
            }

            return (
                <div className="flex min-h-[400px] items-center justify-center p-8">
                    <div className="max-w-md rounded-lg border border-red-500/30 bg-red-500/10 p-8 text-center">
                        <div
                            className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-red-500/20">
                            <AlertTriangle className="h-8 w-8 text-red-400"/>
                        </div>

                        <h2 className="mb-2 text-xl font-semibold text-white">
                            Something went wrong
                        </h2>

                        <p className="mb-6 text-sm text-gray-400">
                            An unexpected error occurred. Please try again or return to the dashboard.
                        </p>

                        {/* Error details in development */}
                        {process.env.NODE_ENV === 'development' && this.state.error && (
                            <div className="mb-6 rounded-lg bg-gray-900 p-4 text-left">
                                <p className="mb-2 text-xs font-medium text-red-400">
                                    {this.state.error.name}: {this.state.error.message}
                                </p>
                                {this.state.errorInfo?.componentStack && (
                                    <pre className="max-h-40 overflow-auto text-xs text-gray-500">
                    {this.state.errorInfo.componentStack}
                  </pre>
                                )}
                            </div>
                        )}

                        <div className="flex justify-center gap-3">
                            <button
                                onClick={this.handleRetry}
                                className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-500"
                            >
                                <RefreshCw className="h-4 w-4"/>
                                Try Again
                            </button>
                            <button
                                onClick={this.handleGoHome}
                                className="inline-flex items-center gap-2 rounded-lg border border-gray-700 bg-gray-800 px-4 py-2 text-sm font-medium text-gray-300 transition-colors hover:bg-gray-700"
                            >
                                <Home className="h-4 w-4"/>
                                Dashboard
                            </button>
                        </div>
                    </div>
                </div>
            );
        }

        return this.props.children;
    }
}

// Hook for functional components to throw errors to boundary
export function useErrorHandler() {
    const [error, setError] = React.useState<Error | null>(null);

    React.useEffect(() => {
        if (error) {
            throw error;
        }
    }, [error]);

    return setError;
}

// HOC for wrapping components with error boundary
export function withErrorBoundary<P extends object>(
    WrappedComponent: React.ComponentType<P>,
    fallback?: ReactNode
) {
    return function WithErrorBoundaryWrapper(props: P) {
        return (
            <ErrorBoundary fallback={fallback}>
                <WrappedComponent {...props} />
            </ErrorBoundary>
        );
    };
}
