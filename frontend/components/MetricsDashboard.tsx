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
  Cpu
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
}

const NO_DATA = '—';

const ROMAN_LEVELS = ['', 'I', 'II', 'III', 'IV', 'V'];
const LEVEL_NAMES = ['', 'Resucitacion', 'Emergencia', 'Urgencia', 'Urgencia Menor', 'No Urgente'];
const LEVEL_COLORS = [
  '',
  'bg-red-500 text-red-100 border-red-500/30',
  'bg-orange-500 text-orange-100 border-orange-500/30',
  'bg-amber-500 text-amber-100 border-amber-500/30',
  'bg-emerald-500 text-emerald-100 border-emerald-500/30',
  'bg-blue-500 text-blue-100 border-blue-500/30'
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
      <div className="flex h-full w-full items-center justify-center bg-slate-900 border border-slate-800 rounded-xl p-6">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin" />
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
    <div className="flex flex-col h-full w-full bg-slate-900 border border-slate-800 rounded-xl p-6 overflow-y-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div className="flex items-center gap-3">
          <div className="p-2.5 bg-emerald-500/10 rounded-xl border border-emerald-500/20 text-emerald-400">
            <BarChart3 className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-slate-100 flex items-center gap-2">
              Panel de Evaluacion Clinica y Metricas de Triaje
              <span className="text-xs font-mono px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                Auditoria Activa
              </span>
            </h1>
            <p className="text-xs text-slate-400">
              Analisis matematico de concordancia Humano-IA, deriva de severidad y desempeno del modelo.
            </p>
          </div>
        </div>

        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className="flex items-center gap-2 px-3.5 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-xs font-semibold border border-slate-700 transition-colors"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin text-emerald-400' : ''}`} />
          {refreshing ? 'Actualizando...' : 'Recalcular Metricas'}
        </button>
      </div>

      {/* Primary KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Concordance Rate */}
        <div className="bg-slate-950/70 border border-slate-800 rounded-xl p-4 flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
              <CheckCircle2 className="w-4 h-4 text-emerald-400" /> Concordancia Humano-IA
            </span>
            <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 font-mono font-bold">
              Meta: &gt;75%
            </span>
          </div>
          <div className="mt-3">
            <div className="text-3xl font-black font-mono text-slate-100">
              {metrics?.concordance_rate != null ? `${metrics.concordance_rate}%` : NO_DATA}
            </div>
            <p className="text-[11px] text-slate-400 mt-1">
              {metrics?.unmodified_count ?? 0} de {metrics?.total_triages ?? 0} clasificaciones sin discrepancia.
            </p>
          </div>
        </div>

        {/* Cohen's Kappa */}
        <div className="bg-slate-950/70 border border-slate-800 rounded-xl p-4 flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
              <ShieldCheck className="w-4 h-4 text-blue-400" /> Kappa Ponderado (Cuadratico)
            </span>
            <span className="text-[10px] px-2 py-0.5 rounded bg-blue-500/10 text-blue-400 font-mono font-bold">
              K sin ponderar = {metrics?.cohen_kappa_unweighted ?? NO_DATA}
            </span>
          </div>
          <div className="mt-3">
            <div className="text-3xl font-black font-mono text-blue-400">
              {metrics?.cohen_kappa ?? NO_DATA}
            </div>
            <p className="text-[11px] text-slate-400 mt-1">
              {metrics?.kappa_interpretation || 'Concordancia clinica analizada'}
            </p>
          </div>
        </div>

        {/* Severity Drift */}
        <div className="bg-slate-950/70 border border-slate-800 rounded-xl p-4 flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
              <TrendingUp className="w-4 h-4 text-amber-400" /> Deriva de Severidad
            </span>
            <span className={`text-[10px] px-2 py-0.5 rounded font-mono font-bold ${
              (metrics?.severity_drift ?? 0) < 0 
                ? 'bg-red-500/10 text-red-400' 
                : 'bg-emerald-500/10 text-emerald-400'
            }`}>
              {(metrics?.severity_drift ?? 0) < 0 ? 'Mayor Urgencia' : 'Menor Urgencia'}
            </span>
          </div>
          <div className="mt-3">
            <div className="text-3xl font-black font-mono text-amber-400">
              {metrics?.severity_drift == null ? NO_DATA : metrics.severity_drift > 0 ? `+${metrics.severity_drift}` : metrics.severity_drift}
            </div>
            <p className="text-[11px] text-slate-400 mt-1">
              Desviacion neta promedio de niveles respecto a recomendacion IA.
            </p>
          </div>
        </div>

        {/* Symptom Retention */}
        <div className="bg-slate-950/70 border border-slate-800 rounded-xl p-4 flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
              <Activity className="w-4 h-4 text-purple-400" /> Retencion de Sintomas
            </span>
            <span className="text-[10px] px-2 py-0.5 rounded bg-purple-500/10 text-purple-400 font-mono font-bold">
              Meta: &gt;90%
            </span>
          </div>
          <div className="mt-3">
            <div className="text-3xl font-black font-mono text-purple-400">
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
        <div className="bg-slate-950/70 border border-red-500/30 rounded-xl p-4">
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
            <AlertTriangle className="w-4 h-4 text-red-400" /> Infratriaje IA
          </span>
          <div className="text-3xl font-black font-mono text-red-400 mt-3">
            {metrics?.undertriage_rate != null ? `${metrics.undertriage_rate}%` : NO_DATA}
          </div>
          <p className="text-[11px] text-slate-400 mt-1">
            Casos en que la IA asigno menor urgencia que el medico.
          </p>
        </div>

        <div className="bg-slate-950/70 border border-slate-800 rounded-xl p-4">
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
            <TrendingUp className="w-4 h-4 text-amber-400" /> Sobretriaje IA
          </span>
          <div className="text-3xl font-black font-mono text-amber-400 mt-3">
            {metrics?.overtriage_rate != null ? `${metrics.overtriage_rate}%` : NO_DATA}
          </div>
          <p className="text-[11px] text-slate-400 mt-1">
            Casos en que la IA asigno mayor urgencia que el medico.
          </p>
        </div>

        <div className="bg-slate-950/70 border border-slate-800 rounded-xl p-4">
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
            <ShieldCheck className="w-4 h-4 text-emerald-400" /> Sensibilidad Niveles I-II
          </span>
          <div className="text-3xl font-black font-mono text-emerald-400 mt-3">
            {metrics?.critical_sensitivity != null ? `${metrics.critical_sensitivity}%` : NO_DATA}
          </div>
          <p className="text-[11px] text-slate-400 mt-1">
            {metrics?.critical_undertriage_count ?? 0} de {metrics?.critical_cases ?? 0} casos criticos clasificados por la IA como nivel III-V.
          </p>
        </div>
      </div>

      {/* Token Governance & Input Optimization KPIs */}
      <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-5 space-y-4">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 pb-3 border-b border-slate-800">
          <div>
            <h2 className="text-xs font-bold uppercase tracking-wider text-slate-200 flex items-center gap-2">
              <Cpu className="w-4 h-4 text-cyan-400" />
              Gobernanza de Tokens y Optimización de Entrada LLM (RAG & Caché Semántico)
            </h2>
            <p className="text-[11px] text-slate-400">
              Métricas de compresión de contexto, decodificación estructurada Pydantic y ahorro de cómputo en urgencias.
            </p>
          </div>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
            Pydantic v2 + Gemini Structured Output
          </span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 pt-1">
          <div className="bg-slate-900/80 rounded-lg p-3 border border-slate-800/80">
            <div className="text-[10px] text-slate-400 uppercase tracking-wider font-mono">Tokens Consumidos</div>
            <div className="text-xl font-bold font-mono text-cyan-300 mt-1">
              {(metrics?.total_tokens_consumed ?? 0).toLocaleString()}
            </div>
            <div className="text-[10px] text-slate-500 mt-0.5">En inferencias de triaje</div>
          </div>
          <div className="bg-slate-900/80 rounded-lg p-3 border border-slate-800/80">
            <div className="text-[10px] text-slate-400 uppercase tracking-wider font-mono">Triajes en Caché</div>
            <div className="text-xl font-bold font-mono text-emerald-400 mt-1">
              {metrics?.cached_triages_count ?? 0}
            </div>
            <div className="text-[10px] text-slate-500 mt-0.5">Respuestas sub-3ms a 0 tokens</div>
          </div>
          <div className="bg-slate-900/80 rounded-lg p-3 border border-slate-800/80">
            <div className="text-[10px] text-slate-400 uppercase tracking-wider font-mono">Aciertos de Caché</div>
            <div className="text-xl font-bold font-mono text-blue-400 mt-1">
              {metrics?.clinical_cache_stats?.hit_rate_pct ?? 0}%
            </div>
            <div className="text-[10px] text-slate-500 mt-0.5">
              {metrics?.clinical_cache_stats?.hits ?? 0} de {metrics?.clinical_cache_stats?.total_requests ?? 0} consultas
            </div>
          </div>
          <div className="bg-slate-900/80 rounded-lg p-3 border border-slate-800/80">
            <div className="text-[10px] text-slate-400 uppercase tracking-wider font-mono">Tokens Ahorrados</div>
            <div className="text-xl font-bold font-mono text-purple-400 mt-1">
              {(metrics?.clinical_cache_stats?.estimated_tokens_saved ?? 0).toLocaleString()}
            </div>
            <div className="text-[10px] text-slate-500 mt-0.5">Por deduplicación canónica</div>
          </div>
        </div>
      </div>

      {/* Comparative Distribution: AI vs Physician */}
      <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-5 space-y-4">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 pb-3 border-b border-slate-800">
          <div>
            <h2 className="text-xs font-bold uppercase tracking-wider text-slate-200 flex items-center gap-2">
              <GitCompare className="w-4 h-4 text-blue-400" />
              Distribucion Comparativa por Niveles de Triaje (I al V)
            </h2>
            <p className="text-[11px] text-slate-400">
              Comparativa de volumen de pacientes clasificados por la IA vs aprobados por el Medico.
            </p>
          </div>

          <div className="flex items-center gap-4 text-xs">
            <div className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded bg-blue-500"></span>
              <span className="text-slate-300">Sugerencia IA</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded bg-emerald-500"></span>
              <span className="text-slate-300">Decision Medica Final</span>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-5 gap-3 pt-2">
          {[1, 2, 3, 4, 5].map((lvl) => {
            const aiCount = distAi[lvl] || 0;
            const phyCount = distPhy[lvl] || 0;
            return (
              <div
                key={lvl}
                className="bg-slate-900/80 border border-slate-800 rounded-xl p-3 flex flex-col justify-between space-y-2"
              >
                <div className="flex items-center justify-between">
                  <span className={`text-[10px] font-bold px-2 py-0.5 rounded border ${LEVEL_COLORS[lvl]}`}>
                    Nivel {ROMAN_LEVELS[lvl]}
                  </span>
                  <span className="text-[10px] text-slate-400 font-medium truncate">
                    {LEVEL_NAMES[lvl]}
                  </span>
                </div>

                <div className="space-y-1.5 pt-2">
                  {/* AI Bar */}
                  <div>
                    <div className="flex justify-between text-[10px] text-slate-400 mb-0.5">
                      <span>IA</span>
                      <span className="font-mono font-bold text-slate-200">{aiCount}</span>
                    </div>
                    <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
                      <div
                        className="bg-blue-500 h-full rounded-full transition-all duration-500"
                        style={{ width: `${(aiCount / maxBarCount) * 100}%` }}
                      />
                    </div>
                  </div>

                  {/* Physician Bar */}
                  <div>
                    <div className="flex justify-between text-[10px] text-slate-400 mb-0.5">
                      <span>Medico</span>
                      <span className="font-mono font-bold text-slate-200">{phyCount}</span>
                    </div>
                    <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
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
      <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-5 space-y-3">
        <h2 className="text-xs font-bold uppercase tracking-wider text-slate-200 flex items-center gap-2">
          <Activity className="w-4 h-4 text-emerald-400" />
          Registro Reciente de Concordancia por Sesion
        </h2>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-slate-800 text-slate-400 uppercase tracking-wider font-semibold text-[10px]">
                <th className="p-2.5">ID Sesion</th>
                <th className="p-2.5">Paciente</th>
                <th className="p-2.5">Nivel IA</th>
                <th className="p-2.5">Nivel Medico</th>
                <th className="p-2.5">Estado</th>
                <th className="p-2.5">Score Concordancia</th>
                <th className="p-2.5">Fecha</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {(!metrics?.recent_evaluations || metrics.recent_evaluations.length === 0) ? (
                <tr>
                  <td colSpan={7} className="p-4 text-center text-slate-500">
                    No hay evaluaciones registradas aun.
                  </td>
                </tr>
              ) : (
                metrics.recent_evaluations.map((ev) => (
                  <tr key={ev.id} className="hover:bg-slate-800/30 transition-colors">
                    <td className="p-2.5 font-mono text-slate-400">#{ev.id}</td>
                    <td className="p-2.5 font-medium text-slate-200">{ev.patient}</td>
                    <td className="p-2.5">
                      <span className={`text-[10px] font-bold px-2 py-0.5 rounded border ${LEVEL_COLORS[ev.ai_level]}`}>
                        Nivel {ROMAN_LEVELS[ev.ai_level]}
                      </span>
                    </td>
                    <td className="p-2.5">
                      <span className={`text-[10px] font-bold px-2 py-0.5 rounded border ${LEVEL_COLORS[ev.final_level]}`}>
                        Nivel {ROMAN_LEVELS[ev.final_level]}
                      </span>
                    </td>
                    <td className="p-2.5">
                      {ev.is_modified ? (
                        <span className="text-[10px] px-2 py-0.5 rounded bg-amber-500/10 text-amber-300 border border-amber-500/20 font-semibold">
                          Ajustado
                        </span>
                      ) : (
                        <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-300 border border-emerald-500/20 font-semibold">
                          Concordante
                        </span>
                      )}
                    </td>
                    <td className="p-2.5 font-mono text-slate-300 font-bold">
                      {ev.agreement_score}%
                    </td>
                    <td className="p-2.5 text-slate-400 font-mono text-[11px]">
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
