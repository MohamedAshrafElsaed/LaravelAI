import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
  title: 'Laravel AI - AI-Powered Code Assistant',
  description: 'Modify your Laravel codebase using AI',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.className} min-h-screen bg-gray-950 text-gray-200 antialiased`}>
        <div className="relative flex min-h-screen flex-col">
          {/* Navigation */}
          <header className="sticky top-0 z-50 w-full border-b border-gray-800 bg-gray-950/95 backdrop-blur">
            <div className="container flex h-14 max-w-screen-2xl items-center px-4 mx-auto">
              <div className="flex items-center space-x-2">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className="h-6 w-6 text-blue-500"
                >
                  <path d="m18 16 4-4-4-4" />
                  <path d="m6 8-4 4 4 4" />
                  <path d="m14.5 4-5 16" />
                </svg>
                <span className="font-bold text-lg">Laravel AI</span>
              </div>

              <nav className="ml-auto flex items-center space-x-4">
                <a
                  href="/dashboard"
                  className="text-sm font-medium text-gray-400 transition-colors hover:text-white"
                >
                  Dashboard
                </a>
                <a
                  href="https://github.com"
                  target="_blank"
                  rel="noreferrer"
                  className="text-sm font-medium text-gray-400 transition-colors hover:text-white"
                >
                  GitHub
                </a>
              </nav>
            </div>
          </header>

          {/* Main content */}
          <main className="flex-1">{children}</main>

          {/* Footer */}
          <footer className="border-t border-gray-800 py-6">
            <div className="container flex flex-col items-center justify-center gap-2 px-4 text-center text-sm text-gray-500 mx-auto">
              <p>Built with FastAPI, Next.js, and Claude AI</p>
            </div>
          </footer>
        </div>
      </body>
    </html>
  );
}