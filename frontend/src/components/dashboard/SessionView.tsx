'use client';

import {forwardRef, useEffect, useImperativeHandle, useState} from 'react';
import {AlertCircle, Check, FileCode, Loader2, Plus, Send} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {AgentThinkingState, ConversationEntry, getAgentInfo, Plan, useChat, ValidationResult,} from '@/hooks/useChat';

// ============== SUB-COMPONENTS ==============

// Activity Feed Item
function ActivityItem({entry}: { entry: ConversationEntry }) {
    const agent = entry.agentType ? getAgentInfo(entry.agentType) : null;

    if (entry.type === 'thinking' && agent) {
        return (
            <div className="flex items-center gap-2 text-sm text-[#a1a1aa] animate-pulse">
                <span style={{color: agent.color}}>{agent.avatar_emoji}</span>
                <span>{entry.thought}</span>
            </div>
        );
    }

    if (entry.type === 'message' && agent) {
        return (
            <div className="flex items-start gap-2 text-sm">
                <span style={{color: agent.color}}>{agent.avatar_emoji}</span>
                <div>
          <span className="font-medium" style={{color: agent.color}}>
            {agent.name}:
          </span>
                    <span className="ml-1 text-[#E0E0DE]">{entry.message}</span>
                    {entry.toAgent && (
                        <span className="ml-2 text-xs text-[#666666]">
              → {getAgentInfo(entry.toAgent).name}
            </span>
                    )}
                </div>
            </div>
        );
    }

    if (entry.type === 'action') {
        const actionColor =
            entry.actionType === 'create'
                ? 'text-[#4ade80]'
                : entry.actionType === 'delete'
                    ? 'text-[#f87171]'
                    : 'text-[#fbbf24]';
        return (
            <div className="flex items-center gap-2 text-sm font-mono">
                {entry.isComplete ? (
                    <Check className="h-3 w-3 text-[#4ade80]"/>
                ) : (
                    <Loader2 className="h-3 w-3 animate-spin text-[#a1a1aa]"/>
                )}
                <span className={actionColor}>[{entry.actionType}]</span>
                <span className="text-[#60a5fa]">{entry.filePath}</span>
            </div>
        );
    }

    if (entry.type === 'system') {
        const colors: Record<string, string> = {
            info: 'text-[#a1a1aa]',
            success: 'text-[#4ade80]',
            warning: 'text-[#fbbf24]',
            error: 'text-[#f87171]',
        };
        return (
            <div className={`text-sm ${colors[entry.systemType || 'info']}`}>
                › {entry.message}
            </div>
        );
    }

    return null;
}

// Thinking Indicator with rotating messages
function ThinkingIndicator({thinking}: { thinking: AgentThinkingState }) {
    const rotatingMessages = [
        'Thinking...',
        'Clauding...',
        'Processing...',
        'Analyzing...',
        'Computing...',
    ];
    const [messageIndex, setMessageIndex] = useState(0);

    useEffect(() => {
        const interval = setInterval(() => {
            setMessageIndex((i) => (i + 1) % rotatingMessages.length);
        }, 2000);
        return () => clearInterval(interval);
    }, []);

    return (
        <div className="flex items-center gap-3 p-4 bg-[#202020] rounded-xl border border-[#2b2b2b]">
            <div className="relative">
                <span className="text-2xl">{thinking.agent.avatar_emoji}</span>
                <span className="absolute -bottom-1 -right-1 h-2 w-2 bg-[#4ade80] rounded-full animate-pulse"/>
            </div>
            <div>
                <div className="text-sm font-medium" style={{color: thinking.agent.color}}>
                    {thinking.agent.name}
                </div>
                <div className="text-xs text-[#a1a1aa]">
                    {thinking.thought || rotatingMessages[messageIndex]}
                </div>
                {thinking.filePath && (
                    <div className="text-xs text-[#60a5fa] font-mono mt-1">{thinking.filePath}</div>
                )}
            </div>
        </div>
    );
}

// Plan Editor Component
function PlanEditor({
                        plan,
                        onApprove,
                        onReject,
                        isLoading,
                    }: {
    plan: Plan;
    onApprove: (plan?: Plan) => void;
    onReject: (reason?: string) => void;
    isLoading: boolean;
}) {
    return (
        <div className="p-4 bg-[#202020] rounded-xl border border-[#2b2b2b]">
            <div className="flex items-center gap-2 mb-3">
                <span className="text-xl">🟠</span>
                <span className="font-medium text-[#F97316]">Blueprint&apos;s Plan</span>
            </div>
            <p className="text-sm text-[#a1a1aa] mb-3">{plan.summary}</p>
            <div className="space-y-2 mb-4">
                {plan.steps.map((step, i) => (
                    <div key={i} className="flex items-center gap-2 text-sm font-mono">
                        <span className="text-[#666666]">{i + 1}.</span>
                        <span
                            className={
                                step.action === 'create'
                                    ? 'text-[#4ade80]'
                                    : step.action === 'delete'
                                        ? 'text-[#f87171]'
                                        : 'text-[#fbbf24]'
                            }
                        >
              [{step.action}]
            </span>
                        <span className="text-[#60a5fa]">{step.file}</span>
                    </div>
                ))}
            </div>
            <div className="flex gap-2">
                <button
                    onClick={() => onApprove(plan)}
                    disabled={isLoading}
                    className="px-4 py-2 bg-[#4ade80] text-[#141414] rounded-lg hover:opacity-90 disabled:opacity-50 text-sm font-medium flex items-center gap-2"
                >
                    {isLoading ? <Loader2 className="h-4 w-4 animate-spin"/> : <Check className="h-4 w-4"/>}
                    Approve
                </button>
                <button
                    onClick={() => onReject('User rejected')}
                    disabled={isLoading}
                    className="px-4 py-2 bg-[#f87171] text-white rounded-lg hover:opacity-90 disabled:opacity-50 text-sm font-medium"
                >
                    Reject
                </button>
            </div>
        </div>
    );
}

