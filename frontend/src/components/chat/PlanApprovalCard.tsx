'use client';

import React, {useState} from 'react';
import {motion} from 'framer-motion';
import {
    AlertCircle,
    ArrowDown,
    ArrowUp,
    CheckCircle,
    ChevronDown,
    ChevronRight,
    Clock,
    Edit3,
    FileCode,
    Loader2,
    Minus,
    Plus,
    XCircle,
    Zap
} from 'lucide-react';
import type {Plan, PlanStep} from './types';

// ============== PLAN APPROVAL CARD ==============
interface PlanApprovalCardProps {
    plan: Plan;
    isLoading: boolean;
    onApprove: (modifiedPlan?: Plan) => void;
    onReject: (reason?: string) => void;
    onModify: (modifiedPlan: Plan) => void;
}

export function PlanApprovalCard({plan, isLoading, onApprove, onReject, onModify,}: PlanApprovalCardProps) {
    const [isExpanded, setIsExpanded] = useState(true);
    const [isEditing, setIsEditing] = useState(false);
    const [editedPlan, setEditedPlan] = useState<Plan>(plan);
    const [rejectionReason, setRejectionReason] = useState('');
    const [showRejectForm, setShowRejectForm] = useState(false);

    const handleApprove = () => {
        if (isEditing) {
            onModify(editedPlan);
        } else {
            onApprove();
        }
    };

    const handleReject = () => {
        if (showRejectForm) {
            onReject(rejectionReason || undefined);
        } else {
            setShowRejectForm(true);
        }
    };

    const updateStep = (index: number, updates: Partial<PlanStep>) => {
        const newSteps = [...editedPlan.steps];
        newSteps[index] = {...newSteps[index], ...updates};
        setEditedPlan({...editedPlan, steps: newSteps});
    };

    const removeStep = (index: number) => {
        const newSteps = editedPlan.steps.filter((_, i) => i !== index);
        // Re-order steps
        const reorderedSteps = newSteps.map((step, i) => ({...step, order: i + 1}));
        setEditedPlan({...editedPlan, steps: reorderedSteps});
    };

    const moveStep = (index: number, direction: 'up' | 'down') => {
        const newSteps = [...editedPlan.steps];
        const targetIndex = direction === 'up' ? index - 1 : index + 1;
        if (targetIndex < 0 || targetIndex >= newSteps.length) return;

        [newSteps[index], newSteps[targetIndex]] = [newSteps[targetIndex], newSteps[index]];
        // Re-order steps
        const reorderedSteps = newSteps.map((step, i) => ({...step, order: i + 1}));
        setEditedPlan({...editedPlan, steps: reorderedSteps});
    };

    const addStep = () => {
        const newStep: PlanStep = {
            order: editedPlan.steps.length + 1,
            action: 'create',
            file: '',
            description: '',
        };
        setEditedPlan({...editedPlan, steps: [...editedPlan.steps, newStep]});
    };

    const getActionIcon = (action: string) => {
        switch (action) {
            case 'create':
                return <Plus className="h-3.5 w-3.5 text-green-400"/>;
            case 'modify':
                return <Edit3 className="h-3.5 w-3.5 text-amber-400"/>;
            case 'delete':
                return <Minus className="h-3.5 w-3.5 text-red-400"/>;
            case 'analyze':
                return <FileCode className="h-3.5 w-3.5 text-blue-400"/>;
            default:
                return <FileCode className="h-3.5 w-3.5 text-gray-400"/>;
        }
    };

    const getActionColor = (action: string) => {
        switch (action) {
            case 'create':
                return 'bg-green-500/20 text-green-400 border-green-500/30';
            case 'modify':
                return 'bg-amber-500/20 text-amber-400 border-amber-500/30';
            case 'delete':
                return 'bg-red-500/20 text-red-400 border-red-500/30';
            case 'analyze':
                return 'bg-blue-500/20 text-blue-400 border-blue-500/30';
            default:
                return 'bg-gray-500/20 text-gray-400 border-gray-500/30';
        }
    };

    const getComplexityColor = (complexity?: string) => {
        switch (complexity) {
            case 'low':
                return 'text-green-400';
            case 'medium':
                return 'text-amber-400';
            case 'high':
                return 'text-red-400';
            default:
                return 'text-gray-400';
        }
    };

    const displayPlan = isEditing ? editedPlan : plan;

    return (
        <motion.div
            initial={{opacity: 0, y: 20, scale: 0.95}}
            animate={{opacity: 1, y: 0, scale: 1}}
            exit={{opacity: 0, y: -20, scale: 0.95}}
            className="rounded-xl border border-blue-500/30 bg-blue-500/5 overflow-hidden"
        >
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3 bg-blue-500/10 border-b border-blue-500/20">
                <div className="flex items-center gap-3">
                    <div className="p-2 rounded-lg bg-blue-500/20">
                        <AlertCircle className="h-5 w-5 text-blue-400"/>
                    </div>
                    <div>
                        <h3 className="font-semibold text-[var(--color-text-primary)]">Review Plan</h3>
                        <p className="text-sm text-[var(--color-text-muted)]">
                            {displayPlan.steps.length} step{displayPlan.steps.length !== 1 ? 's' : ''} planned
                        </p>
                    </div>
                </div>

                <div className="flex items-center gap-2">
                    {plan.complexity && (
                        <span className={`flex items-center gap-1 text-xs ${getComplexityColor(plan.complexity)}`}>
              <Zap className="h-3.5 w-3.5"/>
                            {plan.complexity}
            </span>
                    )}
                    {plan.estimated_time && (
                        <span className="flex items-center gap-1 text-xs text-[var(--color-text-muted)]">
              <Clock className="h-3.5 w-3.5"/>
                            {plan.estimated_time}
            </span>
                    )}
                    <button
                        onClick={() => setIsExpanded(!isExpanded)}
                        className="p-1.5 rounded-lg hover:bg-[var(--color-bg-hover)] text-[var(--color-text-muted)]"
                    >
                        {isExpanded ? <ChevronDown className="h-4 w-4"/> : <ChevronRight className="h-4 w-4"/>}
                    </button>
                </div>
            </div>

            {/* Summary */}
            <div className="px-4 py-3 border-b border-[var(--color-border-subtle)]">
                {isEditing ? (
                    <textarea
                        value={editedPlan.summary}
                        onChange={(e) => setEditedPlan({...editedPlan, summary: e.target.value})}
                        className="w-full px-3 py-2 rounded-lg bg-[var(--color-bg-elevated)] border border-[var(--color-border-subtle)] text-sm text-[var(--color-text-primary)] focus:outline-none focus:border-blue-500 resize-none"
                        rows={2}
                    />
                ) : (
                    <p className="text-sm text-[var(--color-text-secondary)]">{displayPlan.summary}</p>
                )}
            </div>

            {/* Steps */}
            {isExpanded && (
                <div className="px-4 py-3 space-y-2 max-h-64 overflow-y-auto">
                    {displayPlan.steps.map((step, index) => (
                        <div
                            key={step.order}
                            className={`flex items-start gap-3 p-3 rounded-lg border ${getActionColor(step.action)}`}
                        >
                            {/* Step number */}
                            <div
                                className="flex-shrink-0 w-6 h-6 rounded-full bg-black/20 flex items-center justify-center text-xs font-medium">
                                {step.order}
                            </div>

                            {/* Step content */}
                            <div className="flex-1 min-w-0">
                                {isEditing ? (
                                    <div className="space-y-2">
                                        <div className="flex items-center gap-2">
                                            <select
                                                value={step.action}
                                                onChange={(e) => updateStep(index, {action: e.target.value as PlanStep['action']})}
                                                className="px-2 py-1 rounded bg-black/20 border border-[var(--color-border-subtle)] text-xs text-[var(--color-text-primary)] focus:outline-none"
                                            >
                                                <option value="create">Create</option>
                                                <option value="modify">Modify</option>
                                                <option value="delete">Delete</option>
                                                <option value="analyze">Analyze</option>
                                            </select>
                                            <input
                                                type="text"
                                                value={step.file}
                                                onChange={(e) => updateStep(index, {file: e.target.value})}
                                                placeholder="File path"
                                                className="flex-1 px-2 py-1 rounded bg-black/20 border border-[var(--color-border-subtle)] text-xs text-[var(--color-text-primary)] focus:outline-none"
                                            />
                                        </div>
                                        <input
                                            type="text"
                                            value={step.description}
                                            onChange={(e) => updateStep(index, {description: e.target.value})}
                                            placeholder="Description"
                                            className="w-full px-2 py-1 rounded bg-black/20 border border-[var(--color-border-subtle)] text-xs text-[var(--color-text-secondary)] focus:outline-none"
                                        />
                                    </div>
                                ) : (
                                    <>
                                        <div className="flex items-center gap-2">
                                            {getActionIcon(step.action)}
                                            <span className="text-sm font-medium text-[var(--color-text-primary)]">
                        {step.action.charAt(0).toUpperCase() + step.action.slice(1)}
                      </span>
                                            <span className="text-sm text-blue-400 truncate">{step.file}</span>
                                        </div>
                                        <p className="text-xs text-[var(--color-text-muted)] mt-1">{step.description}</p>
                                    </>
                                )}
                            </div>

                            {/* Edit controls */}
                            {isEditing && (
                                <div className="flex flex-col gap-1">
                                    <button
                                        onClick={() => moveStep(index, 'up')}
                                        disabled={index === 0}
                                        className="p-1 rounded hover:bg-black/20 disabled:opacity-30"
                                    >
                                        <ArrowUp className="h-3 w-3"/>
                                    </button>
                                    <button
                                        onClick={() => moveStep(index, 'down')}
                                        disabled={index === displayPlan.steps.length - 1}
                                        className="p-1 rounded hover:bg-black/20 disabled:opacity-30"
                                    >
                                        <ArrowDown className="h-3 w-3"/>
                                    </button>
                                    <button
                                        onClick={() => removeStep(index)}
                                        className="p-1 rounded hover:bg-red-500/20 text-red-400"
                                    >
                                        <Minus className="h-3 w-3"/>
                                    </button>
                                </div>
                            )}
                        </div>
                    ))}

                    {isEditing && (
                        <button
                            onClick={addStep}
                            className="w-full flex items-center justify-center gap-2 p-2 rounded-lg border border-dashed border-[var(--color-border-subtle)] text-[var(--color-text-muted)] hover:border-blue-500 hover:text-blue-400 transition-colors"
                        >
                            <Plus className="h-4 w-4"/>
                            <span className="text-sm">Add Step</span>
                        </button>
                    )}
                </div>
            )}

            {/* Rejection reason form */}
            {showRejectForm && (
                <div className="px-4 py-3 border-t border-[var(--color-border-subtle)] bg-red-500/5">
          <textarea
              value={rejectionReason}
              onChange={(e) => setRejectionReason(e.target.value)}
              placeholder="Why are you rejecting this plan? (optional)"
              className="w-full px-3 py-2 rounded-lg bg-[var(--color-bg-elevated)] border border-red-500/30 text-sm text-[var(--color-text-primary)] placeholder-[var(--color-text-muted)] focus:outline-none focus:border-red-500 resize-none"
              rows={2}
          />
                </div>
            )}

            {/* Actions */}
            <div
                className="flex items-center justify-between px-4 py-3 bg-[var(--color-bg-surface)] border-t border-[var(--color-border-subtle)]">
                <button
                    onClick={() => setIsEditing(!isEditing)}
                    disabled={isLoading}
                    className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-bg-hover)] transition-colors disabled:opacity-50"
                >
                    <Edit3 className="h-4 w-4"/>
                    {isEditing ? 'Cancel Edit' : 'Edit Plan'}
                </button>

                <div className="flex items-center gap-2">
                    <button
                        onClick={handleReject}
                        disabled={isLoading}
                        className="flex items-center gap-2 px-4 py-2 rounded-lg bg-red-500/10 text-red-400 hover:bg-red-500/20 transition-colors disabled:opacity-50"
                    >
                        <XCircle className="h-4 w-4"/>
                        <span className="text-sm font-medium">
              {showRejectForm ? 'Confirm Reject' : 'Reject'}
            </span>
                    </button>
                    <button
                        onClick={handleApprove}
                        disabled={isLoading}
                        className="flex items-center gap-2 px-4 py-2 rounded-lg bg-green-500 text-white hover:bg-green-400 transition-colors disabled:opacity-50"
                    >
                        {isLoading ? (
                            <Loader2 className="h-4 w-4 animate-spin"/>
                        ) : (
                            <CheckCircle className="h-4 w-4"/>
                        )}
                        <span className="text-sm font-medium">
              {isEditing ? 'Approve Modified' : 'Approve & Execute'}
            </span>
                    </button>
                </div>
            </div>
        </motion.div>
    );
}

export default PlanApprovalCard;