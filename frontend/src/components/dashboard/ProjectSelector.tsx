'use client';

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronDown, Folder, Check, Circle } from 'lucide-react';

interface Project {
    id: string;
    name: string;
    repo_full_name: string;
    status: string;
    health_score?: number;
}

interface ProjectSelectorProps {
    projects: Project[];
    selectedProject: Project | null;
    onSelect: (projectId: string) => void;
    loading?: boolean;
}

export default function ProjectSelector({
                                            projects,
                                            selectedProject,
                                            onSelect,
                                            loading = false,
                                        }: ProjectSelectorProps) {
    const [isOpen, setIsOpen] = useState(false);

    const getStatusColor = (status: string) => {
        switch (status) {
            case 'ready':
                return 'text-green-400';
            case 'indexing':
            case 'cloning':
            case 'scanning':
                return 'text-blue-400';
            case 'error':
                return 'text-red-400';
            default:
                return 'text-[var(--color-text-dimmer)]';
        }
    };

    if (loading) {
        return (
            <div className="w-48 h-10 bg-[var(--color-bg-surface)] border border-[var(--color-border-subtle)] rounded-lg animate-pulse" />
        );
    }

    if (projects.length === 0) {
        return (
            <div className="px-3 py-2 text-sm text-[var(--color-text-muted)] border border-dashed border-[var(--color-border-subtle)] rounded-lg">
                No projects
            </div>
        );
    }

    return (
        <div className="relative">
            <button
                onClick={() => setIsOpen(!isOpen)}
                className="flex items-center gap-2 px-3 py-2 min-w-[200px] bg-[var(--color-bg-surface)] border border-[var(--color-border-subtle)] rounded-lg text-left hover:border-[var(--color-border-default)] transition-colors"
            >
                <Folder className="h-4 w-4 text-[var(--color-primary)]" />
                <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-[var(--color-text-primary)] truncate">
                        {selectedProject?.name || 'Select Project'}
                    </div>
                    {selectedProject && (
                        <div className="flex items-center gap-1 text-[10px] text-[var(--color-text-dimmer)]">
                            <Circle className={`h-2 w-2 ${getStatusColor(selectedProject.status)}`} fill="currentColor" />
                            <span className="truncate">{selectedProject.repo_full_name}</span>
                        </div>
                    )}
                </div>
                <ChevronDown
                    className={`h-4 w-4 text-[var(--color-text-dimmer)] transition-transform ${
                        isOpen ? 'rotate-180' : ''
                    }`}
                />
            </button>

            <AnimatePresence>
                {isOpen && (
                    <>
                        {/* Backdrop */}
                        <div
                            className="fixed inset-0 z-10"
                            onClick={() => setIsOpen(false)}
                        />

                        {/* Dropdown */}
                        <motion.div
                            initial={{ opacity: 0, y: -10 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -10 }}
                            transition={{ duration: 0.15 }}
                            className="absolute right-0 top-full mt-1 w-72 z-20 bg-[var(--color-bg-surface)] border border-[var(--color-border-subtle)] rounded-lg shadow-xl overflow-hidden"
                        >
                            <div className="p-2 border-b border-[var(--color-border-subtle)]">
                                <div className="text-[10px] font-medium uppercase tracking-wider text-[var(--color-text-dimmer)] px-2">
                                    Projects ({projects.length})
                                </div>
                            </div>

                            <div className="max-h-64 overflow-y-auto p-1">
                                {projects.map((project) => (
                                    <button
                                        key={project.id}
                                        onClick={() => {
                                            onSelect(project.id);
                                            setIsOpen(false);
                                        }}
                                        className={`w-full flex items-center gap-3 px-3 py-2 rounded-md text-left transition-colors ${
                                            selectedProject?.id === project.id
                                                ? 'bg-[var(--color-primary-subtle)]'
                                                : 'hover:bg-[var(--color-bg-hover)]'
                                        }`}
                                    >
                                        <Folder
                                            className={`h-4 w-4 flex-shrink-0 ${
                                                selectedProject?.id === project.id
                                                    ? 'text-[var(--color-primary)]'
                                                    : 'text-[var(--color-text-muted)]'
                                            }`}
                                        />
                                        <div className="flex-1 min-w-0">
                                            <div
                                                className={`text-sm font-medium truncate ${
                                                    selectedProject?.id === project.id
                                                        ? 'text-[var(--color-primary)]'
                                                        : 'text-[var(--color-text-primary)]'
                                                }`}
                                            >
                                                {project.name}
                                            </div>
                                            <div className="flex items-center gap-2 text-[10px] text-[var(--color-text-dimmer)]">
                                                <span className="truncate">{project.repo_full_name}</span>
                                                <span className={`flex items-center gap-1 ${getStatusColor(project.status)}`}>
                          <Circle className="h-1.5 w-1.5" fill="currentColor" />
                                                    {project.status}
                        </span>
                                            </div>
                                        </div>
                                        {selectedProject?.id === project.id && (
                                            <Check className="h-4 w-4 text-[var(--color-primary)] flex-shrink-0" />
                                        )}
                                    </button>
                                ))}
                            </div>
                        </motion.div>
                    </>
                )}
            </AnimatePresence>
        </div>
    );
}