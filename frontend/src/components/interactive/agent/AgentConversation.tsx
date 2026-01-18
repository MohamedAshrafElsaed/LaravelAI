'use client';

import { useState, useEffect, useRef, useMemo } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';
import { AgentMessage, AgentMessageCompact, AgentHandoffMessage, SystemMessage } from './AgentMessage';
import { AgentThinking, AgentThinkingCompact } from './AgentThinking';
import {
  AgentType,
  AgentInfo,
  AgentEventType,
  InteractiveEvent,
  getAgentInfo,
  AgentThinkingState,
} from './types';

export interface ConversationEntry {
  id: string;
  type: 'message' | 'thinking' | 'handoff' | 'system';
  timestamp: string;
  agentType?: AgentType;
  toAgentType?: AgentType;
  message?: string;
  messageType?: string;
  thought?: string;
  actionType?: string;
  filePath?: string;
  progress?: number;
  systemType?: 'info' | 'success' | 'warning' | 'error';
}

interface AgentConversationProps {
  entries: ConversationEntry[];
  currentThinking?: AgentThinkingState | null;
  autoScroll?: boolean;
  maxHeight?: string;
  compact?: boolean;
  showTimestamps?: boolean;
  className?: string;
}

export function AgentConversation({
  entries,
  currentThinking,
  autoScroll = true,
  maxHeight = '400px',
  compact = false,
  showTimestamps = false,
  className = '',
}: AgentConversationProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [isExpanded, setIsExpanded] = useState(true);

  // Auto-scroll to bottom when new entries arrive
  useEffect(() => {
    if (autoScroll && containerRef.current && isExpanded) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [entries, currentThinking, autoScroll, isExpanded]);

  if (entries.length === 0 && !currentThinking) {
    return null;
  }

  const MessageComponent = compact ? AgentMessageCompact : AgentMessage;

  return (
    <div className={`rounded-lg border border-gray-800 bg-gray-900/50 overflow-hidden ${className}`}>
      {/* Header */}
      <div
        className="flex items-center justify-between px-3 py-2 bg-gray-800/50 cursor-pointer hover:bg-gray-800/70 transition-colors"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-gray-300">Agent Activity</span>
          <span className="text-xs text-gray-500">
            {entries.length} {entries.length === 1 ? 'message' : 'messages'}
          </span>
        </div>
        {isExpanded ? (
          <ChevronUp className="h-4 w-4 text-gray-500" />
        ) : (
          <ChevronDown className="h-4 w-4 text-gray-500" />
        )}
      </div>

      {/* Conversation Thread */}
      {isExpanded && (
        <div
          ref={containerRef}
          className="overflow-y-auto p-3 space-y-3"
          style={{ maxHeight }}
        >
          {entries.map((entry, index) => {
            const animationClass = 'animate-slideIn';
            const animationStyle = { animationDelay: `${Math.min(index * 30, 150)}ms` };

            switch (entry.type) {
              case 'message':
                return (
                  <div key={entry.id} className={animationClass} style={animationStyle}>
                    <MessageComponent
                      agent={entry.agentType || 'conductor'}
                      message={entry.message || ''}
                      messageType={entry.messageType as any}
                      toAgent={entry.toAgentType}
                      timestamp={showTimestamps ? entry.timestamp : undefined}
                    />
                  </div>
                );

              case 'handoff':
                return (
                  <div key={entry.id} className={animationClass} style={animationStyle}>
                    <AgentHandoffMessage
                      fromAgent={entry.agentType || 'conductor'}
                      toAgent={entry.toAgentType || 'conductor'}
                      message={entry.message}
                    />
                  </div>
                );

              case 'thinking':
                return compact ? (
                  <div key={entry.id} className={animationClass} style={animationStyle}>
                    <AgentThinkingCompact
                      agent={entry.agentType || 'conductor'}
                      thought={entry.thought}
                    />
                  </div>
                ) : (
                  <div key={entry.id} className={animationClass} style={animationStyle}>
                    <AgentThinking
                      agent={entry.agentType || 'conductor'}
                      thought={entry.thought}
                      actionType={entry.actionType}
                      filePath={entry.filePath}
                      progress={entry.progress}
                      rotateMessages={false}
                    />
                  </div>
                );

              case 'system':
                return (
                  <div key={entry.id} className={entry.systemType === 'success' ? 'animate-success' : animationClass} style={animationStyle}>
                    <SystemMessage
                      message={entry.message || ''}
                      type={entry.systemType || 'info'}
                    />
                  </div>
                );

              default:
                return null;
            }
          })}

          {/* Current thinking state */}
          {currentThinking && (
            <div className="animate-fadeIn">
              {compact ? (
                <AgentThinkingCompact
                  agent={currentThinking.agent}
                  thought={currentThinking.thought}
                />
              ) : (
                <AgentThinking
                  agent={currentThinking.agent}
                  thought={currentThinking.thought}
                  actionType={currentThinking.actionType}
                  filePath={currentThinking.filePath}
                  progress={currentThinking.progress}
                  rotateMessages
                />
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// Hook to manage agent conversation state from events
export function useAgentConversation() {
  const [entries, setEntries] = useState<ConversationEntry[]>([]);
  const [currentThinking, setCurrentThinking] = useState<AgentThinkingState | null>(null);
  const entryIdRef = useRef(0);

  const generateId = () => {
    entryIdRef.current += 1;
    return `entry-${entryIdRef.current}`;
  };

  const addEntry = (entry: Omit<ConversationEntry, 'id'>) => {
    setEntries((prev) => [...prev, { ...entry, id: generateId() }]);
  };

  const clearEntries = () => {
    setEntries([]);
    setCurrentThinking(null);
    entryIdRef.current = 0;
  };

  const processEvent = (event: InteractiveEvent) => {
    const { event: eventType, data } = event;
    const timestamp = data.timestamp || new Date().toISOString();

    switch (eventType) {
      case 'agent_message':
        addEntry({
          type: 'message',
          timestamp,
          agentType: data.from_agent as AgentType,
          toAgentType: data.to_agent as AgentType,
          message: data.message,
          messageType: data.message_type,
        });
        break;

      case 'agent_handoff':
        addEntry({
          type: 'handoff',
          timestamp,
          agentType: data.from_agent as AgentType,
          toAgentType: data.to_agent as AgentType,
          message: data.message,
        });
        break;

      case 'agent_thinking':
      case 'intent_thinking':
      case 'context_thinking':
      case 'planning_thinking':
      case 'step_thinking':
      case 'validation_thinking':
        setCurrentThinking({
          agent: getAgentInfo(data.agent || data.agent_name || 'conductor'),
          thought: data.thought,
          actionType: data.action_type,
          filePath: data.file_path,
          progress: data.progress || 0,
        });
        break;

      case 'intent_started':
      case 'context_started':
      case 'planning_started':
      case 'execution_started':
      case 'validation_started':
        setCurrentThinking({
          agent: getAgentInfo(data.agent || 'conductor'),
          thought: data.message || 'Processing...',
          progress: 0,
        });
        addEntry({
          type: 'message',
          timestamp,
          agentType: data.agent as AgentType,
          message: data.message,
          messageType: 'greeting',
        });
        break;

      case 'intent_analyzed':
      case 'context_retrieved':
      case 'plan_created':
      case 'execution_completed':
      case 'validation_result':
        setCurrentThinking(null);
        addEntry({
          type: 'message',
          timestamp,
          agentType: data.agent as AgentType,
          message: data.message,
          messageType: 'completion',
        });
        break;

      case 'step_started':
        setCurrentThinking({
          agent: getAgentInfo('forge'),
          thought: `Working on: ${data.step?.description || 'step'}`,
          actionType: data.step?.action,
          filePath: data.step?.file,
          progress: 0,
        });
        break;

      case 'step_completed':
        setCurrentThinking(null);
        break;

      case 'plan_ready':
        setCurrentThinking(null);
        addEntry({
          type: 'system',
          timestamp,
          message: 'Plan ready for review. Please approve to continue.',
          systemType: 'info',
        });
        break;

      case 'plan_approved':
        addEntry({
          type: 'system',
          timestamp,
          message: 'Plan approved! Starting execution...',
          systemType: 'success',
        });
        break;

      case 'validation_issue_found':
        addEntry({
          type: 'message',
          timestamp,
          agentType: 'guardian',
          message: `Found issue: ${data.issue?.message}`,
          messageType: 'error',
        });
        break;

      case 'validation_fix_started':
        addEntry({
          type: 'message',
          timestamp,
          agentType: 'guardian',
          message: data.message || 'Starting auto-fix...',
          messageType: 'custom',
        });
        break;

      case 'error':
        setCurrentThinking(null);
        addEntry({
          type: 'system',
          timestamp,
          message: data.message || 'An error occurred',
          systemType: 'error',
        });
        break;

      case 'complete':
        setCurrentThinking(null);
        if (data.success) {
          addEntry({
            type: 'system',
            timestamp,
            message: 'Task completed successfully!',
            systemType: 'success',
          });
        }
        break;

      default:
        // Ignore other events
        break;
    }
  };

  return {
    entries,
    currentThinking,
    addEntry,
    clearEntries,
    processEvent,
    setCurrentThinking,
  };
}

export default AgentConversation;
