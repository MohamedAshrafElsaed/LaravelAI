'use client';

import { useState, useEffect, useRef, useMemo } from 'react';
import { Check, ChevronRight, Loader2, AlertCircle, ArrowRight } from 'lucide-react';
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
  type: 'message' | 'thinking' | 'handoff' | 'system' | 'step';
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
  completed?: boolean;
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

// CLI-style agent prefix
function AgentPrefix({ agent, isActive = false }: { agent: AgentInfo; isActive?: boolean }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      {isActive ? (
        <Loader2 className="h-3 w-3 animate-spin" style={{ color: agent.color }} />
      ) : (
        <ChevronRight className="h-3 w-3" style={{ color: agent.color }} />
      )}
      <span className="font-semibold" style={{ color: agent.color }}>
        {agent.name}
      </span>
    </span>
  );
}

// CLI-style status indicator
function StatusIcon({ status }: { status: 'pending' | 'active' | 'complete' | 'error' }) {
  switch (status) {
    case 'active':
      return <Loader2 className="h-3 w-3 animate-spin text-blue-400" />;
    case 'complete':
      return <Check className="h-3 w-3 text-green-400" />;
    case 'error':
      return <AlertCircle className="h-3 w-3 text-red-400" />;
    default:
      return <span className="w-3 h-3 inline-block" />;
  }
}

export function AgentConversation({
  entries,
  currentThinking,
  autoScroll = true,
  className = '',
}: AgentConversationProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new entries arrive
  useEffect(() => {
    if (autoScroll && containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [entries, currentThinking, autoScroll]);

  if (entries.length === 0 && !currentThinking) {
    return null;
  }

  return (
    <div ref={containerRef} className={`font-mono text-sm space-y-1 ${className}`}>
      {entries.map((entry) => {
        const agent = entry.agentType ? getAgentInfo(entry.agentType) : getAgentInfo('conductor');

        switch (entry.type) {
          case 'message':
            return (
              <div key={entry.id} className="flex items-start gap-2 py-0.5 animate-fadeIn">
                <AgentPrefix agent={agent} />
                <span className="text-gray-300">{entry.message}</span>
              </div>
            );

          case 'handoff':
            const toAgent = entry.toAgentType ? getAgentInfo(entry.toAgentType) : getAgentInfo('conductor');
            return (
              <div key={entry.id} className="flex items-center gap-2 py-0.5 text-gray-500 animate-fadeIn">
                <ArrowRight className="h-3 w-3" />
                <span style={{ color: agent.color }}>{agent.name}</span>
                <span>→</span>
                <span style={{ color: toAgent.color }}>{toAgent.name}</span>
                {entry.message && (
                  <span className="text-gray-600 italic text-xs">"{entry.message}"</span>
                )}
              </div>
            );

          case 'thinking':
            return (
              <div key={entry.id} className="flex items-start gap-2 py-0.5 text-gray-500 animate-fadeIn">
                <AgentPrefix agent={agent} />
                <span className="italic">{entry.thought || 'Thinking...'}</span>
              </div>
            );

          case 'step':
            return (
              <div key={entry.id} className="flex items-start gap-2 py-0.5 animate-fadeIn">
                <StatusIcon status={entry.completed ? 'complete' : 'active'} />
                <span className="text-gray-400">{entry.actionType}</span>
                {entry.filePath && (
                  <span className="text-blue-400">{entry.filePath}</span>
                )}
                {entry.message && (
                  <span className="text-gray-500">- {entry.message}</span>
                )}
              </div>
            );

          case 'system':
            const systemColors = {
              info: 'text-gray-400',
              success: 'text-green-400',
              warning: 'text-yellow-400',
              error: 'text-red-400',
            };
            return (
              <div key={entry.id} className={`py-0.5 animate-fadeIn ${systemColors[entry.systemType || 'info']}`}>
                <span className="text-gray-600">›</span> {entry.message}
              </div>
            );

          default:
            return null;
        }
      })}

      {/* Current thinking state - CLI style */}
      {currentThinking && (
        <div className="flex items-start gap-2 py-0.5 animate-fadeIn">
          <AgentPrefix agent={currentThinking.agent} isActive />
          <span className="text-gray-400 italic">
            {currentThinking.thought || 'Processing...'}
            {currentThinking.filePath && (
              <span className="text-blue-400 ml-2">{currentThinking.filePath}</span>
            )}
          </span>
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
          thought: data.step?.description || 'Working on step...',
          actionType: data.step?.action,
          filePath: data.step?.file,
          progress: 0,
        });
        addEntry({
          type: 'step',
          timestamp,
          agentType: 'forge',
          actionType: data.step?.action,
          filePath: data.step?.file,
          message: data.step?.description,
          completed: false,
        });
        break;

      case 'step_completed':
        setCurrentThinking(null);
        // Mark the last step entry as completed
        setEntries((prev) => {
          const updated = [...prev];
          for (let i = updated.length - 1; i >= 0; i--) {
            if (updated[i].type === 'step' && !updated[i].completed) {
              updated[i] = { ...updated[i], completed: true };
              break;
            }
          }
          return updated;
        });
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
