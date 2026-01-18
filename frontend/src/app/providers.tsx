'use client';

import {useEffect, useState} from 'react';
import {useThemeStore} from '@/lib/store';

function ThemeInitializer({children}: { children: React.ReactNode }) {
    const {theme} = useThemeStore();
    const [mounted, setMounted] = useState(false);

    useEffect(() => {
        // Apply theme immediately on mount
        const root = document.documentElement;
        root.classList.remove('light', 'dark');
        root.classList.add(theme);
        root.setAttribute('data-theme', theme);
        setMounted(true);
    }, [theme]);

    // Prevent flash of wrong theme
    if (!mounted) {
        return (
            <div style={{visibility: 'hidden'}}>
                {children}
            </div>
        );
    }

    return <>{children}</>;
}

export function Providers({children}: { children: React.ReactNode }) {
    return (
        <ThemeInitializer>
            {children}
        </ThemeInitializer>
    );
}