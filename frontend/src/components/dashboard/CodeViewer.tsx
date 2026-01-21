'use client';

import {useEffect, useRef, useState} from 'react';
import {Check, Copy, Download, FileCode, X} from 'lucide-react';
import Prism from 'prismjs';

// Import Prism theme (dark theme)
import 'prismjs/themes/prism-tomorrow.css';

// Import language support
import 'prismjs/components/prism-php';
import 'prismjs/components/prism-markup-templating';
import 'prismjs/components/prism-javascript';
import 'prismjs/components/prism-typescript';
import 'prismjs/components/prism-jsx';
import 'prismjs/components/prism-tsx';
import 'prismjs/components/prism-json';
import 'prismjs/components/prism-css';
import 'prismjs/components/prism-scss';
import 'prismjs/components/prism-sass';
import 'prismjs/components/prism-yaml';
import 'prismjs/components/prism-sql';
import 'prismjs/components/prism-markdown';
import 'prismjs/components/prism-bash';
import 'prismjs/components/prism-shell-session';
import 'prismjs/components/prism-diff';
import 'prismjs/components/prism-git';
import 'prismjs/components/prism-graphql';
import 'prismjs/components/prism-docker';
import 'prismjs/components/prism-nginx';
import 'prismjs/components/prism-apacheconf';

// Import plugins
import 'prismjs/plugins/line-numbers/prism-line-numbers.css';
import 'prismjs/plugins/line-highlight/prism-line-highlight.css';

// ============== TYPES ==============
interface CodeViewerProps {
    filePath: string;
    content: string;
    language?: string;
    onClose?: () => void;
    highlightLines?: number[]; // Optional: lines to highlight
    showLineNumbers?: boolean;
    maxHeight?: string;
}

// ============== LANGUAGE MAPPING ==============
const getLanguageClass = (language: string): string => {
    const langMap: Record<string, string> = {
        php: 'language-php',
        javascript: 'language-javascript',
        js: 'language-javascript',
        typescript: 'language-typescript',
        ts: 'language-typescript',
        jsx: 'language-jsx',
        tsx: 'language-tsx',
        json: 'language-json',
        css: 'language-css',
        scss: 'language-scss',
        sass: 'language-sass',
        yaml: 'language-yaml',
        yml: 'language-yaml',
        sql: 'language-sql',
        markdown: 'language-markdown',
        md: 'language-markdown',
        bash: 'language-bash',
        sh: 'language-bash',
        shell: 'language-shell-session',
        diff: 'language-diff',
        git: 'language-git',
        graphql: 'language-graphql',
        gql: 'language-graphql',
        dockerfile: 'language-docker',
        docker: 'language-docker',
        nginx: 'language-nginx',
        apache: 'language-apacheconf',
        htaccess: 'language-apacheconf',
        html: 'language-markup',
        xml: 'language-markup',
        svg: 'language-markup',
        vue: 'language-markup',
        blade: 'language-php',
        env: 'language-bash',
        plaintext: 'language-plaintext',
    };

    return langMap[language.toLowerCase()] || 'language-plaintext';
};

const getLanguageFromPath = (path: string): string => {
    const ext = path.split('.').pop()?.toLowerCase() || '';
    const fileName = path.split('/').pop()?.toLowerCase() || '';

    // Special file names
    if (fileName === 'dockerfile') return 'docker';
    if (fileName === '.env' || fileName.startsWith('.env.')) return 'env';
    if (fileName === '.htaccess') return 'htaccess';
    if (fileName === 'nginx.conf') return 'nginx';

    // Extension mapping
    const extMap: Record<string, string> = {
        php: 'php',
        js: 'javascript',
        mjs: 'javascript',
        cjs: 'javascript',
        ts: 'typescript',
        mts: 'typescript',
        cts: 'typescript',
        jsx: 'jsx',
        tsx: 'tsx',
        json: 'json',
        css: 'css',
        scss: 'scss',
        sass: 'sass',
        less: 'css',
        yaml: 'yaml',
        yml: 'yaml',
        sql: 'sql',
        md: 'markdown',
        markdown: 'markdown',
        sh: 'bash',
        bash: 'bash',
        zsh: 'bash',
        diff: 'diff',
        patch: 'diff',
        graphql: 'graphql',
        gql: 'graphql',
        html: 'html',
        htm: 'html',
        xml: 'xml',
        svg: 'svg',
        vue: 'vue',
        blade: 'blade',
        env: 'env',
    };

    return extMap[ext] || 'plaintext';
};

