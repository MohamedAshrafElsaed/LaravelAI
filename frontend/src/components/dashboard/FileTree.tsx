'use client';

import { useState, useCallback, useEffect } from 'react';
import {
    ChevronRight,
    ChevronDown,
    Folder,
    FolderOpen,
    File,
    FileCode,
    FileText,
    Database,
    Layout,
    Settings,
    RefreshCw,
    Search,
} from 'lucide-react';
import { filesApi } from '@/lib/api';

// ============== TYPES ==============
export interface FileNode {
    name: string;
    path: string;
    type: 'file' | 'directory';
    children?: FileNode[];
    indexed?: boolean;
}

interface FileTreeProps {
    projectId: string;
    onFileSelect: (filePath: string, content: string) => void;
    selectedFile: string | null;
}

// ============== HELPERS ==============
const getFileIcon = (fileName: string) => {
    const ext = fileName.split('.').pop()?.toLowerCase();

    switch (ext) {
        case 'php':
            return <FileCode className="h-4 w-4 text-purple-400" />;
        case 'blade':
            return <Layout className="h-4 w-4 text-orange-400" />;
        case 'vue':
        case 'jsx':
        case 'tsx':
            return <FileCode className="h-4 w-4 text-green-400" />;
        case 'js':
        case 'ts':
            return <FileCode className="h-4 w-4 text-yellow-400" />;
        case 'css':
        case 'scss':
        case 'sass':
            return <FileText className="h-4 w-4 text-blue-400" />;
        case 'json':
        case 'yaml':
        case 'yml':
            return <Settings className="h-4 w-4 text-gray-400" />;
        case 'sql':
            return <Database className="h-4 w-4 text-cyan-400" />;
        case 'md':
            return <FileText className="h-4 w-4 text-gray-400" />;
        default:
            return <File className="h-4 w-4 text-gray-400" />;
    }
};

const getLanguageFromPath = (path: string): string => {
    const ext = path.split('.').pop()?.toLowerCase();
    const langMap: Record<string, string> = {
        php: 'php',
        js: 'javascript',
        ts: 'typescript',
        jsx: 'jsx',
        tsx: 'tsx',
        vue: 'vue',
        css: 'css',
        scss: 'scss',
        json: 'json',
        yaml: 'yaml',
        yml: 'yaml',
        md: 'markdown',
        sql: 'sql',
        blade: 'blade',
    };
    return langMap[ext || ''] || 'plaintext';
};

// ============== TREE NODE COMPONENT ==============
function TreeNode({
                      node,
                      depth,
                      onSelect,
                      selectedPath,
                      expandedPaths,
                      toggleExpand,
                  }: {
    node: FileNode;
    depth: number;
    onSelect: (node: FileNode) => void;
    selectedPath: string | null;
    expandedPaths: Set<string>;
    toggleExpand: (path: string) => void;
}) {
    const isExpanded = expandedPaths.has(node.path);
    const isSelected = node.path === selectedPath;
    const isDirectory = node.type === 'directory';

    const handleClick = () => {
        if (isDirectory) {
            toggleExpand(node.path);
        } else {
            onSelect(node);
        }
    };

    return (
        <div>
            <div
                className={`flex items-center gap-1 px-2 py-1 cursor-pointer rounded text-sm transition-colors ${
                    isSelected
                        ? 'bg-[var(--color-primary)]/20 text-[var(--color-primary)]'
                        : 'text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-elevated)] hover:text-[var(--color-text-primary)]'
                }`}
                style={{ paddingLeft: `${depth * 12 + 8}px` }}
                onClick={handleClick}
            >
                {/* Expand/collapse icon */}
                {isDirectory ? (
                    <span className="w-4 flex-shrink-0">
            {isExpanded ? (
                <ChevronDown className="h-4 w-4 text-[var(--color-text-secondary)]" />
            ) : (
                <ChevronRight className="h-4 w-4 text-[var(--color-text-secondary)]" />
            )}
          </span>
                ) : (
                    <span className="w-4 flex-shrink-0" />
                )}

                {/* File/folder icon */}
                <span className="flex-shrink-0">
          {isDirectory ? (
              isExpanded ? (
                  <FolderOpen className="h-4 w-4 text-yellow-500" />
              ) : (
                  <Folder className="h-4 w-4 text-yellow-500" />
              )
          ) : (
              getFileIcon(node.name)
          )}
        </span>

                {/* Name */}
                <span className="truncate flex-1">{node.name}</span>

                {/* Indexed indicator */}
                {node.indexed && (
                    <span
                        className="ml-auto h-2 w-2 rounded-full bg-green-500 flex-shrink-0"
                        title="Indexed in vector DB"
                    />
                )}
            </div>

            {/* Children */}
            {isDirectory && isExpanded && node.children && (
                <div>
                    {node.children.map((child) => (
                        <TreeNode
                            key={child.path}
                            node={child}
                            depth={depth + 1}
                            onSelect={onSelect}
                            selectedPath={selectedPath}
                            expandedPaths={expandedPaths}
                            toggleExpand={toggleExpand}
                        />
                    ))}
                </div>
            )}
        </div>
    );
}

