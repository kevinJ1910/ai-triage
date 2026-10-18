'use client';

import { useEffect, useState } from 'react';
import { fetchWithAuth } from '@/lib/api';

interface EngineStatusData {
  inference_mode: string;
  asr: { model_loaded: boolean; model_size?: string | null; device?: string | null };
  ner: { model_loaded: boolean; mode?: string; engine?: string | null; detail?: string };
  llm: { configured: boolean; model?: string };
}

interface Row {
  key: string;
  label: string;
  ok: boolean;
  text: string;
  title: string;
}

const REFRESH_MS = 60_000;

function rows(data: EngineStatusData): Row[] {
  const asr = data.asr;
  const ner = data.ner;
  return [
    {
      key: 'asr',
      label: 'ASR',
      ok: asr.model_loaded,
      text: asr.model_loaded ? `Whisper ${asr.model_size ?? ''} · ${(asr.device ?? '').toUpperCase()}` : 'No disponible',
      title: asr.model_loaded ? 'Faster-Whisper cargado' : 'El motor de transcripción no está cargado',
    },
    {
      key: 'ner',
      label: 'NER',
      ok: ner.model_loaded,
      text: ner.model_loaded ? 'RoBERTa clínico' : 'Respaldo (catálogo)',
      title: ner.model_loaded ? `Modelo: ${ner.engine ?? 'RoBERTa'}` : (ner.detail || 'Sin modelo NER: se usan el catálogo y el LLM'),
    },
    {
      key: 'llm',
      label: 'LLM',
      ok: data.llm.configured,
      text: data.llm.configured ? (data.llm.model ?? 'Gemini') : 'Sin clave: reglas',
      title: data.llm.configured ? 'Clave de Gemini configurada' : 'Sin clave de Gemini: se aplica el motor de reglas',
    },
  ];
}

/**
 * Estado de los motores de inferencia. Explica de un vistazo por qué un resultado viene del respaldo
 * (sin modelo NER o sin clave de Gemini) o por qué no hay transcripción.
 */
export default function EngineStatus({ compact = false }: { compact?: boolean }) {
  const [data, setData] = useState<EngineStatusData | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const res = await fetchWithAuth('/api/config/engines/');
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json = await res.json();
        if (!cancelled) {
          setData(json);
          setFailed(false);
        }
      } catch {
        if (!cancelled) setFailed(true);
      }
    };
    load();
    const timer = setInterval(load, REFRESH_MS);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, []);

  if (!data) {
    return failed && !compact ? (
      <p className="px-2.5 text-[10px] text-slate-500">Estado de los motores no disponible</p>
    ) : null;
  }

  return (
    <div className={compact ? 'flex flex-col items-center gap-1.5 py-1' : 'flex flex-col gap-1 px-2.5 py-1.5'} data-testid="engine-status" aria-label="Estado de los motores">
      {!compact && <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">Motores</span>}
      {rows(data).map(row => (
        <div key={row.key} className="flex items-center gap-2 text-[10px]" title={`${row.label}: ${row.title}`}>
          <span className={`w-2 h-2 rounded-full shrink-0 ${row.ok ? 'bg-emerald-500' : 'bg-amber-500'}`} />
          {!compact && (
            <span className="truncate">
              <span className="font-semibold text-slate-300">{row.label}</span>{' '}
              <span className="text-slate-400">{row.text}</span>
            </span>
          )}
        </div>
      ))}
    </div>
  );
}
