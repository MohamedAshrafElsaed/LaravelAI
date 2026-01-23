'use client';

import React, {forwardRef, useCallback, useEffect, useImperativeHandle, useRef, useState} from 'react';
import {AnimatePresence, motion} from 'framer-motion';
import {
    AlertCircle,
    ArrowRight,
    Bot,
    Check,
    CheckCircle,
    ChevronDown,
    ChevronRight,
    FileCode,
    Loader2,
    Plus,
    Send,
    Sparkles,
    X,
    XCircle
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {Prism as SyntaxHighlighter} from 'react-syntax-highlighter';
import {oneDark} from 'react-syntax-highlighter/dist/esm/styles/prism';

import {chatApi, getErrorMessage} from '@/lib/api';
import type {
    AgentThinkingState,
    AgentType,
    ExecutionResult,
    GitChangeFile,
    InteractiveEvent,
    Message,
    Plan,
    PlanStep,
    StreamingFile,
    ValidationResult
} from './types';
import {AGENT_CONFIG} from './AgentBadge';
import {ChangesReviewPanel} from './ChangesReviewPanel';

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

const LANG_MAP: Record<string, string> = {
    php: 'php', ts: 'typescript', tsx: 'tsx', js: 'javascript', jsx: 'jsx',
    json: 'json', md: 'markdown', css: 'css', scss: 'scss', html: 'html',
    blade: 'php', vue: 'html', yaml: 'yaml', yml: 'yaml', sql: 'sql', sh: 'bash',
};

function getLanguage(filePath: string): string {
    const ext = filePath.split('.').pop()?.toLowerCase() || 'php';
    return LANG_MAP[ext] || 'php';
}

// ============== AGENT CONFIG ==============
const AGENTS: Record<AgentType, { name: string; emoji: string; color: string; bg: string }> = {
    conductor: {name: 'Conductor', emoji: '🎭', color: 'text-purple-400', bg: 'bg-purple-500/10 border-purple-500/30'},
    nova: {name: 'Nova', emoji: '🎯', color: 'text-blue-400', bg: 'bg-blue-500/10 border-blue-500/30'},
    scout: {name: 'Scout', emoji: '🔍', color: 'text-cyan-400', bg: 'bg-cyan-500/10 border-cyan-500/30'},
    blueprint: {name: 'Blueprint', emoji: '📋', color: 'text-indigo-400', bg: 'bg-indigo-500/10 border-indigo-500/30'},
    forge: {name: 'Forge', emoji: '⚒️', color: 'text-orange-400', bg: 'bg-orange-500/10 border-orange-500/30'},
    guardian: {name: 'Guardian', emoji: '🛡️', color: 'text-emerald-400', bg: 'bg-emerald-500/10 border-emerald-500/30'},
};

export const ChatModule = forwardRef<ChatModuleRef, ChatModuleProps>(function ChatModule(
    {projectId, initialConversationId, onConversationChange, requirePlanApproval = true, className = ''},
    ref
) {
    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [isStreaming, setIsStreaming] = useState(false);
    const [streamingContent, setStreamingContent] = useState('');
    const [conversationId, setConversationId] = useState<string | null>(initialConversationId || null);
    const [error, setError] = useState<string | null>(null);
    const [isLoadingMessages, setIsLoadingMessages] = useState(false);
    const [mounted, setMounted] = useState(false);

    // All chat items (agent messages, plan steps, etc.)
    const [chatItems, setChatItems] = useState<ChatItem[]>([]);
    const [currentThinking, setCurrentThinking] = useState<AgentThinkingState | null>(null);
    const itemIdRef = useRef(0);

    // Plan state
    const [awaitingPlanApproval, setAwaitingPlanApproval] = useState(false);
    const [currentPlan, setCurrentPlan] = useState<Plan | null>(null);
    const [isPlanApprovalLoading, setIsPlanApprovalLoading] = useState(false);

    // Streaming files
    const [streamingFiles, setStreamingFiles] = useState<Map<number, StreamingFile>>(new Map());
    const [completedArtifacts, setCompletedArtifacts] = useState<ExecutionResult[]>([]);

    // Other state
    const [validationResult, setValidationResult] = useState<ValidationResult | null>(null);
    const [executionResults, setExecutionResults] = useState<any[]>([]);
    const [showChangesReview, setShowChangesReview] = useState(false);
    const [pendingChanges, setPendingChanges] = useState<GitChangeFile[]>([]);

    const messagesEndRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLTextAreaElement>(null);
    const abortControllerRef = useRef<AbortController | null>(null);

    const conversationKey = `conversation_${projectId}`;
    const processingStateKey = `chat_processing_${projectId}`;

    // ============== CHAT ITEM TYPE ==============
    type ChatItem = {
        id: string;
        type: 'agent_message' | 'agent_handoff' | 'plan_step' | 'system' | 'step_execution' | 'thinking';
        timestamp: string;
        agent?: AgentType;
        toAgent?: AgentType;
        message?: string;
        messageType?: string;
        step?: PlanStep;
        completed?: boolean;
        systemType?: 'info' | 'success' | 'warning' | 'error';
    };

    const generateId = useCallback(() => {
        itemIdRef.current += 1;
        return `item-${itemIdRef.current}`;
    }, []);

    const addChatItem = useCallback((item: Omit<ChatItem, 'id'>) => {
        setChatItems(prev => [...prev, {...item, id: generateId()}]);
    }, [generateId]);

    const clearChatItems = useCallback(() => {
        setChatItems([]);
        setCurrentThinking(null);
        setStreamingFiles(new Map());
        setCompletedArtifacts([]);
        itemIdRef.current = 0;
    }, []);

    const scrollToBottom = useCallback(() => {
        messagesEndRef.current?.scrollIntoView({behavior: 'smooth'});
    }, []);

    const saveProcessingState = useCallback((isProcessing: boolean, convId: string | null) => {
        if (typeof window === 'undefined') return;
        if (isProcessing && convId) {
            localStorage.setItem(processingStateKey, JSON.stringify({
                isLoading: true,
                conversationId: convId,
                timestamp: Date.now()
            }));
        } else {
            localStorage.removeItem(processingStateKey);
        }
    }, [processingStateKey]);

    useEffect(() => {
        setMounted(true);
        if (typeof window !== 'undefined') {
            if (initialConversationId) {
                loadMessages(initialConversationId);
            } else {
                const savedConvId = localStorage.getItem(conversationKey);
                if (savedConvId) loadMessages(savedConvId);
            }
        }
    }, [projectId]);

    useEffect(() => {
        if (mounted && initialConversationId && initialConversationId !== conversationId) {
            loadMessages(initialConversationId);
        }
    }, [initialConversationId, mounted]);

    useEffect(() => {
        scrollToBottom();
    }, [messages, chatItems, streamingFiles, completedArtifacts, currentThinking, scrollToBottom]);

    const loadMessages = useCallback(async (convId: string) => {
        setIsLoadingMessages(true);
        setError(null);
        clearChatItems();

        try {
            const response = await chatApi.getMessages(projectId, convId);
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

            // Restore artifacts
            const lastAssistantMsg = [...loadedMessages].reverse().find(m => m.role === 'assistant');
            if (lastAssistantMsg?.processingData?.execution_results) {
                const restoredArtifacts: ExecutionResult[] = lastAssistantMsg.processingData.execution_results
                    .filter((r: any) => r.success && r.content)
                    .map((r: any) => ({
                        file: r.file,
                        action: r.action,
                        success: r.success,
                        content: r.content,
                        diff: r.diff,
                        lines_changed: r.content?.split('\n').length || 0
                    }));
                setCompletedArtifacts(restoredArtifacts);
            }
        } catch (err: any) {
            if (err?.status === 404 || err?.response?.status === 404) {
                localStorage.removeItem(conversationKey);
                setMessages([]);
                setConversationId(null);
            } else {
                setError(getErrorMessage(err));
            }
        } finally {
            setIsLoadingMessages(false);
        }
    }, [projectId, onConversationChange, saveProcessingState, conversationKey, clearChatItems]);

    const parseSSEChunk = useCallback((chunk: string): InteractiveEvent[] => {
        const events: InteractiveEvent[] = [];
        const lines = chunk.split('\n');
        let currentEvent: string | null = null;
        for (const line of lines) {
            if (line.startsWith('event:')) currentEvent = line.substring(6).trim();
            else if (line.startsWith('data:') && currentEvent) {
                try {
                    events.push({event: currentEvent as any, data: JSON.parse(line.substring(5).trim())});
                } catch (e) {
                }
                currentEvent = null;
            }
        }
        return events;
    }, []);

    const processAgentEvent = useCallback((event: InteractiveEvent) => {
        const {event: eventType, data} = event;
        const timestamp = data.timestamp || new Date().toISOString();

        switch (eventType) {
            case 'agent_message':
                addChatItem({
                    type: 'agent_message',
                    timestamp,
                    agent: data.from_agent,
                    toAgent: data.to_agent,
                    message: data.message,
                    messageType: data.message_type
                });
                break;
            case 'agent_handoff':
                addChatItem({
                    type: 'agent_handoff',
                    timestamp,
                    agent: data.from_agent,
                    toAgent: data.to_agent,
                    message: data.message
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
                    progress: data.progress || 0
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
                    progress: 0
                });
                addChatItem({
                    type: 'agent_message',
                    timestamp,
                    agent: data.agent,
                    message: data.message,
                    messageType: 'greeting'
                });
                break;
            case 'intent_analyzed':
            case 'context_retrieved':
            case 'execution_completed':
            case 'validation_result':
                setCurrentThinking(null);
                addChatItem({
                    type: 'agent_message',
                    timestamp,
                    agent: data.agent,
                    message: data.message,
                    messageType: 'completion'
                });
                break;
            case 'plan_step_added':
                if (data.step) {
                    addChatItem({type: 'plan_step', timestamp, agent: 'blueprint', step: data.step});
                }
                break;
            case 'step_code_chunk':
                setStreamingFiles(prev => {
                    const next = new Map(prev);
                    const existing = next.get(data.step_index) || {
                        stepIndex: data.step_index,
                        file: data.file,
                        content: '',
                        totalLength: data.total_length || 0,
                        done: false,
                        action: data.action || 'create'
                    };
                    if (data.done) {
                        next.delete(data.step_index);
                        const finalContent = data.content || existing.content;
                        setCompletedArtifacts(artifacts => [...artifacts, {
                            file: data.file,
                            action: data.action || 'create',
                            success: true,
                            content: finalContent,
                            lines_changed: finalContent.split('\n').length
                        }]);
                    } else {
                        next.set(data.step_index, {
                            ...existing,
                            content: existing.content + (data.chunk || ''),
                            totalLength: data.total_length || existing.totalLength
                        });
                    }
                    return next;
                });
                break;
            case 'step_started':
                setCurrentThinking({
                    agent: AGENT_CONFIG.forge,
                    thought: data.step?.description || 'Working...',
                    actionType: data.step?.action,
                    filePath: data.step?.file,
                    progress: 0
                });
                addChatItem({
                    type: 'step_execution',
                    timestamp,
                    agent: 'forge',
                    step: data.step,
                    completed: false,
                    message: `Working on: ${data.step?.file}`
                });
                break;
            case 'step_completed':
                setCurrentThinking(null);
                setChatItems(prev => {
                    const updated = [...prev];
                    for (let i = updated.length - 1; i >= 0; i--) {
                        if (updated[i].type === 'step_execution' && !updated[i].completed) {
                            updated[i] = {...updated[i], completed: true};
                            break;
                        }
                    }
                    return updated;
                });
                if (data.result) setExecutionResults(prev => [...prev, data.result]);
                break;
            case 'plan_ready':
                setCurrentThinking(null);
                addChatItem({type: 'system', timestamp, message: 'Plan ready for review', systemType: 'info'});
                break;
            case 'plan_approved':
                addChatItem({
                    type: 'system',
                    timestamp,
                    message: 'Plan approved! Starting execution...',
                    systemType: 'success'
                });
                break;
            case 'error':
                setCurrentThinking(null);
                addChatItem({
                    type: 'system',
                    timestamp,
                    message: data.message || 'An error occurred',
                    systemType: 'error'
                });
                break;
            case 'complete':
                setCurrentThinking(null);
                if (data.success) addChatItem({
                    type: 'system',
                    timestamp,
                    message: 'Task completed successfully!',
                    systemType: 'success'
                });
                break;
        }
    }, [addChatItem]);

    const handleEvent = useCallback((event: InteractiveEvent) => {
        const {event: eventType, data} = event;
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
                }
                break;
            case 'plan_approved':
                setAwaitingPlanApproval(false);
                setCurrentPlan(null);
                break;
            case 'answer_chunk':
                if (data.chunk) setStreamingContent(prev => prev + data.chunk);
                break;
            case 'complete':
                setIsStreaming(false);
                setIsLoading(false);
                setAwaitingPlanApproval(false);
                setCurrentPlan(null);
                saveProcessingState(false, null);
                if (data.answer || data.success !== undefined) {
                    setMessages(prev => [...prev, {
                        id: `msg-${Date.now()}`,
                        role: 'assistant',
                        content: data.answer || (data.success ? 'Task completed.' : 'Task failed.'),
                        timestamp: new Date(),
                        processingData: {
                            intent: data.intent,
                            plan: data.plan,
                            execution_results: data.execution_results,
                            validation: data.validation,
                            success: data.success,
                            error: data.error
                        },
                    }]);
                    setStreamingContent('');
                    if (data.execution_results?.length > 0) {
                        setPendingChanges(data.execution_results.map((r: any) => ({
                            file: r.file,
                            action: r.action,
                            content: r.content,
                            diff: r.diff
                        })));
                        setShowChangesReview(true);
                    }
                }
                break;
            case 'error':
                setIsStreaming(false);
                setIsLoading(false);
                saveProcessingState(false, null);
                setError(data.message || 'An error occurred');
                break;
        }
    }, [processAgentEvent, onConversationChange, conversationKey, saveProcessingState]);

    const sendMessage = useCallback(async (messageText?: string) => {
        const text = messageText || input.trim();
        if (!text || isLoading || !projectId) return;

        setError(null);
        setIsLoading(true);
        setIsStreaming(true);
        setStreamingContent('');
        clearChatItems();
        setExecutionResults([]);
        setCompletedArtifacts([]);
        setShowChangesReview(false);
        setPendingChanges([]);

        setMessages(prev => [...prev, {id: `msg-${Date.now()}`, role: 'user', content: text, timestamp: new Date()}]);
        setInput('');

        try {
            abortControllerRef.current = new AbortController();
            const response = await fetch(chatApi.getChatUrl(projectId), {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
                },
                body: JSON.stringify({
                    message: text,
                    conversation_id: conversationId,
                    interactive_mode: true,
                    require_plan_approval: requirePlanApproval
                }),
                signal: abortControllerRef.current.signal,
            });

            if (!response.ok) throw new Error(`API error (${response.status})`);

            const reader = response.body?.getReader();
            if (!reader) throw new Error('No response body');

            const decoder = new TextDecoder();
            let buffer = '';
            while (true) {
                const {done, value} = await reader.read();
                if (done) break;
                buffer += decoder.decode(value, {stream: true});
                for (const event of parseSSEChunk(buffer)) handleEvent(event);
                buffer = '';
            }
        } catch (err: any) {
            if (err.name !== 'AbortError') {
                setError(getErrorMessage(err));
                setIsLoading(false);
                setIsStreaming(false);
            }
        }
    }, [input, isLoading, projectId, conversationId, requirePlanApproval, parseSSEChunk, handleEvent, clearChatItems]);

    const handlePlanApproval = useCallback(async (modifiedPlan?: Plan) => {
        if (!conversationId) return;
        setIsPlanApprovalLoading(true);
        try {
            await chatApi.approvePlan(projectId, {
                conversation_id: conversationId,
                approved: true,
                modified_plan: modifiedPlan
            });
            setAwaitingPlanApproval(false);
            setCurrentPlan(null);
        } catch (err) {
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
                rejection_reason: reason
            });
            setAwaitingPlanApproval(false);
            setCurrentPlan(null);
            setIsLoading(false);
            setIsStreaming(false);
        } catch (err) {
            setError(getErrorMessage(err));
        } finally {
            setIsPlanApprovalLoading(false);
        }
    }, [conversationId, projectId]);

    const startNewChat = useCallback(() => {
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
        clearChatItems();
        localStorage.removeItem(conversationKey);
        onConversationChange?.(null);
        inputRef.current?.focus();
    }, [conversationKey, clearChatItems, onConversationChange]);

    useImperativeHandle(ref, () => ({startNewChat, sendMessage}), [startNewChat, sendMessage]);

    if (!mounted) return <div className="flex h-full items-center justify-center bg-[var(--color-bg-primary)]"><Loader2
        className="h-6 w-6 animate-spin"/></div>;
    if (!projectId) return <div className="flex h-full items-center justify-center"><AlertCircle
        className="h-12 w-12 text-amber-400"/></div>;

    return (
        <div className={`flex flex-col h-full bg-[var(--color-bg-primary)] ${className}`}>
            {/* Header */}
            <div
                className="flex items-center justify-between px-4 py-2 border-b border-[var(--color-border-subtle)] bg-[var(--color-bg-surface)]">
                <span
                    className="flex items-center gap-1.5 px-2 py-1 rounded-lg bg-gradient-to-r from-purple-500/20 to-blue-500/20 text-purple-400 text-sm">
                    <Sparkles className="h-4 w-4"/><span className="hidden sm:inline">Multi-Agent Mode</span>
                </span>
                <button onClick={startNewChat}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm text-[var(--color-text-muted)] hover:bg-[var(--color-bg-hover)]">
                    <Plus className="h-4 w-4"/><span className="hidden sm:inline">New Chat</span>
                </button>
            </div>

            {/* Messages Area */}
            <div className="flex-1 overflow-y-auto">
                {isLoadingMessages ? (
                    <div className="flex items-center justify-center h-full"><Loader2 className="h-6 w-6 animate-spin"/>
                    </div>
                ) : messages.length === 0 && !isLoading ? (
                    <WelcomeScreen onExampleClick={sendMessage}/>
                ) : (
                    <div className="p-4 space-y-3">
                        {/* User/Assistant Messages */}
                        {messages.map((msg) => <MessageBubble key={msg.id} message={msg}/>)}

                        {/* Loading */}
                        {isLoading && chatItems.length === 0 && (
                            <div className="flex justify-start">
                                <div
                                    className="rounded-xl bg-[var(--color-bg-elevated)] border border-[var(--color-border-subtle)] p-3">
                                    <div className="flex items-center gap-2 text-[var(--color-text-muted)]">
                                        <Loader2 className="h-4 w-4 animate-spin"/><span
                                        className="text-sm">Connecting...</span>
                                    </div>
                                </div>
                            </div>
                        )}

                        {/* Chat Items (Agent messages, plan steps, etc.) */}
                        {chatItems.map((item) => <ChatItemBubble key={item.id} item={item}/>)}

                        {/* Current Thinking */}
                        {currentThinking && <ThinkingBubble thinking={currentThinking}/>}

                        {/* Plan Approval (inline) */}
                        {awaitingPlanApproval && currentPlan && (
                            <PlanApprovalBubble
                                plan={currentPlan}
                                isLoading={isPlanApprovalLoading}
                                onApprove={() => handlePlanApproval()}
                                onReject={() => handlePlanRejection()}
                            />
                        )}

                        {/* Streaming Files */}
                        {Array.from(streamingFiles.values()).map((sf) => <StreamingFileBubble
                            key={`sf-${sf.stepIndex}`} {...sf}/>)}

                        {/* Completed Artifacts */}
                        {completedArtifacts.map((artifact, i) => <FileArtifactBubble key={`art-${i}`}
                                                                                     result={artifact}/>)}

                        {/* Artifacts Summary Panel */}
                        {completedArtifacts.length > 1 && !isLoading && (
                            <ArtifactsSummaryPanel artifacts={completedArtifacts} />
                        )}

                        {/* Streaming Content */}
                        {streamingContent && (
                            <div className="flex justify-start">
                                <div className="max-w-[85%] rounded-xl bg-[var(--color-bg-elevated)] border border-[var(--color-border-subtle)] p-4">
                                    <div className="prose prose-invert prose-sm max-w-none">
                                        <ReactMarkdown remarkPlugins={[remarkGfm]}>{streamingContent}</ReactMarkdown>
                                    </div>
                                </div>
                            </div>
                        )}

                        {/* Changes Review */}
                        <AnimatePresence>
                            {showChangesReview && pendingChanges.length > 0 && (
                                <ChangesReviewPanel projectId={projectId} conversationId={conversationId}
                                                    changes={pendingChanges}
                                                    onClose={() => setShowChangesReview(false)}/>
                            )}
                        </AnimatePresence>

                        {/* Error */}
                        {error && (
                            <div
                                className="flex items-center gap-2 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
                                <AlertCircle className="h-4 w-4"/><span>{error}</span>
                                <button onClick={() => setError(null)} className="ml-auto"><X className="h-4 w-4"/>
                                </button>
                            </div>
                        )}

                        <div ref={messagesEndRef}/>
                    </div>
                )}
            </div>

            {/* Input */}
            <div className="p-4 border-t border-[var(--color-border-subtle)] bg-[var(--color-bg-surface)]">
                <div className="flex items-end gap-2">
                    <textarea ref={inputRef} value={input} onChange={(e) => setInput(e.target.value)}
                              onKeyDown={(e) => {
                                  if (e.key === 'Enter' && !e.shiftKey) {
                                      e.preventDefault();
                                      sendMessage();
                                  }
                              }}
                              placeholder={awaitingPlanApproval ? "Waiting for plan approval..." : "Describe what you want to build..."}
                              disabled={isLoading || awaitingPlanApproval} rows={1}
                              className="flex-1 resize-none rounded-xl bg-[var(--color-bg-elevated)] border border-[var(--color-border-subtle)] px-4 py-3 text-sm focus:outline-none focus:border-[var(--color-primary)] disabled:opacity-50"
                              style={{minHeight: '44px', maxHeight: '120px'}}/>
                    <button onClick={() => sendMessage()} disabled={!input.trim() || isLoading || awaitingPlanApproval}
                            className="h-11 w-11 rounded-xl bg-[var(--color-primary)] text-white disabled:opacity-50 flex items-center justify-center">
                        {isLoading ? <Loader2 className="h-5 w-5 animate-spin"/> : <Send className="h-5 w-5"/>}
                    </button>
                </div>
            </div>
        </div>
    );
});

