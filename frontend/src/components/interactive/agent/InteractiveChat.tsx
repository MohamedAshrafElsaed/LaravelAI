'use client';

import { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { Send, Loader2, RefreshCw, Settings, History } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Button } from '@/components/ui/Button';
import { chatApi, getErrorMessage } from '@/lib/api';
import { useToast } from '@/components/Toast';
import {
  AgentConversation,
  useAgentConversation,
  AgentAvatar,
  AgentThinking,
  PlanEditor,
  ValidationResultDisplay,
  ScoreReveal,
} from './index';
import {
  AgentInfo,
  AgentType,
  Plan,
  ValidationResult,
  InteractiveEvent,
  AgentTimeline,
  getAgentInfo,
  DEFAULT_AGENTS,
} from './types';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  processingData?: {
    intent?: any;
    plan?: any;
    execution_results?: any[];
    validation?: any;
    events?: any[];
    success?: boolean;
    error?: string;
    agent_timeline?: AgentTimeline;
  };
}

interface InteractiveChatProps {
  projectId: string;
  conversationId?: string | null;
  onConversationChange?: (id: string | null) => void;
  requirePlanApproval?: boolean;
  className?: string;
}

export function InteractiveChat({
  projectId,
  conversationId: initialConversationId,
  onConversationChange,
  requirePlanApproval = true,
  className = '',
}: InteractiveChatProps) {
  const toast = useToast();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // State
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingContent, setStreamingContent] = useState('');
  const [conversationId, setConversationId] = useState<string | null>(initialConversationId || null);
  const [error, setError] = useState<string | null>(null);

  // Agent conversation state
  const {
    entries: conversationEntries,
    currentThinking,
    processEvent,
    clearEntries,
    setCurrentThinking,
  } = useAgentConversation();

  // Plan approval state
  const [awaitingPlanApproval, setAwaitingPlanApproval] = useState(false);
  const [currentPlan, setCurrentPlan] = useState<Plan | null>(null);
  const [isPlanApprovalLoading, setIsPlanApprovalLoading] = useState(false);

  // Validation result state
  const [validationResult, setValidationResult] = useState<ValidationResult | null>(null);

  // Agent timeline
  const [agentTimeline, setAgentTimeline] = useState<AgentTimeline | null>(null);

  // Agents info (from connected event)
  const [agents, setAgents] = useState<AgentInfo[]>(Object.values(DEFAULT_AGENTS));

  // Auto-scroll
  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, streamingContent, conversationEntries, scrollToBottom]);

  // Load conversation messages
  const loadMessages = useCallback(async (convId: string) => {
    try {
      const response = await chatApi.getMessages(projectId, convId);
      const loadedMessages: Message[] = response.data.map((msg: any) => ({
        id: msg.id,
        role: msg.role,
        content: msg.content,
        timestamp: new Date(msg.created_at),
        processingData: msg.processing_data,
      }));
      setMessages(loadedMessages);
      setConversationId(convId);
    } catch (err) {
      console.error('Failed to load messages:', err);
      toast.error('Failed to load messages', getErrorMessage(err));
    }
  }, [projectId, toast]);

  // Handle SSE events
  const handleEvent = useCallback((event: InteractiveEvent) => {
    const { event: eventType, data } = event;

    // Process event in agent conversation
    processEvent(event);

    switch (eventType) {
      case 'connected':
        if (data.conversation_id) {
          setConversationId(data.conversation_id);
          onConversationChange?.(data.conversation_id);
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

        if (data.agent_timeline) {
          setAgentTimeline(data.agent_timeline);
        }

        // Add assistant message
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
        setError(data.message || 'An error occurred');
        toast.error('Error', data.message || 'An error occurred');
        break;

      default:
        // Handle in conversation thread
        break;
    }
  }, [processEvent, onConversationChange, setCurrentThinking, toast]);

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
          events.push({ event: currentEvent as any, data });
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
      // Use interactive mode
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'}/projects/${projectId}/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('auth_token') || ''}`,
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
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
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
      const message = getErrorMessage(err);
      setError(message);
      toast.error('Failed to send message', message);
    }
  }, [input, isLoading, projectId, conversationId, requirePlanApproval, clearEntries, parseSSEChunk, handleEvent, toast]);

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
    } catch (err) {
      console.error('Plan rejection error:', err);
      toast.error('Failed to reject plan', getErrorMessage(err));
    } finally {
      setIsPlanApprovalLoading(false);
    }
  }, [conversationId, projectId, toast]);

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
        {/* Messages */}
        {messages.map((message, index) => (
          <div
            key={message.id}
            className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'} animate-slideIn`}
            style={{ animationDelay: `${Math.min(index * 50, 300)}ms` }}
          >
            <div
              className={`max-w-[80%] rounded-lg px-4 py-2 ${
                message.role === 'user'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-800 text-gray-100'
              }`}
            >
              <div className="prose prose-invert prose-sm max-w-none">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {message.content}
                </ReactMarkdown>
              </div>

              {/* Show validation result for assistant messages */}
              {message.role === 'assistant' && message.processingData?.validation && (
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
        ))}

        {/* Streaming content */}
        {isStreaming && streamingContent && (
          <div className="flex justify-start animate-fadeIn">
            <div className="max-w-[80%] rounded-lg px-4 py-2 bg-gray-800 text-gray-100">
              <div className="prose prose-invert prose-sm max-w-none">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {streamingContent}
                </ReactMarkdown>
                <span className="inline-block w-2 h-4 bg-blue-500 animate-pulse ml-1" />
              </div>
            </div>
          </div>
        )}

        {/* Agent Activity - CLI Style (inline, no box) */}
        {(isLoading || conversationEntries.length > 0) && (
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
        <div ref={messagesEndRef} />
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
              <Loader2 className="h-5 w-5 animate-spin" />
            ) : (
              <Send className="h-5 w-5" />
            )}
          </Button>
        </div>

        {/* Status indicator */}
        {isLoading && !awaitingPlanApproval && (
          <div className="mt-2 text-xs text-gray-500 flex items-center gap-2">
            <Loader2 className="h-3 w-3 animate-spin" />
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
}

export default InteractiveChat;
