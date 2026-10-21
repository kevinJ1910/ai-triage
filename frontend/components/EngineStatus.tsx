'use client';

import { useCallback, useEffect, useState } from 'react';
import { fetchWithAuth } from '@/lib/api';

interface EngineStatusData {
  inference_mode: string;
  asr: {
    model_loaded: boolean;
    loading?: boolean;
    model_size?: string | null;
    device?: string | null;
    configured?: string;
    requested?: string | null;
  };
  ner: { model_loaded: boolean; active?: boolean; mode?: string; engine?: string | null; detail?: string };
  llm: { configured: boolean; model?: string };
}

type RowState = 'ok' | 'warn' | 'info';

interface Row {
  key: string;
  label: string;
  state: RowState;
  text: string;
  title: string;
}

// Lo emite ConfigPanel al guardar los motores, para que el estado se refresque sin esperar al sondeo.
export const ENGINES_CHANGED_EVENT = 'ai-triage-engines-changed';

const REFRESH_MS = 60_000;
// Mientras Whisper se recarga (o descarga un modelo nuevo) se consulta mas a menudo.
const LOADING_REFRESH_MS = 5_000;

const DOT: Record<RowState, string> = { ok: 'bg-emerald-500', warn: 'bg-amber-500', info: 'bg-sky-500' };

function asrPending(asr: EngineStatusData['asr']): boolean {
  if (asr.loading) return true;
  // Un modelo elegido explicitamente que el worker aun no ha intentado cargar: la recarga esta en cola.
  return !!asr.configured && asr.configured !== 'auto' && !!asr.requested && asr.configured !== asr.requested;
}

// Se pidio un modelo pero se cargo otro (respaldo tras un fallo, p. ej. falta de memoria).
function asrFellBack(asr: EngineStatusData['asr']): boolean {
  return asr.model_loaded && !!asr.requested && !!asr.model_size && asr.requested !== asr.model_size;
}

function rows(data: EngineStatusData): Row[] {
  const { asr, ner } = data;
  const nerActive = ner.active ?? ner.model_loaded;
  const asrRow: Row = asrPending(asr)
    ? {
      key: 'asr', label: 'ASR', state: 'warn',
      text: `Cargando Whisper ${asr.configured && asr.configured !== 'auto' ? asr.configured : asr.model_size ?? ''}…`,
      title: 'El worker ASR está cargando el modelo elegido en Configuración (la primera vez puede descargarlo).',
    }
    : {
      key: 'asr', label: 'ASR', state: asr.model_loaded && !asrFellBack(asr) ? 'ok' : 'warn',
      text: asr.model_loaded ? `Whisper ${asr.model_size ?? ''} · ${(asr.device ?? '').toUpperCase()}` : 'No disponible',
      title: !asr.model_loaded
        ? 'El motor de transcripción no está cargado'
        : asrFellBack(asr)
          ? `No se pudo cargar Whisper ${asr.requested}; se usa ${asr.model_size} como respaldo`
          : 'Faster-Whisper cargado',
    };
  const nerRow: Row = ner.mode === 'catalogo'
    ? {
      key: 'ner', label: 'NER', state: 'info', text: 'Solo catálogo y LLM',
      title: 'RoBERTa desactivado en Configuración: las entidades salen del catálogo y de Gemini',
    }
    : {
      key: 'ner', label: 'NER', state: nerActive ? 'ok' : 'warn',
      text: nerActive ? 'RoBERTa clínico' : 'Respaldo (catálogo)',
      title: nerActive ? `Modelo: ${ner.engine ?? 'RoBERTa'}` : (ner.detail || 'Sin modelo NER: se usan el catálogo y el LLM'),
    };
  return [
    asrRow,
    nerRow,
    {
      key: 'llm',
      label: 'LLM',
      state: data.llm.configured ? 'ok' : 'warn',
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

  const load = useCallback(async () => {
    try {
      const res = await fetchWithAuth('/api/config/engines/');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setData(await res.json());
      setFailed(false);
    } catch {
      setFailed(true);
    }
  }, []);

  const loading = data ? asrPending(data.asr) : false;

  useEffect(() => {
    load();
    const timer = setInterval(load, loading ? LOADING_REFRESH_MS : REFRESH_MS);
    window.addEventListener(ENGINES_CHANGED_EVENT, load);
    return () => {
      clearInterval(timer);
      window.removeEventListener(ENGINES_CHANGED_EVENT, load);
    };
  }, [load, loading]);

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
          <span className={`w-2 h-2 rounded-full shrink-0 ${DOT[row.state]} ${row.state === 'warn' && row.text.startsWith('Cargando') ? 'animate-pulse' : ''}`} />
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
