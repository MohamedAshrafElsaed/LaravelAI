'use client';

import { useState, useEffect, useMemo, useCallback } from 'react';
import { Loader2 } from 'lucide-react';
import { AgentAvatar } from './AgentAvatar';
import {
  AgentType,
  AgentInfo,
  getAgentInfo,
} from './types';

interface AgentThinkingProps {
  agent: AgentType | AgentInfo;
  thought?: string;
  actionType?: string;
  filePath?: string;
  progress?: number;
  rotateMessages?: boolean;
  rotationInterval?: number;
  className?: string;
}

// Thinking message pools for different action types
const THINKING_MESSAGES: Record<string, string[]> = {
  intent: [
    'Analyzing the intent behind this request...',
    'Determining the scope and domains affected...',
    'Identifying the type of task...',
    'Understanding what files and systems are involved...',
    'Mapping out the requirements...',
  ],
  context: [
    'Searching the vector database...',
    'Looking for relevant code patterns...',
    'Finding related files and classes...',
    'Checking existing implementations...',
    'Discovering connected components...',
    'Exploring the project structure...',
  ],
  planning: [
    'Analyzing the best approach...',
    'Deciding between creating new vs modifying existing...',
    'Ordering steps by dependency...',
    'Considering migrations and models first...',
    'Planning the controller modifications...',
    'Figuring out the route structure...',
  ],
  create: [
    'Structuring the class hierarchy...',
    'Adding necessary use statements...',
    'Implementing the method signatures...',
    'Writing the business logic...',
    'Adding type hints and docblocks...',
    'Crafting the constructor...',
    'Defining the properties...',
  ],
  modify: [
    'Reading the existing code...',
    'Identifying the insertion point...',
    'Preserving existing functionality...',
    'Integrating the new code...',
    'Ensuring backwards compatibility...',
    'Updating method signatures...',
  ],
  route: [
    'Analyzing existing routes...',
    'Finding the right route group...',
    'Adding the new endpoint...',
    'Verifying route naming conventions...',
    'Setting up middleware...',
  ],
  migration: [
    'Creating the migration schema...',
    'Defining table columns...',
    'Setting up foreign keys...',
    'Adding indexes...',
    'Creating rollback logic...',
  ],
  model: [
    'Defining fillable attributes...',
    'Setting up relationships...',
    'Adding model casts...',
    'Implementing scopes...',
    'Creating accessors and mutators...',
  ],
  controller: [
    'Implementing controller methods...',
    'Adding request validation...',
    'Setting up authorization...',
    'Creating response structures...',
    'Adding error handling...',
  ],
  validation: [
    'Checking for syntax errors...',
    'Verifying use statements...',
    'Analyzing security implications...',
    'Validating Laravel conventions...',
    'Checking backwards compatibility...',
    'Reviewing code quality...',
    'Looking for missing dependencies...',
  ],
  default: [
    'Processing...',
    'Working on it...',
    'Almost there...',
    'Making progress...',
  ],
};

function getThinkingMessages(actionType?: string): string[] {
  if (!actionType) return THINKING_MESSAGES.default;
  return THINKING_MESSAGES[actionType.toLowerCase()] || THINKING_MESSAGES.default;
}

