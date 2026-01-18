'use client';

import {useCallback, useEffect, useRef, useState} from 'react';
import {chatApi, getErrorMessage} from '@/lib/api';

// ============== TYPES ==============
export type AgentType = 'nova' | 'scout' | 'blueprint' | 'forge' | 'guardian' | 'conductor';

export interface AgentInfo {
    type: AgentType;
    name: string;
    role: string;
    color: string;
    icon: string;
    avatar_emoji: string;
    personality: string;
}

export interface PlanStep {
    order: number;
    action: 'create' | 'modify' | 'delete';
    file: string;
    description: string;
}

export interface Plan {
    summary: string;
    steps: PlanStep[];
}

export interface ValidationIssue {
    severity: 'error' | 'warning' | 'info';
    file: string;
    message: string;
    line?: number;
    suggestion?: string;
}

export interface ValidationResult {
    approved: boolean;
    score: number;
    issues: ValidationIssue[];
    suggestions: string[];
    summary: string;
}

export interface ExecutionResult {
    action: string;
    file: string;
    success: boolean;
    description?: string;
    error?: string;
}

export interface ConversationEntry {
    id: string;
    type: 'thinking' | 'message' | 'action' | 'system';
    timestamp: string;
    agentType?: AgentType;
    thought?: string;
    message?: string;
    messageType?: 'greeting' | 'thinking' | 'handoff' | 'completion' | 'error' | 'custom';
    toAgent?: AgentType;
    actionType?: string;
    filePath?: string;
    isComplete?: boolean;
    systemType?: 'info' | 'success' | 'warning' | 'error';
}

export interface Message {
    id: string;
    role: 'user' | 'assistant';
    content: string;
    timestamp: Date;
    processingData?: {
        intent?: any;
        plan?: Plan;
        execution_results?: ExecutionResult[];
        validation?: ValidationResult;
        events?: any[];
        success?: boolean;
        error?: string;
        agent_timeline?: any;
        agent_activity?: ConversationEntry[];
    };
}

export interface AgentThinkingState {
    agent: AgentInfo;
    thought: string;
    actionType?: string;
    filePath?: string;
    stepIndex?: number;
    progress: number;
}

export interface InteractiveEvent {
    event: string;
    data: Record<string, any>;
}

// ============== CONSTANTS ==============
export const AGENT_COLORS: Record<AgentType, string> = {
    nova: '#9333EA',
    scout: '#3B82F6',
    blueprint: '#F97316',
    forge: '#22C55E',
    guardian: '#EF4444',
    conductor: '#FFFFFF',
};

export const DEFAULT_AGENTS: Record<AgentType, AgentInfo> = {
    nova: {
        type: 'nova',
        name: 'Nova',
        role: 'Intent Analyzer',
        color: '#9333EA',
        icon: 'sparkles',
        avatar_emoji: '🟣',
        personality: 'The curious investigator'
    },
    scout: {
        type: 'scout',
        name: 'Scout',
        role: 'Context Retriever',
        color: '#3B82F6',
        icon: 'search',
        avatar_emoji: '🔵',
        personality: 'The code archaeologist'
    },
    blueprint: {
        type: 'blueprint',
        name: 'Blueprint',
        role: 'Planner',
        color: '#F97316',
        icon: 'clipboard-list',
        avatar_emoji: '🟠',
        personality: 'The strategic architect'
    },
    forge: {
        type: 'forge',
        name: 'Forge',
        role: 'Executor',
        color: '#22C55E',
        icon: 'code',
        avatar_emoji: '🟢',
        personality: 'The master craftsman'
    },
    guardian: {
        type: 'guardian',
        name: 'Guardian',
        role: 'Validator',
        color: '#EF4444',
        icon: 'shield-check',
        avatar_emoji: '🔴',
        personality: 'The quality guardian'
    },
    conductor: {
        type: 'conductor',
        name: 'Conductor',
        role: 'Orchestrator',
        color: '#FFFFFF',
        icon: 'users',
        avatar_emoji: '⚪',
        personality: 'The team lead'
    },
};

export function getAgentInfo(agentType: AgentType | string): AgentInfo {
    const type = agentType.toLowerCase() as AgentType;
    return DEFAULT_AGENTS[type] || DEFAULT_AGENTS.conductor;
}

