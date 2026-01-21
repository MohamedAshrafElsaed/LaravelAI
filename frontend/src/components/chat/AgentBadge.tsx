'use client';

import React from 'react';
import {motion} from 'framer-motion';
import type {AgentInfo, AgentType} from './types';

// ============== AGENT CONFIGURATION ==============
export const AGENT_CONFIG: Record<AgentType, AgentInfo> = {
    nova: {
        type: 'nova',
        name: 'Nova',
        description: 'Intent Analyzer - Understands what you want to build',
        emoji: '🎯',
        color: 'text-purple-400',
        bgColor: 'bg-purple-500/20',
        borderColor: 'border-purple-500/30',
        role: 'Intent Analyzer',
    },
    scout: {
        type: 'scout',
        name: 'Scout',
        description: 'Context Retriever - Finds relevant code in your project',
        emoji: '🔍',
        color: 'text-cyan-400',
        bgColor: 'bg-cyan-500/20',
        borderColor: 'border-cyan-500/30',
        role: 'Context Retriever',
    },
    blueprint: {
        type: 'blueprint',
        name: 'Blueprint',
        description: 'Planner - Creates execution plans',
        emoji: '📋',
        color: 'text-blue-400',
        bgColor: 'bg-blue-500/20',
        borderColor: 'border-blue-500/30',
        role: 'Planner',
    },
    forge: {
        type: 'forge',
        name: 'Forge',
        description: 'Executor - Generates and modifies code',
        emoji: '⚡',
        color: 'text-amber-400',
        bgColor: 'bg-amber-500/20',
        borderColor: 'border-amber-500/30',
        role: 'Executor',
    },
    guardian: {
        type: 'guardian',
        name: 'Guardian',
        description: 'Validator - Ensures code quality and Laravel conventions',
        emoji: '🛡️',
        color: 'text-green-400',
        bgColor: 'bg-green-500/20',
        borderColor: 'border-green-500/30',
        role: 'Validator',
    },
    conductor: {
        type: 'conductor',
        name: 'Conductor',
        description: 'Orchestrator - Coordinates all agents',
        emoji: '🎭',
        color: 'text-rose-400',
        bgColor: 'bg-rose-500/20',
        borderColor: 'border-rose-500/30',
        role: 'Orchestrator',
    },
};

// ============== AGENT BADGE COMPONENT ==============
interface AgentBadgeProps {
    agent: AgentType;
    size?: 'sm' | 'md' | 'lg';
    showName?: boolean;
    showRole?: boolean;
    animated?: boolean;
    className?: string;
}

export function AgentBadge({
                               agent,
                               size = 'md',
                               showName = true,
                               showRole = false,
                               animated = false,
                               className = '',
                           }: AgentBadgeProps) {
    const config = AGENT_CONFIG[agent];
    if (!config) return null;

    const sizeClasses = {
        sm: 'text-xs px-1.5 py-0.5 gap-1',
        md: 'text-sm px-2 py-1 gap-1.5',
        lg: 'text-base px-3 py-1.5 gap-2',
    };

    const emojiSizes = {
        sm: 'text-sm',
        md: 'text-base',
        lg: 'text-lg',
    };

    const content = (
        <>
            <span className={emojiSizes[size]}>{config.emoji}</span>
            {showName && <span className={config.color}>{config.name}</span>}
            {showRole && <span className="text-[var(--color-text-muted)] text-xs">({config.role})</span>}
        </>
    );

    if (animated) {
        return (
            <motion.span
                initial={{scale: 0.9, opacity: 0}}
                animate={{scale: 1, opacity: 1}}
                className={`
          inline-flex items-center rounded-full font-medium
          ${config.bgColor} ${config.borderColor} border
          ${sizeClasses[size]}
          ${className}
        `}
            >
                {content}
            </motion.span>
        );
    }

    return (
        <span
            className={`
        inline-flex items-center rounded-full font-medium
        ${config.bgColor} ${config.borderColor} border
        ${sizeClasses[size]}
        ${className}
      `}
        >
      {content}
    </span>
    );
}

// ============== AGENT AVATAR ==============
interface AgentAvatarProps {
    agent: AgentType;
    size?: 'sm' | 'md' | 'lg';
    showPulse?: boolean;
    className?: string;
}

