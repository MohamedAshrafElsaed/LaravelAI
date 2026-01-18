'use client';

import {motion} from 'framer-motion';

interface EmptyStateProps {
    type?: 'search' | 'files' | 'generic';
    message?: string;
    action?: {
        label: string;
        onClick: () => void;
    };
}

const asciiArt = {
    search: `
   _  _
  (o)(o)--.
   \\../ (  )
   m\\/m--m'--
  `,
    files: `
    .---.
   /   /|
  .---. |
  |   | '
  |   |/
  '---'
  `,
    generic: `
    [ ]
   /[ ]\\
  [ ][ ]
  `,
};

export default function EmptyState({
                                       type = 'generic',
                                       message = 'No data available',
                                       action,
                                   }: EmptyStateProps) {
    return (
        <div
            className="flex flex-col items-center justify-center h-full text-[var(--color-text-dimmer)] p-8 font-mono opacity-60">
            <motion.pre
                initial={{opacity: 0, y: 10}}
                animate={{opacity: 1, y: 0}}
                className="text-xs leading-none mb-4 whitespace-pre select-none text-[var(--color-primary)]"
            >
                {asciiArt[type]}
            </motion.pre>
            <motion.div
                initial={{opacity: 0}}
                animate={{opacity: 1}}
                transition={{delay: 0.1}}
                className="text-sm border border-dashed border-[var(--color-border-subtle)] px-3 py-1 rounded-sm"
            >
                {message}
            </motion.div>
            {action && (
                <motion.button
                    initial={{opacity: 0}}
                    animate={{opacity: 1}}
                    transition={{delay: 0.2}}
                    onClick={action.onClick}
                    className="mt-4 px-4 py-2 text-sm bg-[var(--color-primary)] text-white rounded-sm hover:bg-[var(--color-primary-hover)] transition-colors"
                >
                    {action.label}
                </motion.button>
            )}
        </div>
    );
}