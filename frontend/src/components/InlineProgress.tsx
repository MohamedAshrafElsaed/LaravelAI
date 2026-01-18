'use client';

import {useEffect, useMemo, useState} from 'react';
import {
    AlertCircle,
    Brain,
    Check,
    CheckCircle2,
    ChevronDown,
    ChevronRight,
    Circle,
    ClipboardList,
    Copy,
    FileCode,
    FileEdit,
    FilePlus,
    FileX,
    Loader2,
    Play,
    Search,
    ShieldCheck,
    Sparkles,
} from 'lucide-react';

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
        [key: string]: any;
    };
}

interface InlineProgressProps {
    events: ProcessingEvent[];
    isProcessing: boolean;
}

type Phase = 'analyzing' | 'retrieving' | 'planning' | 'executing' | 'validating' | 'complete' | 'error';

interface PhaseConfig {
    id: Phase;
    label: string;
    activeLabel: string;
    icon: React.ReactNode;
}

const phases: PhaseConfig[] = [
    {id: 'analyzing', label: 'Analyzed Intent', activeLabel: 'Analyzing Intent...', icon: <Brain className="h-4 w-4"/>},
    {
        id: 'retrieving',
        label: 'Retrieved Context',
        activeLabel: 'Retrieving Context...',
        icon: <Search className="h-4 w-4"/>
    },
    {
        id: 'planning',
        label: 'Created Plan',
        activeLabel: 'Creating Plan...',
        icon: <ClipboardList className="h-4 w-4"/>
    },
    {id: 'executing', label: 'Executed Steps', activeLabel: 'Executing Steps...', icon: <Play className="h-4 w-4"/>},
    {
        id: 'validating',
        label: 'Validated Code',
        activeLabel: 'Validating Code...',
        icon: <ShieldCheck className="h-4 w-4"/>
    },
];

