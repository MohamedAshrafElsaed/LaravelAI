'use client';

import {forwardRef, useCallback, useEffect, useImperativeHandle, useRef, useState} from 'react';
import {Check, FileCode, Loader2, Send} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {Button} from '@/components/ui/Button';
import {chatApi, getErrorMessage} from '@/lib/api';
import {useToast} from '@/components/Toast';
import {AgentConversation, PlanEditor, useAgentConversation, ValidationResultDisplay,} from './index';
import {AgentInfo, AgentTimeline, DEFAULT_AGENTS, InteractiveEvent, Plan, ValidationResult,} from './types';
import {ConversationEntry, eventsToConversationEntries} from './AgentConversation';

interface ExecutionResult {
    action: string;
    file: string;
    success: boolean;
    description?: string;
    error?: string;
}

interface Message {
    id: string;
    role: 'user' | 'assistant';
    content: string;
    timestamp: Date;
    processingData?: {
        intent?: any;
        plan?: any;
        execution_results?: ExecutionResult[];
        validation?: any;
        events?: any[];
        success?: boolean;
        error?: string;
        agent_timeline?: AgentTimeline;
        agent_activity?: ConversationEntry[];
    };
}

interface InteractiveChatProps {
    projectId: string;
    conversationId?: string | null;
    onConversationChange?: (id: string | null) => void;
    requirePlanApproval?: boolean;
    className?: string;
}

// Ref interface for exposing methods to parent
export interface InteractiveChatRef {
    startNewChat: () => void;
}

