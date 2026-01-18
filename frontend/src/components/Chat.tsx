'use client';

import {useRef} from 'react';
import {Plus, Sparkles} from 'lucide-react';
import {InteractiveChat, type InteractiveChatRef} from './interactive/agent';
import {Button} from '@/components/ui/Button';

interface ChatProps {
    projectId: string;
    onProcessingEvent?: (event: any) => void;
    onConversationChange?: (conversationId: string | null) => void;
}

export function Chat({
                         projectId,
                         onConversationChange,
                     }: ChatProps) {
    const chatRef = useRef<InteractiveChatRef>(null);

    const handleNewChat = () => {
        chatRef.current?.startNewChat();
    };

    return (
        <div className="flex h-full flex-col bg-gray-950">
            {/* Header */}
            <div className="flex items-center justify-between border-b border-gray-800 px-4 py-2">
                <div className="flex items-center gap-2">
          <span
              className="flex items-center gap-1.5 px-2 py-1 rounded-lg bg-gradient-to-r from-purple-500/20 to-blue-500/20 text-purple-400 text-sm">
            <Sparkles className="h-4 w-4"/>
            <span className="hidden sm:inline">Multi-Agent Mode</span>
          </span>
                </div>
                <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleNewChat}
                    className="flex items-center gap-1.5 text-gray-400 hover:text-white"
                >
                    <Plus className="h-4 w-4"/>
                    <span className="hidden sm:inline">New Chat</span>
                </Button>
            </div>

            {/* Interactive Chat Component */}
            <div className="flex-1 overflow-hidden">
                <InteractiveChat
                    ref={chatRef}
                    projectId={projectId}
                    onConversationChange={onConversationChange}
                />
            </div>
        </div>
    );
}

export default Chat;
