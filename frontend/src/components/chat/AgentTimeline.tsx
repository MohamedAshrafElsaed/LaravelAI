'use client';

import React, {useMemo} from 'react';
import {AnimatePresence, motion} from 'framer-motion';
import {AlertCircle, ArrowRight, CheckCircle, FileCode, Info, Loader2} from 'lucide-react';
import type {AgentThinkingState, AgentType, ConversationEntry} from './types';
import {AGENT_CONFIG, AgentAvatar, AgentBadge, AgentThinking} from './AgentBadge';

// ============== AGENT TIMELINE ==============
interface AgentTimelineProps {
    entries: ConversationEntry[];
    currentThinking: AgentThinkingState | null;
    compact?: boolean;
    maxEntries?: number;
}

export function AgentTimeline({entries, currentThinking, compact = false, maxEntries}: AgentTimelineProps) {
    const displayEntries = useMemo(() => {
        if (maxEntries && entries.length > maxEntries) {
            return entries.slice(-maxEntries);
        }
        return entries;
    }, [entries, maxEntries]);

    if (displayEntries.length === 0 && !currentThinking) {
        return null;
    }

    return (
        <div
            className={`rounded-xl border border-[var(--color-border-subtle)] bg-[var(--color-bg-elevated)] overflow-hidden ${compact ? 'text-xs' : ''}`}>
            {/* Header */}
            <div
                className="flex items-center justify-between px-4 py-2 border-b border-[var(--color-border-subtle)] bg-[var(--color-bg-surface)]">
                <div className="flex items-center gap-2">
                    <div className="flex -space-x-1">
                        {getUniqueAgents(displayEntries).map((agent) => (
                            <AgentAvatar key={agent} agent={agent} size="sm"/>
                        ))}
                    </div>
                    <span className="text-sm font-medium text-[var(--color-text-secondary)]">
            Agent Activity
          </span>
                </div>
                <span className="text-xs text-[var(--color-text-muted)]">
          {displayEntries.length} events
        </span>
            </div>

            {/* Timeline */}
            <div className={`p-3 space-y-2 ${compact ? 'max-h-48' : 'max-h-64'} overflow-y-auto`}>
                <AnimatePresence mode="popLayout">
                    {displayEntries.map((entry, index) => (
                        <TimelineEntry key={entry.id} entry={entry}
                                       isLast={index === displayEntries.length - 1 && !currentThinking}
                                       compact={compact}/>
                    ))}

                    {/* Current thinking */}
                    {currentThinking && (
                        <motion.div
                            key="thinking"
                            initial={{opacity: 0, y: 10}}
                            animate={{opacity: 1, y: 0}}
                            exit={{opacity: 0, y: -10}}
                        >
                            <AgentThinking
                                agent={currentThinking.agent.type}
                                thought={currentThinking.thought}
                                actionType={currentThinking.actionType}
                                filePath={currentThinking.filePath}
                                progress={currentThinking.progress}
                            />
                        </motion.div>
                    )}
                </AnimatePresence>
            </div>
        </div>
    );
}

// ============== TIMELINE ENTRY ==============
interface TimelineEntryProps {
    entry: ConversationEntry;
    isLast: boolean;
    compact?: boolean;
}