// ============== HOOK ==============
interface UseChatOptions {
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
    // Agents
    agents: AgentInfo[];
    // Refs
    messagesEndRef: React.RefObject<HTMLDivElement>;
    // Actions
    sendMessage: (messageText?: string) => Promise<void>;
    handlePlanApproval: (plan?: Plan) => Promise<void>;
    handlePlanRejection: (reason?: string) => Promise<void>;
    startNewChat: () => void;
    loadMessages: (convId: string) => Promise<void>;
    loadConversation: (convId: string) => Promise<void>;
    clearError: () => void;
}

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

    // Agent conversation state
    const [conversationEntries, setConversationEntries] = useState<ConversationEntry[]>([]);
    const [currentThinking, setCurrentThinking] = useState<AgentThinkingState | null>(null);
    const entryIdRef = useRef(0);

    // Plan approval state
    const [awaitingPlanApproval, setAwaitingPlanApproval] = useState(false);
    const [currentPlan, setCurrentPlan] = useState<Plan | null>(null);
    const [isPlanApprovalLoading, setIsPlanApprovalLoading] = useState(false);

    // Validation state
    const [validationResult, setValidationResult] = useState<ValidationResult | null>(null);

    // Agents info
    const [agents, setAgents] = useState<AgentInfo[]>(Object.values(DEFAULT_AGENTS));

    // Auth token
    const [authToken, setAuthToken] = useState<string>('');
    const [mounted, setMounted] = useState(false);

    // Refs
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const conversationEntriesRef = useRef<ConversationEntry[]>([]);

    // Keep ref in sync with state for use in callbacks
    useEffect(() => {
        conversationEntriesRef.current = conversationEntries;
    }, [conversationEntries]);

    // Processing state key for localStorage persistence
    const processingStateKey = `chat_processing_${projectId}`;
    const conversationKey = `conversation_${projectId}`;

    // Initialize on mount
    useEffect(() => {
        setMounted(true);
        setAuthToken(localStorage.getItem('auth_token') || '');
    }, []);

    // Load saved conversation on mount
    useEffect(() => {
        if (!mounted) return;
        const savedConvId = localStorage.getItem(conversationKey);
        if (savedConvId) {
            loadMessages(savedConvId);
        }
    }, [projectId, mounted]);

    // Generate entry ID
    const generateEntryId = useCallback(() => {
        entryIdRef.current += 1;
        return `entry-${entryIdRef.current}`;
    }, []);

    // Add conversation entry
    const addEntry = useCallback((entry: Omit<ConversationEntry, 'id'>) => {
        const newEntry: ConversationEntry = {
            ...entry,
            id: generateEntryId(),
        };
        setConversationEntries(prev => [...prev, newEntry]);
    }, [generateEntryId]);

    // Clear entries
    const clearEntries = useCallback(() => {
        setConversationEntries([]);
        entryIdRef.current = 0;
    }, []);

    // Clear error
    const clearError = useCallback(() => {
        setError(null);
    }, []);

    // Save processing state to localStorage
    const saveProcessingState = useCallback((isProcessing: boolean, convId: string | null) => {
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

    // Load messages from API
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

    // Parse SSE chunk
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
                    events.push({event: currentEvent, data});
                } catch (e) {
                    console.error('Failed to parse SSE data:', e);
                }
                currentEvent = null;
            }
        }

        return events;
    }, []);

    // Process SSE event (agent conversation)
    const processAgentEvent = useCallback((event: InteractiveEvent) => {
        const {event: eventType, data} = event;
        const timestamp = data.timestamp || new Date().toISOString();

        switch (eventType) {
            case 'agent_thinking':
                setCurrentThinking({
                    agent: getAgentInfo(data.agent),
                    thought: data.thought,
                    actionType: data.action_type,
                    filePath: data.file_path,
                    progress: data.progress || 0,
                });
                break;

            case 'agent_message':
                setCurrentThinking(null);
                addEntry({
                    type: 'message',
                    timestamp,
                    agentType: data.agent as AgentType,
                    message: data.message,
                    messageType: data.message_type || 'custom',
                });
                break;

            case 'agent_handoff':
                setCurrentThinking(null);
                addEntry({
                    type: 'message',
                    timestamp,
                    agentType: data.from_agent as AgentType,
                    message: data.message,
                    messageType: 'handoff',
                    toAgent: data.to_agent as AgentType,
                });
                break;

            case 'step_started':
            case 'step_completed':
                addEntry({
                    type: 'action',
                    timestamp,
                    agentType: 'forge',
                    actionType: data.step?.action || 'execute',
                    filePath: data.step?.file,
                    message: data.step?.description,
                    isComplete: eventType === 'step_completed',
                });
                break;

            case 'validation_issue_found':
                addEntry({
                    type: 'message',
                    timestamp,
                    agentType: 'guardian',
                    message: `Found issue: ${data.issue?.message}`,
                    messageType: 'error',
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

    // Handle SSE event
    const handleEvent = useCallback((event: InteractiveEvent) => {
        const {event: eventType, data} = event;

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
                if (data.agents) {
                    setAgents(data.agents);
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
                            agent_timeline: data.agent_timeline,
                            agent_activity: [...conversationEntriesRef.current],
                        },
                    };
                    setMessages(prev => [...prev, assistantMessage]);
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
    }, [processAgentEvent, onConversationChange, conversationKey, saveProcessingState]);

    // Send message
    const sendMessage = useCallback(async (messageText?: string) => {
        const text = messageText || input;
        if (!text.trim() || isLoading) return;

        setInput('');
        setIsLoading(true);
        setIsStreaming(true);
        setStreamingContent('');
        setError(null);
        clearEntries();
        setValidationResult(null);

        // Add user message
        const newUserMessage: Message = {
            id: `msg-${Date.now()}`,
            role: 'user',
            content: text.trim(),
            timestamp: new Date(),
        };
        setMessages(prev => [...prev, newUserMessage]);

        try {
            const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
            const response = await fetch(
                `${apiUrl}/projects/${projectId}/chat`,
                {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${authToken}`,
                    },
                    body: JSON.stringify({
                        message: text.trim(),
                        conversation_id: conversationId,
                        interactive_mode: true,
                        require_plan_approval: requirePlanApproval,
                    }),
                }
            );

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
                const lines = buffer.split('\n\n');
                buffer = lines.pop() || '';

                for (const chunk of lines) {
                    if (chunk.trim()) {
                        const events = parseSSEChunk(chunk);
                        for (const event of events) {
                            handleEvent(event);
                        }
                    }
                }
            }

            // Process remaining buffer
            if (buffer.trim()) {
                const events = parseSSEChunk(buffer);
                for (const event of events) {
                    handleEvent(event);
                }
            }
        } catch (err) {
            console.error('Chat error:', err);
            setIsStreaming(false);
            setIsLoading(false);
            saveProcessingState(false, null);
            setError(getErrorMessage(err));
        }
    }, [input, isLoading, projectId, conversationId, requirePlanApproval, authToken, clearEntries, parseSSEChunk, handleEvent, saveProcessingState]);

    // Handle plan approval
    const handlePlanApproval = useCallback(async (plan?: Plan) => {
        if (!conversationId) return;

        setIsPlanApprovalLoading(true);
        try {
            await chatApi.approvePlan(projectId, {
                conversation_id: conversationId,
                approved: true,
                modified_plan: plan,
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

    // Handle plan rejection
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

    // Start new chat
    const startNewChat = useCallback(() => {
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
        clearEntries();
        setCurrentThinking(null);
        localStorage.removeItem(conversationKey);
        localStorage.removeItem(processingStateKey);
        onConversationChange?.(null);
    }, [conversationKey, processingStateKey, clearEntries, onConversationChange]);

    // Auto-scroll
    const scrollToBottom = useCallback(() => {
        messagesEndRef.current?.scrollIntoView({behavior: 'smooth'});
    }, []);

    useEffect(() => {
        scrollToBottom();
    }, [messages, streamingContent, conversationEntries, scrollToBottom]);

    return {
        // State
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
        // Agent conversation
        conversationEntries,
        currentThinking,
        // Plan approval
        awaitingPlanApproval,
        currentPlan,
        isPlanApprovalLoading,
        // Validation
        validationResult,
        // Agents
        agents,
        // Refs
        messagesEndRef,
        // Actions
        sendMessage,
        handlePlanApproval,
        handlePlanRejection,
        startNewChat,
        loadMessages,
        loadConversation: loadMessages,
        clearError,
    };
}