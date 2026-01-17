'use client';

import { useState, useEffect, useMemo } from 'react';
import {
  Brain,
  Search,
  FileCode,
  CheckCircle2,
  Circle,
  Loader2,
  AlertCircle,
  ChevronDown,
  ChevronRight,
  Sparkles,
  ClipboardList,
  Play,
  ShieldCheck,
  FilePlus,
  FileEdit,
  FileX,
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
  { id: 'analyzing', label: 'Analyzed Intent', activeLabel: 'Analyzing Intent...', icon: <Brain className="h-4 w-4" /> },
  { id: 'retrieving', label: 'Retrieved Context', activeLabel: 'Retrieving Context...', icon: <Search className="h-4 w-4" /> },
  { id: 'planning', label: 'Created Plan', activeLabel: 'Creating Plan...', icon: <ClipboardList className="h-4 w-4" /> },
  { id: 'executing', label: 'Executed Steps', activeLabel: 'Executing Steps...', icon: <Play className="h-4 w-4" /> },
  { id: 'validating', label: 'Validated Code', activeLabel: 'Validating Code...', icon: <ShieldCheck className="h-4 w-4" /> },
];

export function InlineProgress({ events, isProcessing }: InlineProgressProps) {
  const [currentPhase, setCurrentPhase] = useState<Phase>('analyzing');
  const [completedPhases, setCompletedPhases] = useState<Set<Phase>>(new Set());
  const [intent, setIntent] = useState<any>(null);
  const [plan, setPlan] = useState<any>(null);
  const [steps, setSteps] = useState<any[]>([]);
  const [validation, setValidation] = useState<any>(null);
  const [chunksCount, setChunksCount] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [expandedSteps, setExpandedSteps] = useState(true);

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
                    ? { ...s, status: 'running', fixing: event.data.fixing }
                    : s
                );
              }
              return [...prev, { ...event.data.step, status: 'running' }];
            });
          }
          break;

        case 'step_completed':
          if (event.data.step) {
            setSteps((prev) =>
              prev.map((s) =>
                s.order === event.data.step.order
                  ? { ...s, status: 'completed' }
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
        return <FilePlus className="h-3.5 w-3.5 text-green-400" />;
      case 'modify':
        return <FileEdit className="h-3.5 w-3.5 text-yellow-400" />;
      case 'delete':
        return <FileX className="h-3.5 w-3.5 text-red-400" />;
      default:
        return <FileCode className="h-3.5 w-3.5 text-gray-400" />;
    }
  };

  return (
    <div className="rounded-xl bg-gray-800/60 border border-gray-700/50 overflow-hidden">
      {/* Header with progress bar */}
      <div className="px-4 py-3 border-b border-gray-700/50">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-purple-400" />
            <span className="text-sm font-medium text-white">AI Processing</span>
          </div>
          <span className="text-xs text-gray-400">{overallProgress}%</span>
        </div>
        {/* Progress bar */}
        <div className="h-1.5 bg-gray-700 rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-blue-500 to-purple-500 transition-all duration-300 ease-out"
            style={{ width: `${overallProgress}%` }}
          />
        </div>
        {/* Current message */}
        <p className="text-xs text-gray-400 mt-2 truncate">{currentMessage}</p>
      </div>

      {/* Phases */}
      <div className="px-4 py-3 space-y-1.5">
        {phases.map((phase) => {
          const status = getPhaseStatus(phase.id);
          if (status === 'pending') return null;

          return (
            <div
              key={phase.id}
              className={`flex items-center gap-2 rounded-lg px-3 py-2 text-sm ${
                status === 'running'
                  ? 'bg-blue-500/10 border border-blue-500/30'
                  : status === 'completed'
                  ? 'bg-gray-700/30'
                  : ''
              }`}
            >
              {/* Status icon */}
              {status === 'completed' ? (
                <CheckCircle2 className="h-4 w-4 text-green-500 shrink-0" />
              ) : status === 'running' ? (
                <Loader2 className="h-4 w-4 text-blue-400 animate-spin shrink-0" />
              ) : status === 'error' ? (
                <AlertCircle className="h-4 w-4 text-red-500 shrink-0" />
              ) : (
                <Circle className="h-4 w-4 text-gray-600 shrink-0" />
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
                className={`${
                  status === 'completed'
                    ? 'text-gray-300'
                    : status === 'running'
                    ? 'text-blue-300'
                    : 'text-gray-500'
                }`}
              >
                {status === 'running' ? phase.activeLabel : phase.label}
              </span>

              {/* Additional info */}
              {phase.id === 'analyzing' && status === 'completed' && intent && (
                <span className="ml-auto text-xs text-gray-500">
                  {intent.task_type}
                </span>
              )}
              {phase.id === 'retrieving' && status === 'completed' && chunksCount > 0 && (
                <span className="ml-auto text-xs text-gray-500">
                  {chunksCount} files
                </span>
              )}
              {phase.id === 'planning' && status === 'completed' && plan?.steps && (
                <span className="ml-auto text-xs text-gray-500">
                  {plan.steps.length} steps
                </span>
              )}
            </div>
          );
        })}
      </div>

      {/* Execution Steps */}
      {steps.length > 0 && (
        <div className="border-t border-gray-700/50">
          <button
            onClick={() => setExpandedSteps(!expandedSteps)}
            className="w-full px-4 py-2 flex items-center justify-between text-sm text-gray-400 hover:bg-gray-700/30"
          >
            <span className="flex items-center gap-2">
              <Play className="h-3.5 w-3.5" />
              Execution Steps ({steps.filter(s => s.status === 'completed').length}/{steps.length})
            </span>
            {expandedSteps ? (
              <ChevronDown className="h-4 w-4" />
            ) : (
              <ChevronRight className="h-4 w-4" />
            )}
          </button>

          {expandedSteps && (
            <div className="px-4 pb-3 space-y-1">
              {steps.map((step, index) => (
                <div
                  key={index}
                  className={`flex items-center gap-2 rounded px-2 py-1.5 text-xs ${
                    step.status === 'running'
                      ? 'bg-blue-500/10'
                      : step.status === 'completed'
                      ? 'bg-gray-700/20'
                      : 'bg-gray-800/30'
                  }`}
                >
                  {step.status === 'completed' ? (
                    <CheckCircle2 className="h-3.5 w-3.5 text-green-500 shrink-0" />
                  ) : step.status === 'running' ? (
                    <Loader2 className="h-3.5 w-3.5 text-blue-400 animate-spin shrink-0" />
                  ) : (
                    <Circle className="h-3.5 w-3.5 text-gray-600 shrink-0" />
                  )}

                  {getActionIcon(step.action)}

                  <span className="text-gray-400 truncate flex-1">
                    {step.file?.split('/').pop() || step.description}
                  </span>

                  {step.fixing && (
                    <span className="text-orange-400 text-[10px] shrink-0">fixing...</span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Validation Result */}
      {validation && (
        <div className="border-t border-gray-700/50 px-4 py-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              {validation.approved ? (
                <>
                  <CheckCircle2 className="h-4 w-4 text-green-500" />
                  <span className="text-sm text-green-400">Validated</span>
                </>
              ) : (
                <>
                  <AlertCircle className="h-4 w-4 text-yellow-500" />
                  <span className="text-sm text-yellow-400">Needs Review</span>
                </>
              )}
            </div>
            <span
              className={`text-sm font-medium ${
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

          {validation.issues?.length > 0 && (
            <div className="mt-2 space-y-1">
              {validation.issues.slice(0, 3).map((issue: any, i: number) => (
                <div
                  key={i}
                  className={`text-xs px-2 py-1 rounded ${
                    issue.severity === 'error'
                      ? 'bg-red-500/10 text-red-300'
                      : 'bg-yellow-500/10 text-yellow-300'
                  }`}
                >
                  {issue.message}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="border-t border-red-500/30 bg-red-500/10 px-4 py-3">
          <div className="flex items-center gap-2 text-red-400">
            <AlertCircle className="h-4 w-4" />
            <span className="text-sm">{error}</span>
          </div>
        </div>
      )}
    </div>
  );
}
