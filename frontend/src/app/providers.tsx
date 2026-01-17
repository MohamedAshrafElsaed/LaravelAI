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

// Error handler for logging
function handleGlobalError(error: Error) {
  console.error('[Global Error]', error);

  // In production, you could send to error tracking service
  // e.g., Sentry.captureException(error);
}

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ErrorBoundary onError={handleGlobalError}>
      <ToastProvider>
        <ToastInitializer />
        {children}
      </ToastProvider>
    </ErrorBoundary>
  );
}
