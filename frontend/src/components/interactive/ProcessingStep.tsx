'use client';

import { useState } from 'react';
import {
  ChevronDown,
  ChevronRight,
  Loader2,
  CheckCircle2,
  AlertCircle,
  Clock,
  FileCode,
  FilePlus,
  FileEdit,
  FileX,
  Search,
  Database,
  Brain,
  GitBranch,
  Play,
  CheckSquare,
} from 'lucide-react';

export type StepStatus = 'pending' | 'running' | 'completed' | 'error';
export type StepType = 'analyze' | 'search' | 'read' | 'write' | 'edit' | 'create' | 'delete' | 'plan' | 'execute' | 'validate' | 'git' | 'custom';

interface ProcessingStepProps {
  type: StepType;
  title: string;
  description?: string;
  status: StepStatus;
  details?: React.ReactNode;
  files?: string[];
  duration?: number;
  collapsible?: boolean;
  defaultExpanded?: boolean;
}

const STEP_ICONS: Record<StepType, React.ReactNode> = {
  analyze: <Brain className="h-4 w-4" />,
  search: <Search className="h-4 w-4" />,
  read: <FileCode className="h-4 w-4" />,
  write: <FilePlus className="h-4 w-4" />,
  edit: <FileEdit className="h-4 w-4" />,
  create: <FilePlus className="h-4 w-4" />,
  delete: <FileX className="h-4 w-4" />,
  plan: <Database className="h-4 w-4" />,
  execute: <Play className="h-4 w-4" />,
  validate: <CheckSquare className="h-4 w-4" />,
  git: <GitBranch className="h-4 w-4" />,
  custom: <Clock className="h-4 w-4" />,
};

const STATUS_STYLES: Record<StepStatus, { icon: React.ReactNode; color: string; bg: string }> = {
  pending: {
    icon: <Clock className="h-3.5 w-3.5" />,
    color: 'text-gray-400',
    bg: 'bg-gray-500/10',
  },
  running: {
    icon: <Loader2 className="h-3.5 w-3.5 animate-spin" />,
    color: 'text-blue-400',
    bg: 'bg-blue-500/10',
  },
  completed: {
    icon: <CheckCircle2 className="h-3.5 w-3.5" />,
    color: 'text-green-400',
    bg: 'bg-green-500/10',
  },
  error: {
    icon: <AlertCircle className="h-3.5 w-3.5" />,
    color: 'text-red-400',
    bg: 'bg-red-500/10',
  },
};

export function ProcessingStep({
  type,
  title,
  description,
  status,
  details,
  files,
  duration,
  collapsible = true,
  defaultExpanded = false,
}: ProcessingStepProps) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);
  const statusStyle = STATUS_STYLES[status];
  const hasDetails = details || (files && files.length > 0);

  return (
    <div className={`rounded-lg border border-gray-800 ${statusStyle.bg} overflow-hidden`}>
      {/* Header */}
      <div
        className={`flex items-center gap-3 px-3 py-2 ${hasDetails && collapsible ? 'cursor-pointer hover:bg-gray-800/50' : ''}`}
        onClick={() => hasDetails && collapsible && setIsExpanded(!isExpanded)}
      >
        {/* Expand/Collapse indicator */}
        {hasDetails && collapsible ? (
          <span className="text-gray-500">
            {isExpanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
          </span>
        ) : (
          <span className="w-4" />
        )}

        {/* Step icon */}
        <span className={statusStyle.color}>{STEP_ICONS[type]}</span>

        {/* Title and description */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-white truncate">{title}</span>
            {files && files.length > 0 && (
              <span className="text-xs text-gray-500">
                {files.length} file{files.length !== 1 ? 's' : ''}
              </span>
            )}
          </div>
          {description && (
            <p className="text-xs text-gray-400 truncate">{description}</p>
          )}
        </div>

        {/* Status indicator */}
        <div className="flex items-center gap-2">
          {duration !== undefined && status === 'completed' && (
            <span className="text-xs text-gray-500">{duration}ms</span>
          )}
          <span className={statusStyle.color}>{statusStyle.icon}</span>
        </div>
      </div>

      {/* Expandable details */}
      {isExpanded && hasDetails && (
        <div className="border-t border-gray-800 bg-gray-900/50 px-4 py-3">
          {/* File list */}
          {files && files.length > 0 && (
            <div className="space-y-1 mb-3">
              {files.map((file, index) => (
                <div key={index} className="flex items-center gap-2 text-xs">
                  <FileCode className="h-3 w-3 text-gray-500" />
                  <span className="text-gray-300 font-mono">{file}</span>
                </div>
              ))}
            </div>
          )}

          {/* Custom details */}
          {details}
        </div>
      )}
    </div>
  );
}
