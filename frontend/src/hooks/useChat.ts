// frontend/src/hooks/useChat.ts
// Enhanced chat hook with full SSE streaming, agent conversations, and plan approval

import {useCallback, useEffect, useRef, useState} from 'react';
import {chatApi, getErrorMessage} from '@/lib/api';
import type {
    AgentInfo,
    AgentThinkingState,
    AgentType,
    ConversationEntry,
    InteractiveEvent,
    Message,
    Plan,
    ValidationResult,
} from '@/components/chat/types';
import {AGENT_CONFIG} from '@/components/chat/AgentBadge';

// ============== TYPES ==============
export interface UseChatOptions {
    projectId: string;
    initialConversationId?: string | null;
    onConversationChange?: (id: string | null) => void;
    requirePlanApproval?: boolean;
}

export interface UseChatReturn {
    // State
    messages: Message[];
    input: string;
    setInput: (value: string) => void;
    isLoading: boolean;
    isStreaming: boolean;
    streamingContent: string;
    conversationId: string | null;
    error: string | null;
    isLoadingMessages: boolean;
    mounted: boolean;
    // Agent conversation
    conversationEntries: ConversationEntry[];
    currentThinking: AgentThinkingState | null;
    // Plan approval
    awaitingPlanApproval: boolean;
    currentPlan: Plan | null;
    isPlanApprovalLoading: boolean;
    // Validation
    validationResult: ValidationResult | null;
    // Execution
    executionResults: any[];
    // Refs
    messagesEndRef: React.RefObject<HTMLDivElement | null>;
    inputRef: React.RefObject<HTMLTextAreaElement | null>;
    // Actions
    sendMessage: (messageText?: string) => Promise<void>;
    handlePlanApproval: (modifiedPlan?: Plan) => Promise<void>;
    handlePlanRejection: (reason?: string) => Promise<void>;
    startNewChat: () => void;
    loadMessages: (convId: string) => Promise<void>;
    clearError: () => void;
    abort: () => void;
}

