'use client';

import { useCallback, useEffect, useState } from 'react';
import { FlaskConical, RefreshCw, AlertCircle, Mic, Tags, Scale, Stethoscope } from 'lucide-react';
import { fetchWithAuth } from '@/lib/api';

type CI = [number, number] | null | undefined;

interface ExtractionRun {
  name: string;
  updated_at: string;
  engine: string | null;
  model: string | null;
  ner_engine: string | null;
  split: string | null;
  match: string | null;
  cases: number | null;
  entities: {
    precision: number | null;
    recall: number | null;
    f1: number | null;
    f1_ci95: CI;
    macro_f1: number | null;
    by_type: Record<string, number | null>;
    negation_accuracy: number | null;
    cie10_accuracy: number | null;
  } | null;
  triage: {
    n: number | null;
    exact_agreement: number | null;
    cohen_kappa: number | null;
    cohen_kappa_ci95: CI;
    critical_sensitivity: number | null;
    critical_sensitivity_ci95: CI;
    undertriage_rate: number | null;
    overtriage_rate: number | null;
  } | null;
  performance: { latency_ms_mean?: number; latency_ms_p95?: number; tokens_mean?: number; cost_usd?: number | null } | null;
  run?: { model_versions?: string[] | null; prompt_version?: string | null; policy?: string | null; tier?: string | null } | null;
}

interface ComparisonRow {
  name: string;
  label: string;
  n: number | null;
  exact_agreement: number | null;
  exact_agreement_ci95?: CI;
  cohen_kappa: number | null;
  cohen_kappa_ci95?: CI;
  critical_sensitivity: number | null;
  critical_sensitivity_ci95?: CI;
  undertriage_rate: number | null;
  overtriage_rate: number | null;
  latency_ms_p50: number | null;
  latency_ms_p95: number | null;
  hardware?: string | null;
  cost_usd_per_1000: number | null;
  privacy: string;
}

interface Comparison {
  name: string;
  split: string;
  baseline: string | null;
  generated_at?: string;
  rows: ComparisonRow[];
  repeatability?: { n: number; cohen_kappa: number | null; exact_agreement: number | null } | null;
}

interface Agreement {
  n: number | null;
  exact_agreement: number | null;
  cohen_kappa: number | null;
  cohen_kappa_ci95?: CI;
  critical_sensitivity?: number | null;
}

interface LikertItem { n: number; mean: number | null; ci95: CI }

interface ClinicalValidation {
  name: string;
  split: string;
  n: number;
  pending?: number;
  clinician_vs_ai: Agreement | null;
  clinician_vs_rules: Agreement | null;
  clinician_vs_team: Agreement | null;
  likert: Record<'clarity' | 'relevance' | 'fidelity', LikertItem> | null;
}

interface AsrSummary {
  audios: number;
  wer: number | null;
  cer: number | null;
  error_terminos_clinicos: number | null;
  rtf: number | null;
  latencia_media_s: number | null;
}

interface AsrRun {
  name: string;
  updated_at: string;
  model_size: string | null;
  device: string | null;
  chunk_seconds: number | null;
  initial_prompt: boolean | null;
  global: AsrSummary | null;
  by_condition: Record<string, AsrSummary> | null;
}

interface ResultsData {
  extraction: ExtractionRun[];
  asr: AsrRun[];
  comparison?: Comparison[];
  clinical_validation?: ClinicalValidation[];
}

const NO_DATA = '—';
const ENTITY_LABELS: Record<string, string> = {
  symptoms: 'Síntomas', diagnoses: 'Diagnósticos', medications: 'Medicamentos', allergies: 'Alergias',
  vitals: 'Vitales', history: 'Antecedentes', negated_findings: 'Negados',
};

const num = (value: number | null | undefined, digits = 3) => (value == null ? NO_DATA : value.toFixed(digits));
const pctValue = (value: number | null | undefined) => (value == null ? NO_DATA : `${value}%`);
const ratioPct = (value: number | null | undefined) => (value == null ? NO_DATA : `${(value * 100).toFixed(1)}%`);
const ci = (interval: CI, digits = 3) => (interval ? `[${interval[0].toFixed(digits)}–${interval[1].toFixed(digits)}]` : '');
const LIKERT_LABELS: Record<string, string> = { clarity: 'Claridad', relevance: 'Pertinencia', fidelity: 'Fidelidad al protocolo' };
const AGREEMENT_LABELS: Record<string, string> = {
  clinician_vs_ai: 'Clínico vs. IA (híbrido)',
  clinician_vs_rules: 'Clínico vs. motor de reglas',
  clinician_vs_team: 'Clínico vs. etiquetas del equipo (techo humano)',
};

