'use client';

import React, { useEffect } from 'react';
import { ErrorBoundary } from '@/components/ErrorBoundary';
import { ToastProvider, useToast, setToastInstance } from '@/components/Toast';

// Initialize toast instance for global access
function ToastInitializer() {
  const toast = useToast();

  useEffect(() => {
    setToastInstance(toast);
  }, [toast]);

  return null;
}

// Error messages from third-party scripts/extensions to ignore
const IGNORED_ERROR_PATTERNS = [
  'No checkout popup config found',  // Browser shopping extensions
  'ResizeObserver loop',             // Benign resize observer warnings
];

// Check if an error should be ignored (from third-party extensions/scripts)
function shouldIgnoreError(error: Error | string): boolean {
  const message = typeof error === 'string' ? error : error.message;
  return IGNORED_ERROR_PATTERNS.some(pattern => message.includes(pattern));
}

// Error handler for logging
function handleGlobalError(error: Error) {
  // Ignore errors from third-party browser extensions
  if (shouldIgnoreError(error)) {
    return;
  }

  console.error('[Global Error]', error);

  // In production, you could send to error tracking service
  // e.g., Sentry.captureException(error);
}

// Component to set up global error handlers
function GlobalErrorHandlers() {
  useEffect(() => {
    // Handle unhandled promise rejections (async errors)
    const handleUnhandledRejection = (event: PromiseRejectionEvent) => {
      const error = event.reason;
      const message = error?.message || String(error);

      if (shouldIgnoreError(message)) {
        // Prevent the error from appearing in console
        event.preventDefault();
        return;
      }

      console.error('[Unhandled Promise Rejection]', error);
    };

    // Handle global errors
    const handleError = (event: ErrorEvent) => {
      if (shouldIgnoreError(event.message)) {
        event.preventDefault();
        return;
      }
    };

    window.addEventListener('unhandledrejection', handleUnhandledRejection);
    window.addEventListener('error', handleError);

    return () => {
      window.removeEventListener('unhandledrejection', handleUnhandledRejection);
      window.removeEventListener('error', handleError);
    };
  }, []);

  return null;
}

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ErrorBoundary onError={handleGlobalError}>
      <ToastProvider>
        <ToastInitializer />
        <GlobalErrorHandlers />
        {children}
      </ToastProvider>
    </ErrorBoundary>
  );
}