// ============== MAIN FILE TREE COMPONENT ==============
export default function FileTree({ projectId, onFileSelect, selectedFile }: FileTreeProps) {
    const [tree, setTree] = useState<FileNode[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [searchQuery, setSearchQuery] = useState('');
    const [expandedPaths, setExpandedPaths] = useState<Set<string>>(new Set());

    // Fetch file tree
    const fetchTree = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const response = await filesApi.getFileTree(projectId);
            setTree(response.data);

            // Auto-expand first level directories
            const firstLevel = new Set<string>();
            response.data.forEach((node: FileNode) => {
                if (node.type === 'directory') {
                    firstLevel.add(node.path);
                }
            });
            setExpandedPaths(firstLevel);
        } catch (err: any) {
            console.error('Failed to fetch file tree:', err);
            setError(err.response?.data?.detail || 'Failed to load files');
        } finally {
            setLoading(false);
        }
    }, [projectId]);

    useEffect(() => {
        fetchTree();
    }, [fetchTree]);

    // Toggle expand/collapse
    const toggleExpand = (path: string) => {
        setExpandedPaths((prev) => {
            const newSet = new Set(prev);
            if (newSet.has(path)) {
                newSet.delete(path);
            } else {
                newSet.add(path);
            }
            return newSet;
        });
    };

    // Handle file selection
    const handleSelect = async (node: FileNode) => {
        if (node.type === 'file') {
            try {
                const response = await filesApi.getFileContent(projectId, node.path);
                onFileSelect(node.path, response.data.content || '');
            } catch (err) {
                console.error('Failed to fetch file content:', err);
                onFileSelect(node.path, '// Failed to load file content');
            }
        }
    };

    // Filter tree based on search
    const filterTree = (nodes: FileNode[], query: string): FileNode[] => {
        if (!query) return nodes;

        return nodes
            .map((node) => {
                if (node.type === 'directory' && node.children) {
                    const filteredChildren = filterTree(node.children, query);
                    if (filteredChildren.length > 0) {
                        return { ...node, children: filteredChildren };
                    }
                }
                if (node.name.toLowerCase().includes(query.toLowerCase())) {
                    return node;
                }
                return null;
            })
            .filter(Boolean) as FileNode[];
    };

    const filteredTree = filterTree(tree, searchQuery);

    // Loading state
    if (loading) {
        return (
            <div className="flex items-center justify-center h-full">
                <RefreshCw className="h-5 w-5 animate-spin text-[var(--color-text-secondary)]" />
            </div>
        );
    }

    // Error state
    if (error) {
        return (
            <div className="p-4 text-center">
                <p className="text-red-400 text-sm mb-2">{error}</p>
                <button
                    onClick={fetchTree}
                    className="text-sm text-[var(--color-primary)] hover:underline"
                >
                    Try again
                </button>
            </div>
        );
    }

    return (
        <div className="h-full flex flex-col">
            {/* Search */}
            <div className="p-2 border-b border-[var(--color-border)]">
                <div className="relative">
                    <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-4 w-4 text-[var(--color-text-secondary)]" />
                    <input
                        type="text"
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        placeholder="Search files..."
                        className="w-full pl-8 pr-3 py-1.5 bg-[var(--color-bg-elevated)] border border-[var(--color-border)] rounded text-sm text-[var(--color-text-primary)] placeholder-[var(--color-text-secondary)] focus:outline-none focus:ring-1 focus:ring-[var(--color-primary)]"
                    />
                </div>
            </div>

            {/* Tree */}
            <div className="flex-1 overflow-y-auto py-2">
                {filteredTree.length === 0 ? (
                    <div className="p-4 text-center text-[var(--color-text-secondary)] text-sm">
                        {searchQuery ? 'No files match your search' : 'No files found'}
                    </div>
                ) : (
                    filteredTree.map((node) => (
                        <TreeNode
                            key={node.path}
                            node={node}
                            depth={0}
                            onSelect={handleSelect}
                            selectedPath={selectedFile}
                            expandedPaths={expandedPaths}
                            toggleExpand={toggleExpand}
                        />
                    ))
                )}
            </div>

            {/* Refresh button */}
            <div className="p-2 border-t border-[var(--color-border)]">
                <button
                    onClick={fetchTree}
                    className="w-full flex items-center justify-center gap-2 px-3 py-1.5 text-sm text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-bg-elevated)] rounded transition-colors"
                >
                    <RefreshCw className="h-4 w-4" />
                    Refresh
                </button>
            </div>
        </div>
    );
}

export { getLanguageFromPath };