// ============== COMPONENT ==============
export default function CodeViewer({
                                       filePath,
                                       content,
                                       language,
                                       onClose,
                                       highlightLines = [],
                                       showLineNumbers = true,
                                       maxHeight,
                                   }: CodeViewerProps) {
    const [copied, setCopied] = useState(false);
    const codeRef = useRef<HTMLElement>(null);
    const preRef = useRef<HTMLPreElement>(null);

    // Determine language from prop or file path
    const detectedLanguage = language || getLanguageFromPath(filePath);
    const languageClass = getLanguageClass(detectedLanguage);

    // File info
    const fileName = filePath.split('/').pop() || filePath;
    const lines = content.split('\n');
    const fileSize = (content.length / 1024).toFixed(1);

    // Apply Prism highlighting
    useEffect(() => {
        if (codeRef.current) {
            Prism.highlightElement(codeRef.current);
        }
    }, [content, detectedLanguage]);

    // Copy to clipboard
    const handleCopy = async () => {
        try {
            await navigator.clipboard.writeText(content);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        } catch (err) {
            console.error('Failed to copy:', err);
        }
    };

    // Download file
    const handleDownload = () => {
        const blob = new Blob([content], {type: 'text/plain'});
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = fileName;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    };

    // Build line highlight data attribute
    const lineHighlightAttr = highlightLines.length > 0
        ? highlightLines.join(',')
        : undefined;

    return (
        <div className="h-full flex flex-col bg-[var(--color-bg-primary)] code-viewer">
            {/* Header */}
            <div
                className="flex items-center justify-between px-4 py-2 bg-[var(--color-bg-surface)] border-b border-[var(--color-border)]">
                <div className="flex items-center gap-2 min-w-0">
                    <FileCode className="h-4 w-4 text-[var(--color-text-secondary)] flex-shrink-0"/>
                    <span className="text-sm font-medium text-[var(--color-text-primary)] truncate">
            {fileName}
          </span>
                    <span className="text-xs text-[var(--color-text-secondary)] truncate hidden sm:inline">
            {filePath !== fileName && filePath}
          </span>
                </div>
                <div className="flex items-center gap-1">
                    {/* Language badge */}
                    <span
                        className="px-2 py-0.5 text-xs bg-[var(--color-bg-elevated)] text-[var(--color-text-secondary)] rounded">
            {detectedLanguage}
          </span>

                    {/* Download button */}
                    <button
                        onClick={handleDownload}
                        className="p-1.5 hover:bg-[var(--color-bg-elevated)] rounded transition-colors"
                        title="Download file"
                    >
                        <Download className="h-4 w-4 text-[var(--color-text-secondary)]"/>
                    </button>

                    {/* Copy button */}
                    <button
                        onClick={handleCopy}
                        className="p-1.5 hover:bg-[var(--color-bg-elevated)] rounded transition-colors"
                        title="Copy code"
                    >
                        {copied ? (
                            <Check className="h-4 w-4 text-green-400"/>
                        ) : (
                            <Copy className="h-4 w-4 text-[var(--color-text-secondary)]"/>
                        )}
                    </button>

                    {/* Close button */}
                    {onClose && (
                        <button
                            onClick={onClose}
                            className="p-1.5 hover:bg-[var(--color-bg-elevated)] rounded transition-colors"
                            title="Close"
                        >
                            <X className="h-4 w-4 text-[var(--color-text-secondary)]"/>
                        </button>
                    )}
                </div>
            </div>

            {/* Code content */}
            <div
                className="flex-1 overflow-auto"
                style={{maxHeight: maxHeight}}
            >
                <div className="flex min-h-full">
                    {/* Line numbers (custom implementation for better control) */}
                    {showLineNumbers && (
                        <div
                            className="flex-shrink-0 py-4 pr-2 pl-4 bg-[var(--color-bg-surface)] border-r border-[var(--color-border)] select-none sticky left-0">
                            {lines.map((_, i) => {
                                const lineNum = i + 1;
                                const isHighlighted = highlightLines.includes(lineNum);
                                return (
                                    <div
                                        key={i}
                                        className={`text-right text-xs font-mono leading-6 px-2 ${
                                            isHighlighted
                                                ? 'text-[var(--color-primary)] bg-[var(--color-primary)]/10'
                                                : 'text-[var(--color-text-secondary)]'
                                        }`}
                                    >
                                        {lineNum}
                                    </div>
                                );
                            })}
                        </div>
                    )}

                    {/* Code */}
                    <pre
                        ref={preRef}
                        className={`flex-1 p-4 overflow-x-auto m-0 bg-transparent ${showLineNumbers ? '' : 'pl-4'}`}
                        data-line={lineHighlightAttr}
                        style={{background: 'transparent'}}
                    >
            <code
                ref={codeRef}
                className={`${languageClass} text-sm leading-6 font-mono`}
                style={{background: 'transparent'}}
            >
              {content}
            </code>
          </pre>
                </div>
            </div>

            {/* Footer with stats */}
            <div
                className="flex items-center justify-between px-4 py-2 bg-[var(--color-bg-surface)] border-t border-[var(--color-border)] text-xs text-[var(--color-text-secondary)]">
                <div className="flex items-center gap-4">
                    <span>{lines.length} lines</span>
                    <span>{fileSize} KB</span>
                </div>
                <div className="flex items-center gap-2">
                    <span>UTF-8</span>
                    <span>•</span>
                    <span>{detectedLanguage.toUpperCase()}</span>
                </div>
            </div>
        </div>
    );
}

// Export helper function
export {getLanguageFromPath};