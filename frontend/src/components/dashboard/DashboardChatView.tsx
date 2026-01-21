// frontend/src/components/dashboard/DashboardChatView.tsx
// Embeddable chat view for the main dashboard

'use client';

import React, {useCallback, useRef, useState} from 'react';
import {AnimatePresence, motion} from 'framer-motion';
import {History, Loader2, Maximize2, MessageSquare, Minimize2, Sparkles, X} from 'lucide-react';
import {ChatModule, type ChatModuleRef} from '@/components/chat';
import {chatApi} from '@/lib/api';
import type {Conversation} from '@/components/chat/types';

interface DashboardChatViewProps {
    projectId: string | null;
    projectName?: string;
    className?: string;
}

export function DashboardChatView({projectId, projectName, className = ''}: DashboardChatViewProps) {
    const chatRef = useRef<ChatModuleRef>(null);

    // State
    const [isExpanded, setIsExpanded] = useState(false);
    const [showHistory, setShowHistory] = useState(false);
    const [conversations, setConversations] = useState<Conversation[]>([]);
    const [conversationsLoading, setConversationsLoading] = useState(false);
    const [currentConversationId, setCurrentConversationId] = useState<string | null>(null);

    // Load conversation history
    const loadConversations = useCallback(async () => {
        if (!projectId) return;

        setConversationsLoading(true);
        try {
            const response = await chatApi.listConversations(projectId);
            setConversations(response.data);
        } catch (err) {
            console.error('Failed to load conversations:', err);
        } finally {
            setConversationsLoading(false);
        }
    }, [projectId]);

    // Toggle history panel
    const toggleHistory = () => {
        if (!showHistory) {
            loadConversations();
        }
        setShowHistory(!showHistory);
    };

    // Handle conversation change
    const handleConversationChange = useCallback((id: string | null) => {
        setCurrentConversationId(id);
        if (id) loadConversations();
    }, [loadConversations]);

    // Select conversation from history
    const selectConversation = (convId: string) => {
        setCurrentConversationId(convId);
        setShowHistory(false);
    };

    // New chat
    const handleNewChat = () => {
        chatRef.current?.startNewChat();
        setShowHistory(false);
    };

    // Format time
    const formatTime = (dateStr: string) => {
        const date = new Date(dateStr);
        const now = new Date();
        const diffMs = now.getTime() - date.getTime();
        const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

        if (diffDays === 0) return 'Today';
        if (diffDays === 1) return 'Yesterday';
        if (diffDays < 7) return `${diffDays}d ago`;
        return date.toLocaleDateString('en-US', {month: 'short', day: 'numeric'});
    };

    if (!projectId) {
        return (
            <div className={`flex flex-col items-center justify-center h-full p-8 text-center ${className}`}>
                <div
                    className="w-12 h-12 rounded-xl bg-[var(--color-bg-elevated)] flex items-center justify-center mb-4">
                    <MessageSquare className="h-6 w-6 text-[var(--color-text-muted)]"/>
                </div>
                <p className="text-[var(--color-text-muted)]">Select a project to start chatting</p>
            </div>
        );
    }

    return (
        <div className={`flex flex-col h-full bg-[var(--color-bg-primary)] ${className}`}>
            {/* Header */}
            <div
                className="flex items-center justify-between px-4 py-2 border-b border-[var(--color-border-subtle)] bg-[var(--color-bg-surface)]">
                <div className="flex items-center gap-2">
          <span
              className="flex items-center gap-1.5 px-2 py-1 rounded-lg bg-gradient-to-r from-purple-500/20 to-blue-500/20 text-purple-400 text-xs">
            <Sparkles className="h-3.5 w-3.5"/>
            AI Chat
          </span>
                    {projectName && (
                        <span className="text-xs text-[var(--color-text-muted)] truncate max-w-[120px]">
              {projectName}
            </span>
                    )}
                </div>

                <div className="flex items-center gap-1">
                    <button
                        onClick={toggleHistory}
                        className={`p-1.5 rounded-lg transition-colors ${
                            showHistory
                                ? 'bg-[var(--color-primary)]/20 text-[var(--color-primary)]'
                                : 'hover:bg-[var(--color-bg-hover)] text-[var(--color-text-muted)]'
                        }`}
                        title="Conversation history"
                    >
                        <History className="h-4 w-4"/>
                    </button>
                    <button
                        onClick={() => setIsExpanded(!isExpanded)}
                        className="p-1.5 rounded-lg hover:bg-[var(--color-bg-hover)] text-[var(--color-text-muted)] transition-colors"
                        title={isExpanded ? 'Minimize' : 'Maximize'}
                    >
                        {isExpanded ? <Minimize2 className="h-4 w-4"/> : <Maximize2 className="h-4 w-4"/>}
                    </button>
                </div>
            </div>

            {/* Main content */}
            <div className="flex-1 flex overflow-hidden">
                {/* History sidebar */}
                <AnimatePresence>
                    {showHistory && (
                        <motion.div
                            initial={{width: 0, opacity: 0}}
                            animate={{width: 200, opacity: 1}}
                            exit={{width: 0, opacity: 0}}
                            transition={{duration: 0.2}}
                            className="flex-shrink-0 border-r border-[var(--color-border-subtle)] bg-[var(--color-bg-surface)] overflow-hidden"
                        >
                            <div className="h-full flex flex-col">
                                <div className="p-2 border-b border-[var(--color-border-subtle)]">
                                    <button
                                        onClick={handleNewChat}
                                        className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-[var(--color-primary)] text-white text-xs font-medium hover:bg-[var(--color-primary-hover)] transition-colors"
                                    >
                                        <MessageSquare className="h-3.5 w-3.5"/>
                                        New Chat
                                    </button>
                                </div>

                                <div className="flex-1 overflow-y-auto p-2 space-y-1">
                                    {conversationsLoading ? (
                                        <div className="flex items-center justify-center py-4">
                                            <Loader2 className="h-4 w-4 animate-spin text-[var(--color-text-muted)]"/>
                                        </div>
                                    ) : conversations.length === 0 ? (
                                        <p className="text-xs text-[var(--color-text-muted)] text-center py-4">
                                            No conversations yet
                                        </p>
                                    ) : (
                                        conversations.map((conv) => (
                                            <button
                                                key={conv.id}
                                                onClick={() => selectConversation(conv.id)}
                                                className={`w-full p-2 rounded-lg text-left transition-colors ${
                                                    currentConversationId === conv.id
                                                        ? 'bg-[var(--color-primary)]/10 border border-[var(--color-primary)]/30'
                                                        : 'hover:bg-[var(--color-bg-hover)]'
                                                }`}
                                            >
                                                <p className="text-xs font-medium text-[var(--color-text-primary)] truncate">
                                                    {conv.title || 'New conversation'}
                                                </p>
                                                <p className="text-[10px] text-[var(--color-text-muted)] mt-0.5">
                                                    {formatTime(conv.updated_at)} · {conv.message_count} msgs
                                                </p>
                                            </button>
                                        ))
                                    )}
                                </div>
                            </div>
                        </motion.div>
                    )}
                </AnimatePresence>

                {/* Chat area */}
                <div className="flex-1 min-w-0">
                    <ChatModule
                        ref={chatRef}
                        projectId={projectId}
                        initialConversationId={currentConversationId}
                        onConversationChange={handleConversationChange}
                        requirePlanApproval={true}
                    />
                </div>
            </div>
        </div>
    );
}

