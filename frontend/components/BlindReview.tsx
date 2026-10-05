'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { EyeOff, RefreshCw, CheckCircle2, Inbox } from 'lucide-react';
import { toast } from 'sonner';
import { fetchWithAuth } from '@/lib/api';

interface BlindCase {
  id: number;
  date: string;
  gender: string;
  age: number | null;
  transcript: string;
}

const LEVELS = [
  { value: 1, roman: 'I', name: 'Resucitacion', color: 'border-red-500/50 text-red-300 hover:bg-red-500/15' },
  { value: 2, roman: 'II', name: 'Emergencia', color: 'border-orange-500/50 text-orange-300 hover:bg-orange-500/15' },
  { value: 3, roman: 'III', name: 'Urgencia', color: 'border-amber-500/50 text-amber-300 hover:bg-amber-500/15' },
  { value: 4, roman: 'IV', name: 'Urgencia Menor', color: 'border-emerald-500/50 text-emerald-300 hover:bg-emerald-500/15' },
  { value: 5, roman: 'V', name: 'No Urgente', color: 'border-blue-500/50 text-blue-300 hover:bg-blue-500/15' },
];

const GENDER_LABELS: Record<string, string> = { male: 'Masculino', female: 'Femenino', other: 'Otro' };

/**
 * Adjudicacion ciega: el clinico asigna un nivel de referencia viendo solo la transcripcion.
 * El backend nunca envia el nivel de la IA ni el del medico tratante a esta vista.
 */
export default function BlindReview() {
  const [cases, setCases] = useState<BlindCase[]>([]);
  const [pendingTotal, setPendingTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const loadQueue = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchWithAuth('/api/triage/sessions/blind_review_queue/');
      if (res.status === 403) {
        setError('Su perfil no tiene permiso para adjudicar niveles de triaje.');
        return;
      }
      if (!res.ok) {
        setError(`No se pudo cargar la cola de validacion (HTTP ${res.status}).`);
        return;
      }
      const data = await res.json();
      setCases(data.results || []);
      setPendingTotal(data.pending_total || 0);
      setSelected(null);
    } catch (err) {
      console.error('Error cargando cola de validacion ciega:', err);
      setError('No se pudo conectar con el servidor.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadQueue();
  }, [loadQueue]);

  const current = cases[0];

  const submit = async () => {
    if (!current || selected == null) return;
    setSubmitting(true);
    try {
      const res = await fetchWithAuth(`/api/triage/sessions/${current.id}/reference_level/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reference_level: selected }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        toast.error(data.error || `No se pudo registrar el nivel (HTTP ${res.status})`);
        if (res.status === 409) await loadQueue();
        return;
      }
      toast.success(`Nivel de referencia registrado para el caso #${current.id}`);
      setCases((prev) => prev.slice(1));
      setPendingTotal((prev) => Math.max(0, prev - 1));
      setSelected(null);
    } catch (err) {
      console.error('Error registrando nivel de referencia:', err);
      toast.error('No se pudo conectar con el servidor.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex flex-col h-full w-full bg-slate-900 border border-slate-800 rounded-xl p-4 md:p-6 overflow-y-auto space-y-5">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div className="flex items-center gap-3">
          <div className="p-2.5 bg-indigo-500/10 rounded-xl border border-indigo-500/20 text-indigo-400">
            <EyeOff className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-slate-100">Validación Ciega de Triaje</h1>
            <p className="text-xs text-slate-400">
              Asigne el nivel según su criterio clínico. No se muestra la propuesta de la IA ni el nivel del médico tratante.
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-[11px] font-mono px-2 py-1 rounded bg-slate-800 text-slate-300 border border-slate-700">
            {pendingTotal} pendientes
          </span>
          <button
            onClick={loadQueue}
            disabled={loading}
            className="flex items-center gap-2 px-3.5 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-xs font-semibold border border-slate-700 transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            Actualizar
          </button>
        </div>
      </div>

      {loading ? (
        <p className="text-xs font-mono uppercase tracking-widest text-slate-400">Cargando casos...</p>
      ) : error ? (
        <p role="alert" className="text-sm text-amber-300">{error}</p>
      ) : !current ? (
        <div className="flex flex-col items-center justify-center gap-2 py-16 text-slate-400">
          <Inbox className="w-8 h-8" />
          <p className="text-sm">No hay casos pendientes de adjudicación.</p>
        </div>
      ) : (
        <div className="space-y-5">
          <div className="flex flex-wrap gap-2 text-[11px] font-mono text-slate-300">
            <span className="px-2 py-1 rounded bg-slate-800 border border-slate-700">Caso #{current.id}</span>
            <span className="px-2 py-1 rounded bg-slate-800 border border-slate-700">{current.date}</span>
            <span className="px-2 py-1 rounded bg-slate-800 border border-slate-700">
              {GENDER_LABELS[current.gender] || 'Sexo no registrado'}
            </span>
            <span className="px-2 py-1 rounded bg-slate-800 border border-slate-700">
              {current.age != null ? `${current.age} años` : 'Edad no registrada'}
            </span>
          </div>

          <div className="bg-slate-950/70 border border-slate-800 rounded-xl p-4">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">Transcripción de la consulta</h2>
            <p className="text-sm text-slate-200 whitespace-pre-wrap leading-relaxed">
              {current.transcript || 'Sin transcripción registrada.'}
            </p>
          </div>

          <fieldset>
            <legend className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">Nivel de referencia</legend>
            <div className="grid grid-cols-1 sm:grid-cols-5 gap-2">
              {LEVELS.map((lvl) => (
                <button
                  key={lvl.value}
                  type="button"
                  aria-pressed={selected === lvl.value}
                  onClick={() => setSelected(lvl.value)}
                  className={`flex flex-col items-center gap-0.5 px-3 py-3 rounded-lg border bg-slate-950/50 transition-colors ${lvl.color} ${
                    selected === lvl.value ? 'ring-2 ring-offset-2 ring-offset-slate-900 ring-indigo-400' : ''
                  }`}
                >
                  <span className="text-lg font-black font-mono">{lvl.roman}</span>
                  <span className="text-[11px]">{lvl.name}</span>
                </button>
              ))}
            </div>
          </fieldset>

          <button
            onClick={submit}
            disabled={selected == null || submitting}
            className="flex items-center gap-2 px-4 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:bg-slate-700 disabled:text-slate-400 text-white rounded-lg text-sm font-semibold transition-colors"
          >
            <CheckCircle2 className="w-4 h-4" />
            {submitting ? 'Registrando...' : 'Registrar nivel de referencia'}
          </button>
          <p className="text-[11px] text-slate-400">El nivel registrado es definitivo y queda en la auditoría.</p>
        </div>
      )}
    </div>
  );
}
