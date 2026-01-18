'use client';

import React from 'react';
import {cn} from '@/lib/utils';

interface ProgressBarProps {
    value: number; // 0-100
    max?: number;
    size?: 'sm' | 'md' | 'lg';
    variant?: 'default' | 'success' | 'warning' | 'error';
    showLabel?: boolean;
    label?: string;
    animated?: boolean;
    striped?: boolean;
    className?: string;
}

const sizeStyles = {
    sm: 'h-1',
    md: 'h-2',
    lg: 'h-3',
};

const variantStyles = {
    default: 'bg-blue-500',
    success: 'bg-green-500',
    warning: 'bg-yellow-500',
    error: 'bg-red-500',
};

export function ProgressBar({
                                value,
                                max = 100,
                                size = 'md',
                                variant = 'default',
                                showLabel = false,
                                label,
                                animated = false,
                                striped = false,
                                className,
                            }: ProgressBarProps) {
    const percentage = Math.min(Math.max((value / max) * 100, 0), 100);

    return (
        <div className={cn('w-full', className)}>
            {(showLabel || label) && (
                <div className="mb-1 flex items-center justify-between text-sm">
                    <span className="text-gray-400">{label}</span>
                    {showLabel && (
                        <span className="text-gray-300 font-medium">{Math.round(percentage)}%</span>
                    )}
                </div>
            )}
            <div
                className={cn(
                    'w-full overflow-hidden rounded-full bg-gray-800',
                    sizeStyles[size]
                )}
                role="progressbar"
                aria-valuenow={value}
                aria-valuemin={0}
                aria-valuemax={max}
            >
                <div
                    className={cn(
                        'h-full rounded-full transition-all duration-300 ease-out',
                        variantStyles[variant],
                        striped && 'bg-stripes',
                        animated && 'animate-progress'
                    )}
                    style={{width: `${percentage}%`}}
                />
            </div>
        </div>
    );
}

// Indeterminate progress bar for unknown duration tasks
interface IndeterminateProgressProps {
    size?: 'sm' | 'md' | 'lg';
    variant?: 'default' | 'success' | 'warning' | 'error';
    label?: string;
    className?: string;
}

export function IndeterminateProgress({
                                          size = 'md',
                                          variant = 'default',
                                          label,
                                          className,
                                      }: IndeterminateProgressProps) {
    return (
        <div className={cn('w-full', className)}>
            {label && (
                <div className="mb-1 text-sm text-gray-400">{label}</div>
            )}
            <div
                className={cn(
                    'w-full overflow-hidden rounded-full bg-gray-800',
                    sizeStyles[size]
                )}
                role="progressbar"
                aria-busy="true"
            >
                <div
                    className={cn(
                        'h-full w-1/3 rounded-full animate-indeterminate',
                        variantStyles[variant]
                    )}
                />
            </div>
        </div>
    );
}

// Circular progress for specific use cases
interface CircularProgressProps {
    value: number;
    max?: number;
    size?: number;
    strokeWidth?: number;
    variant?: 'default' | 'success' | 'warning' | 'error';
    showLabel?: boolean;
    className?: string;
}

const circularVariantStyles = {
    default: 'text-blue-500',
    success: 'text-green-500',
    warning: 'text-yellow-500',
    error: 'text-red-500',
};

export function CircularProgress({
                                     value,
                                     max = 100,
                                     size = 48,
                                     strokeWidth = 4,
                                     variant = 'default',
                                     showLabel = false,
                                     className,
                                 }: CircularProgressProps) {
    const percentage = Math.min(Math.max((value / max) * 100, 0), 100);
    const radius = (size - strokeWidth) / 2;
    const circumference = radius * 2 * Math.PI;
    const offset = circumference - (percentage / 100) * circumference;

    return (
        <div
            className={cn('relative inline-flex', className)}
            style={{width: size, height: size}}
        >
            <svg className="transform -rotate-90" width={size} height={size}>
                {/* Background circle */}
                <circle
                    className="text-gray-800"
                    strokeWidth={strokeWidth}
                    stroke="currentColor"
                    fill="transparent"
                    r={radius}
                    cx={size / 2}
                    cy={size / 2}
                />
                {/* Progress circle */}
                <circle
                    className={cn('transition-all duration-300 ease-out', circularVariantStyles[variant])}
                    strokeWidth={strokeWidth}
                    strokeLinecap="round"
                    stroke="currentColor"
                    fill="transparent"
                    r={radius}
                    cx={size / 2}
                    cy={size / 2}
                    style={{
                        strokeDasharray: circumference,
                        strokeDashoffset: offset,
                    }}
                />
            </svg>
            {showLabel && (
                <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-xs font-medium text-gray-300">
            {Math.round(percentage)}%
          </span>
                </div>
            )}
        </div>
    );
}

// Spinner component for loading states
interface SpinnerProps {
    size?: 'sm' | 'md' | 'lg' | 'xl';
    className?: string;
}

const spinnerSizes = {
    sm: 'h-4 w-4',
    md: 'h-6 w-6',
    lg: 'h-8 w-8',
    xl: 'h-12 w-12',
};

export function Spinner({size = 'md', className}: SpinnerProps) {
    return (
        <svg
            className={cn('animate-spin', spinnerSizes[size], className)}
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
        >
            <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
            />
            <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
            />
        </svg>
    );
}