// ============== SUB COMPONENTS ==============

function WelcomeScreen({onExampleClick}: { onExampleClick: (msg: string) => void }) {
    const examples = ["Create a new Product model with name, price, and category relationships", "Add authentication middleware to the API routes", "Generate CRUD controller for Order management", "Create a migration for user subscriptions table"];
    return (
        <div className="flex flex-col items-center justify-center h-full p-8 text-center">
            <div
                className="w-16 h-16 rounded-2xl bg-gradient-to-br from-purple-500 to-blue-500 flex items-center justify-center mb-6">
                <Bot className="h-8 w-8 text-white"/></div>
            <h2 className="text-xl font-semibold mb-2">Maestro AI Assistant</h2>
            <p className="text-[var(--color-text-muted)] mb-8 max-w-md">Watch the agents collaborate in real-time!</p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 max-w-2xl w-full">
                {examples.map((ex, i) => <button key={i} onClick={() => onExampleClick(ex)}
                                                 className="p-4 rounded-xl bg-[var(--color-bg-elevated)] border border-[var(--color-border-subtle)] text-left text-sm hover:border-[var(--color-primary)]">{ex}</button>)}
            </div>
        </div>
    );
}

function MessageBubble({message}: { message: Message }) {
    const isUser = message.role === 'user';
    return (
        <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
            <div
                className={`max-w-[85%] rounded-xl p-4 ${isUser ? 'bg-[var(--color-primary)] text-white' : 'bg-[var(--color-bg-elevated)] border border-[var(--color-border-subtle)]'}`}>
                <div className="prose prose-invert prose-sm max-w-none">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
                </div>
            </div>
        </div>
    );
}

