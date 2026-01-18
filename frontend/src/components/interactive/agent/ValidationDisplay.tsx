'use client';

import {useEffect, useMemo, useState} from 'react';
import {
    AlertCircle,
    AlertTriangle,
    CheckCircle,
    ChevronDown,
    ChevronRight,
    FileCode,
    Info,
    Lightbulb,
    ShieldAlert,
    ShieldCheck,
} from 'lucide-react';
import {IssueSeverity, ValidationIssue, ValidationResult} from './types';

// Severity styles
const SEVERITY_STYLES: Record<IssueSeverity, {
    icon: typeof AlertCircle;
    iconClass: string;
    bgClass: string;
    borderClass: string;
    textClass: string;
    label: string;
}> = {
    error: {
        icon: AlertCircle,
        iconClass: 'text-red-400',
        bgClass: 'bg-red-500/10',
        borderClass: 'border-red-500/30',
        textClass: 'text-red-400',
        label: 'Error',
    },
    warning: {
        icon: AlertTriangle,
        iconClass: 'text-yellow-400',
        bgClass: 'bg-yellow-500/10',
        borderClass: 'border-yellow-500/30',
        textClass: 'text-yellow-400',
        label: 'Warning',
    },
    info: {
        icon: Info,
        iconClass: 'text-blue-400',
        bgClass: 'bg-blue-500/10',
        borderClass: 'border-blue-500/30',
        textClass: 'text-blue-400',
        label: 'Info',
    },
};

interface ValidationIssueCardProps {
    issue: ValidationIssue;
    animated?: boolean;
    className?: string;
}

