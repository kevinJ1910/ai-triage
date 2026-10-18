import type { Metadata } from 'next';
import { Inter, Space_Grotesk } from 'next/font/google';
import './globals.css';
import { THEME_INIT_SCRIPT } from '@/lib/theme-script';

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-sans',
  display: 'swap',
});

const spaceGrotesk = Space_Grotesk({
  subsets: ['latin'],
  variable: '--font-disp',
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'AI-Triage | Asistente Inteligente de Voz',
  description: 'Clasificación médica automatizada en entornos hospitalarios.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    // suppressHydrationWarning: el script de tema fija data-theme en <html> antes de hidratar.
    <html lang="es" className={`h-full ${inter.variable} ${spaceGrotesk.variable}`} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
      </head>
      <body className="font-sans antialiased bg-slate-900 text-slate-200 h-full flex flex-col overflow-hidden" suppressHydrationWarning>
        {children}
      </body>
    </html>
  );
}
