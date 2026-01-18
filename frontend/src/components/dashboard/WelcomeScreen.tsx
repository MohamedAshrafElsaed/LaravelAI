'use client';

import {ChevronDown} from 'lucide-react';
import type {Repo} from '@/app/dashboard/page';

interface WelcomeScreenProps {
    selectedRepo: Repo | undefined;
    onSuggestionClick: (suggestion: string) => void;
}

const suggestions = [
    {
        id: 'review',
        title: 'Review recent changes',
        description: 'Look at the recent git commits and summarize the key changes, highlighting anything that might need attention or follow-up',
        badge: {type: 'code' as const, text: 'git log', subtext: '3 commits'},
    },
    {
        id: 'error',
        title: 'Add error handling',
        description: 'Find functions that could benefit from better error handling and add appropriate error handling with clear error messages',
        badge: null,
    },
    {
        id: 'feature',
        title: 'Implement a small feature',
        description: 'Look for feature requests in comments, simple enhancements, or obvious missing functionality and implement one',
        badge: {type: 'text' as const, text: '+ Feature', subtext: 'ready to ship 🚀'},
    },
];

export default function WelcomeScreen({selectedRepo, onSuggestionClick}: WelcomeScreenProps) {
    return (
        <div className="flex min-h-full flex-col items-center justify-center px-6 py-12">
            {/* Mascot */}
            <div className="mb-8">
                <svg width="80" height="56" viewBox="0 0 80 56" fill="none" xmlns="http://www.w3.org/2000/svg">
                    {/* Body */}
                    <rect x="16" y="8" width="48" height="40" rx="4" fill="#e07a5f"/>
                    {/* Eyes */}
                    <rect x="28" y="20" width="8" height="8" rx="1" fill="#141414"/>
                    <rect x="44" y="20" width="8" height="8" rx="1" fill="#141414"/>
                    {/* Feet */}
                    <rect x="24" y="48" width="12" height="8" rx="2" fill="#e07a5f"/>
                    <rect x="44" y="48" width="12" height="8" rx="2" fill="#e07a5f"/>
                    {/* Antenna left */}
                    <rect x="24" y="0" width="4" height="12" rx="2" fill="#e07a5f"/>
                    <circle cx="26" cy="0" r="3" fill="#e07a5f"/>
                    {/* Antenna right */}
                    <rect x="52" y="0" width="4" height="12" rx="2" fill="#e07a5f"/>
                    <circle cx="54" cy="0" r="3" fill="#e07a5f"/>
                </svg>
            </div>

            {/* Repo selector row */}
            <div className="mb-8 flex items-center gap-3">
                <button
                    className="flex items-center gap-2 rounded-lg border border-[#2b2b2b] bg-[#1b1b1b] px-4 py-2.5 transition-colors hover:border-[#3a3a3a]">
          <span className="text-[13px] text-[#a1a1aa]">
            {selectedRepo ? `${selectedRepo.owner}/${selectedRepo.name}` : 'Select repository'}
          </span>
                    <ChevronDown className="h-4 w-4 text-[#666666]"/>
                </button>

                <button
                    className="flex items-center gap-2 rounded-lg border border-[#2b2b2b] bg-[#1b1b1b] px-4 py-2.5 transition-colors hover:border-[#3a3a3a]">
                    <span className="text-[13px] text-[#a1a1aa]">Default</span>
                    <ChevronDown className="h-4 w-4 text-[#666666]"/>
                </button>
            </div>

            {/* Suggestion cards */}
            <div className="w-full max-w-[480px] space-y-3">
                {suggestions.map((suggestion) => (
                    <button
                        key={suggestion.id}
                        className="group flex w-full items-start justify-between rounded-xl border border-[#2b2b2b] bg-[#1b1b1b] p-4 text-left transition-all hover:border-[#3a3a3a] hover:bg-[#1f1f1f]"
                        onClick={() => onSuggestionClick(suggestion.id)}
                    >
                        <div className="flex-1 pr-4">
                            <h3 className="mb-1.5 text-[14px] font-medium text-[#E0E0DE]">{suggestion.title}</h3>
                            <p className="text-[13px] leading-relaxed text-[#808080]">{suggestion.description}</p>
                        </div>
                        {suggestion.badge && (
                            <div className="flex flex-shrink-0 flex-col items-end">
                                {suggestion.badge.type === 'code' ? (
                                    <>
                                        <code className="rounded bg-[#252525] px-2 py-1 text-[11px] text-[#e07a5f]">
                                            {suggestion.badge.text}
                                        </code>
                                        <span
                                            className="mt-1 text-[11px] text-[#666666]">{suggestion.badge.subtext}</span>
                                    </>
                                ) : (
                                    <>
                                        <span className="text-[11px] text-[#666666]">{suggestion.badge.text}</span>
                                        <span
                                            className="mt-0.5 text-[11px] text-[#666666]">{suggestion.badge.subtext}</span>
                                    </>
                                )}
                            </div>
                        )}
                    </button>
                ))}
            </div>
        </div>
    );
}