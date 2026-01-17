'use client';

import { useState } from 'react';
import {
  ChevronDown,
  ChevronRight,
  FileCode,
  FilePlus,
  FileEdit,
  FileX,
  Eye,
  CheckCircle2,
  Copy,
  Check,
} from 'lucide-react';

export type FileOperationType = 'read' | 'write' | 'edit' | 'create' | 'delete';

interface FileOperationProps {
  type: FileOperationType;
  filePath: string;
  content?: string;
  diff?: string;
  lineCount?: number;
  showContent?: boolean;
  defaultExpanded?: boolean;
  onCopy?: () => void;
}

const OPERATION_CONFIG: Record<FileOperationType, { icon: React.ReactNode; label: string; color: string; bg: string }> = {
  read: {
    icon: <Eye className="h-4 w-4" />,
    label: 'Read',
    color: 'text-blue-400',
    bg: 'bg-blue-500/10',
  },
  write: {
    icon: <FilePlus className="h-4 w-4" />,
    label: 'Write',
    color: 'text-green-400',
    bg: 'bg-green-500/10',
  },
  edit: {
    icon: <FileEdit className="h-4 w-4" />,
    label: 'Edit',
    color: 'text-yellow-400',
    bg: 'bg-yellow-500/10',
  },
  create: {
    icon: <FilePlus className="h-4 w-4" />,
    label: 'Create',
    color: 'text-green-400',
    bg: 'bg-green-500/10',
  },
  delete: {
    icon: <FileX className="h-4 w-4" />,
    label: 'Delete',
    color: 'text-red-400',
    bg: 'bg-red-500/10',
  },
};

export function FileOperation({
  type,
  filePath,
  content,
  diff,
  lineCount,
  showContent = true,
  defaultExpanded = false,
}: FileOperationProps) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);
  const [copied, setCopied] = useState(false);
  const config = OPERATION_CONFIG[type];
  const hasContent = showContent && (content || diff);

  const handleCopy = async (e: React.MouseEvent) => {
    e.stopPropagation();
    const textToCopy = diff || content || '';
    await navigator.clipboard.writeText(textToCopy);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Count lines for "Show full diff" indicator
  const contentLines = (diff || content || '').split('\n').length;
  const truncatedLines = contentLines > 20 ? 20 : contentLines;
  const hasMoreLines = contentLines > 20;

  return (
    <div className={`rounded-lg border border-gray-800 ${config.bg} overflow-hidden`}>
      {/* Header */}
      <div
        className={`flex items-center gap-3 px-3 py-2 ${hasContent ? 'cursor-pointer hover:bg-gray-800/50' : ''}`}
        onClick={() => hasContent && setIsExpanded(!isExpanded)}
      >
        {hasContent ? (
          <span className="text-gray-500">
            {isExpanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
          </span>
        ) : (
          <span className="w-4" />
        )}

        <span className={config.color}>{config.icon}</span>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className={`text-xs px-1.5 py-0.5 rounded ${config.bg} ${config.color}`}>
              {config.label}
            </span>
            <span className="text-sm text-gray-300 font-mono truncate">{filePath}</span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {lineCount !== undefined && (
            <span className="text-xs text-gray-500">{lineCount} lines</span>
          )}
          {hasContent && (
            <button
              onClick={handleCopy}
              className="p-1 text-gray-500 hover:text-gray-300 rounded"
              title="Copy to clipboard"
            >
              {copied ? <Check className="h-3.5 w-3.5 text-green-400" /> : <Copy className="h-3.5 w-3.5" />}
            </button>
          )}
          <CheckCircle2 className="h-4 w-4 text-green-400" />
        </div>
      </div>

      {/* Content/Diff view */}
      {isExpanded && hasContent && (
        <div className="border-t border-gray-800">
          <pre className="text-xs font-mono overflow-x-auto p-3 max-h-96 overflow-y-auto">
            {diff ? (
              <DiffView diff={diff} maxLines={isExpanded ? undefined : truncatedLines} />
            ) : (
              <code className="text-gray-300">{content}</code>
            )}
          </pre>
          {hasMoreLines && !isExpanded && (
            <div className="px-3 py-2 border-t border-gray-800 text-center">
              <span className="text-xs text-gray-500">
                Show {contentLines - truncatedLines} more lines
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// Diff view with syntax highlighting
function DiffView({ diff, maxLines }: { diff: string; maxLines?: number }) {
  const lines = diff.split('\n');
  const displayLines = maxLines ? lines.slice(0, maxLines) : lines;

  return (
    <div className="space-y-0">
      {displayLines.map((line, index) => {
        let className = 'text-gray-400';
        let bgClass = '';

        if (line.startsWith('+') && !line.startsWith('+++')) {
          className = 'text-green-400';
          bgClass = 'bg-green-500/10';
        } else if (line.startsWith('-') && !line.startsWith('---')) {
          className = 'text-red-400';
          bgClass = 'bg-red-500/10';
        } else if (line.startsWith('@@')) {
          className = 'text-cyan-400';
          bgClass = 'bg-cyan-500/5';
        } else if (line.startsWith('diff') || line.startsWith('index')) {
          className = 'text-gray-500';
        }

        return (
          <div key={index} className={`${bgClass} px-2 -mx-2`}>
            <span className={className}>{line || ' '}</span>
          </div>
        );
      })}
    </div>
  );
}

// Multi-file operation group
interface FileOperationGroupProps {
  title: string;
  operations: Array<{
    type: FileOperationType;
    filePath: string;
    content?: string;
    diff?: string;
    lineCount?: number;
  }>;
  defaultExpanded?: boolean;
}

export function FileOperationGroup({
  title,
  operations,
  defaultExpanded = false,
}: FileOperationGroupProps) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);

  return (
    <div className="rounded-lg border border-gray-800 bg-gray-900/50 overflow-hidden">
      {/* Header */}
      <div
        className="flex items-center gap-3 px-3 py-2.5 cursor-pointer hover:bg-gray-800/50"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <span className="text-gray-500">
          {isExpanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
        </span>

        <FileCode className="h-4 w-4 text-blue-400" />

        <div className="flex-1">
          <span className="text-sm font-medium text-white">{title}</span>
          <span className="ml-2 text-xs text-gray-500">
            {operations.length} file{operations.length !== 1 ? 's' : ''}
          </span>
        </div>

        <CheckCircle2 className="h-4 w-4 text-green-400" />
      </div>

      {/* File list */}
      {isExpanded && (
        <div className="border-t border-gray-800 p-2 space-y-2">
          {operations.map((op, index) => (
            <FileOperation
              key={index}
              type={op.type}
              filePath={op.filePath}
              content={op.content}
              diff={op.diff}
              lineCount={op.lineCount}
            />
          ))}
        </div>
      )}
    </div>
  );
}
