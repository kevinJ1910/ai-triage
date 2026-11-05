'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { 
  Server, 
  CheckCircle2, 
  Clock, 
  Copy, 
  Check, 
  Send, 
  RefreshCw, 
  Layers, 
  ShieldCheck, 
  FileCode, 
  ArrowUpRight, 
  Download,
  ChevronLeft
} from 'lucide-react';
import { toast } from 'sonner';
import { fetchWithAuth } from '@/lib/api';

interface FHIRLogItem {
  id: number;
  session_id: number | null;
  resource_type: string;
  direction: 'OUTBOUND' | 'INBOUND';
  status_code: number;
  fhir_resource_id: string;
  validation_status: 'VALID' | 'WARNING' | 'ERROR';
  validation_details: string;
  payload: any;
  created_at: string;
}

export default function FHIRMonitor() {
  const [logs, setLogs] = useState<FHIRLogItem[]>([]);
  const [selectedLog, setSelectedLog] = useState<FHIRLogItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);
  const [syncingTest, setSyncingTest] = useState(false);
  const [mobileView, setMobileView] = useState<'list' | 'detail'>('list');

  const fetchLogs = useCallback(async () => {
    try {
      const res = await fetchWithAuth('/api/triage/sessions/fhir_logs/');
      if (res.ok) {
        const data = await res.json();
        setLogs(data);
        setSelectedLog(prev => (!prev && data.length > 0 ? data[0] : prev));
      }
    } catch (err) {
      console.error('Error cargando logs FHIR:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  const handleCopyJson = () => {
    if (!selectedLog) return;
    navigator.clipboard.writeText(JSON.stringify(selectedLog.payload, null, 2));
    setCopied(true);
    toast.success('Payload FHIR copiado al portapapeles');
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownloadJson = () => {
    if (!selectedLog) return;
    const blob = new Blob([JSON.stringify(selectedLog.payload, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${selectedLog.fhir_resource_id || 'fhir-bundle'}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleSendTestSync = async () => {
    setSyncingTest(true);
    try {
      const testBundle = {
        resourceType: 'Bundle',
        type: 'transaction',
        timestamp: new Date().toISOString(),
        entry: [
          {
            resource: {
              resourceType: 'Patient',
              id: `pat-live-${Date.now()}`,
              name: [{ text: 'Paciente Prueba Interoperabilidad' }]
            }
          },
          {
            resource: {
              resourceType: 'Encounter',
              id: `enc-live-${Date.now()}`,
              status: 'arrived',
              class: { code: 'EMER', display: 'Emergencia' },
              priority: { coding: [{ code: 'L2', display: 'Emergencia' }] }
            }
          },
          {
            resource: {
              resourceType: 'Observation',
              status: 'final',
              code: { text: 'Nivel de Triaje Medico' },
              valueInteger: 2
            }
          }
        ]
      };

      const res = await fetchWithAuth('/api/fhir/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(testBundle)
      });

      if (res.ok) {
        toast.success('Transaccion FHIR R4 enviada y registrada con exito');
        await fetchLogs();
      } else {
        toast.error('Fallo en sincronizacion FHIR');
      }
    } catch (err) {
      toast.error('Error de conexion al servidor FHIR');
    } finally {
      setSyncingTest(false);
    }
  };

  // Extract resources inside the bundle payload
  const bundleEntries: any[] = selectedLog?.payload?.entry || [];

  return (
    <div className="flex flex-col h-full w-full bg-[var(--surface-base)] border border-[var(--surface-border)] rounded-2xl overflow-hidden font-sans shadow-xl">
      {/* Header Interoperabilidad */}
      <div className="h-16 bg-[var(--surface-panel)] border-b border-[var(--surface-border)] flex items-center justify-between px-5 shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-sky-500/10 border border-sky-500/20 flex items-center justify-center text-sky-400">
            <Server className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xs sm:text-sm font-semibold tracking-wide text-slate-100">
                Monitor de Interoperabilidad Clinica (HL7 FHIR R4)
              </h1>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-medium">
                Auditoria Activa en BD
              </span>
            </div>
            <p className="text-[11px] text-slate-400">
              Inspeccion y validacion de bundles transaccionales para integracion con HIS hospitalario.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleSendTestSync}
            disabled={syncingTest}
            className="flex items-center gap-1.5 px-3 py-2 bg-sky-600 hover:bg-sky-500 disabled:opacity-50 text-white text-xs font-medium rounded-xl transition-colors shadow-sm"
          >
            <Send className="w-3.5 h-3.5" />
            {syncingTest ? 'Transmitiendo...' : 'Transmitir Bundle Test'}
          </button>
          <button
            onClick={fetchLogs}
            className="p-2 bg-[var(--surface-card)] hover:bg-slate-800 text-slate-300 rounded-xl border border-[var(--surface-border)] transition-colors"
            title="Refrescar Registros"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Main Container: Grid 12 cols */}
      <div className="flex-1 grid grid-cols-1 md:grid-cols-12 overflow-hidden">
        {/* Left Column: Transaction Log (4 cols) */}
        <div className={`md:col-span-4 border-r border-[var(--surface-border)] bg-[var(--surface-panel)] flex flex-col overflow-hidden ${
          mobileView === 'detail' ? 'hidden md:flex' : 'flex'
        }`}>
          <div className="px-4 py-3 text-[11px] font-semibold text-slate-400 border-b border-[var(--surface-border)] flex justify-between items-center">
            <span>Mensajes Transaccionales ({logs.length})</span>
            <span className="text-slate-500 font-mono text-[10px]">HL7 FHIR R4 JSON</span>
          </div>

          <div className="flex-1 overflow-y-auto p-3 space-y-2">
            {loading ? (
              <div className="flex flex-col items-center justify-center p-12 text-slate-500 text-xs gap-2">
                <RefreshCw className="w-4 h-4 animate-spin text-sky-400" />
                Consultando registros FHIR...
              </div>
            ) : logs.length === 0 ? (
              <div className="p-8 text-center text-slate-500 text-xs bg-[var(--surface-card)] rounded-xl border border-[var(--surface-border)]">
                No hay transacciones registradas.
              </div>
            ) : (
              logs.map((log) => {
                const isSelected = selectedLog?.id === log.id;
                return (
                  <button
                    key={log.id}
                    onClick={() => {
                      setSelectedLog(log);
                      setMobileView('detail');
                    }}
                    className={`w-full text-left p-3.5 rounded-xl border transition-all flex flex-col gap-2 ${
                      isSelected
                        ? 'bg-sky-500/10 border-sky-500/40 shadow-sm'
                        : 'bg-[var(--surface-card)] border-[var(--surface-border)] hover:border-slate-700'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-xs font-semibold text-slate-200 truncate">
                        {log.fhir_resource_id || `LOG-#${log.id}`}
                      </span>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-semibold">
                        {log.status_code} Creado
                      </span>
                    </div>

                    <div className="flex items-center justify-between text-[11px] text-slate-400">
                      <span className="flex items-center gap-1.5 font-mono text-[11px]">
                        <Layers className="w-3.5 h-3.5 text-sky-400" />
                        {log.resource_type}
                      </span>
                      <span className="flex items-center gap-1 text-[10px] text-slate-500">
                        <Clock className="w-3 h-3" />
                        {log.created_at}
                      </span>
                    </div>

                    <div className="flex items-center justify-between pt-2 border-t border-[var(--surface-border)] text-[11px]">
                      <span className="text-slate-400 flex items-center gap-1">
                        <ArrowUpRight className="w-3.5 h-3.5 text-sky-400" />
                        {log.direction}
                      </span>
                      <span className="text-emerald-400 font-medium">
                        {log.validation_status}
                      </span>
                    </div>
                  </button>
                );
              })
            )}
          </div>
        </div>

        {/* Right Column: Payload Inspector & Schema Validation (8 cols) */}
        <div className={`md:col-span-8 bg-[var(--surface-base)] p-4 sm:p-6 flex flex-col overflow-y-auto space-y-4 ${
          mobileView === 'list' ? 'hidden md:flex' : 'flex'
        }`}>
          {/* Mobile Back Button */}
          <div className="md:hidden flex items-center pb-1">
            <button
              onClick={() => setMobileView('list')}
              className="flex items-center gap-1.5 text-xs font-medium text-sky-400 hover:text-sky-300 py-1.5 px-3 rounded-xl bg-[var(--surface-card)] border border-[var(--surface-border)]"
            >
              <ChevronLeft className="w-4 h-4" />
              Volver a Transacciones
            </button>
          </div>

          {selectedLog ? (
            <>
              {/* Transaction Metadata Card */}
              <div className="bg-[var(--surface-panel)] border border-[var(--surface-border)] rounded-2xl p-4 sm:p-5 space-y-3.5 shadow-sm">
                <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 pb-3 border-b border-[var(--surface-border)]">
                  <div className="flex items-center gap-3">
                    <div className="p-2.5 bg-emerald-500/10 rounded-xl text-emerald-400 border border-emerald-500/20">
                      <ShieldCheck className="w-5 h-5" />
                    </div>
                    <div>
                      <h3 className="text-xs sm:text-sm font-semibold text-slate-200">
                        Validacion de Conformidad FHIR R4
                      </h3>
                      <p className="text-[11px] text-slate-400">
                        {selectedLog.validation_details}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      onClick={handleCopyJson}
                      className="flex items-center gap-1.5 px-3 py-1.5 bg-[var(--surface-card)] hover:bg-slate-800 text-slate-300 rounded-xl text-xs border border-[var(--surface-border)] transition-colors"
                    >
                      {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                      {copied ? 'Copiado' : 'Copiar JSON'}
                    </button>
                    <button
                      onClick={handleDownloadJson}
                      className="flex items-center gap-1.5 px-3 py-1.5 bg-[var(--surface-card)] hover:bg-slate-800 text-slate-300 rounded-xl text-xs border border-[var(--surface-border)] transition-colors"
                    >
                      <Download className="w-3.5 h-3.5" />
                      Descargar
                    </button>
                  </div>
                </div>

                {/* Sub-resources chips */}
                {bundleEntries.length > 0 && (
                  <div>
                    <span className="text-[10px] uppercase font-semibold text-slate-500 block mb-2 tracking-wider">
                      Recursos Anidados en el Bundle:
                    </span>
                    <div className="flex flex-wrap gap-2">
                      {bundleEntries.map((e, idx) => {
                        const resType = e.resource?.resourceType || 'Resource';
                        const resId = e.resource?.id || idx;
                        return (
                          <span
                            key={idx}
                            className="px-2.5 py-1 bg-[var(--surface-card)] border border-[var(--surface-border)] rounded-lg text-[11px] font-mono text-slate-300 flex items-center gap-1.5"
                          >
                            <FileCode className="w-3.5 h-3.5 text-sky-400" />
                            {resType}: <span className="text-sky-300">{resId}</span>
                          </span>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>

              {/* JSON Payload Inspector */}
              <div className="flex-1 flex flex-col bg-[var(--surface-panel)] border border-[var(--surface-border)] rounded-2xl overflow-hidden min-h-[320px] shadow-sm">
                <div className="px-4 py-2.5 bg-[var(--surface-panel)] border-b border-[var(--surface-border)] flex items-center justify-between text-xs">
                  <span className="text-slate-400 font-mono text-[11px] flex items-center gap-1.5">
                    <FileCode className="w-3.5 h-3.5 text-sky-400" />
                    Payload Estructurado (JSON R4)
                  </span>
                  <span className="text-[10px] text-slate-500 font-mono">
                    {JSON.stringify(selectedLog.payload).length} bytes
                  </span>
                </div>

                <pre className="flex-1 p-4 bg-slate-950/80 text-slate-200 font-mono text-xs leading-relaxed overflow-x-auto overflow-y-auto selection:bg-sky-600 selection:text-white">
                  {JSON.stringify(selectedLog.payload, null, 2)}
                </pre>
              </div>
            </>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center text-slate-500 text-xs bg-[var(--surface-card)] rounded-2xl border border-[var(--surface-border)]">
              Seleccione una transaccion del historial para inspeccionar el payload FHIR.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
