'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { useRouter } from 'next/navigation';
import { FileCode, Copy, Check, X } from 'lucide-react';
import { useDashboard } from '@/hooks/useDashboardData';
import DevFileExplorer from '@/components/dashboard/DevFileExplorer';
import EmptyState from '@/components/dashboard/EmptyState';
import ProjectSelector from '@/components/dashboard/ProjectSelector';

// Helper to get language from file path
const getLanguageFromPath = (path: string): string => {
    const ext = path.split('.').pop()?.toLowerCase() || '';
    const langMap: Record<string, string> = {
        php: 'php', js: 'javascript', ts: 'typescript', jsx: 'jsx', tsx: 'tsx',
        json: 'json', css: 'css', scss: 'scss', yaml: 'yaml', yml: 'yaml',
        md: 'markdown', sql: 'sql', vue: 'vue', blade: 'blade',
    };
    return langMap[ext] || 'plaintext';
};

export default function FilesRoutePage() {
    const router = useRouter();
    const {
        projects,
        selectedProject,
        loading,
        setSelectedProjectId,
    } = useDashboard();

    const [selectedFile, setSelectedFile] = useState<string | null>(null);
    const [fileContent, setFileContent] = useState<string>('');
    const [copied, setCopied] = useState(false);

    // Handle file selection
    const handleFileSelect = (filePath: string, content: string) => {
        setSelectedFile(filePath);
        setFileContent(content);
    };

    // Handle copy
    const handleCopy = async () => {
        try {
            await navigator.clipboard.writeText(fileContent);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        } catch (err) {
            console.error('Failed to copy:', err);
        }
    };

    // Handle close file
    const handleCloseFile = () => {
        setSelectedFile(null);
        setFileContent('');
    };

    // Clear selected file when switching projects
    useEffect(() => {
        setSelectedFile(null);
        setFileContent('');
    }, [selectedProject?.id]);

    const lines = fileContent.split('\n');
    const fileName = selectedFile?.split('/').pop() || '';

    return (
        <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="flex-1 flex flex-col h-full overflow-hidden"
        >
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--color-border-subtle)] bg-[var(--color-bg-surface)]">
                <div>
                    <h1 className="text-xl font-bold text-[var(--color-text-primary)]">
                        File Explorer
                    </h1>
                    <p className="text-sm text-[var(--color-text-dimmer)]">
                        Browse and view your project files
                    </p>
                </div>
                <ProjectSelector
                    projects={projects}
                    selectedProject={selectedProject}
                    onSelect={setSelectedProjectId}
                    loading={loading}
                />
            </div>

            {/* Content */}
            <div className="flex-1 flex overflow-hidden">
                {/* File Tree Sidebar */}
                <div className="w-64 flex-shrink-0 border-r border-[var(--color-border-subtle)] overflow-hidden">
                    {selectedProject?.id ? (
                        <DevFileExplorer
                            projectId={selectedProject.id}
                            onFileSelect={handleFileSelect}
                            selectedFile={selectedFile}
                        />
                    ) : (
                        <div className="flex items-center justify-center h-full p-4">
                            <EmptyState
                                type="generic"
                                message="Select a project first"
                                action={{
                                    label: 'Go to Projects',
                                    onClick: () => router.push('/dashboard/projects'),
                                }}
                            />
                        </div>
                    )}
                </div>

                {/* File Content Viewer */}
                <div className="flex-1 flex flex-col bg-[var(--color-bg-surface)] overflow-hidden">
                    {selectedFile ? (
                        <>
                            {/* File Header */}
                            <div className="flex items-center justify-between px-4 py-2 bg-[var(--color-bg-primary)] border-b border-[var(--color-border-subtle)]">
                                <div className="flex items-center gap-2 min-w-0">
                                    <FileCode className="h-4 w-4 text-[var(--color-text-muted)]" />
                                    <span className="text-sm font-medium text-[var(--color-text-primary)]">
                                        {fileName}
                                    </span>
                                    <span className="text-xs text-[var(--color-text-dimmer)] truncate">
                                        {selectedFile}
                                    </span>
                                </div>
                                <div className="flex items-center gap-1">
                                    <span className="px-2 py-0.5 text-xs bg-[var(--color-bg-hover)] text-[var(--color-text-muted)] rounded">
                                        {getLanguageFromPath(selectedFile)}
                                    </span>
                                    <button
                                        onClick={handleCopy}
                                        className="p-1.5 hover:bg-[var(--color-bg-hover)] rounded transition-colors"
                                        title="Copy"
                                    >
                                        {copied ? (
                                            <Check className="h-4 w-4 text-green-400" />
                                        ) : (
                                            <Copy className="h-4 w-4 text-[var(--color-text-muted)]" />
                                        )}
                                    </button>
                                    <button
                                        onClick={handleCloseFile}
                                        className="p-1.5 hover:bg-[var(--color-bg-hover)] rounded transition-colors"
                                        title="Close"
                                    >
                                        <X className="h-4 w-4 text-[var(--color-text-muted)]" />
                                    </button>
                                </div>
                            </div>

                            {/* Code Content */}
                            <div className="flex-1 overflow-auto">
                                <div className="flex min-h-full">
                                    {/* Line Numbers */}
                                    <div className="flex-shrink-0 py-4 pr-2 pl-4 bg-[var(--color-bg-primary)] border-r border-[var(--color-border-subtle)] select-none sticky left-0">
                                        {lines.map((_, i) => (
                                            <div
                                                key={i}
                                                className="text-right text-xs font-mono text-[var(--color-text-dimmer)] leading-6 px-2"
                                            >
                                                {i + 1}
                                            </div>
                                        ))}
                                    </div>
                                    {/* Code */}
                                    <pre className="flex-1 p-4 overflow-x-auto font-mono text-sm leading-6 text-[var(--color-text-primary)]">
                                        <code>{fileContent}</code>
                                    </pre>
                                </div>
                            </div>

                            {/* Footer */}
                            <div className="px-4 py-2 bg-[var(--color-bg-primary)] border-t border-[var(--color-border-subtle)] text-xs text-[var(--color-text-dimmer)]">
                                {lines.length} lines • {(fileContent.length / 1024).toFixed(1)} KB • UTF-8
                            </div>
                        </>
                    ) : (
                        <div className="flex-1 flex items-center justify-center">
                            <EmptyState type="files" message="Select a file to view contents" />
                        </div>
                    )}
                </div>
            </div>
        </motion.div>
    );
}