'use client';

import {motion} from 'framer-motion';
import {Circle, GitBranch, MoreHorizontal} from 'lucide-react';

interface Deployment {
    id: string;
    project: string;
    branch: string;
    status: 'ready' | 'building' | 'error' | 'queued';
    commit: string;
    age: string;
    environment: string;
}

interface DataTableProps {
    deployments?: Deployment[];
    title?: string;
}

const defaultDeployments: Deployment[] = [
    {
        id: 'dep_1',
        project: 'frontend-core',
        branch: 'main',
        status: 'ready',
        commit: '7f3a21',
        age: '2m ago',
        environment: 'Production',
    },
    {
        id: 'dep_2',
        project: 'api-gateway',
        branch: 'feat/auth',
        status: 'building',
        commit: '8b1c9d',
        age: '45s ago',
        environment: 'Preview',
    },
    {
        id: 'dep_3',
        project: 'worker-service',
        branch: 'fix/retry',
        status: 'error',
        commit: 'e4d2c1',
        age: '1h ago',
        environment: 'Staging',
    },
    {
        id: 'dep_4',
        project: 'frontend-core',
        branch: 'main',
        status: 'ready',
        commit: '9a8b7c',
        age: '3h ago',
        environment: 'Production',
    },
    {
        id: 'dep_5',
        project: 'database-migration',
        branch: 'chore/idx',
        status: 'queued',
        commit: '1f2e3d',
        age: '5m ago',
        environment: 'Staging',
    },
];

export default function DataTable({
                                      deployments = defaultDeployments,
                                      title = 'Recent Deployments',
                                  }: DataTableProps) {
    const getStatusColor = (status: Deployment['status']) => {
        switch (status) {
            case 'ready':
                return 'text-green-400';
            case 'building':
                return 'text-blue-400';
            case 'error':
                return 'text-[var(--color-primary)]';
            case 'queued':
                return 'text-[var(--color-text-muted)]';
        }
    };

    return (
        <div
            className="w-full overflow-hidden border border-[var(--color-border-subtle)] rounded-sm bg-[var(--color-bg-primary)]">
            <div
                className="flex items-center justify-between px-4 py-3 border-b border-[var(--color-border-subtle)] bg-[var(--color-bg-surface)]">
                <h3 className="text-sm font-semibold text-[var(--color-text-primary)]">{title}</h3>
                <div className="flex gap-2">
                    <button
                        className="text-xs text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)] transition-colors">
                        Filter
                    </button>
                    <button
                        className="text-xs text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)] transition-colors">
                        Export
                    </button>
                </div>
            </div>

            <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                    <thead>
                    <tr className="border-b border-[var(--color-border-subtle)]">
                        <th className="px-4 py-2 text-[10px] uppercase tracking-wider text-[var(--color-text-dimmer)] font-medium">
                            Project
                        </th>
                        <th className="px-4 py-2 text-[10px] uppercase tracking-wider text-[var(--color-text-dimmer)] font-medium">
                            Status
                        </th>
                        <th className="px-4 py-2 text-[10px] uppercase tracking-wider text-[var(--color-text-dimmer)] font-medium font-mono">
                            COMMIT
                        </th>
                        <th className="px-4 py-2 text-[10px] uppercase tracking-wider text-[var(--color-text-dimmer)] font-medium">
                            Environment
                        </th>
                        <th className="px-4 py-2 text-[10px] uppercase tracking-wider text-[var(--color-text-dimmer)] font-medium text-right">
                            Age
                        </th>
                        <th className="px-4 py-2 w-10"></th>
                    </tr>
                    </thead>
                    <tbody className="divide-y divide-[var(--color-border-subtle)]">
                    {deployments.map((row, i) => (
                        <motion.tr
                            key={row.id}
                            initial={{opacity: 0, y: 5}}
                            animate={{opacity: 1, y: 0}}
                            transition={{delay: i * 0.05}}
                            className="group hover:bg-[var(--color-bg-surface)] transition-colors"
                        >
                            <td className="px-4 py-2.5">
                                <div className="flex flex-col">
                    <span className="text-sm text-[var(--color-text-primary)] font-medium">
                      {row.project}
                    </span>
                                    <span
                                        className="text-xs text-[var(--color-text-dimmer)] font-mono flex items-center gap-1">
                      <GitBranch className="w-3 h-3"/> {row.branch}
                    </span>
                                </div>
                            </td>
                            <td className="px-4 py-2.5">
                                <div
                                    className={`flex items-center gap-2 text-xs font-mono uppercase ${getStatusColor(
                                        row.status
                                    )}`}
                                >
                                    <Circle
                                        size={8}
                                        fill="currentColor"
                                        className={row.status === 'building' ? 'animate-pulse' : ''}
                                    />
                                    {row.status}
                                </div>
                            </td>
                            <td className="px-4 py-2.5">
                  <span
                      className="font-mono text-xs text-[var(--color-text-muted)] bg-[var(--color-bg-elevated)] px-1.5 py-0.5 rounded border border-[var(--color-border-subtle)]">
                    {row.commit}
                  </span>
                            </td>
                            <td className="px-4 py-2.5">
                                <span className="text-xs text-[var(--color-text-muted)]">{row.environment}</span>
                            </td>
                            <td className="px-4 py-2.5 text-right">
                                <span className="text-xs text-[var(--color-text-dimmer)] font-mono">{row.age}</span>
                            </td>
                            <td className="px-4 py-2.5 text-right">
                                <button
                                    className="text-[var(--color-text-dimmer)] hover:text-[var(--color-text-primary)] opacity-0 group-hover:opacity-100 transition-all">
                                    <MoreHorizontal size={16}/>
                                </button>
                            </td>
                        </motion.tr>
                    ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
}