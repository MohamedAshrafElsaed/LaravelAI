'use client';

import {useEffect} from 'react';
import {Moon, Sun} from 'lucide-react';
import {useThemeStore} from '@/lib/store';

interface ThemeToggleProps {
    variant?: 'icon' | 'button' | 'dropdown';
    className?: string;
}

export function ThemeToggle({variant = 'button', className = ''}: ThemeToggleProps) {
    const {theme, toggleTheme, setTheme} = useThemeStore();

    // Apply theme on mount and changes
    useEffect(() => {
        const root = document.documentElement;
        root.classList.remove('light', 'dark');
        root.classList.add(theme);
        root.setAttribute('data-theme', theme);
    }, [theme]);

    if (variant === 'icon') {
        return (
            <button
                onClick={toggleTheme}
                className={`p-2 rounded-lg transition-colors hover:bg-[var(--color-bg-hover)] ${className}`}
                title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
            >
                {theme === 'dark' ? (
                    <Sun className="h-5 w-5 text-[var(--color-text-muted)]"/>
                ) : (
                    <Moon className="h-5 w-5 text-[var(--color-text-muted)]"/>
                )}
            </button>
        );
    }

    return (
        <button
            onClick={toggleTheme}
            className={`
        flex items-center gap-2 px-3 py-2 w-full
        text-sm text-[var(--color-text-secondary)]
        rounded-lg transition-colors
        hover:bg-[var(--color-bg-hover)]
        hover:text-[var(--color-text-primary)]
        ${className}
      `}
        >
            {theme === 'dark' ? (
                <>
                    <Sun className="h-4 w-4"/>
                    <span>Light Mode</span>
                </>
            ) : (
                <>
                    <Moon className="h-4 w-4"/>
                    <span>Dark Mode</span>
                </>
            )}
        </button>
    );
}

// Hook to use theme in components
export function useTheme() {
    const {theme, setTheme, toggleTheme} = useThemeStore();

    const isDark = theme === 'dark';
    const isLight = theme === 'light';

    return {
        theme,
        isDark,
        isLight,
        setTheme,
        toggleTheme,
    };
}