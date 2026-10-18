'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { 
  BarChart3, 
  ShieldCheck, 
  TrendingUp, 
  CheckCircle2, 
  RefreshCw, 
  Activity, 
  GitCompare, 
  Zap, 
  AlertTriangle,
  Cpu,
  Layers,
  ArrowUpDown
} from 'lucide-react';
import { fetchWithAuth } from '@/lib/api';

interface EvaluationItem {
  id: number;
  patient: string;
  ai_level: number;
  final_level: number;
  is_modified: boolean;
  agreement_score: number;
  date: string;
}

interface CacheStats {
  hits: number;
  misses: number;
  total_requests: number;
  hit_rate_pct: number;
  cached_items_count: number;
  estimated_tokens_saved: number;
}

interface ReferenceAgreement {
  n: number;
  exact_agreement: number | null;
  cohen_kappa: number | null;
  kappa_interpretation: string;
  undertriage_rate: number | null;
  overtriage_rate: number | null;
  critical_cases: number;
  critical_sensitivity: number | null;
  critical_undertriage_count: number;
}

interface ReferenceValidation {
  referenced_count: number;
  ai_vs_reference: ReferenceAgreement;
  physician_vs_reference: ReferenceAgreement;
}

interface MetricsData {
  total_triages: number;
  // null cuando aun no hay sesiones: no se muestran valores inventados
  concordance_rate: number | null;
  severity_drift: number | null;
  symptom_retention: number | null;
  cohen_kappa: number | null;
  cohen_kappa_unweighted?: number | null;
  kappa_type?: string;
  kappa_interpretation: string;
  undertriage_rate?: number | null;
  overtriage_rate?: number | null;
  critical_cases?: number;
  critical_sensitivity?: number | null;
  critical_undertriage_count?: number;
  confusion_matrix?: number[][];
  modified_count: number;
  unmodified_count: number;
  distribution_ai: Record<number, number>;
  distribution_physician: Record<number, number>;
  total_tokens_consumed?: number;
  cached_triages_count?: number;
  clinical_cache_stats?: CacheStats;
  recent_evaluations: EvaluationItem[];
  reference_validation?: ReferenceValidation;
}

const pct = (value: number | null | undefined) => (value != null ? `${value}%` : NO_DATA);

const REFERENCE_ROWS: { key: keyof ReferenceAgreement; label: string; format: (v: ReferenceAgreement) => string }[] = [
  { key: 'exact_agreement', label: 'Concordancia exacta', format: (v) => pct(v.exact_agreement) },
  { key: 'cohen_kappa', label: 'Kappa ponderado', format: (v) => (v.cohen_kappa != null ? String(v.cohen_kappa) : NO_DATA) },
  { key: 'undertriage_rate', label: 'Infratriaje', format: (v) => pct(v.undertriage_rate) },
  { key: 'overtriage_rate', label: 'Sobretriaje', format: (v) => pct(v.overtriage_rate) },
  { key: 'critical_sensitivity', label: 'Sensibilidad niveles I-II', format: (v) => pct(v.critical_sensitivity) },
];

const NO_DATA = '—';

const ROMAN_LEVELS = ['', 'I', 'II', 'III', 'IV', 'V'];
const LEVEL_NAMES = ['', 'Resucitacion', 'Emergencia', 'Urgencia', 'Urgencia Menor', 'No Urgente'];
const LEVEL_COLORS = [
  '',
  'bg-red-500/15 text-red-300 border-red-500/30',
  'bg-orange-500/15 text-orange-300 border-orange-500/30',
  'bg-amber-500/15 text-amber-300 border-amber-500/30',
  'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
  'bg-sky-500/15 text-sky-300 border-sky-500/30'
];

