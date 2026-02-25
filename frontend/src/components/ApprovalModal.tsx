'use client';

import { useState } from 'react';

interface ApprovalModalProps {
    /** The draft content to display for review */
    pendingAction: Record<string, unknown>;
    /** Current conversation ID for the approval request */
    conversationId: string;
    /** Base URL for the agent API */
    agentUrl: string;
    /** Called with the approval result (status + response text) */
    onResult: (result: { status: string; response: string }) => void;
}

export default function ApprovalModal({
    pendingAction,
    conversationId,
    agentUrl,
    onResult,
}: ApprovalModalProps) {
    const [clinicianNote, setClinicianNote] = useState('');
    const [submitting, setSubmitting] = useState(false);

    const handleSubmit = async (approved: boolean) => {
        setSubmitting(true);
        try {
            const res = await fetch(`${agentUrl}/approve`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    conversation_id: conversationId,
                    approved,
                    clinician_note: clinicianNote,
                }),
            });
            if (!res.ok) {
                throw new Error(`Approval request failed: ${res.status}`);
            }
            const data = await res.json();
            onResult({ status: data.status, response: data.response });
        } catch (err) {
            onResult({
                status: 'error',
                response: err instanceof Error ? err.message : 'Approval request failed',
            });
        } finally {
            setSubmitting(false);
        }
    };

    const rawDraft = pendingAction.draft;
    const draft = typeof rawDraft === 'string' ? rawDraft : JSON.stringify(rawDraft ?? pendingAction, null, 2);
    const noteType = (pendingAction.note_type as string) || 'clinical note';

    return (
        <div className="border-2 border-amber-300 bg-amber-50 rounded-lg p-4 mb-3">
            <div className="flex items-center gap-2 mb-3">
                <span className="text-amber-600 text-lg">&#9888;</span>
                <h3 className="font-semibold text-amber-800">
                    Clinician Review Required
                </h3>
            </div>

            <p className="text-sm text-gray-600 mb-2">
                The agent drafted a <strong>{noteType}</strong> that requires your approval
                before it can be saved.
            </p>

            <div className="bg-white border border-gray-200 rounded p-3 mb-3 max-h-60 overflow-y-auto">
                <pre className="text-sm text-gray-800 whitespace-pre-wrap font-mono">
                    {draft}
                </pre>
            </div>

            <div className="mb-3">
                <label htmlFor="clinician-note" className="block text-sm font-medium text-gray-700 mb-1">
                    Clinician note (optional)
                </label>
                <textarea
                    id="clinician-note"
                    value={clinicianNote}
                    onChange={(e) => setClinicianNote(e.target.value)}
                    placeholder="Add context for approval or reason for rejection..."
                    className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-400"
                    rows={2}
                    disabled={submitting}
                />
            </div>

            <div className="flex gap-3">
                <button
                    onClick={() => handleSubmit(true)}
                    disabled={submitting}
                    className="px-4 py-2 bg-green-600 text-white rounded text-sm font-medium hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                    {submitting ? 'Processing...' : 'Approve'}
                </button>
                <button
                    onClick={() => handleSubmit(false)}
                    disabled={submitting}
                    className="px-4 py-2 bg-red-600 text-white rounded text-sm font-medium hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                    {submitting ? 'Processing...' : 'Reject'}
                </button>
            </div>
        </div>
    );
}
