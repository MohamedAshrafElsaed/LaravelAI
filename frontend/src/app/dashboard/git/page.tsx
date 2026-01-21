'use client';

import {motion} from 'framer-motion';
import {useRouter} from 'next/navigation';
import {useDashboard} from '@/hooks/useDashboardData';
import EmptyState from '@/components/dashboard/EmptyState';
import ProjectSelector from '@/components/dashboard/ProjectSelector';

export default function GitRoutePage() {
    const router = useRouter();
    const {
        projects,
        selectedProject,
        loading,
        setSelectedProjectId,
    } = useDashboard();

    return (
        <motion.div
            initial={{opacity: 0}}
            animate={{opacity: 1}}
            exit={{opacity: 0}}
            className="flex-1 flex flex-col h-full overflow-hidden"
        >
            {/* Header */}
            <div
                className="flex items-center justify-between px-6 py-4 border-b border-[var(--color-border-subtle)] bg-[var(--color-bg-surface)]">
                <div>
                    <h1 className="text-xl font-bold text-[var(--color-text-primary)]">
                        Source Control
                    </h1>
                    <p className="text-sm text-[var(--color-text-dimmer)]">
                        Manage branches and view git changes
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
            <div className="flex-1 flex items-center justify-center">
                {selectedProject ? (
                    <EmptyState
                        type="generic"
                        message="Source control features coming soon"
                        action={{
                            label: 'View Project Files',
                            onClick: () => router.push('/dashboard/files'),
                        }}
                    />
                ) : (
                    <EmptyState
                        type="generic"
                        message="Select a project to view source control"
                        action={{
                            label: 'Go to Projects',
                            onClick: () => router.push('/dashboard/projects'),
                        }}
                    />
                )}
            </div>
        </motion.div>
    );
}