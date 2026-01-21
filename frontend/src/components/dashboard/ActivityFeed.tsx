'use client';

import {motion} from 'framer-motion';
import {AlertCircle, CheckCircle2, Code2, FileEdit, GitCommit, GitPullRequest} from 'lucide-react';

export interface Activity {
    id: string;
    type: 'commit' | 'pr' | 'alert' | 'deploy' | 'change';
    message: string;
    user: string;
    timestamp: string;
    meta: string;
    projectId?: string;
}

interface ActivityFeedProps {
    activities?: Activity[];
    loading?: boolean;
}

const defaultActivities: Activity[] = [
    {
        id: '1',
        type: 'commit',
        message: 'feat: implement virtual scrolling for logs',
        user: 'alex.dev',
        timestamp: '14:32:18',
        meta: 'a3f2c1b',
    },
    {
        id: '2',
        type: 'pr',
        message: 'Merge pull request #42 from feature/auth',
        user: 'sarah.engineer',
        timestamp: '14:30:05',
        meta: '#42',
    },
    {
        id: '3',
        type: 'deploy',
        message: 'Production deployment started',
        user: 'system',
        timestamp: '14:28:11',
        meta: 'v2.4.0',
    },
    {
        id: '4',
        type: 'alert',
        message: 'High memory usage detected on worker-01',
        user: 'monitor',
        timestamp: '14:15:22',
        meta: 'WARN',
    },
    {
        id: '5',
        type: 'change',
        message: 'fix: resolve race condition in cache',
        user: 'AI Assistant',
        timestamp: '13:55:41',
        meta: '8b9c2d1',
    },
];

export default function ActivityFeed({activities, loading = false}: ActivityFeedProps) {
    const displayActivities = activities && activities.length > 0 ? activities : defaultActivities;

    const getIcon = (type: Activity['type']) => {
        switch (type) {
            case 'commit':
                return <GitCommit size={14} className="text-blue-400"/>;
            case 'pr':
                return <GitPullRequest size={14} className="text-purple-400"/>;
            case 'deploy':
                return <CheckCircle2 size={14} className="text-green-400"/>;
            case 'alert':
                return <AlertCircle size={14} className="text-[var(--color-primary)]"/>;
            case 'change':
                return <FileEdit size={14} className="text-cyan-400"/>;
            default:
                return <Code2 size={14} className="text-[var(--color-text-muted)]"/>;
        }
    };

    const getTypeLabel = (type: Activity['type']) => {
        switch (type) {
            case 'commit':
                return 'Commit';
            case 'pr':
                return 'Pull Request';
            case 'deploy':
                return 'Deploy';
            case 'alert':
                return 'Alert';
            case 'change':
                return 'Code Change';
            default:
                return 'Activity';
        }
    };

    if (loading) {
        return (
            <div className="h-full flex flex-col">
                <div className="flex items-center justify-between mb-4 px-1">
                    <h3 className="text-xs font-bold text-[var(--color-text-muted)] uppercase tracking-wider">
                        Activity Log
                    </h3>
                    <span className="text-[10px] font-mono text-[var(--color-text-dimmer)]">LOADING</span>
                </div>
                <div className="flex-1 flex items-center justify-center">
                    <div
                        className="h-6 w-6 animate-spin rounded-full border-2 border-[var(--color-primary)]/30 border-t-[var(--color-primary)]"/>
                </div>
            </div>
        );
    }

    return (
        <div className="h-full flex flex-col">
            <div className="flex items-center justify-between mb-4 px-1">
                <h3 className="text-xs font-bold text-[var(--color-text-muted)] uppercase tracking-wider">
                    Activity Log
                </h3>
                <span className="text-[10px] font-mono text-[var(--color-text-dimmer)]">
          {displayActivities.length > 0 ? 'LIVE' : 'EMPTY'}
        </span>
            </div>

            <div className="flex-1 overflow-y-auto pr-2 space-y-3">
                {displayActivities.map((item, index) => (
                    <motion.div
                        key={item.id}
                        initial={{opacity: 0, x: -10}}
                        animate={{opacity: 1, x: 0}}
                        transition={{delay: index * 0.05}}
                        className="group flex flex-col gap-1 p-3 rounded-sm border border-dashed border-[var(--color-border-subtle)] hover:border-[var(--color-border-default)] hover:bg-[var(--color-bg-surface)] transition-all cursor-default"
                    >
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                                {getIcon(item.type)}
                                <span className="text-xs font-mono text-[var(--color-text-dimmer)]">
                  {item.timestamp}
                </span>
                            </div>
                            <span
                                className={`text-[10px] font-mono px-1.5 py-0.5 rounded ${
                                    item.type === 'alert'
                                        ? 'bg-[var(--color-primary-subtle)] text-[var(--color-primary)]'
                                        : 'bg-[var(--color-bg-elevated)] text-[var(--color-text-muted)]'
                                }`}
                            >
                {item.meta}
              </span>
                        </div>

                        <p className="text-sm text-[var(--color-text-primary)] font-medium truncate pl-6">
                            {item.message}
                        </p>

                        <div className="flex items-center justify-between pl-6 mt-1">
                            <div className="flex items-center">
                                <div
                                    className="w-4 h-4 rounded-full bg-[var(--color-bg-elevated)] flex items-center justify-center text-[8px] text-[var(--color-text-secondary)] mr-2">
                                    {item.user[0].toUpperCase()}
                                </div>
                                <span className="text-xs text-[var(--color-text-dimmer)]">{item.user}</span>
                            </div>
                            <span className="text-[10px] text-[var(--color-text-dimmer)]">
                {getTypeLabel(item.type)}
              </span>
                        </div>
                    </motion.div>
                ))}
            </div>
        </div>
    );
}