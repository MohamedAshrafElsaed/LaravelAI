// frontend/src/components/chat/index.ts

// Main component
export {ChatModule, type ChatModuleProps, type ChatModuleRef} from './ChatModule';

// Sub-components
export {AgentBadge, AgentAvatar, AgentThinking, AgentHandoff, AGENT_CONFIG, getAgentInfo} from './AgentBadge';
export {AgentTimeline, AgentSummaryBar} from './AgentTimeline';
export {PlanApprovalCard} from './PlanApprovalCard';
export {ChangesReviewPanel} from './ChangesReviewPanel';

// Types
export type {
    // Agent types
    AgentType,
    AgentInfo,
    MessageType,
    // Conversation types
    ConversationEntry,
    AgentThinkingState,
    Message,
    // Plan types
    Plan,
    PlanStep,
    // Execution types
    ExecutionResult,
    // Validation types
    ValidationIssue,
    ValidationResult,
    // Timeline types
    AgentActivity,
    AgentTimeline as AgentTimelineType,
    // Event types
    SSEEventType,
    InteractiveEvent,
    // Git types
    GitChangeFile,
    GitChange,
    // API types
    PlanApprovalRequest,
    Conversation,
    ConversationMessage,
} from './types';

// Default export
export {ChatModule as default} from './ChatModule';