export function InlineProgress({events, isProcessing}: InlineProgressProps) {
    const [currentPhase, setCurrentPhase] = useState<Phase>('analyzing');
    const [completedPhases, setCompletedPhases] = useState<Set<Phase>>(new Set());
    const [intent, setIntent] = useState<any>(null);
    const [plan, setPlan] = useState<any>(null);
    const [steps, setSteps] = useState<any[]>([]);
    const [validation, setValidation] = useState<any>(null);
    const [chunksCount, setChunksCount] = useState(0);
    const [error, setError] = useState<string | null>(null);
    const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set(['steps', 'plan']));

    // Toggle section expansion
    const toggleSection = (section: string) => {
        setExpandedSections((prev) => {
            const newSet = new Set(prev);
            if (newSet.has(section)) {
                newSet.delete(section);
            } else {
                newSet.add(section);
            }
            return newSet;
        });
    };

    // Process events
    useEffect(() => {
        for (const event of events) {
            switch (event.event) {
                case 'intent_analyzed':
                    setCurrentPhase('retrieving');
                    setCompletedPhases((prev) => new Set([...prev, 'analyzing']));
                    if (event.data.intent) {
                        setIntent(event.data.intent);
                    }
                    break;

                case 'context_retrieved':
                    setCurrentPhase('planning');
                    setCompletedPhases((prev) => new Set([...prev, 'analyzing', 'retrieving']));
                    if (event.data.chunks_count) {
                        setChunksCount(event.data.chunks_count);
                    }
                    break;

                case 'planning_started':
                    setCurrentPhase('planning');
                    break;

                case 'plan_created':
                    setCurrentPhase('executing');
                    setCompletedPhases((prev) => new Set([...prev, 'analyzing', 'retrieving', 'planning']));
                    if (event.data.plan) {
                        setPlan(event.data.plan);
                    }
                    break;

                case 'step_started':
                    setCurrentPhase('executing');
                    if (event.data.step) {
                        setSteps((prev) => {
                            const existing = prev.find((s) => s.order === event.data.step.order);
                            if (existing) {
                                return prev.map((s) =>
                                    s.order === event.data.step.order
                                        ? {...s, status: 'running', fixing: event.data.fixing}
                                        : s
                                );
                            }
                            return [...prev, {...event.data.step, status: 'running'}];
                        });
                    }
                    break;

                case 'step_completed':
                    if (event.data.step) {
                        // Result is in event.data.result, not event.data.step.result
                        setSteps((prev) =>
                            prev.map((s) =>
                                s.order === event.data.step.order
                                    ? {...s, status: 'completed', result: event.data.result}
                                    : s
                            )
                        );
                    }
                    break;

                case 'validation_result':
                    setCurrentPhase('validating');
                    setCompletedPhases((prev) => new Set([...prev, 'analyzing', 'retrieving', 'planning', 'executing']));
                    if (event.data.validation) {
                        setValidation(event.data.validation);
                    }
                    break;

                case 'complete':
                    setCurrentPhase('complete');
                    setCompletedPhases((prev) => new Set([...prev, 'analyzing', 'retrieving', 'planning', 'executing', 'validating']));
                    if (event.data.validation) {
                        setValidation(event.data.validation);
                    }
                    break;

                case 'error':
                    setCurrentPhase('error');
                    setError(event.data.message || 'An error occurred');
                    break;
            }
        }
    }, [events]);

    const getPhaseStatus = (phase: Phase) => {
        if (error && currentPhase === 'error') return 'error';
        if (completedPhases.has(phase)) return 'completed';
        if (currentPhase === phase) return 'running';
        return 'pending';
    };

    // Get current active message
    const currentMessage = useMemo(() => {
        if (events.length === 0) return 'Starting...';
        const lastEvent = events[events.length - 1];
        return lastEvent.data.message || 'Processing...';
    }, [events]);

    // Calculate overall progress
    const overallProgress = useMemo(() => {
        if (events.length === 0) return 0;
        const lastEvent = events[events.length - 1];
        return lastEvent.data.progress ? Math.round(lastEvent.data.progress * 100) : 0;
    }, [events]);

    if (!isProcessing && events.length === 0) {
        return null;
    }

    const getActionIcon = (action: string) => {
        switch (action) {
            case 'create':
                return <FilePlus className="h-3.5 w-3.5 text-green-400"/>;
            case 'modify':
                return <FileEdit className="h-3.5 w-3.5 text-yellow-400"/>;
            case 'delete':
                return <FileX className="h-3.5 w-3.5 text-red-400"/>;
            default:
                return <FileCode className="h-3.5 w-3.5 text-gray-400"/>;
        }
    };

    const completedSteps = steps.filter(s => s.status === 'completed').length;
    const totalSteps = plan?.steps?.length || steps.length;

    return (
        <div className="space-y-3">
            {/* Todo-style progress indicator */}
            <TodoStyleProgress
                phases={phases}
                currentPhase={currentPhase}
                completedPhases={completedPhases}
                error={error}
                intent={intent}
                chunksCount={chunksCount}
                plan={plan}
                isExpanded={expandedSections.has('phases')}
                onToggle={() => toggleSection('phases')}
            />

            {/* Plan section */}
            {plan && (
                <PlanSection
                    plan={plan}
                    isExpanded={expandedSections.has('plan')}
                    onToggle={() => toggleSection('plan')}
                />
            )}

            {/* Execution steps */}
            {steps.length > 0 && (
                <ExecutionSteps
                    steps={steps}
                    completedSteps={completedSteps}
                    totalSteps={totalSteps}
                    isExpanded={expandedSections.has('steps')}
                    onToggle={() => toggleSection('steps')}
                    getActionIcon={getActionIcon}
                />
            )}

            {/* Validation Result */}
            {validation && (
                <ValidationSection validation={validation}/>
            )}

            {/* Error */}
            {error && (
                <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3">
                    <div className="flex items-center gap-2 text-red-400">
                        <AlertCircle className="h-4 w-4"/>
                        <span className="text-sm">{error}</span>
                    </div>
                </div>
            )}
        </div>
    );
}