function ChatItemBubble({item}: { item: any }) {
    const agent = item.agent ? AGENTS[item.agent as AgentType] : null;

    // Agent Message
    if (item.type === 'agent_message' && agent) {
        return (
            <motion.div initial={{opacity: 0, y: 10}} animate={{opacity: 1, y: 0}} className="flex justify-start">
                <div className={`max-w-[85%] rounded-xl p-3 border ${agent.bg}`}>
                    <div className="flex items-center gap-2 mb-1">
                        <span>{agent.emoji}</span>
                        <span className={`text-sm font-medium ${agent.color}`}>{agent.name}</span>
                    </div>
                    <p className="text-sm text-[var(--color-text-secondary)]">{item.message}</p>
                </div>
            </motion.div>
        );
    }

    // Agent Handoff
    if (item.type === 'agent_handoff' && agent) {
        const toAgent = item.toAgent ? AGENTS[item.toAgent as AgentType] : null;
        return (
            <motion.div initial={{opacity: 0, x: -10}} animate={{opacity: 1, x: 0}} className="flex justify-start">
                <div
                    className="flex items-center gap-2 px-3 py-2 rounded-lg bg-[var(--color-bg-elevated)] border border-[var(--color-border-subtle)]">
                    <span>{agent.emoji}</span>
                    <span className={`text-xs ${agent.color}`}>{agent.name}</span>
                    <ArrowRight className="h-3 w-3 text-[var(--color-text-muted)]"/>
                    {toAgent && <>
                        <span>{toAgent.emoji}</span>
                        <span className={`text-xs ${toAgent.color}`}>{toAgent.name}</span>
                    </>}
                </div>
            </motion.div>
        );
    }

    // Plan Step
    if (item.type === 'plan_step' && item.step) {
        const colors: Record<string, string> = {
            create: 'text-green-400 bg-green-500/10 border-green-500/30',
            modify: 'text-amber-400 bg-amber-500/10 border-amber-500/30',
            delete: 'text-red-400 bg-red-500/10 border-red-500/30',
        };
        return (
            <motion.div initial={{opacity: 0, x: -20}} animate={{opacity: 1, x: 0}} className="flex justify-start">
                <div className={`max-w-[85%] rounded-xl p-3 border ${colors[item.step.action] || colors.create}`}>
                    <div className="flex items-center gap-2 mb-1">
                        <span
                            className="text-xs font-mono bg-black/20 px-2 py-0.5 rounded">Step {item.step.order}</span>
                        <span className="text-xs font-medium uppercase">{item.step.action}</span>
                    </div>
                    <p className="text-sm font-mono text-blue-300">{item.step.file}</p>
                    <p className="text-xs text-[var(--color-text-muted)] mt-1">{item.step.description}</p>
                </div>
            </motion.div>
        );
    }

    // Step Execution
    if (item.type === 'step_execution') {
        return (
            <motion.div initial={{opacity: 0}} animate={{opacity: 1}} className="flex justify-start">
                <div
                    className="flex items-center gap-2 px-3 py-2 rounded-lg bg-orange-500/10 border border-orange-500/30">
                    <span>⚒️</span>
                    <span className="text-xs text-orange-400">{item.message}</span>
                    {item.completed ? <Check className="h-3 w-3 text-green-400"/> :
                        <Loader2 className="h-3 w-3 animate-spin text-orange-400"/>}
                </div>
            </motion.div>
        );
    }

    // System Message
    if (item.type === 'system') {
        const colors: Record<string, string> = {
            info: 'bg-blue-500/10 border-blue-500/30 text-blue-400',
            success: 'bg-green-500/10 border-green-500/30 text-green-400',
            warning: 'bg-amber-500/10 border-amber-500/30 text-amber-400',
            error: 'bg-red-500/10 border-red-500/30 text-red-400',
        };
        return (
            <motion.div initial={{opacity: 0}} animate={{opacity: 1}} className="flex justify-center">
                <div className={`px-4 py-2 rounded-full text-xs border ${colors[item.systemType || 'info']}`}>
                    {item.message}
                </div>
            </motion.div>
        );
    }

    return null;
}

