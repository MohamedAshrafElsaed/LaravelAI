import type {Metadata} from 'next';
import './globals.css';
import {Providers} from './providers';

export const metadata: Metadata = {
    title: 'Maestro AI - Enterprise App Builder',
    description: 'Build enterprise applications with AI-powered precision',
};

export default function RootLayout({
                                       children,
                                   }: {
    children: React.ReactNode;
}) {
    return (
        <html lang="en" suppressHydrationWarning>
        <head>
            <link rel="preconnect" href="https://fonts.googleapis.com"/>
            <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous"/>
            <link
                href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600&display=swap"
                rel="stylesheet"
            />
            {/* Prevent flash of wrong theme */}
            <script
                dangerouslySetInnerHTML={{
                    __html: `
              (function() {
                try {
                  var stored = localStorage.getItem('theme-storage');
                  var theme = stored ? JSON.parse(stored).state.theme : 'dark';
                  document.documentElement.classList.add(theme);
                  document.documentElement.setAttribute('data-theme', theme);
                } catch (e) {
                  document.documentElement.classList.add('dark');
                  document.documentElement.setAttribute('data-theme', 'dark');
                }
              })();
            `,
                }}
            />
        </head>
        <body
            className="font-sans min-h-screen bg-[var(--color-bg-primary)] text-[var(--color-text-primary)] antialiased">
        <Providers>
            {children}
        </Providers>
        </body>
        </html>
    );
}