// Todo-style progress component
function TodoStyleProgress({
                               phases,
                               currentPhase,
                               completedPhases,
                               error,
                               intent,
                               chunksCount,
                               plan,
                               isExpanded,
                               onToggle,
                           }: {
    phases: PhaseConfig[];
    currentPhase: Phase;
    completedPhases: Set<Phase>;
    error: string | null;
    intent: any;
    chunksCount: number;
    plan: any;
    isExpanded: boolean;
    onToggle: () => void;
}) {
    const getPhaseStatus = (phase: Phase) => {
        if (error && currentPhase === 'error') return 'error';
        if (completedPhases.has(phase)) return 'completed';
        if (currentPhase === phase) return 'running';
        return 'pending';
    };

    const completedCount = phases.filter(p => completedPhases.has(p.id)).length;
    const currentPhaseConfig = phases.find(p => getPhaseStatus(p.id) === 'running');

    return (
        <div className="rounded-lg border border-gray-800 bg-gray-900/50 overflow-hidden">
            {/* Header */}
            <div
                className="flex items-center gap-3 px-3 py-2.5 cursor-pointer hover:bg-gray-800/50"
                onClick={onToggle}
            >
        <span className="text-gray-500">
          {isExpanded ? <ChevronDown className="h-4 w-4"/> : <ChevronRight className="h-4 w-4"/>}
        </span>

                <Sparkles className="h-4 w-4 text-purple-400"/>

                <div className="flex-1 flex items-center gap-2">
                    <span className="text-sm font-medium text-white">AI Processing</span>
                    <span className="text-xs text-gray-500">
            {completedCount}/{phases.length}
          </span>
                </div>

                {/* Progress bar */}
                <div className="w-20 h-1.5 bg-gray-700 rounded-full overflow-hidden">
                    <div
                        className="h-full bg-gradient-to-r from-blue-500 to-purple-500 transition-all duration-300"
                        style={{width: `${(completedCount / phases.length) * 100}%`}}
                    />
                </div>
            </div>

            {/* Active phase indicator when collapsed */}
            {!isExpanded && currentPhaseConfig && (
                <div className="px-4 py-2 border-t border-gray-800 bg-blue-500/5">
                    <div className="flex items-center gap-2 text-xs">
                        <Loader2 className="h-3 w-3 text-blue-400 animate-spin"/>
                        <span className="text-blue-400">{currentPhaseConfig.activeLabel}</span>
                    </div>
                </div>
            )}

            {/* Phases list */}
            {isExpanded && (
                <div className="border-t border-gray-800">
                    {phases.map((phase, index) => {
                        const status = getPhaseStatus(phase.id);

                        return (
                            <div
                                key={phase.id}
                                className={`flex items-start gap-3 px-4 py-2 ${
                                    index !== phases.length - 1 ? 'border-b border-gray-800/50' : ''
                                } ${status === 'running' ? 'bg-blue-500/5' : ''}`}
                            >
                <span className="mt-0.5">
                  {status === 'completed' ? (
                      <CheckCircle2 className="h-4 w-4 text-green-400"/>
                  ) : status === 'running' ? (
                      <Loader2 className="h-4 w-4 text-blue-400 animate-spin"/>
                  ) : (
                      <Circle className="h-4 w-4 text-gray-600"/>
                  )}
                </span>

                                <div className={`${
                                    status === 'running' ? 'text-blue-400' : ''
                                }`}>
                                    {phase.icon}
                                </div>

                                <div className="flex-1 min-w-0">
                  <span className={`text-sm ${
                      status === 'completed' ? 'text-gray-400' :
                          status === 'running' ? 'text-blue-400' : 'text-gray-500'
                  }`}>
                    {status === 'running' ? phase.activeLabel : phase.label}
                  </span>

                                    {/* Phase-specific details */}
                                    {phase.id === 'analyzing' && status === 'completed' && intent && (
                                        <p className="text-xs text-gray-500 mt-0.5">
                                            Task: {intent.task_type} | Scope: {intent.scope}
                                        </p>
                                    )}
                                    {phase.id === 'retrieving' && status === 'completed' && chunksCount > 0 && (
                                        <p className="text-xs text-gray-500 mt-0.5">
                                            Found {chunksCount} relevant code sections
                                        </p>
                                    )}
                                    {phase.id === 'planning' && status === 'completed' && plan?.steps && (
                                        <p className="text-xs text-gray-500 mt-0.5">
                                            Created plan with {plan.steps.length} steps
                                        </p>
                                    )}
                                </div>
                            </div>
                        );
                    })}
                </div>
            )}
        </div>
    );
}

