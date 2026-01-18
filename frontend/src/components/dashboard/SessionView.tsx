'use client';

import {useEffect, useMemo, useState} from 'react';
import {Check, ChevronDown, Circle, Copy, ExternalLink, Image, Send, Sparkles} from 'lucide-react';

const loadingStatuses = ['Thinking...', 'Processing...', 'Generating...', 'Shimmying...', 'Clauding...'];

interface ActivityItem {
    type: 'glob' | 'read' | 'grep' | 'todo';
    path?: string;
    pattern?: string;
    lines?: number;
    items?: string[];
}

interface DiffLine {
    type: 'add' | 'remove' | 'neutral';
    num: number;
    code: string;
}

const activity: ActivityItem[] = [
    {type: 'glob', path: '**/Notifications/**/*.php'},
    {type: 'read', path: '/home/user/ConvertedOrders/app/Notifications/BaseNotification.php', lines: 227},
    {type: 'grep', pattern: 'implements ShouldQueue|onQueue|queue'},
    {
        type: 'todo',
        items: ['Creating VerifyEmail notification', 'Override sendEmailVerificationNotification in User model', 'Test and commit changes']
    },
];

const diffLines: DiffLine[] = [
    {type: 'add', num: 1, code: '<?php'},
    {type: 'add', num: 2, code: ''},
    {type: 'add', num: 3, code: 'namespace App\\Notifications\\User\\Auth;'},
    {type: 'add', num: 4, code: ''},
    {type: 'add', num: 5, code: 'use Illuminate\\Auth\\Notifications\\VerifyEmail;'},
    {type: 'add', num: 6, code: 'use Illuminate\\Bus\\Queueable;'},
    {type: 'add', num: 7, code: 'use Illuminate\\Contracts\\Queue\\ShouldQueue;'},
    {type: 'add', num: 8, code: 'use Illuminate\\Notifications\\Messages\\MailMessage;'},
    {type: 'add', num: 9, code: 'use Illuminate\\Support\\Carbon;'},
    {type: 'add', num: 10, code: 'use Illuminate\\Support\\Facades\\Config;'},
    {type: 'add', num: 11, code: 'use Illuminate\\Support\\Facades\\URL;'},
    {type: 'add', num: 12, code: ''},
    {type: 'add', num: 13, code: 'class VerifyEmailNotification extends VerifyEmail implements ShouldQueue'},
    {type: 'add', num: 14, code: '{'},
    {type: 'add', num: 15, code: '    use Queueable;'},
    {type: 'add', num: 16, code: ''},
    {type: 'add', num: 17, code: '    public int $tries = 3;'},
    {type: 'add', num: 18, code: '    public int $backoff = 30;'},
    {type: 'add', num: 19, code: '    public int $timeout = 90;'},
    {type: 'add', num: 20, code: ''},
];

const getActionLabel = (type: string): string => {
    const labels: Record<string, string> = {read: 'Read', grep: 'Grep', glob: 'Glob'};
    return labels[type] || type;
};

