'use client';

import { useState, useEffect, useCallback } from 'react';
import { 
  Settings, 
  Key, 
  Trash2, 
  Plus, 
  ShieldCheck, 
  Upload, 
  Check, 
  RefreshCw, 
  Cpu, 
  Sparkles, 
  Database,
  Eye,
  EyeOff,
  AlertTriangle,
  X
} from 'lucide-react';
import { toast } from 'sonner';
import { fetchWithAuth } from '@/lib/api';

interface APIKeyItem {
  id: number;
  provider: string;
  provider_display: string;
  name: string;
  masked_key: string;
  is_active: boolean;
  created_at: string;
}

interface ConfigData {
  active_asr_model: string;
  active_llm_engine: string;
  active_ner_model: string;
  snomed_version: string;
  snomed_updated_at: string;
  icd10_version: string;
  icd10_updated_at: string;
}

interface ModelOption {
  id: string;
  name: string;
  recommended?: boolean;
  type?: string;
  provider?: string;
  description?: string;
}

interface AvailableOptions {
  asr_models: ModelOption[];
  llm_engines: ModelOption[];
  ner_models: ModelOption[];
}

interface RuntimeStatus {
  cuda_available: boolean;
  hardware_device: string;
  gemini_configured: boolean;
  active_keys_count: number;
  system_timezone: string;
  ner_status?: { model_loaded: boolean; source?: string; detail?: string };
}

interface VocabItem {
  code: string;
  title: string;
  provider: string;
  updated_at: string;
  total_terms: number;
  indexed_emergency_terms: number;
  status: string;
  update_available: boolean;
  latest_release: string;
  token_notice: string;
}

interface VocabulariesData {
  snomed: VocabItem;
  icd10: VocabItem;
}

