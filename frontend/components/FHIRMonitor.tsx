'use client';

import React, { useState, useEffect } from 'react';
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
  Download 
} from 'lucide-react';
import { toast } from 'sonner';

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

  const fetchLogs = async () => {
    try {
      const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null;
      const headers: Record<string, string> = {};
      if (token) headers['Authorization'] = `Bearer ${token}`;

      const res = await fetch('/api/triage/sessions/fhir_logs/', { headers });
      if (res.ok) {
        const data = await res.json();
        setLogs(data);
        if (data.length > 0 && !selectedLog) {
          setSelectedLog(data[0]);
        }
      }
    } catch (err) {
      console.error('Error cargando logs FHIR:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs();
  }, []);

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
              code: { text: 'Nivel de Triaje Medico' },
              valueInteger: 2
            }
          }
        ]
      };

      const res = await fetch('/api/fhir/', {
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
    <div className="flex flex-col h-full w-full bg-slate-950 border border-slate-800 rounded-xl overflow-hidden font-sans shadow-2xl">
      {/* Header */}
      <div className="h-14 bg-slate-900 border-b border-slate-800 flex items-center justify-between px-5 shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-orange-500/20 border border-orange-500/30 flex items-center justify-center text-orange-400">
            <Server className="w-4 h-4" />
          </div>
          <div>
            <h1 className="text-xs font-bold uppercase tracking-wider text-slate-100 flex items-center gap-2">
              Monitor de Interoperabilidad Clinica (HL7 FHIR R4)
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                Auditoria Activa en BD
              </span>
            </h1>
            <p className="text-[10px] text-slate-400">
              Inspeccion y validacion de bundles transaccionales para integracion con HIS hospitalario.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleSendTestSync}
            disabled={syncingTest}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-orange-600 hover:bg-orange-500 disabled:opacity-50 text-white text-xs font-semibold rounded-lg transition-colors shadow-md shadow-orange-600/20"
          >
            <Send className="w-3.5 h-3.5" />
            {syncingTest ? 'Transmitiendo...' : 'Transmitir Bundle Test'}
          </button>
          <button
            onClick={fetchLogs}
            className="p-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg border border-slate-700 transition-colors"
            title="Refrescar Registros"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Main Container: Grid 12 cols */}
      <div className="flex-1 grid grid-cols-1 md:grid-cols-12 overflow-hidden">
        {/* Left Column: Transaction Log (4 cols) */}
        <div className="md:col-span-4 border-r border-slate-800 bg-slate-900/60 flex flex-col overflow-hidden">
          <div className="px-4 py-2.5 text-[10px] font-bold uppercase tracking-wider text-slate-400 border-b border-slate-800 flex justify-between items-center">
            <span>Mensajes Transaccionales ({logs.length})</span>
            <span className="text-slate-500 font-mono">FHIR R4 JSON</span>
          </div>

          <div className="flex-1 overflow-y-auto p-3 space-y-2">
            {loading ? (
              <div className="flex flex-col items-center justify-center p-8 text-slate-500 text-xs gap-2">
                <RefreshCw className="w-4 h-4 animate-spin" />
                Consultando registros FHIR...
              </div>
            ) : logs.length === 0 ? (
              <div className="p-6 text-center text-slate-500 text-xs">
                No hay transacciones registradas.
              </div>
            ) : (
              logs.map((log) => {
                const isSelected = selectedLog?.id === log.id;
                return (
                  <button
                    key={log.id}
                    onClick={() => setSelectedLog(log)}
                    className={`w-full text-left p-3 rounded-xl border transition-all flex flex-col gap-1.5 ${
                      isSelected
                        ? 'bg-orange-600/15 border-orange-500/50 shadow-md shadow-orange-600/10'
                        : 'bg-slate-900/80 border-slate-800/80 hover:bg-slate-800/50'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-xs font-bold text-slate-200 truncate">
                        {log.fhir_resource_id || `LOG-#${log.id}`}
                      </span>
                      <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-bold">
                        {log.status_code} Creado
                      </span>
                    </div>

                    <div className="flex items-center justify-between text-[11px] text-slate-400">
                      <span className="flex items-center gap-1 font-mono text-[10px]">
                        <Layers className="w-3 h-3 text-slate-500" />
                        {log.resource_type}
                      </span>
                      <span className="flex items-center gap-1 text-[10px] text-slate-500">
                        <Clock className="w-3 h-3" />
                        {log.created_at}
                      </span>
                    </div>

                    <div className="flex items-center justify-between pt-1 border-t border-slate-800/60 text-[10px]">
                      <span className="text-slate-500 uppercase flex items-center gap-1">
                        <ArrowUpRight className="w-3 h-3 text-orange-400" />
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
        <div className="md:col-span-8 bg-slate-950 p-6 flex flex-col overflow-y-auto space-y-4">
          {selectedLog ? (
            <>
              {/* Transaction Metadata Card */}
              <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4 space-y-3">
                <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 pb-3 border-b border-slate-800">
                  <div className="flex items-center gap-2.5">
                    <div className="p-2 bg-emerald-500/10 rounded-lg text-emerald-400">
                      <ShieldCheck className="w-4 h-4" />
                    </div>
                    <div>
                      <h3 className="text-xs font-bold uppercase tracking-wider text-slate-200">
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
                      className="flex items-center gap-1 px-2.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs border border-slate-700 transition-colors"
                    >
                      {copied ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                      {copied ? 'Copiado' : 'Copiar JSON'}
                    </button>
                    <button
                      onClick={handleDownloadJson}
                      className="flex items-center gap-1 px-2.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs border border-slate-700 transition-colors"
                    >
                      <Download className="w-3 h-3" />
                      Descargar
                    </button>
                  </div>
                </div>

                {/* Sub-resources chips */}
                {bundleEntries.length > 0 && (
                  <div>
                    <span className="text-[10px] uppercase font-semibold text-slate-500 block mb-1.5">
                      Recursos Anidados en el Bundle:
                    </span>
                    <div className="flex flex-wrap gap-2">
                      {bundleEntries.map((e, idx) => {
                        const resType = e.resource?.resourceType || 'Resource';
                        const resId = e.resource?.id || idx;
                        return (
                          <span
                            key={idx}
                            className="px-2 py-1 bg-slate-950 border border-slate-800 rounded-md text-[11px] font-mono text-slate-300 flex items-center gap-1.5"
                          >
                            <FileCode className="w-3 h-3 text-orange-400" />
                            {resType}: <span className="text-blue-400">{resId}</span>
                          </span>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>

              {/* JSON Payload Inspector */}
              <div className="flex-1 flex flex-col bg-slate-900/60 border border-slate-800 rounded-xl overflow-hidden min-h-[300px]">
                <div className="px-4 py-2.5 bg-slate-900 border-b border-slate-800 flex items-center justify-between text-xs">
                  <span className="text-slate-400 font-mono text-[11px] flex items-center gap-1.5">
                    <FileCode className="w-3.5 h-3.5 text-blue-400" />
                    Payload Estructurado (JSON R4)
                  </span>
                  <span className="text-[10px] text-slate-500 font-mono">
                    {JSON.stringify(selectedLog.payload).length} bytes
                  </span>
                </div>

                <pre className="flex-1 p-4 bg-slate-950/90 text-slate-200 font-mono text-xs leading-relaxed overflow-x-auto overflow-y-auto selection:bg-orange-600 selection:text-white">
                  {JSON.stringify(selectedLog.payload, null, 2)}
                </pre>
              </div>
            </>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center text-slate-500 text-xs">
              Seleccione una transaccion del historial para inspeccionar el payload FHIR.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
