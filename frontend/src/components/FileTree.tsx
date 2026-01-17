'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  ChevronRight,
  ChevronDown,
  Folder,
  FolderOpen,
  FileCode,
  FileText,
  File,
  Database,
  Settings,
  Layout,
  Search,
  RefreshCw,
} from 'lucide-react';
import { api } from '@/lib/api';

interface FileNode {
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

// Get icon based on file type
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

// Tree node component
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
        className={`flex cursor-pointer items-center gap-1 rounded px-2 py-1 text-sm hover:bg-gray-800 ${
          isSelected ? 'bg-blue-500/20 text-blue-400' : 'text-gray-300'
        }`}
        style={{ paddingLeft: `${depth * 12 + 8}px` }}
        onClick={handleClick}
      >
        {/* Expand/collapse icon for directories */}
        {isDirectory ? (
          <span className="w-4">
            {isExpanded ? (
              <ChevronDown className="h-4 w-4 text-gray-500" />
            ) : (
              <ChevronRight className="h-4 w-4 text-gray-500" />
            )}
          </span>
        ) : (
          <span className="w-4" />
        )}

        {/* File/folder icon */}
        {isDirectory ? (
          isExpanded ? (
            <FolderOpen className="h-4 w-4 text-yellow-500" />
          ) : (
            <Folder className="h-4 w-4 text-yellow-500" />
          )
        ) : (
          getFileIcon(node.name)
        )}

        {/* Name */}
        <span className="truncate">{node.name}</span>

        {/* Indexed indicator */}
        {node.indexed && (
          <span className="ml-auto h-2 w-2 rounded-full bg-green-500" title="Indexed" />
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

export function FileTree({ projectId, onFileSelect, selectedFile }: FileTreeProps) {
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
      const response = await api.get(`/projects/${projectId}/files`);
      setTree(response.data);

      // Auto-expand first level
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
        const response = await api.get(`/projects/${projectId}/files/${encodeURIComponent(node.path)}`);
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
      .filter((node): node is FileNode => node !== null);
  };

  const filteredTree = filterTree(tree, searchQuery);

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-full flex-col items-center justify-center p-4 text-center">
        <p className="text-sm text-red-400">{error}</p>
        <button
          onClick={fetchTree}
          className="mt-2 flex items-center gap-1 text-sm text-blue-400 hover:underline"
        >
          <RefreshCw className="h-4 w-4" />
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      {/* Search */}
      <div className="border-b border-gray-800 p-2">
        <div className="relative">
          <Search className="absolute left-2 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-500" />
          <input
            type="text"
            placeholder="Search files..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full rounded bg-gray-800 py-1.5 pl-8 pr-3 text-sm text-white placeholder-gray-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>
      </div>

      {/* Tree */}
      <div className="flex-1 overflow-y-auto py-2">
        {filteredTree.length === 0 ? (
          <div className="p-4 text-center text-sm text-gray-500">
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

      {/* Footer with stats */}
      <div className="border-t border-gray-800 px-3 py-2 text-xs text-gray-500">
        {tree.length > 0 && `${countFiles(tree)} files`}
      </div>
    </div>
  );
}

// Helper to count files
function countFiles(nodes: FileNode[]): number {
  let count = 0;
  for (const node of nodes) {
    if (node.type === 'file') {
      count++;
    } else if (node.children) {
      count += countFiles(node.children);
    }
  }
  return count;
}
