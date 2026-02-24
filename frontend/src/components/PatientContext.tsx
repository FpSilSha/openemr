'use client';

interface PatientContextProps {
    patientUuid: string;
    onPatientUuidChange: (uuid: string) => void;
}

export default function PatientContext({ patientUuid, onPatientUuidChange }: PatientContextProps) {
    return (
        <div className="flex items-center gap-2 px-4 py-2 bg-gray-50 border-b">
            <label htmlFor="patient-uuid" className="text-sm font-medium text-gray-600">
                Patient UUID:
            </label>
            <input
                id="patient-uuid"
                type="text"
                value={patientUuid}
                onChange={(e) => onPatientUuidChange(e.target.value)}
                placeholder="Enter patient UUID..."
                className="flex-1 max-w-md px-3 py-1 text-sm border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
        </div>
    );
}
