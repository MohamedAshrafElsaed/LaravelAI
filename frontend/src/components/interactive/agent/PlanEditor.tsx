'use client';

import { useState, useCallback, useMemo } from 'react';
import {
  Check,
  X,
  Edit2,
  Plus,
  Trash2,
  GripVertical,
  ChevronDown,
  ChevronUp,
  RefreshCw,
  AlertCircle,
  FileCode,
  FilePlus,
  FileX,
  Save,
} from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Plan, PlanStep } from './types';

interface PlanEditorProps {
  plan: Plan;
  onApprove: (plan?: Plan) => void;
  onReject: (reason?: string) => void;
  onRegenerate?: (instructions?: string) => void;
  isLoading?: boolean;
  className?: string;
}

// Action type colors and icons
const ACTION_STYLES = {
  create: {
    bg: 'bg-green-500/10',
    border: 'border-green-500/30',
    text: 'text-green-400',
    icon: FilePlus,
    label: 'Create',
  },
  modify: {
    bg: 'bg-yellow-500/10',
    border: 'border-yellow-500/30',
    text: 'text-yellow-400',
    icon: FileCode,
    label: 'Modify',
  },
  delete: {
    bg: 'bg-red-500/10',
    border: 'border-red-500/30',
    text: 'text-red-400',
    icon: FileX,
    label: 'Delete',
  },
};

