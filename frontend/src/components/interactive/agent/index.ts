/**
 * Multi-Agent Chat Components
 *
 * This module provides a complete set of components for the interactive
 * multi-agent chat experience.
 */

// Types
export * from './types';

// Components
export {default as AgentAvatar, AgentEmojiAvatar, AgentBadge, AgentRow} from './AgentAvatar';
export {
    default as AgentMessage,
    AgentMessageCompact,
    AgentHandoffMessage,
    SystemMessage,
} from './AgentMessage';
export {
    default as AgentThinking,
    AgentThinkingCompact,
    TypingText,
    ThinkingDots,
} from './AgentThinking';
export {
    default as AgentConversation,
    useAgentConversation,
    eventsToConversationEntries,
    type ConversationEntry,
} from './AgentConversation';
export {default as PlanEditor} from './PlanEditor';
export {
    default as ValidationDisplay,
    ValidationIssueCard,
    ValidationIssueList,
    ScoreReveal,
    ValidationResultDisplay,
} from './ValidationDisplay';
export {default as InteractiveChat, type InteractiveChatRef} from './InteractiveChat';
export {default as TaskSummary} from './TaskSummary';
