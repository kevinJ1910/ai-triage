'use client';

import React, { useState } from 'react';
import { RefreshCw, ArrowRight, Check, Copy, Sparkles, BookOpen, AlertCircle, Database } from 'lucide-react';

interface MappingItem {
  raw_term: string;
  medical_term: string;
  code_snomed: string;
  category: string;
}

interface NormalizationResponse {
  normalized_text: string;
  summary: string;
  mappings: MappingItem[];
  error?: string;
}

const PRESET_CASES = [
  {
    title: 'Caso Cardiopulmonar',
    text: 'Siento que me aprieta el pecho y me falta el aire. Yo tomo posartan pa la presion alta y tengo sudor frio desde hace 2 horas.'
  },
  {
    title: 'Caso Respiratorio Agudo',
    text: 'Al paciente le chilla el pecho y tiene calentura. Dice que tiene fatiga y no puede dormir bien por el ahogo.'
  },
  {
    title: 'Caso Gastrointestinal / Metabolico',
    text: 'Tengo dolor en la boca del estomago con mareo continuo. Se me olvido la pastilla pal azucar y tengo palpitaciones.'
  }
];

export default function NormalizationMonitor() {
  const [rawText, setRawText] = useState(PRESET_CASES[0].text);
  const [normalizedData, setNormalizedData] = useState<NormalizationResponse | null>({
    normalized_text: 'Siento opresion toracica y disnea de medianos esfuerzos. Refiere tratamiento con losartan potasico por antecedente de hipertension arterial sistemica, acompanado de diaforesis profusa de 2 horas de evolucion.',
    summary: 'Sindrome coronario agudo probable con compromiso hemodinamico y antecedentes cardiovasculares.',
    mappings: [
      { raw_term: 'aprieta el pecho', medical_term: 'opresion toracica', code_snomed: '29857009', category: 'Sintoma' },
      { raw_term: 'falta el aire', medical_term: 'disnea de medianos esfuerzos', code_snomed: '267036007', category: 'Sintoma' },
      { raw_term: 'posartan', medical_term: 'losartan potasico', code_snomed: '318851002', category: 'Medicamento' },
      { raw_term: 'presion alta', medical_term: 'hipertension arterial sistemica', code_snomed: '38341003', category: 'Antecedente' },
      { raw_term: 'sudor frio', medical_term: 'diaforesis profusa', code_snomed: '52613005', category: 'Signo' }
    ]
  });
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);
  const [filterCategory, setFilterCategory] = useState('ALL');
  const [errorMsg, setErrorMsg] = useState('');

  const handleNormalize = async () => {
    if (!rawText.trim()) return;
    setLoading(true);
    setErrorMsg('');
    try {
      const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null;
      const headers: Record<string, string> = { 'Content-Type': 'application/json' };
      if (token) headers['Authorization'] = 'Bearer ' + token;

      const res = await fetch('/api/transcribe/normalize/', {
        method: 'POST',
        headers,
        body: JSON.stringify({ raw_text: rawText })
      });

      if (!res.ok) {
        throw new Error('Error en el servicio de normalizacion (' + res.status + ')');
      }

      const data: NormalizationResponse = await res.json();
      setNormalizedData(data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Fallo de conexion';
      setErrorMsg(msg);
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = () => {
    if (!normalizedData?.normalized_text) return;
    navigator.clipboard.writeText(normalizedData.normalized_text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const filteredMappings = normalizedData?.mappings.filter(m => {
    if (filterCategory === 'ALL') return true;
    return m.category.toLowerCase() === filterCategory.toLowerCase();
  }) || [];

  return (
    <div className="flex flex-col h-full w-full bg-slate-900 border border-slate-800 rounded-xl p-6 overflow-y-auto space-y-6">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div className="flex items-center gap-3">
          <div className="p-2.5 bg-purple-500/10 rounded-xl border border-purple-500/20 text-purple-400">
            <RefreshCw className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-slate-100 flex items-center gap-2">
              Motor de Normalizacion Clinica
              <span className="text-xs font-mono px-2 py-0.5 rounded bg-purple-500/20 text-purple-300 border border-purple-500/30">
                SNOMED-CT / CIE-10
              </span>
            </h1>
            <p className="text-xs text-slate-400">
              Conversion semantica de relatos coloquiales a terminologia medica estructurada de urgencias.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="flex items-center gap-1.5 text-xs text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-3 py-1 rounded-full font-medium">
            <Database className="w-3.5 h-3.5" /> Ontologia Activa
          </span>
        </div>
      </div>

      <div className="space-y-2">
        <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
          <BookOpen className="w-3.5 h-3.5 text-slate-400" /> Casos Clinicos Predefinidos:
        </label>
        <div className="flex flex-wrap gap-2">
          {PRESET_CASES.map((preset, idx) => (
            <button
              key={idx}
              onClick={() => setRawText(preset.text)}
              className="text-xs px-3 py-1.5 rounded-lg bg-slate-800/80 hover:bg-slate-800 text-slate-300 border border-slate-700 hover:border-purple-500/50 transition-colors"
            >
              {preset.title}
            </button>
          ))}
        </div>
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
            Texto Crudo del Paciente / Transcripcion ASR
          </label>
          <span className="text-xs text-slate-500">{rawText.length} caracteres</span>
        </div>
        <textarea
          value={rawText}
          onChange={(e) => setRawText(e.target.value)}
          rows={3}
          placeholder="Ingrese la declaracion verbal del paciente o transcripcion ASR..."
          className="w-full px-4 py-3 bg-slate-950/80 border border-slate-800 rounded-lg text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-purple-500 transition-colors"
        />
        <div className="flex justify-end">
          <button
            onClick={handleNormalize}
            disabled={loading || !rawText.trim()}
            className="flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-white rounded-lg text-xs font-semibold transition-all shadow-lg shadow-purple-600/20"
          >
            {loading ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin" />
                Normalizando con IA...
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4" />
                Normalizar Terminologia
              </>
            )}
          </button>
        </div>
      </div>

      {errorMsg && (
        <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-xs text-red-400 flex items-center gap-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          {errorMsg}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-slate-950/50 rounded-xl border border-slate-800 p-4 flex flex-col space-y-3">
          <div className="flex items-center justify-between pb-2 border-b border-slate-800/80">
            <h2 className="text-xs font-bold uppercase tracking-wider text-rose-400 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-rose-500"></span>
              Entrada Coloquial (Crudo)
            </h2>
            <span className="text-[10px] text-slate-500 uppercase font-mono">Entrada</span>
          </div>
          <div className="flex-1 p-3 bg-slate-900/90 rounded-lg border border-slate-800/60 font-serif text-sm leading-relaxed text-slate-300 italic min-h-[100px]">
            {rawText || <span className="text-slate-600 not-italic">Sin texto de entrada</span>}
          </div>
        </div>

        <div className="bg-slate-950/50 rounded-xl border border-slate-800 p-4 flex flex-col space-y-3">
          <div className="flex items-center justify-between pb-2 border-b border-slate-800/80">
            <h2 className="text-xs font-bold uppercase tracking-wider text-emerald-400 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
              Salida Clinica Estandarizada
            </h2>
            <button
              onClick={handleCopy}
              className="flex items-center gap-1 text-[11px] text-slate-400 hover:text-slate-200 transition-colors bg-slate-800/60 px-2 py-1 rounded border border-slate-700"
            >
              {copied ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
              {copied ? 'Copiado' : 'Copiar'}
            </button>
          </div>
          <div className="flex-1 p-3 bg-slate-900/90 rounded-lg border border-slate-800/60 font-serif text-sm leading-relaxed text-slate-200 italic min-h-[100px]">
            {normalizedData?.normalized_text || (
              <span className="text-slate-600 not-italic">Esperando normalizacion...</span>
            )}
          </div>
          {normalizedData?.summary && (
            <div className="p-2.5 bg-purple-500/10 border border-purple-500/20 rounded-lg text-xs text-purple-300">
              <span className="font-bold text-purple-200">Sintesis Clinica: </span>
              {normalizedData.summary}
            </div>
          )}
        </div>
      </div>

      {normalizedData && normalizedData.mappings && (
        <div className="bg-slate-950/50 rounded-xl border border-slate-800 p-4 space-y-4">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 pb-3 border-b border-slate-800">
            <div>
              <h2 className="text-xs font-bold uppercase tracking-wider text-slate-200 flex items-center gap-2">
                Tabla de Mapeo Ontologico SNOMED-CT / CIE-10
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-slate-800 text-slate-400 border border-slate-700">
                  {filteredMappings.length} entidades
                </span>
              </h2>
            </div>
            <div className="flex items-center gap-1.5">
              {['ALL', 'Sintoma', 'Signo', 'Medicamento', 'Antecedente'].map((cat) => (
                <button
                  key={cat}
                  onClick={() => setFilterCategory(cat)}
                  className={`text-[10px] px-2 py-1 rounded transition-colors ${
                    filterCategory === cat
                      ? 'bg-purple-600 text-white font-bold'
                      : 'bg-slate-800 text-slate-400 hover:text-slate-200'
                  }`}
                >
                  {cat === 'ALL' ? 'Todos' : cat}
                </button>
              ))}
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400 uppercase tracking-wider font-semibold text-[10px]">
                  <th className="p-2.5">Termino Coloquial Detectado</th>
                  <th className="p-2.5"></th>
                  <th className="p-2.5">Termino Medico Estandarizado</th>
                  <th className="p-2.5">Codigo SNOMED-CT</th>
                  <th className="p-2.5">Categoria</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {filteredMappings.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="p-4 text-center text-slate-500">
                      No se encontraron entidades para esta categoria.
                    </td>
                  </tr>
                ) : (
                  filteredMappings.map((m, idx) => (
                    <tr key={idx} className="hover:bg-slate-800/30 transition-colors">
                      <td className="p-2.5 font-medium text-rose-300 font-mono">{m.raw_term}</td>
                      <td className="p-2.5 text-slate-600"><ArrowRight className="w-3.5 h-3.5" /></td>
                      <td className="p-2.5 font-bold text-emerald-300">{m.medical_term}</td>
                      <td className="p-2.5 font-mono text-slate-300 bg-slate-900/60 px-2 rounded">
                        {m.code_snomed || 'N/A'}
                      </td>
                      <td className="p-2.5">
                        <span
                          className={`text-[10px] px-2 py-0.5 rounded font-medium border ${
                            m.category === 'Sintoma'
                              ? 'bg-amber-500/10 text-amber-300 border-amber-500/20'
                              : m.category === 'Signo'
                              ? 'bg-red-500/10 text-red-300 border-red-500/20'
                              : m.category === 'Medicamento'
                              ? 'bg-blue-500/10 text-blue-300 border-blue-500/20'
                              : 'bg-purple-500/10 text-purple-300 border-purple-500/20'
                          }`}
                        >
                          {m.category}
                        </span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
