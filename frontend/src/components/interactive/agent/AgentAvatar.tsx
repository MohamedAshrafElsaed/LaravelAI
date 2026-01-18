'use client';

import {useMemo} from 'react';
import {ClipboardList, Code, LucideIcon, Search, ShieldCheck, Sparkles, Users,} from 'lucide-react';
import {AgentInfo, AgentState, AgentType, getAgentInfo} from './types';

interface AgentAvatarProps {
    agent: AgentType | AgentInfo;
    size?: 'sm' | 'md' | 'lg';
    state?: AgentState;
    showLabel?: boolean;
    showRole?: boolean;
    className?: string;
}

// Icon mapping
const AGENT_ICONS: Record<string, LucideIcon> = {
    sparkles: Sparkles,
    search: Search,
    'clipboard-list': ClipboardList,
    code: Code,
    'shield-check': ShieldCheck,
    users: Users,
};

// Size classes
const SIZE_CLASSES = {
    sm: {
        container: 'w-8 h-8',
        icon: 'h-4 w-4',
        ring: 'ring-2',
        text: 'text-xs',
        label: 'text-xs',
        role: 'text-[10px]',
    },
    md: {
        container: 'w-10 h-10',
        icon: 'h-5 w-5',
        ring: 'ring-2',
        text: 'text-sm',
        label: 'text-sm',
        role: 'text-xs',
    },
    lg: {
        container: 'w-14 h-14',
        icon: 'h-7 w-7',
        ring: 'ring-3',
        text: 'text-lg',
        label: 'text-base',
        role: 'text-sm',
    },
};

export function AgentAvatar({
                                agent,
                                size = 'md',
                                state = 'idle',
                                showLabel = false,
                                showRole = false,
                                className = '',
                            }: AgentAvatarProps) {
    // Resolve agent info
    const agentInfo = useMemo(() => {
        if (typeof agent === 'string') {
            return getAgentInfo(agent);
        }
        return agent;
    }, [agent]);

    // Get icon component
    const IconComponent = AGENT_ICONS[agentInfo.icon] || Users;
    const sizeClasses = SIZE_CLASSES[size];

    // State-based styles
    const stateStyles = useMemo(() => {
        switch (state) {
            case 'active':
                return 'ring-opacity-100 animate-pulse shadow-lg';
            case 'waiting':
                return 'ring-opacity-50 animate-bounce';
            default:
                return 'ring-opacity-30';
        }
    }, [state]);

    return (
        <div className={`flex items-center gap-2 ${className}`}>
            {/* Avatar circle */}
            <div
                className={`
          ${sizeClasses.container}
          ${sizeClasses.ring}
          ${stateStyles}
          rounded-full flex items-center justify-center
          bg-gray-900/80 backdrop-blur-sm
          transition-all duration-300 ease-in-out
        `}
                style={{
                    ringColor: agentInfo.color,
                    boxShadow: state === 'active' ? `0 0 20px ${agentInfo.color}40` : 'none',
                }}
            >
                <IconComponent
                    className={`${sizeClasses.icon} transition-colors duration-300`}
                    style={{color: agentInfo.color}}
                />
            </div>

            {/* Labels */}
            {(showLabel || showRole) && (
                <div className="flex flex-col">
                    {showLabel && (
                        <span
                            className={`${sizeClasses.label} font-medium`}
                            style={{color: agentInfo.color}}
                        >
              {agentInfo.name}
            </span>
                    )}
                    {showRole && (
                        <span className={`${sizeClasses.role} text-gray-500`}>
              {agentInfo.role}
            </span>
                    )}
                </div>
            )}
        </div>
    );
}

// Compact avatar with just emoji
export function AgentEmojiAvatar({
                                     agent,
                                     size = 'md',
                                     state = 'idle',
                                     className = '',
                                 }: Omit<AgentAvatarProps, 'showLabel' | 'showRole'>) {
    const agentInfo = useMemo(() => {
        if (typeof agent === 'string') {
            return getAgentInfo(agent);
        }
        return agent;
    }, [agent]);

    const sizeClasses = {
        sm: 'text-lg',
        md: 'text-xl',
        lg: 'text-3xl',
    };

    return (
        <span
            className={`
        ${sizeClasses[size]}
        ${state === 'active' ? 'animate-pulse' : ''}
        ${className}
      `}
            title={`${agentInfo.name} - ${agentInfo.role}`}
        >
      {agentInfo.avatar_emoji}
    </span>
    );
}

// Agent badge with color indicator
export function AgentBadge({
                               agent,
                               showRole = false,
                               className = '',
                           }: {
    agent: AgentType | AgentInfo;
    showRole?: boolean;
    className?: string;
}) {
    const agentInfo = useMemo(() => {
        if (typeof agent === 'string') {
            return getAgentInfo(agent);
        }
        return agent;
    }, [agent]);

    return (
        <div
            className={`
        inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full
        bg-gray-800/50 backdrop-blur-sm border
        ${className}
      `}
            style={{
                borderColor: `${agentInfo.color}40`,
            }}
        >
      <span
          className="w-2 h-2 rounded-full"
          style={{backgroundColor: agentInfo.color}}
      />
            <span
                className="text-xs font-medium"
                style={{color: agentInfo.color}}
            >
        {agentInfo.name}
      </span>
            {showRole && (
                <span className="text-xs text-gray-500">
          ({agentInfo.role})
        </span>
            )}
        </div>
    );
}

// Agent row with avatar and info
export function AgentRow({
                             agent,
                             state = 'idle',
                             subtitle,
                             action,
                             className = '',
                         }: {
    agent: AgentType | AgentInfo;
    state?: AgentState;
    subtitle?: string;
    action?: React.ReactNode;
    className?: string;
}) {
    const agentInfo = useMemo(() => {
        if (typeof agent === 'string') {
            return getAgentInfo(agent);
        }
        return agent;
    }, [agent]);

    return (
        <div className={`flex items-center gap-3 ${className}`}>
            <AgentAvatar agent={agentInfo} size="md" state={state}/>
            <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
          <span
              className="font-medium text-sm"
              style={{color: agentInfo.color}}
          >
            {agentInfo.name}
          </span>
                    <span className="text-xs text-gray-500">
            {agentInfo.role}
          </span>
                </div>
                {subtitle && (
                    <p className="text-xs text-gray-400 truncate">
                        {subtitle}
                    </p>
                )}
            </div>
            {action}
        </div>
    );
}

export default AgentAvatar;
