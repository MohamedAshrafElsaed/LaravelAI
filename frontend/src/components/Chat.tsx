'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { Send, User, Bot, Loader2, Plus, Trash2, MessageSquare, History, AlertCircle } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { InlineProgress } from './InlineProgress';
import { chatApi, getErrorMessage } from '@/lib/api';
import { useToast } from './Toast';
import { SkeletonConversationList, SkeletonChatMessages } from './ui/Skeleton';
import { Button } from './ui/Button';

interface ProcessingData {
  intent?: any;
  plan?: any;
  execution_results?: any[];
  validation?: any;
  events?: any[];
  success?: boolean;
  error?: string;
}

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  processing_data?: ProcessingData;
}

interface Conversation {
  id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
  message_count: number;
  last_message: string | null;
}

interface ProcessingEvent {
  event: string;
  data: {
    message?: string;
    progress?: number;
    timestamp?: string;
    intent?: any;
    plan?: any;
    step?: any;
    validation?: any;
    chunks_count?: number;
    fixing?: boolean;
    conversation_id?: string;
    [key: string]: any;
  };
}

interface ChatProps {
  projectId: string;
  onProcessingEvent?: (event: ProcessingEvent) => void;
  onConversationChange?: (conversationId: string | null) => void;
}

// Detect RTL text (Arabic, Hebrew, etc.)
function isRTL(text: string): boolean {
  const rtlChars = /[\u0591-\u07FF\uFB1D-\uFDFD\uFE70-\uFEFC]/;
  return rtlChars.test(text);
}