export default function MetricsDashboard() {
  const [metrics, setMetrics] = useState<MetricsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchMetrics = useCallback(async () => {
    try {
      const res = await fetchWithAuth('/api/triage/sessions/evaluation_metrics/');
      if (res.ok) {
        const data = await res.json();
        setMetrics(data);
      }
    } catch (err) {
      console.error('Error cargando metricas:', err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchMetrics();
  }, [fetchMetrics]);

  const handleRefresh = () => {
    setRefreshing(true);
    fetchMetrics();
  };

  if (loading) {
    return (
      <div className="flex h-full w-full items-center justify-center bg-slate-900/90 border border-slate-800/80 rounded-2xl p-6 backdrop-blur-md">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-emerald-500/30 border-t-emerald-500 rounded-full animate-spin" />
          <p className="text-xs font-mono uppercase tracking-widest text-slate-400">
            Calculando metricas de concordancia clinica...
          </p>
        </div>
      </div>
    );
  }

  const distAi = metrics?.distribution_ai || { 1: 0, 2: 0, 3: 0, 4: 0, 5: 0 };
  const distPhy = metrics?.distribution_physician || { 1: 0, 2: 0, 3: 0, 4: 0, 5: 0 };
  const maxBarCount = Math.max(
    ...Object.values(distAi),
    ...Object.values(distPhy),
    1
  );

  return (
    <div className="flex flex-col h-full w-full bg-slate-900/90 border border-slate-800/80 rounded-2xl p-4 md:p-6 overflow-y-auto space-y-6 shadow-xl backdrop-blur-md">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pb-5 border-b border-slate-800/80">
        <div className="flex items-center gap-3.5">
          <div className="p-2.5 bg-emerald-500/10 rounded-xl border border-emerald-500/20 text-emerald-400 shrink-0">
            <BarChart3 className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-base md:text-lg font-semibold text-slate-100 flex items-center gap-2.5 flex-wrap">
              <span>Panel de Evaluacion Clinica y Metricas de Triaje</span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-medium">
                Auditoria Activa
              </span>
            </h1>
            <p className="text-xs text-slate-400 mt-0.5">
              Analisis matematico de concordancia Humano-IA, deriva de severidad y desempeno del modelo.
            </p>
          </div>
        </div>

        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className="flex items-center gap-1.5 px-3.5 py-2 bg-slate-800/80 hover:bg-slate-700 text-slate-200 rounded-xl text-xs font-semibold border border-slate-700/60 transition-colors shrink-0 shadow-sm"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin text-emerald-400' : ''}`} />
          <span>{refreshing ? 'Actualizando...' : 'Recalcular Metricas'}</span>
        </button>
      </div>

      {/* Validacion contra referencia ciega (sin sesgo de anclaje) */}
      <div className="bg-slate-950/70 border border-sky-500/20 rounded-2xl p-5 space-y-4" data-testid="reference-validation">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 pb-3 border-b border-slate-800/80">
          <div>
            <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-200 flex items-center gap-2">
              <GitCompare className="w-4 h-4 text-sky-400" />
              <span>Validación contra nivel de referencia ciego</span>
            </h2>
            <p className="text-[11px] text-slate-400 mt-0.5">
              Un clínico distinto al tratante asigna el nivel viendo solo la transcripción. Es la referencia válida para la evaluación:
              las métricas de abajo usan el nivel final, fijado después de ver la propuesta de la IA, y por eso tienden a sobrestimar la concordancia.
            </p>
          </div>
          <span className="text-[10px] font-mono px-2.5 py-1 rounded-full bg-sky-500/10 text-sky-300 border border-sky-500/20 shrink-0 font-medium">
            {metrics?.reference_validation?.referenced_count ?? 0} de {metrics?.total_triages ?? 0} casos adjudicados
          </span>
        </div>

        {metrics?.reference_validation && metrics.reference_validation.referenced_count > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left text-slate-400 font-medium text-[11px] pb-2">
                  <th className="py-2 pr-4 font-semibold">Métrica</th>
                  <th className="py-2 pr-4 font-semibold">IA vs referencia</th>
                  <th className="py-2 font-semibold">Médico tratante vs referencia</th>
                </tr>
              </thead>
              <tbody className="font-mono text-slate-200">
                {REFERENCE_ROWS.map((row) => (
                  <tr key={row.key} className="border-t border-slate-800/70">
                    <td className="py-2.5 pr-4 font-sans text-slate-300 font-medium">{row.label}</td>
                    <td className="py-2.5 pr-4 font-semibold text-sky-300">{row.format(metrics.reference_validation!.ai_vs_reference)}</td>
                    <td className="py-2.5 font-semibold text-emerald-300">{row.format(metrics.reference_validation!.physician_vs_reference)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-[11px] text-slate-400">
            Aún no hay casos adjudicados. Use el módulo &quot;Validacion Ciega&quot; para asignar niveles de referencia.
          </p>
        )}
      </div>

      {/* Metricas contra el nivel final del medico (con sesgo de anclaje) */}
      <div className="flex items-center gap-2 text-[11px] text-slate-400" data-testid="anchored-metrics-note">
        <AlertTriangle className="w-3.5 h-3.5 text-amber-400 shrink-0" />
        <span>Concordancia con el nivel final del médico tratante, que vio la propuesta de la IA (sesgo de anclaje).</span>
      </div>

      {/* Primary KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Concordance Rate */}
        <div className="bg-slate-950/70 border border-slate-800/80 rounded-2xl p-4 flex flex-col justify-between hover:border-slate-700 transition-colors">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-300 flex items-center gap-1.5">
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              <span>Concordancia Humano-IA</span>
            </span>
            <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 font-mono font-medium border border-emerald-500/20">
              Meta: &gt;75%
            </span>
          </div>
          <div className="mt-4">
            <div className="text-3xl font-semibold font-mono text-slate-100 tracking-tight">
              {metrics?.concordance_rate != null ? `${metrics.concordance_rate}%` : NO_DATA}
            </div>
            <p className="text-[11px] text-slate-400 mt-1">
              {metrics?.unmodified_count ?? 0} de {metrics?.total_triages ?? 0} clasificaciones sin discrepancia.
            </p>
          </div>
        </div>

        {/* Cohen's Kappa */}
        <div className="bg-slate-950/70 border border-slate-800/80 rounded-2xl p-4 flex flex-col justify-between hover:border-slate-700 transition-colors">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-300 flex items-center gap-1.5">
              <ShieldCheck className="w-4 h-4 text-sky-400" />
              <span>Kappa Ponderado (Cuadratico)</span>
            </span>
            <span className="text-[10px] px-2 py-0.5 rounded-full bg-sky-500/10 text-sky-400 font-mono font-medium border border-sky-500/20">
              K sin ponderar = {metrics?.cohen_kappa_unweighted ?? NO_DATA}
            </span>
          </div>
          <div className="mt-4">
            <div className="text-3xl font-semibold font-mono text-sky-400 tracking-tight">
              {metrics?.cohen_kappa ?? NO_DATA}
            </div>
            <p className="text-[11px] text-slate-400 mt-1">
              {metrics?.kappa_interpretation || 'Concordancia clinica analizada'}
            </p>
          </div>
        </div>

        {/* Severity Drift */}
        <div className="bg-slate-950/70 border border-slate-800/80 rounded-2xl p-4 flex flex-col justify-between hover:border-slate-700 transition-colors">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-300 flex items-center gap-1.5">
              <TrendingUp className="w-4 h-4 text-amber-400" />
              <span>Deriva de Severidad</span>
            </span>
            <span className={`text-[10px] px-2 py-0.5 rounded-full font-mono font-medium border ${
              (metrics?.severity_drift ?? 0) < 0 
                ? 'bg-rose-500/10 text-rose-400 border-rose-500/20' 
                : 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
            }`}>
              {(metrics?.severity_drift ?? 0) < 0 ? 'Mayor Urgencia' : 'Menor Urgencia'}
            </span>
          </div>
          <div className="mt-4">
            <div className="text-3xl font-semibold font-mono text-amber-400 tracking-tight">
              {metrics?.severity_drift == null ? NO_DATA : metrics.severity_drift > 0 ? `+${metrics.severity_drift}` : metrics.severity_drift}
            </div>
            <p className="text-[11px] text-slate-400 mt-1">
              Desviacion neta promedio de niveles respecto a recomendacion IA.
            </p>
          </div>
        </div>

        {/* Symptom Retention */}
        <div className="bg-slate-950/70 border border-slate-800/80 rounded-2xl p-4 flex flex-col justify-between hover:border-slate-700 transition-colors">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-300 flex items-center gap-1.5">
              <Activity className="w-4 h-4 text-purple-400" />
              <span>Retencion de Sintomas</span>
            </span>
            <span className="text-[10px] px-2 py-0.5 rounded-full bg-purple-500/10 text-purple-400 font-mono font-medium border border-purple-500/20">
              Meta: &gt;90%
            </span>
          </div>
          <div className="mt-4">
            <div className="text-3xl font-semibold font-mono text-purple-400 tracking-tight">
              {metrics?.symptom_retention != null ? `${metrics.symptom_retention}%` : NO_DATA}
            </div>
            <p className="text-[11px] text-slate-400 mt-1">
              Entidades clinicas extraidas por el modelo retenidas por el personal.
            </p>
          </div>
        </div>
      </div>

      {/* Triage Safety KPIs (referencia: nivel final ratificado por el medico) */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-slate-950/70 border border-red-500/30 rounded-2xl p-4.5">
          <span className="text-xs font-medium text-slate-300 flex items-center gap-1.5">
            <AlertTriangle className="w-4 h-4 text-red-400" />
            <span>Infratriaje IA</span>
          </span>
          <div className="text-3xl font-semibold font-mono text-red-400 mt-3 tracking-tight">
            {metrics?.undertriage_rate != null ? `${metrics.undertriage_rate}%` : NO_DATA}
          </div>
          <p className="text-[11px] text-slate-400 mt-1">
            Casos en que la IA asigno menor urgencia que el medico.
          </p>
        </div>

        <div className="bg-slate-950/70 border border-slate-800/80 rounded-2xl p-4.5">
          <span className="text-xs font-medium text-slate-300 flex items-center gap-1.5">
            <TrendingUp className="w-4 h-4 text-amber-400" />
            <span>Sobretriaje IA</span>
          </span>
          <div className="text-3xl font-semibold font-mono text-amber-400 mt-3 tracking-tight">
            {metrics?.overtriage_rate != null ? `${metrics.overtriage_rate}%` : NO_DATA}
          </div>
          <p className="text-[11px] text-slate-400 mt-1">
            Casos en que la IA asigno mayor urgencia que el medico.
          </p>
        </div>

        <div className="bg-slate-950/70 border border-slate-800/80 rounded-2xl p-4.5">
          <span className="text-xs font-medium text-slate-300 flex items-center gap-1.5">
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
            <span>Sensibilidad Niveles I-II</span>
          </span>
          <div className="text-3xl font-semibold font-mono text-emerald-400 mt-3 tracking-tight">
            {metrics?.critical_sensitivity != null ? `${metrics.critical_sensitivity}%` : NO_DATA}
          </div>
          <p className="text-[11px] text-slate-400 mt-1">
            {metrics?.critical_undertriage_count ?? 0} de {metrics?.critical_cases ?? 0} casos criticos clasificados por la IA como nivel III-V.
          </p>
        </div>
      </div>

      {/* Token Governance & Input Optimization KPIs */}
      <div className="bg-slate-950/70 border border-slate-800/80 rounded-2xl p-5 space-y-4">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 pb-3 border-b border-slate-800/80">
          <div>
            <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-200 flex items-center gap-2">
              <Cpu className="w-4 h-4 text-teal-400" />
              <span>Gobernanza de Tokens y Optimización de Entrada LLM (RAG & Caché Semántico)</span>
            </h2>
            <p className="text-[11px] text-slate-400 mt-0.5">
              Métricas de compresión de contexto, decodificación estructurada Pydantic y ahorro de cómputo en urgencias.
            </p>
          </div>
          <span className="text-[10px] font-mono px-2.5 py-1 rounded-full bg-teal-500/10 text-teal-400 border border-teal-500/20 font-medium">
            Pydantic v2 + Gemini Structured Output
          </span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3.5 pt-1">
          <div className="bg-slate-900/70 rounded-xl p-3.5 border border-slate-800/80">
            <div className="text-[10px] text-slate-400 uppercase tracking-wider font-mono">Tokens Consumidos</div>
            <div className="text-xl font-bold font-mono text-teal-300 mt-1">
              {(metrics?.total_tokens_consumed ?? 0).toLocaleString()}
            </div>
            <div className="text-[10px] text-slate-400 mt-0.5">En inferencias de triaje</div>
          </div>
          <div className="bg-slate-900/70 rounded-xl p-3.5 border border-slate-800/80">
            <div className="text-[10px] text-slate-400 uppercase tracking-wider font-mono">Triajes en Caché</div>
            <div className="text-xl font-bold font-mono text-emerald-400 mt-1">
              {metrics?.cached_triages_count ?? 0}
            </div>
            <div className="text-[10px] text-slate-400 mt-0.5">Servidos desde la caché, sin tokens</div>
          </div>
          <div className="bg-slate-900/70 rounded-xl p-3.5 border border-slate-800/80">
            <div className="text-[10px] text-slate-400 uppercase tracking-wider font-mono">Aciertos de Caché</div>
            <div className="text-xl font-bold font-mono text-sky-400 mt-1">
              {metrics?.clinical_cache_stats?.hit_rate_pct ?? 0}%
            </div>
            <div className="text-[10px] text-slate-400 mt-0.5">
              {metrics?.clinical_cache_stats?.hits ?? 0} de {metrics?.clinical_cache_stats?.total_requests ?? 0} consultas
            </div>
          </div>
          <div className="bg-slate-900/70 rounded-xl p-3.5 border border-slate-800/80">
            <div className="text-[10px] text-slate-400 uppercase tracking-wider font-mono">Tokens Ahorrados</div>
            <div className="text-xl font-bold font-mono text-purple-400 mt-1">
              {(metrics?.clinical_cache_stats?.estimated_tokens_saved ?? 0).toLocaleString()}
            </div>
            <div className="text-[10px] text-slate-400 mt-0.5">Por deduplicación canónica</div>
          </div>
        </div>
      </div>

      {/* Comparative Distribution: AI vs Physician */}
      <div className="bg-slate-950/70 border border-slate-800/80 rounded-2xl p-5 space-y-4">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 pb-3 border-b border-slate-800/80">
          <div>
            <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-200 flex items-center gap-2">
              <GitCompare className="w-4 h-4 text-sky-400" />
              <span>Distribucion Comparativa por Niveles de Triaje (I al V)</span>
            </h2>
            <p className="text-[11px] text-slate-400 mt-0.5">
              Comparativa de volumen de pacientes clasificados por la IA vs aprobados por el Medico.
            </p>
          </div>

          <div className="flex items-center gap-4 text-xs font-medium">
            <div className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-sky-500"></span>
              <span className="text-slate-300">Sugerencia IA</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-500"></span>
              <span className="text-slate-300">Decision Medica Final</span>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-5 gap-3 pt-1">
          {[1, 2, 3, 4, 5].map((lvl) => {
            const aiCount = distAi[lvl] || 0;
            const phyCount = distPhy[lvl] || 0;
            return (
              <div
                key={lvl}
                className="bg-slate-900/70 border border-slate-800/80 rounded-xl p-3.5 flex flex-col justify-between space-y-3"
              >
                <div className="flex items-center justify-between gap-1">
                  <span className={`text-[10px] font-bold font-mono px-2 py-0.5 rounded-full border ${LEVEL_COLORS[lvl]}`}>
                    Nivel {ROMAN_LEVELS[lvl]}
                  </span>
                  <span className="text-[10px] text-slate-400 font-medium truncate">
                    {LEVEL_NAMES[lvl]}
                  </span>
                </div>

                <div className="space-y-2 pt-1">
                  {/* AI Bar */}
                  <div>
                    <div className="flex justify-between text-[10px] text-slate-400 mb-1">
                      <span>IA</span>
                      <span className="font-mono font-bold text-slate-200">{aiCount}</span>
                    </div>
                    <div className="w-full bg-slate-950 h-2 rounded-full overflow-hidden p-0.5 border border-slate-800">
                      <div
                        className="bg-sky-500 h-full rounded-full transition-all duration-500"
                        style={{ width: `${(aiCount / maxBarCount) * 100}%` }}
                      />
                    </div>
                  </div>

                  {/* Physician Bar */}
                  <div>
                    <div className="flex justify-between text-[10px] text-slate-400 mb-1">
                      <span>Medico</span>
                      <span className="font-mono font-bold text-slate-200">{phyCount}</span>
                    </div>
                    <div className="w-full bg-slate-950 h-2 rounded-full overflow-hidden p-0.5 border border-slate-800">
                      <div
                        className="bg-emerald-500 h-full rounded-full transition-all duration-500"
                        style={{ width: `${(phyCount / maxBarCount) * 100}%` }}
                      />
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Recent Evaluations Table */}
      <div className="bg-slate-950/70 border border-slate-800/80 rounded-2xl p-5 space-y-3">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-200 flex items-center gap-2">
          <Activity className="w-4 h-4 text-emerald-400" />
          <span>Registro Reciente de Concordancia por Sesion</span>
        </h2>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-slate-800 text-slate-400 uppercase tracking-wider font-semibold text-[10px]">
                <th className="p-3">ID Sesion</th>
                <th className="p-3">Paciente</th>
                <th className="p-3">Nivel IA</th>
                <th className="p-3">Nivel Medico</th>
                <th className="p-3">Estado</th>
                <th className="p-3">Score Concordancia</th>
                <th className="p-3">Fecha</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {(!metrics?.recent_evaluations || metrics.recent_evaluations.length === 0) ? (
                <tr>
                  <td colSpan={7} className="p-6 text-center text-slate-500">
                    No hay evaluaciones registradas aun.
                  </td>
                </tr>
              ) : (
                metrics.recent_evaluations.map((ev) => (
                  <tr key={ev.id} className="hover:bg-slate-800/30 transition-colors">
                    <td className="p-3 font-mono text-slate-400">#{ev.id}</td>
                    <td className="p-3 font-medium text-slate-200">{ev.patient}</td>
                    <td className="p-3">
                      <span className={`text-[10px] font-bold font-mono px-2 py-0.5 rounded-full border ${LEVEL_COLORS[ev.ai_level]}`}>
                        Nivel {ROMAN_LEVELS[ev.ai_level]}
                      </span>
                    </td>
                    <td className="p-3">
                      <span className={`text-[10px] font-bold font-mono px-2 py-0.5 rounded-full border ${LEVEL_COLORS[ev.final_level]}`}>
                        Nivel {ROMAN_LEVELS[ev.final_level]}
                      </span>
                    </td>
                    <td className="p-3">
                      {ev.is_modified ? (
                        <span className="text-[10px] px-2.5 py-0.5 rounded-full bg-amber-500/10 text-amber-300 border border-amber-500/20 font-medium">
                          Ajustado
                        </span>
                      ) : (
                        <span className="text-[10px] px-2.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-300 border border-emerald-500/20 font-medium">
                          Concordante
                        </span>
                      )}
                    </td>
                    <td className="p-3 font-mono text-slate-200 font-semibold">
                      {ev.agreement_score}%
                    </td>
                    <td className="p-3 text-slate-400 font-mono text-[11px]">
                      {ev.date}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