export function AgentAvatar({agent, size = 'md', showPulse = false, className = ''}: AgentAvatarProps) {
    const config = AGENT_CONFIG[agent];
    if (!config) return null;

    const sizeClasses = {
        sm: 'w-6 h-6 text-sm',
        md: 'w-8 h-8 text-base',
        lg: 'w-10 h-10 text-lg',
    };

    return (
        <div className={`relative ${className}`}>
            <div
                className={`
          ${sizeClasses[size]} rounded-full flex items-center justify-center
          ${config.bgColor} ${config.borderColor} border
        `}
                title={`${config.name} - ${config.role}`}
            >
                {config.emoji}
            </div>
            {showPulse && (
                <span className="absolute -top-0.5 -right-0.5 flex h-2.5 w-2.5">
          <span
              className={`animate-ping absolute inline-flex h-full w-full rounded-full ${config.bgColor} opacity-75`}/>
          <span className={`relative inline-flex rounded-full h-2.5 w-2.5 ${config.bgColor}`}/>
        </span>
            )}
        </div>
    );
}

// ============== AGENT THINKING INDICATOR ==============
interface AgentThinkingProps {
    agent: AgentType;
    thought: string;
    actionType?: string;
    filePath?: string;
    progress?: number;
}

export function AgentThinking({agent, thought, actionType, filePath, progress = 0}: AgentThinkingProps) {
    const config = AGENT_CONFIG[agent];
    if (!config) return null;

    return (
        <motion.div
            initial={{opacity: 0, y: 10}}
            animate={{opacity: 1, y: 0}}
            exit={{opacity: 0, y: -10}}
            className={`
        flex items-start gap-3 p-3 rounded-lg
        ${config.bgColor} ${config.borderColor} border
      `}
        >
            <AgentAvatar agent={agent} size="sm" showPulse/>
            <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                    <span className={`font-medium ${config.color}`}>{config.name}</span>
                    <span className="text-xs text-[var(--color-text-muted)]">is thinking...</span>
                </div>
                <p className="text-sm text-[var(--color-text-secondary)] line-clamp-2">{thought}</p>
                {(actionType || filePath) && (
                    <div className="flex items-center gap-2 mt-1 text-xs text-[var(--color-text-muted)]">
                        {actionType && (
                            <span className="px-1.5 py-0.5 rounded bg-black/20">{actionType}</span>
                        )}
                        {filePath && (
                            <span className="truncate text-blue-400">{filePath}</span>
                        )}
                    </div>
                )}
                {progress > 0 && (
                    <div className="mt-2 h-1 bg-black/20 rounded-full overflow-hidden">
                        <motion.div
                            initial={{width: 0}}
                            animate={{width: `${progress}%`}}
                            className={`h-full ${config.bgColor.replace('/20', '')}`}
                        />
                    </div>
                )}
            </div>
        </motion.div>
    );
}

// ============== AGENT HANDOFF INDICATOR ==============
interface AgentHandoffProps {
    fromAgent: AgentType;
    toAgent: AgentType;
    message?: string;
}

export function AgentHandoff({fromAgent, toAgent, message}: AgentHandoffProps) {
    const fromConfig = AGENT_CONFIG[fromAgent];
    const toConfig = AGENT_CONFIG[toAgent];
    if (!fromConfig || !toConfig) return null;

    return (
        <motion.div
            initial={{opacity: 0, scale: 0.95}}
            animate={{opacity: 1, scale: 1}}
            className="flex items-center gap-2 py-2 text-sm"
        >
            <AgentBadge agent={fromAgent} size="sm"/>
            <div className="flex items-center gap-1 text-[var(--color-text-muted)]">
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6"/>
                </svg>
            </div>
            <AgentBadge agent={toAgent} size="sm"/>
            {message && (
                <span className="text-[var(--color-text-muted)] text-xs ml-2 truncate">
          {message}
        </span>
            )}
        </motion.div>
    );
}

// Helper function to get agent info
export function getAgentInfo(agent: AgentType | string): AgentInfo {
    return AGENT_CONFIG[agent as AgentType] || AGENT_CONFIG.conductor;
}

export default AgentBadge;