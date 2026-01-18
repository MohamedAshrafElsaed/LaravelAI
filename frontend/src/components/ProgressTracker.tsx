'use client';

import {useEffect, useState} from 'react';
import {
    AlertCircle,
    Brain,
    CheckCircle2,
    ChevronDown,
    ChevronRight,
    Circle,
    ClipboardList,
    FileCode,
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

interface ProgressTrackerProps {
    events: ProcessingEvent[];
}

type Phase = 'analyzing' | 'retrieving' | 'planning' | 'executing' | 'validating' | 'complete' | 'error';

interface PhaseConfig {
    id: Phase;
    label: string;
    icon: React.ReactNode;
}

const phases: PhaseConfig[] = [
    {id: 'analyzing', label: 'Analyzing Intent', icon: <Brain className="h-4 w-4"/>},
    {id: 'retrieving', label: 'Retrieving Context', icon: <Search className="h-4 w-4"/>},
    {id: 'planning', label: 'Creating Plan', icon: <ClipboardList className="h-4 w-4"/>},
    {id: 'executing', label: 'Executing Steps', icon: <Play className="h-4 w-4"/>},
    {id: 'validating', label: 'Validating Code', icon: <ShieldCheck className="h-4 w-4"/>},
];

export function ProgressTracker({events}: ProgressTrackerProps) {
    const [currentPhase, setCurrentPhase] = useState<Phase>('analyzing');
    const [completedPhases, setCompletedPhases] = useState<Set<Phase>>(new Set());
    const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set(['steps']));
    const [intent, setIntent] = useState<any>(null);
    const [plan, setPlan] = useState<any>(null);
    const [steps, setSteps] = useState<any[]>([]);
    const [validation, setValidation] = useState<any>(null);
    const [chunksCount, setChunksCount] = useState(0);
    const [error, setError] = useState<string | null>(null);

    // Process events
    useEffect(() => {
        if (events.length === 0) return;

        const latestEvent = events[events.length - 1];

        switch (latestEvent.event) {
            case 'intent_analyzed':
                setCurrentPhase('retrieving');
                setCompletedPhases((prev) => new Set([...prev, 'analyzing']));
                if (latestEvent.data.intent) {
                    setIntent(latestEvent.data.intent);
                }
                break;

            case 'context_retrieved':
                setCurrentPhase('planning');
                setCompletedPhases((prev) => new Set([...prev, 'analyzing', 'retrieving']));
                if (latestEvent.data.chunks_count) {
                    setChunksCount(latestEvent.data.chunks_count);
                }
                break;

            case 'planning_started':
                setCurrentPhase('planning');
                break;

            case 'plan_created':
                setCurrentPhase('executing');
                setCompletedPhases((prev) => new Set([...prev, 'analyzing', 'retrieving', 'planning']));
                if (latestEvent.data.plan) {
                    setPlan(latestEvent.data.plan);
                }
                break;

            case 'step_started':
                setCurrentPhase('executing');
                if (latestEvent.data.step) {
                    setSteps((prev) => {
                        const existing = prev.find((s) => s.order === latestEvent.data.step.order);
                        if (existing) {
                            return prev.map((s) =>
                                s.order === latestEvent.data.step.order
                                    ? {...s, status: 'running', fixing: latestEvent.data.fixing}
                                    : s
                            );
                        }
                        return [...prev, {...latestEvent.data.step, status: 'running'}];
                    });
                }
                break;

            case 'step_completed':
                if (latestEvent.data.step) {
                    setSteps((prev) =>
                        prev.map((s) =>
                            s.order === latestEvent.data.step.order
                                ? {...s, status: 'completed'}
                                : s
                        )
                    );
                }
                break;

            case 'validation_result':
                setCurrentPhase('validating');
                setCompletedPhases((prev) => new Set([...prev, 'analyzing', 'retrieving', 'planning', 'executing']));
                if (latestEvent.data.validation) {
                    setValidation(latestEvent.data.validation);
                }
                break;

            case 'complete':
                setCurrentPhase('complete');
                setCompletedPhases((prev) => new Set([...prev, 'analyzing', 'retrieving', 'planning', 'executing', 'validating']));
                if (latestEvent.data.validation) {
                    setValidation(latestEvent.data.validation);
                }
                break;

            case 'error':
                setCurrentPhase('error');
                setError(latestEvent.data.message || 'An error occurred');
                break;
        }
    }, [events]);

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

    const getPhaseStatus = (phase: Phase) => {
        if (error && currentPhase === 'error') return 'error';
        if (completedPhases.has(phase)) return 'completed';
        if (currentPhase === phase) return 'running';
        return 'pending';
    };

    return (
        <div className="flex h-full flex-col bg-gray-900/50 overflow-y-auto">
            {/* Header */}
            <div className="border-b border-gray-800 p-4">
                <div className="flex items-center gap-2">
                    <Sparkles className="h-5 w-5 text-purple-400"/>
                    <h2 className="font-semibold text-white">AI Progress</h2>
                </div>
            </div>

            {/* Phases */}
            <div className="p-4 space-y-2">
                {phases.map((phase) => {
                    const status = getPhaseStatus(phase.id);
                    return (
                        <div
                            key={phase.id}
                            className={`flex items-center gap-3 rounded-lg p-3 ${
                                status === 'running'
                                    ? 'bg-blue-500/10 border border-blue-500/30'
                                    : status === 'completed'
                                        ? 'bg-green-500/10'
                                        : 'bg-gray-800/50'
                            }`}
                        >
                            {/* Status icon */}
                            {status === 'completed' ? (
                                <CheckCircle2 className="h-5 w-5 text-green-500"/>
                            ) : status === 'running' ? (
                                <Loader2 className="h-5 w-5 text-blue-500 animate-spin"/>
                            ) : status === 'error' ? (
                                <AlertCircle className="h-5 w-5 text-red-500"/>
                            ) : (
                                <Circle className="h-5 w-5 text-gray-600"/>
                            )}

                            {/* Phase icon */}
                            <div
                                className={`${
                                    status === 'completed'
                                        ? 'text-green-400'
                                        : status === 'running'
                                            ? 'text-blue-400'
                                            : 'text-gray-500'
                                }`}
                            >
                                {phase.icon}
                            </div>

                            {/* Label */}
                            <span
                                className={`text-sm ${
                                    status === 'completed'
                                        ? 'text-green-400'
                                        : status === 'running'
                                            ? 'text-blue-400'
                                            : 'text-gray-500'
                                }`}
                            >
                {phase.label}
              </span>
                        </div>
                    );
                })}
            </div>

            {/* Error */}
            {error && (
                <div className="mx-4 mb-4 rounded-lg bg-red-500/10 border border-red-500/30 p-3">
                    <div className="flex items-center gap-2 text-red-400">
                        <AlertCircle className="h-4 w-4"/>
                        <span className="text-sm font-medium">Error</span>
                    </div>
                    <p className="mt-1 text-sm text-red-300">{error}</p>
                </div>
            )}

            {/* Intent Details */}
            {intent && (
                <CollapsibleSection
                    title="Intent"
                    expanded={expandedSections.has('intent')}
                    onToggle={() => toggleSection('intent')}
                >
                    <div className="space-y-2 text-sm">
                        <DetailRow label="Task Type" value={intent.task_type}/>
                        <DetailRow label="Scope" value={intent.scope}/>
                        {intent.domains_affected?.length > 0 && (
                            <DetailRow
                                label="Domains"
                                value={intent.domains_affected.join(', ')}
                            />
                        )}
                        {intent.requires_migration && (
                            <DetailRow label="Migration" value="Required"/>
                        )}
                    </div>
                </CollapsibleSection>
            )}

            {/* Context Stats */}
            {chunksCount > 0 && (
                <div className="mx-4 mb-4 rounded-lg bg-gray-800/50 p-3">
                    <div className="flex items-center gap-2 text-gray-400">
                        <FileCode className="h-4 w-4"/>
                        <span className="text-sm">Found {chunksCount} relevant code sections</span>
                    </div>
                </div>
            )}

            {/* Plan Steps */}
            {plan && plan.steps && plan.steps.length > 0 && (
                <CollapsibleSection
                    title={`Plan (${plan.steps.length} steps)`}
                    expanded={expandedSections.has('steps')}
                    onToggle={() => toggleSection('steps')}
                >
                    <div className="space-y-2">
                        {plan.steps.map((step: any, index: number) => {
                            const stepState = steps.find((s) => s.order === step.order);
                            const status = stepState?.status || 'pending';

                            return (
                                <div
                                    key={index}
                                    className={`flex items-start gap-2 rounded p-2 ${
                                        status === 'running'
                                            ? 'bg-blue-500/10'
                                            : status === 'completed'
                                                ? 'bg-green-500/10'
                                                : 'bg-gray-800/30'
                                    }`}
                                >
                                    {status === 'completed' ? (
                                        <CheckCircle2 className="h-4 w-4 text-green-500 shrink-0 mt-0.5"/>
                                    ) : status === 'running' ? (
                                        <Loader2 className="h-4 w-4 text-blue-500 animate-spin shrink-0 mt-0.5"/>
                                    ) : (
                                        <Circle className="h-4 w-4 text-gray-600 shrink-0 mt-0.5"/>
                                    )}
                                    <div className="min-w-0 flex-1">
                                        <div className="flex items-center gap-2">
                      <span
                          className={`text-xs font-medium px-1.5 py-0.5 rounded ${
                              step.action === 'create'
                                  ? 'bg-green-500/20 text-green-400'
                                  : step.action === 'modify'
                                      ? 'bg-yellow-500/20 text-yellow-400'
                                      : 'bg-red-500/20 text-red-400'
                          }`}
                      >
                        {step.action}
                      </span>
                                            {stepState?.fixing && (
                                                <span className="text-xs text-orange-400">fixing...</span>
                                            )}
                                        </div>
                                        <p className="text-sm text-gray-300 mt-1 truncate">{step.file}</p>
                                        <p className="text-xs text-gray-500 mt-0.5">{step.description}</p>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </CollapsibleSection>
            )}

            {/* Validation Result */}
            {validation && (
                <CollapsibleSection
                    title="Validation"
                    expanded={expandedSections.has('validation')}
                    onToggle={() => toggleSection('validation')}
                >
                    <div className="space-y-3">
                        {/* Score */}
                        <div className="flex items-center justify-between">
                            <span className="text-sm text-gray-400">Score</span>
                            <span
                                className={`text-lg font-bold ${
                                    validation.score >= 80
                                        ? 'text-green-400'
                                        : validation.score >= 60
                                            ? 'text-yellow-400'
                                            : 'text-red-400'
                                }`}
                            >
                {validation.score}/100
              </span>
                        </div>

                        {/* Status */}
                        <div className="flex items-center gap-2">
                            {validation.approved ? (
                                <>
                                    <CheckCircle2 className="h-4 w-4 text-green-500"/>
                                    <span className="text-sm text-green-400">Approved</span>
                                </>
                            ) : (
                                <>
                                    <AlertCircle className="h-4 w-4 text-yellow-500"/>
                                    <span className="text-sm text-yellow-400">Needs Review</span>
                                </>
                            )}
                        </div>

                        {/* Issues */}
                        {validation.issues?.length > 0 && (
                            <div className="space-y-1">
                                <span className="text-xs text-gray-500 uppercase">Issues</span>
                                {validation.issues.map((issue: any, i: number) => (
                                    <div
                                        key={i}
                                        className={`text-xs p-2 rounded ${
                                            issue.severity === 'error'
                                                ? 'bg-red-500/10 text-red-300'
                                                : issue.severity === 'warning'
                                                    ? 'bg-yellow-500/10 text-yellow-300'
                                                    : 'bg-gray-700 text-gray-300'
                                        }`}
                                    >
                                        {issue.message}
                                    </div>
                                ))}
                            </div>
                        )}

                        {/* Suggestions */}
                        {validation.suggestions?.length > 0 && (
                            <div className="space-y-1">
                                <span className="text-xs text-gray-500 uppercase">Suggestions</span>
                                {validation.suggestions.map((suggestion: string, i: number) => (
                                    <div key={i} className="text-xs text-gray-400 p-2 bg-gray-800/50 rounded">
                                        {suggestion}
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </CollapsibleSection>
            )}
        </div>
    );
}

// Collapsible section component
function CollapsibleSection({
                                title,
                                expanded,
                                onToggle,
                                children,
                            }: {
    title: string;
    expanded: boolean;
    onToggle: () => void;
    children: React.ReactNode;
}) {
    return (
        <div className="mx-4 mb-4 rounded-lg bg-gray-800/50 overflow-hidden">
            <button
                onClick={onToggle}
                className="flex w-full items-center justify-between p-3 text-left hover:bg-gray-800/70"
            >
                <span className="text-sm font-medium text-gray-300">{title}</span>
                {expanded ? (
                    <ChevronDown className="h-4 w-4 text-gray-500"/>
                ) : (
                    <ChevronRight className="h-4 w-4 text-gray-500"/>
                )}
            </button>
            {expanded && <div className="px-3 pb-3">{children}</div>}
        </div>
    );
}

// Detail row component
function DetailRow({label, value}: { label: string; value: string }) {
    return (
        <div className="flex items-center justify-between">
            <span className="text-gray-500">{label}</span>
            <span className="text-gray-300">{value}</span>
        </div>
    );
}
