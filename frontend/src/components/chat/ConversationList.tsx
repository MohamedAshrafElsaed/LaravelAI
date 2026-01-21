// frontend/src/components/chat/ConversationList.tsx
// Reusable conversation list component for sidebars

'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
    MessageSquare, Plus, Trash2, Search, Loader2, Clock,
    MoreHorizontal, Archive, Pin, Edit2, Check, X
} from 'lucide-react';
import { chatApi } from '@/lib/api';
import type { Conversation } from './types';

interface ConversationListProps {
    projectId: string;
    currentConversationId: string | null;
    onSelectConversation: (id: string) => void;
    onNewChat: () => void;
    onDeleteConversation?: (id: string) => void;
    compact?: boolean;
    showSearch?: boolean;
    maxHeight?: string;
    className?: string;
}

export function ConversationList({
                                     projectId,
                                     currentConversationId,
                                     onSelectConversation,
                                     onNewChat,
                                     onDeleteConversation,
                                     compact = false,
                                     showSearch = true,
                                     maxHeight = '400px',
                                     className = '',
                                 }: ConversationListProps) {
    const [conversations, setConversations] = useState<Conversation[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [searchQuery, setSearchQuery] = useState('');
    const [deleteLoading, setDeleteLoading] = useState<string | null>(null);
    const [menuOpen, setMenuOpen] = useState<string | null>(null);
    const [renaming, setRenaming] = useState<string | null>(null);
    const [renameValue, setRenameValue] = useState('');

    // Load conversations
    const loadConversations = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const response = await chatApi.listConversations(projectId);
            setConversations(response.data);
        } catch (err) {
            console.error('Failed to load conversations:', err);
            setError('Failed to load conversations');
        } finally {
            setLoading(false);
        }
    }, [projectId]);

    useEffect(() => {
        loadConversations();
    }, [loadConversations]);

    // Filter conversations
    const filteredConversations = searchQuery
        ? conversations.filter(
            (c) =>
                c.title?.toLowerCase().includes(searchQuery.toLowerCase()) ||
                c.last_message?.toLowerCase().includes(searchQuery.toLowerCase())
        )
        : conversations;

    // Group conversations by date
    const groupedConversations = groupByDate(filteredConversations);

    // Delete conversation
    const handleDelete = async (convId: string) => {
        setDeleteLoading(convId);
        try {
            await chatApi.deleteConversation(projectId, convId);
            setConversations((prev) => prev.filter((c) => c.id !== convId));
            onDeleteConversation?.(convId);
        } catch (err) {
            console.error('Failed to delete conversation:', err);
        } finally {
            setDeleteLoading(null);
            setMenuOpen(null);
        }
    };

    // Format time
    const formatTime = (dateStr: string) => {
        const date = new Date(dateStr);
        const now = new Date();
        const diffMs = now.getTime() - date.getTime();
        const diffMins = Math.floor(diffMs / (1000 * 60));
        const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
        const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

        if (diffMins < 1) return 'Just now';
        if (diffMins < 60) return `${diffMins}m ago`;
        if (diffHours < 24) return `${diffHours}h ago`;
        if (diffDays === 1) return 'Yesterday';
        if (diffDays < 7) return `${diffDays}d ago`;
        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    };

    // Click outside to close menu
    useEffect(() => {
        const handleClickOutside = () => setMenuOpen(null);
        if (menuOpen) {
            document.addEventListener('click', handleClickOutside);
            return () => document.removeEventListener('click', handleClickOutside);
        }
    }, [menuOpen]);

    return (
        <div className={`flex flex-col ${className}`}>
            {/* New Chat Button */}
            <div className="p-2 border-b border-[var(--color-border-subtle)]">
                <button
                    onClick={onNewChat}
                    className={`w-full flex items-center justify-center gap-2 rounded-lg bg-[var(--color-primary)] text-white font-medium hover:bg-[var(--color-primary-hover)] transition-colors ${
                        compact ? 'px-3 py-2 text-xs' : 'px-4 py-2.5 text-sm'
                    }`}
                >
                    <Plus className={compact ? 'h-3.5 w-3.5' : 'h-4 w-4'} />
                    New Chat
                </button>
            </div>

            {/* Search */}
            {showSearch && (
                <div className="p-2">
                    <div className="relative">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[var(--color-text-muted)]" />
                        <input
                            type="text"
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            placeholder="Search conversations..."
                            className={`w-full pl-9 pr-3 rounded-lg bg-[var(--color-bg-elevated)] border border-[var(--color-border-subtle)] text-[var(--color-text-primary)] placeholder-[var(--color-text-muted)] focus:outline-none focus:border-[var(--color-primary)] ${
                                compact ? 'py-1.5 text-xs' : 'py-2 text-sm'
                            }`}
                        />
                    </div>
                </div>
            )}

            {/* Conversation List */}
            <div
                className="flex-1 overflow-y-auto custom-scrollbar"
                style={{ maxHeight }}
            >
                {loading ? (
                    <div className="flex items-center justify-center py-8">
                        <Loader2 className="h-5 w-5 animate-spin text-[var(--color-text-muted)]" />
                    </div>
                ) : error ? (
                    <div className="flex flex-col items-center justify-center py-8 px-4 text-center">
                        <p className="text-sm text-red-400">{error}</p>
                        <button
                            onClick={loadConversations}
                            className="mt-2 text-xs text-[var(--color-primary)] hover:underline"
                        >
                            Retry
                        </button>
                    </div>
                ) : filteredConversations.length === 0 ? (
                    <div className="flex flex-col items-center justify-center py-8 px-4 text-center">
                        <MessageSquare className="h-8 w-8 text-[var(--color-text-muted)] mb-2" />
                        <p className="text-sm text-[var(--color-text-muted)]">
                            {searchQuery ? 'No matching conversations' : 'No conversations yet'}
                        </p>
                    </div>
                ) : (
                    <div className="px-2 py-1">
                        {Object.entries(groupedConversations).map(([group, convs]) => (
                            <div key={group}>
                                {/* Group header */}
                                <div className="px-2 py-1.5 sticky top-0 bg-[var(--color-bg-surface)]">
                  <span className="text-[10px] font-medium text-[var(--color-text-muted)] uppercase tracking-wider">
                    {group}
                  </span>
                                </div>

                                {/* Conversations */}
                                <div className="space-y-1">
                                    {convs.map((conv) => (
                                        <div
                                            key={conv.id}
                                            className="relative group"
                                        >
                                            <button
                                                onClick={() => onSelectConversation(conv.id)}
                                                className={`w-full flex items-start gap-2 rounded-lg text-left transition-colors ${
                                                    compact ? 'p-2' : 'p-3'
                                                } ${
                                                    currentConversationId === conv.id
                                                        ? 'bg-[var(--color-primary)]/10 border border-[var(--color-primary)]/30'
                                                        : 'hover:bg-[var(--color-bg-hover)] border border-transparent'
                                                }`}
                                            >
                                                <MessageSquare
                                                    className={`flex-shrink-0 mt-0.5 ${compact ? 'h-3.5 w-3.5' : 'h-4 w-4'} ${
                                                        currentConversationId === conv.id
                                                            ? 'text-[var(--color-primary)]'
                                                            : 'text-[var(--color-text-muted)]'
                                                    }`}
                                                />
                                                <div className="flex-1 min-w-0">
                                                    <div className="flex items-center justify-between gap-2">
                            <span
                                className={`font-medium truncate ${compact ? 'text-xs' : 'text-sm'} ${
                                    currentConversationId === conv.id
                                        ? 'text-[var(--color-primary)]'
                                        : 'text-[var(--color-text-primary)]'
                                }`}
                            >
                              {conv.title || 'New conversation'}
                            </span>
                                                        <span className="text-[10px] text-[var(--color-text-muted)] flex-shrink-0">
                              {formatTime(conv.updated_at)}
                            </span>
                                                    </div>
                                                    {!compact && conv.last_message && (
                                                        <p className="text-xs text-[var(--color-text-muted)] truncate mt-0.5">
                                                            {conv.last_message}
                                                        </p>
                                                    )}
                                                    <div className="flex items-center gap-2 mt-1">
                            <span className="text-[10px] text-[var(--color-text-dimmer)]">
                              {conv.message_count} message{conv.message_count !== 1 ? 's' : ''}
                            </span>
                                                    </div>
                                                </div>
                                            </button>

                                            {/* Menu button */}
                                            <button
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    setMenuOpen(menuOpen === conv.id ? null : conv.id);
                                                }}
                                                className="absolute top-2 right-2 p-1 rounded opacity-0 group-hover:opacity-100 hover:bg-[var(--color-bg-elevated)] text-[var(--color-text-muted)] transition-opacity"
                                            >
                                                <MoreHorizontal className="h-4 w-4" />
                                            </button>

                                            {/* Context menu */}
                                            <AnimatePresence>
                                                {menuOpen === conv.id && (
                                                    <motion.div
                                                        initial={{ opacity: 0, scale: 0.95 }}
                                                        animate={{ opacity: 1, scale: 1 }}
                                                        exit={{ opacity: 0, scale: 0.95 }}
                                                        className="absolute top-8 right-2 z-10 w-36 rounded-lg border border-[var(--color-border-subtle)] bg-[var(--color-bg-elevated)] shadow-lg py-1"
                                                    >
                                                        <button
                                                            onClick={(e) => {
                                                                e.stopPropagation();
                                                                handleDelete(conv.id);
                                                            }}
                                                            disabled={deleteLoading === conv.id}
                                                            className="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-red-400 hover:bg-red-500/10 transition-colors"
                                                        >
                                                            {deleteLoading === conv.id ? (
                                                                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                                            ) : (
                                                                <Trash2 className="h-3.5 w-3.5" />
                                                            )}
                                                            Delete
                                                        </button>
                                                    </motion.div>
                                                )}
                                            </AnimatePresence>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>

            {/* Footer */}
            <div className="p-2 border-t border-[var(--color-border-subtle)]">
                <div className="flex items-center justify-between text-[10px] text-[var(--color-text-muted)]">
                    <div className="flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        <span>{conversations.length} conversations</span>
                    </div>
                    <button
                        onClick={loadConversations}
                        className="hover:text-[var(--color-text-secondary)] transition-colors"
                    >
                        Refresh
                    </button>
                </div>
            </div>
        </div>
    );
}

// ============== HELPERS ==============
function groupByDate(conversations: Conversation[]): Record<string, Conversation[]> {
    const groups: Record<string, Conversation[]> = {};
    const now = new Date();

    conversations.forEach((conv) => {
        const date = new Date(conv.updated_at);
        const diffMs = now.getTime() - date.getTime();
        const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

        let group: string;
        if (diffDays === 0) {
            group = 'Today';
        } else if (diffDays === 1) {
            group = 'Yesterday';
        } else if (diffDays < 7) {
            group = 'This Week';
        } else if (diffDays < 30) {
            group = 'This Month';
        } else {
            group = 'Older';
        }

        if (!groups[group]) {
            groups[group] = [];
        }
        groups[group].push(conv);
    });

    return groups;
}

export default ConversationList;