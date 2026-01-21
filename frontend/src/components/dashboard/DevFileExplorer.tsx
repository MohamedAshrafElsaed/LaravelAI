'use client';

import {useCallback, useEffect, useState} from 'react';
import {
    AlertCircle,
    ChevronDown,
    ChevronRight,
    Database,
    File,
    FileCode,
    FileText,
    Folder,
    FolderOpen,
    FolderTree,
    Layout,
    RefreshCw,
    Search,
    Settings,
} from 'lucide-react';
import {FileNode, filesApi} from '@/lib/api';

// ============== HELPERS ==============
const getFileIcon = (fileName: string) => {
    const ext = fileName.split('.').pop()?.toLowerCase();
    switch (ext) {
        case 'php':
            return <FileCode className="h-4 w-4 text-purple-400"/>;
        case 'blade':
            return <Layout className="h-4 w-4 text-orange-400"/>;
        case 'vue':
        case 'jsx':
        case 'tsx':
            return <FileCode className="h-4 w-4 text-green-400"/>;
        case 'js':
        case 'ts':
            return <FileCode className="h-4 w-4 text-yellow-400"/>;
        case 'css':
        case 'scss':
            return <FileText className="h-4 w-4 text-blue-400"/>;
        case 'json':
        case 'yaml':
        case 'yml':
            return <Settings className="h-4 w-4 text-gray-400"/>;
        case 'sql':
            return <Database className="h-4 w-4 text-cyan-400"/>;
        case 'md':
            return <FileText className="h-4 w-4 text-gray-400"/>;
        default:
            return <File className="h-4 w-4 text-gray-400"/>;
    }
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

    return (
        <div>
            <div
                className={`flex items-center gap-1 px-2 py-1 cursor-pointer rounded text-sm transition-colors ${
                    isSelected
                        ? 'bg-[var(--color-primary)]/20 text-[var(--color-primary)]'
                        : 'text-[var(--color-text-muted)] hover:bg-[var(--color-bg-hover)]'
                }`}
                style={{paddingLeft: `${depth * 12 + 8}px`}}
                onClick={() => isDirectory ? toggleExpand(node.path) : onSelect(node)}
            >
                {isDirectory ? (
                    <span className="w-4">
                        {isExpanded ? <ChevronDown className="h-4 w-4"/> : <ChevronRight className="h-4 w-4"/>}
                    </span>
                ) : <span className="w-4"/>}

                {isDirectory ? (
                    isExpanded ? <FolderOpen className="h-4 w-4 text-yellow-500"/> :
                        <Folder className="h-4 w-4 text-yellow-500"/>
                ) : getFileIcon(node.name)}

                <span className="truncate flex-1">{node.name}</span>

                {node.indexed && (
                    <span className="h-2 w-2 rounded-full bg-green-500" title="Indexed"/>
                )}
            </div>

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

// ============== MAIN FILE EXPLORER COMPONENT ==============
interface FileExplorerProps {
    projectId?: string;
    // ✅ NEW: Callback when file is selected
    onFileSelect?: (filePath: string, content: string) => void;
    // ✅ NEW: Currently selected file (controlled from parent)
    selectedFile?: string | null;
}

export default function DevFileExplorer({
                                            projectId,
                                            onFileSelect,
                                            selectedFile: externalSelectedFile
                                        }: FileExplorerProps) {
    // Tree state
    const [tree, setTree] = useState<FileNode[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [searchQuery, setSearchQuery] = useState('');
    const [expandedPaths, setExpandedPaths] = useState<Set<string>>(new Set());

    // Internal selected file state (used if no external control)
    const [internalSelectedFile, setInternalSelectedFile] = useState<string | null>(null);

    // Use external or internal selected file
    const selectedFile = externalSelectedFile !== undefined ? externalSelectedFile : internalSelectedFile;

    // Debug: Log projectId
    useEffect(() => {
        console.log('[DevFileExplorer] Mounted with projectId:', projectId);
    }, [projectId]);

    // Fetch file tree
    const fetchTree = useCallback(async () => {
        if (!projectId) {
            console.error('[DevFileExplorer] No projectId provided!');
            setError('No project selected');
            setLoading(false);
            return;
        }

        console.log('[DevFileExplorer] Fetching tree for projectId:', projectId);
        setLoading(true);
        setError(null);

        try {
            const response = await filesApi.getFileTree(projectId);
            console.log('[DevFileExplorer] API Response:', response.data);

            if (response.data && Array.isArray(response.data)) {
                setTree(response.data);
                console.log('[DevFileExplorer] Tree loaded with', response.data.length, 'root items');

                // Auto-expand first level
                const firstLevel = new Set<string>();
                response.data.forEach((node: FileNode) => {
                    if (node.type === 'directory') {
                        firstLevel.add(node.path);
                    }
                });
                setExpandedPaths(firstLevel);
            } else {
                console.warn('[DevFileExplorer] Unexpected response format:', response.data);
                setTree([]);
            }
        } catch (err: any) {
            console.error('[DevFileExplorer] Failed to fetch file tree:', err);
            console.error('[DevFileExplorer] Error details:', err.response?.data);
            setError(err.response?.data?.detail || err.message || 'Failed to load files');
        } finally {
            setLoading(false);
        }
    }, [projectId]);

    useEffect(() => {
        if (projectId) {
            fetchTree();
        }
    }, [fetchTree, projectId]);

    // Toggle directory expand/collapse
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
    const handleFileSelect = async (node: FileNode) => {
        if (node.type !== 'file' || !projectId) return;

        console.log('[DevFileExplorer] Selecting file:', node.path);

        // Update internal state
        setInternalSelectedFile(node.path);

        try {
            const response = await filesApi.getFileContent(projectId, node.path);
            const content = response.data.content || '';
            console.log('[DevFileExplorer] File content loaded, length:', content.length);

            // ✅ Call parent callback if provided
            if (onFileSelect) {
                onFileSelect(node.path, content);
            }
        } catch (err: any) {
            console.error('[DevFileExplorer] Failed to fetch file content:', err);
            const errorContent = '// Failed to load file content\n// Error: ' + (err.message || 'Unknown error');

            if (onFileSelect) {
                onFileSelect(node.path, errorContent);
            }
        }
    };

    // Filter tree based on search
    const filterTree = (nodes: FileNode[], query: string): FileNode[] => {
        if (!query) return nodes;
        return nodes
            .map((node) => {
                if (node.type === 'directory' && node.children) {
                    const filtered = filterTree(node.children, query);
                    if (filtered.length > 0) return {...node, children: filtered};
                }
                if (node.name.toLowerCase().includes(query.toLowerCase())) return node;
                return null;
            })
            .filter(Boolean) as FileNode[];
    };

    const filteredTree = filterTree(tree, searchQuery);

    // No projectId state
    if (!projectId) {
        return (
            <div className="flex flex-col items-center justify-center h-full p-4">
                <AlertCircle className="h-8 w-8 text-yellow-500 mb-2"/>
                <p className="text-sm text-[var(--color-text-muted)] text-center">
                    Select a project to view files
                </p>
            </div>
        );
    }

    // Loading state
    if (loading) {
        return (
            <div className="flex flex-col items-center justify-center h-full">
                <RefreshCw className="h-6 w-6 animate-spin text-[var(--color-text-muted)]"/>
                <span className="mt-2 text-sm text-[var(--color-text-muted)]">Loading files...</span>
            </div>
        );
    }

    // Error state
    if (error) {
        return (
            <div className="flex flex-col items-center justify-center h-full p-4">
                <AlertCircle className="h-8 w-8 text-red-400 mb-2"/>
                <p className="text-sm text-red-400 text-center mb-2">{error}</p>
                <button
                    onClick={fetchTree}
                    className="text-xs text-[var(--color-primary)] hover:underline"
                >
                    Try Again
                </button>
            </div>
        );
    }

    return (
        <div className="h-full flex flex-col bg-[var(--color-bg-primary)]">
            {/* Header */}
            <div className="h-10 flex items-center justify-between px-3 border-b border-[var(--color-border-subtle)]">
                <div className="flex items-center gap-2">
                    <FolderTree className="h-4 w-4 text-[var(--color-text-muted)]"/>
                    <span className="text-xs font-semibold text-[var(--color-text-muted)] uppercase tracking-wider">
                        Explorer
                    </span>
                </div>
                <button
                    onClick={fetchTree}
                    className="p-1 hover:bg-[var(--color-bg-hover)] rounded"
                    title="Refresh"
                >
                    <RefreshCw className="h-3.5 w-3.5 text-[var(--color-text-muted)]"/>
                </button>
            </div>

            {/* Search */}
            <div className="p-2 border-b border-[var(--color-border-subtle)]">
                <div className="relative">
                    <Search
                        className="absolute left-2 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-[var(--color-text-dimmer)]"/>
                    <input
                        type="text"
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        placeholder="Search files..."
                        className="w-full pl-7 pr-3 py-1.5 bg-[var(--color-bg-surface)] border border-[var(--color-border-subtle)] rounded text-xs text-[var(--color-text-primary)] placeholder-[var(--color-text-dimmer)] focus:outline-none focus:ring-1 focus:ring-[var(--color-primary)]"
                    />
                </div>
            </div>

            {/* Tree */}
            <div className="flex-1 overflow-y-auto py-1">
                {filteredTree.length === 0 ? (
                    <div className="p-4 text-center text-[var(--color-text-muted)] text-xs">
                        {searchQuery ? 'No files match' : 'No files found. Make sure the project is cloned.'}
                    </div>
                ) : (
                    filteredTree.map((node) => (
                        <TreeNode
                            key={node.path}
                            node={node}
                            depth={0}
                            onSelect={handleFileSelect}
                            selectedPath={selectedFile}
                            expandedPaths={expandedPaths}
                            toggleExpand={toggleExpand}
                        />
                    ))
                )}
            </div>

            {/* Footer */}
            <div
                className="px-3 py-2 border-t border-[var(--color-border-subtle)] text-[10px] text-[var(--color-text-dimmer)]">
                {tree.length > 0 ? `${tree.length} root items` : 'No files'}
            </div>
        </div>
    );
}