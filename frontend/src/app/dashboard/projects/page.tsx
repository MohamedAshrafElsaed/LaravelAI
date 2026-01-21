// frontend/src/app/dashboard/projects/page.tsx
'use client';

import { motion } from 'framer-motion';
import ProjectsPage from '@/components/dashboard/ProjectsPage';

export default function ProjectsRoutePage() {
    return (
        <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="flex-1 flex flex-col min-h-0 overflow-hidden"
        >
            <ProjectsPage />
        </motion.div>
    );
}