function ThinkingBubble({thinking}: { thinking: AgentThinkingState }) {
    const agent = AGENTS[thinking.agent.type as AgentType] || AGENTS.conductor;
    return (
        <motion.div initial={{opacity: 0}} animate={{opacity: 1}} className="flex justify-start">
            <div className={`max-w-[85%] rounded-xl p-3 border ${agent.bg}`}>
                <div className="flex items-center gap-2">
                    <span>{agent.emoji}</span>
                    <span className={`text-sm ${agent.color}`}>{agent.name}</span>
                    <Loader2 className="h-3 w-3 animate-spin"/>
                </div>
                <p className="text-xs text-[var(--color-text-muted)] mt-1 italic">{thinking.thought}</p>
                {thinking.filePath && <p className="text-xs font-mono text-blue-400 mt-1">{thinking.filePath}</p>}
            </div>
        </motion.div>
    );
}

function PlanApprovalBubble({plan, isLoading, onApprove, onReject}: {
    plan: Plan;
    isLoading: boolean;
    onApprove: () => void;
    onReject: () => void
}) {
    return (
        <motion.div initial={{opacity: 0, scale: 0.95}} animate={{opacity: 1, scale: 1}} className="flex justify-start">
            <div className="max-w-[90%] w-full rounded-xl border border-blue-500/30 bg-blue-500/5 overflow-hidden">
                <div className="px-4 py-3 bg-blue-500/10 border-b border-blue-500/20">
                    <div className="flex items-center gap-2">
                        <AlertCircle className="h-5 w-5 text-blue-400"/>
                        <span className="font-medium">Review Plan</span>
                        <span className="text-xs text-[var(--color-text-muted)]">{plan.steps.length} steps</span>
                    </div>
                </div>
                <div className="p-4">
                    <p className="text-sm text-[var(--color-text-secondary)] mb-3">{plan.summary}</p>
                    <div className="flex gap-2">
                        <button onClick={onReject} disabled={isLoading}
                                className="flex-1 flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-red-500/10 text-red-400 hover:bg-red-500/20 disabled:opacity-50">
                            <XCircle className="h-4 w-4"/><span className="text-sm">Reject</span>
                        </button>
                        <button onClick={onApprove} disabled={isLoading}
                                className="flex-1 flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-green-500 text-white hover:bg-green-400 disabled:opacity-50">
                            {isLoading ? <Loader2 className="h-4 w-4 animate-spin"/> :
                                <CheckCircle className="h-4 w-4"/>}
                            <span className="text-sm">Approve</span>
                        </button>
                    </div>
                </div>
            </div>
        </motion.div>
    );
}

