'use client';

import Link from 'next/link';

export default function NotFound() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-slate-900 text-slate-100 p-4">
      <h1 className="text-4xl font-bold font-mono text-blue-400 mb-2">404</h1>
      <p className="text-sm text-slate-400 mb-6 font-mono uppercase tracking-widest">Página No Encontrada</p>
      <Link
        href="/"
        className="px-4 py-2 rounded bg-blue-600 hover:bg-blue-500 text-xs font-bold uppercase tracking-wider text-white transition-colors"
      >
        Volver al Inicio
      </Link>
    </div>
  );
}
