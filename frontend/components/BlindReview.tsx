'use client';

import React, { useState, useEffect, useCallback } from 'react';
import {
  EyeOff,
  RefreshCw,
  CheckCircle2,
  ShieldCheck,
  Clock,
  FileText,
  ChevronRight,
  ChevronLeft,
  AlertCircle,
  HelpCircle,
  History,
  Check,
  Star,
} from 'lucide-react';
import { toast } from 'sonner';
import { fetchWithAuth } from '@/lib/api';

interface BlindCase {
  id: number;
  date: string;
  gender: string;
  age: number | null;
  transcript: string;
}

interface AdjudicatedRecord {
  id: number;
  date: string;
  level: number;
  levelName: string;
  timestamp: string;
}

const LEVELS = [
  {
    value: 1,
    roman: 'I',
    name: 'Resucitacion',
    desc: 'Riesgo vital inmediato, compromiso severo de via aerea o shock.',
    color: 'border-red-500/40 text-red-300 hover:bg-red-500/10 hover:border-red-500/60',
    selectedStyle: 'ring-2 ring-red-400 bg-red-950/40 border-red-500',
  },
  {
    value: 2,
    roman: 'II',
    name: 'Emergencia',
    desc: 'Alto riesgo de deterioro rapido, dolor severo o alteracion neurologica aguda.',
    color: 'border-orange-500/40 text-orange-300 hover:bg-orange-500/10 hover:border-orange-500/60',
    selectedStyle: 'ring-2 ring-orange-400 bg-orange-950/40 border-orange-500',
  },
  {
    value: 3,
    roman: 'III',
    name: 'Urgencia',
    desc: 'Condicion estable que requiere multiples recursos diagnosticos o terapeuticos.',
    color: 'border-amber-500/40 text-amber-300 hover:bg-amber-500/10 hover:border-amber-500/60',
    selectedStyle: 'ring-2 ring-amber-400 bg-amber-950/40 border-amber-500',
  },
  {
    value: 4,
    roman: 'IV',
    name: 'Urgencia Menor',
    desc: 'Condicion subaguda o sintomatologia leve que requiere un recurso simple.',
    color: 'border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/10 hover:border-emerald-500/60',
    selectedStyle: 'ring-2 ring-emerald-400 bg-emerald-950/40 border-emerald-500',
  },
  {
    value: 5,
    roman: 'V',
    name: 'No Urgente',
    desc: 'Condicion cronica o administrativa, sin requerimiento de recursos agudos.',
    color: 'border-sky-500/40 text-sky-300 hover:bg-sky-500/10 hover:border-sky-500/60',
    selectedStyle: 'ring-2 ring-sky-400 bg-sky-950/40 border-sky-500',
  },
];

const GENDER_LABELS: Record<string, string> = { male: 'Masculino', female: 'Femenino', other: 'Otro' };

type RatingKey = 'clarity' | 'relevance' | 'fidelity';

const RATING_ITEMS: { key: RatingKey; label: string; help: string }[] = [
  { key: 'clarity', label: 'Claridad', help: 'Se entiende sin ambigüedad por qué se asignó el nivel.' },
  { key: 'relevance', label: 'Pertinencia clínica', help: 'Los hallazgos citados son los que importan para el triaje.' },
  { key: 'fidelity', label: 'Fidelidad al protocolo', help: 'El razonamiento sigue los criterios Christus Sinergia / Res. 5596.' },
];

const EMPTY_SCORES: Record<RatingKey, number | null> = { clarity: null, relevance: null, fidelity: null };

interface PendingRating {
  id: number;
  justification: string;
}

/**
 * Adjudicacion ciega: el clinico asigna un nivel de referencia viendo solo la transcripcion.
 * El backend nunca envia el nivel de la IA ni el del medico tratante a esta vista.
 */