export function AgentThinking({
  agent,
  thought,
  actionType,
  filePath,
  progress,
  rotateMessages = true,
  rotationInterval = 2000,
  className = '',
}: AgentThinkingProps) {
  const agentInfo = useMemo(() => {
    if (typeof agent === 'string') {
      return getAgentInfo(agent);
    }
    return agent;
  }, [agent]);

  // Rotating message state
  const [currentMessageIndex, setCurrentMessageIndex] = useState(0);
  const messages = useMemo(() => getThinkingMessages(actionType), [actionType]);

  // Rotate messages
  useEffect(() => {
    if (!rotateMessages || thought) return;

    const interval = setInterval(() => {
      setCurrentMessageIndex((prev) => (prev + 1) % messages.length);
    }, rotationInterval);

    return () => clearInterval(interval);
  }, [rotateMessages, messages, rotationInterval, thought]);

  // Display message
  const displayMessage = thought || messages[currentMessageIndex];

  return (
    <div className={`flex gap-3 ${className}`}>
      {/* Agent Avatar with active state */}
      <div className="flex-shrink-0 pt-1">
        <AgentAvatar agent={agentInfo} size="sm" state="active" />
      </div>

      {/* Thinking Content */}
      <div className="flex-1 min-w-0">
        {/* Header */}
        <div className="flex items-center gap-2 mb-1">
          <span
            className="text-sm font-medium"
            style={{ color: agentInfo.color }}
          >
            {agentInfo.name}
          </span>
          <Loader2 className="h-3 w-3 text-gray-500 animate-spin" />
          {progress !== undefined && progress > 0 && (
            <span className="text-xs text-gray-500">
              {Math.round(progress * 100)}%
            </span>
          )}
        </div>

        {/* Thinking Bubble */}
        <div
          className="rounded-lg border border-gray-700/50 bg-gray-800/30 px-3 py-2"
          style={{
            borderLeftColor: `${agentInfo.color}40`,
            borderLeftWidth: '3px',
          }}
        >
          {/* File path indicator */}
          {filePath && (
            <div className="text-xs text-gray-500 font-mono mb-1">
              {filePath}
            </div>
          )}

          {/* Thinking message with typing effect */}
          <p className="text-sm text-gray-400 italic">
            {displayMessage}
            <span className="inline-block w-1 h-4 bg-gray-500 animate-pulse ml-1 align-middle" />
          </p>
        </div>

        {/* Progress bar */}
        {progress !== undefined && progress > 0 && (
          <div className="mt-2 h-1 bg-gray-700 rounded-full overflow-hidden">
            <div
              className="h-full transition-all duration-500 ease-out rounded-full"
              style={{
                width: `${progress * 100}%`,
                backgroundColor: agentInfo.color,
              }}
            />
          </div>
        )}
      </div>
    </div>
  );
}

// Compact thinking indicator
export function AgentThinkingCompact({
  agent,
  thought,
  className = '',
}: {
  agent: AgentType | AgentInfo;
  thought?: string;
  className?: string;
}) {
  const agentInfo = useMemo(() => {
    if (typeof agent === 'string') {
      return getAgentInfo(agent);
    }
    return agent;
  }, [agent]);

  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <span>{agentInfo.avatar_emoji}</span>
      <Loader2
        className="h-3 w-3 animate-spin"
        style={{ color: agentInfo.color }}
      />
      <span className="text-xs text-gray-500 italic">
        {thought || 'Thinking...'}
      </span>
    </div>
  );
}

// Typing text animation component (Claude Code style)
export function TypingText({
  text,
  speed = 30,
  onComplete,
  className = '',
}: {
  text: string;
  speed?: number;
  onComplete?: () => void;
  className?: string;
}) {
  const [displayText, setDisplayText] = useState('');
  const [isComplete, setIsComplete] = useState(false);

  useEffect(() => {
    if (!text) return;

    setDisplayText('');
    setIsComplete(false);
    let currentIndex = 0;

    const interval = setInterval(() => {
      if (currentIndex < text.length) {
        setDisplayText(text.substring(0, currentIndex + 1));
        currentIndex++;
      } else {
        clearInterval(interval);
        setIsComplete(true);
        onComplete?.();
      }
    }, speed);

    return () => clearInterval(interval);
  }, [text, speed, onComplete]);

  return (
    <span className={className}>
      {displayText}
      {!isComplete && (
        <span className="inline-block w-1.5 h-4 bg-blue-500 animate-pulse ml-0.5 align-middle" />
      )}
    </span>
  );
}

// Thinking dots animation
export function ThinkingDots({ className = '' }: { className?: string }) {
  return (
    <span className={`inline-flex gap-1 items-center ${className}`}>
      <span className="w-1.5 h-1.5 bg-gray-500 rounded-full animate-thinking-dot" />
      <span className="w-1.5 h-1.5 bg-gray-500 rounded-full animate-thinking-dot" />
      <span className="w-1.5 h-1.5 bg-gray-500 rounded-full animate-thinking-dot" />
    </span>
  );
}

export default AgentThinking;
