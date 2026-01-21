
// ============== AGENT TYPES ==============
export type AgentType = 'nova' | 'scout' | 'blueprint' | 'forge' | 'guardian' | 'conductor';

export type MessageType = 'greeting' | 'thinking' | 'completion' | 'handoff' | 'error' | 'custom';

export interface AgentInfo {
    type: AgentType;
    name: string;
    description: string;
    emoji: string;
    color: string;
    bgColor: string;
    borderColor: string;
    role: string;
}

// ============== CONVERSATION TYPES ==============
export interface ConversationEntry {
    id: string;
    type: 'message' | 'handoff' | 'step' | 'system';
    timestamp: string;
    agentType?: AgentType;
    toAgentType?: AgentType;
    message?: string;
    messageType?: MessageType;
    actionType?: string;
    filePath?: string;
    completed?: boolean;
    systemType?: 'info' | 'success' | 'warning' | 'error';
}

export interface AgentThinkingState {
    agent: AgentInfo;
    thought: string;
    actionType?: string;
    filePath?: string;
    progress: number;
}

// ============== MESSAGE TYPES ==============
export interface Message {
    id: string;
    role: 'user' | 'assistant' | 'system';
    content: string;
    timestamp: Date;
    isStreaming?: boolean;
    processingData?: {
        intent?: any;
        plan?: Plan;
        execution_results?: ExecutionResult[];
        validation?: ValidationResult;
        success?: boolean;
        error?: string;
        agent_activity?: ConversationEntry[];
        agent_timeline?: AgentTimeline;
    };
}

// ============== PLAN TYPES ==============
export interface PlanStep {
    order: number;
    action: 'create' | 'modify' | 'delete' | 'analyze';
    file: string;
    description: string;
    dependencies?: string[];
    estimated_lines?: number;
}

export interface Plan {
    summary: string;
    steps: PlanStep[];
    estimated_time?: string;
    complexity?: 'low' | 'medium' | 'high';
    affected_files?: string[];
}

// ============== EXECUTION TYPES ==============
export interface ExecutionResult {
    file: string;
    action: 'create' | 'modify' | 'delete';
    success: boolean;
    content?: string;
    diff?: string;
    original_content?: string;
    error?: string;
    lines_changed?: number;
}

// ============== VALIDATION TYPES ==============
export interface ValidationIssue {
    severity: 'error' | 'warning' | 'info';
    message: string;
    file?: string;
    line?: number;
    suggestion?: string;
    auto_fixable?: boolean;
}

export interface ValidationResult {
    approved: boolean;
    score: number;
    issues: ValidationIssue[];
    suggestions: string[];
    summary: string;
}

// ============== TIMELINE TYPES ==============
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

// ============== SSE EVENT TYPES ==============
export type SSEEventType =
    | 'connected'
    | 'agent_message'
    | 'agent_handoff'
    | 'agent_thinking'
    | 'intent_started'
    | 'intent_thinking'
    | 'intent_analyzed'
    | 'context_started'
    | 'context_thinking'
    | 'context_retrieved'
    | 'planning_started'
    | 'planning_thinking'
    | 'plan_step_added'
    | 'plan_created'
    | 'plan_ready'
    | 'plan_approved'
    | 'execution_started'
    | 'step_started'
    | 'step_thinking'
    | 'step_completed'
    | 'execution_completed'
    | 'validation_started'
    | 'validation_thinking'
    | 'validation_issue_found'
    | 'validation_fix_started'
    | 'validation_result'
    | 'answer_chunk'
    | 'complete'
    | 'error';

export interface InteractiveEvent {
    event: SSEEventType;
    data: any;
}

// ============== GIT TYPES ==============
export interface GitChangeFile {
    file: string;
    action: 'create' | 'modify' | 'delete';
    content?: string;
    diff?: string;
    original_content?: string;
}

export interface GitChange {
    id: string;
    conversation_id: string;
    project_id: string;
    message_id?: string;
    branch_name: string;
    base_branch: string;
    commit_hash?: string;
    status: 'pending' | 'applied' | 'pushed' | 'pr_created' | 'pr_merged' | 'merged' | 'rolled_back' | 'discarded';
    pr_number?: number;
    pr_url?: string;
    pr_state?: string;
    title?: string;
    description?: string;
    files_changed?: GitChangeFile[];
    change_summary?: string;
    rollback_commit?: string;
    rolled_back_at?: string;
    rolled_back_from_status?: string;
    created_at: string;
    updated_at: string;
    applied_at?: string;
    pushed_at?: string;
    pr_created_at?: string;
    merged_at?: string;
}

// ============== API TYPES ==============
export interface PlanApprovalRequest {
    conversation_id: string;
    approved: boolean;
    modified_plan?: Plan;
    rejection_reason?: string;
}

export interface Conversation {
    id: string;
    project_id: string;
    title: string | null;
    created_at: string;
    updated_at: string;
    message_count: number;
    last_message?: string | null;
}

export interface ConversationMessage {
    id: string;
    role: 'user' | 'assistant' | 'system';
    content: string;
    created_at: string;
    processing_data?: any;
}