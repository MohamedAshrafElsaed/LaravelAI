// frontend/src/components/chat/ChatModule.tsx
'use client';

import React, { useState, useRef, useEffect, useCallback, forwardRef, useImperativeHandle } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
    Send, Loader2, AlertCircle, CheckCircle, X, Plus, Sparkles,
    Bot, ChevronDown, ChevronRight, GitBranch, FileCode, Play,
    GitPullRequest, ExternalLink, Copy, Check, RotateCcw
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

import { chatApi, gitApi, gitChangesApi, getErrorMessage } from '@/lib/api';
import type { Plan, PlanStep, ValidationResult, AgentType, ConversationEntry, AgentThinkingState, Message, InteractiveEvent, GitChange, GitChangeFile } from './types';
import { AgentTimeline } from './AgentTimeline';
import { PlanApprovalCard } from './PlanApprovalCard';
import { ChangesReviewPanel } from './ChangesReviewPanel';
import { AgentBadge, AGENT_CONFIG } from './AgentBadge';

// ============== TYPES ==============
export interface ChatModuleProps {
    projectId: string;
    initialConversationId?: string | null;
    onConversationChange?: (id: string | null) => void;
    requirePlanApproval?: boolean;
    className?: string;
}

export interface ChatModuleRef {
    startNewChat: () => void;
    sendMessage: (message: string) => void;
}

