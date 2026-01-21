// frontend/src/app/dashboard/terminal/page.tsx
'use client';

import {motion} from 'framer-motion';
import {useRouter} from 'next/navigation';
import EmptyState from '@/components/dashboard/EmptyState';

export default function TerminalRoutePage() {
    const router = useRouter();

    return (
        <motion.div
            initial={{opacity: 0}}
            animate={{opacity: 1}}
            exit={{opacity: 0}}
            className="flex-1 flex flex-col h-full overflow-hidden"
        >
            {/* Header */}
            <div
                className="flex items-center justify-between px-6 py-4 border-b border-[var(--color-border-subtle)] bg-[var(--color-bg-surface)]">
                <div>
                    <h1 className="text-xl font-bold text-[var(--color-text-primary)]">
                        Terminal
                    </h1>
                    <p className="text-sm text-[var(--color-text-dimmer)]">
                        Execute commands in your project
                    </p>
                </div>
            </div>

            {/* Content */}
            <div className="flex-1 flex items-center justify-center">
                <EmptyState
                    type="generic"
                    message="Terminal not available yet"
                    action={{
                        label: 'Use AI Chat Instead',
                        onClick: () => router.push('/dashboard/chat'),
                    }}
                />
            </div>
        </motion.div>
    );
}