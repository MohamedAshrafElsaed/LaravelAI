'use client';

import {useCallback, useMemo, useState} from 'react';
import {Check, ChevronRight, Edit2, Loader2, RefreshCw, Trash2, X,} from 'lucide-react';
import {Plan, PlanStep} from './types';

interface PlanEditorProps {
    plan: Plan;
    onApprove: (plan?: Plan) => void;
    onReject: (reason?: string) => void;
    onRegenerate?: (instructions?: string) => void;
    isLoading?: boolean;
    className?: string;
}

// Action type colors
const ACTION_COLORS = {
    create: 'text-green-400',
    modify: 'text-yellow-400',
    delete: 'text-red-400',
};

export function PlanEditor({
                               plan,
                               onApprove,
                               onReject,
                               onRegenerate,
                               isLoading = false,
                               className = '',
                           }: PlanEditorProps) {
    const [editedPlan, setEditedPlan] = useState<Plan>({...plan});
    const [isEditing, setIsEditing] = useState(false);
    const [editingStepIndex, setEditingStepIndex] = useState<number | null>(null);
    const [showRejectInput, setShowRejectInput] = useState(false);
    const [rejectReason, setRejectReason] = useState('');

    // Track if plan was modified
    const isModified = useMemo(() => {
        return JSON.stringify(plan) !== JSON.stringify(editedPlan);
    }, [plan, editedPlan]);

    // Reset to original plan
    const resetPlan = useCallback(() => {
        setEditedPlan({...plan});
        setIsEditing(false);
        setEditingStepIndex(null);
    }, [plan]);

    // Update step
    const updateStep = useCallback((index: number, updates: Partial<PlanStep>) => {
        setEditedPlan((prev) => ({
            ...prev,
            steps: prev.steps.map((step, i) =>
                i === index ? {...step, ...updates} : step
            ),
        }));
    }, []);

    // Delete step
    const deleteStep = useCallback((index: number) => {
        setEditedPlan((prev) => ({
            ...prev,
            steps: prev.steps
                .filter((_, i) => i !== index)
                .map((step, i) => ({...step, order: i + 1})),
        }));
    }, []);

    // Handle approve
    const handleApprove = useCallback(() => {
        if (isModified) {
            onApprove(editedPlan);
        } else {
            onApprove();
        }
    }, [isModified, editedPlan, onApprove]);

    // Handle reject
    const handleReject = useCallback(() => {
        onReject(rejectReason || undefined);
        setShowRejectInput(false);
        setRejectReason('');
    }, [rejectReason, onReject]);

    return (
        <div className={`font-mono text-sm ${className}`}>
            {/* Header */}
            <div className="flex items-center gap-2 text-purple-400 mb-2">
                <ChevronRight className="h-4 w-4"/>
                <span className="font-semibold">Blueprint</span>
                <span className="text-gray-500">- Implementation Plan</span>
                {isModified && <span className="text-yellow-400 text-xs">(modified)</span>}
            </div>

            {/* Summary */}
            <div className="text-gray-400 mb-3 pl-6">
                {editedPlan.summary}
            </div>

            {/* Steps */}
            <div className="space-y-1 pl-4 mb-4">
                {editedPlan.steps.map((step, index) => {
                    const actionColor = ACTION_COLORS[step.action] || 'text-gray-400';

                    if (editingStepIndex === index) {
                        return (
                            <div key={index} className="pl-2 py-2 border-l-2 border-purple-500">
                                <div className="flex items-center gap-2 mb-2">
                                    <select
                                        value={step.action}
                                        onChange={(e) => updateStep(index, {action: e.target.value as PlanStep['action']})}
                                        className="px-2 py-1 bg-gray-800 border border-gray-700 rounded text-xs"
                                    >
                                        <option value="create">create</option>
                                        <option value="modify">modify</option>
                                        <option value="delete">delete</option>
                                    </select>
                                    <input
                                        type="text"
                                        value={step.file}
                                        onChange={(e) => updateStep(index, {file: e.target.value})}
                                        placeholder="file path"
                                        className="flex-1 px-2 py-1 bg-gray-800 border border-gray-700 rounded text-xs"
                                    />
                                </div>
                                <input
                                    type="text"
                                    value={step.description}
                                    onChange={(e) => updateStep(index, {description: e.target.value})}
                                    placeholder="description"
                                    className="w-full px-2 py-1 bg-gray-800 border border-gray-700 rounded text-xs mb-2"
                                />
                                <button
                                    onClick={() => setEditingStepIndex(null)}
                                    className="text-xs text-blue-400 hover:text-blue-300"
                                >
                                    Done
                                </button>
                            </div>
                        );
                    }

                    return (
                        <div key={index} className="flex items-start gap-2 group">
                            <span className="text-gray-600 w-4">{step.order}.</span>
                            <span className={`${actionColor} w-14`}>[{step.action}]</span>
                            <span className="text-blue-400">{step.file}</span>
                            {step.description && (
                                <span className="text-gray-500">- {step.description}</span>
                            )}
                            {isEditing && (
                                <div className="hidden group-hover:flex items-center gap-1 ml-2">
                                    <button
                                        onClick={() => setEditingStepIndex(index)}
                                        className="text-gray-600 hover:text-blue-400"
                                    >
                                        <Edit2 className="h-3 w-3"/>
                                    </button>
                                    <button
                                        onClick={() => deleteStep(index)}
                                        className="text-gray-600 hover:text-red-400"
                                    >
                                        <Trash2 className="h-3 w-3"/>
                                    </button>
                                </div>
                            )}
                        </div>
                    );
                })}
            </div>

            {/* Reject reason input */}
            {showRejectInput && (
                <div className="pl-6 mb-4">
                    <input
                        type="text"
                        value={rejectReason}
                        onChange={(e) => setRejectReason(e.target.value)}
                        placeholder="Reason for rejection (optional)..."
                        className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded text-sm mb-2"
                        onKeyDown={(e) => {
                            if (e.key === 'Enter') handleReject();
                            if (e.key === 'Escape') setShowRejectInput(false);
                        }}
                        autoFocus
                    />
                    <div className="flex gap-2">
                        <button
                            onClick={handleReject}
                            className="text-xs text-red-400 hover:text-red-300"
                        >
                            Confirm Reject
                        </button>
                        <button
                            onClick={() => setShowRejectInput(false)}
                            className="text-xs text-gray-500 hover:text-gray-400"
                        >
                            Cancel
                        </button>
                    </div>
                </div>
            )}

            {/* Action buttons */}
            {!showRejectInput && (
                <div className="flex items-center gap-4 pl-6">
                    <button
                        onClick={handleApprove}
                        disabled={isLoading || editedPlan.steps.length === 0}
                        className="flex items-center gap-1 text-green-400 hover:text-green-300 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        {isLoading ? (
                            <Loader2 className="h-4 w-4 animate-spin"/>
                        ) : (
                            <Check className="h-4 w-4"/>
                        )}
                        <span>{isModified ? 'approve (modified)' : 'approve'}</span>
                    </button>

                    <button
                        onClick={() => setShowRejectInput(true)}
                        disabled={isLoading}
                        className="flex items-center gap-1 text-red-400 hover:text-red-300 disabled:opacity-50"
                    >
                        <X className="h-4 w-4"/>
                        <span>reject</span>
                    </button>

                    <button
                        onClick={() => setIsEditing(!isEditing)}
                        disabled={isLoading}
                        className="flex items-center gap-1 text-gray-400 hover:text-gray-300 disabled:opacity-50"
                    >
                        <Edit2 className="h-4 w-4"/>
                        <span>{isEditing ? 'done editing' : 'edit'}</span>
                    </button>

                    {isModified && (
                        <button
                            onClick={resetPlan}
                            disabled={isLoading}
                            className="flex items-center gap-1 text-gray-500 hover:text-gray-400 disabled:opacity-50"
                        >
                            <RefreshCw className="h-4 w-4"/>
                            <span>reset</span>
                        </button>
                    )}
                </div>
            )}
        </div>
    );
}

export default PlanEditor;
