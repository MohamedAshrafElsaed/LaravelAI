'use client';

import {Bug, Code, Database, FileText, GitBranch, Shield, Sparkles, Zap} from 'lucide-react';

interface Repo {
    name: string;
    owner: string;
    selected: boolean;
}

interface WelcomeScreenProps {
    selectedRepo?: Repo;
    onSuggestionClick: (suggestion: string) => void;
}

const SUGGESTIONS = [
    {
        icon: Code,
        title: 'Add new API endpoint',
        description: 'Create a REST API endpoint with validation',
        prompt: 'Create a new API endpoint for user profile management with proper validation and error handling',
        color: '#4ade80',
    },
    {
        icon: Zap,
        title: 'Implement a feature',
        description: 'Build a complete feature with all layers',
        prompt: 'Implement a feature for sending email notifications with queue support',
        color: '#fbbf24',
    },
    {
        icon: Shield,
        title: 'Add authentication',
        description: 'Implement auth middleware and guards',
        prompt: 'Add JWT authentication middleware with role-based access control',
        color: '#60a5fa',
    },
    {
        icon: Database,
        title: 'Create model & migration',
        description: 'Generate Eloquent model with migration',
        prompt: 'Create a new Product model with migration, including relationships to Category and User',
        color: '#a78bfa',
    },
    {
        icon: Bug,
        title: 'Debug an issue',
        description: 'Analyze and fix code problems',
        prompt: 'Help me debug and fix issues in my application controllers',
        color: '#f87171',
    },
    {
        icon: FileText,
        title: 'Write tests',
        description: 'Generate unit and feature tests',
        prompt: 'Write comprehensive tests for the authentication system including unit and feature tests',
        color: '#2dd4bf',
    },
];

// Animated robot mascot SVG
function RobotMascot() {
    return (
        <div className="relative">
            {/* Glow effect */}
            <div
                className="absolute inset-0 blur-3xl opacity-30 bg-gradient-to-r from-[#e07a5f] to-[#9333EA] rounded-full"/>

            <svg
                width="140"
                height="140"
                viewBox="0 0 140 140"
                className="relative animate-float"
            >
                {/* Outer ring with gradient */}
                <defs>
                    <linearGradient id="ringGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                        <stop offset="0%" stopColor="#e07a5f"/>
                        <stop offset="100%" stopColor="#9333EA"/>
                    </linearGradient>
                    <linearGradient id="bodyGradient" x1="0%" y1="0%" x2="0%" y2="100%">
                        <stop offset="0%" stopColor="#2b2b2b"/>
                        <stop offset="100%" stopColor="#1b1b1b"/>
                    </linearGradient>
                </defs>

                {/* Background circle */}
                <circle cx="70" cy="70" r="60" fill="url(#bodyGradient)"/>

                {/* Ring */}
                <circle
                    cx="70"
                    cy="70"
                    r="60"
                    fill="none"
                    stroke="url(#ringGradient)"
                    strokeWidth="2"
                />

                {/* Eyes */}
                <circle cx="50" cy="60" r="10" fill="#e07a5f">
                    <animate
                        attributeName="r"
                        values="10;8;10"
                        dur="3s"
                        repeatCount="indefinite"
                    />
                </circle>
                <circle cx="90" cy="60" r="10" fill="#e07a5f">
                    <animate
                        attributeName="r"
                        values="10;8;10"
                        dur="3s"
                        repeatCount="indefinite"
                    />
                </circle>

                {/* Eye highlights */}
                <circle cx="53" cy="57" r="3" fill="#fff" opacity="0.8"/>
                <circle cx="93" cy="57" r="3" fill="#fff" opacity="0.8"/>

                {/* Smile */}
                <path
                    d="M 45 85 Q 70 100 95 85"
                    stroke="#e07a5f"
                    strokeWidth="3"
                    fill="none"
                    strokeLinecap="round"
                />

                {/* Antenna */}
                <rect x="65" y="5" width="10" height="18" fill="#e07a5f" rx="3"/>
                <circle cx="70" cy="5" r="6" fill="#e07a5f">
                    <animate
                        attributeName="opacity"
                        values="1;0.5;1"
                        dur="2s"
                        repeatCount="indefinite"
                    />
                </circle>

                {/* Decorative dots */}
                <circle cx="30" cy="70" r="3" fill="#666666"/>
                <circle cx="110" cy="70" r="3" fill="#666666"/>
            </svg>
        </div>
    );
}