function StreamingFileBubble({file, content, totalLength, action}: StreamingFile) {
    const progress = totalLength > 0 ? (content.length / totalLength) * 100 : 0;
    const displayContent = content ? content + '▊' : '// Generating...';
    const lineCount = content ? content.split('\n').length : 0;

    return (
        <motion.div initial={{opacity: 0, y: 10}} animate={{opacity: 1, y: 0}} className="flex justify-start">
            <div
                className="max-w-[90%] w-full rounded-xl bg-[var(--color-bg-elevated)] border border-[var(--color-border-subtle)] overflow-hidden">
                <div
                    className="flex items-center justify-between px-3 py-2 bg-black/20 border-b border-[var(--color-border-subtle)]">
                    <div className="flex items-center gap-2">
                        <FileCode className="h-4 w-4 text-blue-400"/>
                        <span className="text-xs font-mono text-blue-400">{file}</span>
                        <span
                            className="text-[10px] px-1.5 py-0.5 rounded bg-green-500/20 text-green-400 uppercase">{action}</span>
                    </div>
                    <div className="flex items-center gap-2">
                        <span className="text-[10px] text-[var(--color-text-muted)]">{lineCount} lines</span>
                        <Loader2 className="h-3 w-3 animate-spin text-[var(--color-primary)]"/>
                    </div>
                </div>
                <div className="relative">
                    <div className="absolute top-0 left-0 h-0.5 bg-[var(--color-primary)] transition-all"
                         style={{width: `${progress}%`}}/>
                    <div className="max-h-64 overflow-auto">
                        <SyntaxHighlighter language={getLanguage(file)} style={oneDark} customStyle={{
                            margin: 0,
                            padding: '0.75rem',
                            fontSize: '0.75rem',
                            background: 'transparent'
                        }} showLineNumbers wrapLongLines>
                            {displayContent}
                        </SyntaxHighlighter>
                    </div>
                </div>
            </div>
        </motion.div>
    );
}

