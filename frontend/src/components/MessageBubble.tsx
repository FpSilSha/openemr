'use client';

import ReactMarkdown from 'react-markdown';
import ToolCallCard from './ToolCallCard';

interface ToolCall {
    name: string;
    args: Record<string, unknown>;
}

interface MessageBubbleProps {
    role: 'user' | 'assistant';
    content: string;
    toolCalls?: ToolCall[];
}

export default function MessageBubble({ role, content, toolCalls }: MessageBubbleProps) {
    const isUser = role === 'user';

    return (
        <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-3`}>
            <div
                className={`max-w-[80%] rounded-lg px-4 py-2 ${
                    isUser
                        ? 'bg-blue-600 text-white'
                        : 'bg-white border border-gray-200 text-gray-800'
                }`}
            >
                {toolCalls && toolCalls.length > 0 && (
                    <div className="mb-2">
                        {toolCalls.map((tc, i) => (
                            <ToolCallCard key={i} name={tc.name} args={tc.args} />
                        ))}
                    </div>
                )}
                <div className={`prose prose-sm max-w-none ${isUser ? 'prose-invert' : ''}`}>
                    <ReactMarkdown>{content}</ReactMarkdown>
                </div>
            </div>
        </div>
    );
}