function TimelineEntry({entry, isLast, compact = false}: TimelineEntryProps) {
    const formatTime = (timestamp: string) => {
        const date = new Date(timestamp);
        return date.toLocaleTimeString('en-US', {
            hour12: false,
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
        });
    };

    switch (entry.type) {
        case 'message':
            return (
                <motion.div
                    initial={{opacity: 0, x: -10}}
                    animate={{opacity: 1, x: 0}}
                    exit={{opacity: 0, x: 10}}
                    className="flex items-start gap-2"
                >
                    {entry.agentType && <AgentAvatar agent={entry.agentType} size="sm"/>}
                    <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                            {entry.agentType && (
                                <span
                                    className={`font-medium text-sm ${AGENT_CONFIG[entry.agentType]?.color || 'text-gray-400'}`}>
                  {AGENT_CONFIG[entry.agentType]?.name || entry.agentType}
                </span>
                            )}
                            {entry.toAgentType && (
                                <>
                                    <ArrowRight className="h-3 w-3 text-[var(--color-text-muted)]"/>
                                    <span
                                        className={`font-medium text-sm ${AGENT_CONFIG[entry.toAgentType]?.color || 'text-gray-400'}`}>
                    {AGENT_CONFIG[entry.toAgentType]?.name || entry.toAgentType}
                  </span>
                                </>
                            )}
                            <span className="text-xs text-[var(--color-text-muted)]">
                {formatTime(entry.timestamp)}
              </span>
                        </div>
                        <p className={`text-[var(--color-text-secondary)] ${compact ? 'text-xs line-clamp-1' : 'text-sm'}`}>
                            {entry.message}
                        </p>
                    </div>
                </motion.div>
            );

        case 'handoff':
            return (
                <motion.div
                    initial={{opacity: 0, scale: 0.95}}
                    animate={{opacity: 1, scale: 1}}
                    exit={{opacity: 0, scale: 0.95}}
                    className="flex items-center gap-2 py-1"
                >
                    {entry.agentType && <AgentBadge agent={entry.agentType} size="sm" showName={!compact}/>}
                    <ArrowRight className="h-3 w-3 text-[var(--color-text-muted)]"/>
                    {entry.toAgentType && <AgentBadge agent={entry.toAgentType} size="sm" showName={!compact}/>}
                    {!compact && entry.message && (
                        <span className="text-xs text-[var(--color-text-muted)] truncate">
              {entry.message}
            </span>
                    )}
                </motion.div>
            );

        case 'step':
            return (
                <motion.div
                    initial={{opacity: 0, y: 5}}
                    animate={{opacity: 1, y: 0}}
                    exit={{opacity: 0, y: -5}}
                    className={`flex items-start gap-2 p-2 rounded-lg ${
                        entry.completed
                            ? 'bg-green-500/10 border border-green-500/20'
                            : 'bg-amber-500/10 border border-amber-500/20'
                    }`}
                >
                    <div className="mt-0.5">
                        {entry.completed ? (
                            <CheckCircle className="h-4 w-4 text-green-400"/>
                        ) : (
                            <Loader2 className="h-4 w-4 text-amber-400 animate-spin"/>
                        )}
                    </div>
                    <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                            {entry.actionType && (
                                <span
                                    className={`px-1.5 py-0.5 rounded text-xs font-medium ${getActionColor(entry.actionType)}`}>
                  {entry.actionType}
                </span>
                            )}
                            {entry.filePath && (
                                <span className="text-xs text-blue-400 truncate flex items-center gap-1">
                  <FileCode className="h-3 w-3"/>
                                    {entry.filePath}
                </span>
                            )}
                        </div>
                        {!compact && entry.message && (
                            <p className="text-xs text-[var(--color-text-muted)] mt-1">{entry.message}</p>
                        )}
                    </div>
                </motion.div>
            );

        case 'system':
            return (
                <motion.div
                    initial={{opacity: 0}}
                    animate={{opacity: 1}}
                    exit={{opacity: 0}}
                    className={`flex items-center gap-2 py-1 px-2 rounded-lg text-xs ${getSystemTypeStyles(entry.systemType)}`}
                >
                    {getSystemIcon(entry.systemType)}
                    <span>{entry.message}</span>
                </motion.div>
            );

        default:
            return null;
    }
}

// ============== HELPERS ==============
function getUniqueAgents(entries: ConversationEntry[]): AgentType[] {
    const agents = new Set<AgentType>();
    entries.forEach((entry) => {
        if (entry.agentType) agents.add(entry.agentType);
        if (entry.toAgentType) agents.add(entry.toAgentType);
    });
    return Array.from(agents);
}

function getActionColor(action?: string): string {
    switch (action) {
        case 'create':
            return 'bg-green-500/20 text-green-400';
        case 'modify':
            return 'bg-amber-500/20 text-amber-400';
        case 'delete':
            return 'bg-red-500/20 text-red-400';
        case 'analyze':
            return 'bg-blue-500/20 text-blue-400';
        default:
            return 'bg-gray-500/20 text-gray-400';
    }
}

function getSystemTypeStyles(type?: string): string {
    switch (type) {
        case 'success':
            return 'bg-green-500/10 text-green-400 border border-green-500/20';
        case 'warning':
            return 'bg-amber-500/10 text-amber-400 border border-amber-500/20';
        case 'error':
            return 'bg-red-500/10 text-red-400 border border-red-500/20';
        case 'info':
        default:
            return 'bg-blue-500/10 text-blue-400 border border-blue-500/20';
    }
}

function getSystemIcon(type?: string) {
    switch (type) {
        case 'success':
            return <CheckCircle className="h-3.5 w-3.5 text-green-400"/>;
        case 'warning':
            return <AlertCircle className="h-3.5 w-3.5 text-amber-400"/>;
        case 'error':
            return <AlertCircle className="h-3.5 w-3.5 text-red-400"/>;
        case 'info':
        default:
            return <Info className="h-3.5 w-3.5 text-blue-400"/>;
    }
}

// ============== AGENT SUMMARY BAR ==============
interface AgentSummaryBarProps {
    entries: ConversationEntry[];
    className?: string;
}

export function AgentSummaryBar({entries, className = ''}: AgentSummaryBarProps) {
    const agentStats = useMemo(() => {
        const stats: Record<AgentType, number> = {} as Record<AgentType, number>;
        entries.forEach((entry) => {
            if (entry.agentType) {
                stats[entry.agentType] = (stats[entry.agentType] || 0) + 1;
            }
        });
        return stats;
    }, [entries]);

    if (Object.keys(agentStats).length === 0) return null;

    return (
        <div className={`flex items-center gap-2 ${className}`}>
            {Object.entries(agentStats).map(([agent, count]) => (
                <div key={agent} className="flex items-center gap-1">
                    <AgentBadge agent={agent as AgentType} size="sm" showName={false}/>
                    <span className="text-xs text-[var(--color-text-muted)]">{count}</span>
                </div>
            ))}
        </div>
    );
}

export default AgentTimeline;