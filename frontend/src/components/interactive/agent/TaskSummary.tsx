'use client';

import {useMemo, useState} from 'react';
import {
    Activity,
    CheckCircle,
    ChevronDown,
    ChevronUp,
    Clock,
    FileCode,
    GitPullRequest,
    Play,
    Star,
    XCircle,
} from 'lucide-react';
import {Button} from '@/components/ui/Button';
import {AgentBadge} from './AgentAvatar';
import {ScoreReveal} from './ValidationDisplay';
import {AgentTimeline, AgentType, Plan, ValidationResult,} from './types';

interface ExecutionResult {
    file: string;
    action: 'create' | 'modify' | 'delete';
    content?: string;
    diff?: string;
    success: boolean;
    error?: string;
}

interface TaskSummaryProps {
    success: boolean;
    summary?: string;
    plan?: Plan;
    executionResults?: ExecutionResult[];
    validation?: ValidationResult;
    agentTimeline?: AgentTimeline;
    error?: string;
    onApplyChanges?: () => void;
    onCreatePR?: () => void;
    onViewDetails?: () => void;
    className?: string;
}

export function TaskSummary({
                                success,
                                summary,
                                plan,
                                executionResults = [],
                                validation,
                                agentTimeline,
                                error,
                                onApplyChanges,
                                onCreatePR,
                                onViewDetails,
                                className = '',
                            }: TaskSummaryProps) {
    const [isExpanded, setIsExpanded] = useState(false);

    // Calculate stats
    const filesChanged = executionResults.length;
    const filesCreated = executionResults.filter((r) => r.action === 'create').length;
    const filesModified = executionResults.filter((r) => r.action === 'modify').length;
    const filesDeleted = executionResults.filter((r) => r.action === 'delete').length;

    // Format duration
    const formatDuration = (ms: number) => {
        if (ms < 1000) return `${ms}ms`;
        return `${(ms / 1000).toFixed(1)}s`;
    };

    // Agent timeline component
    const AgentTimelineDisplay = useMemo(() => {
        if (!agentTimeline?.timeline?.length) return null;

        return (
            <div className="flex items-center gap-1 text-xs overflow-x-auto">
                {agentTimeline.timeline.map((activity, index) => (
                    <div
                        key={`${activity.agentType}-${index}`}
                        className="flex items-center gap-1"
                    >
                        <AgentBadge agent={activity.agentType as AgentType}/>
                        {activity.durationMs && (
                            <span className="text-gray-500">
                {formatDuration(activity.durationMs)}
              </span>
                        )}
                        {index < agentTimeline.timeline.length - 1 && (
                            <span className="text-gray-600 mx-1">→</span>
                        )}
                    </div>
                ))}
            </div>
        );
    }, [agentTimeline]);

    return (
        <div
            className={`
        rounded-lg border overflow-hidden
        ${success
                ? 'border-green-500/30 bg-green-500/5'
                : 'border-red-500/30 bg-red-500/5'
            }
        ${className}
      `}
        >
            {/* Header */}
            <div className="px-4 py-3 bg-gray-800/30 border-b border-gray-700/50">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        {success ? (
                            <CheckCircle className="h-6 w-6 text-green-400"/>
                        ) : (
                            <XCircle className="h-6 w-6 text-red-400"/>
                        )}
                        <div>
                            <h4 className={`text-sm font-medium ${success ? 'text-green-400' : 'text-red-400'}`}>
                                {success ? 'Task Completed Successfully' : 'Task Failed'}
                            </h4>
                            {summary && (
                                <p className="text-xs text-gray-500 mt-0.5">{summary}</p>
                            )}
                        </div>
                    </div>

                    {/* Quality Score */}
                    {validation && (
                        <div className="flex items-center gap-2">
                            <Star className="h-4 w-4 text-yellow-400"/>
                            <ScoreReveal
                                score={validation.score}
                                animated={true}
                                size="sm"
                                showLabel={false}
                            />
                        </div>
                    )}
                </div>
            </div>

            {/* Quick Stats */}
            <div className="px-4 py-3 grid grid-cols-2 md:grid-cols-4 gap-4 border-b border-gray-700/30">
                {/* Files Changed */}
                <div className="flex items-center gap-2">
                    <FileCode className="h-4 w-4 text-gray-500"/>
                    <div>
                        <p className="text-sm font-medium text-white">{filesChanged}</p>
                        <p className="text-xs text-gray-500">Files Changed</p>
                    </div>
                </div>

                {/* Files Breakdown */}
                <div className="flex items-center gap-2">
                    <div className="flex gap-1">
                        {filesCreated > 0 && (
                            <span className="text-xs px-1.5 py-0.5 rounded bg-green-500/20 text-green-400">
                +{filesCreated}
              </span>
                        )}
                        {filesModified > 0 && (
                            <span className="text-xs px-1.5 py-0.5 rounded bg-yellow-500/20 text-yellow-400">
                ~{filesModified}
              </span>
                        )}
                        {filesDeleted > 0 && (
                            <span className="text-xs px-1.5 py-0.5 rounded bg-red-500/20 text-red-400">
                -{filesDeleted}
              </span>
                        )}
                    </div>
                </div>

                {/* Duration */}
                {agentTimeline && (
                    <div className="flex items-center gap-2">
                        <Clock className="h-4 w-4 text-gray-500"/>
                        <div>
                            <p className="text-sm font-medium text-white">
                                {formatDuration(agentTimeline.totalDurationMs)}
                            </p>
                            <p className="text-xs text-gray-500">Total Time</p>
                        </div>
                    </div>
                )}

                {/* Validation Score */}
                {validation && (
                    <div className="flex items-center gap-2">
                        <Activity className="h-4 w-4 text-gray-500"/>
                        <div>
                            <p className="text-sm font-medium text-white">{validation.score}/100</p>
                            <p className="text-xs text-gray-500">Quality Score</p>
                        </div>
                    </div>
                )}
            </div>

            {/* Agent Activity Timeline */}
            {agentTimeline && (
                <div className="px-4 py-2 border-b border-gray-700/30 bg-gray-800/20">
                    <div className="flex items-center gap-2 mb-2">
                        <Activity className="h-3 w-3 text-gray-500"/>
                        <span className="text-xs text-gray-500">Agent Activity:</span>
                    </div>
                    {AgentTimelineDisplay}
                </div>
            )}

            {/* Expandable Details */}
            {(executionResults.length > 0 || error) && (
                <div
                    className="px-4 py-2 cursor-pointer hover:bg-gray-800/30 transition-colors flex items-center justify-between"
                    onClick={() => setIsExpanded(!isExpanded)}
                >
          <span className="text-xs text-gray-400">
            {isExpanded ? 'Hide Details' : 'View Details'}
          </span>
                    {isExpanded ? (
                        <ChevronUp className="h-4 w-4 text-gray-500"/>
                    ) : (
                        <ChevronDown className="h-4 w-4 text-gray-500"/>
                    )}
                </div>
            )}

            {isExpanded && (
                <div className="px-4 py-3 space-y-3 border-t border-gray-700/30">
                    {/* Error */}
                    {error && (
                        <div className="p-3 rounded bg-red-500/10 border border-red-500/30">
                            <p className="text-sm text-red-400">{error}</p>
                        </div>
                    )}

                    {/* Files List */}
                    {executionResults.length > 0 && (
                        <div className="space-y-2">
                            <h5 className="text-xs font-medium text-gray-400">Files Changed:</h5>
                            {executionResults.map((result, index) => (
                                <div
                                    key={index}
                                    className={`
                    flex items-center gap-2 px-2 py-1.5 rounded text-xs
                    ${result.action === 'create'
                                        ? 'bg-green-500/10 text-green-400'
                                        : result.action === 'modify'
                                            ? 'bg-yellow-500/10 text-yellow-400'
                                            : 'bg-red-500/10 text-red-400'
                                    }
                  `}
                                >
                  <span className="px-1 py-0.5 rounded bg-gray-800/50 text-[10px] uppercase">
                    {result.action}
                  </span>
                                    <span className="font-mono truncate">{result.file}</span>
                                    {result.success ? (
                                        <CheckCircle className="h-3 w-3 ml-auto flex-shrink-0"/>
                                    ) : (
                                        <XCircle className="h-3 w-3 ml-auto flex-shrink-0 text-red-400"/>
                                    )}
                                </div>
                            ))}
                        </div>
                    )}

                    {/* Validation Issues Summary */}
                    {validation && validation.issues.length > 0 && (
                        <div className="space-y-2">
                            <h5 className="text-xs font-medium text-gray-400">
                                {validation.issues.length} Issue{validation.issues.length !== 1 ? 's' : ''} Found
                            </h5>
                            <ul className="space-y-1">
                                {validation.issues.slice(0, 5).map((issue, index) => (
                                    <li
                                        key={index}
                                        className={`
                      text-xs flex items-start gap-2
                      ${issue.severity === 'error'
                                            ? 'text-red-400'
                                            : issue.severity === 'warning'
                                                ? 'text-yellow-400'
                                                : 'text-blue-400'
                                        }
                    `}
                                    >
                                        <span className="text-gray-600">•</span>
                                        {issue.message}
                                    </li>
                                ))}
                                {validation.issues.length > 5 && (
                                    <li className="text-xs text-gray-500">
                                        ...and {validation.issues.length - 5} more
                                    </li>
                                )}
                            </ul>
                        </div>
                    )}
                </div>
            )}

            {/* Actions */}
            {success && (onApplyChanges || onCreatePR || onViewDetails) && (
                <div
                    className="px-4 py-3 bg-gray-800/30 border-t border-gray-700/50 flex items-center justify-end gap-2">
                    {onViewDetails && (
                        <Button
                            size="sm"
                            variant="ghost"
                            onClick={onViewDetails}
                        >
                            View Full Details
                        </Button>
                    )}
                    {onApplyChanges && (
                        <Button
                            size="sm"
                            variant="ghost"
                            onClick={onApplyChanges}
                        >
                            <Play className="h-4 w-4 mr-1"/>
                            Apply Changes
                        </Button>
                    )}
                    {onCreatePR && (
                        <Button
                            size="sm"
                            onClick={onCreatePR}
                        >
                            <GitPullRequest className="h-4 w-4 mr-1"/>
                            Create PR
                        </Button>
                    )}
                </div>
            )}
        </div>
    );
}

export default TaskSummary;