export function PlanEditor({
  plan,
  onApprove,
  onReject,
  onRegenerate,
  isLoading = false,
  className = '',
}: PlanEditorProps) {
  const [editedPlan, setEditedPlan] = useState<Plan>({ ...plan });
  const [isEditing, setIsEditing] = useState(false);
  const [editingStepIndex, setEditingStepIndex] = useState<number | null>(null);
  const [showRejectModal, setShowRejectModal] = useState(false);
  const [rejectReason, setRejectReason] = useState('');
  const [regenerateInstructions, setRegenerateInstructions] = useState('');
  const [showRegenerateModal, setShowRegenerateModal] = useState(false);

  // Track if plan was modified
  const isModified = useMemo(() => {
    return JSON.stringify(plan) !== JSON.stringify(editedPlan);
  }, [plan, editedPlan]);

  // Reset to original plan
  const resetPlan = useCallback(() => {
    setEditedPlan({ ...plan });
    setIsEditing(false);
    setEditingStepIndex(null);
  }, [plan]);

  // Update step
  const updateStep = useCallback((index: number, updates: Partial<PlanStep>) => {
    setEditedPlan((prev) => ({
      ...prev,
      steps: prev.steps.map((step, i) =>
        i === index ? { ...step, ...updates } : step
      ),
    }));
  }, []);

  // Delete step
  const deleteStep = useCallback((index: number) => {
    setEditedPlan((prev) => ({
      ...prev,
      steps: prev.steps
        .filter((_, i) => i !== index)
        .map((step, i) => ({ ...step, order: i + 1 })),
    }));
  }, []);

  // Add step
  const addStep = useCallback((afterIndex: number) => {
    const newStep: PlanStep = {
      order: afterIndex + 2,
      action: 'modify',
      file: '',
      description: '',
    };
    setEditedPlan((prev) => {
      const steps = [...prev.steps];
      steps.splice(afterIndex + 1, 0, newStep);
      return {
        ...prev,
        steps: steps.map((step, i) => ({ ...step, order: i + 1 })),
      };
    });
    setEditingStepIndex(afterIndex + 1);
  }, []);

  // Move step
  const moveStep = useCallback((fromIndex: number, direction: 'up' | 'down') => {
    const toIndex = direction === 'up' ? fromIndex - 1 : fromIndex + 1;
    if (toIndex < 0 || toIndex >= editedPlan.steps.length) return;

    setEditedPlan((prev) => {
      const steps = [...prev.steps];
      [steps[fromIndex], steps[toIndex]] = [steps[toIndex], steps[fromIndex]];
      return {
        ...prev,
        steps: steps.map((step, i) => ({ ...step, order: i + 1 })),
      };
    });
  }, [editedPlan.steps.length]);

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
    setShowRejectModal(false);
    setRejectReason('');
  }, [rejectReason, onReject]);

  // Handle regenerate
  const handleRegenerate = useCallback(() => {
    onRegenerate?.(regenerateInstructions || undefined);
    setShowRegenerateModal(false);
    setRegenerateInstructions('');
  }, [regenerateInstructions, onRegenerate]);

  return (
    <div className={`rounded-lg border border-purple-500/30 bg-purple-500/5 overflow-hidden ${className}`}>
      {/* Header */}
      <div className="px-4 py-3 bg-purple-500/10 border-b border-purple-500/20">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-lg">📋</span>
            <h3 className="text-sm font-medium text-purple-300">Implementation Plan</h3>
            <span className="text-xs text-gray-500">
              {editedPlan.steps.length} {editedPlan.steps.length === 1 ? 'step' : 'steps'}
            </span>
            {isModified && (
              <span className="text-xs px-1.5 py-0.5 rounded bg-yellow-500/20 text-yellow-400">
                Modified
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            {isEditing ? (
              <>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={resetPlan}
                  disabled={isLoading}
                >
                  <X className="h-4 w-4 mr-1" />
                  Cancel
                </Button>
                <Button
                  size="sm"
                  onClick={() => setIsEditing(false)}
                  disabled={isLoading}
                >
                  <Save className="h-4 w-4 mr-1" />
                  Done
                </Button>
              </>
            ) : (
              <Button
                size="sm"
                variant="ghost"
                onClick={() => setIsEditing(true)}
                disabled={isLoading}
              >
                <Edit2 className="h-4 w-4 mr-1" />
                Edit
              </Button>
            )}
          </div>
        </div>

        {/* Summary */}
        <p className="text-sm text-gray-400 mt-2">{editedPlan.summary}</p>
      </div>

      {/* Steps List */}
      <div className="p-4 space-y-3">
        {editedPlan.steps.map((step, index) => (
          <PlanStepRow
            key={`step-${index}`}
            step={step}
            index={index}
            isEditing={isEditing}
            isStepEditing={editingStepIndex === index}
            onEdit={() => setEditingStepIndex(index)}
            onSaveEdit={() => setEditingStepIndex(null)}
            onUpdate={(updates) => updateStep(index, updates)}
            onDelete={() => deleteStep(index)}
            onMoveUp={() => moveStep(index, 'up')}
            onMoveDown={() => moveStep(index, 'down')}
            onAddAfter={() => addStep(index)}
            canMoveUp={index > 0}
            canMoveDown={index < editedPlan.steps.length - 1}
            isLoading={isLoading}
          />
        ))}

        {/* Add step button (when editing and no steps) */}
        {isEditing && editedPlan.steps.length === 0 && (
          <button
            onClick={() => addStep(-1)}
            className="w-full py-2 border border-dashed border-gray-600 rounded-lg text-gray-500 hover:border-gray-500 hover:text-gray-400 transition-colors text-sm"
          >
            <Plus className="h-4 w-4 inline mr-1" />
            Add Step
          </button>
        )}
      </div>

      {/* Action Buttons */}
      <div className="px-4 py-3 bg-gray-800/50 border-t border-gray-700/50">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            {onRegenerate && (
              <Button
                size="sm"
                variant="ghost"
                onClick={() => setShowRegenerateModal(true)}
                disabled={isLoading}
                className="text-gray-400 hover:text-gray-300"
              >
                <RefreshCw className="h-4 w-4 mr-1" />
                Regenerate
              </Button>
            )}
          </div>

          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="ghost"
              onClick={() => setShowRejectModal(true)}
              disabled={isLoading}
              className="text-red-400 hover:text-red-300"
            >
              <X className="h-4 w-4 mr-1" />
              Reject
            </Button>
            <Button
              size="sm"
              onClick={handleApprove}
              disabled={isLoading || editedPlan.steps.length === 0}
              className="bg-green-600 hover:bg-green-700"
            >
              <Check className="h-4 w-4 mr-1" />
              {isModified ? 'Approve Modified' : 'Approve Plan'}
            </Button>
          </div>
        </div>
      </div>

      {/* Reject Modal */}
      {showRejectModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-gray-900 border border-gray-700 rounded-lg p-4 max-w-md w-full mx-4">
            <h4 className="text-sm font-medium text-white mb-3">Reject Plan</h4>
            <textarea
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              placeholder="Optional: Explain why you're rejecting this plan..."
              className="w-full h-24 px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-red-500"
            />
            <div className="flex justify-end gap-2 mt-3">
              <Button
                size="sm"
                variant="ghost"
                onClick={() => setShowRejectModal(false)}
              >
                Cancel
              </Button>
              <Button
                size="sm"
                onClick={handleReject}
                className="bg-red-600 hover:bg-red-700"
              >
                Reject
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Regenerate Modal */}
      {showRegenerateModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-gray-900 border border-gray-700 rounded-lg p-4 max-w-md w-full mx-4">
            <h4 className="text-sm font-medium text-white mb-3">Regenerate Plan</h4>
            <textarea
              value={regenerateInstructions}
              onChange={(e) => setRegenerateInstructions(e.target.value)}
              placeholder="Optional: Provide additional instructions for the new plan..."
              className="w-full h-24 px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500"
            />
            <div className="flex justify-end gap-2 mt-3">
              <Button
                size="sm"
                variant="ghost"
                onClick={() => setShowRegenerateModal(false)}
              >
                Cancel
              </Button>
              <Button
                size="sm"
                onClick={handleRegenerate}
              >
                Regenerate
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// Individual plan step row component
function PlanStepRow({
  step,
  index,
  isEditing,
  isStepEditing,
  onEdit,
  onSaveEdit,
  onUpdate,
  onDelete,
  onMoveUp,
  onMoveDown,
  onAddAfter,
  canMoveUp,
  canMoveDown,
  isLoading,
}: {
  step: PlanStep;
  index: number;
  isEditing: boolean;
  isStepEditing: boolean;
  onEdit: () => void;
  onSaveEdit: () => void;
  onUpdate: (updates: Partial<PlanStep>) => void;
  onDelete: () => void;
  onMoveUp: () => void;
  onMoveDown: () => void;
  onAddAfter: () => void;
  canMoveUp: boolean;
  canMoveDown: boolean;
  isLoading: boolean;
}) {
  const style = ACTION_STYLES[step.action] || ACTION_STYLES.modify;
  const IconComponent = style.icon;

  if (isStepEditing) {
    return (
      <div className={`p-3 rounded-lg border-2 ${style.border} ${style.bg}`}>
        <div className="space-y-2">
          {/* Action selector */}
          <div className="flex items-center gap-2">
            <label className="text-xs text-gray-400">Action:</label>
            <select
              value={step.action}
              onChange={(e) => onUpdate({ action: e.target.value as PlanStep['action'] })}
              className="px-2 py-1 bg-gray-800 border border-gray-700 rounded text-sm text-white"
            >
              <option value="create">Create</option>
              <option value="modify">Modify</option>
              <option value="delete">Delete</option>
            </select>
          </div>

          {/* File path */}
          <input
            type="text"
            value={step.file}
            onChange={(e) => onUpdate({ file: e.target.value })}
            placeholder="File path..."
            className="w-full px-2 py-1 bg-gray-800 border border-gray-700 rounded text-sm text-white font-mono"
          />

          {/* Description */}
          <textarea
            value={step.description}
            onChange={(e) => onUpdate({ description: e.target.value })}
            placeholder="Description..."
            className="w-full px-2 py-1 bg-gray-800 border border-gray-700 rounded text-sm text-white h-16 resize-none"
          />

          {/* Save button */}
          <div className="flex justify-end">
            <Button size="sm" onClick={onSaveEdit}>
              Done
            </Button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={`flex items-start gap-3 p-3 rounded-lg border ${style.border} ${style.bg}`}>
      {/* Drag handle (when editing) */}
      {isEditing && (
        <div className="flex flex-col gap-0.5 pt-1">
          <button
            onClick={onMoveUp}
            disabled={!canMoveUp || isLoading}
            className="text-gray-500 hover:text-gray-300 disabled:opacity-30 disabled:cursor-not-allowed"
          >
            <ChevronUp className="h-4 w-4" />
          </button>
          <button
            onClick={onMoveDown}
            disabled={!canMoveDown || isLoading}
            className="text-gray-500 hover:text-gray-300 disabled:opacity-30 disabled:cursor-not-allowed"
          >
            <ChevronDown className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* Step number */}
      <span className="text-xs text-gray-500 font-mono w-5 pt-1">
        {step.order}.
      </span>

      {/* Action badge */}
      <span className={`text-xs px-1.5 py-0.5 rounded flex items-center gap-1 ${style.bg} ${style.text}`}>
        <IconComponent className="h-3 w-3" />
        {style.label}
      </span>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="font-mono text-xs text-gray-300 truncate">
          {step.file || '(no file specified)'}
        </div>
        <p className="text-sm text-gray-400 mt-0.5">
          {step.description || '(no description)'}
        </p>
      </div>

      {/* Edit/Delete buttons (when editing) */}
      {isEditing && (
        <div className="flex items-center gap-1">
          <button
            onClick={onAddAfter}
            disabled={isLoading}
            className="p-1 text-gray-500 hover:text-green-400 transition-colors"
            title="Add step after"
          >
            <Plus className="h-4 w-4" />
          </button>
          <button
            onClick={onEdit}
            disabled={isLoading}
            className="p-1 text-gray-500 hover:text-blue-400 transition-colors"
            title="Edit step"
          >
            <Edit2 className="h-4 w-4" />
          </button>
          <button
            onClick={onDelete}
            disabled={isLoading}
            className="p-1 text-gray-500 hover:text-red-400 transition-colors"
            title="Delete step"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      )}
    </div>
  );
}

export default PlanEditor;
