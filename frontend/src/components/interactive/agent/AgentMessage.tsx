'use client';

import { useMemo } from 'react';
import { ArrowRight, CheckCircle, AlertCircle, Loader2 } from 'lucide-react';
import { AgentAvatar, AgentEmojiAvatar, AgentBadge } from './AgentAvatar';
import {
  AgentType,
  AgentInfo,
  MessageType,
  getAgentInfo,
} from './types';

interface AgentMessageProps {
  agent: AgentType | AgentInfo;
  message: string;
  messageType?: MessageType;
  toAgent?: AgentType | AgentInfo;
  timestamp?: string;
  isThinking?: boolean;
  className?: string;
}

export function AgentMessage({
  agent,
  message,
  messageType = 'custom',
  toAgent,
  timestamp,
  isThinking = false,
  className = '',
}: AgentMessageProps) {
  const agentInfo = useMemo(() => {
    if (typeof agent === 'string') {
      return getAgentInfo(agent);
    }
    return agent;
  }, [agent]);

  const toAgentInfo = useMemo(() => {
    if (!toAgent) return null;
    if (typeof toAgent === 'string') {
      return getAgentInfo(toAgent);
    }
    return toAgent;
  }, [toAgent]);

  // Message type indicator
  const typeIndicator = useMemo(() => {
    switch (messageType) {
      case 'greeting':
        return null;
      case 'thinking':
        return (
          <Loader2 className="h-3 w-3 text-gray-500 animate-spin" />
        );
      case 'handoff':
        return (
          <ArrowRight className="h-3 w-3 text-gray-500" />
        );
      case 'completion':
        return (
          <CheckCircle className="h-3 w-3 text-green-500" />
        );
      case 'error':
        return (
          <AlertCircle className="h-3 w-3 text-red-500" />
        );
      default:
        return null;
    }
  }, [messageType]);

  // Background color based on message type
  const bgColor = useMemo(() => {
    switch (messageType) {
      case 'error':
        return 'bg-red-500/5 border-red-500/20';
      case 'completion':
        return 'bg-green-500/5 border-green-500/20';
      case 'handoff':
        return 'bg-blue-500/5 border-blue-500/20';
      default:
        return 'bg-gray-800/50 border-gray-700/50';
    }
  }, [messageType]);

  return (
    <div className={`flex gap-3 ${className}`}>
      {/* Agent Avatar */}
      <div className="flex-shrink-0 pt-1">
        <AgentAvatar
          agent={agentInfo}
          size="sm"
          state={isThinking ? 'active' : 'idle'}
        />
      </div>

      {/* Message Content */}
      <div className="flex-1 min-w-0">
        {/* Header */}
        <div className="flex items-center gap-2 mb-1">
          <span
            className="text-sm font-medium"
            style={{ color: agentInfo.color }}
          >
            {agentInfo.name}
          </span>

          {typeIndicator}

          {toAgentInfo && (
            <>
              <ArrowRight className="h-3 w-3 text-gray-500" />
              <span
                className="text-sm font-medium"
                style={{ color: toAgentInfo.color }}
              >
                {toAgentInfo.name}
              </span>
            </>
          )}

          {timestamp && (
            <span className="text-xs text-gray-600">
              {new Date(timestamp).toLocaleTimeString()}
            </span>
          )}
        </div>

        {/* Message Bubble */}
        <div
          className={`
            rounded-lg border px-3 py-2
            ${bgColor}
          `}
        >
          <p className="text-sm text-gray-300 whitespace-pre-wrap">
            {message}
            {isThinking && (
              <span className="inline-block w-1.5 h-4 bg-gray-500 animate-pulse ml-1 align-middle" />
            )}
          </p>
        </div>
      </div>
    </div>
  );
}

// Compact inline message (for conversation thread)
export function AgentMessageCompact({
  agent,
  message,
  messageType = 'custom',
  toAgent,
  className = '',
}: Omit<AgentMessageProps, 'timestamp' | 'isThinking'>) {
  const agentInfo = useMemo(() => {
    if (typeof agent === 'string') {
      return getAgentInfo(agent);
    }
    return agent;
  }, [agent]);

  const toAgentInfo = useMemo(() => {
    if (!toAgent) return null;
    if (typeof toAgent === 'string') {
      return getAgentInfo(toAgent);
    }
    return toAgent;
  }, [toAgent]);

  return (
    <div className={`flex items-start gap-2 ${className}`}>
      <AgentEmojiAvatar agent={agentInfo} size="sm" />
      <div className="flex-1 min-w-0">
        <span
          className="text-sm font-medium mr-1"
          style={{ color: agentInfo.color }}
        >
          {agentInfo.name}:
        </span>
        {toAgentInfo && (
          <span className="text-xs text-gray-500 mr-1">
            (to {toAgentInfo.name})
          </span>
        )}
        <span className="text-sm text-gray-300">
          {message}
        </span>
      </div>
    </div>
  );
}

// Handoff message between agents
export function AgentHandoffMessage({
  fromAgent,
  toAgent,
  message,
  context,
  className = '',
}: {
  fromAgent: AgentType | AgentInfo;
  toAgent: AgentType | AgentInfo;
  message?: string;
  context?: Record<string, any>;
  className?: string;
}) {
  const fromInfo = useMemo(() => {
    if (typeof fromAgent === 'string') {
      return getAgentInfo(fromAgent);
    }
    return fromAgent;
  }, [fromAgent]);

  const toInfo = useMemo(() => {
    if (typeof toAgent === 'string') {
      return getAgentInfo(toAgent);
    }
    return toAgent;
  }, [toAgent]);

  return (
    <div className={`flex items-center gap-3 py-2 ${className}`}>
      <AgentBadge agent={fromInfo} />
      <div className="flex items-center gap-2 text-gray-500">
        <ArrowRight className="h-4 w-4 animate-handoff" />
        {message && (
          <span className="text-xs italic animate-fadeIn">
            "{message}"
          </span>
        )}
        <ArrowRight className="h-4 w-4 animate-handoff" style={{ animationDelay: '0.3s' }} />
      </div>
      <AgentBadge agent={toInfo} />
    </div>
  );
}

// System message (from Conductor or general)
export function SystemMessage({
  message,
  type = 'info',
  className = '',
}: {
  message: string;
  type?: 'info' | 'success' | 'warning' | 'error';
  className?: string;
}) {
  const styles = {
    info: 'border-gray-700 bg-gray-800/30 text-gray-400',
    success: 'border-green-700/50 bg-green-500/5 text-green-400',
    warning: 'border-yellow-700/50 bg-yellow-500/5 text-yellow-400',
    error: 'border-red-700/50 bg-red-500/5 text-red-400',
  };

  return (
    <div
      className={`
        text-center text-xs px-4 py-2 rounded-lg border
        ${styles[type]}
        ${className}
      `}
    >
      {message}
    </div>
  );
}

export default AgentMessage;
