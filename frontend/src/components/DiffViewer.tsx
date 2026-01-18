'use client';

import {useMemo} from 'react';
import {FileCode, Minus, Plus} from 'lucide-react';

interface DiffViewerProps {
    diff: string;
    fileName?: string;
}

interface DiffLine {
    type: 'header' | 'hunk' | 'addition' | 'deletion' | 'context';
    content: string;
    oldLineNumber?: number;
    newLineNumber?: number;
}

interface DiffStats {
    additions: number;
    deletions: number;
}

// Parse unified diff format
function parseDiff(diff: string): { lines: DiffLine[]; stats: DiffStats } {
    const lines: DiffLine[] = [];
    const rawLines = diff.split('\n');

    let oldLine = 0;
    let newLine = 0;
    let additions = 0;
    let deletions = 0;

    for (const line of rawLines) {
        if (line.startsWith('---') || line.startsWith('+++')) {
            lines.push({type: 'header', content: line});
        } else if (line.startsWith('@@')) {
            // Parse hunk header: @@ -start,count +start,count @@
            const match = line.match(/@@ -(\d+),?\d* \+(\d+),?\d* @@/);
            if (match) {
                oldLine = parseInt(match[1], 10);
                newLine = parseInt(match[2], 10);
            }
            lines.push({type: 'hunk', content: line});
        } else if (line.startsWith('+')) {
            lines.push({
                type: 'addition',
                content: line.slice(1),
                newLineNumber: newLine++,
            });
            additions++;
        } else if (line.startsWith('-')) {
            lines.push({
                type: 'deletion',
                content: line.slice(1),
                oldLineNumber: oldLine++,
            });
            deletions++;
        } else if (line.startsWith(' ')) {
            lines.push({
                type: 'context',
                content: line.slice(1),
                oldLineNumber: oldLine++,
                newLineNumber: newLine++,
            });
        } else if (line.length > 0) {
            // Handle lines without prefix (shouldn't happen in valid diff)
            lines.push({
                type: 'context',
                content: line,
                oldLineNumber: oldLine++,
                newLineNumber: newLine++,
            });
        }
    }

    return {lines, stats: {additions, deletions}};
}

export function DiffViewer({diff, fileName}: DiffViewerProps) {
    const {lines, stats} = useMemo(() => parseDiff(diff), [diff]);

    if (!diff || diff.trim() === '') {
        return (
            <div className="flex h-full items-center justify-center text-gray-500">
                <p>No changes to display</p>
            </div>
        );
    }

    return (
        <div className="flex h-full flex-col bg-gray-950">
            {/* Header */}
            {fileName && (
                <div className="flex items-center justify-between border-b border-gray-800 px-4 py-2">
                    <div className="flex items-center gap-2">
                        <FileCode className="h-4 w-4 text-gray-400"/>
                        <span className="font-mono text-sm text-gray-300">{fileName}</span>
                    </div>
                    <div className="flex items-center gap-3">
            <span className="flex items-center gap-1 text-sm text-green-400">
              <Plus className="h-4 w-4"/>
                {stats.additions}
            </span>
                        <span className="flex items-center gap-1 text-sm text-red-400">
              <Minus className="h-4 w-4"/>
                            {stats.deletions}
            </span>
                    </div>
                </div>
            )}

            {/* Diff Content */}
            <div className="flex-1 overflow-auto">
                <table className="w-full font-mono text-sm">
                    <tbody>
                    {lines.map((line, index) => (
                        <DiffLineRow key={index} line={line}/>
                    ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
}

// Diff line row component
function DiffLineRow({line}: { line: DiffLine }) {
    const bgColor = {
        header: 'bg-gray-800',
        hunk: 'bg-blue-900/30',
        addition: 'bg-green-900/30',
        deletion: 'bg-red-900/30',
        context: 'bg-transparent',
    }[line.type];

    const textColor = {
        header: 'text-gray-400',
        hunk: 'text-blue-300',
        addition: 'text-green-300',
        deletion: 'text-red-300',
        context: 'text-gray-400',
    }[line.type];

    const lineNumColor = {
        header: 'text-transparent',
        hunk: 'text-blue-500',
        addition: 'text-green-600',
        deletion: 'text-red-600',
        context: 'text-gray-600',
    }[line.type];

    const prefix = {
        header: '',
        hunk: '',
        addition: '+',
        deletion: '-',
        context: ' ',
    }[line.type];

    return (
        <tr className={`${bgColor} border-b border-gray-800/50`}>
            {/* Old line number */}
            <td className={`w-12 select-none px-2 py-0 text-right ${lineNumColor}`}>
                {line.type === 'hunk' || line.type === 'header'
                    ? ''
                    : line.type === 'addition'
                        ? ''
                        : line.oldLineNumber || ''}
            </td>

            {/* New line number */}
            <td className={`w-12 select-none px-2 py-0 text-right ${lineNumColor} border-r border-gray-800`}>
                {line.type === 'hunk' || line.type === 'header'
                    ? ''
                    : line.type === 'deletion'
                        ? ''
                        : line.newLineNumber || ''}
            </td>

            {/* Prefix */}
            <td className={`w-6 select-none px-1 py-0 text-center ${textColor} font-bold`}>
                {prefix}
            </td>

            {/* Content */}
            <td className={`px-2 py-0 ${textColor} whitespace-pre`}>
                <code>{line.content}</code>
            </td>
        </tr>
    );
}

// Compact diff stats component (for use in lists)
export function DiffStats({diff}: { diff: string }) {
    const {stats} = useMemo(() => parseDiff(diff), [diff]);

    return (
        <div className="flex items-center gap-2 text-xs">
      <span className="flex items-center gap-0.5 text-green-400">
        <Plus className="h-3 w-3"/>
          {stats.additions}
      </span>
            <span className="flex items-center gap-0.5 text-red-400">
        <Minus className="h-3 w-3"/>
                {stats.deletions}
      </span>
        </div>
    );
}