function FileArtifactBubble({result}: { result: ExecutionResult }) {
    const [expanded, setExpanded] = useState(false);
    const lineCount = result.content?.split('\n').length || 0;
    const colors: Record<string, string> = {
        create: 'border-green-500/30 bg-green-500/5',
        modify: 'border-amber-500/30 bg-amber-500/5',
        delete: 'border-red-500/30 bg-red-500/5'
    };

    return (
        <motion.div initial={{opacity: 0, scale: 0.95}} animate={{opacity: 1, scale: 1}} className="flex justify-start">
            <div
                className={`max-w-[90%] w-full rounded-xl border overflow-hidden ${colors[result.action] || colors.create}`}>
                <button onClick={() => setExpanded(!expanded)}
                        className="w-full flex items-center justify-between px-3 py-2 hover:bg-black/10">
                    <div className="flex items-center gap-2">
                        <FileCode className="h-4 w-4 text-green-400"/>
                        <span className="text-xs font-mono">{result.file}</span>
                        <span
                            className="text-[10px] px-1.5 py-0.5 rounded bg-green-500/20 text-green-400 uppercase">{result.action}</span>
                        <span className="text-[10px] text-[var(--color-text-muted)]">{lineCount} lines</span>
                        <Check className="h-3 w-3 text-green-400"/>
                    </div>
                    {expanded ? <ChevronDown className="h-4 w-4"/> : <ChevronRight className="h-4 w-4"/>}
                </button>
                {expanded && result.content && (
                    <div className="border-t border-[var(--color-border-subtle)] max-h-96 overflow-auto">
                        <SyntaxHighlighter language={getLanguage(result.file)} style={oneDark}
                                           customStyle={{margin: 0, padding: '0.75rem', fontSize: '0.7rem'}}
                                           showLineNumbers>
                            {result.content}
                        </SyntaxHighlighter>
                    </div>
                )}
            </div>
        </motion.div>
    );
}

