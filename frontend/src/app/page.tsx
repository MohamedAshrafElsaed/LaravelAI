'use client';

import {useCallback, useEffect, useState} from 'react';
import Link from 'next/link';
import {useAuthStore} from '@/lib/store';
import {
    ArrowRight,
    CheckCircle,
    ClipboardList,
    Code2,
    Database,
    FileCode,
    GitBranch,
    Layers,
    Play,
    Search,
    ShieldCheck,
    Sparkles,
    Users,
    Zap
} from 'lucide-react';

// Agent data with their roles and colors
const agents = [
    {
        name: 'Nova',
        role: 'Intent Analyzer',
        color: '#9333EA',
        emoji: '🟣',
        icon: Sparkles,
        desc: 'Understands what you want to build'
    },
    {
        name: 'Scout',
        role: 'Context Retriever',
        color: '#3B82F6',
        emoji: '🔵',
        icon: Search,
        desc: 'Finds relevant code in your codebase'
    },
    {
        name: 'Blueprint',
        role: 'Planner',
        color: '#F97316',
        emoji: '🟠',
        icon: ClipboardList,
        desc: 'Creates step-by-step execution plans'
    },
    {name: 'Forge', role: 'Executor', color: '#22C55E', emoji: '🟢', icon: Code2, desc: 'Writes production-ready code'},
    {
        name: 'Guardian',
        role: 'Validator',
        color: '#EF4444',
        emoji: '🔴',
        icon: ShieldCheck,
        desc: 'Ensures code quality & security'
    },
    {
        name: 'Conductor',
        role: 'Orchestrator',
        color: '#FFFFFF',
        emoji: '⚪',
        icon: Users,
        desc: 'Coordinates the entire workflow'
    },
];

const features = [
    {
        icon: Database,
        title: 'Smart Codebase Indexing',
        desc: 'Vector embeddings powered by Qdrant for semantic code search across your entire Laravel project'
    },
    {
        icon: Layers,
        title: 'Dependency-Aware Planning',
        desc: 'Automatically orders migrations → models → services → controllers → routes'
    },
    {
        icon: ShieldCheck,
        title: 'Laravel Convention Validation',
        desc: 'PSR-12, type hints, docblocks, security checks, and best practices enforcement'
    },
    {
        icon: Zap,
        title: 'Real-time Streaming',
        desc: 'Watch agents think and work in real-time with SSE-powered live updates'
    },
    {
        icon: GitBranch,
        title: 'Full CRUD Generation',
        desc: 'Controllers, Form Requests, API Resources, migrations, and routes in one request'
    },
    {
        icon: FileCode,
        title: 'Context-Aware Modifications',
        desc: 'Understands your existing code patterns and follows your conventions'
    },
];

const laravelFeatures = [
    'Eloquent Models & Relationships',
    'Database Migrations',
    'Controllers & Routes',
    'Form Request Validation',
    'API Resources',
    'Service Classes',
    'Middleware',
    'Queue Jobs',
    'Events & Listeners',
    'Blade Templates',
];

interface Particle {
    id: number;
    x: number;
    y: number;
    size: number;
    duration: number;
    delay: number;
}