// Files Changed Display
function FilesChanged({results}: { results: any[] }) {
    if (!results?.length) return null;

    return (
        <div className="mt-3 pt-3 border-t border-[#2b2b2b]">
            <div className="flex items-center gap-2 text-sm text-[#a1a1aa] mb-2">
                <FileCode className="h-4 w-4"/>
                <span>Files Changed ({results.length})</span>
            </div>
            <div className="font-mono text-xs space-y-1">
                {results.map((result, i) => (
                    <div key={i} className="flex items-center gap-2">
                        {result.success ? (
                            <Check className="h-3 w-3 text-[#4ade80]"/>
                        ) : (
                            <span className="text-[#f87171]">✗</span>
                        )}
                        <span
                            className={
                                result.action === 'create'
                                    ? 'text-[#4ade80]'
                                    : result.action === 'delete'
                                        ? 'text-[#f87171]'
                                        : 'text-[#fbbf24]'
                            }
                        >
              [{result.action}]
            </span>
                        <span className="text-[#60a5fa]">{result.file}</span>
                    </div>
                ))}
            </div>
        </div>
    );
}

// Validation Display
function ValidationDisplay({validation}: { validation: ValidationResult }) {
    const scoreColor =
        validation.score >= 80
            ? 'text-[#4ade80]'
            : validation.score >= 60
                ? 'text-[#fbbf24]'
                : 'text-[#f87171]';

    return (
        <div className="mt-3 pt-3 border-t border-[#2b2b2b]">
            <div className="flex items-center gap-2 mb-2">
                <span>🔴</span>
                <span className="text-sm font-medium text-[#EF4444]">Guardian&apos;s Review</span>
                <span className={`ml-auto font-mono ${scoreColor}`}>{validation.score}/100</span>
            </div>
            {validation.issues.length > 0 && (
                <div className="space-y-1">
                    {validation.issues.slice(0, 3).map((issue, i) => (
                        <div key={i} className="text-xs text-[#a1a1aa]">
              <span className={issue.severity === 'error' ? 'text-[#f87171]' : 'text-[#fbbf24]'}>
                [{issue.severity}]
              </span>{' '}
                            {issue.message}
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}

// Error Display
function ErrorDisplay({error, onDismiss}: { error: string; onDismiss: () => void }) {
    return (
        <div className="p-4 rounded-xl bg-[#f87171]/10 border border-[#f87171]/30 flex items-start gap-3">
            <AlertCircle className="h-5 w-5 text-[#f87171] flex-shrink-0 mt-0.5"/>
            <div className="flex-1">
                <p className="text-sm text-[#f87171]">{error}</p>
            </div>
            <button
                onClick={onDismiss}
                className="text-[#f87171] hover:text-[#fca5a5] text-sm"
            >
                Dismiss
            </button>
        </div>
    );
}

// ============== MAIN COMPONENT ==============

export interface SessionViewRef {
    startNewChat: () => void;
    sendMessage: (message: string) => Promise<void>;
}

interface SessionViewProps {
    projectId: string;
    conversationId?: string | null;
    onConversationChange?: (id: string | null) => void;
}

const SessionView = forwardRef<SessionViewRef, SessionViewProps>(function SessionView(
    {projectId, conversationId: initialConversationId, onConversationChange},
    ref
) {
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
        messagesEndRef,
        sendMessage,
        handlePlanApproval,
        handlePlanRejection,
        startNewChat,
        clearError,
    } = useChat({
        projectId,
        initialConversationId,
        onConversationChange,
        requirePlanApproval: true,
    });

    // Expose methods to parent via ref
    useImperativeHandle(
        ref,
        () => ({
            startNewChat,
            sendMessage,
        }),
        [startNewChat, sendMessage]
    );

    const handleKeyPress = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    };

    return (
        <div className="flex flex-col h-full bg-[#141414]">
            {/* Header */}
            <header className="flex items-center justify-between h-12 px-4 border-b border-[#2b2b2b] bg-[#1b1b1b]">
                <h2 className="text-sm font-medium text-[#E0E0DE]">Chat</h2>
                <button
                    onClick={startNewChat}
                    className="flex items-center gap-1.5 px-2 py-1 rounded-md text-[#a1a1aa] hover:bg-white/5 hover:text-[#E0E0DE] transition-colors"
                    title="New Chat"
                >
                    <Plus className="h-4 w-4"/>
                    <span className="text-xs">New Chat</span>
                </button>
            </header>

            {/* Messages Area */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {isLoadingMessages && (
                    <div className="flex items-center justify-center py-8">
                        <Loader2 className="h-6 w-6 animate-spin text-[#a1a1aa]"/>
                        <span className="ml-2 text-[#a1a1aa]">Loading messages...</span>
                    </div>
                )}

                {messages.map((message) => (
                    <div
                        key={message.id}
                        className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
                    >
                        <div
                            className={`max-w-[80%] rounded-xl p-4 ${
                                message.role === 'user'
                                    ? 'bg-[#e07a5f] text-white'
                                    : 'bg-[#202020] text-[#E0E0DE] border border-[#2b2b2b]'
                            }`}
                        >
                            <ReactMarkdown
                                remarkPlugins={[remarkGfm]}
                                className="prose prose-invert prose-sm max-w-none"
                                components={{
                                    pre: ({children}) => (
                                        <pre className="bg-[#141414] rounded-lg p-3 overflow-x-auto text-xs">
                      {children}
                    </pre>
                                    ),
                                    code: ({children, className}) => {
                                        const isInline = !className;
                                        return isInline ? (
                                            <code className="bg-[#2b2b2b] px-1.5 py-0.5 rounded text-[#e07a5f] text-xs">
                                                {children}
                                            </code>
                                        ) : (
                                            <code className={className}>{children}</code>
                                        );
                                    },
                                }}
                            >
                                {message.content}
                            </ReactMarkdown>

                            {message.processingData?.execution_results && (
                                <FilesChanged results={message.processingData.execution_results}/>
                            )}

                            {message.processingData?.validation && (
                                <ValidationDisplay validation={message.processingData.validation}/>
                            )}
                        </div>
                    </div>
                ))}

                {/* Streaming content */}
                {isStreaming && streamingContent && (
                    <div className="flex justify-start">
                        <div className="max-w-[80%] rounded-xl p-4 bg-[#202020] border border-[#2b2b2b]">
                            <ReactMarkdown
                                remarkPlugins={[remarkGfm]}
                                className="prose prose-invert prose-sm max-w-none"
                            >
                                {streamingContent}
                            </ReactMarkdown>
                        </div>
                    </div>
                )}

                {/* Activity Feed */}
                {conversationEntries.length > 0 && (
                    <div className="bg-[#202020] rounded-xl p-4 border border-[#2b2b2b] space-y-2">
                        {conversationEntries.map((entry) => (
                            <ActivityItem key={entry.id} entry={entry}/>
                        ))}
                    </div>
                )}

                {/* Current Thinking */}
                {currentThinking && <ThinkingIndicator thinking={currentThinking}/>}

                {/* Plan Approval */}
                {awaitingPlanApproval && currentPlan && (
                    <PlanEditor
                        plan={currentPlan}
                        onApprove={handlePlanApproval}
                        onReject={handlePlanRejection}
                        isLoading={isPlanApprovalLoading}
                    />
                )}

                {/* Error */}
                {error && <ErrorDisplay error={error} onDismiss={clearError}/>}

                <div ref={messagesEndRef}/>
            </div>

            {/* Input Area */}
            <div className="border-t border-[#2b2b2b] bg-[#1b1b1b] p-4">
                <div className="mx-auto max-w-3xl">
                    <div
                        className="relative rounded-xl border border-[#2b2b2b] bg-[#202020] transition-colors focus-within:border-[#3a3a3a]">
            <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyPress}
                placeholder={awaitingPlanApproval ? 'Waiting for plan approval...' : 'Type your message...'}
                disabled={isLoading || awaitingPlanApproval}
                className="w-full bg-transparent px-4 py-3.5 pr-14 text-[13px] text-[#E0E0DE] outline-none placeholder:text-[#666666] resize-none disabled:opacity-50"
                rows={1}
                style={{minHeight: '48px', maxHeight: '200px'}}
            />
                        <div className="absolute right-2.5 bottom-2.5">
                            <button
                                onClick={() => sendMessage()}
                                disabled={!input.trim() || isLoading || awaitingPlanApproval}
                                className={`flex h-8 w-8 items-center justify-center rounded-full transition-all ${
                                    input.trim() && !isLoading && !awaitingPlanApproval
                                        ? 'bg-[#e07a5f] text-[#141414] hover:opacity-90'
                                        : 'bg-[#3a3a3a] text-[#666666]'
                                }`}
                            >
                                {isLoading ? (
                                    <Loader2 className="h-4 w-4 animate-spin"/>
                                ) : (
                                    <Send className="h-4 w-4"/>
                                )}
                            </button>
                        </div>
                    </div>

                    {isLoading && !awaitingPlanApproval && (
                        <div className="mt-2 text-xs text-[#a1a1aa] flex items-center gap-2">
                            <Loader2 className="h-3 w-3 animate-spin"/>
                            Processing with AI agents...
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
});

export default SessionView;