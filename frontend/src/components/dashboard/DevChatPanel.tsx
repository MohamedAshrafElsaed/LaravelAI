'use client';

import {useCallback, useEffect, useRef, useState} from 'react';
import {motion} from 'framer-motion';
import {AlertCircle, Bot, Loader2, Send, Sparkles, User} from 'lucide-react';
import {chatApi} from '@/lib/api';

interface Message {
    id: string;
    role: 'user' | 'assistant';
    content: string;
    codeBlock?: string;
    timestamp: string;
    isStreaming?: boolean;
    error?: boolean;
}

interface DevChatPanelProps {
    projectId?: string;
    initialMessages?: Message[];
}

const defaultMessages: Message[] = [
    {
        id: '1',
        role: 'assistant',
        content: 'System initialized. Select a project and ask me to help with your Laravel code.',
        timestamp: new Date().toLocaleTimeString('en-US', {
            hour12: false,
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
        }),
    },
];

export default function DevChatPanel({
                                         projectId,
                                         initialMessages = defaultMessages,
                                     }: DevChatPanelProps) {
    const [input, setInput] = useState('');
    const [messages, setMessages] = useState<Message[]>(initialMessages);
    const [isLoading, setIsLoading] = useState(false);
    const [conversationId, setConversationId] = useState<string | null>(null);
    const scrollRef = useRef<HTMLDivElement>(null);
    const abortControllerRef = useRef<AbortController | null>(null);

    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [messages]);

    // Reset conversation when project changes
    useEffect(() => {
        setConversationId(null);
        setMessages(defaultMessages);
    }, [projectId]);

    const handleSend = useCallback(async () => {
        if (!input.trim() || isLoading) return;

        if (!projectId) {
            setMessages(prev => [
                ...prev,
                {
                    id: Date.now().toString(),
                    role: 'assistant',
                    content: 'Please select a project first to start chatting.',
                    timestamp: new Date().toLocaleTimeString('en-US', {
                        hour12: false,
                        hour: '2-digit',
                        minute: '2-digit',
                        second: '2-digit',
                    }),
                    error: true,
                },
            ]);
            return;
        }

        const userMessage: Message = {
            id: Date.now().toString(),
            role: 'user',
            content: input,
            timestamp: new Date().toLocaleTimeString('en-US', {
                hour12: false,
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit',
            }),
        };

        setMessages(prev => [...prev, userMessage]);
        const userInput = input;
        setInput('');
        setIsLoading(true);

        // Add streaming assistant message placeholder
        const assistantMessageId = (Date.now() + 1).toString();
        setMessages(prev => [
            ...prev,
            {
                id: assistantMessageId,
                role: 'assistant',
                content: '',
                timestamp: new Date().toLocaleTimeString('en-US', {
                    hour12: false,
                    hour: '2-digit',
                    minute: '2-digit',
                    second: '2-digit',
                }),
                isStreaming: true,
            },
        ]);

        try {
            // Create abort controller for cancellation
            abortControllerRef.current = new AbortController();

            // Get the SSE endpoint URL
            const chatUrl = chatApi.getChatUrl(projectId);

            // Make SSE request
            const response = await fetch(chatUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${localStorage.getItem('auth_token')}`,
                },
                body: JSON.stringify({
                    message: userInput,
                    conversation_id: conversationId,
                    interactive_mode: false,
                }),
                signal: abortControllerRef.current.signal,
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const reader = response.body?.getReader();
            const decoder = new TextDecoder();
            let fullContent = '';
            let codeBlock = '';

            if (reader) {
                while (true) {
                    const {done, value} = await reader.read();
                    if (done) break;

                    const chunk = decoder.decode(value);
                    const lines = chunk.split('\n');

                    for (const line of lines) {
                        if (line.startsWith('data: ')) {
                            try {
                                const data = JSON.parse(line.slice(6));

                                if (data.type === 'token') {
                                    fullContent += data.content;
                                    setMessages(prev =>
                                        prev.map(msg =>
                                            msg.id === assistantMessageId
                                                ? {...msg, content: fullContent}
                                                : msg
                                        )
                                    );
                                } else if (data.type === 'conversation_id') {
                                    setConversationId(data.conversation_id);
                                } else if (data.type === 'code_change') {
                                    codeBlock = JSON.stringify(data.files, null, 2);
                                } else if (data.type === 'error') {
                                    throw new Error(data.message);
                                } else if (data.type === 'done') {
                                    // Stream complete
                                    setMessages(prev =>
                                        prev.map(msg =>
                                            msg.id === assistantMessageId
                                                ? {...msg, isStreaming: false, codeBlock: codeBlock || undefined}
                                                : msg
                                        )
                                    );
                                }
                            } catch (e) {
                                // Ignore JSON parse errors for incomplete chunks
                            }
                        }
                    }
                }
            }
        } catch (error: any) {
            if (error.name === 'AbortError') {
                // Request was cancelled
                return;
            }

            console.error('Chat error:', error);
            setMessages(prev =>
                prev.map(msg =>
                    msg.id === assistantMessageId
                        ? {
                            ...msg,
                            content: `Error: ${error.message || 'Failed to get response'}`,
                            isStreaming: false,
                            error: true,
                        }
                        : msg
                )
            );
        } finally {
            setIsLoading(false);
            abortControllerRef.current = null;
        }
    }, [input, isLoading, projectId, conversationId]);

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

    return (
        <div className="flex flex-col h-full bg-[var(--color-bg-primary)] border-l border-[var(--color-border-subtle)]">
            {/* Header */}
            <div
                className="h-10 flex items-center px-4 border-b border-[var(--color-border-subtle)] bg-[var(--color-bg-surface)]">
                <Sparkles size={14} className="text-[var(--color-primary)] mr-2"/>
                <span className="text-xs font-bold text-[var(--color-text-primary)] uppercase tracking-wider">
          AI Assistant
        </span>
                <span className="ml-auto text-[10px] font-mono text-green-500 flex items-center">
          <span className="w-1.5 h-1.5 rounded-full bg-green-500 mr-1.5 animate-pulse"/>
                    {projectId ? 'READY' : 'SELECT PROJECT'}
        </span>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4" ref={scrollRef}>
                {messages.map((msg) => (
                    <motion.div
                        key={msg.id}
                        initial={{opacity: 0, y: 10}}
                        animate={{opacity: 1, y: 0}}
                        className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'}`}
                    >
                        <div
                            className={`flex items-center gap-2 mb-1 ${
                                msg.role === 'user' ? 'flex-row-reverse' : ''
                            }`}
                        >
                            <div
                                className={`w-5 h-5 rounded-sm flex items-center justify-center ${
                                    msg.role === 'assistant'
                                        ? msg.error
                                            ? 'bg-red-500 text-white'
                                            : 'bg-[var(--color-primary)] text-white'
                                        : 'bg-[var(--color-bg-elevated)] text-[var(--color-text-secondary)]'
                                }`}
                            >
                                {msg.role === 'assistant' ? (
                                    msg.error ? (
                                        <AlertCircle size={12}/>
                                    ) : msg.isStreaming ? (
                                        <Loader2 size={12} className="animate-spin"/>
                                    ) : (
                                        <Bot size={12}/>
                                    )
                                ) : (
                                    <User size={12}/>
                                )}
                            </div>
                            <span className="text-[10px] font-mono text-[var(--color-text-dimmer)]">
                {msg.timestamp}
              </span>
                        </div>

                        <div
                            className={`max-w-[90%] p-3 rounded-sm text-sm ${
                                msg.role === 'user'
                                    ? 'bg-[var(--color-bg-elevated)] text-[var(--color-text-primary)] border border-[var(--color-border-subtle)]'
                                    : msg.error
                                        ? 'bg-red-500/10 text-red-400 border border-red-500/20'
                                        : 'bg-[var(--color-bg-surface)] text-[var(--color-text-secondary)] border border-dashed border-[var(--color-border-subtle)]'
                            }`}
                        >
                            <p className="whitespace-pre-wrap">{msg.content || (msg.isStreaming ? '...' : '')}</p>
                            {msg.codeBlock && (
                                <div
                                    className="mt-2 p-2 bg-[var(--color-code-bg)] rounded border border-[var(--color-border-subtle)] font-mono text-xs text-[var(--color-code-text)] whitespace-pre-wrap overflow-x-auto">
                                    {msg.codeBlock}
                                </div>
                            )}
                        </div>
                    </motion.div>
                ))}
            </div>

            {/* Input */}
            <div className="p-4 border-t border-[var(--color-border-subtle)] bg-[var(--color-bg-surface)]">
                <div className="relative">
                    <input
                        type="text"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder={projectId ? 'Ask me to help with your code...' : 'Select a project first...'}
                        disabled={isLoading || !projectId}
                        className="w-full bg-[var(--color-bg-input)] border border-[var(--color-border-subtle)] text-[var(--color-text-primary)] text-sm rounded-sm pl-3 pr-10 py-2.5 focus:outline-none focus:border-[var(--color-primary)] transition-colors font-mono placeholder:text-[var(--color-text-dimmer)] disabled:opacity-50 disabled:cursor-not-allowed"
                    />
                    <button
                        onClick={handleSend}
                        disabled={isLoading || !input.trim() || !projectId}
                        className="absolute right-2 top-1/2 -translate-y-1/2 text-[var(--color-text-dimmer)] hover:text-[var(--color-primary)] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        {isLoading ? (
                            <Loader2 size={14} className="animate-spin"/>
                        ) : (
                            <Send size={14}/>
                        )}
                    </button>
                </div>
            </div>
        </div>
    );
}