export default function LandingPage() {
    const [isLoaded, setIsLoaded] = useState(false);
    const [mousePos, setMousePos] = useState({x: 0, y: 0});
    const [particles, setParticles] = useState<Particle[]>([]);
    const [activeAgent, setActiveAgent] = useState(0);

    // Auth state
    const {isAuthenticated, user, isHydrated, logout} = useAuthStore();
    const [mounted, setMounted] = useState(false);

    // API URL for GitHub OAuth
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

    useEffect(() => {
        setMounted(true);
        setParticles(
            Array.from({length: 50}, (_, i) => ({
                id: i,
                x: Math.random() * 100,
                y: Math.random() * 100,
                size: Math.random() * 4 + 1,
                duration: Math.random() * 20 + 10,
                delay: Math.random() * 5,
            }))
        );
        setTimeout(() => setIsLoaded(true), 100);

        // Auto-rotate agents
        const interval = setInterval(() => {
            setActiveAgent((prev) => (prev + 1) % agents.length);
        }, 3000);
        return () => clearInterval(interval);
    }, []);

    const handleMouseMove = useCallback((e: React.MouseEvent) => {
        setMousePos({
            x: (e.clientX / window.innerWidth) * 100,
            y: (e.clientY / window.innerHeight) * 100,
        });
    }, []);

    // Check if user is authenticated (only after hydration to avoid mismatch)
    const showAuthenticatedUI = mounted && isHydrated && isAuthenticated;

    return (
        <div className="min-h-screen bg-[#1C1917] text-[#FAFAF9] overflow-hidden" onMouseMove={handleMouseMove}>
            {/* Animated Background */}
            <div className="fixed inset-0 pointer-events-none">
                <div
                    className="absolute w-[800px] h-[800px] rounded-full opacity-20 blur-3xl transition-all duration-1000 ease-out"
                    style={{
                        background: 'radial-gradient(circle, rgba(224, 120, 80, 0.4) 0%, transparent 70%)',
                        left: `${mousePos.x * 0.3 - 20}%`,
                        top: `${mousePos.y * 0.3 - 20}%`,
                    }}
                />
                <div
                    className="absolute w-[600px] h-[600px] rounded-full opacity-15 blur-3xl transition-all duration-[1500ms] ease-out"
                    style={{
                        background: 'radial-gradient(circle, rgba(255, 45, 32, 0.3) 0%, transparent 70%)',
                        right: `${(100 - mousePos.x) * 0.2 - 10}%`,
                        bottom: `${(100 - mousePos.y) * 0.2 - 10}%`,
                    }}
                />
                {particles.map((p) => (
                    <div
                        key={p.id}
                        className="absolute rounded-full bg-[#E07850]/20"
                        style={{
                            left: `${p.x}%`,
                            top: `${p.y}%`,
                            width: `${p.size}px`,
                            height: `${p.size}px`,
                            animation: `float ${p.duration}s ease-in-out infinite`,
                            animationDelay: `${p.delay}s`,
                        }}
                    />
                ))}
                <div
                    className="absolute inset-0 bg-[linear-gradient(rgba(68,64,60,0.1)_1px,transparent_1px),linear-gradient(90deg,rgba(68,64,60,0.1)_1px,transparent_1px)] bg-[size:64px_64px]"/>
            </div>

            {/* Header */}
            <header className="fixed top-0 left-0 right-0 z-50">
                <div className="mx-4 mt-4">
                    <div
                        className="max-w-7xl mx-auto px-6 py-4 bg-[#292524]/80 backdrop-blur-xl rounded-2xl border border-[#44403C]/50 shadow-lg shadow-black/20">
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-3">
                                <div className="relative">
                                    <div
                                        className="w-10 h-10 bg-gradient-to-br from-[#E07850] to-[#C65D3D] rounded-xl flex items-center justify-center shadow-lg shadow-[#E07850]/30">
                                        <svg className="w-6 h-6 text-white" viewBox="0 0 24 24" fill="none"
                                             stroke="currentColor" strokeWidth="2">
                                            <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
                                        </svg>
                                    </div>
                                    <div
                                        className="absolute -top-1 -right-1 w-3 h-3 bg-[#22C55E] rounded-full border-2 border-[#292524] animate-pulse"/>
                                </div>
                                <div>
                                    <span
                                        className="text-xl font-bold bg-gradient-to-r from-[#FAFAF9] to-[#A8A29E] bg-clip-text text-transparent">Maestro</span>
                                    <span className="text-xl font-light text-[#E07850] ml-1">AI</span>
                                </div>
                            </div>

                            <nav className="hidden md:flex items-center gap-1">
                                <a href="#agents"
                                   className="px-4 py-2 text-sm font-medium text-[#A8A29E] hover:text-[#FAFAF9] hover:bg-[#44403C] rounded-lg transition-all">Agents</a>
                                <a href="#features"
                                   className="px-4 py-2 text-sm font-medium text-[#A8A29E] hover:text-[#FAFAF9] hover:bg-[#44403C] rounded-lg transition-all">Features</a>
                                <a href="#how-it-works"
                                   className="px-4 py-2 text-sm font-medium text-[#A8A29E] hover:text-[#FAFAF9] hover:bg-[#44403C] rounded-lg transition-all">How
                                    it Works</a>
                                <a href="https://laravel.com/docs" target="_blank" rel="noreferrer"
                                   className="px-4 py-2 text-sm font-medium text-[#A8A29E] hover:text-[#FAFAF9] hover:bg-[#44403C] rounded-lg transition-all">Laravel
                                    Docs</a>
                            </nav>

                            <div className="flex items-center gap-3">
                                {showAuthenticatedUI ? (
                                    <>
                                        {/* User avatar and info */}
                                        <div className="flex items-center gap-2">
                                            {user?.avatar_url ? (
                                                <img
                                                    src={user.avatar_url}
                                                    alt={user.username}
                                                    className="w-8 h-8 rounded-full border-2 border-[#44403C]"
                                                />
                                            ) : (
                                                <div
                                                    className="w-8 h-8 rounded-full bg-gradient-to-br from-[#E07850] to-[#C65D3D] flex items-center justify-center text-xs font-bold text-white">
                                                    {user?.username?.charAt(0).toUpperCase()}
                                                </div>
                                            )}
                                            <span
                                                className="hidden sm:block text-sm text-[#A8A29E]">{user?.username}</span>
                                        </div>
                                        <Link
                                            href="/dashboard"
                                            className="group relative px-5 py-2.5 text-sm font-semibold text-white bg-gradient-to-r from-[#E07850] to-[#C65D3D] rounded-xl overflow-hidden hover:shadow-lg hover:shadow-[#E07850]/30 hover:-translate-y-0.5 transition-all duration-300"
                                        >
                                            <span className="relative z-10">Dashboard</span>
                                            <div
                                                className="absolute inset-0 bg-gradient-to-r from-[#C65D3D] to-[#A64D36] opacity-0 group-hover:opacity-100 transition-opacity"/>
                                        </Link>
                                    </>
                                ) : (
                                    <>
                                        <a
                                            href={`${apiUrl}/auth/github`}
                                            className="px-4 py-2 text-sm font-medium text-[#A8A29E] hover:text-[#FAFAF9] transition-colors"
                                        >
                                            Sign in
                                        </a>
                                        <a
                                            href={`${apiUrl}/auth/github`}
                                            className="group relative px-5 py-2.5 text-sm font-semibold text-white bg-gradient-to-r from-[#E07850] to-[#C65D3D] rounded-xl overflow-hidden hover:shadow-lg hover:shadow-[#E07850]/30 hover:-translate-y-0.5 transition-all duration-300"
                                        >
                                            <span className="relative z-10">Start Building</span>
                                            <div
                                                className="absolute inset-0 bg-gradient-to-r from-[#C65D3D] to-[#A64D36] opacity-0 group-hover:opacity-100 transition-opacity"/>
                                        </a>
                                    </>
                                )}
                            </div>
                        </div>
                    </div>
                </div>
            </header>

            {/* Hero Section */}
            <section className="relative pt-40 pb-20">
                <div className="relative max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
                    <div
                        className={`flex justify-center mb-8 transition-all duration-700 ${isLoaded ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'}`}>
                        <div
                            className="inline-flex items-center gap-3 px-5 py-2.5 bg-[#292524] rounded-full border border-[#44403C] shadow-lg shadow-black/20">
                            <div className="flex items-center gap-1">
                                {/* Laravel Logo */}
                                <svg className="w-5 h-5" viewBox="0 0 50 52" fill="none">
                                    <path
                                        d="M49.626 11.564a.809.809 0 0 1 .028.209v10.972a.8.8 0 0 1-.402.694l-9.209 5.302V39.25c0 .286-.152.55-.4.694L20.42 51.01c-.044.025-.092.041-.14.058-.018.006-.035.017-.054.022a.805.805 0 0 1-.41 0c-.022-.006-.042-.018-.063-.026-.044-.016-.09-.03-.132-.054L.402 39.944A.801.801 0 0 1 0 39.25V6.334c0-.072.01-.142.028-.21.006-.023.02-.044.028-.067.015-.042.029-.085.051-.124.015-.026.037-.047.055-.071.023-.032.044-.065.071-.093.023-.023.053-.04.079-.06.029-.024.055-.05.088-.069h.001l9.61-5.533a.802.802 0 0 1 .8 0l9.61 5.533h.002c.032.02.059.045.088.068.026.02.055.038.078.06.028.029.048.062.072.094.017.024.04.045.054.071.023.04.036.082.052.124.008.023.022.044.028.068a.809.809 0 0 1 .028.209v20.559l8.008-4.611v-10.51c0-.07.01-.141.028-.208.007-.024.02-.045.028-.068.016-.042.03-.085.052-.124.015-.026.037-.047.054-.071.024-.032.044-.065.072-.093.023-.023.052-.04.078-.06.03-.024.056-.05.088-.069h.001l9.611-5.533a.801.801 0 0 1 .8 0l9.61 5.533c.034.02.06.045.09.068.025.02.054.038.077.06.028.029.048.062.072.094.018.024.04.045.054.071.023.039.036.082.052.124.009.023.022.044.028.068z"
                                        fill="#FF2D20"/>
                                </svg>
                            </div>
                            <span className="text-sm font-medium text-[#A8A29E]">Built exclusively for Laravel</span>
                            <span
                                className="px-2.5 py-1 text-xs font-bold text-[#E07850] bg-[#E07850]/10 rounded-full">Multi-Agent</span>
                        </div>
                    </div>

                    <div className="text-center mb-8">
                        <h1 className={`text-5xl sm:text-6xl lg:text-7xl font-black tracking-tight mb-6 transition-all duration-700 delay-100 ${isLoaded ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'}`}>
                            <span className="block text-[#FAFAF9]">Your Laravel Codebase</span>
                            <span className="block mt-2">
                <span className="relative">
                  <span
                      className="bg-gradient-to-r from-[#FF2D20] via-[#E07850] to-[#FF2D20] bg-clip-text text-transparent">6 AI Agents Strong</span>
                  <svg className="absolute -bottom-2 left-0 w-full h-3 text-[#FF2D20]/30" viewBox="0 0 200 12"
                       preserveAspectRatio="none">
                    <path d="M0,8 Q50,0 100,8 T200,8" fill="none" stroke="currentColor" strokeWidth="3"/>
                  </svg>
                </span>
              </span>
                        </h1>

                        <p className={`text-lg sm:text-xl text-[#A8A29E] max-w-3xl mx-auto leading-relaxed transition-all duration-700 delay-200 ${isLoaded ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'}`}>
                            A <span className="font-semibold text-[#FAFAF9]">multi-agent AI system</span> that
                            understands your Laravel codebase,
                            plans changes with proper dependency ordering, and generates
                            <span className="text-[#FF2D20] font-semibold"> production-ready code</span> following
                            Laravel conventions.
                        </p>
                    </div>

                    <div
                        className={`flex flex-col sm:flex-row items-center justify-center gap-4 mb-16 transition-all duration-700 delay-300 ${isLoaded ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'}`}>
                        {showAuthenticatedUI ? (
                            <Link
                                href="/dashboard"
                                className="group relative px-8 py-4 text-base font-semibold text-white bg-gradient-to-r from-[#E07850] to-[#C65D3D] rounded-2xl overflow-hidden shadow-xl shadow-[#E07850]/30 hover:shadow-2xl hover:shadow-[#E07850]/40 hover:-translate-y-1 transition-all duration-300"
                            >
                <span className="relative z-10 flex items-center gap-2">
                  Go to Dashboard
                  <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform"/>
                </span>
                                <div
                                    className="absolute inset-0 bg-gradient-to-r from-[#C65D3D] to-[#A64D36] opacity-0 group-hover:opacity-100 transition-opacity"/>
                            </Link>
                        ) : (
                            <a
                                href={`${apiUrl}/auth/github`}
                                className="group relative px-8 py-4 text-base font-semibold text-white bg-gradient-to-r from-[#E07850] to-[#C65D3D] rounded-2xl overflow-hidden shadow-xl shadow-[#E07850]/30 hover:shadow-2xl hover:shadow-[#E07850]/40 hover:-translate-y-1 transition-all duration-300"
                            >
                <span className="relative z-10 flex items-center gap-2">
                  Connect Your Project
                  <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform"/>
                </span>
                                <div
                                    className="absolute inset-0 bg-gradient-to-r from-[#C65D3D] to-[#A64D36] opacity-0 group-hover:opacity-100 transition-opacity"/>
                            </a>
                        )}
                        <button
                            className="px-8 py-4 text-base font-semibold text-[#FAFAF9] bg-[#292524] border-2 border-[#44403C] rounded-2xl hover:border-[#57534E] hover:shadow-lg hover:shadow-black/20 hover:-translate-y-1 transition-all duration-300 flex items-center gap-2">
                            <Play className="w-5 h-5 text-[#E07850]" fill="currentColor"/>
                            Watch Demo
                        </button>
                    </div>

                    {/* Terminal Preview */}
                    <div
                        className={`relative max-w-4xl mx-auto transition-all duration-1000 delay-400 ${isLoaded ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'}`}>
                        <div
                            className="absolute -inset-4 bg-gradient-to-r from-[#E07850]/20 to-[#FF2D20]/20 rounded-3xl opacity-50 blur-2xl"/>
                        <div
                            className="relative bg-[#1C1917] rounded-2xl shadow-2xl border border-[#44403C] overflow-hidden">
                            <div className="flex items-center gap-2 px-4 py-3 bg-[#292524] border-b border-[#44403C]">
                                <div className="flex gap-2">
                                    <div className="w-3 h-3 rounded-full bg-[#EF4444]"/>
                                    <div className="w-3 h-3 rounded-full bg-[#F59E0B]"/>
                                    <div className="w-3 h-3 rounded-full bg-[#22C55E]"/>
                                </div>
                                <span
                                    className="ml-4 text-sm text-[#78716C] font-mono">maestro-ai — Laravel Project</span>
                            </div>
                            <div className="p-6 font-mono text-sm">
                                <div className="flex items-center gap-2 text-[#78716C] mb-4">
                                    <span className="text-[#22C55E]">$</span>
                                    <span
                                        className="text-[#FAFAF9]">Add a product reviews feature with 1-5 star ratings</span>
                                </div>
                                <div className="space-y-2 text-[#A8A29E]">
                                    <p><span className="text-[#9333EA]">🟣 Nova:</span> Analyzing intent... feature
                                        request, affects models, controllers, routes</p>
                                    <p><span className="text-[#3B82F6]">🔵 Scout:</span> Found Product.php, User.php,
                                        api.php routes...</p>
                                    <p><span className="text-[#F97316]">🟠 Blueprint:</span> Planning 8 steps: migration
                                        → model → request → resource → controller → routes</p>
                                    <p><span className="text-[#22C55E]">🟢 Forge:</span> Creating reviews table migration
                                        with indexes...</p>
                                    <p><span className="text-[#22C55E]">🟢 Forge:</span> Creating Review model with
                                        relationships...</p>
                                    <p><span className="text-[#EF4444]">🔴 Guardian:</span> Validating... Score: 96/100 ✓
                                    </p>
                                    <p className="text-[#22C55E] font-semibold mt-4">✔ Complete! 8 files
                                        created/modified. Ready to commit.</p>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </section>

            {/* Agents Section */}
            <section id="agents" className="py-24 relative">
                <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
                    <div className="text-center mb-16">
                        <h2 className="text-sm font-bold uppercase tracking-widest text-[#E07850] mb-4">Meet The
                            Team</h2>
                        <p className="text-3xl sm:text-4xl lg:text-5xl font-bold text-[#FAFAF9] mb-4">
                            6 Specialized AI Agents
                        </p>
                        <p className="text-lg text-[#A8A29E] max-w-2xl mx-auto">
                            Each agent has a distinct role in the pipeline, working together to understand, plan,
                            execute, and validate your Laravel code changes.
                        </p>
                    </div>

                    <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
                        {agents.map((agent, index) => (
                            <div
                                key={agent.name}
                                className={`group relative p-6 bg-[#292524] rounded-2xl border transition-all duration-500 cursor-pointer ${
                                    activeAgent === index
                                        ? 'border-[#E07850] shadow-xl shadow-[#E07850]/10'
                                        : 'border-[#44403C] hover:border-[#57534E]'
                                }`}
                                onClick={() => setActiveAgent(index)}
                            >
                                <div className="flex items-start gap-4">
                                    <div
                                        className="w-12 h-12 rounded-xl flex items-center justify-center text-2xl"
                                        style={{backgroundColor: `${agent.color}20`}}
                                    >
                                        {agent.emoji}
                                    </div>
                                    <div className="flex-1">
                                        <div className="flex items-center gap-2 mb-1">
                                            <h3 className="text-lg font-bold text-[#FAFAF9]">{agent.name}</h3>
                                            {activeAgent === index && (
                                                <span className="w-2 h-2 rounded-full bg-[#22C55E] animate-pulse"/>
                                            )}
                                        </div>
                                        <p className="text-sm font-medium mb-2"
                                           style={{color: agent.color}}>{agent.role}</p>
                                        <p className="text-sm text-[#A8A29E]">{agent.desc}</p>
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            </section>

            {/* Laravel Features Grid */}
            <section className="py-24 relative">
                <div className="absolute inset-0 bg-gradient-to-b from-transparent via-[#292524]/30 to-transparent"/>
                <div className="relative max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
                    <div className="text-center mb-12">
                        <h2 className="text-sm font-bold uppercase tracking-widest text-[#FF2D20] mb-4">Laravel
                            Expertise</h2>
                        <p className="text-3xl sm:text-4xl font-bold text-[#FAFAF9]">
                            Everything Laravel, Automated
                        </p>
                    </div>

                    <div className="flex flex-wrap justify-center gap-3">
                        {laravelFeatures.map((feature) => (
                            <div
                                key={feature}
                                className="flex items-center gap-2 px-4 py-2.5 bg-[#292524] rounded-xl border border-[#44403C] hover:border-[#FF2D20]/50 hover:shadow-lg hover:shadow-[#FF2D20]/10 transition-all duration-300"
                            >
                                <CheckCircle className="w-4 h-4 text-[#22C55E]"/>
                                <span className="text-sm font-medium text-[#FAFAF9]">{feature}</span>
                            </div>
                        ))}
                    </div>
                </div>
            </section>

            {/* Features Section */}
            <section id="features" className="py-24 relative">
                <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
                    <div className="text-center mb-16">
                        <h2 className="text-sm font-bold uppercase tracking-widest text-[#E07850] mb-4">Powerful
                            Features</h2>
                        <p className="text-3xl sm:text-4xl lg:text-5xl font-bold text-[#FAFAF9] mb-4">
                            Built for <span className="text-[#FF2D20]">Laravel</span> Developers
                        </p>
                        <p className="text-lg text-[#A8A29E] max-w-2xl mx-auto">
                            Not a generic AI code assistant. Every feature is designed specifically for Laravel
                            development workflows.
                        </p>
                    </div>

                    <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
                        {features.map((feature) => (
                            <div key={feature.title}
                                 className="group relative p-8 bg-[#292524] rounded-2xl border border-[#44403C] hover:border-[#57534E] hover:shadow-2xl hover:shadow-[#E07850]/5 transition-all duration-500">
                                <div
                                    className="absolute inset-0 bg-gradient-to-br from-[#E07850]/5 via-transparent to-transparent rounded-2xl opacity-0 group-hover:opacity-100 transition-opacity duration-500"/>
                                <div className="relative">
                                    <div
                                        className="w-14 h-14 bg-gradient-to-br from-[#E07850]/20 to-[#C65D3D]/20 rounded-2xl flex items-center justify-center mb-5 group-hover:scale-110 group-hover:shadow-lg group-hover:shadow-[#E07850]/20 transition-all duration-300">
                                        <feature.icon className="w-7 h-7 text-[#E07850]"/>
                                    </div>
                                    <h3 className="text-xl font-bold text-[#FAFAF9] mb-3 group-hover:text-[#E07850] transition-colors">{feature.title}</h3>
                                    <p className="text-[#A8A29E] leading-relaxed">{feature.desc}</p>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            </section>

            {/* How It Works */}
            <section id="how-it-works" className="py-24 relative overflow-hidden">
                <div className="absolute inset-0 bg-gradient-to-b from-[#292524]/50 to-transparent"/>
                <div className="relative max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
                    <div className="text-center mb-16">
                        <h2 className="text-sm font-bold uppercase tracking-widest text-[#E07850] mb-4">The
                            Pipeline</h2>
                        <p className="text-3xl sm:text-4xl font-bold text-[#FAFAF9]">
                            How It Works
                        </p>
                    </div>

                    <div className="relative">
                        {/* Connection line */}
                        <div
                            className="hidden lg:block absolute top-1/2 left-0 right-0 h-0.5 bg-gradient-to-r from-[#9333EA] via-[#22C55E] to-[#EF4444] -translate-y-1/2"/>

                        <div className="grid lg:grid-cols-5 gap-8">
                            {[
                                {
                                    step: 1,
                                    agent: 'Nova',
                                    action: 'Analyze',
                                    desc: 'Understands your request and identifies affected domains'
                                },
                                {
                                    step: 2,
                                    agent: 'Scout',
                                    action: 'Retrieve',
                                    desc: 'Searches your codebase using vector embeddings'
                                },
                                {
                                    step: 3,
                                    agent: 'Blueprint',
                                    action: 'Plan',
                                    desc: 'Creates ordered steps respecting dependencies'
                                },
                                {
                                    step: 4,
                                    agent: 'Forge',
                                    action: 'Execute',
                                    desc: 'Generates production-ready Laravel code'
                                },
                                {
                                    step: 5,
                                    agent: 'Guardian',
                                    action: 'Validate',
                                    desc: 'Checks conventions, security, and quality'
                                },
                            ].map((item, index) => (
                                <div key={item.step} className="relative text-center">
                                    <div
                                        className="relative z-10 w-16 h-16 mx-auto mb-4 bg-[#292524] rounded-2xl border-2 border-[#44403C] flex items-center justify-center">
                                        <span className="text-2xl font-bold text-[#E07850]">{item.step}</span>
                                    </div>
                                    <h3 className="text-lg font-bold text-[#FAFAF9] mb-1">{item.action}</h3>
                                    <p className="text-sm text-[#E07850] font-medium mb-2">{item.agent}</p>
                                    <p className="text-sm text-[#A8A29E]">{item.desc}</p>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            </section>

            {/* Why Maestro */}
            <section className="py-24 relative">
                <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
                    <div className="grid lg:grid-cols-2 gap-16 items-center">
                        <div>
                            <h2 className="text-sm font-bold uppercase tracking-widest text-[#E07850] mb-4">Why
                                Maestro</h2>
                            <p className="text-3xl sm:text-4xl font-bold text-[#FAFAF9] mb-6">
                                Focus on Building, <span className="text-[#E07850]">Not Boilerplate</span>
                            </p>
                            <ul className="space-y-4">
                                {[
                                    {
                                        icon: Zap,
                                        label: 'Ship Features Faster',
                                        desc: 'Generate complete CRUD endpoints in seconds, not hours'
                                    },
                                    {
                                        icon: ShieldCheck,
                                        label: 'Built-in Best Practices',
                                        desc: 'Every line follows Laravel conventions and security standards'
                                    },
                                    {
                                        icon: GitBranch,
                                        label: 'Understands Your Code',
                                        desc: 'Learns your project structure and follows your patterns'
                                    },
                                    {
                                        icon: CheckCircle,
                                        label: 'Production Ready',
                                        desc: 'Validated code with proper error handling and type hints'
                                    },
                                ].map((item) => (
                                    <li key={item.label} className="flex items-start gap-4">
                                        <div
                                            className="w-10 h-10 bg-[#E07850]/10 rounded-xl flex items-center justify-center flex-shrink-0">
                                            <item.icon className="w-5 h-5 text-[#E07850]"/>
                                        </div>
                                        <div>
                                            <h3 className="font-semibold text-[#FAFAF9]">{item.label}</h3>
                                            <p className="text-sm text-[#A8A29E]">{item.desc}</p>
                                        </div>
                                    </li>
                                ))}
                            </ul>
                        </div>
                        <div className="relative">
                            <div
                                className="absolute -inset-4 bg-gradient-to-r from-[#E07850]/20 to-[#FF2D20]/20 rounded-3xl opacity-30 blur-2xl"/>
                            <div className="relative bg-[#292524] rounded-2xl shadow-2xl border border-[#44403C] p-8">
                                <div className="grid grid-cols-2 gap-6">
                                    {[
                                        {value: '10x', label: 'Faster Development'},
                                        {value: '100%', label: 'Laravel Compatible'},
                                        {value: '< 30s', label: 'Per Feature'},
                                        {value: '0', label: 'Boilerplate Writing'},
                                    ].map((stat) => (
                                        <div key={stat.label} className="text-center">
                                            <p className="text-4xl font-bold text-[#E07850]">{stat.value}</p>
                                            <p className="text-[#78716C] text-sm mt-1">{stat.label}</p>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </section>

            {/* CTA Section */}
            <section className="py-24 relative">
                <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
                    <h2 className="text-3xl sm:text-4xl font-bold text-[#FAFAF9] mb-6">
                        Ready to Supercharge Your Laravel Development?
                    </h2>
                    <p className="text-lg text-[#A8A29E] mb-8 max-w-2xl mx-auto">
                        Connect your GitHub repository and let the AI agents understand your codebase.
                    </p>
                    <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
                        {showAuthenticatedUI ? (
                            <Link
                                href="/dashboard"
                                className="group relative px-8 py-4 text-base font-semibold text-white bg-gradient-to-r from-[#E07850] to-[#C65D3D] rounded-2xl overflow-hidden shadow-xl shadow-[#E07850]/30 hover:shadow-2xl hover:shadow-[#E07850]/40 hover:-translate-y-1 transition-all duration-300"
                            >
                <span className="relative z-10 flex items-center gap-2">
                  Go to Dashboard
                  <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform"/>
                </span>
                                <div
                                    className="absolute inset-0 bg-gradient-to-r from-[#C65D3D] to-[#A64D36] opacity-0 group-hover:opacity-100 transition-opacity"/>
                            </Link>
                        ) : (
                            <a
                                href={`${apiUrl}/auth/github`}
                                className="group relative px-8 py-4 text-base font-semibold text-white bg-gradient-to-r from-[#E07850] to-[#C65D3D] rounded-2xl overflow-hidden shadow-xl shadow-[#E07850]/30 hover:shadow-2xl hover:shadow-[#E07850]/40 hover:-translate-y-1 transition-all duration-300"
                            >
                <span className="relative z-10 flex items-center gap-2">
                  Get Started Free
                  <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform"/>
                </span>
                                <div
                                    className="absolute inset-0 bg-gradient-to-r from-[#C65D3D] to-[#A64D36] opacity-0 group-hover:opacity-100 transition-opacity"/>
                            </a>
                        )}
                        <a
                            href="https://github.com"
                            target="_blank"
                            rel="noreferrer"
                            className="px-8 py-4 text-base font-semibold text-[#FAFAF9] bg-[#292524] border-2 border-[#44403C] rounded-2xl hover:border-[#57534E] hover:shadow-lg hover:shadow-black/20 hover:-translate-y-1 transition-all duration-300 flex items-center gap-2"
                        >
                            <GitBranch className="w-5 h-5"/>
                            View on GitHub
                        </a>
                    </div>
                </div>
            </section>

            {/* Footer */}
            <footer className="py-12 border-t border-[#292524]">
                <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
                    <div className="flex flex-col md:flex-row items-center justify-between gap-6">
                        <div className="flex items-center gap-3">
                            <div
                                className="w-8 h-8 bg-gradient-to-br from-[#E07850] to-[#C65D3D] rounded-lg flex items-center justify-center">
                                <svg className="w-5 h-5 text-white" viewBox="0 0 24 24" fill="none"
                                     stroke="currentColor" strokeWidth="2">
                                    <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
                                </svg>
                            </div>
                            <span className="text-lg font-bold text-[#FAFAF9]">Maestro AI</span>
                            <span className="text-sm text-[#78716C]">for Laravel</span>
                        </div>
                        <div className="flex items-center gap-6">
                            <a href="#"
                               className="text-sm text-[#78716C] hover:text-[#FAFAF9] transition-colors">Privacy</a>
                            <a href="#"
                               className="text-sm text-[#78716C] hover:text-[#FAFAF9] transition-colors">Terms</a>
                            <a href="#"
                               className="text-sm text-[#78716C] hover:text-[#FAFAF9] transition-colors">Contact</a>
                        </div>
                        <p className="text-sm text-[#78716C]">© 2025 Maestro AI. Built for Laravel developers.</p>
                    </div>
                </div>
            </footer>
        </div>
    );
}