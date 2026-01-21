'use client';

import React, {forwardRef, useImperativeHandle, useState} from 'react';
import {Check, FileCode, FolderOpen, Loader2, MessageSquare, Plus, Send} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import DevFileExplorer from './DevFileExplorer';
import {useChat} from '@/hooks/useChat';

// ============== TYPES ==============
type ViewTab = 'chat' | 'explorer';

interface SessionViewProps {
    projectId: string;
    conversationId?: string | null;
    onConversationChange?: (id: string | null) => void;
}

export interface SessionViewRef {
    startNewChat: () => void;
    sendMessage: (message: string) => void;
}

// ============== COMPONENT ==============
const SessionView = forwardRef<SessionViewRef, SessionViewProps>(function SessionView(
    {projectId, conversationId: initialConversationId, onConversationChange},
    ref
) {
    const [activeTab, setActiveTab] = useState<ViewTab>('chat');

    // Use the chat hook
    const {
        messages,
        input,
        setInput,
        isLoading,
        isStreaming,
        streamingContent,
        error,
        isLoadingMessages,
        conversationEntries,
        currentThinking,
        awaitingPlanApproval,
        currentPlan,
        isPlanApprovalLoading,
        validationResult,
        messagesEndRef,
        sendMessage,
        handlePlanApproval,
        handlePlanRejection,
        startNewChat,
    } = useChat({
        projectId,
        initialConversationId,
        onConversationChange,
        requirePlanApproval: true,
    });

    // Expose methods to parent
    useImperativeHandle(ref, () => ({
        startNewChat,
        sendMessage,
    }), [startNewChat, sendMessage]);

    // Handle key press in input
    const handleKeyPress = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    };

    return (
        <div className="flex flex-col h-full bg-(--color-bg-primary)">
            {/* Tab Bar */}
            <div
                className="flex items-center gap-2 px-4 py-2 bg-(--color-bg-surface) border-b border-(--color-border)">
                <button
                    onClick={() => setActiveTab('chat')}
                    className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                        activeTab === 'chat'
                            ? 'bg-[var(--color-primary)] text-white'
                            : 'text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-elevated)] hover:text-[var(--color-text-primary)]'
                    }`}
                >
                    <MessageSquare className="h-4 w-4"/>
                    Chat
                </button>
                <button
                    onClick={() => setActiveTab('explorer')}
                    className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                        activeTab === 'explorer'
                            ? 'bg-[var(--color-primary)] text-white'
                            : 'text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-elevated)] hover:text-[var(--color-text-primary)]'
                    }`}
                >
                    <FolderOpen className="h-4 w-4"/>
                    Explorer
                </button>

                {/* New Chat button (only show in chat tab) */}
                {activeTab === 'chat' && (
                    <button
                        onClick={startNewChat}
                        className="ml-auto p-2 hover:bg-[var(--color-bg-elevated)] rounded-lg transition-colors"
                        title="New Chat"
                    >
                        <Plus className="h-5 w-5 text-[var(--color-text-secondary)]"/>
                    </button>
                )}
            </div>

            {/* Tab Content */}
            <div className="flex-1 overflow-hidden">
                {activeTab === 'chat' ? (
                    /* ========== CHAT VIEW ========== */
                    <div className="flex flex-col h-full">
                        {/* Messages Area */}
                        <div className="flex-1 overflow-y-auto p-4 space-y-4">
                            {isLoadingMessages && (
                                <div className="flex items-center justify-center py-8">
                                    <Loader2 className="h-6 w-6 animate-spin text-[var(--color-text-secondary)]"/>
                                    <span className="ml-2 text-[var(--color-text-secondary)]">Loading messages...</span>
                                </div>
                            )}

                            {/* Messages */}
                            {messages.map((message) => (
                                <div
                                    key={message.id}
                                    className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
                                >
                                    <div className={`max-w-[80%] rounded-lg p-4 ${
                                        message.role === 'user'
                                            ? 'bg-[var(--color-primary)] text-white'
                                            : 'bg-[var(--color-bg-surface)] text-[var(--color-text-primary)] border border-[var(--color-border)]'
                                    }`}>
                                        <ReactMarkdown
                                            remarkPlugins={[remarkGfm]}
                                            className="prose prose-invert prose-sm max-w-none"
                                        >
                                            {message.content}
                                        </ReactMarkdown>

                                        {/* Files Changed */}
                                        {message.processingData?.execution_results && message.processingData.execution_results.length > 0 && (
                                            <div className="mt-3 pt-3 border-t border-[var(--color-border)]">
                                                <div
                                                    className="flex items-center gap-2 text-sm text-[var(--color-text-secondary)] mb-2">
                                                    <FileCode className="h-4 w-4"/>
                                                    <span>Files Changed ({message.processingData.execution_results.length})</span>
                                                </div>
                                                <div className="font-mono text-xs space-y-1">
                                                    {message.processingData.execution_results.map((result: any, i: number) => (
                                                        <div key={i} className="flex items-center gap-2">
                                                            {result.success ?
                                                                <Check className="h-3 w-3 text-green-400"/> :
                                                                <span className="text-red-400">✗</span>}
                                                            <span
                                                                className={result.action === 'create' ? 'text-green-400' : result.action === 'delete' ? 'text-red-400' : 'text-yellow-400'}>
                                                                [{result.action}]
                                                            </span>
                                                            <span className="text-blue-400">{result.file}</span>
                                                        </div>
                                                    ))}
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            ))}

                            {/* Streaming content */}
                            {isStreaming && streamingContent && (
                                <div className="flex justify-start">
                                    <div
                                        className="max-w-[80%] rounded-lg p-4 bg-[var(--color-bg-surface)] border border-[var(--color-border)]">
                                        <ReactMarkdown remarkPlugins={[remarkGfm]}
                                                       className="prose prose-invert prose-sm max-w-none">
                                            {streamingContent}
                                        </ReactMarkdown>
                                    </div>
                                </div>
                            )}

                            {/* Current Thinking */}
                            {currentThinking && (
                                <div
                                    className="flex items-center gap-3 p-4 bg-[var(--color-bg-surface)] rounded-lg border border-[var(--color-border)]">
                                    <span className="text-2xl">{currentThinking.agent.avatar_emoji}</span>
                                    <div>
                                        <div className="text-sm font-medium"
                                             style={{color: currentThinking.agent.color}}>
                                            {currentThinking.agent.name}
                                        </div>
                                        <div className="text-xs text-[var(--color-text-secondary)]">
                                            {currentThinking.thought || 'Processing...'}
                                        </div>
                                    </div>
                                </div>
                            )}

                            {/* Plan Approval */}
                            {awaitingPlanApproval && currentPlan && (
                                <div
                                    className="p-4 bg-[var(--color-bg-surface)] rounded-lg border border-[var(--color-border)]">
                                    <div className="flex items-center gap-2 mb-3">
                                        <span className="text-xl">🟠</span>
                                        <span
                                            className="font-medium text-[var(--color-primary)]">Blueprint's Plan</span>
                                    </div>
                                    <p className="text-sm text-[var(--color-text-secondary)] mb-3">{currentPlan.summary}</p>
                                    <div className="space-y-2 mb-4">
                                        {currentPlan.steps.map((step: any, i: number) => (
                                            <div key={i} className="flex items-center gap-2 text-sm font-mono">
                                                <span className="text-[var(--color-text-secondary)]">{i + 1}.</span>
                                                <span
                                                    className={step.action === 'create' ? 'text-green-400' : step.action === 'delete' ? 'text-red-400' : 'text-yellow-400'}>
                                                    [{step.action}]
                                                </span>
                                                <span className="text-blue-400">{step.file}</span>
                                            </div>
                                        ))}
                                    </div>
                                    <div className="flex gap-2">
                                        <button
                                            onClick={() => handlePlanApproval(currentPlan)}
                                            disabled={isPlanApprovalLoading}
                                            className="px-4 py-2 bg-[var(--color-success)] text-white rounded-lg hover:opacity-90 disabled:opacity-50 text-sm font-medium"
                                        >
                                            {isPlanApprovalLoading ?
                                                <Loader2 className="h-4 w-4 animate-spin"/> : 'Approve'}
                                        </button>
                                        <button
                                            onClick={() => handlePlanRejection('User rejected')}
                                            disabled={isPlanApprovalLoading}
                                            className="px-4 py-2 bg-[var(--color-danger)] text-white rounded-lg hover:opacity-90 disabled:opacity-50 text-sm font-medium"
                                        >
                                            Reject
                                        </button>
                                    </div>
                                </div>
                            )}

                            {/* Error */}
                            {error && (
                                <div className="p-4 rounded-lg bg-red-500/10 border border-red-500/30">
                                    <p className="text-sm text-red-400">{error}</p>
                                </div>
                            )}

                            <div ref={messagesEndRef}/>
                        </div>

                        {/* Input Area */}
                        <div className="border-t border-[var(--color-border)] p-4">
                            <div className="flex gap-2">
                                <textarea
                                    value={input}
                                    onChange={(e) => setInput(e.target.value)}
                                    onKeyDown={handleKeyPress}
                                    placeholder="Type your message..."
                                    disabled={isLoading || awaitingPlanApproval}
                                    className="flex-1 px-4 py-3 bg-[var(--color-bg-surface)] border border-[var(--color-border)] rounded-lg text-[var(--color-text-primary)] placeholder-[var(--color-text-secondary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)] resize-none"
                                    rows={1}
                                />
                                <button
                                    onClick={() => sendMessage()}
                                    disabled={!input.trim() || isLoading || awaitingPlanApproval}
                                    className="px-4 py-3 bg-[var(--color-primary)] text-white rounded-lg hover:opacity-90 disabled:opacity-50 transition-opacity"
                                >
                                    {isLoading ? <Loader2 className="h-5 w-5 animate-spin"/> :
                                        <Send className="h-5 w-5"/>}
                                </button>
                            </div>

                            {isLoading && !awaitingPlanApproval && (
                                <div
                                    className="mt-2 text-xs text-[var(--color-text-secondary)] flex items-center gap-2">
                                    <Loader2 className="h-3 w-3 animate-spin"/>
                                    Processing with AI agents...
                                </div>
                            )}
                        </div>
                    </div>
                ) : (
                    /* ========== FILE EXPLORER VIEW ========== */
                    <DevFileExplorer projectId={projectId}/>
                )}
            </div>
        </div>
    );
});

export default SessionView;