// ============== FLOATING CHAT WIDGET ==============
interface FloatingChatWidgetProps {
    projectId: string | null;
    projectName?: string;
}

export function FloatingChatWidget({projectId, projectName}: FloatingChatWidgetProps) {
    const [isOpen, setIsOpen] = useState(false);
    const [isMinimized, setIsMinimized] = useState(false);

    if (!projectId) return null;

    return (
        <>
            {/* Floating button */}
            {!isOpen && (
                <motion.button
                    initial={{scale: 0}}
                    animate={{scale: 1}}
                    exit={{scale: 0}}
                    onClick={() => setIsOpen(true)}
                    className="fixed bottom-6 right-6 z-50 w-14 h-14 rounded-full bg-gradient-to-br from-purple-500 to-blue-500 text-white shadow-lg shadow-purple-500/25 hover:shadow-purple-500/40 transition-shadow flex items-center justify-center"
                >
                    <MessageSquare className="h-6 w-6"/>
                </motion.button>
            )}

            {/* Chat panel */}
            <AnimatePresence>
                {isOpen && (
                    <motion.div
                        initial={{opacity: 0, y: 20, scale: 0.95}}
                        animate={{
                            opacity: 1,
                            y: 0,
                            scale: 1,
                            height: isMinimized ? 56 : 500,
                            width: isMinimized ? 280 : 380,
                        }}
                        exit={{opacity: 0, y: 20, scale: 0.95}}
                        transition={{type: 'spring', damping: 25, stiffness: 300}}
                        className="fixed bottom-6 right-6 z-50 rounded-xl border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface)] shadow-2xl overflow-hidden"
                    >
                        {/* Widget header */}
                        <div
                            className="flex items-center justify-between px-4 py-3 bg-gradient-to-r from-purple-500/10 to-blue-500/10 border-b border-[var(--color-border-subtle)]">
                            <div className="flex items-center gap-2">
                                <div
                                    className="w-8 h-8 rounded-lg bg-gradient-to-br from-purple-500 to-blue-500 flex items-center justify-center">
                                    <Sparkles className="h-4 w-4 text-white"/>
                                </div>
                                <div>
                                    <h3 className="text-sm font-semibold text-[var(--color-text-primary)]">Maestro
                                        AI</h3>
                                    {projectName && (
                                        <p className="text-xs text-[var(--color-text-muted)] truncate max-w-[150px]">
                                            {projectName}
                                        </p>
                                    )}
                                </div>
                            </div>
                            <div className="flex items-center gap-1">
                                <button
                                    onClick={() => setIsMinimized(!isMinimized)}
                                    className="p-1.5 rounded-lg hover:bg-[var(--color-bg-hover)] text-[var(--color-text-muted)] transition-colors"
                                >
                                    {isMinimized ? <Maximize2 className="h-4 w-4"/> : <Minimize2 className="h-4 w-4"/>}
                                </button>
                                <button
                                    onClick={() => setIsOpen(false)}
                                    className="p-1.5 rounded-lg hover:bg-[var(--color-bg-hover)] text-[var(--color-text-muted)] transition-colors"
                                >
                                    <X className="h-4 w-4"/>
                                </button>
                            </div>
                        </div>

                        {/* Chat content */}
                        {!isMinimized && (
                            <div className="h-[calc(100%-56px)]">
                                <ChatModule
                                    projectId={projectId}
                                    requirePlanApproval={true}
                                />
                            </div>
                        )}
                    </motion.div>
                )}
            </AnimatePresence>
        </>
    );
}

export default DashboardChatView;