export default function BlindReview() {
  const [cases, setCases] = useState<BlindCase[]>([]);
  const [pendingTotal, setPendingTotal] = useState(0);
  const [adjudicatedTotal, setAdjudicatedTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [showGuidelines, setShowGuidelines] = useState(false);
  const [sessionHistory, setSessionHistory] = useState<AdjudicatedRecord[]>([]);
  const [pendingRating, setPendingRating] = useState<PendingRating | null>(null);
  const [scores, setScores] = useState<Record<RatingKey, number | null>>(EMPTY_SCORES);
  const [ratingSubmitting, setRatingSubmitting] = useState(false);
  const [needsBatchReload, setNeedsBatchReload] = useState(false);

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
      if (typeof data.adjudicated_by_me === 'number') {
        setAdjudicatedTotal(data.adjudicated_by_me);
      }
      setNeedsBatchReload(false);
      setSelected(null);
      setCurrentIndex(0);
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

  const current = cases[currentIndex] || cases[0];

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (loading || submitting || pendingRating || !current) return;
      if (event.ctrlKey || event.metaKey || event.altKey) return;
      const target = event.target as HTMLElement | null;
      if (target && ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName)) return;
      if (['1', '2', '3', '4', '5'].includes(event.key)) {
        setSelected(Number(event.key));
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [loading, submitting, pendingRating, current]);

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

      const selectedLevelObj = LEVELS.find((l) => l.value === selected);
      toast.success(`Nivel de referencia registrado para el caso #${current.id}`);

      const remainingInBatch = cases.length - 1;
      const nextPendingTotal = Math.max(0, pendingTotal - 1);

      setSessionHistory((prev) => [
        {
          id: current.id,
          date: current.date,
          level: selected,
          levelName: selectedLevelObj?.name || `Nivel ${selected}`,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        },
        ...prev,
      ]);

      setCases((prev) => prev.filter((_, idx) => idx !== currentIndex));
      setPendingTotal(nextPendingTotal);
      setAdjudicatedTotal((prev) => prev + 1);
      setSelected(null);
      if (currentIndex >= cases.length - 1 && currentIndex > 0) {
        setCurrentIndex((prev) => prev - 1);
      }

      if (data.justification) {
        setPendingRating({ id: current.id, justification: data.justification });
        setScores(EMPTY_SCORES);
        if (remainingInBatch === 0 && nextPendingTotal > 0) {
          setNeedsBatchReload(true);
        }
      } else if (remainingInBatch === 0 && nextPendingTotal > 0) {
        await loadQueue();
      }
    } catch (err) {
      console.error('Error registrando nivel de referencia:', err);
      toast.error('No se pudo conectar con el servidor.');
    } finally {
      setSubmitting(false);
    }
  };

  const closeRating = useCallback(() => {
    const shouldReload = needsBatchReload;
    setPendingRating(null);
    setScores(EMPTY_SCORES);
    setNeedsBatchReload(false);
    if (shouldReload) {
      void loadQueue();
    }
  }, [needsBatchReload, loadQueue]);

  const submitRating = async () => {
    if (!pendingRating || RATING_ITEMS.some((item) => scores[item.key] == null)) return;
    setRatingSubmitting(true);
    try {
      const res = await fetchWithAuth(`/api/triage/sessions/${pendingRating.id}/justification_rating/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(scores),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        toast.error(data.error || `No se pudo registrar la valoración (HTTP ${res.status})`);
        if (res.status === 409) closeRating();
        return;
      }
      toast.success(`Valoración registrada para el caso #${pendingRating.id}`);
      closeRating();
    } catch (err) {
      console.error('Error registrando la valoracion de la justificacion:', err);
      toast.error('No se pudo conectar con el servidor.');
    } finally {
      setRatingSubmitting(false);
    }
  };

  const totalScope = adjudicatedTotal + pendingTotal;
  const progressPct = totalScope > 0 ? Math.round((adjudicatedTotal / totalScope) * 100) : 0;

  return (
    <div className="flex flex-col h-full w-full bg-[var(--surface-base)] border border-[var(--surface-border)] rounded-2xl p-4 md:p-6 overflow-y-auto space-y-6 shadow-xl">
      {/* Module Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pb-5 border-b border-[var(--surface-border)]">
        <div className="flex items-center gap-3.5">
          <div className="p-2.5 bg-sky-500/10 rounded-xl border border-sky-500/20 text-sky-400 shrink-0">
            <EyeOff className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-base md:text-lg font-semibold text-slate-100 tracking-tight">Validación Ciega de Triaje</h1>
            <p className="text-xs text-slate-400 mt-0.5">
              Asigne el nivel según su criterio clínico. No se muestra la propuesta de la IA ni el nivel del médico tratante.
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2.5 self-end sm:self-auto">
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[var(--surface-sunken)] text-slate-300 border border-[var(--surface-border)] text-xs font-mono">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
            <span>{adjudicatedTotal} adjudicados</span>
          </div>

          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[var(--surface-sunken)] text-slate-300 border border-[var(--surface-border)] text-xs font-mono">
            <Clock className="w-3.5 h-3.5 text-sky-400" />
            <span>{pendingTotal} pendientes</span>
          </div>

          <button
            type="button"
            onClick={() => setShowGuidelines((prev) => !prev)}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-[var(--surface-card)] hover:bg-[var(--surface-card-hover)] text-slate-300 rounded-lg text-xs font-medium border border-[var(--surface-border)] transition-colors"
          >
            <HelpCircle className="w-3.5 h-3.5 text-sky-400" />
            <span>{showGuidelines ? 'Ocultar Criterios' : 'Criterios Clinicos'}</span>
          </button>

          <button
            type="button"
            onClick={loadQueue}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-[var(--surface-card)] hover:bg-[var(--surface-card-hover)] text-slate-200 rounded-lg text-xs font-medium border border-[var(--surface-border)] transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span>Actualizar</span>
          </button>
        </div>
      </div>

      {/* Progress Bar */}
      {totalScope > 0 && (
        <div className="p-3 rounded-xl bg-[var(--surface-panel)] border border-[var(--surface-border)] space-y-1.5">
          <div className="flex items-center justify-between text-[11px] font-mono text-slate-400">
            <span>Progreso de adjudicación ciega</span>
            <span className="text-slate-200 font-semibold">{progressPct}% ({adjudicatedTotal}/{totalScope})</span>
          </div>
          <div className="w-full h-1.5 rounded-full bg-[var(--surface-sunken)] overflow-hidden">
            <div
              className="h-full bg-sky-500 transition-all duration-300"
              style={{ width: `${progressPct}%` }}
            />
          </div>
        </div>
      )}

      {/* Informative Blind Protocol Callout */}
      <div className="p-3.5 rounded-xl bg-sky-950/30 border border-sky-800/30 text-xs text-slate-300 flex items-start gap-3">
        <ShieldCheck className="w-4 h-4 text-sky-400 shrink-0 mt-0.5" />
        <div className="space-y-1">
          <p className="font-semibold text-sky-200">
            ¿Por qué esta sección aísla los campos del triaje original?
          </p>
          <p className="text-slate-400 leading-relaxed text-[11px]">
            <strong>Metodología Doble Ciego (Resolución 5596 / Gold Standard):</strong> Para garantizar una evaluación científica sin sesgo de anclaje (anclaje cognitivo hacia la sugerencia del algoritmo), el clínico adjudicador únicamente tiene acceso a la transcripción pura del paciente, sin conocer la clasificación de la IA ni el veredicto del médico tratante.
          </p>
        </div>
      </div>

      {/* Protocol Banner & Clinical Criteria Accordion */}
      {showGuidelines && (
        <div className="p-4 rounded-xl bg-[var(--surface-panel)] border border-sky-500/30 text-xs space-y-3 animate-in fade-in">
          <div className="flex items-center gap-2 text-sky-300 font-semibold">
            <ShieldCheck className="w-4 h-4" />
            <span>Criterios de Clasificacion — Protocolo Christus Sinergia Salud</span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-5 gap-2.5 pt-1">
            {LEVELS.map((lvl) => (
              <div key={lvl.value} className="p-2.5 rounded-lg bg-[var(--surface-card)] border border-[var(--surface-border)] space-y-1">
                <span className="font-bold font-mono text-slate-200 block">Nivel {lvl.roman}: {lvl.name}</span>
                <p className="text-[11px] text-slate-400 leading-snug">{lvl.desc}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {loading ? (
        <div className="flex flex-col items-center justify-center py-16 gap-3">
          <div className="w-8 h-8 border-2 border-sky-500/30 border-t-sky-500 rounded-full animate-spin" />
          <p className="text-xs font-mono uppercase tracking-widest text-slate-400">Cargando casos...</p>
        </div>
      ) : error ? (
        <div role="alert" className="p-4 rounded-xl bg-amber-950/30 border border-amber-800/40 text-amber-200 text-sm flex items-center gap-3">
          <AlertCircle className="w-5 h-5 text-amber-400 shrink-0" />
          <span>{error}</span>
        </div>
      ) : pendingRating ? (
        <div className="space-y-4 max-w-4xl" data-testid="justification-rating">
          <div className="p-3.5 rounded-xl bg-emerald-950/30 border border-emerald-800/40 text-xs text-slate-300 flex items-start gap-3">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
            <p className="leading-relaxed">
              Nivel de referencia del caso <strong>#{pendingRating.id}</strong> registrado. Ahora puede ver la justificación que dio la IA:
              valórela de 1 (muy en desacuerdo) a 5 (muy de acuerdo). La valoración ya no influye en el nivel adjudicado.
            </p>
          </div>

          <div className="bg-[var(--surface-panel)] border border-[var(--surface-border)] rounded-2xl p-5">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-300 flex items-center gap-2 mb-3">
              <FileText className="w-4 h-4 text-sky-400" />
              <span>Justificación de la IA</span>
            </h2>
            <p className="text-sm text-slate-200 whitespace-pre-wrap leading-relaxed bg-[var(--surface-sunken)] p-4 rounded-xl border border-[var(--surface-border)]">
              {pendingRating.justification}
            </p>
          </div>

          <div className="space-y-3">
            {RATING_ITEMS.map((item) => (
              <fieldset key={item.key} className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 p-3 rounded-xl bg-[var(--surface-panel)] border border-[var(--surface-border)]">
                <legend className="sr-only">{item.label}</legend>
                <div>
                  <span className="text-xs font-semibold text-slate-200 flex items-center gap-1.5">
                    <Star className="w-3.5 h-3.5 text-amber-400" /> {item.label}
                  </span>
                  <span className="text-[11px] text-slate-400">{item.help}</span>
                </div>
                <div className="flex gap-1.5">
                  {[1, 2, 3, 4, 5].map((value) => {
                    const active = scores[item.key] === value;
                    return (
                      <button
                        key={value}
                        type="button"
                        aria-pressed={active}
                        aria-label={`${item.label}: ${value}`}
                        onClick={() => setScores((prev) => ({ ...prev, [item.key]: value }))}
                        className={`w-9 h-9 rounded-lg border text-sm font-bold font-mono transition-colors ${
                          active
                            ? 'bg-sky-600 border-sky-500 text-white'
                            : 'bg-[var(--surface-card)] border-[var(--surface-border)] text-slate-300 hover:bg-[var(--surface-card-hover)]'
                        }`}
                      >
                        {value}
                      </button>
                    );
                  })}
                </div>
              </fieldset>
            ))}
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={submitRating}
              disabled={ratingSubmitting || RATING_ITEMS.some((item) => scores[item.key] == null)}
              className="flex items-center gap-2 px-5 py-2.5 bg-sky-600 hover:bg-sky-500 disabled:bg-slate-800 disabled:text-slate-500 text-white rounded-xl text-xs font-semibold transition-all"
            >
              <Check className="w-4 h-4" />
              <span>{ratingSubmitting ? 'Registrando...' : 'Registrar valoración'}</span>
            </button>
            <button
              type="button"
              onClick={closeRating}
              disabled={ratingSubmitting}
              className="px-4 py-2.5 bg-[var(--surface-card)] hover:bg-[var(--surface-card-hover)] text-slate-300 rounded-xl text-xs font-medium border border-[var(--surface-border)] transition-colors"
            >
              Omitir y seguir
            </button>
            <p className="text-[11px] text-slate-400">La valoración es definitiva; si la omite, el caso queda sin valorar.</p>
          </div>
        </div>
      ) : !current ? (
        <div className="flex flex-col items-center justify-center gap-4 py-20 text-slate-400">
          <div className="p-4 bg-emerald-500/10 rounded-full border border-emerald-500/20 text-emerald-400">
            <CheckCircle2 className="w-10 h-10" />
          </div>
          <div className="text-center space-y-1">
            <p className="text-base font-semibold text-slate-200">Cola de Validación Ciega al Día</p>
            <p className="text-xs text-slate-400 max-w-md">
              No hay casos pendientes de adjudicación en este momento. Todos los triajes cuentan con evaluación de referencia o fueron registrados por su usuario.
            </p>
          </div>
          <button
            type="button"
            onClick={loadQueue}
            className="px-4 py-2 bg-[var(--surface-card)] hover:bg-[var(--surface-card-hover)] text-slate-200 text-xs font-medium rounded-xl border border-[var(--surface-border)] transition-colors"
          >
            Verificar Nuevos Casos
          </button>
        </div>
      ) : (
        <div className="space-y-6 max-w-4xl">
          {/* Navigation between queue cases if multiple exist */}
          {cases.length > 1 && (
            <div className="flex items-center justify-between p-2 rounded-xl bg-[var(--surface-panel)] border border-[var(--surface-border)] text-xs">
              <span className="text-slate-400 font-mono text-[11px] px-2">
                Caso <span className="font-bold text-sky-400">{currentIndex + 1}</span> de <span className="text-slate-200">{cases.length}</span> en lote actual ({pendingTotal} totales)
              </span>
              <div className="flex items-center gap-1.5">
                <button
                  type="button"
                  onClick={() => {
                    setCurrentIndex((prev) => Math.max(0, prev - 1));
                    setSelected(null);
                  }}
                  disabled={currentIndex === 0}
                  className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-[var(--surface-card)] border border-[var(--surface-border)] text-slate-300 disabled:opacity-40 hover:bg-[var(--surface-card-hover)] transition-colors"
                >
                  <ChevronLeft className="w-3.5 h-3.5" />
                  <span>Anterior</span>
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setCurrentIndex((prev) => Math.min(cases.length - 1, prev + 1));
                    setSelected(null);
                  }}
                  disabled={currentIndex === cases.length - 1}
                  className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-[var(--surface-card)] border border-[var(--surface-border)] text-slate-300 disabled:opacity-40 hover:bg-[var(--surface-card-hover)] transition-colors"
                >
                  <span>Siguiente</span>
                  <ChevronRight className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          )}

          {/* Patient case metadata bar */}
          <div className="flex flex-wrap items-center gap-2 p-2.5 rounded-xl bg-[var(--surface-panel)] border border-[var(--surface-border)] text-xs">
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-[var(--surface-card)] border border-[var(--surface-border)] text-slate-200 font-mono">
              <span className="text-slate-500">CASO</span>
              <span className="font-semibold text-sky-400">#{current.id}</span>
            </div>
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-[var(--surface-card)] border border-[var(--surface-border)] text-slate-300 font-mono">
              <span className="text-slate-500">FECHA</span>
              <span>{current.date}</span>
            </div>
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-[var(--surface-card)] border border-[var(--surface-border)] text-slate-300 font-mono">
              <span className="text-slate-500">SEXO</span>
              <span>{GENDER_LABELS[current.gender] || 'Sexo no registrado'}</span>
            </div>
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-[var(--surface-card)] border border-[var(--surface-border)] text-slate-300 font-mono">
              <span className="text-slate-500">EDAD</span>
              <span>{current.age != null ? `${current.age} años` : 'Edad no registrada'}</span>
            </div>
          </div>

          {/* Clinical Transcript Record Card */}
          <div className="bg-[var(--surface-panel)] border border-[var(--surface-border)] rounded-2xl p-5 shadow-inner">
            <div className="flex items-center justify-between pb-3 mb-3 border-b border-[var(--surface-border)]">
              <div className="flex items-center gap-2">
                <FileText className="w-4 h-4 text-sky-400" />
                <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-300">Transcripción de la consulta</h2>
              </div>
              <span className="text-[11px] text-slate-500 font-mono">Registro Clínico de Voz</span>
            </div>
            <p className="text-sm text-slate-200 whitespace-pre-wrap leading-relaxed font-sans bg-[var(--surface-sunken)] p-4 rounded-xl border border-[var(--surface-border)]">
              {current.transcript || 'Sin transcripción registrada.'}
            </p>
          </div>

          {/* Level adjudication grid */}
          <fieldset className="space-y-3">
            <legend className="text-xs font-semibold uppercase tracking-wider text-slate-300 flex items-center justify-between w-full">
              <span className="flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-sky-400" />
                <span>Nivel de referencia</span>
              </span>
              <span className="text-[10px] font-mono text-slate-500 normal-case">Atajo: teclas 1 a 5</span>
            </legend>
            <div className="grid grid-cols-1 sm:grid-cols-5 gap-3">
              {LEVELS.map((lvl) => {
                const isSelected = selected === lvl.value;
                return (
                  <button
                    key={lvl.value}
                    type="button"
                    aria-pressed={isSelected}
                    onClick={() => setSelected(lvl.value)}
                    className={`flex flex-col items-center justify-center gap-1.5 p-3.5 rounded-xl border bg-[var(--surface-panel)] transition-all text-center ${lvl.color} ${
                      isSelected ? `${lvl.selectedStyle} scale-[1.02] shadow-lg` : 'hover:scale-[1.01]'
                    }`}
                  >
                    <span className="text-xl font-bold font-mono tracking-tight">{lvl.roman}</span>
                    <span className="text-xs font-medium">{lvl.name}</span>
                  </button>
                );
              })}
            </div>
          </fieldset>

          {/* Submission Action */}
          <div className="pt-2 flex flex-col sm:flex-row items-start sm:items-center gap-4">
            <button
              type="button"
              onClick={submit}
              disabled={selected == null || submitting}
              className="flex items-center gap-2 px-5 py-2.5 bg-sky-600 hover:bg-sky-500 disabled:bg-slate-800 disabled:text-slate-500 disabled:border-slate-800 text-white rounded-xl text-xs font-semibold transition-all shadow-md shadow-sky-600/20"
            >
              <CheckCircle2 className="w-4 h-4" />
              <span>{submitting ? 'Registrando...' : 'Registrar nivel de referencia'}</span>
            </button>
            <p className="text-[11px] text-slate-400">
              El nivel registrado es definitivo e inmutable para garantizar la trazabilidad del estudio.
            </p>
          </div>

          {/* Session Adjudications Log */}
          {sessionHistory.length > 0 && (
            <div className="pt-4 border-t border-[var(--surface-border)] space-y-3">
              <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
                <History className="w-3.5 h-3.5 text-sky-400" />
                <span>Adjudicaciones Realizadas en esta Sesión ({sessionHistory.length})</span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2.5">
                {sessionHistory.map((item) => (
                  <div key={item.id} className="p-3 rounded-xl bg-[var(--surface-panel)] border border-[var(--surface-border)] flex items-center justify-between text-xs">
                    <div>
                      <span className="font-mono text-slate-300 font-semibold">Caso #{item.id}</span>
                      <span className="text-[10px] text-slate-500 block font-mono">{item.timestamp}</span>
                    </div>
                    <span className="px-2 py-0.5 rounded-full bg-sky-500/10 text-sky-300 border border-sky-500/20 font-medium text-[11px]">
                      {item.levelName}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
