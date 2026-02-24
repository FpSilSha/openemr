'use client';

import { useState } from 'react';

interface ToolCallCardProps {
    name: string;
    args: Record<string, unknown>;
}

export default function ToolCallCard({ name, args }: ToolCallCardProps) {
    const [expanded, setExpanded] = useState(false);

    return (
        <div className="my-1 border rounded-md bg-gray-50 text-sm">
            <button
                onClick={() => setExpanded(!expanded)}
                className="w-full flex items-center justify-between px-3 py-1.5 text-left hover:bg-gray-100"
            >
                <span className="font-mono text-blue-700">{name}</span>
                <span className="text-gray-400 text-xs">{expanded ? '▲' : '▼'}</span>
            </button>
            {expanded && (
                <pre className="px-3 py-2 border-t text-xs overflow-x-auto bg-white">
                    {JSON.stringify(args, null, 2)}
                </pre>
            )}
        </div>
    );
}