export function Chat({
  projectId,
  onProcessingEvent,
  onConversationChange,
}: ChatProps) {
  const toast = useToast();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingContent, setStreamingContent] = useState('');
  const [processingEvents, setProcessingEvents] = useState<ProcessingEvent[]>([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [showHistory, setShowHistory] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deletingConvId, setDeletingConvId] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Load conversations list
  const loadConversations = useCallback(async () => {
    setLoadingHistory(true);
    try {
      const response = await chatApi.listConversations(projectId);
      setConversations(response.data);
    } catch (err) {
      console.error('Failed to load conversations:', err);
      toast.error('Failed to load conversations', getErrorMessage(err));
    } finally {
      setLoadingHistory(false);
    }
  }, [projectId, toast]);

  // Load messages for a conversation
  const loadMessages = useCallback(async (convId: string) => {
    setLoadingMessages(true);
    setError(null);
    try {
      const response = await chatApi.getMessages(projectId, convId);
      const loadedMessages: Message[] = response.data.map((msg: any) => ({
        id: msg.id,
        role: msg.role,
        content: msg.content,
        timestamp: new Date(msg.created_at),
        processing_data: msg.processing_data,
      }));
      setMessages(loadedMessages);
      setConversationId(convId);
      setShowHistory(false);

      // Save to localStorage
      localStorage.setItem(`conversation_${projectId}`, convId);
    } catch (err) {
      console.error('Failed to load messages:', err);
      const message = getErrorMessage(err);
      setError(message);
      toast.error('Failed to load messages', message);
    } finally {
      setLoadingMessages(false);
    }
  }, [projectId, toast]);

  // Load saved conversation on mount
  useEffect(() => {
    const savedConvId = localStorage.getItem(`conversation_${projectId}`);
    if (savedConvId) {
      loadMessages(savedConvId);
    }
    loadConversations();
  }, [projectId, loadMessages, loadConversations]);

  // Notify parent of conversation changes
  useEffect(() => {
    onConversationChange?.(conversationId);
  }, [conversationId, onConversationChange]);

  // Auto-scroll to bottom
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, streamingContent, processingEvents]);

  // Auto-resize textarea
  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.style.height = 'auto';
      inputRef.current.style.height = `${Math.min(inputRef.current.scrollHeight, 150)}px`;
    }
  }, [input]);

  // Start a new conversation
  const startNewConversation = () => {
    setConversationId(null);
    setMessages([]);
    setShowHistory(false);
    localStorage.removeItem(`conversation_${projectId}`);
  };

  // Delete a conversation
  const deleteConversation = async (convId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm('Delete this conversation?')) return;

    setDeletingConvId(convId);
    try {
      await chatApi.deleteConversation(projectId, convId);
      setConversations((prev) => prev.filter((c) => c.id !== convId));
      if (convId === conversationId) {
        startNewConversation();
      }
      toast.success('Conversation deleted');
    } catch (err) {
      console.error('Failed to delete conversation:', err);
      toast.error('Failed to delete conversation', getErrorMessage(err));
    } finally {
      setDeletingConvId(null);
    }
  };

  // Parse SSE chunk properly
  const parseSSEChunk = (chunk: string): { eventType: string | null; data: any }[] => {
    const results: { eventType: string | null; data: any }[] = [];
    const lines = chunk.split('\n');
    let currentEventType: string | null = null;

    for (const line of lines) {
      const trimmedLine = line.trim();

      if (trimmedLine.startsWith('event:')) {
        currentEventType = trimmedLine.replace('event:', '').trim();
      } else if (trimmedLine.startsWith('data:')) {
        try {
          const jsonStr = trimmedLine.replace('data:', '').trim();
          if (jsonStr) {
            const data = JSON.parse(jsonStr);
            const eventType = data.event || currentEventType || 'unknown';
            results.push({ eventType, data: { ...data, event: eventType } });
          }
        } catch (e) {
          // Ignore parse errors
        }
        currentEventType = null;
      }
    }

    return results;
  };

  // Send message
  const sendMessage = useCallback(async () => {
    if (!input.trim() || isLoading) return;

    const userMessage: Message = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: input.trim(),
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);
    setIsStreaming(true);
    setStreamingContent('');
    setProcessingEvents([]);
    setIsProcessing(true);

    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'}/projects/${projectId}/chat`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            message: userMessage.content,
            conversation_id: conversationId,
          }),
        }
      );

      if (!response.ok) {
        throw new Error('Failed to send message');
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let fullContent = '';
      let buffer = '';
      let newConversationId: string | null = null;

      if (reader) {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          const chunk = decoder.decode(value, { stream: true });
          buffer += chunk;

          const messages = buffer.split('\n\n');
          buffer = messages.pop() || '';

          for (const message of messages) {
            if (!message.trim()) continue;

            const parsedEvents = parseSSEChunk(message);

            for (const { eventType, data } of parsedEvents) {
              const event: ProcessingEvent = {
                event: eventType || 'unknown',
                data,
              };

              // Capture conversation_id from connected event
              if (eventType === 'connected' && data.conversation_id) {
                newConversationId = data.conversation_id;
                setConversationId(data.conversation_id);
                localStorage.setItem(`conversation_${projectId}`, data.conversation_id);
              }

              setProcessingEvents((prev) => [...prev, event]);
              onProcessingEvent?.(event);

              if (data.chunk) {
                fullContent += data.chunk;
                setStreamingContent(fullContent);
              }

              if (eventType === 'complete' || data.success !== undefined) {
                if (data.answer) {
                  fullContent = data.answer;
                  setStreamingContent(fullContent);
                }
                setIsProcessing(false);
              }

              if (eventType === 'error') {
                setIsProcessing(false);
              }
            }
          }
        }

        // Process remaining buffer
        if (buffer.trim()) {
          const parsedEvents = parseSSEChunk(buffer);
          for (const { eventType, data } of parsedEvents) {
            const event: ProcessingEvent = {
              event: eventType || 'unknown',
              data,
            };
            setProcessingEvents((prev) => [...prev, event]);
            onProcessingEvent?.(event);

            if (data.chunk) {
              fullContent += data.chunk;
              setStreamingContent(fullContent);
            }
            if (data.answer) {
              fullContent = data.answer;
            }
          }
        }
      }

      // Add assistant message
      if (fullContent) {
        const assistantMessage: Message = {
          id: `assistant-${Date.now()}`,
          role: 'assistant',
          content: fullContent,
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, assistantMessage]);
      }

      // Refresh conversations list
      loadConversations();
    } catch (err) {
      console.error('Chat error:', err);
      const errorText = getErrorMessage(err);
      const errorMessage: Message = {
        id: `error-${Date.now()}`,
        role: 'assistant',
        content: `Sorry, an error occurred: ${errorText}. Please try again.`,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
      setError(errorText);
      toast.error('Chat error', errorText);
    } finally {
      setIsLoading(false);
      setIsStreaming(false);
      setStreamingContent('');
      setIsProcessing(false);
    }
  }, [input, isLoading, projectId, conversationId, onProcessingEvent, loadConversations]);

  // Handle key press
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="flex h-full flex-col bg-gray-950">
      {/* Header with actions */}
      <div className="flex items-center justify-between border-b border-gray-800 px-4 py-2">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowHistory(!showHistory)}
            className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm transition-colors ${
              showHistory
                ? 'bg-blue-500/20 text-blue-400'
                : 'text-gray-400 hover:bg-gray-800 hover:text-white'
            }`}
          >
            <History className="h-4 w-4" />
            <span className="hidden sm:inline">History</span>
            {conversations.length > 0 && (
              <span className="ml-1 rounded-full bg-gray-700 px-1.5 py-0.5 text-xs">
                {conversations.length}
              </span>
            )}
          </button>
        </div>
        <button
          onClick={startNewConversation}
          className="flex items-center gap-1.5 rounded-lg bg-blue-600 px-3 py-1.5 text-sm text-white hover:bg-blue-500 transition-colors"
        >
          <Plus className="h-4 w-4" />
          <span className="hidden sm:inline">New Chat</span>
        </button>
      </div>

      {/* Conversation history sidebar */}
      {showHistory && (
        <div className="border-b border-gray-800 bg-gray-900/50 max-h-64 overflow-y-auto">
          {loadingHistory ? (
            <SkeletonConversationList />
          ) : conversations.length === 0 ? (
            <div className="py-8 text-center text-sm text-gray-500">
              No previous conversations
            </div>
          ) : (
            <div className="p-2 space-y-1">
              {conversations.map((conv) => (
                <button
                  key={conv.id}
                  onClick={() => loadMessages(conv.id)}
                  className={`w-full flex items-center justify-between rounded-lg px-3 py-2 text-left text-sm transition-colors group ${
                    conv.id === conversationId
                      ? 'bg-blue-500/20 text-white'
                      : 'text-gray-300 hover:bg-gray-800'
                  }`}
                >
                  <div className="flex items-center gap-2 min-w-0 flex-1">
                    <MessageSquare className="h-4 w-4 shrink-0 text-gray-500" />
                    <div className="min-w-0 flex-1">
                      <div className="truncate font-medium">
                        {conv.title || 'Untitled conversation'}
                      </div>
                      {conv.last_message && (
                        <div className="truncate text-xs text-gray-500 mt-0.5">
                          {conv.last_message}
                        </div>
                      )}
                    </div>
                  </div>
                  <button
                    onClick={(e) => deleteConversation(conv.id, e)}
                    disabled={deletingConvId === conv.id}
                    className="opacity-0 group-hover:opacity-100 p-1 hover:text-red-400 transition-opacity disabled:opacity-100 disabled:cursor-wait"
                  >
                    {deletingConvId === conv.id ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Trash2 className="h-4 w-4" />
                    )}
                  </button>
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {loadingMessages ? (
          <SkeletonChatMessages />
        ) : error && messages.length === 0 ? (
          <div className="flex h-full items-center justify-center">
            <div className="text-center text-red-400">
              <AlertCircle className="mx-auto h-12 w-12 mb-4 opacity-50" />
              <p className="text-lg font-medium">Failed to load messages</p>
              <p className="text-sm mt-1 text-gray-500">{error}</p>
              <button
                onClick={() => conversationId && loadMessages(conversationId)}
                className="mt-4 text-blue-400 hover:text-blue-300"
              >
                Try again
              </button>
            </div>
          </div>
        ) : messages.length === 0 && !isStreaming ? (
          <div className="flex h-full items-center justify-center">
            <div className="text-center text-gray-500">
              <Bot className="mx-auto h-12 w-12 mb-4 opacity-50" />
              <p className="text-lg font-medium">How can I help you?</p>
              <p className="text-sm mt-1">
                Ask questions or describe what you want to build
              </p>
            </div>
          </div>
        ) : (
          <>
            {messages.map((message) => (
              <MessageBubble key={message.id} message={message} />
            ))}

            {/* Inline Progress (while processing) */}
            {isProcessing && processingEvents.length > 0 && (
              <div className="flex items-start gap-3">
                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-purple-500/20 shrink-0">
                  <Bot className="h-4 w-4 text-purple-400" />
                </div>
                <div className="flex-1 max-w-[85%]">
                  <InlineProgress events={processingEvents} isProcessing={isProcessing} />
                </div>
              </div>
            )}

            {/* Streaming message */}
            {isStreaming && streamingContent && !isProcessing && (
              <MessageBubble
                message={{
                  id: 'streaming',
                  role: 'assistant',
                  content: streamingContent,
                  timestamp: new Date(),
                }}
                isStreaming
              />
            )}

            {/* Loading indicator (before any events) */}
            {isLoading && processingEvents.length === 0 && !streamingContent && (
              <div className="flex items-start gap-3">
                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-purple-500/20">
                  <Bot className="h-4 w-4 text-purple-400" />
                </div>
                <div className="flex items-center gap-2 text-gray-400 bg-gray-800 rounded-lg px-4 py-3">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span className="text-sm">Starting AI processing...</span>
                </div>
              </div>
            )}
          </>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="border-t border-gray-800 p-4">
        <div className="relative flex items-end gap-2">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask a question or describe what you want to build..."
            disabled={isLoading}
            rows={1}
            dir={isRTL(input) ? 'rtl' : 'ltr'}
            className="flex-1 resize-none rounded-lg bg-gray-800 px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
          />
          <button
            onClick={sendMessage}
            disabled={!input.trim() || isLoading}
            className="flex h-12 w-12 items-center justify-center rounded-lg bg-blue-600 text-white hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isLoading ? (
              <Loader2 className="h-5 w-5 animate-spin" />
            ) : (
              <Send className="h-5 w-5" />
            )}
          </button>
        </div>
        <p className="mt-2 text-xs text-gray-500">
          Press Enter to send, Shift+Enter for new line
        </p>
      </div>
    </div>
  );
}

// Processing history display for saved messages
function ProcessingHistory({ data }: { data: ProcessingData }) {
  const [expanded, setExpanded] = useState(false);

  if (!data || (!data.intent && !data.plan && !data.events?.length)) {
    return null;
  }

  return (
    <div className="mt-3 border-t border-gray-700 pt-3">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 text-xs text-gray-400 hover:text-gray-300"
      >
        <span>{expanded ? '▼' : '▶'}</span>
        <span>Processing Details</span>
        {data.success !== undefined && (
          <span className={data.success ? 'text-green-400' : 'text-red-400'}>
            ({data.success ? 'Success' : 'Failed'})
          </span>
        )}
      </button>

      {expanded && (
        <div className="mt-2 space-y-2 text-xs">
          {/* Intent */}
          {data.intent && (
            <div className="rounded bg-gray-900 p-2">
              <div className="font-medium text-blue-400">Intent</div>
              <div className="text-gray-400">
                Type: {data.intent.task_type} | Complexity: {data.intent.complexity}
              </div>
              {data.intent.summary && (
                <div className="text-gray-500 mt-1">{data.intent.summary}</div>
              )}
            </div>
          )}

          {/* Plan */}
          {data.plan && (
            <div className="rounded bg-gray-900 p-2">
              <div className="font-medium text-purple-400">Plan</div>
              <div className="text-gray-400">{data.plan.summary}</div>
              {data.plan.steps && data.plan.steps.length > 0 && (
                <ul className="mt-1 space-y-1">
                  {data.plan.steps.map((step: any, i: number) => (
                    <li key={i} className="text-gray-500">
                      {i + 1}. [{step.action}] {step.file}: {step.description?.slice(0, 50)}...
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}

          {/* Execution Results */}
          {data.execution_results && data.execution_results.length > 0 && (
            <div className="rounded bg-gray-900 p-2">
              <div className="font-medium text-green-400">Execution Results</div>
              <ul className="mt-1 space-y-1">
                {data.execution_results.map((result: any, i: number) => (
                  <li key={i} className={result.success ? 'text-green-500' : 'text-red-500'}>
                    [{result.action}] {result.file} - {result.success ? 'Success' : 'Failed'}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Validation */}
          {data.validation && (
            <div className="rounded bg-gray-900 p-2">
              <div className="font-medium text-yellow-400">Validation</div>
              <div className="text-gray-400">
                Score: {data.validation.score}/100 | Approved: {data.validation.approved ? 'Yes' : 'No'}
              </div>
              {data.validation.errors && data.validation.errors.length > 0 && (
                <ul className="mt-1">
                  {data.validation.errors.slice(0, 3).map((err: any, i: number) => (
                    <li key={i} className="text-red-400">- {err.message}</li>
                  ))}
                </ul>
              )}
            </div>
          )}

          {/* Error */}
          {data.error && (
            <div className="rounded bg-red-900/30 p-2 text-red-400">
              Error: {data.error}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// Message bubble component
function MessageBubble({
  message,
  isStreaming,
}: {
  message: Message;
  isStreaming?: boolean;
}) {
  const isUser = message.role === 'user';
  const textDirection = isRTL(message.content) ? 'rtl' : 'ltr';

  return (
    <div className={`flex items-start gap-3 ${isUser ? 'flex-row-reverse' : ''}`}>
      {/* Avatar */}
      <div
        className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${
          isUser ? 'bg-blue-500/20' : 'bg-purple-500/20'
        }`}
      >
        {isUser ? (
          <User className="h-4 w-4 text-blue-400" />
        ) : (
          <Bot className="h-4 w-4 text-purple-400" />
        )}
      </div>

      {/* Content */}
      <div
        className={`max-w-[85%] rounded-lg px-4 py-3 ${
          isUser
            ? 'bg-blue-600 text-white'
            : 'bg-gray-800 text-gray-100'
        }`}
        dir={textDirection}
      >
        {isUser ? (
          <p className="whitespace-pre-wrap">{message.content}</p>
        ) : (
          <>
            <div className="prose prose-invert prose-sm max-w-none">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  // Style code blocks
                  code({ node, className, children, ...props }) {
                    const match = /language-(\w+)/.exec(className || '');
                    const isInline = !match;

                    if (isInline) {
                      return (
                        <code
                          className="rounded bg-gray-700 px-1 py-0.5 text-sm"
                          {...props}
                        >
                          {children}
                        </code>
                      );
                    }

                    return (
                      <pre className="overflow-x-auto rounded-lg bg-gray-900 p-4">
                        <code className={className} {...props}>
                          {children}
                        </code>
                      </pre>
                    );
                  },
                  // Style links
                  a({ children, href }) {
                    return (
                      <a
                        href={href}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-blue-400 hover:underline"
                      >
                        {children}
                      </a>
                    );
                  },
                }}
              >
                {message.content}
              </ReactMarkdown>
              {isStreaming && (
                <span className="inline-block h-4 w-2 animate-pulse bg-gray-400 ml-1" />
              )}
            </div>
            {/* Show processing history for saved messages */}
            {message.processing_data && !isStreaming && (
              <ProcessingHistory data={message.processing_data} />
            )}
          </>
        )}
      </div>
    </div>
  );
}
