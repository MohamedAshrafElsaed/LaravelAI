'use client';

import { useRef } from 'react';
import { Plus, Sparkles } from 'lucide-react';
import { motion } from 'framer-motion';
import { InteractiveChat, type InteractiveChatRef } from './interactive/agent';
import { Button } from '@/components/ui/Button';

interface ChatProps {
    projectId: string;
    onProcessingEvent?: (event: any) => void;
    onConversationChange?: (conversationId: string | null) => void;
}

export function Chat({
    projectId,
    onConversationChange,
}: ChatProps) {
    const chatRef = useRef<InteractiveChatRef>(null);

    const handleNewChat = () => {
        chatRef.current?.startNewChat();
    };

    return (
        <div className="flex h-full flex-col bg-[var(--color-bg-primary)] relative overflow-hidden">
            {/* Background Gradients */}
            <div className="absolute top-0 left-0 w-full h-96 bg-gradient-to-b from-[var(--color-primary-subtle)]/5 to-transparent pointer-events-none" />

            {/* Header */}
            <motion.div
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4, ease: "easeOut" }}
                className="flex items-center justify-between border-b border-[var(--color-border-subtle)] bg-[var(--color-bg-overlay)] backdrop-blur-xl px-6 py-4 z-10 shadow-sm"
            >
                <div className="flex items-center gap-3">
                    <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-[var(--color-bg-elevated)] border border-[var(--color-border-subtle)] shadow-sm">
                        <div className="relative flex h-2 w-2">
                            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[var(--color-primary)] opacity-75"></span>
                            <span className="relative inline-flex rounded-full h-2 w-2 bg-[var(--color-primary)]"></span>
                        </div>
                        <span className="text-sm font-medium text-[var(--color-text-primary)]">
                            Multi-Agent Mode
                        </span>
                        <div className="h-4 w-[1px] bg-[var(--color-border-subtle)] mx-1" />
                        <Sparkles className="h-3.5 w-3.5 text-[var(--color-primary)]" />
                    </div>
                </div>
                <Button
                    variant="ghost"
                    onClick={handleNewChat}
                    className="group flex items-center gap-2 text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-bg-elevated)] transition-all duration-200 border border-transparent hover:border-[var(--color-border-subtle)] rounded-lg px-3"
                >
                    <Plus className="h-4 w-4 group-hover:text-[var(--color-primary)] transition-colors" />
                    <span className="hidden sm:inline font-medium">New Chat</span>
                </Button>
            </motion.div>

            {/* Interactive Chat Component */}
            <div className="flex-1 overflow-hidden relative z-0">
                <InteractiveChat
                    ref={chatRef}
                    projectId={projectId}
                    onConversationChange={onConversationChange}
                />
            </div>
        </div>
    );
}

export default Chat;
