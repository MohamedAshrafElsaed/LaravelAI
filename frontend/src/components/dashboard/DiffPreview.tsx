'use client';

import {motion} from 'framer-motion';

interface DiffLine {
    num: number;
    content: string;
    type: 'added' | 'removed' | 'neutral';
}

interface DiffPreviewProps {
    fileName?: string;
    additions?: number;
    deletions?: number;
    lines?: DiffLine[];
    onStage?: () => void;
    onDiscard?: () => void;
}

const defaultLines: DiffLine[] = [
    {num: 142, content: '  const handleScroll = useCallback(() => {', type: 'neutral'},
    {num: 143, content: '    if (!containerRef.current) return', type: 'neutral'},
    {num: 144, content: '-   const scrollTop = containerRef.current.scrollTop', type: 'removed'},
    {num: 144, content: '+   const { scrollTop, clientHeight } = containerRef.current', type: 'added'},
    {num: 145, content: '    ', type: 'neutral'},
    {num: 146, content: '-   setScrollPos(scrollTop)', type: 'removed'},
    {num: 146, content: '+   // Optimize state updates using requestAnimationFrame', type: 'added'},
    {num: 147, content: '+   requestAnimationFrame(() => {', type: 'added'},
    {num: 148, content: '+     setScrollState({ top: scrollTop, height: clientHeight })', type: 'added'},
    {num: 149, content: '+   })', type: 'added'},
    {num: 150, content: '  }, [])', type: 'neutral'},
];

export default function DiffPreview({
                                        fileName = 'src/components/VirtualList.tsx',
                                        additions = 5,
                                        deletions = 2,
                                        lines = defaultLines,
                                        onStage,
                                        onDiscard,
                                    }: DiffPreviewProps) {
    return (
        <div
            className="border border-[var(--color-border-subtle)] rounded-sm bg-[var(--color-bg-primary)] overflow-hidden font-mono text-xs">
            {/* Header */}
            <div
                className="flex items-center justify-between px-3 py-2 bg-[var(--color-bg-surface)] border-b border-[var(--color-border-subtle)]">
                <div className="flex items-center gap-2">
                    <span className="text-[var(--color-text-muted)]">{fileName}</span>
                    <span className="text-xs text-green-500">+{additions}</span>
                    <span className="text-xs text-red-500">-{deletions}</span>
                </div>
                <div className="flex gap-2">
                    <button
                        onClick={onStage}
                        className="px-2 py-0.5 bg-[var(--color-primary)] text-white rounded-sm text-[10px] font-bold hover:bg-[var(--color-primary-hover)] transition-colors"
                    >
                        STAGE
                    </button>
                    <button
                        onClick={onDiscard}
                        className="px-2 py-0.5 bg-[var(--color-bg-elevated)] text-[var(--color-text-secondary)] rounded-sm text-[10px] hover:bg-[var(--color-bg-hover)] transition-colors"
                    >
                        DISCARD
                    </button>
                </div>
            </div>

            {/* Diff Content */}
            <div className="overflow-x-auto">
                <table className="w-full border-collapse">
                    <tbody>
                    {lines.map((line, i) => (
                        <motion.tr
                            key={i}
                            initial={{opacity: 0}}
                            animate={{opacity: 1}}
                            transition={{delay: i * 0.02}}
                            className={`${
                                line.type === 'added'
                                    ? 'bg-green-500/10'
                                    : line.type === 'removed'
                                        ? 'bg-red-500/10'
                                        : ''
                            }`}
                        >
                            <td className="w-12 px-2 py-0.5 text-right text-[var(--color-text-dimmer)] border-r border-[var(--color-border-subtle)] select-none bg-[var(--color-bg-surface)]">
                                {line.type === 'added' ? '+' : line.type === 'removed' ? '-' : line.num}
                            </td>
                            <td className="px-4 py-0.5 whitespace-pre">
                  <span
                      className={`${
                          line.type === 'added'
                              ? 'text-green-400'
                              : line.type === 'removed'
                                  ? 'text-red-400 line-through opacity-70'
                                  : 'text-[var(--color-text-secondary)]'
                      }`}
                  >
                    {line.content}
                  </span>
                            </td>
                        </motion.tr>
                    ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
}