function ArtifactsSummaryPanel({artifacts}: { artifacts: ExecutionResult[] }) {
    const [selectedIndex, setSelectedIndex] = useState(0);
    const selected = artifacts[selectedIndex];

    return (
        <motion.div initial={{opacity: 0, y: 20}} animate={{opacity: 1, y: 0}}
                    className="w-full rounded-xl border border-[var(--color-border-subtle)] bg-[var(--color-bg-elevated)] overflow-hidden">
            <div className="flex items-center gap-2 px-4 py-2 bg-black/20 border-b border-[var(--color-border-subtle)]">
                <Sparkles className="h-4 w-4 text-purple-400"/>
                <span className="text-sm font-medium">Generated Files</span>
                <span className="text-xs text-[var(--color-text-muted)]">{artifacts.length} files</span>
            </div>
            <div className="flex">
                {/* File list */}
                <div className="w-48 border-r border-[var(--color-border-subtle)] max-h-80 overflow-auto">
                    {artifacts.map((art, i) => (
                        <button key={i} onClick={() => setSelectedIndex(i)}
                                className={`w-full text-left px-3 py-2 text-xs font-mono truncate hover:bg-[var(--color-bg-hover)] ${
                                    i === selectedIndex ? 'bg-[var(--color-primary)]/20 text-[var(--color-primary)]' : 'text-[var(--color-text-secondary)]'
                                }`}>
                            {art.file.split('/').pop()}
                        </button>
                    ))}
                </div>
                {/* Code preview */}
                <div className="flex-1 max-h-80 overflow-auto">
                    {selected?.content && (
                        <SyntaxHighlighter language={getLanguage(selected.file)} style={oneDark}
                                           customStyle={{margin: 0, padding: '0.75rem', fontSize: '0.7rem', minHeight: '100%'}}
                                           showLineNumbers>
                            {selected.content}
                        </SyntaxHighlighter>
                    )}
                </div>
            </div>
        </motion.div>
    );
}

export default ChatModule;