// ============== HOOK ==============
export function useChat({
                            projectId,
                            initialConversationId,
                            onConversationChange,
                            requirePlanApproval = true,
                        }: UseChatOptions): UseChatReturn {
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
        const newEntry = {...entry, id: generateEntryId()};
        setConversationEntries((prev) => [...prev, newEntry]);
    }, [generateEntryId]);

    const clearEntries = useCallback(() => {
        setConversationEntries([]);
        setCurrentThinking(null);
        entryIdRef.current = 0;
    }, []);

    const clearError = useCallback(() => {
        setError(null);
    }, []);

    const saveProcessingState = useCallback((isProcessing: boolean, convId: string | null) => {
        if (typeof window === 'undefined') return;
        if (isProcessing && convId) {
            localStorage.setItem(processingStateKey, JSON.stringify({
                isLoading: true,
                conversationId: convId,
                timestamp: Date.now(),
            }));
        } else {
            localStorage.removeItem(processingStateKey);
        }
    }, [processingStateKey]);

    const scrollToBottom = useCallback(() => {
        messagesEndRef.current?.scrollIntoView({behavior: 'smooth'});
    }, []);

    // ============== LIFECYCLE ==============
    useEffect(() => {
        setMounted(true);
        if (typeof window !== 'undefined') {
            const savedConvId = localStorage.getItem(conversationKey);
            if (savedConvId && !initialConversationId) {
                loadMessages(savedConvId);
            }
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    useEffect(() => {
        scrollToBottom();
    }, [messages, streamingContent, conversationEntries, scrollToBottom]);

    // ============== LOAD MESSAGES ==============
    const loadMessages = useCallback(async (convId: string) => {
        setIsLoadingMessages(true);
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
        } catch (err) {
            console.error('Failed to load messages:', err);
            setError(getErrorMessage(err));
        } finally {
            setIsLoadingMessages(false);
        }
    }, [projectId, onConversationChange, saveProcessingState, conversationKey]);

    // ============== SSE PARSING ==============
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
                    events.push({event: currentEvent as any, data});
                } catch (e) {
                    console.error('Failed to parse SSE data:', e);
                }
                currentEvent = null;
            }
        }
        return events;
    }, []);

    // ============== EVENT PROCESSING ==============
    const processAgentEvent = useCallback((event: InteractiveEvent) => {
        const {event: eventType, data} = event;
        const timestamp = data.timestamp || new Date().toISOString();

        const getAgent = (agentType: string): AgentInfo => {
            return AGENT_CONFIG[agentType as AgentType] || AGENT_CONFIG.conductor;
        };

        switch (eventType) {
            case 'agent_message':
                addEntry({
                    type: 'message',
                    timestamp,
                    agentType: data.from_agent as AgentType,
                    toAgentType: data.to_agent as AgentType,
                    message: data.message,
                    messageType: data.message_type,
                });
                break;

            case 'agent_handoff':
                addEntry({
                    type: 'handoff',
                    timestamp,
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
                    agent: getAgent(data.agent),
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
                    agent: getAgent(data.agent),
                    thought: data.message || 'Processing...',
                    progress: 0,
                });
                addEntry({
                    type: 'message',
                    timestamp,
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
                    type: 'message',
                    timestamp,
                    agentType: data.agent as AgentType,
                    message: data.message,
                    messageType: 'completion',
                });
                break;

            case 'step_started':
                setCurrentThinking({
                    agent: AGENT_CONFIG.forge,
                    thought: data.step?.description || 'Working...',
                    actionType: data.step?.action,
                    filePath: data.step?.file,
                    progress: 0,
                });
                addEntry({
                    type: 'step',
                    timestamp,
                    agentType: 'forge',
                    actionType: data.step?.action,
                    filePath: data.step?.file,
                    message: data.step?.description,
                    completed: false,
                });
                break;

            case 'step_completed':
                setCurrentThinking(null);
                setConversationEntries((prev) => {
                    const updated = [...prev];
                    for (let i = updated.length - 1; i >= 0; i--) {
                        if (updated[i].type === 'step' && !updated[i].completed) {
                            updated[i] = {...updated[i], completed: true};
                            break;
                        }
                    }
                    return updated;
                });
                if (data.result) {
                    setExecutionResults((prev) => [...prev, data.result]);
                }
                break;

            case 'plan_ready':
                setCurrentThinking(null);
                addEntry({
                    type: 'system',
                    timestamp,
                    message: 'Plan ready for review. Please approve to continue.',
                    systemType: 'info',
                });
                break;

            case 'plan_approved':
                addEntry({
                    type: 'system',
                    timestamp,
                    message: 'Plan approved! Starting execution...',
                    systemType: 'success',
                });
                break;

            case 'error':
                setCurrentThinking(null);
                addEntry({
                    type: 'system',
                    timestamp,
                    message: data.message || 'An error occurred',
                    systemType: 'error',
                });
                break;

            case 'complete':
                setCurrentThinking(null);
                if (data.success) {
                    addEntry({
                        type: 'system',
                        timestamp,
                        message: 'Task completed successfully!',
                        systemType: 'success',
                    });
                }
                break;
        }
    }, [addEntry]);

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
                    setStreamingContent((prev) => prev + data.chunk);
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
                    setMessages((prev) => [...prev, assistantMessage]);
                    setStreamingContent('');
                    setValidationResult(data.validation || null);
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
        if (!text || isLoading) return;

        setError(null);
        setIsLoading(true);
        setIsStreaming(true);
        setStreamingContent('');
        clearEntries();
        setExecutionResults([]);

        const userMessage: Message = {
            id: `msg-${Date.now()}`,
            role: 'user',
            content: text,
            timestamp: new Date(),
        };
        setMessages((prev) => [...prev, userMessage]);
        setInput('');

        try {
            abortControllerRef.current = new AbortController();
            const chatUrl = chatApi.getChatUrl(projectId);
            const authToken = typeof window !== 'undefined' ? localStorage.getItem('auth_token') : '';

            const response = await fetch(chatUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    Authorization: `Bearer ${authToken}`,
                },
                body: JSON.stringify({
                    message: text,
                    conversation_id: conversationId,
                    interactive_mode: true,
                    require_plan_approval: requirePlanApproval,
                }),
                signal: abortControllerRef.current.signal,
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const reader = response.body?.getReader();
            if (!reader) throw new Error('No response body');

            const decoder = new TextDecoder();
            let buffer = '';

            while (true) {
                const {done, value} = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, {stream: true});
                const events = parseSSEChunk(buffer);
                buffer = '';

                for (const event of events) {
                    handleEvent(event);
                }
            }
        } catch (err: any) {
            if (err.name !== 'AbortError') {
                console.error('Chat error:', err);
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
        clearEntries();
        setCurrentThinking(null);

        localStorage.removeItem(conversationKey);
        localStorage.removeItem(processingStateKey);
        onConversationChange?.(null);

        inputRef.current?.focus();
    }, [conversationKey, processingStateKey, clearEntries, onConversationChange]);

    // ============== ABORT ==============
    const abort = useCallback(() => {
        abortControllerRef.current?.abort();
        setIsLoading(false);
        setIsStreaming(false);
        setCurrentThinking(null);
        saveProcessingState(false, null);
    }, [saveProcessingState]);

    return {
        messages,
        input,
        setInput,
        isLoading,
        isStreaming,
        streamingContent,
        conversationId,
        error,
        isLoadingMessages,
        mounted,
        conversationEntries,
        currentThinking,
        awaitingPlanApproval,
        currentPlan,
        isPlanApprovalLoading,
        validationResult,
        executionResults,
        messagesEndRef,
        inputRef,
        sendMessage,
        handlePlanApproval,
        handlePlanRejection,
        startNewChat,
        loadMessages,
        clearError,
        abort,
    };
}

export default useChat;