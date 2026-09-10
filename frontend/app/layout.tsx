import type { Metadata } from 'next';
import { Inter, Space_Grotesk } from 'next/font/google';
import './globals.css';

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-sans',
});

const spaceGrotesk = Space_Grotesk({
  subsets: ['latin'],
  variable: '--font-disp',
});

export const metadata: Metadata = {
  title: 'AI-Triage | Asistente Inteligente de Voz',
  description: 'Clasificación médica automatizada en entornos hospitalarios.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es" className={`h-full ${inter.variable} ${spaceGrotesk.variable}`}>
      <body className="font-sans antialiased bg-slate-900 text-slate-200 h-full flex flex-col overflow-hidden" suppressHydrationWarning>
        {children}
      </body>
    </html>
  );
}
