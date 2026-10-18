'use client';

import { useState } from 'react';
import { BookOpen, ChevronDown, ChevronUp, Cpu, Tags, ListChecks, CheckCircle2, AlertTriangle } from 'lucide-react';

// Datos que el backend ya devuelve en el analisis (ai_analyzer + views.analyze).
export interface NormalizedTerm {
  raw_term: string;
  medical_term: string;
  code: string | null;
  code_system: string | null;
  code_snomed?: string | null;
  snomed_valid?: boolean;
  category?: string;
  source: string;
  valid: boolean;
  negated?: boolean;
  allergy?: boolean;
}

export interface NerSpan {
  text: string;
  label: string;
  score: number;
  term?: string;
  negated?: boolean;
  kept?: boolean;
  confirmed_by?: string[];
}

export interface RagCriterion {
  id: string;
  level: number;
  name: string;
  criterion: string;
}

export interface ExplainableAnalysis {
  engine_used?: string;
  ner_engine?: string | null;
  cached?: boolean;
  total_tokens?: number;
  normalized_terms?: NormalizedTerm[];
  ner_spans?: NerSpan[];
  rag_criteria?: RagCriterion[];
  [key: string]: unknown;
}

const SOURCE_LABELS: Record<string, string> = {
  correccion_asr: 'Corrección ASR',
  abreviatura: 'Abreviatura',
  diccionario: 'Diccionario',
  llm: 'LLM',
};

const NER_LABELS: Record<string, string> = {
  SINTOMA: 'Síntoma',
  ENFERMEDAD: 'Enfermedad',
  FARMACO: 'Fármaco',
};

const LEVEL_STYLES = [
  '',
  'bg-red-500/15 text-red-300 border-red-500/30',
  'bg-orange-500/15 text-orange-300 border-orange-500/30',
  'bg-amber-500/15 text-amber-300 border-amber-500/30',
  'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
  'bg-sky-500/15 text-sky-300 border-sky-500/30',
];

/**
 * Explica de dónde sale el resultado del triaje: criterios del protocolo recuperados (RAG), términos normalizados
 * con su código CIE-10/SNOMED (verificado o no) y menciones del NER con el motor que las detectó.
 */