export default function SessionView() {
    const [currentStatusIndex, setCurrentStatusIndex] = useState(0);
    const [isLoading, setIsLoading] = useState(true);
    const [copied, setCopied] = useState(false);
    const [replyMessage, setReplyMessage] = useState('');
    const branchName = 'claude/update-color-scheme';

    const currentLoadingStatus = useMemo(() => loadingStatuses[currentStatusIndex], [currentStatusIndex]);

    useEffect(() => {
        const interval = setInterval(() => {
            setCurrentStatusIndex((prev) => (prev + 1) % loadingStatuses.length);
        }, 1500);

        const timeout = setTimeout(() => setIsLoading(false), 3000);

        return () => {
            clearInterval(interval);
            clearTimeout(timeout);
        };
    }, []);

    const copyBranchName = () => {
        navigator.clipboard.writeText(branchName);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    return (
        <div className="flex h-full flex-col">
            {/* Top bar */}
            <header className="flex h-12 items-center justify-between border-b border-[#2b2b2b] bg-[#1b1b1b] px-4">
                <div className="flex items-center gap-2">
                    <div className="flex h-5 w-5 items-center justify-center">
                        <div
                            className="h-3 w-3 animate-spin rounded-full border-2 border-[#e07a5f] border-t-transparent"/>
                    </div>
                    <button
                        className="flex items-center gap-1.5 rounded-md px-2 py-1 transition-colors hover:bg-white/5">
            <span className="max-w-[300px] truncate text-[13px] font-medium text-[#E0E0DE]">
              Update app color scheme to match design
            </span>
                        <ChevronDown className="h-3.5 w-3.5 text-[#666666]"/>
                    </button>
                </div>
                <div className="flex items-center gap-3">
          <span
              className="rounded-md border border-[#2b2b2b] bg-[#202020] px-2.5 py-1 font-mono text-[11px] text-[#a1a1aa]">
            {branchName}
          </span>
                    <button
                        className="flex h-7 w-7 items-center justify-center rounded-md transition-colors hover:bg-white/10"
                        onClick={copyBranchName}
                        title={copied ? 'Copied!' : 'Copy branch name'}
                    >
                        {copied ? <Check className="h-4 w-4 text-[#4ade80]"/> :
                            <Copy className="h-4 w-4 text-[#666666]"/>}
                    </button>
                    <button
                        className="flex items-center gap-2 rounded-md border border-[#2b2b2b] bg-[#202020] px-3 py-1.5 transition-colors hover:bg-[#252525]">
                        <span className="text-[13px] text-[#a1a1aa]">Open in CLI</span>
                        <ExternalLink className="h-3.5 w-3.5 text-[#666666]"/>
                    </button>
                </div>
            </header>

            {/* Content */}
            <div className="flex-1 overflow-y-auto bg-[#141414]">
                <div className="mx-auto max-w-3xl px-6 py-8">
                    {/* Loading state */}
                    {isLoading ? (
                        <div className="flex items-center justify-center py-32">
                            <div className="flex items-center gap-2">
                                <Sparkles className="h-4 w-4 text-[#e07a5f] loading-pulse"/>
                                <span className="text-[14px] font-medium text-[#e07a5f] loading-shimmer">
                  {currentLoadingStatus}
                </span>
                            </div>
                        </div>
                    ) : (
                        /* Activity feed */
                        <div className="space-y-4">
                            {/* Activity items */}
                            {activity.map((item, idx) => (
                                <div key={idx} className="flex items-start gap-3">
                                    <div className="mt-1.5 h-2 w-2 flex-shrink-0 rounded-full bg-[#4ade80]"/>
                                    <div className="flex-1">
                                        {/* Todo type */}
                                        {item.type === 'todo' ? (
                                            <>
                                                <span
                                                    className="text-[13px] font-medium text-[#E0E0DE]">Update Todos</span>
                                                {item.items && (
                                                    <div className="mt-2 space-y-1.5 pl-1">
                                                        {item.items.map((todo, i) => (
                                                            <div key={i} className="flex items-center gap-2">
                                                                <Circle className="h-3 w-3 text-[#666666]"/>
                                                                <span
                                                                    className="text-[13px] text-[#a1a1aa]">{todo}</span>
                                                            </div>
                                                        ))}
                                                    </div>
                                                )}
                                            </>
                                        ) : (
                                            /* Other types */
                                            <>
                                                <div className="flex flex-wrap items-center gap-2">
                          <span className="text-[13px] font-medium text-[#E0E0DE]">
                            {getActionLabel(item.type)}
                          </span>
                                                    {item.path && (
                                                        <code
                                                            className="rounded bg-[#202020] px-1.5 py-0.5 text-[11px] text-[#a1a1aa]">
                                                            {item.path}
                                                        </code>
                                                    )}
                                                    {item.pattern && (
                                                        <code
                                                            className="rounded bg-[#202020] px-1.5 py-0.5 text-[11px] text-[#a1a1aa]">
                                                            {item.pattern}
                                                        </code>
                                                    )}
                                                </div>
                                                {item.lines && (
                                                    <div className="mt-1 pl-1">
                                                        <span
                                                            className="text-[11px] text-[#666666]">Read {item.lines} lines</span>
                                                    </div>
                                                )}
                                            </>
                                        )}
                                    </div>
                                </div>
                            ))}

                            {/* Write action with diff */}
                            <div className="flex items-start gap-3">
                                <div className="mt-1.5 h-2 w-2 flex-shrink-0 rounded-full bg-[#4ade80]"/>
                                <div className="flex-1">
                                    <p className="mb-2 text-[13px] text-[#E0E0DE]">
                                        Now I&apos;ll create a custom VerifyEmail notification that uses the{' '}
                                        <code
                                            className="rounded bg-[#202020] px-1.5 py-0.5 text-[11px] text-[#e07a5f]">emails</code>{' '}
                                        queue:
                                    </p>
                                    <div className="flex flex-wrap items-center gap-2">
                                        <span className="text-[13px] font-medium text-[#E0E0DE]">Write</span>
                                        <code className="rounded bg-[#202020] px-1.5 py-0.5 text-[11px] text-[#a1a1aa]">
                                            /home/user/.../VerifyEmailNotification.php
                                        </code>
                                    </div>

                                    {/* Code diff */}
                                    <div
                                        className="mt-3 overflow-hidden rounded-lg border border-[#2b2b2b] bg-[#1b1b1b]">
                                        <div className="overflow-x-auto">
                                            <table className="w-full font-mono text-[11px]">
                                                <tbody>
                                                {diffLines.map((line) => (
                                                    <tr key={line.num} className="bg-[#4ade80]/5">
                                                        <td className="w-10 border-r border-[#2b2b2b] px-2 py-0.5 text-right text-[#666666] select-none">
                                                            {line.num}
                                                        </td>
                                                        <td className="w-5 px-1 py-0.5 text-center text-[#4ade80] select-none">+</td>
                                                        <td className="px-2 py-0.5 whitespace-pre text-[#4ade80]">{line.code}</td>
                                                    </tr>
                                                ))}
                                                </tbody>
                                            </table>
                                        </div>
                                        <div className="border-t border-[#2b2b2b] px-3 py-2">
                                            <button
                                                className="text-[11px] text-[#666666] transition-colors hover:text-[#888888] hover:underline">
                                                Show full diff (110 more lines)
                                            </button>
                                        </div>
                                    </div>

                                    <div className="mt-3 flex justify-end">
                                        <button
                                            className="flex items-center gap-2 rounded-lg bg-[#e07a5f] px-4 py-2 text-[13px] font-medium text-[#141414] transition-colors hover:bg-[#d66b50]">
                                            View PR
                                            <ExternalLink className="h-3.5 w-3.5"/>
                                        </button>
                                    </div>
                                </div>
                            </div>

                            {/* Final todo */}
                            <div className="flex items-start gap-3">
                                <div className="mt-1.5 h-2 w-2 flex-shrink-0 rounded-full bg-[#4ade80]"/>
                                <span className="text-[13px] font-medium text-[#E0E0DE]">Update Todos</span>
                            </div>
                        </div>
                    )}
                </div>
            </div>

            {/* Reply composer */}
            <div className="border-t border-[#2b2b2b] bg-[#1b1b1b] p-4">
                <div className="mx-auto max-w-3xl">
                    <div
                        className="relative rounded-xl border border-[#2b2b2b] bg-[#202020] transition-colors focus-within:border-[#3a3a3a]">
                        <input
                            type="text"
                            value={replyMessage}
                            onChange={(e) => setReplyMessage(e.target.value)}
                            placeholder="Reply..."
                            className="w-full bg-transparent px-4 py-3.5 pr-20 text-[13px] text-[#E0E0DE] outline-none placeholder:text-[#666666]"
                        />
                        <div className="absolute bottom-2.5 left-2.5">
                            <button
                                className="flex h-8 w-8 items-center justify-center rounded-lg text-[#666666] transition-colors hover:bg-white/5 hover:text-[#888888]">
                                <Image className="h-[18px] w-[18px]"/>
                            </button>
                        </div>
                        <div className="absolute right-2.5 bottom-2.5">
                            <button
                                className={`flex h-8 w-8 items-center justify-center rounded-full transition-all ${
                                    replyMessage.trim() ? 'bg-[#e07a5f] text-[#141414]' : 'bg-[#3a3a3a] text-[#666666]'
                                }`}
                            >
                                <Send className="h-4 w-4"/>
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}