// Files Changed Display Component
function FilesChanged({results}: { results: ExecutionResult[] }) {
    if (!results || results.length === 0) return null;

    return (
        <div className="mt-3 pt-3 border-t border-gray-700">
            <div className="flex items-center gap-2 text-sm text-gray-400 mb-2">
                <FileCode className="h-4 w-4"/>
                <span>Files Changed ({results.length})</span>
            </div>
            <div className="font-mono text-xs space-y-1">
                {results.map((result, index) => {
                    const actionColor =
                        result.action === 'create' ? 'text-green-400' :
                            result.action === 'delete' ? 'text-red-400' :
                                'text-yellow-400';

                    return (
                        <div key={index} className="flex items-center gap-2">
                            {result.success ? (
                                <Check className="h-3 w-3 text-green-400"/>
                            ) : (
                                <span className="text-red-400">✗</span>
                            )}
                            <span className={actionColor}>[{result.action}]</span>
                            <span className="text-blue-400">{result.file}</span>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}

// Stored Activity Display - for displaying persisted conversation entries
function StoredActivityDisplay({entries}: { entries: ConversationEntry[] }) {
    if (!entries || entries.length === 0) return null;

    return (
        <div className="bg-gray-950 rounded-lg p-4 border border-gray-800 mb-4">
            <AgentConversation entries={entries} autoScroll={false}/>
        </div>
    );
}

export const InteractiveChat = forwardRef<InteractiveChatRef, InteractiveChatProps>(function InteractiveChat({
                                                                                                                 projectId,
                                                                                                                 conversationId: initialConversationId,
                                                                                                                 onConversationChange,
                                                                                                                 requirePlanApproval = true,
                                                                                                                 className = '',
                                                                                                             }, ref) {
    const toast = useToast();
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLTextAreaElement>(null);

    // SSR hydration handling - only access localStorage after mount
    const [mounted, setMounted] = useState(false);

    // State
    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [isStreaming, setIsStreaming] = useState(false);
    const [streamingContent, setStreamingContent] = useState('');
    const [conversationId, setConversationId] = useState<string | null>(initialConversationId || null);
    const [error, setError] = useState<string | null>(null);
    const [isLoadingMessages, setIsLoadingMessages] = useState(false);
    const [authToken, setAuthToken] = useState<string>('');

    // Agent conversation state
    const {
        entries: conversationEntries,
        currentThinking,
        processEvent,
        clearEntries,
        setCurrentThinking,
        addEntry,
    } = useAgentConversation();

    // Plan approval state
    const [awaitingPlanApproval, setAwaitingPlanApproval] = useState(false);
    const [currentPlan, setCurrentPlan] = useState<Plan | null>(null);
    const [isPlanApprovalLoading, setIsPlanApprovalLoading] = useState(false);

    // Validation result state
    const [validationResult, setValidationResult] = useState<ValidationResult | null>(null);

    // Agent timeline
    const [agentTimeline, setAgentTimeline] = useState<AgentTimeline | null>(null);

    // Agents info
    const [agents, setAgents] = useState<AgentInfo[]>(Object.values(DEFAULT_AGENTS));

    // Processing state key for localStorage
    const processingStateKey = `chat_processing_${projectId}`;

    // Auto-scroll
    const scrollToBottom = useCallback(() => {
        messagesEndRef.current?.scrollIntoView({behavior: 'smooth'});
    }, []);

    useEffect(() => {
        scrollToBottom();
    }, [messages, streamingContent, conversationEntries, scrollToBottom]);

    // Mark component as mounted (client-side only) and load auth token
    useEffect(() => {
        setMounted(true);
        setAuthToken(localStorage.getItem('auth_token') || '');
    }, []);

    // Load saved conversation on mount - only after component is mounted (client-side)
    useEffect(() => {
        if (!mounted) return;
        const savedConvId = localStorage.getItem(`conversation_${projectId}`);
        if (savedConvId) {
            loadMessages(savedConvId);
        }
    }, [projectId, mounted]);

    // Check for in-progress processing state on mount - only after component is mounted
    useEffect(() => {
        if (!mounted) return;
        const processingState = localStorage.getItem(processingStateKey);
        if (processingState) {
            try {
                const state = JSON.parse(processingState);
                // If there's an active processing state, try to restore it
                if (state.isLoading && state.conversationId) {
                    setConversationId(state.conversationId);
                    setIsLoading(true);
                    // Try to reconnect or load current state
                    loadMessages(state.conversationId);
                }
            } catch (e) {
                localStorage.removeItem(processingStateKey);
            }
        }
    }, [processingStateKey, mounted]);

    // Start new chat function - clears all state and starts fresh
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
        setAgentTimeline(null);
        clearEntries();

        // Clear localStorage
        localStorage.removeItem(`conversation_${projectId}`);
        localStorage.removeItem(processingStateKey);

        onConversationChange?.(null);
        inputRef.current?.focus();
    }, [projectId, processingStateKey, clearEntries, onConversationChange]);

    // Expose startNewChat to parent via ref
    useImperativeHandle(ref, () => ({
        startNewChat,
    }), [startNewChat]);

    // Save processing state
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

    // Load conversation messages
    const loadMessages = useCallback(async (convId: string) => {
        setIsLoadingMessages(true);
        try {
            const response = await chatApi.getMessages(projectId, convId);
            const loadedMessages: Message[] = response.data.map((msg: any) => {
                const processingData = msg.processing_data || {};

                // Convert stored events to conversation entries if available
                // This allows us to display the agent activity from stored data
                let agentActivity: ConversationEntry[] = [];
                if (processingData.events && Array.isArray(processingData.events)) {
                    agentActivity = eventsToConversationEntries(processingData.events);
                }

                return {
                    id: msg.id,
                    role: msg.role,
                    content: msg.content,
                    timestamp: new Date(msg.created_at),
                    processingData: {
                        ...processingData,
                        agent_activity: agentActivity,
                    },
                };
            });
            setMessages(loadedMessages);
            setConversationId(convId);
            onConversationChange?.(convId);
            localStorage.setItem(`conversation_${projectId}`, convId);

            // Clear any stale processing state if we loaded completed messages
            saveProcessingState(false, null);
        } catch (err) {
            console.error('Failed to load messages:', err);
            toast.error('Failed to load messages', getErrorMessage(err));
        } finally {
            setIsLoadingMessages(false);
        }
    }, [projectId, toast, onConversationChange, saveProcessingState]);

    // Handle SSE events
    const handleEvent = useCallback((event: InteractiveEvent) => {
        const {event: eventType, data} = event;

        // Process event in agent conversation
        processEvent(event);

        switch (eventType) {
            case 'connected':
                if (data.conversation_id) {
                    setConversationId(data.conversation_id);
                    onConversationChange?.(data.conversation_id);
                    localStorage.setItem(`conversation_${projectId}`, data.conversation_id);
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

                if (data.agent_timeline) {
                    setAgentTimeline(data.agent_timeline);
                }

                // Add assistant message with stored activity
                if (data.answer || data.success) {
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
                            // Store current conversation entries for persistence
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
                toast.error('Error', data.message || 'An error occurred');
                break;

            default:
                break;
        }
    }, [processEvent, onConversationChange, setCurrentThinking, toast, projectId, saveProcessingState, conversationEntries]);

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
                    events.push({event: currentEvent as any, data});
                } catch (e) {
                    console.error('Failed to parse SSE data:', e);
                }
                currentEvent = null;
            }
        }

        return events;
    }, []);

    // Send message
    const sendMessage = useCallback(async () => {
        if (!input.trim() || isLoading) return;

        const userMessage = input.trim();
        setInput('');
        setIsLoading(true);
        setIsStreaming(true);
        setStreamingContent('');
        setError(null);
        clearEntries();
        setValidationResult(null);
        setAgentTimeline(null);

        // Add user message
        const newUserMessage: Message = {
            id: `msg-${Date.now()}`,
            role: 'user',
            content: userMessage,
            timestamp: new Date(),
        };
        setMessages((prev) => [...prev, newUserMessage]);

        try {
            const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'}/projects/${projectId}/chat`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${authToken}`,
                },
                body: JSON.stringify({
                    message: userMessage,
                    conversation_id: conversationId,
                    interactive_mode: true,
                    require_plan_approval: requirePlanApproval,
                }),
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const reader = response.body?.getReader();
            if (!reader) {
                throw new Error('No response body');
            }

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

            // Process any remaining buffer
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
            const message = getErrorMessage(err);
            setError(message);
            toast.error('Failed to send message', message);
        }
    }, [input, isLoading, projectId, conversationId, requirePlanApproval, clearEntries, parseSSEChunk, handleEvent, toast, saveProcessingState, authToken]);

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
            toast.error('Failed to approve plan', getErrorMessage(err));
        } finally {
            setIsPlanApprovalLoading(false);
        }
    }, [conversationId, projectId, toast]);

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
            toast.error('Failed to reject plan', getErrorMessage(err));
        } finally {
            setIsPlanApprovalLoading(false);
        }
    }, [conversationId, projectId, toast, saveProcessingState]);

    // Handle key press
    const handleKeyPress = useCallback((e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    }, [sendMessage]);

    return (
        <div className={`flex flex-col h-full bg-gray-900 ${className}`}>
            {/* Messages Area */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {/* Loading messages indicator */}
                {isLoadingMessages && (
                    <div className="flex items-center justify-center py-8">
                        <Loader2 className="h-6 w-6 animate-spin text-gray-500"/>
                        <span className="ml-2 text-gray-500">Loading messages...</span>
                    </div>
                )}

                {/* Messages */}
                {messages.map((message, index) => (
                    <div key={message.id}>
                        {/* User message */}
                        {message.role === 'user' && (
                            <div className="flex justify-end animate-slideIn">
                                <div className="max-w-[80%] rounded-lg px-4 py-2 bg-blue-600 text-white">
                                    <div className="prose prose-invert prose-sm max-w-none">
                                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                            {message.content}
                                        </ReactMarkdown>
                                    </div>
                                </div>
                            </div>
                        )}

                        {/* Assistant message */}
                        {message.role === 'assistant' && (
                            <div className="space-y-2">
                                {/* Show stored agent activity if available */}
                                {message.processingData?.agent_activity && message.processingData.agent_activity.length > 0 && (
                                    <StoredActivityDisplay entries={message.processingData.agent_activity}/>
                                )}

                                {/* Message content */}
                                <div className="flex justify-start animate-slideIn">
                                    <div className="max-w-[80%] rounded-lg px-4 py-2 bg-gray-800 text-gray-100">
                                        <div className="prose prose-invert prose-sm max-w-none">
                                            <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                                {message.content}
                                            </ReactMarkdown>
                                        </div>

                                        {/* Files changed */}
                                        {message.processingData?.execution_results && (
                                            <FilesChanged results={message.processingData.execution_results}/>
                                        )}

                                        {/* Validation result */}
                                        {message.processingData?.validation && (
                                            <div className="mt-3 pt-3 border-t border-gray-700">
                                                <ValidationResultDisplay
                                                    validation={message.processingData.validation}
                                                    animated={false}
                                                    showIssues={true}
                                                />
                                            </div>
                                        )}
                                    </div>
                                </div>
                            </div>
                        )}
                    </div>
                ))}

                {/* Streaming content */}
                {isStreaming && streamingContent && (
                    <div className="flex justify-start animate-fadeIn">
                        <div className="max-w-[80%] rounded-lg px-4 py-2 bg-gray-800 text-gray-100">
                            <div className="prose prose-invert prose-sm max-w-none">
                                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                    {streamingContent}
                                </ReactMarkdown>
                                <span className="inline-block w-2 h-4 bg-blue-500 animate-pulse ml-1"/>
                            </div>
                        </div>
                    </div>
                )}

                {/* Agent Activity - CLI Style (current processing) */}
                {(isLoading || conversationEntries.length > 0) && !isLoadingMessages && (
                    <div className="bg-gray-950 rounded-lg p-4 border border-gray-800">
                        <AgentConversation
                            entries={conversationEntries}
                            currentThinking={currentThinking}
                            autoScroll={true}
                        />
                    </div>
                )}

                {/* Plan Approval Gateway */}
                {awaitingPlanApproval && currentPlan && (
                    <div className="my-4 animate-slideIn">
                        <PlanEditor
                            plan={currentPlan}
                            onApprove={handlePlanApproval}
                            onReject={handlePlanRejection}
                            isLoading={isPlanApprovalLoading}
                        />
                    </div>
                )}

                {/* Error display */}
                {error && (
                    <div className="p-4 rounded-lg bg-red-500/10 border border-red-500/30 animate-error-shake">
                        <p className="text-sm text-red-400">{error}</p>
                    </div>
                )}

                {/* Scroll anchor */}
                <div ref={messagesEndRef}/>
            </div>

            {/* Input Area */}
            <div className="border-t border-gray-700 p-4">
                <div className="flex gap-2">
          <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyPress}
              placeholder="Type your message..."
              disabled={isLoading || awaitingPlanApproval}
              className="flex-1 px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
              rows={1}
          />
                    <Button
                        onClick={sendMessage}
                        disabled={!input.trim() || isLoading || awaitingPlanApproval}
                        className="px-4"
                    >
                        {isLoading ? (
                            <Loader2 className="h-5 w-5 animate-spin"/>
                        ) : (
                            <Send className="h-5 w-5"/>
                        )}
                    </Button>
                </div>

                {/* Status indicator */}
                {isLoading && !awaitingPlanApproval && (
                    <div className="mt-2 text-xs text-gray-500 flex items-center gap-2">
                        <Loader2 className="h-3 w-3 animate-spin"/>
                        Processing with AI agents...
                    </div>
                )}
                {awaitingPlanApproval && (
                    <div className="mt-2 text-xs text-purple-400 flex items-center gap-2">
                        Waiting for plan approval...
                    </div>
                )}
            </div>
        </div>
    );
});

export default InteractiveChat;
