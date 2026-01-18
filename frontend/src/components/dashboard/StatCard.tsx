'use client';

import {motion} from 'framer-motion';
import {LucideIcon} from 'lucide-react';

interface StatCardProps {
    label: string;
    value: string | number;
    change?: string;
    changeType?: 'positive' | 'negative' | 'neutral';
    icon?: LucideIcon;
    delay?: number;
}

export default function StatCard({
                                     label,
                                     value,
                                     change,
                                     changeType = 'positive',
                                     icon: Icon,
                                     delay = 0,
                                 }: StatCardProps) {
    const getChangeColor = () => {
        switch (changeType) {
            case 'positive':
                return 'text-green-400';
            case 'negative':
                return 'text-red-400';
            case 'neutral':
                return 'text-[var(--color-text-muted)]';
        }
    };

    return (
        <motion.div
            initial={{opacity: 0, y: 10}}
            animate={{opacity: 1, y: 0}}
            transition={{delay}}
            className="bg-[var(--color-bg-surface)] border border-[var(--color-border-subtle)] p-4 rounded-sm relative overflow-hidden group hover:border-[var(--color-border-default)] transition-colors"
        >
            {/* Background decoration */}
            <div className="absolute top-0 right-0 p-2 opacity-10 group-hover:opacity-20 transition-opacity">
                <div className="w-16 h-16 border-2 border-dashed border-[var(--color-text-muted)] rounded-full"/>
            </div>

            {/* Icon */}
            {Icon && (
                <div className="absolute top-3 right-3 opacity-30 group-hover:opacity-50 transition-opacity">
                    <Icon className="w-6 h-6 text-[var(--color-primary)]"/>
                </div>
            )}

            {/* Content */}
            <h3 className="text-xs text-[var(--color-text-dimmer)] uppercase tracking-wider font-medium mb-1">
                {label}
            </h3>
            <div className="flex items-end gap-2">
        <span className="text-2xl font-bold text-[var(--color-text-primary)] font-mono">
          {value}
        </span>
                {change && (
                    <span className={`text-xs font-mono mb-1 ${getChangeColor()}`}>{change}</span>
                )}
            </div>
        </motion.div>
    );
}