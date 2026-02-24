import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
    title: 'AgentForge OpenEMR',
    description: 'Clinical AI Assistant for OpenEMR',
};

export default function RootLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    return (
        <html lang="en">
            <body>{children}</body>
        </html>
    );
}
