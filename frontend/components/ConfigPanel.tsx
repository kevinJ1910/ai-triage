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
    active_ner_model: 'ClinicalBERT (v2.1 - Recomendado)',
    snomed_version: 'SNOMED CT (Edicion en Espanol)',
    snomed_updated_at: new Date().toISOString(),
    icd10_version: 'ICD-10 (CIE-10)',
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
    <div className="flex flex-col h-full w-full bg-slate-900 border border-slate-700/80 rounded-xl p-3 sm:p-5 overflow-y-auto space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-3 shrink-0">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-blue-600/20 border border-blue-500/30 flex items-center justify-center text-blue-400">
            <Settings className="w-4 h-4" />
          </div>
          <div>
            <h2 className="text-xs sm:text-sm font-bold uppercase text-white tracking-wider">
              Configuracion del Sistema y Motores IA
            </h2>
            <p className="text-[10px] text-slate-400">
              Parametrizacion de modelos ASR, motores LLM y gestion segura de credenciales
            </p>
          </div>
        </div>

        <button
          onClick={handleSaveModels}
          disabled={savingConfig}
          className="px-3 py-1.5 rounded-lg text-[10px] sm:text-xs font-semibold text-white bg-blue-600 hover:bg-blue-500 transition-all flex items-center gap-1.5 shadow-md shadow-blue-600/20 disabled:opacity-50"
        >
          {savingConfig ? (
            <RefreshCw className="w-3.5 h-3.5 animate-spin" />
          ) : (
            <Check className="w-3.5 h-3.5" />
          )}
          Guardar Cambios
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* CARD 1: Model Management */}
        <div className="bg-slate-950/60 rounded-xl border border-slate-800 p-4 space-y-4 shadow-sm">
          <div className="flex items-center gap-2 text-slate-300 pb-2 border-b border-slate-800">
            <Cpu className="w-4 h-4 text-blue-400" />
            <h3 className="text-xs uppercase font-bold tracking-wider text-slate-200">
              Motores de Inferencia Clinica
            </h3>
          </div>

          <div className="space-y-3.5">
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">
                  Motor ASR de Transcripcion (Faster-Whisper)
                </label>
                {runtimeStatus && (
                  <span className={`px-2 py-0.5 rounded text-[9px] font-mono font-bold uppercase ${runtimeStatus.cuda_available ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'}`}>
                    {runtimeStatus.hardware_device}
                  </span>
                )}
              </div>
              <select
                value={config.active_asr_model}
                onChange={(e) => setConfig({ ...config, active_asr_model: e.target.value })}
                className="w-full bg-slate-900 border border-slate-700 rounded-lg p-2.5 text-xs text-slate-200 focus:ring-2 focus:ring-blue-500 focus:outline-none"
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
              <span className="text-[10px] text-slate-500 mt-1 block">
                Aceleracion por tensores CTranslate2 con soporte NVIDIA CUDA y fallback dinamico a CPU INT8. El cambio de modelo se aplica al reiniciar el worker ASR.
              </span>
            </div>

            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">
                  Motor de Explicabilidad y Triaje (LLM)
                </label>
                {runtimeStatus?.gemini_configured && (
                  <span className="px-2 py-0.5 rounded text-[9px] font-mono font-bold uppercase bg-blue-500/10 text-blue-400 border border-blue-500/20">
                    Credencial Activa
                  </span>
                )}
              </div>
              <select
                value={config.active_llm_engine}
                onChange={(e) => setConfig({ ...config, active_llm_engine: e.target.value })}
                className="w-full bg-slate-900 border border-slate-700 rounded-lg p-2.5 text-xs text-slate-200 focus:ring-2 focus:ring-blue-500 focus:outline-none"
              >
                {(availableOptions?.llm_engines || [
                  { id: 'gemini-2.5-flash', name: 'Google Gemini 2.5 Flash - Baja Latencia Clinica (Recomendado)' },
                  { id: 'gemini-1.5-pro', name: 'Google Gemini 1.5 Pro - Razonamiento Extendido' },
                  { id: 'gpt-4o-mini', name: 'OpenAI GPT-4o-mini - Soporte Multimodal' },
                  { id: 'gpt-4o', name: 'OpenAI GPT-4o - Modelo de Referencia' },
                  { id: 'claude-3-5-sonnet', name: 'Anthropic Claude 3.5 Sonnet - Precision Diagnostica' },
                ]).map((opt) => (
                  <option key={opt.id} value={opt.id}>
                    {opt.name}
                  </option>
                ))}
              </select>
              <span className="text-[10px] text-slate-500 mt-1 block">
                El motor analiza la conversacion medica para extraer sintomas, signos vitales y escala ESI/Manchester.
              </span>
            </div>

            <div>
              <label className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block mb-1.5">
                Modelo NER Especializado (Entidades Medicas)
              </label>
              <select
                value={config.active_ner_model}
                onChange={(e) => setConfig({ ...config, active_ner_model: e.target.value })}
                className="w-full bg-slate-900 border border-slate-700 rounded-lg p-2.5 text-xs text-slate-200 focus:ring-2 focus:ring-blue-500 focus:outline-none"
              >
                {(availableOptions?.ner_models || [
                  { id: 'ClinicalBERT (v2.1 - Recomendado)', name: 'ClinicalBERT (v2.1 - Recomendado)' },
                  { id: 'BioBERT (v1.5 - Legacy)', name: 'BioBERT (v1.5 - Legacy)' },
                  { id: 'PubMedBERT (Experimental)', name: 'PubMedBERT (Experimental)' },
                ]).map((opt) => (
                  <option key={opt.id} value={opt.id}>
                    {opt.name}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* CARD 2: Encrypted API Keys Vault */}
        <div className="bg-slate-950/60 rounded-xl border border-slate-800 p-4 space-y-4 shadow-sm flex flex-col">
          <div className="flex items-center justify-between pb-2 border-b border-slate-800">
            <div className="flex items-center gap-2 text-slate-300">
              <Key className="w-4 h-4 text-emerald-400" />
              <h3 className="text-xs uppercase font-bold tracking-wider text-slate-200">
                Boveda de Llaves API Cifradas (AES)
              </h3>
            </div>
            <button
              onClick={() => setShowKeyModal(true)}
              className="px-2.5 py-1 rounded-lg text-[10px] font-bold uppercase tracking-wider text-emerald-400 bg-emerald-500/10 border border-emerald-500/30 hover:bg-emerald-500/20 transition-colors flex items-center gap-1"
            >
              <Plus className="w-3.5 h-3.5" /> Agregar Llave
            </button>
          </div>

          <p className="text-[11px] text-slate-400">
            Las credenciales de acceso se cifran mediante algoritmos simetricos AES en base de datos. Una vez registradas, las llaves nunca son expuestas en texto plano; unicamente pueden eliminarse.
          </p>

          {/* Keys list */}
          <div className="space-y-2 flex-1 overflow-y-auto max-h-[220px] pr-1">
            {apiKeys.length === 0 ? (
              <div className="p-6 rounded-lg bg-slate-900/50 border border-dashed border-slate-800 text-center text-xs text-slate-500">
                No hay llaves personalizadas registradas. Se esta utilizando la llave configurada en el archivo de entorno (.env).
              </div>
            ) : (
              apiKeys.map((key) => (
                <div
                  key={key.id}
                  className="flex items-center justify-between p-3 rounded-lg bg-slate-900 border border-slate-800 hover:border-slate-700 transition-all"
                >
                  <div className="flex items-center gap-3">
                    <div className="w-7 h-7 rounded-md bg-slate-800 flex items-center justify-center text-slate-300 text-xs font-mono font-bold">
                      {key.provider === 'gemini' ? 'G' : key.provider === 'openai' ? 'OA' : key.provider === 'anthropic' ? 'CL' : key.provider === 'deepseek' ? 'DS' : 'K'}
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-semibold text-slate-200">{key.name}</span>
                        <span className="px-1.5 py-0.5 rounded text-[9px] font-bold uppercase bg-blue-500/10 text-blue-400 border border-blue-500/20">
                          {key.provider_display}
                        </span>
                        {key.name.includes('.env') && (
                          <span className="px-1.5 py-0.5 rounded text-[9px] font-bold uppercase bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                            .env
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-2 mt-0.5">
                        <span className="text-[11px] font-mono text-emerald-400 tracking-wider">
                          {key.masked_key}
                        </span>
                        <span className="text-[9px] text-slate-500">
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

          <div className="p-2.5 rounded-lg bg-emerald-950/20 border border-emerald-500/20 flex items-center gap-2 text-[10px] text-emerald-300">
            <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0" />
            <span>Almacenamiento seguro conforme a estandares HIPAA y Ley 1581 de proteccion de datos.</span>
          </div>
        </div>

        {/* CARD 3: Vocabularies */}
        <div className="lg:col-span-2 bg-slate-950/60 rounded-xl border border-slate-800 p-4 space-y-4 shadow-sm">
          <div className="flex items-center justify-between pb-2 border-b border-slate-800">
            <div className="flex items-center gap-2 text-slate-300">
              <Database className="w-4 h-4 text-purple-400" />
              <h3 className="text-xs uppercase font-bold tracking-wider text-slate-200">
                Estandares de Interoperabilidad Clinica (Vocabularios)
              </h3>
            </div>
            <span className="text-[10px] font-mono text-slate-400">
              Mapeo Semantico Activo
            </span>
          </div>

          {/* Token consumption notice banner */}
          <div className="p-3 rounded-lg bg-indigo-950/20 border border-indigo-500/30 flex items-start gap-2.5 text-[11px] text-indigo-300">
            <Sparkles className="w-4 h-4 text-indigo-400 shrink-0 mt-0.5" />
            <div>
              <span className="font-bold text-white block mb-0.5">Control de Consumo de Tokens (Filtrado Semantico LLM):</span>
              <p className="text-slate-300 leading-relaxed text-[10px] sm:text-[11px]">
                El motor realiza busqueda determinista y RAG semantico para vocabulario clinico. Cuando se activa el LLM para disambiguar lenguaje coloquial, cada consulta consume un promedio de <strong>~120 a 180 tokens</strong> (entrada: ~100 tokens, salida estructurada: ~40 tokens). Mantener vocabularios sincronizados permite maximizar el acierto local y reducir llamadas a API de terceros.
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* SNOMED CT Card */}
            <div className="p-4 bg-slate-900 rounded-lg border border-slate-800 flex flex-col justify-between space-y-3">
              <div>
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-slate-200">{config.snomed_version}</span>
                  <span className="px-2 py-0.5 rounded text-[9px] font-bold uppercase bg-purple-500/10 text-purple-400 border border-purple-500/20">
                    {vocabularies?.snomed?.status || 'OPERACIONAL'}
                  </span>
                </div>
                <span className="text-[10px] text-slate-400 block mt-1">
                  Proveedor: {vocabularies?.snomed?.provider || 'IHTSDO / SNOMED International (Edicion Espanol)'}
                </span>
                <span className="text-[10px] text-slate-500 block mt-0.5">
                  Ultima actualizacion: {formatDate(config.snomed_updated_at)} • Ultimo release: {vocabularies?.snomed?.latest_release || '2026-09-01'}
                </span>

                <div className="mt-2.5 grid grid-cols-2 gap-2 p-2 rounded bg-slate-950/60 border border-slate-800/80 text-[10px]">
                  <div>
                    <span className="text-slate-500 block text-[9px]">Terminos del Catalogo:</span>
                    <span className="font-mono font-bold text-slate-300">{(vocabularies?.snomed?.total_terms || 352267).toLocaleString('es-CO')}</span>
                  </div>
                  <div>
                    <span className="text-slate-500 block text-[9px]">Prioritarios Urgencias:</span>
                    <span className="font-mono font-bold text-emerald-400">{(vocabularies?.snomed?.indexed_emergency_terms || 24500).toLocaleString('es-CO')}</span>
                  </div>
                </div>

                <span className="text-[9px] text-purple-400 uppercase font-bold tracking-wider mt-2 block">
                  Ontologia de sintomas, signos y hallazgos
                </span>
              </div>

              <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-800/60">
                <button
                  onClick={() => handleCheckUpdate('snomed')}
                  disabled={checkingUpdate === 'snomed'}
                  className="bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 px-2.5 py-1.5 rounded-lg text-[10px] font-semibold uppercase tracking-wider flex items-center gap-1.5 transition-colors disabled:opacity-50"
                  title="Comprobar si existe una edicion mas reciente en el servidor oficial"
                >
                  {checkingUpdate === 'snomed' ? (
                    <RefreshCw className="w-3 h-3 animate-spin text-blue-400" />
                  ) : (
                    <RefreshCw className="w-3 h-3 text-slate-400" />
                  )}
                  Comprobar
                </button>

                <button
                  onClick={() => handleSyncVocab('snomed')}
                  disabled={syncingVocab === 'snomed'}
                  className="bg-blue-600/20 text-blue-400 border border-blue-500/40 hover:bg-blue-600/30 px-3 py-1.5 rounded-lg text-[10px] font-bold uppercase tracking-wider flex items-center gap-1.5 transition-colors disabled:opacity-50"
                >
                  {syncingVocab === 'snomed' ? (
                    <RefreshCw className="w-3 h-3 animate-spin" />
                  ) : (
                    <Upload className="w-3 h-3" />
                  )}
                  Sincronizar
                </button>
              </div>
            </div>

            {/* ICD-10 Card */}
            <div className="p-4 bg-slate-900 rounded-lg border border-slate-800 flex flex-col justify-between space-y-3">
              <div>
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-slate-200">{config.icd10_version}</span>
                  <span className="px-2 py-0.5 rounded text-[9px] font-bold uppercase bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                    {vocabularies?.icd10?.status || 'OPERACIONAL'}
                  </span>
                </div>
                <span className="text-[10px] text-slate-400 block mt-1">
                  Proveedor: {vocabularies?.icd10?.provider || 'OMS / Catalogo Oficial CIE-10 (Edicion Clinica)'}
                </span>
                <span className="text-[10px] text-slate-500 block mt-0.5">
                  Ultima actualizacion: {formatDate(config.icd10_updated_at)} • Ultimo release: {vocabularies?.icd10?.latest_release || '2026-08-15'}
                </span>

                <div className="mt-2.5 grid grid-cols-2 gap-2 p-2 rounded bg-slate-950/60 border border-slate-800/80 text-[10px]">
                  <div>
                    <span className="text-slate-500 block text-[9px]">Codigos del Catalogo:</span>
                    <span className="font-mono font-bold text-slate-300">{(vocabularies?.icd10?.total_terms || 14200).toLocaleString('es-CO')}</span>
                  </div>
                  <div>
                    <span className="text-slate-500 block text-[9px]">Prioritarios Urgencias:</span>
                    <span className="font-mono font-bold text-indigo-400">{(vocabularies?.icd10?.indexed_emergency_terms || 4200).toLocaleString('es-CO')}</span>
                  </div>
                </div>

                <span className="text-[9px] text-indigo-400 uppercase font-bold tracking-wider mt-2 block">
                  Clasificacion Internacional de Enfermedades
                </span>
              </div>

              <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-800/60">
                <button
                  onClick={() => handleCheckUpdate('icd10')}
                  disabled={checkingUpdate === 'icd10'}
                  className="bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 px-2.5 py-1.5 rounded-lg text-[10px] font-semibold uppercase tracking-wider flex items-center gap-1.5 transition-colors disabled:opacity-50"
                  title="Comprobar si existe una edicion mas reciente en el servidor oficial"
                >
                  {checkingUpdate === 'icd10' ? (
                    <RefreshCw className="w-3 h-3 animate-spin text-blue-400" />
                  ) : (
                    <RefreshCw className="w-3 h-3 text-slate-400" />
                  )}
                  Comprobar
                </button>

                <button
                  onClick={() => handleSyncVocab('icd10')}
                  disabled={syncingVocab === 'icd10'}
                  className="bg-blue-600/20 text-blue-400 border border-blue-500/40 hover:bg-blue-600/30 px-3 py-1.5 rounded-lg text-[10px] font-bold uppercase tracking-wider flex items-center gap-1.5 transition-colors disabled:opacity-50"
                >
                  {syncingVocab === 'icd10' ? (
                    <RefreshCw className="w-3 h-3 animate-spin" />
                  ) : (
                    <Upload className="w-3 h-3" />
                  )}
                  Sincronizar
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* MODAL: Agregar Llave API Cifrada */}
      {showKeyModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <div className="w-full max-w-md bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-2xl space-y-4 animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <Key className="w-4 h-4 text-emerald-400" />
                <h3 className="text-xs font-bold uppercase text-white tracking-wider">
                  Registrar Llave API Cifrada
                </h3>
              </div>
              <button
                onClick={() => setShowKeyModal(false)}
                className="text-slate-500 hover:text-slate-300"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleCreateKey} className="space-y-3.5">
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
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg py-2 px-3 text-xs text-slate-200 placeholder-slate-600 focus:ring-2 focus:ring-blue-500 focus:outline-none"
                />
              </div>

              <div>
                <div className="flex justify-between items-center mb-1">
                  <label className="block text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                    Llave API (Texto Plano)
                  </label>
                  {newKeyValue && (
                    <span className="text-[10px] text-blue-400 font-mono">
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
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg py-2 pl-3 pr-9 text-xs text-slate-200 placeholder-slate-600 focus:ring-2 focus:ring-blue-500 focus:outline-none font-mono"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPlainKey(!showPlainKey)}
                    className="absolute right-2.5 top-2.5 text-slate-500 hover:text-slate-300"
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
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg py-2 px-3 text-xs text-slate-200 focus:ring-2 focus:ring-blue-500 focus:outline-none"
                >
                  <option value="auto">Autodetectar por formato de prefijo</option>
                  <option value="gemini">Google Gemini (AIza / AQ)</option>
                  <option value="openai">OpenAI (sk-...)</option>
                  <option value="anthropic">Anthropic Claude (sk-ant-...)</option>
                  <option value="deepseek">DeepSeek</option>
                  <option value="custom">Servidor Local / Compatible OpenAI</option>
                </select>
              </div>

              <div className="p-3 rounded-lg bg-amber-950/20 border border-amber-500/20 flex items-start gap-2 text-[10px] text-amber-300">
                <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                <span>
                  Por diseno de seguridad, esta llave sera cifrada inmediatamente. Nadie podra recuperarla ni leerla en texto plano.
                </span>
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowKeyModal(false)}
                  className="px-3 py-2 rounded-lg text-xs font-semibold text-slate-400 hover:text-slate-200 bg-slate-800/50 hover:bg-slate-800 transition-colors"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={savingKey}
                  className="px-4 py-2 rounded-lg text-xs font-semibold text-white bg-emerald-600 hover:bg-emerald-500 shadow-md shadow-emerald-600/20 transition-all disabled:opacity-50"
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
