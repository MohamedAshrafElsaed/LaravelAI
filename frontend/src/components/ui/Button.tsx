'use client';

import React from 'react';
import {Loader2} from 'lucide-react';
import {cn} from '@/lib/utils';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
    variant?: 'primary' | 'secondary' | 'danger' | 'ghost' | 'outline';
    size?: 'sm' | 'md' | 'lg';
    loading?: boolean;
    loadingText?: string;
    leftIcon?: React.ReactNode;
    rightIcon?: React.ReactNode;
}

const variantStyles = {
    primary: 'bg-gradient-to-r from-[#E07850] to-[#C65D3D] text-white hover:shadow-lg hover:shadow-[#E07850]/30 hover:-translate-y-0.5 disabled:opacity-50',
    secondary: 'bg-[#292524] text-[#FAFAF9] border border-[#44403C] hover:bg-[#44403C] hover:border-[#57534E] disabled:opacity-50',
    danger: 'bg-[#EF4444] text-white hover:bg-[#DC2626] disabled:opacity-50',
    ghost: 'bg-transparent text-[#A8A29E] hover:bg-[#44403C] hover:text-[#FAFAF9]',
    outline: 'border-2 border-[#44403C] bg-transparent text-[#FAFAF9] hover:bg-[#292524] hover:border-[#57534E]',
};

const sizeStyles = {
    sm: 'h-8 px-3 text-xs gap-1.5 rounded-lg',
    md: 'h-10 px-4 text-sm gap-2 rounded-xl',
    lg: 'h-12 px-6 text-base gap-2.5 rounded-2xl',
};

export function Button({
                           children,
                           className,
                           variant = 'primary',
                           size = 'md',
                           loading = false,
                           loadingText,
                           leftIcon,
                           rightIcon,
                           disabled,
                           ...props
                       }: ButtonProps) {
    const isDisabled = disabled || loading;

    return (
        <button
            className={cn(
                'inline-flex items-center justify-center font-semibold transition-all duration-300',
                'focus:outline-none focus:ring-2 focus:ring-[#E07850] focus:ring-offset-2 focus:ring-offset-[#1C1917]',
                'disabled:cursor-not-allowed disabled:transform-none',
                variantStyles[variant],
                sizeStyles[size],
                className
            )}
            disabled={isDisabled}
            {...props}
        >
            {loading ? (
                <>
                    <Loader2 className={cn(
                        'animate-spin',
                        size === 'sm' ? 'h-3 w-3' : size === 'lg' ? 'h-5 w-5' : 'h-4 w-4'
                    )}/>
                    {loadingText && <span>{loadingText}</span>}
                </>
            ) : (
                <>
                    {leftIcon}
                    {children}
                    {rightIcon}
                </>
            )}
        </button>
    );
}

// Card component for consistency
export function Card({
                         children,
                         className,
                         hover = false,
                         ...props
                     }: React.HTMLAttributes<HTMLDivElement> & { hover?: boolean }) {
    return (
        <div
            className={cn(
                'bg-[#292524] border border-[#44403C] rounded-2xl',
                hover && 'transition-all duration-300 hover:border-[#57534E] hover:shadow-xl hover:shadow-[#E07850]/5',
                className
            )}
            {...props}
        >
            {children}
        </div>
    );
}

// Input component
export function Input({
                          className,
                          ...props
                      }: React.InputHTMLAttributes<HTMLInputElement>) {
    return (
        <input
            className={cn(
                'w-full bg-[#1C1917] border border-[#44403C] text-[#FAFAF9] rounded-lg px-4 py-2.5',
                'placeholder:text-[#78716C]',
                'focus:outline-none focus:border-[#E07850] focus:ring-2 focus:ring-[#E07850]/30',
                'transition-all duration-200',
                className
            )}
            {...props}
        />
    );
}

// Badge component
export function Badge({
                          children,
                          variant = 'default',
                          className,
                      }: {
    children: React.ReactNode;
    variant?: 'default' | 'success' | 'warning' | 'danger' | 'info';
    className?: string;
}) {
    const variants = {
        default: 'bg-[#E07850]/10 text-[#E07850]',
        success: 'bg-[#22C55E]/10 text-[#22C55E]',
        warning: 'bg-[#F59E0B]/10 text-[#F59E0B]',
        danger: 'bg-[#EF4444]/10 text-[#EF4444]',
        info: 'bg-[#3B82F6]/10 text-[#3B82F6]',
    };

    return (
        <span
            className={cn(
                'inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold',
                variants[variant],
                className
            )}
        >
      {children}
    </span>
    );
}