/**
 * Resultados reproducibles (evaluate_extraction / evaluate_benchmark / evaluate_asr) guardados en el repositorio.
 * No recalcula nada: muestra los JSON tal como los dejaron los comandos.
 */
export default function EvaluationResults() {
  const [data, setData] = useState<ResultsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchWithAuth('/api/triage/sessions/benchmark_results/');
      if (!res.ok) {
        setError(`No se pudieron cargar los resultados (HTTP ${res.status}).`);
        return;
      }
      setData(await res.json());
    } catch {
      setError('No se pudo conectar con el servidor.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="flex flex-col h-full w-full bg-slate-900/90 border border-slate-800/80 rounded-2xl p-4 md:p-6 overflow-y-auto space-y-6 shadow-xl backdrop-blur-md">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pb-5 border-b border-slate-800/80">
        <div className="flex items-center gap-3.5">
          <div className="p-2.5 bg-violet-500/10 rounded-xl border border-violet-500/20 text-violet-300 shrink-0">
            <FlaskConical className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-base md:text-lg font-semibold text-slate-100">Resultados de Evaluación</h1>
            <p className="text-xs text-slate-400 mt-0.5">
              Cifras reproducibles sobre el corpus anotado y los audios grabados. Las del split <strong>test</strong> son la evaluación final.
            </p>
          </div>
        </div>
        <button
          onClick={load}
          disabled={loading}
          className="flex items-center gap-1.5 px-3.5 py-2 bg-slate-800/80 hover:bg-slate-700 text-slate-200 rounded-xl text-xs font-semibold border border-slate-700/60 transition-colors shrink-0"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>Actualizar</span>
        </button>
      </div>

      {error && (
        <div role="alert" className="p-4 rounded-xl bg-amber-950/30 border border-amber-800/40 text-amber-200 text-sm flex items-center gap-3">
          <AlertCircle className="w-5 h-5 text-amber-400 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Extraccion de entidades y triaje */}
      <section className="space-y-3" data-testid="extraction-results">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-200 flex items-center gap-2">
          <Tags className="w-4 h-4 text-violet-300" /> Extracción de entidades y nivel de triaje
        </h2>
        {data?.extraction.length ? (
          <div className="overflow-x-auto rounded-xl border border-slate-800/80">
            <table className="w-full text-xs">
              <thead className="bg-slate-950/60 text-slate-400 text-[11px]">
                <tr className="text-left">
                  <th className="py-2 px-3 font-semibold">Corrida</th>
                  <th className="py-2 px-3 font-semibold">F1 micro (IC 95 %)</th>
                  <th className="py-2 px-3 font-semibold">F1 macro</th>
                  <th className="py-2 px-3 font-semibold">Negación</th>
                  <th className="py-2 px-3 font-semibold">CIE-10</th>
                  <th className="py-2 px-3 font-semibold">Kappa (IC 95 %)</th>
                  <th className="py-2 px-3 font-semibold">Sens. I–II</th>
                  <th className="py-2 px-3 font-semibold">Latencia</th>
                </tr>
              </thead>
              <tbody className="font-mono text-slate-200">
                {data.extraction.map(run => (
                  <tr key={run.name} className="border-t border-slate-800/70 align-top">
                    <td className="py-2.5 px-3 font-sans">
                      <div className="font-semibold text-slate-100">{run.name}</div>
                      <div className="text-[10px] text-slate-400 mt-0.5 flex flex-wrap gap-1">
                        <span className={`px-1.5 rounded border ${run.split === 'test' ? 'border-violet-500/40 text-violet-300' : 'border-slate-700 text-slate-400'}`}>
                          {run.split ?? '?'}
                        </span>
                        <span>{run.engine}{run.model ? ` · ${run.model}` : ''}{run.ner_engine ? ` · ${run.ner_engine}` : ''}</span>
                        <span>· {run.cases ?? NO_DATA} casos</span>
                        {run.run?.prompt_version && <span>· prompt {run.run.prompt_version}</span>}
                        {run.run?.model_versions?.length ? <span>· {run.run.model_versions.join(', ')}</span> : null}
                      </div>
                      {run.entities && Object.keys(run.entities.by_type).length > 0 && (
                        <div className="text-[10px] text-slate-500 mt-1">
                          {Object.entries(run.entities.by_type).map(([key, value]) => `${ENTITY_LABELS[key] || key} ${num(value, 2)}`).join(' · ')}
                        </div>
                      )}
                    </td>
                    <td className="py-2.5 px-3">
                      {num(run.entities?.f1)} <span className="text-[10px] text-slate-500">{ci(run.entities?.f1_ci95)}</span>
                    </td>
                    <td className="py-2.5 px-3">{num(run.entities?.macro_f1)}</td>
                    <td className="py-2.5 px-3">{ratioPct(run.entities?.negation_accuracy)}</td>
                    <td className="py-2.5 px-3">{ratioPct(run.entities?.cie10_accuracy)}</td>
                    <td className="py-2.5 px-3">
                      {num(run.triage?.cohen_kappa)} <span className="text-[10px] text-slate-500">{ci(run.triage?.cohen_kappa_ci95)}</span>
                    </td>
                    <td className="py-2.5 px-3">
                      {pctValue(run.triage?.critical_sensitivity)}{' '}
                      <span className="text-[10px] text-slate-500">{ci(run.triage?.critical_sensitivity_ci95, 1)}</span>
                    </td>
                    <td className="py-2.5 px-3">
                      {run.performance?.latency_ms_mean != null ? `${run.performance.latency_ms_mean} ms` : NO_DATA}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : !loading && (
          <p className="text-[11px] text-slate-400">
            Aún no hay corridas guardadas. Se generan con <code className="text-slate-300">evaluate_extraction</code> o{' '}
            <code className="text-slate-300">evaluate_benchmark</code> y la opción <code className="text-slate-300">--output</code> en{' '}
            <code className="text-slate-300">triage/benchmark/resultados/</code>.
          </p>
        )}
      </section>

      {/* Comparativa de motores (compare_engines) */}
      {data?.comparison?.length ? (
        <section className="space-y-3" data-testid="engine-comparison">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-200 flex items-center gap-2">
            <Scale className="w-4 h-4 text-emerald-300" /> Comparativa de motores de triaje
          </h2>
          {data.comparison.map(comp => (
            <div key={comp.name} className="overflow-x-auto rounded-xl border border-slate-800/80">
              <div className="px-3 py-2 text-[10px] text-slate-400 bg-slate-950/40 flex flex-wrap gap-2">
                <span className={`px-1.5 rounded border ${comp.split === 'test' ? 'border-violet-500/40 text-violet-300' : 'border-slate-700 text-slate-400'}`}>{comp.split}</span>
                <span>IC 95 % por bootstrap</span>
                {comp.repeatability && (
                  <span>· repetibilidad Kappa {num(comp.repeatability.cohen_kappa)} ({comp.repeatability.n} casos)</span>
                )}
              </div>
              <table className="w-full text-xs">
                <thead className="bg-slate-950/60 text-slate-400 text-[11px]">
                  <tr className="text-left">
                    <th className="py-2 px-3 font-semibold">Motor</th>
                    <th className="py-2 px-3 font-semibold">Exactitud</th>
                    <th className="py-2 px-3 font-semibold">Kappa</th>
                    <th className="py-2 px-3 font-semibold">Sens. I–II</th>
                    <th className="py-2 px-3 font-semibold">Infratriaje</th>
                    <th className="py-2 px-3 font-semibold">Latencia p50 / p95</th>
                    <th className="py-2 px-3 font-semibold">Costo / 1.000</th>
                    <th className="py-2 px-3 font-semibold">Privacidad</th>
                  </tr>
                </thead>
                <tbody className="font-mono text-slate-200">
                  {comp.rows.map(row => (
                    <tr key={row.name} className="border-t border-slate-800/70 align-top">
                      <td className="py-2.5 px-3 font-sans">
                        <div className="font-semibold text-slate-100">{row.label}</div>
                        <div className="text-[10px] text-slate-500">{row.n ?? NO_DATA} casos{row.name === comp.baseline ? ' · referencia' : ''}</div>
                      </td>
                      <td className="py-2.5 px-3">{pctValue(row.exact_agreement)} <span className="text-[10px] text-slate-500">{ci(row.exact_agreement_ci95, 1)}</span></td>
                      <td className="py-2.5 px-3">{num(row.cohen_kappa)} <span className="text-[10px] text-slate-500">{ci(row.cohen_kappa_ci95)}</span></td>
                      <td className="py-2.5 px-3">{pctValue(row.critical_sensitivity)} <span className="text-[10px] text-slate-500">{ci(row.critical_sensitivity_ci95, 1)}</span></td>
                      <td className="py-2.5 px-3">{pctValue(row.undertriage_rate)}</td>
                      <td className="py-2.5 px-3">
                        {row.latency_ms_p50 != null ? `${row.latency_ms_p50} / ${row.latency_ms_p95 ?? NO_DATA} ms` : NO_DATA}
                        {row.hardware && <div className="text-[10px] text-slate-500 font-sans">{row.hardware}</div>}
                      </td>
                      <td className="py-2.5 px-3">{row.cost_usd_per_1000 == null ? NO_DATA : `${row.cost_usd_per_1000.toFixed(2)} USD`}</td>
                      <td className="py-2.5 px-3 font-sans text-[11px]">{row.privacy}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}
        </section>
      ) : null}

      {/* Validacion clinica ciega (export_blind_review) */}
      {data?.clinical_validation?.length ? (
        <section className="space-y-3" data-testid="clinical-validation">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-200 flex items-center gap-2">
            <Stethoscope className="w-4 h-4 text-rose-300" /> Validación clínica ciega
          </h2>
          {data.clinical_validation.map(val => (
            <div key={val.name} className="rounded-xl border border-slate-800/80 p-3 space-y-2">
              <p className="text-[11px] text-slate-400">
                {val.n} casos del split {val.split} adjudicados a ciegas por el clínico{val.pending ? ` · ${val.pending} pendientes` : ''}.
              </p>
              <table className="w-full text-xs">
                <tbody className="font-mono text-slate-200">
                  {(['clinician_vs_ai', 'clinician_vs_rules', 'clinician_vs_team'] as const).map(key => (
                    <tr key={key} className="border-t border-slate-800/70">
                      <td className="py-2 px-2 font-sans text-slate-300">{AGREEMENT_LABELS[key]}</td>
                      <td className="py-2 px-2">Kappa {num(val[key]?.cohen_kappa)} <span className="text-[10px] text-slate-500">{ci(val[key]?.cohen_kappa_ci95)}</span></td>
                      <td className="py-2 px-2">Exactitud {pctValue(val[key]?.exact_agreement)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {val.likert && (
                <p className="text-[11px] text-slate-400">
                  Justificaciones (Likert 1–5):{' '}
                  {Object.entries(val.likert).map(([key, item]) => `${LIKERT_LABELS[key] || key} ${num(item.mean, 2)} ${ci(item.ci95, 2)}`).join(' · ')}
                </p>
              )}
            </div>
          ))}
        </section>
      ) : null}

      {/* ASR */}
      <section className="space-y-3" data-testid="asr-results">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-200 flex items-center gap-2">
          <Mic className="w-4 h-4 text-sky-400" /> Reconocimiento de voz (WER)
        </h2>
        {data?.asr.length ? (
          <div className="overflow-x-auto rounded-xl border border-slate-800/80">
            <table className="w-full text-xs">
              <thead className="bg-slate-950/60 text-slate-400 text-[11px]">
                <tr className="text-left">
                  <th className="py-2 px-3 font-semibold">Corrida</th>
                  <th className="py-2 px-3 font-semibold">WER</th>
                  <th className="py-2 px-3 font-semibold">CER</th>
                  <th className="py-2 px-3 font-semibold">Error en términos clínicos</th>
                  <th className="py-2 px-3 font-semibold">RTF</th>
                  <th className="py-2 px-3 font-semibold">Por condición (WER)</th>
                </tr>
              </thead>
              <tbody className="font-mono text-slate-200">
                {data.asr.map(run => (
                  <tr key={run.name} className="border-t border-slate-800/70 align-top">
                    <td className="py-2.5 px-3 font-sans">
                      <div className="font-semibold text-slate-100">{run.name}</div>
                      <div className="text-[10px] text-slate-400 mt-0.5">
                        {run.model_size} · {run.device} · {run.chunk_seconds ? `fragmentos de ${run.chunk_seconds} s` : 'archivo completo'}
                        {' · '}{run.initial_prompt ? 'con prompt clínico' : 'sin prompt'} · {run.global?.audios ?? 0} audios
                      </div>
                    </td>
                    <td className="py-2.5 px-3">{ratioPct(run.global?.wer)}</td>
                    <td className="py-2.5 px-3">{ratioPct(run.global?.cer)}</td>
                    <td className="py-2.5 px-3">{ratioPct(run.global?.error_terminos_clinicos)}</td>
                    <td className="py-2.5 px-3">{num(run.global?.rtf, 2)}</td>
                    <td className="py-2.5 px-3 text-[11px]">
                      {run.by_condition
                        ? Object.entries(run.by_condition).map(([cond, s]) => `${cond}: ${ratioPct(s.wer)}`).join(' · ')
                        : NO_DATA}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : !loading && (
          <p className="text-[11px] text-slate-400">
            Aún no hay mediciones de WER. Se generan con <code className="text-slate-300">evaluate_asr --output data/asr/resultado_*.json</code>{' '}
            después de grabar los audios del guion.
          </p>
        )}
      </section>
    </div>
  );
}