export default function ConfigPanel() {
  const [config, setConfig] = useState<ConfigData>({
    active_asr_model: 'auto',
    active_llm_engine: 'gemini-2.5-flash',
    active_ner_model: 'auto',
    snomed_version: 'SNOMED CT International Edition',
    snomed_updated_at: new Date().toISOString(),
    icd10_version: 'CIE-10 (OMS)',
    icd10_updated_at: new Date().toISOString(),
  });

  const [apiKeys, setApiKeys] = useState<APIKeyItem[]>([]);
  const [availableOptions, setAvailableOptions] = useState<AvailableOptions | null>(null);
  const [runtimeStatus, setRuntimeStatus] = useState<RuntimeStatus | null>(null);
  const [vocabularies, setVocabularies] = useState<VocabulariesData | null>(null);
  const [loading, setLoading] = useState(true);
  const [savingConfig, setSavingConfig] = useState(false);
  const [syncingVocab, setSyncingVocab] = useState<'snomed' | 'icd10' | null>(null);
  const [checkingUpdate, setCheckingUpdate] = useState<'snomed' | 'icd10' | null>(null);

  // Modal Agregar Llave
  const [showKeyModal, setShowKeyModal] = useState(false);
  const [newKeyName, setNewKeyName] = useState('');
  const [newKeyValue, setNewKeyValue] = useState('');
  const [newKeyProvider, setNewKeyProvider] = useState('auto');
  const [showPlainKey, setShowPlainKey] = useState(false);
  const [savingKey, setSavingKey] = useState(false);

  const loadConfig = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetchWithAuth('/api/config/');
      if (!res.ok) throw new Error('Error al cargar configuracion');
      const data = await res.json();
      if (data.config) setConfig(data.config);
      if (data.api_keys) setApiKeys(data.api_keys);
      if (data.available_options) setAvailableOptions(data.available_options);
      if (data.runtime_status) setRuntimeStatus(data.runtime_status);
      if (data.vocabularies) setVocabularies(data.vocabularies);
    } catch (err: any) {
      toast.error(err.message || 'No se pudo conectar con el servicio de configuracion');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadConfig();
  }, [loadConfig]);

  const handleSaveModels = async () => {
    setSavingConfig(true);
    try {
      const res = await fetchWithAuth('/api/config/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          active_asr_model: config.active_asr_model,
          active_llm_engine: config.active_llm_engine,
          active_ner_model: config.active_ner_model,
        }),
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Error al guardar');
      toast.success('Modelos de inferencia actualizados satisfactoriamente');
    } catch (err: any) {
      toast.error(err.message || 'Fallo al guardar configuracion');
    } finally {
      setSavingConfig(false);
    }
  };

  const handleDetectProvider = (val: string) => {
    const trimmed = val.trim();
    if (trimmed.startsWith('AIza') || trimmed.includes('AQ.')) return 'Google Gemini';
    if (trimmed.startsWith('sk-ant-')) return 'Anthropic Claude';
    if (trimmed.startsWith('sk-proj-') || (trimmed.startsWith('sk-') && trimmed.length > 35)) return 'OpenAI';
    if (trimmed.toLowerCase().includes('deepseek')) return 'DeepSeek';
    return 'Autodetectar';
  };

  const handleCreateKey = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newKeyValue || !newKeyName) {
      toast.error('Nombre y Llave son obligatorios');
      return;
    }

    setSavingKey(true);
    try {
      const providerParam = newKeyProvider === 'auto' ? '' : newKeyProvider;
      const res = await fetchWithAuth('/api/config/keys/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: newKeyName,
          api_key: newKeyValue,
          provider: providerParam,
        }),
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || data.api_key?.[0] || 'Error al guardar llave');

      toast.success('Llave API cifrada con AES y almacenada exitosamente');
      setShowKeyModal(false);
      setNewKeyName('');
      setNewKeyValue('');
      setNewKeyProvider('auto');
      loadConfig();
    } catch (err: any) {
      toast.error(err.message || 'Error al almacenar llave');
    } finally {
      setSavingKey(false);
    }
  };

  const handleDeleteKey = async (keyId: number, keyName: string) => {
    if (!confirm(`Confirmas eliminar la llave API "${keyName}"? Esta accion no se puede deshacer.`)) return;

    try {
      const res = await fetchWithAuth(`/api/config/keys/${keyId}/`, {
        method: 'DELETE',
      });
      if (!res.ok) throw new Error('Error al eliminar llave');

      toast.success(`Llave "${keyName}" eliminada correctamente`);
      setApiKeys(prev => prev.filter(k => k.id !== keyId));
    } catch (err: any) {
      toast.error(err.message || 'No se pudo eliminar la llave');
    }
  };

  const handleCheckUpdate = async (type: 'snomed' | 'icd10') => {
    setCheckingUpdate(type);
    try {
      const res = await fetchWithAuth('/api/config/vocabulary/sync/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ type, action: 'check_update' }),
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Fallo al verificar catalogo remoto');

      toast.info(data.message || 'Verificacion completada con exito');
      if (vocabularies) {
        setVocabularies(prev => prev ? ({
          ...prev,
          [type]: {
            ...prev[type],
            update_available: data.update_available,
            latest_release: data.latest_release,
          }
        }) : null);
      }
    } catch (err: any) {
      toast.error(err.message || 'Error al comprobar actualizaciones');
    } finally {
      setCheckingUpdate(null);
    }
  };

  const handleSyncVocab = async (type: 'snomed' | 'icd10') => {
    setSyncingVocab(type);
    try {
      const res = await fetchWithAuth('/api/config/vocabulary/sync/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ type, action: 'sync' }),
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Fallo al sincronizar vocabulario');

      toast.success(data.message || 'Vocabulario actualizado');
      if (type === 'snomed') {
        setConfig(prev => ({ ...prev, snomed_updated_at: data.snomed_updated_at }));
      } else {
        setConfig(prev => ({ ...prev, icd10_updated_at: data.icd10_updated_at }));
      }

      if (vocabularies) {
        setVocabularies(prev => prev ? ({
          ...prev,
          [type]: {
            ...prev[type],
            updated_at: data[type === 'snomed' ? 'snomed_updated_at' : 'icd10_updated_at'],
            indexed_emergency_terms: data.indexed_emergency_terms || prev[type].indexed_emergency_terms,
            update_available: false,
          }
        }) : null);
      }
    } catch (err: any) {
      toast.error(err.message || 'Error en sincronizacion');
    } finally {
      setSyncingVocab(null);
    }
  };

  const formatDate = (isoStr: string) => {
    try {
      return new Date(isoStr).toLocaleDateString('es-CO', {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
      });
    } catch {
      return 'Reciente';
    }
  };

  return (
    <div className="flex flex-col h-full w-full bg-[var(--surface-base)] border border-[var(--surface-border)] rounded-2xl p-4 sm:p-6 overflow-y-auto space-y-6 shadow-xl">
      {/* Header Configuracion */}
      <div className="flex items-center justify-between border-b border-[var(--surface-border)] pb-4 shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-sky-500/10 border border-sky-500/20 flex items-center justify-center text-sky-400">
            <Settings className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-xs sm:text-sm font-semibold uppercase text-slate-100 tracking-wide">
              Configuracion del Sistema y Motores IA
            </h2>
            <p className="text-[11px] text-slate-400">
              Parametrizacion de modelos ASR, motores LLM y gestion segura de credenciales
            </p>
          </div>
        </div>

        <button
          onClick={handleSaveModels}
          disabled={savingConfig}
          className="px-3.5 py-2 rounded-xl text-xs font-medium text-white bg-sky-600 hover:bg-sky-500 transition-colors flex items-center gap-2 shadow-sm disabled:opacity-50"
        >
          {savingConfig ? (
            <RefreshCw className="w-3.5 h-3.5 animate-spin" />
          ) : (
            <Check className="w-3.5 h-3.5" />
          )}
          Guardar Cambios
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* CARD 1: Model Management */}
        <div className="bg-[var(--surface-panel)] rounded-2xl border border-[var(--surface-border)] p-4 sm:p-5 space-y-4 shadow-sm">
          <div className="flex items-center gap-2.5 text-slate-200 pb-3 border-b border-[var(--surface-border)]">
            <Cpu className="w-4 h-4 text-sky-400" />
            <h3 className="text-xs uppercase font-semibold tracking-wider text-slate-200">
              Motores de Inferencia Clinica
            </h3>
          </div>

          <div className="space-y-4">
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">
                  Motor ASR de Transcripcion (Faster-Whisper)
                </label>
                {runtimeStatus && (
                  <span className={`px-2 py-0.5 rounded-full text-[9px] font-mono font-bold uppercase ${runtimeStatus.cuda_available ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'}`}>
                    {runtimeStatus.hardware_device}
                  </span>
                )}
              </div>
              <select
                value={config.active_asr_model}
                onChange={(e) => setConfig({ ...config, active_asr_model: e.target.value })}
                className="w-full bg-[var(--surface-card)] border border-[var(--surface-border)] rounded-xl p-2.5 text-xs text-slate-200 focus:ring-1 focus:ring-sky-500 focus:outline-none"
              >
                {(availableOptions?.asr_models || [
                  { id: 'auto', name: 'Segun entorno (WHISPER_MODEL_SIZE) - Recomendado' },
                  { id: 'large-v3-turbo', name: 'Faster-Whisper (large-v3-turbo) - Alta Precision (GPU)' },
                  { id: 'large-v3', name: 'Whisper Large V3 - Modelo Completo (Requiere GPU dedicada)' },
                  { id: 'medium', name: 'Faster-Whisper Medium - Balance Precision/Velocidad' },
                  { id: 'small', name: 'Faster-Whisper Small - Liviano / Baja Latencia' },
                  { id: 'base', name: 'Faster-Whisper Base - Modo Ahorro Recursos' },
                  { id: 'tiny', name: 'Faster-Whisper Tiny - Ultra Rapido' },
                ]).map((opt) => (
                  <option key={opt.id} value={opt.id}>
                    {opt.name}
                  </option>
                ))}
              </select>
              <span className="text-[10px] text-slate-500 mt-1.5 block leading-relaxed">
                Aceleracion por tensores CTranslate2 con soporte NVIDIA CUDA y fallback dinamico a CPU INT8. El cambio de modelo se aplica al reiniciar el worker ASR.
              </span>
            </div>

            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">
                  Motor de Explicabilidad y Triaje (LLM)
                </label>
                {runtimeStatus?.gemini_configured && (
                  <span className="px-2 py-0.5 rounded-full text-[9px] font-mono font-semibold uppercase bg-sky-500/10 text-sky-400 border border-sky-500/20">
                    Credencial Activa
                  </span>
                )}
              </div>
              <select
                value={config.active_llm_engine}
                onChange={(e) => setConfig({ ...config, active_llm_engine: e.target.value })}
                className="w-full bg-[var(--surface-card)] border border-[var(--surface-border)] rounded-xl p-2.5 text-xs text-slate-200 focus:ring-1 focus:ring-sky-500 focus:outline-none"
              >
                {(availableOptions?.llm_engines || [
                  { id: 'gemini-2.5-flash', name: 'Google Gemini 2.5 Flash - Baja Latencia Clinica (Recomendado)' },
                  { id: 'gemini-3.5-flash-lite', name: 'Google Gemini 3.5 Flash-Lite - Bajo Costo' },
                  { id: 'gemini-3.8-flash', name: 'Google Gemini 3.8 Flash' },
                ]).map((opt) => (
                  <option key={opt.id} value={opt.id}>
                    {opt.name}
                  </option>
                ))}
              </select>
              <span className="text-[10px] text-slate-500 mt-1.5 block leading-relaxed">
                Gemini recibe la pauta del motor de reglas (Christus Sinergia / Res. 5596) y los criterios recuperados por el RAG; si falla o no hay cuota, clasifica el motor de reglas.
              </span>
            </div>

            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">
                  Extraccion de Entidades (NER)
                </label>
                {runtimeStatus?.ner_status && (
                  <span className={`px-2 py-0.5 rounded-full text-[9px] font-mono font-semibold uppercase border ${runtimeStatus.ner_status.model_loaded ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' : 'bg-amber-500/10 text-amber-400 border-amber-500/20'}`}>
                    {runtimeStatus.ner_status.model_loaded ? 'RoBERTa cargado' : 'Sin modelo: catalogo'}
                  </span>
                )}
              </div>
              <select
                value={config.active_ner_model}
                onChange={(e) => setConfig({ ...config, active_ner_model: e.target.value })}
                className="w-full bg-[var(--surface-card)] border border-[var(--surface-border)] rounded-xl p-2.5 text-xs text-slate-200 focus:ring-1 focus:ring-sky-500 focus:outline-none"
              >
                {(availableOptions?.ner_models || [
                  { id: 'auto', name: 'RoBERTa clinico + catalogo' },
                  { id: 'catalogo', name: 'Solo catalogo terminologico y LLM' },
                ]).map((opt) => (
                  <option key={opt.id} value={opt.id}>
                    {opt.name}
                  </option>
                ))}
              </select>
              <span className="text-[10px] text-slate-500 mt-1.5 block leading-relaxed">
                El modelo se carga en el worker LLM desde NER_MODEL_PATH (ver ml/ner/README.md). La negacion y el contexto (alergias, antecedentes) los decide el pipeline, no el modelo.
              </span>
            </div>
          </div>
        </div>

        {/* CARD 2: Encrypted API Keys Vault */}
        <div className="bg-[var(--surface-panel)] rounded-2xl border border-[var(--surface-border)] p-4 sm:p-5 space-y-4 shadow-sm flex flex-col">
          <div className="flex items-center justify-between pb-3 border-b border-[var(--surface-border)]">
            <div className="flex items-center gap-2.5 text-slate-200">
              <Key className="w-4 h-4 text-emerald-400" />
              <h3 className="text-xs uppercase font-semibold tracking-wider text-slate-200">
                Boveda de Llaves API Cifradas (Fernet)
              </h3>
            </div>
            <button
              onClick={() => setShowKeyModal(true)}
              className="px-3 py-1.5 rounded-xl text-xs font-semibold text-emerald-400 bg-emerald-500/10 border border-emerald-500/30 hover:bg-emerald-500/20 transition-colors flex items-center gap-1.5"
            >
              <Plus className="w-3.5 h-3.5" /> Agregar Llave
            </button>
          </div>

          <p className="text-[11px] text-slate-400">
            Las credenciales se cifran en base de datos con Fernet (AES-128 + HMAC-SHA256). Una vez registradas no se vuelven a mostrar en texto plano; solo pueden eliminarse. El triaje usa la llave de Gemini.
          </p>

          {/* Keys list */}
          <div className="space-y-2 flex-1 overflow-y-auto max-h-[220px] pr-1">
            {apiKeys.length === 0 ? (
              <div className="p-8 rounded-xl bg-[var(--surface-card)] border border-dashed border-[var(--surface-border)] text-center text-xs text-slate-500">
                No hay llaves personalizadas registradas. Se esta utilizando la llave configurada en el archivo de entorno (.env).
              </div>
            ) : (
              apiKeys.map((key) => (
                <div
                  key={key.id}
                  className="flex items-center justify-between p-3 rounded-xl bg-[var(--surface-card)] border border-[var(--surface-border)] hover:border-slate-700 transition-all shadow-sm"
                >
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg bg-[var(--surface-base)] border border-[var(--surface-border)] flex items-center justify-center text-slate-300 text-xs font-mono font-bold">
                      {key.provider === 'gemini' ? 'G' : key.provider === 'openai' ? 'OA' : key.provider === 'anthropic' ? 'CL' : key.provider === 'deepseek' ? 'DS' : 'K'}
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-semibold text-slate-200">{key.name}</span>
                        <span className="px-2 py-0.5 rounded-full text-[9px] font-semibold uppercase bg-sky-500/10 text-sky-400 border border-sky-500/20">
                          {key.provider_display}
                        </span>
                        {key.name.includes('.env') && (
                          <span className="px-2 py-0.5 rounded-full text-[9px] font-semibold uppercase bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                            .env
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-2 mt-0.5">
                        <span className="text-[11px] font-mono text-emerald-400 tracking-wider font-semibold">
                          {key.masked_key}
                        </span>
                        <span className="text-[10px] text-slate-500">
                          Registrada: {formatDate(key.created_at)}
                        </span>
                      </div>
                    </div>
                  </div>

                  <button
                    onClick={() => handleDeleteKey(key.id, key.name)}
                    className="p-1.5 rounded-lg text-slate-500 hover:text-red-400 hover:bg-red-500/10 transition-colors"
                    title="Eliminar credencial"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ))
            )}
          </div>

          <div className="p-3 rounded-xl bg-emerald-950/20 border border-emerald-500/20 flex items-center gap-2.5 text-[11px] text-emerald-300">
            <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0" />
            <span>Cifrado en reposo como medida de seguridad para la Ley 1581 de proteccion de datos; no es una certificacion de cumplimiento.</span>
          </div>
        </div>

        {/* CARD 3: Vocabularies */}
        <div className="lg:col-span-2 bg-[var(--surface-panel)] rounded-2xl border border-[var(--surface-border)] p-4 sm:p-5 space-y-4 shadow-sm">
          <div className="flex items-center justify-between pb-3 border-b border-[var(--surface-border)]">
            <div className="flex items-center gap-2.5 text-slate-200">
              <Database className="w-4 h-4 text-teal-400" />
              <h3 className="text-xs uppercase font-semibold tracking-wider text-slate-200">
                Estandares de Interoperabilidad Clinica (Vocabularios)
              </h3>
            </div>
            <span className="text-[11px] font-mono text-slate-400">
              Catalogo local versionado
            </span>
          </div>

          {/* Token consumption notice banner */}
          <div className="p-3.5 rounded-xl bg-sky-950/20 border border-sky-500/30 flex items-start gap-3 text-[11px] text-sky-200">
            <Sparkles className="w-4 h-4 text-sky-400 shrink-0 mt-0.5" />
            <div>
              <span className="font-semibold text-white block mb-0.5">Consumo de tokens de la normalizacion:</span>
              <p className="text-slate-300 leading-relaxed text-[11px]">
                {vocabularies?.snomed?.token_notice || 'Las capas del catalogo no consumen tokens; el LLM solo procesa los terminos residuales en el monitor de normalizacion.'}
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* SNOMED CT Card */}
            <div className="p-4 bg-[var(--surface-card)] rounded-xl border border-[var(--surface-border)] flex flex-col justify-between space-y-3.5">
              <div>
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-slate-200">{vocabularies?.snomed?.title || config.snomed_version}</span>
                  <span className="px-2 py-0.5 rounded-full text-[9px] font-semibold uppercase bg-teal-500/10 text-teal-400 border border-teal-500/20">
                    {vocabularies?.snomed?.status || '—'}
                  </span>
                </div>
                <span className="text-[11px] text-slate-400 block mt-1">
                  Fuente: {vocabularies?.snomed?.provider || '—'}
                </span>
                <span className="text-[10px] text-slate-500 block mt-0.5">
                  Ultima recarga: {formatDate(config.snomed_updated_at)} • Version del catalogo: {vocabularies?.snomed?.latest_release || '—'}
                </span>

                <div className="mt-3 grid grid-cols-2 gap-2 p-2.5 rounded-xl bg-[var(--surface-base)] border border-[var(--surface-border)] text-[11px]">
                  <div>
                    <span className="text-slate-500 block text-[10px]">Codigos verificados:</span>
                    <span className="font-mono font-semibold text-slate-300">{vocabularies?.snomed ? vocabularies.snomed.total_terms.toLocaleString('es-CO') : '—'}</span>
                  </div>
                  <div>
                    <span className="text-slate-500 block text-[10px]">Conceptos con codigo:</span>
                    <span className="font-mono font-semibold text-emerald-400">{vocabularies?.snomed ? vocabularies.snomed.indexed_emergency_terms.toLocaleString('es-CO') : '—'}</span>
                  </div>
                </div>

                <span className="text-[10px] text-teal-400 uppercase font-semibold tracking-wider mt-2.5 block">
                  Sintomas, hallazgos, trastornos y sustancias
                </span>
              </div>

              <div className="flex items-center justify-end gap-2 pt-3 border-t border-[var(--surface-border)]">
                <button
                  onClick={() => handleCheckUpdate('snomed')}
                  disabled={checkingUpdate === 'snomed'}
                  className="bg-[var(--surface-panel)] hover:bg-slate-800 text-slate-300 border border-[var(--surface-border)] px-3 py-1.5 rounded-xl text-[10px] font-semibold uppercase tracking-wider flex items-center gap-1.5 transition-colors disabled:opacity-50"
                  title="Validar la consistencia del catalogo local"
                >
                  {checkingUpdate === 'snomed' ? (
                    <RefreshCw className="w-3 h-3 animate-spin text-sky-400" />
                  ) : (
                    <RefreshCw className="w-3 h-3 text-slate-400" />
                  )}
                  Validar
                </button>

                <button
                  onClick={() => handleSyncVocab('snomed')}
                  disabled={syncingVocab === 'snomed'}
                  className="bg-sky-600 hover:bg-sky-500 text-white px-3 py-1.5 rounded-xl text-[10px] font-semibold uppercase tracking-wider flex items-center gap-1.5 transition-colors disabled:opacity-50 shadow-sm"
                >
                  {syncingVocab === 'snomed' ? (
                    <RefreshCw className="w-3 h-3 animate-spin" />
                  ) : (
                    <Upload className="w-3 h-3" />
                  )}
                  Recargar
                </button>
              </div>
            </div>

            {/* ICD-10 Card */}
            <div className="p-4 bg-[var(--surface-card)] rounded-xl border border-[var(--surface-border)] flex flex-col justify-between space-y-3.5">
              <div>
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-slate-200">{vocabularies?.icd10?.title || config.icd10_version}</span>
                  <span className="px-2 py-0.5 rounded-full text-[9px] font-semibold uppercase bg-sky-500/10 text-sky-400 border border-sky-500/20">
                    {vocabularies?.icd10?.status || '—'}
                  </span>
                </div>
                <span className="text-[11px] text-slate-400 block mt-1">
                  Fuente: {vocabularies?.icd10?.provider || '—'}
                </span>
                <span className="text-[10px] text-slate-500 block mt-0.5">
                  Ultima recarga: {formatDate(config.icd10_updated_at)} • Version del catalogo: {vocabularies?.icd10?.latest_release || '—'}
                </span>

                <div className="mt-3 grid grid-cols-2 gap-2 p-2.5 rounded-xl bg-[var(--surface-base)] border border-[var(--surface-border)] text-[11px]">
                  <div>
                    <span className="text-slate-500 block text-[10px]">Codigos en el catalogo:</span>
                    <span className="font-mono font-semibold text-slate-300">{vocabularies?.icd10 ? vocabularies.icd10.total_terms.toLocaleString('es-CO') : '—'}</span>
                  </div>
                  <div>
                    <span className="text-slate-500 block text-[10px]">Conceptos con codigo:</span>
                    <span className="font-mono font-semibold text-sky-400">{vocabularies?.icd10 ? vocabularies.icd10.indexed_emergency_terms.toLocaleString('es-CO') : '—'}</span>
                  </div>
                </div>

                <span className="text-[10px] text-sky-400 uppercase font-semibold tracking-wider mt-2.5 block">
                  Clasificacion Internacional de Enfermedades
                </span>
              </div>

              <div className="flex items-center justify-end gap-2 pt-3 border-t border-[var(--surface-border)]">
                <button
                  onClick={() => handleCheckUpdate('icd10')}
                  disabled={checkingUpdate === 'icd10'}
                  className="bg-[var(--surface-panel)] hover:bg-slate-800 text-slate-300 border border-[var(--surface-border)] px-3 py-1.5 rounded-xl text-[10px] font-semibold uppercase tracking-wider flex items-center gap-1.5 transition-colors disabled:opacity-50"
                  title="Validar la consistencia del catalogo local"
                >
                  {checkingUpdate === 'icd10' ? (
                    <RefreshCw className="w-3 h-3 animate-spin text-sky-400" />
                  ) : (
                    <RefreshCw className="w-3 h-3 text-slate-400" />
                  )}
                  Validar
                </button>

                <button
                  onClick={() => handleSyncVocab('icd10')}
                  disabled={syncingVocab === 'icd10'}
                  className="bg-sky-600 hover:bg-sky-500 text-white px-3 py-1.5 rounded-xl text-[10px] font-semibold uppercase tracking-wider flex items-center gap-1.5 transition-colors disabled:opacity-50 shadow-sm"
                >
                  {syncingVocab === 'icd10' ? (
                    <RefreshCw className="w-3 h-3 animate-spin" />
                  ) : (
                    <Upload className="w-3 h-3" />
                  )}
                  Recargar
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* MODAL: Agregar Llave API Cifrada */}
      {showKeyModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <div className="w-full max-w-md bg-[var(--surface-panel)] border border-[var(--surface-border)] rounded-2xl p-5 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-[var(--surface-border)] pb-3">
              <div className="flex items-center gap-2">
                <Key className="w-4 h-4 text-emerald-400" />
                <h3 className="text-xs font-semibold uppercase text-white tracking-wider">
                  Registrar Llave API Cifrada
                </h3>
              </div>
              <button
                onClick={() => setShowKeyModal(false)}
                className="text-slate-400 hover:text-slate-200"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleCreateKey} className="space-y-4">
              <div>
                <label className="block text-[11px] font-semibold uppercase tracking-wider text-slate-400 mb-1">
                  Nombre Identificador
                </label>
                <input
                  type="text"
                  required
                  value={newKeyName}
                  onChange={(e) => setNewKeyName(e.target.value)}
                  placeholder="Ej: Google Gemini Pro Produccion"
                  className="w-full bg-[var(--surface-card)] border border-[var(--surface-border)] rounded-xl py-2 px-3 text-xs text-slate-200 placeholder-slate-500 focus:ring-1 focus:ring-sky-500 focus:outline-none"
                />
              </div>

              <div>
                <div className="flex justify-between items-center mb-1">
                  <label className="block text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                    Llave API (Texto Plano)
                  </label>
                  {newKeyValue && (
                    <span className="text-[10px] text-sky-400 font-mono font-medium">
                      {handleDetectProvider(newKeyValue)}
                    </span>
                  )}
                </div>
                <div className="relative">
                  <input
                    type={showPlainKey ? 'text' : 'password'}
                    required
                    value={newKeyValue}
                    onChange={(e) => setNewKeyValue(e.target.value)}
                    placeholder="AIzaSy... o sk-..."
                    className="w-full bg-[var(--surface-card)] border border-[var(--surface-border)] rounded-xl py-2 pl-3 pr-9 text-xs text-slate-200 placeholder-slate-500 focus:ring-1 focus:ring-sky-500 focus:outline-none font-mono"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPlainKey(!showPlainKey)}
                    className="absolute right-2.5 top-2.5 text-slate-400 hover:text-slate-200"
                  >
                    {showPlainKey ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                  </button>
                </div>
              </div>

              <div>
                <label className="block text-[11px] font-semibold uppercase tracking-wider text-slate-400 mb-1">
                  Proveedor de IA
                </label>
                <select
                  value={newKeyProvider}
                  onChange={(e) => setNewKeyProvider(e.target.value)}
                  className="w-full bg-[var(--surface-card)] border border-[var(--surface-border)] rounded-xl py-2 px-3 text-xs text-slate-200 focus:ring-1 focus:ring-sky-500 focus:outline-none"
                >
                  <option value="auto">Autodetectar por formato de prefijo</option>
                  <option value="gemini">Google Gemini (AIza / AQ)</option>
                  <option value="openai">OpenAI (sk-...)</option>
                  <option value="anthropic">Anthropic Claude (sk-ant-...)</option>
                  <option value="deepseek">DeepSeek</option>
                  <option value="custom">Servidor Local / Compatible OpenAI</option>
                </select>
              </div>

              <div className="p-3 rounded-xl bg-amber-950/20 border border-amber-500/20 flex items-start gap-2 text-[11px] text-amber-300">
                <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                <span>
                  Por diseno de seguridad, esta llave sera cifrada inmediatamente. Nadie podra recuperarla ni leerla en texto plano.
                </span>
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowKeyModal(false)}
                  className="px-3.5 py-2 rounded-xl text-xs font-medium text-slate-400 hover:text-slate-200 bg-[var(--surface-card)] transition-colors border border-[var(--surface-border)]"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={savingKey}
                  className="px-4 py-2 rounded-xl text-xs font-semibold text-white bg-emerald-600 hover:bg-emerald-500 shadow-sm transition-all disabled:opacity-50"
                >
                  {savingKey ? 'Cifrando...' : 'Guardar Llave Cifrada'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