export default function WelcomeScreen({selectedRepo, onSuggestionClick}: WelcomeScreenProps) {
    return (
        <div className="flex flex-col items-center justify-center h-full p-8 bg-[#141414]">
            {/* Robot Mascot */}
            <div className="mb-8">
                <RobotMascot/>
            </div>

            {/* Title */}
            <h1 className="text-2xl font-bold text-[#E0E0DE] mb-2">
                Welcome to Maestro AI
            </h1>
            <p className="text-[#a1a1aa] mb-8 text-center max-w-md">
                Your AI-powered Laravel code assistant. Select a repository and start building amazing things.
            </p>

            {selectedRepo ? (
                <>
                    {/* Current repo indicator */}
                    <div
                        className="flex items-center gap-2 mb-6 px-3 py-2 rounded-lg bg-[#202020] border border-[#2b2b2b]">
                        <GitBranch className="h-4 w-4 text-[#e07a5f]"/>
                        <span className="text-sm text-[#a1a1aa]">Working with:</span>
                        <span className="text-sm font-medium text-[#e07a5f]">
              {selectedRepo.owner}/{selectedRepo.name}
            </span>
                    </div>

                    {/* Suggestion Cards */}
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 w-full max-w-4xl">
                        {SUGGESTIONS.map((suggestion, index) => (
                            <button
                                key={index}
                                onClick={() => onSuggestionClick(suggestion.prompt)}
                                className="group p-4 bg-[#1b1b1b] border border-[#2b2b2b] rounded-xl text-left hover:border-[#3a3a3a] hover:bg-[#202020] transition-all duration-200"
                            >
                                <div className="flex items-start gap-3">
                                    <div
                                        className="p-2 rounded-lg transition-colors"
                                        style={{backgroundColor: `${suggestion.color}15`}}
                                    >
                                        <suggestion.icon
                                            className="h-5 w-5 transition-transform group-hover:scale-110"
                                            style={{color: suggestion.color}}
                                        />
                                    </div>
                                    <div className="flex-1 min-w-0">
                                        <h3 className="font-medium text-[#E0E0DE] group-hover:text-white transition-colors">
                                            {suggestion.title}
                                        </h3>
                                        <p className="text-sm text-[#666666] group-hover:text-[#a1a1aa] transition-colors mt-0.5">
                                            {suggestion.description}
                                        </p>
                                    </div>
                                </div>
                            </button>
                        ))}
                    </div>

                    {/* Keyboard hint */}
                    <p className="mt-6 text-xs text-[#666666]">
                        Or type a message in the chat to get started
                    </p>
                </>
            ) : (
                // No repo selected state
                <div className="text-center">
                    <div
                        className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-[#202020] border border-[#2b2b2b] mb-4">
                        <Sparkles className="h-4 w-4 text-[#a1a1aa]"/>
                        <span className="text-sm text-[#a1a1aa]">No repository selected</span>
                    </div>
                    <p className="text-sm text-[#666666]">
                        Select a repository from the sidebar to start coding with AI
                    </p>
                </div>
            )}

            {/* CSS for float animation */}
            <style jsx>{`
                @keyframes float {
                    0%, 100% {
                        transform: translateY(0px);
                    }
                    50% {
                        transform: translateY(-10px);
                    }
                }

                .animate-float {
                    animation: float 3s ease-in-out infinite;
                }
            `}</style>
        </div>
    );
}