// ============== MAIN COMPONENT ==============
export const ChatModule = forwardRef<ChatModuleRef, ChatModuleProps>(function ChatModule(
    { projectId, initialConversationId, onConversationChange, requirePlanApproval = true, className = '' },
    ref
) {
    // Core state
    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [isStreaming, setIsStreaming] = useState(false);
    const [streamingContent, setStreamingContent] = useState('');
    const [conversationId, setConversationId] = useState<string | null>(initialConversationId || null);
    const [error, setError] = useState<string | null>(null);
    const [isLoadingMessages, setIsLoadingMessages] = useState(false);
    const [mounted, setMounted] = useState(false);

    // Agent conversation state
    const [conversationEntries, setConversationEntries] = useState<ConversationEntry[]>([]);
    const [currentThinking, setCurrentThinking] = useState<AgentThinkingState | null>(null);
    const entryIdRef = useRef(0);

    // Plan approval state
    const [awaitingPlanApproval, setAwaitingPlanApproval] = useState(false);
    const [currentPlan, setCurrentPlan] = useState<Plan | null>(null);
    const [isPlanApprovalLoading, setIsPlanApprovalLoading] = useState(false);

    // Validation & execution state
    const [validationResult, setValidationResult] = useState<ValidationResult | null>(null);
    const [executionResults, setExecutionResults] = useState<any[]>([]);

    // Changes review state
    const [showChangesReview, setShowChangesReview] = useState(false);
    const [pendingChanges, setPendingChanges] = useState<GitChangeFile[]>([]);

    // UI state
    const [showAgentTimeline, setShowAgentTimeline] = useState(true);

    // Refs
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLTextAreaElement>(null);
    const abortControllerRef = useRef<AbortController | null>(null);

    // Storage keys
    const conversationKey = `conversation_${projectId}`;
    const processingStateKey = `chat_processing_${projectId}`;

    // ============== HELPERS ==============
    const generateEntryId = useCallback(() => {
        entryIdRef.current += 1;
        return `entry-${entryIdRef.current}`;
    }, []);

    const addEntry = useCallback((entry: Omit<ConversationEntry, 'id'>) => {
        const newEntry = { ...entry, id: generateEntryId() };
        setConversationEntries(prev => [...prev, newEntry]);
    }, [generateEntryId]);

    const clearEntries = useCallback(() => {
        setConversationEntries([]);
        setCurrentThinking(null);
        entryIdRef.current = 0;
    }, []);

    const scrollToBottom = useCallback(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, []);

    const saveProcessingState = useCallback((isProcessing: boolean, convId: string | null) => {
        if (typeof window === 'undefined') return;
        if (isProcessing && convId) {
            localStorage.setItem(processingStateKey, JSON.stringify({
                isLoading: true, conversationId: convId, timestamp: Date.now()
            }));
        } else {
            localStorage.removeItem(processingStateKey);
        }
    }, [processingStateKey]);

    // ============== LIFECYCLE ==============
    useEffect(() => {
        setMounted(true);
        console.log('[ChatModule] Mounted with projectId:', projectId);

        // Load auth token and restore conversation
        if (typeof window !== 'undefined') {
            const token = localStorage.getItem('auth_token');
            console.log('[ChatModule] Auth token exists:', !!token);

            if (initialConversationId) {
                console.log('[ChatModule] Loading initial conversation:', initialConversationId);
                loadMessages(initialConversationId);
            } else {
                const savedConvId = localStorage.getItem(conversationKey);
                if (savedConvId) {
                    console.log('[ChatModule] Loading saved conversation:', savedConvId);
                    loadMessages(savedConvId);
                } else {
                    console.log('[ChatModule] No saved conversation, showing welcome screen');
                }
            }
        }
    }, [projectId]);

    // Update conversation when initialConversationId changes
    useEffect(() => {
        if (mounted && initialConversationId && initialConversationId !== conversationId) {
            console.log('[ChatModule] Conversation ID changed, loading:', initialConversationId);
            loadMessages(initialConversationId);
        }
    }, [initialConversationId, mounted]);

    useEffect(() => {
        scrollToBottom();
    }, [messages, streamingContent, conversationEntries, scrollToBottom]);

    // ============== API METHODS ==============
    const loadMessages = useCallback(async (convId: string) => {
        console.log('[ChatModule] loadMessages called for:', convId);
        setIsLoadingMessages(true);
        setError(null);

        try {
            const response = await chatApi.getMessages(projectId, convId);
            console.log('[ChatModule] Loaded messages:', response.data?.length || 0);

            const loadedMessages: Message[] = response.data.map((msg: any) => ({
                id: msg.id,
                role: msg.role,
                content: msg.content,
                timestamp: new Date(msg.created_at),
                processingData: msg.processing_data || {},
            }));
            setMessages(loadedMessages);
            setConversationId(convId);
            onConversationChange?.(convId);
            localStorage.setItem(conversationKey, convId);
            saveProcessingState(false, null);
        } catch (err: any) {
            console.error('[ChatModule] Failed to load messages:', err);
            // If conversation not found, clear it from localStorage and start fresh
            if (err?.status === 404 || err?.response?.status === 404) {
                console.log('[ChatModule] Conversation not found, clearing saved state');
                localStorage.removeItem(conversationKey);
                setMessages([]);
                setConversationId(null);
            } else {
                setError(getErrorMessage(err));
            }
        } finally {
            setIsLoadingMessages(false);
        }
    }, [projectId, onConversationChange, saveProcessingState, conversationKey]);

    // ============== SSE EVENT HANDLERS ==============
    const parseSSEChunk = useCallback((chunk: string): InteractiveEvent[] => {
        const events: InteractiveEvent[] = [];
        const lines = chunk.split('\n');
        let currentEvent: string | null = null;

        for (const line of lines) {
            if (line.startsWith('event:')) {
                currentEvent = line.substring(6).trim();
            } else if (line.startsWith('data:') && currentEvent) {
                try {
                    const data = JSON.parse(line.substring(5).trim());
                    events.push({ event: currentEvent as any, data });
                } catch (e) {
                    console.error('Failed to parse SSE data:', e);
                }
                currentEvent = null;
            }
        }
        return events;
    }, []);

    const processAgentEvent = useCallback((event: InteractiveEvent) => {
        const { event: eventType, data } = event;
        const timestamp = data.timestamp || new Date().toISOString();

        switch (eventType) {
            case 'agent_message':
                addEntry({
                    type: 'message', timestamp,
                    agentType: data.from_agent as AgentType,
                    toAgentType: data.to_agent as AgentType,
                    message: data.message,
                    messageType: data.message_type,
                });
                break;

            case 'agent_handoff':
                addEntry({
                    type: 'handoff', timestamp,
                    agentType: data.from_agent as AgentType,
                    toAgentType: data.to_agent as AgentType,
                    message: data.message,
                });
                break;

            case 'agent_thinking':
            case 'intent_thinking':
            case 'context_thinking':
            case 'planning_thinking':
            case 'step_thinking':
            case 'validation_thinking':
                setCurrentThinking({
                    agent: AGENT_CONFIG[data.agent as AgentType] || AGENT_CONFIG.conductor,
                    thought: data.thought,
                    actionType: data.action_type,
                    filePath: data.file_path,
                    progress: data.progress || 0,
                });
                break;

            case 'intent_started':
            case 'context_started':
            case 'planning_started':
            case 'execution_started':
            case 'validation_started':
                setCurrentThinking({
                    agent: AGENT_CONFIG[data.agent as AgentType] || AGENT_CONFIG.conductor,
                    thought: data.message || 'Processing...',
                    progress: 0,
                });
                addEntry({
                    type: 'message', timestamp,
                    agentType: data.agent as AgentType,
                    message: data.message,
                    messageType: 'greeting',
                });
                break;

            case 'intent_analyzed':
            case 'context_retrieved':
            case 'plan_created':
            case 'execution_completed':
            case 'validation_result':
                setCurrentThinking(null);
                addEntry({
                    type: 'message', timestamp,
                    agentType: data.agent as AgentType,
                    message: data.message,
                    messageType: 'completion',
                });
                break;

            case 'step_started':
                setCurrentThinking({
                    agent: AGENT_CONFIG.forge,
                    thought: data.step?.description || 'Working on step...',
                    actionType: data.step?.action,
                    filePath: data.step?.file,
                    progress: 0,
                });
                addEntry({
                    type: 'step', timestamp,
                    agentType: 'forge',
                    actionType: data.step?.action,
                    filePath: data.step?.file,
                    message: data.step?.description,
                    completed: false,
                });
                break;

            case 'step_completed':
                setCurrentThinking(null);
                setConversationEntries(prev => {
                    const updated = [...prev];
                    for (let i = updated.length - 1; i >= 0; i--) {
                        if (updated[i].type === 'step' && !updated[i].completed) {
                            updated[i] = { ...updated[i], completed: true };
                            break;
                        }
                    }
                    return updated;
                });
                // Store execution result
                if (data.result) {
                    setExecutionResults(prev => [...prev, data.result]);
                }
                break;

            case 'plan_ready':
                setCurrentThinking(null);
                addEntry({
                    type: 'system', timestamp,
                    message: 'Plan ready for review. Please approve to continue.',
                    systemType: 'info',
                });
                break;

            case 'plan_approved':
                addEntry({
                    type: 'system', timestamp,
                    message: 'Plan approved! Starting execution...',
                    systemType: 'success',
                });
                break;

            case 'error':
                setCurrentThinking(null);
                addEntry({
                    type: 'system', timestamp,
                    message: data.message || 'An error occurred',
                    systemType: 'error',
                });
                break;

            case 'complete':
                setCurrentThinking(null);
                if (data.success) {
                    addEntry({
                        type: 'system', timestamp,
                        message: 'Task completed successfully!',
                        systemType: 'success',
                    });
                }
                break;
        }
    }, [addEntry]);

    const handleEvent = useCallback((event: InteractiveEvent) => {
        const { event: eventType, data } = event;

        // Process agent conversation events
        processAgentEvent(event);

        switch (eventType) {
            case 'connected':
                if (data.conversation_id) {
                    setConversationId(data.conversation_id);
                    onConversationChange?.(data.conversation_id);
                    localStorage.setItem(conversationKey, data.conversation_id);
                    saveProcessingState(true, data.conversation_id);
                }
                break;

            case 'plan_ready':
                if (data.awaiting_approval && data.plan) {
                    setCurrentPlan(data.plan);
                    setAwaitingPlanApproval(true);
                    setCurrentThinking(null);
                }
                break;

            case 'plan_approved':
                setAwaitingPlanApproval(false);
                setCurrentPlan(null);
                break;

            case 'validation_result':
                if (data.validation) {
                    setValidationResult(data.validation);
                }
                break;

            case 'answer_chunk':
                if (data.chunk) {
                    setStreamingContent(prev => prev + data.chunk);
                }
                break;

            case 'complete':
                setIsStreaming(false);
                setIsLoading(false);
                setCurrentThinking(null);
                setAwaitingPlanApproval(false);
                setCurrentPlan(null);
                saveProcessingState(false, null);

                if (data.answer || data.success !== undefined) {
                    const assistantMessage: Message = {
                        id: `msg-${Date.now()}`,
                        role: 'assistant',
                        content: data.answer || (data.success ? 'Task completed successfully.' : 'Task failed.'),
                        timestamp: new Date(),
                        processingData: {
                            intent: data.intent,
                            plan: data.plan,
                            execution_results: data.execution_results,
                            validation: data.validation,
                            success: data.success,
                            error: data.error,
                            agent_activity: [...conversationEntries],
                        },
                    };
                    setMessages(prev => [...prev, assistantMessage]);
                    setStreamingContent('');
                    setValidationResult(data.validation || null);

                    // If there are code changes, show the review panel
                    if (data.execution_results?.length > 0) {
                        setPendingChanges(data.execution_results.map((r: any) => ({
                            file: r.file,
                            action: r.action,
                            content: r.content,
                            diff: r.diff,
                        })));
                        setShowChangesReview(true);
                    }
                }
                break;

            case 'error':
                setIsStreaming(false);
                setIsLoading(false);
                setCurrentThinking(null);
                saveProcessingState(false, null);
                setError(data.message || 'An error occurred');
                break;
        }
    }, [processAgentEvent, onConversationChange, conversationKey, saveProcessingState, conversationEntries]);

    // ============== SEND MESSAGE ==============
    const sendMessage = useCallback(async (messageText?: string) => {
        const text = messageText || input.trim();
        console.log('[ChatModule] sendMessage called with:', text);

        if (!text) {
            console.log('[ChatModule] No text to send');
            return;
        }

        if (isLoading) {
            console.log('[ChatModule] Already loading, skipping');
            return;
        }

        if (!projectId) {
            console.error('[ChatModule] No projectId provided');
            setError('No project selected');
            return;
        }

        // Reset state
        setError(null);
        setIsLoading(true);
        setIsStreaming(true);
        setStreamingContent('');
        clearEntries();
        setExecutionResults([]);
        setShowChangesReview(false);
        setPendingChanges([]);

        // Add user message
        const userMessage: Message = {
            id: `msg-${Date.now()}`,
            role: 'user',
            content: text,
            timestamp: new Date(),
        };
        setMessages(prev => [...prev, userMessage]);
        setInput('');

        try {
            abortControllerRef.current = new AbortController();
            const chatUrl = chatApi.getChatUrl(projectId);
            const authToken = localStorage.getItem('auth_token');

            // Debug: Log the full URL and check if API_URL is set correctly
            const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
            console.log('[ChatModule] API Base URL:', apiUrl);
            console.log('[ChatModule] Full Chat URL:', chatUrl);
            console.log('[ChatModule] Project ID:', projectId);
            console.log('[ChatModule] Auth token exists:', !!authToken);
            console.log('[ChatModule] Request body:', {
                message: text,
                conversation_id: conversationId,
                interactive_mode: true,
                require_plan_approval: requirePlanApproval,
            });

            const response = await fetch(chatUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${authToken}`,
                },
                body: JSON.stringify({
                    message: text,
                    conversation_id: conversationId,
                    interactive_mode: true,
                    require_plan_approval: requirePlanApproval,
                }),
                signal: abortControllerRef.current.signal,
            });

            console.log('[ChatModule] Response status:', response.status);

            if (!response.ok) {
                const errorText = await response.text();
                console.error('[ChatModule] Error response:', errorText);

                // Provide helpful error messages based on status
                if (response.status === 404) {
                    throw new Error(`Chat endpoint not found. Make sure your backend has the POST /projects/{project_id}/chat endpoint implemented.`);
                } else if (response.status === 401) {
                    throw new Error(`Authentication failed. Please log in again.`);
                } else if (response.status === 403) {
                    throw new Error(`Access denied. You may not have permission for this project.`);
                } else {
                    throw new Error(`API error (${response.status}): ${errorText}`);
                }
            }

            const reader = response.body?.getReader();
            if (!reader) throw new Error('No response body');

            const decoder = new TextDecoder();
            let buffer = '';

            console.log('[ChatModule] Starting to read stream...');

            while (true) {
                const { done, value } = await reader.read();
                if (done) {
                    console.log('[ChatModule] Stream complete');
                    break;
                }

                buffer += decoder.decode(value, { stream: true });
                const events = parseSSEChunk(buffer);
                buffer = '';

                for (const event of events) {
                    console.log('[ChatModule] Event:', event.event, event.data);
                    handleEvent(event);
                }
            }
        } catch (err: any) {
            if (err.name !== 'AbortError') {
                console.error('[ChatModule] Chat error:', err);
                setError(getErrorMessage(err));
                setIsLoading(false);
                setIsStreaming(false);
                saveProcessingState(false, null);
            }
        }
    }, [input, isLoading, projectId, conversationId, requirePlanApproval, parseSSEChunk, handleEvent, clearEntries, saveProcessingState]);

    // ============== PLAN APPROVAL ==============
    const handlePlanApproval = useCallback(async (modifiedPlan?: Plan) => {
        if (!conversationId) return;

        setIsPlanApprovalLoading(true);
        try {
            await chatApi.approvePlan(projectId, {
                conversation_id: conversationId,
                approved: true,
                modified_plan: modifiedPlan,
            });
            setAwaitingPlanApproval(false);
            setCurrentPlan(null);
        } catch (err) {
            console.error('Plan approval error:', err);
            setError(getErrorMessage(err));
        } finally {
            setIsPlanApprovalLoading(false);
        }
    }, [conversationId, projectId]);

    const handlePlanRejection = useCallback(async (reason?: string) => {
        if (!conversationId) return;

        setIsPlanApprovalLoading(true);
        try {
            await chatApi.approvePlan(projectId, {
                conversation_id: conversationId,
                approved: false,
                rejection_reason: reason,
            });
            setAwaitingPlanApproval(false);
            setCurrentPlan(null);
            setIsLoading(false);
            setIsStreaming(false);
            saveProcessingState(false, null);
        } catch (err) {
            console.error('Plan rejection error:', err);
            setError(getErrorMessage(err));
        } finally {
            setIsPlanApprovalLoading(false);
        }
    }, [conversationId, projectId, saveProcessingState]);

    // ============== NEW CHAT ==============
    const startNewChat = useCallback(() => {
        // Abort any ongoing request
        abortControllerRef.current?.abort();

        setMessages([]);
        setConversationId(null);
        setInput('');
        setIsLoading(false);
        setIsStreaming(false);
        setStreamingContent('');
        setError(null);
        setAwaitingPlanApproval(false);
        setCurrentPlan(null);
        setValidationResult(null);
        setExecutionResults([]);
        setShowChangesReview(false);
        setPendingChanges([]);
        clearEntries();
        setCurrentThinking(null);

        localStorage.removeItem(conversationKey);
        localStorage.removeItem(processingStateKey);
        onConversationChange?.(null);

        inputRef.current?.focus();
    }, [conversationKey, processingStateKey, clearEntries, onConversationChange]);

    // Expose methods to parent
    useImperativeHandle(ref, () => ({
        startNewChat,
        sendMessage,
    }), [startNewChat, sendMessage]);

    // ============== RENDER ==============
    if (!mounted) {
        return (
            <div className="flex h-full items-center justify-center bg-[var(--color-bg-primary)]">
                <Loader2 className="h-6 w-6 animate-spin text-[var(--color-text-muted)]" />
                <span className="ml-2 text-sm text-[var(--color-text-muted)]">Initializing...</span>
            </div>
        );
    }

    if (!projectId) {
        return (
            <div className="flex h-full items-center justify-center bg-[var(--color-bg-primary)]">
                <div className="text-center">
                    <AlertCircle className="h-12 w-12 text-amber-400 mx-auto mb-4" />
                    <p className="text-[var(--color-text-muted)]">No project selected</p>
                    <p className="text-sm text-[var(--color-text-dimmer)] mt-2">Please select a project to start chatting</p>
                </div>
            </div>
        );
    }

    return (
        <div className={`flex flex-col h-full bg-[var(--color-bg-primary)] ${className}`}>
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-2 border-b border-[var(--color-border-subtle)] bg-[var(--color-bg-surface)]">
                <div className="flex items-center gap-2">
          <span className="flex items-center gap-1.5 px-2 py-1 rounded-lg bg-gradient-to-r from-purple-500/20 to-blue-500/20 text-purple-400 text-sm">
            <Sparkles className="h-4 w-4" />
            <span className="hidden sm:inline">Multi-Agent Mode</span>
          </span>
                    <button
                        onClick={() => setShowAgentTimeline(!showAgentTimeline)}
                        className="p-1.5 rounded-lg hover:bg-[var(--color-bg-hover)] text-[var(--color-text-muted)] transition-colors"
                        title={showAgentTimeline ? 'Hide agent activity' : 'Show agent activity'}
                    >
                        {showAgentTimeline ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                    </button>
                </div>
                <button
                    onClick={startNewChat}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-bg-hover)] transition-colors"
                >
                    <Plus className="h-4 w-4" />
                    <span className="hidden sm:inline">New Chat</span>
                </button>
            </div>

            {/* Messages Area */}
            <div className="flex-1 overflow-y-auto">
                {isLoadingMessages ? (
                    <div className="flex items-center justify-center h-full">
                        <Loader2 className="h-6 w-6 animate-spin text-[var(--color-text-muted)]" />
                        <span className="ml-2 text-[var(--color-text-muted)]">Loading messages...</span>
                    </div>
                ) : messages.length === 0 && !isStreaming && !isLoading ? (
                    <WelcomeScreen onExampleClick={sendMessage} />
                ) : (
                    <div className="p-4 space-y-4">
                        {messages.map((message) => (
                            <MessageBubble key={message.id} message={message} showAgentTimeline={showAgentTimeline} />
                        ))}

                        {/* Loading indicator when waiting for response */}
                        {isLoading && !streamingContent && conversationEntries.length === 0 && (
                            <div className="flex justify-start">
                                <div className="max-w-[85%] rounded-xl bg-[var(--color-bg-elevated)] border border-[var(--color-border-subtle)] p-4">
                                    <div className="flex items-center gap-2 text-[var(--color-text-muted)]">
                                        <Loader2 className="h-4 w-4 animate-spin" />
                                        <span className="text-sm">Connecting to AI agents...</span>
                                    </div>
                                </div>
                            </div>
                        )}

                        {/* Streaming content */}
                        {isStreaming && streamingContent && (
                            <div className="flex justify-start">
                                <div className="max-w-[85%] rounded-xl bg-[var(--color-bg-elevated)] border border-[var(--color-border-subtle)] p-4">
                                    <ReactMarkdown remarkPlugins={[remarkGfm]} className="prose prose-invert prose-sm max-w-none">
                                        {streamingContent}
                                    </ReactMarkdown>
                                </div>
                            </div>
                        )}

                        {/* Agent Timeline */}
                        {showAgentTimeline && (conversationEntries.length > 0 || currentThinking) && (
                            <AgentTimeline entries={conversationEntries} currentThinking={currentThinking} />
                        )}

                        {/* Plan Approval */}
                        <AnimatePresence>
                            {awaitingPlanApproval && currentPlan && (
                                <PlanApprovalCard
                                    plan={currentPlan}
                                    isLoading={isPlanApprovalLoading}
                                    onApprove={handlePlanApproval}
                                    onReject={handlePlanRejection}
                                    onModify={(modifiedPlan) => handlePlanApproval(modifiedPlan)}
                                />
                            )}
                        </AnimatePresence>

                        {/* Changes Review */}
                        <AnimatePresence>
                            {showChangesReview && pendingChanges.length > 0 && (
                                <ChangesReviewPanel
                                    projectId={projectId}
                                    conversationId={conversationId}
                                    changes={pendingChanges}
                                    onClose={() => setShowChangesReview(false)}
                                />
                            )}
                        </AnimatePresence>

                        {/* Error */}
                        {error && (
                            <div className="flex items-center gap-2 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
                                <AlertCircle className="h-4 w-4 flex-shrink-0" />
                                <span>{error}</span>
                                <button onClick={() => setError(null)} className="ml-auto hover:text-red-300">
                                    <X className="h-4 w-4" />
                                </button>
                            </div>
                        )}

                        <div ref={messagesEndRef} />
                    </div>
                )}
            </div>

            {/* Input Area */}
            <div className="p-4 border-t border-[var(--color-border-subtle)] bg-[var(--color-bg-surface)]">
                <div className="flex items-end gap-2">
          <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      sendMessage();
                  }
              }}
              placeholder={awaitingPlanApproval ? "Waiting for plan approval..." : "Describe what you want to build..."}
              disabled={isLoading || awaitingPlanApproval}
              rows={1}
              className="flex-1 resize-none rounded-xl bg-[var(--color-bg-elevated)] border border-[var(--color-border-subtle)] px-4 py-3 text-sm text-[var(--color-text-primary)] placeholder-[var(--color-text-muted)] focus:outline-none focus:border-[var(--color-primary)] disabled:opacity-50 disabled:cursor-not-allowed"
              style={{ minHeight: '44px', maxHeight: '120px' }}
          />
                    <button
                        onClick={() => sendMessage()}
                        disabled={!input.trim() || isLoading || awaitingPlanApproval}
                        className="flex items-center justify-center h-11 w-11 rounded-xl bg-[var(--color-primary)] text-white hover:bg-[var(--color-primary-hover)] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    >
                        {isLoading ? <Loader2 className="h-5 w-5 animate-spin" /> : <Send className="h-5 w-5" />}
                    </button>
                </div>
            </div>
        </div>
    );
});

// ============== SUB-COMPONENTS ==============

function WelcomeScreen({ onExampleClick }: { onExampleClick: (msg: string) => void }) {
    const examples = [
        "Create a new Product model with name, price, and category relationships",
        "Add authentication middleware to the API routes",
        "Generate CRUD controller for Order management",
        "Create a migration for user subscriptions table",
    ];

    const handleExampleClick = (example: string) => {
        console.log('[WelcomeScreen] Example clicked:', example);
        onExampleClick(example);
    };

    return (
        <div className="flex flex-col items-center justify-center h-full p-8 text-center">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-purple-500 to-blue-500 flex items-center justify-center mb-6">
                <Bot className="h-8 w-8 text-white" />
            </div>
            <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-2">
                Maestro AI Assistant
            </h2>
            <p className="text-[var(--color-text-muted)] mb-8 max-w-md">
                I can help you generate Laravel code, create models, controllers, migrations, and more.
                Watch the agents collaborate in real-time!
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 max-w-2xl w-full">
                {examples.map((example, i) => (
                    <button
                        key={i}
                        onClick={() => handleExampleClick(example)}
                        className="p-4 rounded-xl bg-[var(--color-bg-elevated)] border border-[var(--color-border-subtle)] text-left text-sm text-[var(--color-text-secondary)] hover:border-[var(--color-primary)] hover:bg-[var(--color-bg-hover)] transition-all"
                    >
                        {example}
                    </button>
                ))}
            </div>
        </div>
    );
}

function MessageBubble({ message, showAgentTimeline }: { message: Message; showAgentTimeline: boolean }) {
    const [copied, setCopied] = useState(false);
    const isUser = message.role === 'user';

    const handleCopy = async () => {
        await navigator.clipboard.writeText(message.content);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    return (
        <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[85%] rounded-xl p-4 ${
                isUser
                    ? 'bg-[var(--color-primary)] text-white'
                    : 'bg-[var(--color-bg-elevated)] border border-[var(--color-border-subtle)] text-[var(--color-text-primary)]'
            }`}>
                <div className={`prose prose-sm max-w-none ${isUser ? 'prose-invert' : 'prose-invert'}`}>
                    <ReactMarkdown
                        remarkPlugins={[remarkGfm]}
                        components={{
                            code({ node, className, children, ...props }) {
                                const match = /language-(\w+)/.exec(className || '');
                                const inline = !match;
                                return inline ? (
                                    <code className="px-1.5 py-0.5 rounded bg-black/20 text-sm font-mono" {...props}>
                                        {children}
                                    </code>
                                ) : (
                                    <pre className="rounded-lg bg-black/30 p-3 text-sm overflow-x-auto my-2">
                    <code className={`language-${match[1]} font-mono`}>
                      {String(children).replace(/\n$/, '')}
                    </code>
                  </pre>
                                );
                            },
                        }}
                    >
                        {message.content}
                    </ReactMarkdown>
                </div>

                {!isUser && (
                    <div className="flex items-center justify-end gap-2 mt-3 pt-2 border-t border-[var(--color-border-subtle)]">
                        <button
                            onClick={handleCopy}
                            className="p-1.5 rounded-lg hover:bg-[var(--color-bg-hover)] text-[var(--color-text-muted)] transition-colors"
                            title="Copy message"
                        >
                            {copied ? <Check className="h-4 w-4 text-green-400" /> : <Copy className="h-4 w-4" />}
                        </button>
                    </div>
                )}

                {/* Show stored agent activity for assistant messages */}
                {!isUser && showAgentTimeline && message.processingData?.agent_activity?.length > 0 && (
                    <details className="mt-3 pt-3 border-t border-[var(--color-border-subtle)]">
                        <summary className="cursor-pointer text-xs text-[var(--color-text-muted)] hover:text-[var(--color-text-secondary)]">
                            View agent activity ({message.processingData.agent_activity.length} events)
                        </summary>
                        <div className="mt-2">
                            <AgentTimeline entries={message.processingData.agent_activity} currentThinking={null} compact />
                        </div>
                    </details>
                )}
            </div>
        </div>
    );
}

export default ChatModule;