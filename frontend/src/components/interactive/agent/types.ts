/**
 * Types for the Multi-Agent Chat Experience
 */

// Agent Types
export type AgentType = 'nova' | 'scout' | 'blueprint' | 'forge' | 'guardian' | 'conductor';

export interface AgentInfo {
    type: AgentType;
    name: string;
    role: string;
    color: string;
    icon: string;
    avatar_emoji: string;
    personality: string;
}

// Agent state types
export type AgentState = 'active' | 'idle' | 'waiting';

// Event types for interactive mode
export type AgentEventType =
    | 'connected'
    | 'complete'
    | 'error'
    | 'agent_thinking'
    | 'agent_message'
    | 'agent_handoff'
    | 'agent_state_change'
    | 'intent_started'
    | 'intent_thinking'
    | 'intent_analyzed'
    | 'context_started'
    | 'context_thinking'
    | 'context_chunk_found'
    | 'context_retrieved'
    | 'planning_started'
    | 'planning_thinking'
    | 'plan_step_added'
    | 'plan_ready'
    | 'plan_approved'
    | 'plan_modified'
    | 'plan_rejected'
    | 'plan_created'
    | 'execution_started'
    | 'step_started'
    | 'step_thinking'
    | 'step_code_chunk'
    | 'step_progress'
    | 'step_completed'
    | 'execution_completed'
    | 'validation_started'
    | 'validation_thinking'
    | 'validation_issue_found'
    | 'validation_fix_started'
    | 'validation_fix_completed'
    | 'validation_result'
    | 'answer_chunk'
    | 'answer_complete'
    | 'progress_update';

// Message types
export type MessageType = 'greeting' | 'thinking' | 'handoff' | 'completion' | 'error' | 'custom';

export interface AgentMessage {
    id: string;
    agent: AgentInfo;
    message: string;
    messageType: MessageType;
    toAgent?: AgentInfo;
    timestamp: string;
    metadata?: Record<string, any>;
}

export interface AgentThinkingState {
    agent: AgentInfo;
    thought: string;
    actionType?: string;
    filePath?: string;
    stepIndex?: number;
    progress: number;
}

// Plan types
export interface PlanStep {
    order: number;
    action: 'create' | 'modify' | 'delete';
    file: string;
    description: string;
}

export interface Plan {
    summary: string;
    steps: PlanStep[];
}

// Validation types
export type IssueSeverity = 'error' | 'warning' | 'info';

export interface ValidationIssue {
    severity: IssueSeverity;
    file: string;
    message: string;
    line?: number;
    suggestion?: string;
}

export interface ValidationResult {
    approved: boolean;
    score: number;
    issues: ValidationIssue[];
    suggestions: string[];
    summary: string;
}

// Timeline types
export interface AgentActivity {
    agentType: AgentType;
    agentName: string;
    startTime: string;
    endTime?: string;
    durationMs?: number;
    status: 'active' | 'completed' | 'error';
    messages: string[];
    thoughts: string[];
}

export interface AgentTimeline {
    totalDurationMs: number;
    agentCount: number;
    agentDurations: Record<AgentType, number>;
    timeline: AgentActivity[];
}

// SSE Event data types
export interface AgentThinkingEventData {
    agent: AgentType;
    agent_name: string;
    thought: string;
    action_type?: string;
    file_path?: string;
    step_index?: number;
    progress: number;
    timestamp: string;
}

export interface AgentMessageEventData {
    from_agent: AgentType;
    from_name: string;
    message: string;
    message_type: MessageType;
    to_agent?: AgentType;
    to_name?: string;
    metadata?: Record<string, any>;
    timestamp: string;
}

export interface AgentHandoffEventData {
    from_agent: AgentType;
    from_name: string;
    to_agent: AgentType;
    to_name: string;
    message?: string;
    context?: Record<string, any>;
    timestamp: string;
}

export interface PlanStepAddedEventData {
    step_index: number;
    step: PlanStep;
    total_steps: number;
    agent: AgentType;
    agent_name: string;
    timestamp: string;
}

export interface PlanReadyEventData {
    message: string;
    plan: Plan;
    awaiting_approval: boolean;
    agent: AgentType;
    agent_name: string;
    timestamp: string;
}

export interface ValidationIssueFoundEventData {
    issue: ValidationIssue;
    agent: AgentType;
    agent_name: string;
    timestamp: string;
}

export interface StepThinkingEventData {
    step_index: number;
    thought: string;
    action_type?: string;
    file_path?: string;
    progress: number;
    agent: AgentType;
    agent_name: string;
    timestamp: string;
}

// Interactive mode event
export interface InteractiveEvent {
    event: AgentEventType;
    data: Record<string, any>;
}

// Agent color map
export const AGENT_COLORS: Record<AgentType, string> = {
    nova: '#9333EA',      // Purple
    scout: '#3B82F6',     // Blue
    blueprint: '#F97316', // Orange
    forge: '#22C55E',     // Green
    guardian: '#EF4444',  // Red
    conductor: '#FFFFFF', // White
};

// Agent emoji map
export const AGENT_EMOJIS: Record<AgentType, string> = {
    nova: '🟣',
    scout: '🔵',
    blueprint: '🟠',
    forge: '🟢',
    guardian: '🔴',
    conductor: '⚪',
};

// Default agent info for fallbacks
export const DEFAULT_AGENTS: Record<AgentType, AgentInfo> = {
    nova: {
        type: 'nova',
        name: 'Nova',
        role: 'Intent Analyzer',
        color: AGENT_COLORS.nova,
        icon: 'sparkles',
        avatar_emoji: AGENT_EMOJIS.nova,
        personality: 'The curious investigator',
    },
    scout: {
        type: 'scout',
        name: 'Scout',
        role: 'Context Retriever',
        color: AGENT_COLORS.scout,
        icon: 'search',
        avatar_emoji: AGENT_EMOJIS.scout,
        personality: 'The code archaeologist',
    },
    blueprint: {
        type: 'blueprint',
        name: 'Blueprint',
        role: 'Planner',
        color: AGENT_COLORS.blueprint,
        icon: 'clipboard-list',
        avatar_emoji: AGENT_EMOJIS.blueprint,
        personality: 'The strategic architect',
    },
    forge: {
        type: 'forge',
        name: 'Forge',
        role: 'Executor',
        color: AGENT_COLORS.forge,
        icon: 'code',
        avatar_emoji: AGENT_EMOJIS.forge,
        personality: 'The master craftsman',
    },
    guardian: {
        type: 'guardian',
        name: 'Guardian',
        role: 'Validator',
        color: AGENT_COLORS.guardian,
        icon: 'shield-check',
        avatar_emoji: AGENT_EMOJIS.guardian,
        personality: 'The quality guardian',
    },
    conductor: {
        type: 'conductor',
        name: 'Conductor',
        role: 'Orchestrator',
        color: AGENT_COLORS.conductor,
        icon: 'users',
        avatar_emoji: AGENT_EMOJIS.conductor,
        personality: 'The team lead',
    },
};

// Helper function to get agent info
export function getAgentInfo(agentType: AgentType | string): AgentInfo {
    const type = agentType.toLowerCase() as AgentType;
    return DEFAULT_AGENTS[type] || DEFAULT_AGENTS.conductor;
}
