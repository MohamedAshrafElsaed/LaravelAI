'use client';

import {useState} from 'react';
import {AnimatePresence, motion} from 'framer-motion';
import {ChevronDown, ChevronRight, File, FileCode, FileJson, FileType, Folder,} from 'lucide-react';

interface FileNode {
    id: string;
    name: string;
    type: 'folder' | 'file';
    fileType?: 'ts' | 'tsx' | 'php' | 'json' | 'css' | 'blade' | 'config';
    children?: FileNode[];
    meta?: string;
    lines?: number;
}

interface DevFileExplorerProps {
    files?: FileNode[];
    onFileSelect?: (file: FileNode) => void;
}

const defaultFileSystem: FileNode[] = [
    {
        id: 'app',
        name: 'app',
        type: 'folder',
        children: [
            {
                id: 'http',
                name: 'Http',
                type: 'folder',
                children: [
                    {
                        id: 'controllers',
                        name: 'Controllers',
                        type: 'folder',
                        children: [
                            {
                                id: 'UserController.php',
                                name: 'UserController.php',
                                type: 'file',
                                fileType: 'php',
                                meta: '4.2KB',
                                lines: 186
                            },
                            {
                                id: 'AuthController.php',
                                name: 'AuthController.php',
                                type: 'file',
                                fileType: 'php',
                                meta: '3.1KB',
                                lines: 142
                            },
                            {
                                id: 'ApiController.php',
                                name: 'ApiController.php',
                                type: 'file',
                                fileType: 'php',
                                meta: '2.8KB',
                                lines: 124
                            },
                        ],
                    },
                    {
                        id: 'middleware',
                        name: 'Middleware',
                        type: 'folder',
                        children: [
                            {
                                id: 'Authenticate.php',
                                name: 'Authenticate.php',
                                type: 'file',
                                fileType: 'php',
                                meta: '1.2KB',
                                lines: 48
                            },
                        ],
                    },
                ],
            },
            {
                id: 'models',
                name: 'Models',
                type: 'folder',
                children: [
                    {id: 'User.php', name: 'User.php', type: 'file', fileType: 'php', meta: '2.4KB', lines: 98},
                    {id: 'Project.php', name: 'Project.php', type: 'file', fileType: 'php', meta: '1.8KB', lines: 72},
                ],
            },
            {
                id: 'services',
                name: 'Services',
                type: 'folder',
                children: [
                    {
                        id: 'UserService.php',
                        name: 'UserService.php',
                        type: 'file',
                        fileType: 'php',
                        meta: '3.6KB',
                        lines: 156
                    },
                ],
            },
        ],
    },
    {
        id: 'resources',
        name: 'resources',
        type: 'folder',
        children: [
            {
                id: 'views',
                name: 'views',
                type: 'folder',
                children: [
                    {
                        id: 'welcome.blade.php',
                        name: 'welcome.blade.php',
                        type: 'file',
                        fileType: 'blade',
                        meta: '2.1KB',
                        lines: 86
                    },
                ],
            },
        ],
    },
    {
        id: 'routes',
        name: 'routes',
        type: 'folder',
        children: [
            {id: 'api.php', name: 'api.php', type: 'file', fileType: 'php', meta: '1.4KB', lines: 58},
            {id: 'web.php', name: 'web.php', type: 'file', fileType: 'php', meta: '0.8KB', lines: 32},
        ],
    },
    {id: 'composer.json', name: 'composer.json', type: 'file', fileType: 'json', meta: '2.1KB', lines: 78},
];

function FileTreeNode({
                          node,
                          level,
                          onFileSelect,
                      }: {
    node: FileNode;
    level: number;
    onFileSelect?: (file: FileNode) => void;
}) {
    const [isOpen, setIsOpen] = useState(level === 0);

    const getIcon = (node: FileNode) => {
        if (node.type === 'folder') return <Folder size={14} className="text-blue-400"/>;
        switch (node.fileType) {
            case 'tsx':
            case 'ts':
                return <FileCode size={14} className="text-blue-300"/>;
            case 'php':
                return <FileCode size={14} className="text-purple-400"/>;
            case 'blade':
                return <FileType size={14} className="text-orange-400"/>;
            case 'json':
                return <FileJson size={14} className="text-yellow-200"/>;
            case 'css':
                return <FileType size={14} className="text-pink-400"/>;
            default:
                return <File size={14} className="text-[var(--color-text-muted)]"/>;
        }
    };

    const handleClick = () => {
        if (node.type === 'folder') {
            setIsOpen(!isOpen);
        } else if (onFileSelect) {
            onFileSelect(node);
        }
    };

    return (
        <div>
            <div
                className="flex items-center px-2 py-1 hover:bg-[var(--color-bg-surface)] cursor-pointer group text-sm"
                style={{paddingLeft: `${level * 12 + 8}px`}}
                onClick={handleClick}
            >
        <span className="mr-1 text-[var(--color-text-dimmer)]">
          {node.type === 'folder' &&
              (isOpen ? <ChevronDown size={12}/> : <ChevronRight size={12}/>)}
            {node.type === 'file' && <span className="w-3"/>}
        </span>

                <span className="mr-2 opacity-80 group-hover:opacity-100 transition-opacity">
          {getIcon(node)}
        </span>

                <span
                    className={`truncate ${
                        node.type === 'folder'
                            ? 'text-[var(--color-text-primary)]'
                            : 'text-[var(--color-text-muted)] group-hover:text-[var(--color-text-primary)]'
                    }`}
                >
          {node.name}
        </span>

                {node.type === 'file' && (
                    <span
                        className="ml-auto text-[10px] font-mono text-[var(--color-text-dimmer)] group-hover:text-[var(--color-text-muted)]">
            {node.meta}
          </span>
                )}
            </div>

            <AnimatePresence>
                {isOpen && node.children && (
                    <motion.div
                        initial={{height: 0, opacity: 0}}
                        animate={{height: 'auto', opacity: 1}}
                        exit={{height: 0, opacity: 0}}
                        transition={{duration: 0.2}}
                        className="overflow-hidden"
                    >
                        {node.children.map((child) => (
                            <FileTreeNode
                                key={child.id}
                                node={child}
                                level={level + 1}
                                onFileSelect={onFileSelect}
                            />
                        ))}
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
}

export default function DevFileExplorer({
                                            files = defaultFileSystem,
                                            onFileSelect,
                                        }: DevFileExplorerProps) {
    return (
        <div className="h-full border-r border-[var(--color-border-subtle)] bg-[var(--color-bg-primary)] flex flex-col">
            <div className="h-10 flex items-center px-4 border-b border-[var(--color-border-subtle)]">
        <span className="text-xs font-bold text-[var(--color-text-muted)] uppercase tracking-wider">
          Explorer
        </span>
            </div>
            <div className="flex-1 overflow-y-auto py-2">
                {files.map((node) => (
                    <FileTreeNode key={node.id} node={node} level={0} onFileSelect={onFileSelect}/>
                ))}
            </div>
        </div>
    );
}