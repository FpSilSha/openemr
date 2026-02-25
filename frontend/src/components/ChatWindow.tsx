'use client';

import { useState, useRef, useEffect } from 'react';
import ApprovalModal from './ApprovalModal';
import ChatInput from './ChatInput';
import ExpirationNotice from './ExpirationNotice';
import MessageBubble from './MessageBubble';
import PatientContext from './PatientContext';

interface ToolCall {
    name: string;
    args: Record<string, unknown>;
}

interface Message {
    role: 'user' | 'assistant';
    content: string;
    toolCalls?: ToolCall[];
}

const AGENT_URL = process.env.NEXT_PUBLIC_AGENT_URL || 'http://localhost:8000';

export default function ChatWindow() {
    const [messages, setMessages] = useState<Message[]>([]);
    const [patientUuid, setPatientUuid] = useState('');
    const [loading, setLoading] = useState(false);
    const [conversationId, setConversationId] = useState<string | null>(null);
    const [pendingApproval, setPendingApproval] = useState(false);
    const [pendingAction, setPendingAction] = useState<Record<string, unknown> | null>(null);
    const messagesEndRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages, pendingApproval]);

    const sendMessage = async (text: string) => {
        const userMsg: Message = { role: 'user', content: text };
        setMessages((prev) => [...prev, userMsg]);
        setLoading(true);

        try {
            const res = await fetch(`${AGENT_URL}/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: text,
                    patient_uuid: patientUuid || null,
                    conversation_id: conversationId,
                }),
            });

            if (!res.ok) {
                throw new Error(`Agent returned ${res.status}`);
            }

            const data = await res.json();
            setConversationId(data.conversation_id);

            if (data.pending_approval && data.pending_action) {
                setPendingApproval(true);
                setPendingAction(data.pending_action);
                // Add a status message so the user knows what happened
                const statusMsg: Message = {
                    role: 'assistant',
                    content: data.response || 'A draft has been created and requires your review before it can be saved.',
                    toolCalls: data.tool_calls,
                };
                setMessages((prev) => [...prev, statusMsg]);
            } else {
                const assistantMsg: Message = {
                    role: 'assistant',
                    content: data.response,
                    toolCalls: data.tool_calls,
                };
                setMessages((prev) => [...prev, assistantMsg]);
            }
        } catch (err) {
            const errorMsg: Message = {
                role: 'assistant',
                content: `Error: ${err instanceof Error ? err.message : 'Failed to reach agent'}`,
            };
            setMessages((prev) => [...prev, errorMsg]);
        } finally {
            setLoading(false);
        }
    };

    const handleApprovalResult = (result: { status: string; response: string }) => {
        setPendingApproval(false);
        setPendingAction(null);

        if (result.status === 'expired') {
            setMessages((prev) => [
                ...prev,
                { role: 'assistant', content: '' } as Message,
            ]);
            // We'll render ExpirationNotice inline — mark with a special flag
            // by using a sentinel content value
            setMessages((prev) => {
                const updated = [...prev];
                updated[updated.length - 1] = {
                    role: 'assistant',
                    content: '__EXPIRED__',
                };
                return updated;
            });
        } else {
            const msg: Message = {
                role: 'assistant',
                content: result.response || `Action ${result.status}.`,
            };
            setMessages((prev) => [...prev, msg]);
        }
    };

    return (
        <div className="flex flex-col h-screen max-w-4xl mx-auto">
            <header className="px-4 py-3 border-b bg-white">
                <h1 className="text-xl font-bold text-gray-800">AgentForge Clinical Assistant</h1>
                <p className="text-xs text-gray-500">OpenEMR AI-powered decision support</p>
            </header>

            <PatientContext patientUuid={patientUuid} onPatientUuidChange={setPatientUuid} />

            <div className="flex-1 overflow-y-auto p-4 bg-gray-100">
                {messages.length === 0 && (
                    <div className="text-center text-gray-400 mt-20">
                        <p className="text-lg">Welcome to AgentForge</p>
                        <p className="text-sm mt-1">
                            Enter a patient UUID above, then ask about their data.
                        </p>
                    </div>
                )}
                {messages.map((msg, i) =>
                    msg.content === '__EXPIRED__' ? (
                        <ExpirationNotice key={i} />
                    ) : (
                        <MessageBubble
                            key={i}
                            role={msg.role}
                            content={msg.content}
                            toolCalls={msg.toolCalls}
                        />
                    )
                )}
                {pendingApproval && pendingAction && conversationId && (
                    <ApprovalModal
                        pendingAction={pendingAction}
                        conversationId={conversationId}
                        agentUrl={AGENT_URL}
                        onResult={handleApprovalResult}
                    />
                )}
                {loading && (
                    <div className="flex justify-start mb-3">
                        <div className="bg-white border border-gray-200 rounded-lg px-4 py-2 text-gray-400 text-sm">
                            Thinking...
                        </div>
                    </div>
                )}
                <div ref={messagesEndRef} />
            </div>

            <ChatInput onSend={sendMessage} disabled={loading || pendingApproval} />
        </div>
    );
}
