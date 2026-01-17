'use client';

import React from 'react';
import { Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost' | 'outline';
  size?: 'sm' | 'md' | 'lg';
  loading?: boolean;
  loadingText?: string;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

const variantStyles = {
  primary: 'bg-blue-600 text-white hover:bg-blue-500 disabled:bg-blue-600/50',
  secondary: 'bg-gray-700 text-white hover:bg-gray-600 disabled:bg-gray-700/50',
  danger: 'bg-red-600 text-white hover:bg-red-500 disabled:bg-red-600/50',
  ghost: 'bg-transparent text-gray-300 hover:bg-gray-800 hover:text-white',
  outline: 'border border-gray-700 bg-transparent text-gray-300 hover:bg-gray-800 hover:text-white',
};

const sizeStyles = {
  sm: 'h-8 px-3 text-xs gap-1.5',
  md: 'h-10 px-4 text-sm gap-2',
  lg: 'h-12 px-6 text-base gap-2.5',
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
        'inline-flex items-center justify-center rounded-lg font-medium transition-colors',
        'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 focus:ring-offset-gray-900',
        'disabled:cursor-not-allowed disabled:opacity-50',
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
          )} />
          {loadingText && <span>{loadingText}</span>}
          {!loadingText && children}
        </>
      ) : (
        <>
          {leftIcon && <span className="shrink-0">{leftIcon}</span>}
          {children}
          {rightIcon && <span className="shrink-0">{rightIcon}</span>}
        </>
      )}
    </button>
  );
}

// Icon-only button variant
export interface IconButtonProps extends Omit<ButtonProps, 'leftIcon' | 'rightIcon' | 'loadingText'> {
  icon: React.ReactNode;
  'aria-label': string;
}

export function IconButton({
  icon,
  className,
  variant = 'ghost',
  size = 'md',
  loading = false,
  ...props
}: IconButtonProps) {
  const iconSizeStyles = {
    sm: 'h-8 w-8',
    md: 'h-10 w-10',
    lg: 'h-12 w-12',
  };

  return (
    <button
      className={cn(
        'inline-flex items-center justify-center rounded-lg transition-colors',
        'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 focus:ring-offset-gray-900',
        'disabled:cursor-not-allowed disabled:opacity-50',
        variantStyles[variant],
        iconSizeStyles[size],
        className
      )}
      {...props}
    >
      {loading ? (
        <Loader2 className={cn(
          'animate-spin',
          size === 'sm' ? 'h-4 w-4' : size === 'lg' ? 'h-6 w-6' : 'h-5 w-5'
        )} />
      ) : (
        icon
      )}
    </button>
  );
}

// Button group for related actions
interface ButtonGroupProps {
  children: React.ReactNode;
  className?: string;
}

export function ButtonGroup({ children, className }: ButtonGroupProps) {
  return (
    <div className={cn('inline-flex rounded-lg shadow-sm', className)}>
      {React.Children.map(children, (child, index) => {
        if (React.isValidElement(child)) {
          return React.cloneElement(child as React.ReactElement<ButtonProps>, {
            className: cn(
              (child as React.ReactElement<ButtonProps>).props.className,
              index === 0 && 'rounded-r-none',
              index === React.Children.count(children) - 1 && 'rounded-l-none',
              index > 0 && index < React.Children.count(children) - 1 && 'rounded-none',
              index > 0 && '-ml-px'
            ),
          });
        }
        return child;
      })}
    </div>
  );
}