// Plan section component
function PlanSection({
                         plan,
                         isExpanded,
                         onToggle,
                     }: {
    plan: any;
    isExpanded: boolean;
    onToggle: () => void;
}) {
    return (
        <div className="rounded-lg border border-gray-800 bg-purple-500/5 overflow-hidden">
            <div
                className="flex items-center gap-3 px-3 py-2.5 cursor-pointer hover:bg-gray-800/50"
                onClick={onToggle}
            >
        <span className="text-gray-500">
          {isExpanded ? <ChevronDown className="h-4 w-4"/> : <ChevronRight className="h-4 w-4"/>}
        </span>

                <ClipboardList className="h-4 w-4 text-purple-400"/>

                <div className="flex-1">
                    <span className="text-sm font-medium text-white">Plan</span>
                    <span className="ml-2 text-xs text-gray-500">{plan.steps?.length || 0} steps</span>
                </div>

                <CheckCircle2 className="h-4 w-4 text-green-400"/>
            </div>

            {isExpanded && (
                <div className="border-t border-gray-800 p-3">
                    {plan.summary && (
                        <p className="text-sm text-gray-300 mb-3">{plan.summary}</p>
                    )}

                    <div className="space-y-2">
                        {plan.steps?.map((step: any, index: number) => (
                            <div key={index} className="flex items-start gap-3 text-sm">
                                <span className="text-xs text-gray-500 w-5 shrink-0">{step.order}.</span>
                                <span className={`text-xs px-1.5 py-0.5 rounded shrink-0 ${
                                    step.action === 'create' ? 'bg-green-500/20 text-green-400' :
                                        step.action === 'modify' ? 'bg-yellow-500/20 text-yellow-400' :
                                            'bg-red-500/20 text-red-400'
                                }`}>
                  {step.action}
                </span>
                                <div className="flex-1 min-w-0">
                                    <span className="text-gray-300 font-mono text-xs truncate block">{step.file}</span>
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

// Execution steps component
function ExecutionSteps({
                            steps,
                            completedSteps,
                            totalSteps,
                            isExpanded,
                            onToggle,
                            getActionIcon,
                        }: {
    steps: any[];
    completedSteps: number;
    totalSteps: number;
    isExpanded: boolean;
    onToggle: () => void;
    getActionIcon: (action: string) => React.ReactNode;
}) {
    const [expandedStep, setExpandedStep] = useState<number | null>(null);

    const runningStep = steps.find(s => s.status === 'running');

    return (
        <div className="rounded-lg border border-gray-800 bg-gray-900/50 overflow-hidden">
            <div
                className="flex items-center gap-3 px-3 py-2.5 cursor-pointer hover:bg-gray-800/50"
                onClick={onToggle}
            >
        <span className="text-gray-500">
          {isExpanded ? <ChevronDown className="h-4 w-4"/> : <ChevronRight className="h-4 w-4"/>}
        </span>

                <Play className="h-4 w-4 text-blue-400"/>

                <div className="flex-1 flex items-center gap-2">
                    <span className="text-sm font-medium text-white">Execution</span>
                    <span className="text-xs text-gray-500">
            {completedSteps}/{totalSteps}
          </span>
                </div>

                {/* Progress bar */}
                <div className="w-20 h-1.5 bg-gray-700 rounded-full overflow-hidden">
                    <div
                        className="h-full bg-green-500 transition-all duration-300"
                        style={{width: `${totalSteps > 0 ? (completedSteps / totalSteps) * 100 : 0}%`}}
                    />
                </div>
            </div>

            {/* Running step indicator when collapsed */}
            {!isExpanded && runningStep && (
                <div className="px-4 py-2 border-t border-gray-800 bg-blue-500/5">
                    <div className="flex items-center gap-2 text-xs">
                        <Loader2 className="h-3 w-3 text-blue-400 animate-spin"/>
                        <span className="text-blue-400">
              Step {runningStep.order}: {runningStep.file?.split('/').pop() || runningStep.description}
            </span>
                    </div>
                </div>
            )}

            {/* Steps list */}
            {isExpanded && (
                <div className="border-t border-gray-800">
                    {steps.map((step, index) => (
                        <StepItem
                            key={index}
                            step={step}
                            isLast={index === steps.length - 1}
                            isExpanded={expandedStep === step.order}
                            onToggle={() => setExpandedStep(expandedStep === step.order ? null : step.order)}
                            getActionIcon={getActionIcon}
                        />
                    ))}
                </div>
            )}
        </div>
    );
}

// Individual step item
function StepItem({
                      step,
                      isLast,
                      isExpanded,
                      onToggle,
                      getActionIcon,
                  }: {
    step: any;
    isLast: boolean;
    isExpanded: boolean;
    onToggle: () => void;
    getActionIcon: (action: string) => React.ReactNode;
}) {
    const [copied, setCopied] = useState(false);
    const hasContent = step.result?.content || step.result?.diff;

    const handleCopy = async (e: React.MouseEvent) => {
        e.stopPropagation();
        const text = step.result?.content || step.result?.diff || '';
        await navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    return (
        <div className={`${!isLast ? 'border-b border-gray-800/50' : ''}`}>
            <div
                className={`flex items-center gap-3 px-4 py-2 ${hasContent ? 'cursor-pointer hover:bg-gray-800/30' : ''} ${
                    step.status === 'running' ? 'bg-blue-500/5' : ''
                }`}
                onClick={() => hasContent && onToggle()}
            >
                {hasContent ? (
                    <span className="text-gray-500">
            {isExpanded ? <ChevronDown className="h-3.5 w-3.5"/> : <ChevronRight className="h-3.5 w-3.5"/>}
          </span>
                ) : (
                    <span className="w-3.5"/>
                )}

                {step.status === 'completed' ? (
                    <CheckCircle2 className="h-4 w-4 text-green-400 shrink-0"/>
                ) : step.status === 'running' ? (
                    <Loader2 className="h-4 w-4 text-blue-400 animate-spin shrink-0"/>
                ) : (
                    <Circle className="h-4 w-4 text-gray-600 shrink-0"/>
                )}

                {getActionIcon(step.action)}

                <div className="flex-1 min-w-0">
          <span className={`text-xs px-1.5 py-0.5 rounded mr-2 ${
              step.action === 'create' ? 'bg-green-500/20 text-green-400' :
                  step.action === 'modify' ? 'bg-yellow-500/20 text-yellow-400' :
                      'bg-red-500/20 text-red-400'
          }`}>
            {step.action}
          </span>
                    <span className="text-sm text-gray-300 font-mono">
            {step.file?.split('/').pop() || 'Unknown file'}
          </span>
                    {step.fixing && (
                        <span className="ml-2 text-xs text-orange-400">(fixing...)</span>
                    )}
                </div>

                {hasContent && (
                    <button
                        onClick={handleCopy}
                        className="p-1 text-gray-500 hover:text-gray-300 rounded"
                        title="Copy content"
                    >
                        {copied ? <Check className="h-3.5 w-3.5 text-green-400"/> : <Copy className="h-3.5 w-3.5"/>}
                    </button>
                )}
            </div>

            {/* Expanded content */}
            {isExpanded && hasContent && (
                <div className="border-t border-gray-800 bg-gray-900/50 px-4 py-2">
                    <p className="text-xs text-gray-500 mb-2 font-mono">{step.file}</p>
                    <pre className="text-xs font-mono max-h-60 overflow-auto">
            {step.result?.diff ? (
                <DiffView diff={step.result.diff}/>
            ) : (
                <code className="text-gray-300">{step.result?.content}</code>
            )}
          </pre>
                </div>
            )}
        </div>
    );
}

// Diff viewer
function DiffView({diff}: { diff: string }) {
    const lines = diff.split('\n');

    return (
        <div className="space-y-0">
            {lines.map((line, index) => {
                let className = 'text-gray-400';
                let bgClass = '';

                if (line.startsWith('+') && !line.startsWith('+++')) {
                    className = 'text-green-400';
                    bgClass = 'bg-green-500/10';
                } else if (line.startsWith('-') && !line.startsWith('---')) {
                    className = 'text-red-400';
                    bgClass = 'bg-red-500/10';
                } else if (line.startsWith('@@')) {
                    className = 'text-cyan-400';
                    bgClass = 'bg-cyan-500/5';
                } else if (line.startsWith('diff') || line.startsWith('index')) {
                    className = 'text-gray-500';
                }

                return (
                    <div key={index} className={`${bgClass} px-2 -mx-2`}>
                        <span className={className}>{line || ' '}</span>
                    </div>
                );
            })}
        </div>
    );
}

// Validation section
function ValidationSection({validation}: { validation: any }) {
    const [isExpanded, setIsExpanded] = useState(true);

    return (
        <div className={`rounded-lg border overflow-hidden ${
            validation.approved
                ? 'border-green-500/30 bg-green-500/5'
                : 'border-yellow-500/30 bg-yellow-500/5'
        }`}>
            <div
                className="flex items-center gap-3 px-3 py-2.5 cursor-pointer hover:bg-gray-800/30"
                onClick={() => setIsExpanded(!isExpanded)}
            >
        <span className="text-gray-500">
          {isExpanded ? <ChevronDown className="h-4 w-4"/> : <ChevronRight className="h-4 w-4"/>}
        </span>

                {validation.approved ? (
                    <CheckCircle2 className="h-4 w-4 text-green-400"/>
                ) : (
                    <AlertCircle className="h-4 w-4 text-yellow-400"/>
                )}

                <div className="flex-1">
          <span className={`text-sm font-medium ${
              validation.approved ? 'text-green-400' : 'text-yellow-400'
          }`}>
            Validation {validation.approved ? 'Passed' : 'Needs Review'}
          </span>
                </div>

                <span className={`text-sm font-bold ${
                    validation.score >= 80 ? 'text-green-400' :
                        validation.score >= 60 ? 'text-yellow-400' : 'text-red-400'
                }`}>
          {validation.score}/100
        </span>
            </div>

            {isExpanded && (
                <div className="border-t border-gray-800/50 p-3">
                    {validation.summary && (
                        <p className="text-sm text-gray-400 mb-2">{validation.summary}</p>
                    )}

                    {validation.issues?.length > 0 && (
                        <div className="space-y-1 mt-2">
                            {validation.issues.map((issue: any, i: number) => (
                                <div
                                    key={i}
                                    className={`text-xs px-2 py-1.5 rounded ${
                                        issue.severity === 'error'
                                            ? 'bg-red-500/10 text-red-300 border border-red-500/20'
                                            : issue.severity === 'warning'
                                                ? 'bg-yellow-500/10 text-yellow-300 border border-yellow-500/20'
                                                : 'bg-blue-500/10 text-blue-300 border border-blue-500/20'
                                    }`}
                                >
                                    <span className="font-medium">[{issue.severity}]</span>{' '}
                                    {issue.file && <span className="font-mono">{issue.file}:{issue.line}</span>}{' '}
                                    {issue.message}
                                </div>
                            ))}
                        </div>
                    )}

                    {validation.suggestions?.length > 0 && (
                        <div className="mt-3">
                            <p className="text-xs text-gray-500 mb-1">Suggestions:</p>
                            <ul className="list-disc list-inside text-xs text-gray-400 space-y-0.5">
                                {validation.suggestions.map((suggestion: string, i: number) => (
                                    <li key={i}>{suggestion}</li>
                                ))}
                            </ul>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