export default function ExplainabilityPanel({ analysis }: { analysis: ExplainableAnalysis | null | undefined }) {
  const [open, setOpen] = useState(false);
  if (!analysis) return null;

  const criteria = analysis.rag_criteria ?? [];
  const terms = analysis.normalized_terms ?? [];
  const spans = analysis.ner_spans ?? [];
  const nerEngine = analysis.ner_engine;
  const codedTerms = terms.filter(t => t.code).length;
  // Un triaje cargado del historial solo conserva los criterios y el motor: los terminos y el NER no se guardan.
  const fromHistory = analysis.normalized_terms === undefined && analysis.ner_engine === undefined;
  const nerSummary = nerEngine ? 'RoBERTa' : fromHistory ? 'no registrado' : 'respaldo';

  return (
    <div className="shrink-0 rounded-xl border border-[var(--surface-border)] bg-[var(--surface-card)]" data-testid="explainability-panel">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        className="w-full flex items-center justify-between gap-2 px-3 py-2 text-left"
      >
        <span className="flex items-center gap-2 text-[11px] font-semibold text-slate-200">
          <BookOpen className="w-3.5 h-3.5 text-sky-400" />
          ¿En qué se basa este resultado?
        </span>
        <span className="flex items-center gap-2 text-[10px] text-slate-400 font-mono">
          <span className="hidden sm:inline">
            {fromHistory ? `${criteria.length} criterios · historial` : `${criteria.length} criterios · ${codedTerms} códigos · NER: ${nerSummary}`}
          </span>
          {open ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
        </span>
      </button>

      {open && (
        <div className="px-3 pb-3 space-y-3 text-[11px]">
          {/* Motores */}
          <div className="flex flex-wrap gap-1.5">
            <span className="flex items-center gap-1 px-2 py-0.5 rounded-full border border-slate-700 bg-slate-800/60 text-slate-300">
              <Cpu className="w-3 h-3" /> Triaje: {analysis.engine_used || 'Motor de reglas'}
            </span>
            {!fromHistory && (
              <span className={`px-2 py-0.5 rounded-full border ${nerEngine ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300' : 'border-amber-500/30 bg-amber-500/10 text-amber-300'}`}>
                NER: {nerEngine ? `RoBERTa clínico (${nerEngine.replace(/^roberta:/, '')})` : 'sin modelo, se usan el catálogo y el LLM'}
              </span>
            )}
            {analysis.cached && (
              <span className="px-2 py-0.5 rounded-full border border-sky-500/30 bg-sky-500/10 text-sky-300">Respuesta en caché</span>
            )}
          </div>

          {/* Criterios del protocolo */}
          <section>
            <h4 className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-slate-400 mb-1.5">
              <ListChecks className="w-3.5 h-3.5" /> Criterios del protocolo consultados
            </h4>
            <p className="text-[10px] text-slate-500 mb-1.5">
              Recuperados del protocolo y enviados al modelo como contexto; el nivel final no tiene por qué cumplirlos todos.
            </p>
            {criteria.length ? (
              <ul className="space-y-1.5">
                {criteria.map(c => (
                  <li key={c.id} className="flex items-start gap-2">
                    <span className={`shrink-0 px-1.5 py-0.5 rounded border text-[9px] font-bold font-mono ${LEVEL_STYLES[c.level] || ''}`}>
                      N{c.level}
                    </span>
                    <span className="text-slate-300 leading-snug">
                      <span className="font-semibold text-slate-200">{c.name}.</span> {c.criterion}
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-slate-400">No hay criterios registrados para este análisis.</p>
            )}
          </section>

          {/* Terminos normalizados */}
          <section>
            <h4 className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-slate-400 mb-1.5">
              <Tags className="w-3.5 h-3.5" /> Términos normalizados y códigos
            </h4>
            {terms.length ? (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="text-left text-[10px] text-slate-400">
                      <th className="py-1 pr-2 font-medium">En el relato</th>
                      <th className="py-1 pr-2 font-medium">Término clínico</th>
                      <th className="py-1 pr-2 font-medium">CIE-10 / ATC</th>
                      <th className="py-1 pr-2 font-medium">SNOMED CT</th>
                      <th className="py-1 font-medium">Origen</th>
                    </tr>
                  </thead>
                  <tbody>
                    {terms.map((t, i) => (
                      <tr key={`${t.raw_term}-${i}`} className="border-t border-slate-800/70 align-top">
                        <td className="py-1 pr-2 text-slate-400 italic">«{t.raw_term}»</td>
                        <td className="py-1 pr-2 text-slate-200">
                          {t.medical_term}
                          {t.negated && <span className="ml-1 text-[9px] px-1 rounded bg-slate-700/60 text-slate-300">negado</span>}
                          {t.allergy && <span className="ml-1 text-[9px] px-1 rounded bg-orange-500/15 text-orange-300">alergia</span>}
                        </td>
                        <td className="py-1 pr-2 font-mono"><CodeCell code={t.code} valid={t.valid} /></td>
                        <td className="py-1 pr-2 font-mono"><CodeCell code={t.code_snomed ?? null} valid={!!t.snomed_valid} /></td>
                        <td className="py-1 text-slate-400">{SOURCE_LABELS[t.source] || t.source}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-slate-400">
                {fromHistory
                  ? 'Los términos normalizados y las menciones del NER no se guardan en el historial; se muestran al analizar.'
                  : 'El catálogo local no reconoció términos en el relato.'}
              </p>
            )}
          </section>

          {/* Menciones del NER */}
          {spans.length > 0 && (
            <section>
              <h4 className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-slate-400 mb-1.5">
                <Cpu className="w-3.5 h-3.5" /> Menciones detectadas por el NER
              </h4>
              <div className="flex flex-wrap gap-1.5">
                {spans.map((s, i) => (
                  <span
                    key={`${s.text}-${i}`}
                    title={s.confirmed_by?.length ? `Confirmado por: ${s.confirmed_by.join(', ')}` : 'Sin confirmación externa'}
                    className={`px-2 py-0.5 rounded-full border text-[10px] ${s.kept === false ? 'border-slate-700 text-slate-500 line-through' : 'border-sky-500/30 bg-sky-500/10 text-sky-200'}`}
                  >
                    {s.text} · {NER_LABELS[s.label] || s.label} · {Math.round((s.score || 0) * 100)}%
                    {s.negated ? ' · negado' : ''}
                  </span>
                ))}
              </div>
              <p className="mt-1 text-[10px] text-slate-500">Las tachadas no superaron el umbral de confianza ni fueron confirmadas por el catálogo o el LLM.</p>
            </section>
          )}
        </div>
      )}
    </div>
  );
}

function CodeCell({ code, valid }: { code: string | null; valid: boolean }) {
  if (!code) return <span className="text-slate-500">—</span>;
  return (
    <span className={`inline-flex items-center gap-1 ${valid ? 'text-emerald-300' : 'text-amber-300'}`} title={valid ? 'Código verificado en el catálogo' : 'Código no verificado'}>
      {valid ? <CheckCircle2 className="w-3 h-3" /> : <AlertTriangle className="w-3 h-3" />}
      {code}
    </span>
  );
}
