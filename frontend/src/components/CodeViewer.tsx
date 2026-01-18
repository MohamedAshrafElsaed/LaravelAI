'use client';

import {useEffect, useState} from 'react';
import Editor, {loader} from '@monaco-editor/react';
import {Check, Copy, Download, FileCode} from 'lucide-react';

interface CodeViewerProps {
    filePath: string | null;
    content: string;
    language?: string;
}

// Map file extensions to Monaco language IDs
function getLanguage(filePath: string): string {
    const ext = filePath.split('.').pop()?.toLowerCase();

    const languageMap: Record<string, string> = {
        php: 'php',
        blade: 'blade',
        js: 'javascript',
        jsx: 'javascript',
        ts: 'typescript',
        tsx: 'typescript',
        vue: 'html',
        html: 'html',
        css: 'css',
        scss: 'scss',
        sass: 'scss',
        less: 'less',
        json: 'json',
        yaml: 'yaml',
        yml: 'yaml',
        xml: 'xml',
        md: 'markdown',
        sql: 'sql',
        sh: 'shell',
        bash: 'shell',
        env: 'dotenv',
    };

    // Handle blade.php files
    if (filePath.includes('.blade.php')) {
        return 'blade';
    }

    return languageMap[ext || ''] || 'plaintext';
}

// Register Blade language for Monaco
function registerBladeLanguage(monaco: any) {
    // Check if already registered
    if (monaco.languages.getLanguages().some((lang: any) => lang.id === 'blade')) {
        return;
    }

    monaco.languages.register({id: 'blade'});

    monaco.languages.setMonarchTokensProvider('blade', {
        tokenizer: {
            root: [
                // Blade directives
                [/@(if|else|elseif|endif|foreach|endforeach|for|endfor|while|endwhile|forelse|empty|endforelse|switch|case|break|default|endswitch|include|extends|section|endsection|yield|show|parent|push|endpush|stack|prepend|endprepend|once|endonce|verbatim|endverbatim|php|endphp|isset|endisset|empty|endempty|auth|endauth|guest|endguest|production|endproduction|env|endenv|hasSection|sectionMissing|component|endcomponent|slot|endslot|props|aware|class|style|checked|selected|disabled|readonly|required)\b/, 'keyword'],

                // Blade echo
                [/\{\{--/, 'comment', '@bladeComment'],
                [/\{\{\{/, 'string', '@bladeRawEcho'],
                [/\{\{/, 'string', '@bladeEcho'],
                [/\{!!/, 'string', '@bladeUnescapedEcho'],

                // PHP tags
                [/<\?php/, 'keyword', '@php'],
                [/<\?=/, 'keyword', '@phpShort'],

                // HTML
                [/<\/?[\w\-]+/, 'tag'],
                [/[^<@{]+/, 'text'],
            ],

            bladeComment: [
                [/--\}\}/, 'comment', '@pop'],
                [/./, 'comment'],
            ],

            bladeEcho: [
                [/\}\}/, 'string', '@pop'],
                [/./, 'string'],
            ],

            bladeRawEcho: [
                [/\}\}\}/, 'string', '@pop'],
                [/./, 'string'],
            ],

            bladeUnescapedEcho: [
                [/!!\}/, 'string', '@pop'],
                [/./, 'string'],
            ],

            php: [
                [/\?>/, 'keyword', '@pop'],
                [/\$\w+/, 'variable'],
                [/"/, 'string', '@phpString'],
                [/'/, 'string', '@phpStringSingle'],
                [/[a-zA-Z_]\w*/, 'identifier'],
                [/[{}()\[\]]/, 'bracket'],
                [/[;,.]/, 'delimiter'],
            ],

            phpShort: [
                [/\?>/, 'keyword', '@pop'],
                [/./, 'string'],
            ],

            phpString: [
                [/"/, 'string', '@pop'],
                [/\\./, 'string.escape'],
                [/./, 'string'],
            ],

            phpStringSingle: [
                [/'/, 'string', '@pop'],
                [/\\./, 'string.escape'],
                [/./, 'string'],
            ],
        },
    });
}

export function CodeViewer({filePath, content, language: langOverride}: CodeViewerProps) {
    const [copied, setCopied] = useState(false);
    const [monacoReady, setMonacoReady] = useState(false);

    const language = langOverride || (filePath ? getLanguage(filePath) : 'plaintext');

    // Initialize Monaco with Blade language
    useEffect(() => {
        loader.init().then((monaco) => {
            registerBladeLanguage(monaco);
            setMonacoReady(true);
        });
    }, []);

    const handleCopy = async () => {
        await navigator.clipboard.writeText(content);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    const handleDownload = () => {
        const blob = new Blob([content], {type: 'text/plain'});
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filePath?.split('/').pop() || 'file.txt';
        a.click();
        URL.revokeObjectURL(url);
    };

    if (!filePath) {
        return (
            <div className="flex h-full items-center justify-center bg-gray-950 text-gray-500">
                <div className="text-center">
                    <FileCode className="mx-auto h-12 w-12 opacity-50"/>
                    <p className="mt-4">Select a file to view its content</p>
                </div>
            </div>
        );
    }

    return (
        <div className="flex h-full flex-col bg-gray-950">
            {/* Header */}
            <div className="flex items-center justify-between border-b border-gray-800 px-4 py-2">
                <div className="flex items-center gap-2">
                    <FileCode className="h-4 w-4 text-gray-400"/>
                    <span className="font-mono text-sm text-gray-300">{filePath}</span>
                    <span className="rounded bg-gray-800 px-1.5 py-0.5 text-xs text-gray-500">
            {language}
          </span>
                </div>

                <div className="flex items-center gap-2">
                    <button
                        onClick={handleCopy}
                        className="flex items-center gap-1 rounded px-2 py-1 text-sm text-gray-400 hover:bg-gray-800 hover:text-white"
                    >
                        {copied ? (
                            <>
                                <Check className="h-4 w-4 text-green-500"/>
                                Copied
                            </>
                        ) : (
                            <>
                                <Copy className="h-4 w-4"/>
                                Copy
                            </>
                        )}
                    </button>
                    <button
                        onClick={handleDownload}
                        className="flex items-center gap-1 rounded px-2 py-1 text-sm text-gray-400 hover:bg-gray-800 hover:text-white"
                    >
                        <Download className="h-4 w-4"/>
                        Download
                    </button>
                </div>
            </div>

            {/* Editor */}
            <div className="flex-1">
                {monacoReady && (
                    <Editor
                        height="100%"
                        language={language}
                        value={content}
                        theme="vs-dark"
                        options={{
                            readOnly: true,
                            minimap: {enabled: true},
                            fontSize: 13,
                            fontFamily: "'Fira Code', 'Cascadia Code', Consolas, monospace",
                            fontLigatures: true,
                            lineNumbers: 'on',
                            renderLineHighlight: 'line',
                            scrollBeyondLastLine: false,
                            wordWrap: 'on',
                            automaticLayout: true,
                            padding: {top: 12, bottom: 12},
                            scrollbar: {
                                verticalScrollbarSize: 10,
                                horizontalScrollbarSize: 10,
                            },
                        }}
                    />
                )}
            </div>
        </div>
    );
}
