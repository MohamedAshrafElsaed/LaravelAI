'use client';

import {useMemo, useState} from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {AlertCircle, Bot, CheckCircle2, ChevronDown, ChevronRight, Loader2,} from 'lucide-react';
import {TodoList} from './TodoList';
import {FileOperation, FileOperationGroup, FileOperationType} from './FileOperation';
import {ProcessingStep, StepStatus, StepType} from './ProcessingStep';

// Types for structured message content
export interface MessageTodo {
    id: string;
    content: string;
    activeForm?: string;
    status: 'pending' | 'in_progress' | 'completed';
}

export interface MessageFileOp {
    type: FileOperationType;
    filePath: string;
    content?: string;
    diff?: string;
    lineCount?: number;
}

export interface MessageStep {
    id: string;
    type: StepType;
    title: string;
    description?: string;
    status: StepStatus;
    files?: string[];
    duration?: number;
    details?: string;
}

export interface StructuredContent {
    text?: string;
    todos?: MessageTodo[];
    fileOps?: MessageFileOp[];
    steps?: MessageStep[];
    plan?: {
        summary: string;
        steps: Array<{
            order: number;
            action: string;
            file: string;
            description: string;
        }>;
    };
    validation?: {
        approved: boolean;
        score: number;
        summary: string;
    };
}

interface InteractiveMessageProps {
    content: StructuredContent | string;
    isStreaming?: boolean;
    processingPhase?: string;
}

// Parse message content to extract structured elements
function parseMessageContent(content: string): StructuredContent {
    const structured: StructuredContent = {text: content};

    // Try to extract todos from markdown-like format
    // Format: - [ ] Task or - [x] Task
    const todoMatches = content.matchAll(/^-\s*\[([ xX])\]\s*(.+)$/gm);
    const todos: MessageTodo[] = [];
    for (const match of todoMatches) {
        todos.push({
            id: `todo-${todos.length}`,
            content: match[2],
            status: match[1] === ' ' ? 'pending' : 'completed',
        });
    }
    if (todos.length > 0) {
        structured.todos = todos;
        // Remove todo lines from text
        structured.text = content.replace(/^-\s*\[[ xX]\]\s*.+$/gm, '').trim();
    }

    return structured;
}

export function InteractiveMessage({
                                       content,
                                       isStreaming = false,
                                       processingPhase,
                                   }: InteractiveMessageProps) {
    const structured = useMemo(() => {
        if (typeof content === 'string') {
            return parseMessageContent(content);
        }
        return content;
    }, [content]);

    return (
        <div className="space-y-3">
            {/* Processing phase indicator */}
            {processingPhase && (
                <div className="flex items-center gap-2 text-sm text-blue-400">
                    <Loader2 className="h-4 w-4 animate-spin"/>
                    <span>{processingPhase}</span>
                </div>
            )}

            {/* Todo list */}
            {structured.todos && structured.todos.length > 0 && (
                <TodoList
                    title="Tasks"
                    todos={structured.todos}
                    defaultExpanded={true}
                />
            )}

            {/* Plan display */}
            {structured.plan && (
                <PlanDisplay plan={structured.plan}/>
            )}

            {/* Steps */}
            {structured.steps && structured.steps.length > 0 && (
                <div className="space-y-2">
                    {structured.steps.map((step) => (
                        <ProcessingStep
                            key={step.id}
                            type={step.type}
                            title={step.title}
                            description={step.description}
                            status={step.status}
                            files={step.files}
                            duration={step.duration}
                            details={step.details ? (
                                <pre className="text-xs text-gray-400 whitespace-pre-wrap">{step.details}</pre>
                            ) : undefined}
                        />
                    ))}
                </div>
            )}

            {/* File operations */}
            {structured.fileOps && structured.fileOps.length > 0 && (
                structured.fileOps.length === 1 ? (
                    <FileOperation
                        type={structured.fileOps[0].type}
                        filePath={structured.fileOps[0].filePath}
                        content={structured.fileOps[0].content}
                        diff={structured.fileOps[0].diff}
                        lineCount={structured.fileOps[0].lineCount}
                    />
                ) : (
                    <FileOperationGroup
                        title={`${structured.fileOps.length} files`}
                        operations={structured.fileOps}
                        defaultExpanded={false}
                    />
                )
            )}

            {/* Validation result */}
            {structured.validation && (
                <ValidationDisplay validation={structured.validation}/>
            )}

            {/* Text content */}
            {structured.text && (
                <div className="prose prose-invert prose-sm max-w-none">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {structured.text}
                    </ReactMarkdown>
                    {isStreaming && (
                        <span className="inline-block w-2 h-4 bg-blue-500 animate-pulse ml-1"/>
                    )}
                </div>
            )}
        </div>
    );
}

// Plan display component
function PlanDisplay({plan}: { plan: NonNullable<StructuredContent['plan']> }) {
    const [isExpanded, setIsExpanded] = useState(true);

    return (
        <div className="rounded-lg border border-gray-800 bg-purple-500/5 overflow-hidden">
            <div
                className="flex items-center gap-3 px-3 py-2.5 cursor-pointer hover:bg-gray-800/50"
                onClick={() => setIsExpanded(!isExpanded)}
            >
        <span className="text-gray-500">
          {isExpanded ? <ChevronDown className="h-4 w-4"/> : <ChevronRight className="h-4 w-4"/>}
        </span>
                <Bot className="h-4 w-4 text-purple-400"/>
                <div className="flex-1">
                    <span className="text-sm font-medium text-white">Plan</span>
                    <span className="ml-2 text-xs text-gray-500">{plan.steps.length} steps</span>
                </div>
            </div>

            {isExpanded && (
                <div className="border-t border-gray-800 p-3">
                    <p className="text-sm text-gray-300 mb-3">{plan.summary}</p>
                    <div className="space-y-2">
                        {plan.steps.map((step, index) => (
                            <div key={index} className="flex items-start gap-3 text-sm">
                                <span className="text-xs text-gray-500 w-5">{step.order}.</span>
                                <span className={`text-xs px-1.5 py-0.5 rounded ${
                                    step.action === 'create' ? 'bg-green-500/20 text-green-400' :
                                        step.action === 'modify' ? 'bg-yellow-500/20 text-yellow-400' :
                                            'bg-red-500/20 text-red-400'
                                }`}>
                  {step.action}
                </span>
                                <div className="flex-1">
                                    <span className="text-gray-300 font-mono text-xs">{step.file}</span>
                                    <p className="text-gray-500 text-xs mt-0.5">{step.description}</p>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}

// Validation display component
function ValidationDisplay({validation}: { validation: NonNullable<StructuredContent['validation']> }) {
    return (
        <div className={`rounded-lg border p-3 ${
            validation.approved
                ? 'border-green-500/30 bg-green-500/5'
                : 'border-red-500/30 bg-red-500/5'
        }`}>
            <div className="flex items-center gap-2 mb-2">
                {validation.approved ? (
                    <CheckCircle2 className="h-4 w-4 text-green-400"/>
                ) : (
                    <AlertCircle className="h-4 w-4 text-red-400"/>
                )}
                <span className={`text-sm font-medium ${
                    validation.approved ? 'text-green-400' : 'text-red-400'
                }`}>
          Validation {validation.approved ? 'Passed' : 'Failed'}
        </span>
                <span className="text-xs text-gray-500">Score: {validation.score}/100</span>
            </div>
            <p className="text-sm text-gray-400">{validation.summary}</p>
        </div>
    );
}
