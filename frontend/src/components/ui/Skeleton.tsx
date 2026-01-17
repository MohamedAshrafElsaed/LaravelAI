'use client';

import React from 'react';
import { cn } from '@/lib/utils';

// Base Skeleton component
interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> {
  className?: string;
}

export function Skeleton({ className, ...props }: SkeletonProps) {
  return (
    <div
      className={cn(
        'animate-pulse rounded-md bg-gray-800',
        className
      )}
      {...props}
    />
  );
}

// Skeleton for text lines
interface SkeletonTextProps {
  lines?: number;
  className?: string;
  lastLineWidth?: 'full' | 'half' | 'third' | 'quarter';
}

export function SkeletonText({
  lines = 3,
  className,
  lastLineWidth = 'half',
}: SkeletonTextProps) {
  const widthMap = {
    full: 'w-full',
    half: 'w-1/2',
    third: 'w-1/3',
    quarter: 'w-1/4',
  };

  return (
    <div className={cn('space-y-2', className)}>
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton
          key={i}
          className={cn(
            'h-4',
            i === lines - 1 ? widthMap[lastLineWidth] : 'w-full'
          )}
        />
      ))}
    </div>
  );
}

// Skeleton for cards
interface SkeletonCardProps {
  showImage?: boolean;
  showActions?: boolean;
  className?: string;
}

export function SkeletonCard({
  showImage = false,
  showActions = false,
  className,
}: SkeletonCardProps) {
  return (
    <div
      className={cn(
        'rounded-lg border border-gray-800 bg-gray-900 p-4',
        className
      )}
    >
      {showImage && (
        <Skeleton className="mb-4 h-40 w-full rounded-lg" />
      )}
      <div className="flex items-start gap-3">
        <Skeleton className="h-10 w-10 shrink-0 rounded-lg" />
        <div className="flex-1 space-y-2">
          <Skeleton className="h-4 w-3/4" />
          <Skeleton className="h-3 w-1/2" />
        </div>
      </div>
      <div className="mt-4">
        <SkeletonText lines={2} lastLineWidth="third" />
      </div>
      {showActions && (
        <div className="mt-4 flex gap-2">
          <Skeleton className="h-8 w-20" />
          <Skeleton className="h-8 w-20" />
        </div>
      )}
    </div>
  );
}

// Skeleton for list items
interface SkeletonListProps {
  count?: number;
  showAvatar?: boolean;
  className?: string;
}

export function SkeletonList({
  count = 5,
  showAvatar = true,
  className,
}: SkeletonListProps) {
  return (
    <div className={cn('space-y-3', className)}>
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="flex items-center gap-3 p-3 rounded-lg bg-gray-900">
          {showAvatar && (
            <Skeleton className="h-10 w-10 shrink-0 rounded-full" />
          )}
          <div className="flex-1 space-y-2">
            <Skeleton className="h-4 w-1/3" />
            <Skeleton className="h-3 w-2/3" />
          </div>
          <Skeleton className="h-6 w-16 rounded-full" />
        </div>
      ))}
    </div>
  );
}

// Skeleton for table
interface SkeletonTableProps {
  rows?: number;
  columns?: number;
  className?: string;
}

export function SkeletonTable({
  rows = 5,
  columns = 4,
  className,
}: SkeletonTableProps) {
  return (
    <div className={cn('rounded-lg border border-gray-800 overflow-hidden', className)}>
      {/* Header */}
      <div className="flex gap-4 bg-gray-900 p-4">
        {Array.from({ length: columns }).map((_, i) => (
          <Skeleton key={i} className="h-4 flex-1" />
        ))}
      </div>
      {/* Rows */}
      {Array.from({ length: rows }).map((_, rowIndex) => (
        <div
          key={rowIndex}
          className="flex gap-4 border-t border-gray-800 p-4"
        >
          {Array.from({ length: columns }).map((_, colIndex) => (
            <Skeleton
              key={colIndex}
              className={cn(
                'h-4 flex-1',
                colIndex === 0 && 'w-1/4 flex-none'
              )}
            />
          ))}
        </div>
      ))}
    </div>
  );
}

// Skeleton for project cards (specific to this app)
export function SkeletonProjectCard() {
  return (
    <div className="rounded-lg border border-gray-800 bg-gray-900 p-6">
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <Skeleton className="h-10 w-10 rounded-lg" />
          <div className="space-y-2">
            <Skeleton className="h-4 w-32" />
            <Skeleton className="h-3 w-24" />
          </div>
        </div>
        <Skeleton className="h-6 w-16 rounded-full" />
      </div>
      <div className="mt-4 flex items-center gap-4">
        <Skeleton className="h-3 w-16" />
        <Skeleton className="h-3 w-24" />
      </div>
    </div>
  );
}

// Skeleton for conversation history
export function SkeletonConversationList() {
  return (
    <div className="space-y-1 p-2">
      {Array.from({ length: 4 }).map((_, i) => (
        <div key={i} className="flex items-center gap-2 rounded-lg px-3 py-2">
          <Skeleton className="h-4 w-4 shrink-0" />
          <div className="flex-1 space-y-1.5">
            <Skeleton className="h-3.5 w-3/4" />
            <Skeleton className="h-2.5 w-1/2" />
          </div>
        </div>
      ))}
    </div>
  );
}

// Skeleton for chat messages
export function SkeletonChatMessages() {
  return (
    <div className="space-y-4 p-4">
      {/* User message */}
      <div className="flex items-start gap-3 flex-row-reverse">
        <Skeleton className="h-8 w-8 shrink-0 rounded-full" />
        <Skeleton className="h-16 w-64 rounded-lg" />
      </div>
      {/* Assistant message */}
      <div className="flex items-start gap-3">
        <Skeleton className="h-8 w-8 shrink-0 rounded-full" />
        <div className="space-y-2">
          <Skeleton className="h-24 w-80 rounded-lg" />
        </div>
      </div>
      {/* Another user message */}
      <div className="flex items-start gap-3 flex-row-reverse">
        <Skeleton className="h-8 w-8 shrink-0 rounded-full" />
        <Skeleton className="h-12 w-48 rounded-lg" />
      </div>
    </div>
  );
}