export function ValidationIssueCard({
                                        issue,
                                        animated = false,
                                        className = '',
                                    }: ValidationIssueCardProps) {
    const style = SEVERITY_STYLES[issue.severity];
    const IconComponent = style.icon;

    return (
        <div
            className={`
        rounded-lg border p-3
        ${style.bgClass} ${style.borderClass}
        ${animated ? 'animate-slideIn' : ''}
        ${className}
      `}
        >
            <div className="flex items-start gap-3">
                {/* Severity Icon */}
                <IconComponent className={`h-5 w-5 flex-shrink-0 mt-0.5 ${style.iconClass}`}/>

                {/* Content */}
                <div className="flex-1 min-w-0">
                    {/* Severity badge */}
                    <span className={`text-xs font-medium ${style.textClass}`}>
            {style.label}
          </span>

                    {/* File and line */}
                    <div className="flex items-center gap-2 mt-1">
                        <FileCode className="h-3 w-3 text-gray-500"/>
                        <span className="text-xs font-mono text-gray-400">
              {issue.file}
                            {issue.line && `:${issue.line}`}
            </span>
                    </div>

                    {/* Message */}
                    <p className="text-sm text-gray-300 mt-1">
                        {issue.message}
                    </p>

                    {/* Suggestion */}
                    {issue.suggestion && (
                        <div className="flex items-start gap-2 mt-2 p-2 rounded bg-gray-800/50">
                            <Lightbulb className="h-4 w-4 text-yellow-400 flex-shrink-0 mt-0.5"/>
                            <p className="text-xs text-gray-400">
                                <span className="text-gray-500">Fix:</span> {issue.suggestion}
                            </p>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}

interface ValidationIssueListProps {
    issues: ValidationIssue[];
    title?: string;
    showCount?: boolean;
    defaultExpanded?: boolean;
    animateEntries?: boolean;
    className?: string;
}

export function ValidationIssueList({
                                        issues,
                                        title = 'Issues',
                                        showCount = true,
                                        defaultExpanded = true,
                                        animateEntries = false,
                                        className = '',
                                    }: ValidationIssueListProps) {
    const [isExpanded, setIsExpanded] = useState(defaultExpanded);

    // Group issues by severity
    const groupedIssues = useMemo(() => {
        const groups: Record<IssueSeverity, ValidationIssue[]> = {
            error: [],
            warning: [],
            info: [],
        };
        issues.forEach((issue) => {
            groups[issue.severity].push(issue);
        });
        return groups;
    }, [issues]);

    const errorCount = groupedIssues.error.length;
    const warningCount = groupedIssues.warning.length;
    const infoCount = groupedIssues.info.length;

    if (issues.length === 0) {
        return null;
    }

    return (
        <div className={`rounded-lg border border-gray-700 overflow-hidden ${className}`}>
            {/* Header */}
            <div
                className="flex items-center justify-between px-3 py-2 bg-gray-800/50 cursor-pointer hover:bg-gray-800/70 transition-colors"
                onClick={() => setIsExpanded(!isExpanded)}
            >
                <div className="flex items-center gap-3">
                    {isExpanded ? (
                        <ChevronDown className="h-4 w-4 text-gray-500"/>
                    ) : (
                        <ChevronRight className="h-4 w-4 text-gray-500"/>
                    )}
                    <span className="text-sm font-medium text-gray-300">{title}</span>

                    {showCount && (
                        <div className="flex items-center gap-2">
                            {errorCount > 0 && (
                                <span className="text-xs px-1.5 py-0.5 rounded bg-red-500/20 text-red-400">
                  {errorCount} error{errorCount !== 1 ? 's' : ''}
                </span>
                            )}
                            {warningCount > 0 && (
                                <span className="text-xs px-1.5 py-0.5 rounded bg-yellow-500/20 text-yellow-400">
                  {warningCount} warning{warningCount !== 1 ? 's' : ''}
                </span>
                            )}
                            {infoCount > 0 && (
                                <span className="text-xs px-1.5 py-0.5 rounded bg-blue-500/20 text-blue-400">
                  {infoCount} info
                </span>
                            )}
                        </div>
                    )}
                </div>
            </div>

            {/* Issues */}
            {isExpanded && (
                <div className="p-3 space-y-2">
                    {/* Errors first, then warnings, then info */}
                    {groupedIssues.error.map((issue, index) => (
                        <ValidationIssueCard
                            key={`error-${index}`}
                            issue={issue}
                            animated={animateEntries}
                        />
                    ))}
                    {groupedIssues.warning.map((issue, index) => (
                        <ValidationIssueCard
                            key={`warning-${index}`}
                            issue={issue}
                            animated={animateEntries}
                        />
                    ))}
                    {groupedIssues.info.map((issue, index) => (
                        <ValidationIssueCard
                            key={`info-${index}`}
                            issue={issue}
                            animated={animateEntries}
                        />
                    ))}
                </div>
            )}
        </div>
    );
}

interface ScoreRevealProps {
    score: number;
    maxScore?: number;
    animated?: boolean;
    animationDuration?: number;
    showLabel?: boolean;
    size?: 'sm' | 'md' | 'lg';
    className?: string;
}

export function ScoreReveal({
                                score,
                                maxScore = 100,
                                animated = true,
                                animationDuration = 1500,
                                showLabel = true,
                                size = 'md',
                                className = '',
                            }: ScoreRevealProps) {
    const [displayScore, setDisplayScore] = useState(animated ? 0 : score);
    const [hasAnimated, setHasAnimated] = useState(!animated);

    // Animate score count up
    useEffect(() => {
        if (!animated || hasAnimated) {
            setDisplayScore(score);
            return;
        }

        const startTime = Date.now();
        const startScore = 0;

        const animate = () => {
            const elapsed = Date.now() - startTime;
            const progress = Math.min(elapsed / animationDuration, 1);

            // Ease out cubic
            const easeOut = 1 - Math.pow(1 - progress, 3);
            const currentScore = Math.round(startScore + (score - startScore) * easeOut);

            setDisplayScore(currentScore);

            if (progress < 1) {
                requestAnimationFrame(animate);
            } else {
                setHasAnimated(true);
            }
        };

        requestAnimationFrame(animate);
    }, [score, animated, animationDuration, hasAnimated]);

    // Calculate score percentage
    const percentage = (displayScore / maxScore) * 100;

    // Determine color based on score
    const getScoreColor = (score: number) => {
        if (score >= 90) return 'text-green-400';
        if (score >= 70) return 'text-yellow-400';
        if (score >= 50) return 'text-orange-400';
        return 'text-red-400';
    };

    const getBarColor = (score: number) => {
        if (score >= 90) return 'bg-green-500';
        if (score >= 70) return 'bg-yellow-500';
        if (score >= 50) return 'bg-orange-500';
        return 'bg-red-500';
    };

    const getLabel = (score: number) => {
        if (score >= 90) return 'Excellent';
        if (score >= 70) return 'Good';
        if (score >= 50) return 'Fair';
        return 'Needs Work';
    };

    // Size classes
    const sizeClasses = {
        sm: {
            score: 'text-2xl',
            label: 'text-xs',
            bar: 'h-1.5',
        },
        md: {
            score: 'text-4xl',
            label: 'text-sm',
            bar: 'h-2',
        },
        lg: {
            score: 'text-6xl',
            label: 'text-base',
            bar: 'h-3',
        },
    };

    const classes = sizeClasses[size];

    return (
        <div className={`${className}`}>
            {/* Score number */}
            <div className="flex items-baseline gap-2">
        <span
            className={`font-bold tabular-nums ${classes.score} ${getScoreColor(displayScore)} ${hasAnimated ? 'animate-countUp' : ''}`}
        >
          {displayScore}
        </span>
                <span className={`text-gray-500 ${classes.label}`}>/ {maxScore}</span>
            </div>

            {/* Progress bar */}
            <div className={`mt-2 bg-gray-700 rounded-full overflow-hidden ${classes.bar}`}>
                <div
                    className={`h-full transition-all duration-500 ease-out rounded-full ${getBarColor(displayScore)}`}
                    style={{width: `${percentage}%`}}
                />
            </div>

            {/* Label */}
            {showLabel && (
                <p className={`mt-1 ${classes.label} ${getScoreColor(displayScore)}`}>
                    {getLabel(displayScore)}
                </p>
            )}
        </div>
    );
}

interface ValidationResultDisplayProps {
    validation: ValidationResult;
    animated?: boolean;
    showIssues?: boolean;
    className?: string;
}

export function ValidationResultDisplay({
                                            validation,
                                            animated = true,
                                            showIssues = true,
                                            className = '',
                                        }: ValidationResultDisplayProps) {
    const {approved, score, issues, suggestions, summary} = validation;

    return (
        <div
            className={`
        rounded-lg border overflow-hidden
        ${approved
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
                        {approved ? (
                            <ShieldCheck className="h-6 w-6 text-green-400"/>
                        ) : (
                            <ShieldAlert className="h-6 w-6 text-red-400"/>
                        )}
                        <div>
                            <h4 className={`text-sm font-medium ${approved ? 'text-green-400' : 'text-red-400'}`}>
                                Validation {approved ? 'Passed' : 'Failed'}
                            </h4>
                            <p className="text-xs text-gray-500">{summary}</p>
                        </div>
                    </div>

                    {/* Score */}
                    <ScoreReveal
                        score={score}
                        animated={animated}
                        size="sm"
                        showLabel={false}
                    />
                </div>
            </div>

            {/* Content */}
            <div className="p-4 space-y-4">
                {/* Issues */}
                {showIssues && issues.length > 0 && (
                    <ValidationIssueList
                        issues={issues}
                        title={`${issues.length} Issue${issues.length !== 1 ? 's' : ''} Found`}
                        defaultExpanded={!approved}
                        animateEntries={animated}
                    />
                )}

                {/* Suggestions */}
                {suggestions.length > 0 && (
                    <div className="space-y-2">
                        <h5 className="text-xs font-medium text-gray-400 flex items-center gap-2">
                            <Lightbulb className="h-4 w-4"/>
                            Suggestions
                        </h5>
                        <ul className="space-y-1">
                            {suggestions.map((suggestion, index) => (
                                <li key={index} className="text-xs text-gray-500 flex items-start gap-2">
                                    <span className="text-gray-600">•</span>
                                    {suggestion}
                                </li>
                            ))}
                        </ul>
                    </div>
                )}

                {/* All clear message */}
                {approved && issues.length === 0 && (
                    <div className="flex items-center gap-2 text-green-400 animate-success">
                        <CheckCircle className="h-5 w-5 animate-checkmark"/>
                        <span className="text-sm">All checks passed!</span>
                    </div>
                )}
            </div>
        </div>
    );
}

export default ValidationResultDisplay;
