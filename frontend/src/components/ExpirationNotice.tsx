'use client';

interface ExpirationNoticeProps {
    /** Number of hours after which drafts expire */
    ttlHours?: number;
}

export default function ExpirationNotice({ ttlHours = 24 }: ExpirationNoticeProps) {
    return (
        <div className="border border-amber-300 bg-amber-50 rounded-lg p-3 mb-3">
            <div className="flex items-start gap-2">
                <span className="text-amber-500 text-base mt-0.5">&#128336;</span>
                <div>
                    <p className="text-sm font-medium text-amber-800">
                        Draft Expired
                    </p>
                    <p className="text-sm text-amber-700 mt-1">
                        This draft expired after {ttlHours} hours for patient safety.
                        Patient data may have changed since the draft was created.
                        Please request a new draft.
                    </p>
                </div>
            </div>
        </div>
    );
}
