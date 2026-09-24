'use client';

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-slate-900 text-slate-100 p-4">
      <h1 className="text-3xl font-bold font-mono text-red-400 mb-2">Error del Sistema</h1>
      <p className="text-xs text-slate-400 mb-6 font-mono max-w-md text-center">
        {error.message || 'Se produjo un error inesperado en la interfaz clínica.'}
      </p>
      <button
        onClick={() => reset()}
        className="px-4 py-2 rounded bg-red-600 hover:bg-red-500 text-xs font-bold uppercase tracking-wider text-white transition-colors"
      >
        Reintentar
      </button>
    </div>
  );
}
