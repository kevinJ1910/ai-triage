'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { 
  Database, 
  User, 
  Search, 
  Clock, 
  Activity, 
  FileText, 
  Check, 
  ArrowRight, 
  Heart, 
  ShieldAlert, 
  Bed, 
  Sparkles,
  Phone,
  RefreshCw,
  ChevronLeft
} from 'lucide-react';
import { toast } from 'sonner';
import { fetchWithAuth } from '@/lib/api';

interface PatientEMR {
  id: number;
  patient_id: number;
  document_id: string;
  name: string;
  gender: string;
  birth_date: string;
  phone: string;
  insurance: string;
  level: number;
  ai_level: number;
  assigned_box: string;
  status: string;
  admission_time: string;
  justification: string;
  entities: {
    symptoms?: string[];
    vitals?: Record<string, string>;
  };
}

const ROMAN_LEVELS = ['', 'I', 'II', 'III', 'IV', 'V'];
const LEVEL_STYLES = [
  '',
  'bg-red-500/15 text-red-300 border-red-500/30',
  'bg-orange-500/15 text-orange-300 border-orange-500/30',
  'bg-amber-500/15 text-amber-300 border-amber-500/30',
  'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
  'bg-sky-500/15 text-sky-300 border-sky-500/30'
];

const LEVEL_BORDER_ACCENT = [
  '',
  'border-l-red-500',
  'border-l-orange-500',
  'border-l-amber-500',
  'border-l-emerald-500',
  'border-l-sky-500'
];

const AVAILABLE_BOXES = [
  'REAN-01',
  'REAN-02',
  'BOX-01',
  'BOX-02',
  'BOX-03',
  'BOX-04',
  'BOX-05',
  'BOX-06',
  'SALA-OBSERVACION'
];

export default function EMRSimulator() {
  const [patients, setPatients] = useState<PatientEMR[]>([]);
  const [selectedPatient, setSelectedPatient] = useState<PatientEMR | null>(null);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [assignedBox, setAssignedBox] = useState('');
  const [isSavingBox, setIsSavingBox] = useState(false);
  const [mobileView, setMobileView] = useState<'list' | 'detail'>('list');

  const fetchPatients = useCallback(async () => {
    try {
      const res = await fetchWithAuth('/api/triage/sessions/emr_patients/');
      if (res.ok) {
        const data = await res.json();
        setPatients(data);
        setSelectedPatient(prev => {
          if (!prev && data.length > 0) {
            setAssignedBox(data[0].assigned_box || 'BOX-01');
            return data[0];
          }
          return prev;
        });
      }
    } catch (err) {
      console.error('Error cargando pacientes EMR:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPatients();
  }, [fetchPatients]);

  const handleSelectPatient = (p: PatientEMR) => {
    setSelectedPatient(p);
    setAssignedBox(p.assigned_box || 'BOX-01');
    setMobileView('detail');
  };

  const handleAssignBox = async () => {
    if (!selectedPatient) return;
    setIsSavingBox(true);
    try {
      const res = await fetchWithAuth(`/api/triage/sessions/${selectedPatient.id}/assign_box/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ box_name: assignedBox }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Error al asignar box hospitalario');

      setPatients(prev => prev.map(p => 
        p.id === selectedPatient.id 
          ? { ...p, assigned_box: assignedBox, status: 'En Atencion' } 
          : p
      ));
      setSelectedPatient(prev => prev ? { ...prev, assigned_box: assignedBox, status: 'En Atencion' } : null);
      toast.success(data.message || `Paciente asignado a ${assignedBox} exitosamente.`);
    } catch (err: any) {
      toast.error(err.message || 'Fallo de comunicacion con el servidor HCE');
    } finally {
      setIsSavingBox(false);
    }
  };

  const filteredPatients = patients.filter(p => 
    p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    p.document_id.includes(searchQuery)
  );

  return (
    <div className="flex flex-col h-full w-full bg-slate-900/90 border border-slate-800/80 rounded-2xl overflow-hidden font-sans shadow-xl backdrop-blur-md">
      {/* Top Banner */}
      <div className="h-16 bg-slate-900 border-b border-slate-800/80 flex items-center justify-between px-5 shrink-0">
        <div className="flex items-center gap-3.5">
          <div className="w-9 h-9 rounded-xl bg-sky-500/10 border border-sky-500/20 flex items-center justify-center text-sky-400 shrink-0">
            <Database className="w-4 h-4" />
          </div>
          <div>
            <h1 className="text-sm font-semibold text-slate-100 flex items-center gap-2.5">
              <span>Simulador HCE / HIS Clinico Integrado</span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-sky-500/10 text-sky-400 border border-sky-500/20 font-medium">
                Urgencias Core v5.4
              </span>
            </h1>
            <p className="text-xs text-slate-400 mt-0.5">
              Conexion directa con Admisiones, Triaje Automatizado y Asignacion de Camillas
            </p>
          </div>
        </div>

        <button
          onClick={fetchPatients}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-800/80 hover:bg-slate-700 text-slate-200 text-xs rounded-lg border border-slate-700/60 font-medium transition-colors"
        >
          <RefreshCw className="w-3.5 h-3.5 text-slate-400" />
          <span>Actualizar Lista</span>
        </button>
      </div>

      {/* Main Workspace */}
      <div className="flex-1 grid grid-cols-1 md:grid-cols-12 overflow-hidden">
        {/* Left Column: Patient Queue (4 cols) */}
        <div className={`md:col-span-4 border-r border-slate-800/80 bg-slate-950/40 flex flex-col overflow-hidden ${
          mobileView === 'detail' ? 'hidden md:flex' : 'flex'
        }`}>
          {/* Search box */}
          <div className="p-3 border-b border-slate-800/80 bg-slate-900/40">
            <div className="relative">
              <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                placeholder="Buscar por nombre o cedula..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-9 pr-3 py-2 bg-slate-950/80 border border-slate-800 rounded-xl text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-sky-500 transition-colors"
              />
            </div>
          </div>

          <div className="px-4 py-2.5 text-xs font-medium text-slate-400 border-b border-slate-800/60 flex justify-between items-center bg-slate-950/30">
            <span className="font-semibold text-slate-300">Pacientes en Sala / Triaje ({filteredPatients.length})</span>
            <span className="text-emerald-400 flex items-center gap-1.5 text-[11px] font-mono">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
              En Espera
            </span>
          </div>

          {/* Patient list */}
          <div className="flex-1 overflow-y-auto p-3 space-y-2">
            {loading ? (
              <div className="flex flex-col items-center justify-center p-12 text-slate-400 text-xs gap-3">
                <div className="w-6 h-6 border-2 border-sky-500/30 border-t-sky-500 rounded-full animate-spin" />
                <span>Cargando admisiones...</span>
              </div>
            ) : filteredPatients.length === 0 ? (
              <div className="p-8 text-center text-slate-500 text-xs">
                No hay pacientes en la cola de urgencias.
              </div>
            ) : (
              filteredPatients.map((p) => {
                const isSelected = selectedPatient?.id === p.id;
                const borderAccent = LEVEL_BORDER_ACCENT[p.level] || 'border-l-slate-700';
                return (
                  <button
                    key={p.id}
                    onClick={() => handleSelectPatient(p)}
                    className={`w-full text-left p-3.5 rounded-xl border border-l-4 transition-all relative flex flex-col gap-2 ${borderAccent} ${
                      isSelected
                        ? 'bg-sky-950/30 border-sky-500/50 shadow-md shadow-sky-950/50'
                        : 'bg-slate-900/60 border-slate-800/80 hover:bg-slate-800/60'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="font-semibold text-xs text-slate-100 truncate">
                        {p.name}
                      </div>
                      <span className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded-full border shrink-0 ${LEVEL_STYLES[p.level] || 'bg-slate-800 text-slate-400'}`}>
                        Nivel {ROMAN_LEVELS[p.level] || p.level}
                      </span>
                    </div>

                    <div className="flex items-center justify-between text-[11px] text-slate-400 font-mono">
                      <span>Doc: {p.document_id}</span>
                      <span className="text-slate-400 flex items-center gap-1">
                        <Clock className="w-3 h-3 text-slate-500" />
                        {p.admission_time}
                      </span>
                    </div>

                    <div className="flex items-center justify-between pt-1.5 border-t border-slate-800/60 text-[11px]">
                      <span className="text-slate-400 flex items-center gap-1">
                        <Bed className="w-3.5 h-3.5 text-slate-500" />
                        <span className="font-mono">{p.assigned_box || 'Sin Box'}</span>
                      </span>
                      <span className={`font-medium ${
                        p.status.includes('Reanimacion') 
                          ? 'text-red-400' 
                          : p.status === 'En Atencion' 
                          ? 'text-emerald-400' 
                          : 'text-amber-400'
                      }`}>
                        {p.status}
                      </span>
                    </div>
                  </button>
                );
              })
            )}
          </div>
        </div>

        {/* Right Column: Selected Patient Clinical Record (8 cols) */}
        <div className={`md:col-span-8 bg-slate-950/70 p-4 sm:p-6 flex flex-col overflow-y-auto space-y-5 ${
          mobileView === 'list' ? 'hidden md:flex' : 'flex'
        }`}>
          {/* Mobile Back Button */}
          <div className="md:hidden flex items-center pb-2">
            <button
              onClick={() => setMobileView('list')}
              className="flex items-center gap-1.5 text-xs font-semibold text-sky-400 hover:text-sky-300 py-1.5 px-3 rounded-lg bg-slate-900 border border-slate-800"
            >
              <ChevronLeft className="w-4 h-4" />
              <span>Volver a Cola de Pacientes</span>
            </button>
          </div>

          {selectedPatient ? (
            <>
              {/* Header profile card */}
              <div className="bg-slate-900/90 border border-slate-800/80 rounded-2xl p-5 shadow-lg space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-slate-800/80">
                  <div className="flex items-center gap-3.5">
                    <div className="w-11 h-11 rounded-xl bg-sky-950 border border-sky-800/60 flex items-center justify-center text-sky-300 font-bold text-sm shadow-inner shrink-0">
                      {selectedPatient.name[0]}
                    </div>
                    <div>
                      <h2 className="text-base font-semibold text-slate-100 flex items-center gap-2.5">
                        <span>{selectedPatient.name}</span>
                        <span className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded-full border ${LEVEL_STYLES[selectedPatient.level]}`}>
                          Triaje Nivel {ROMAN_LEVELS[selectedPatient.level]}
                        </span>
                      </h2>
                      <p className="text-xs text-slate-400 mt-0.5">
                        Identificacion: <span className="font-mono text-slate-200">{selectedPatient.document_id}</span> | EPS: <span className="text-slate-300">{selectedPatient.insurance}</span>
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <span className="text-xs px-3 py-1 rounded-full font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center gap-1.5">
                      <Activity className="w-3.5 h-3.5" />
                      <span>{selectedPatient.status}</span>
                    </span>
                  </div>
                </div>

                {/* Patient Demographics Grid */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs">
                  <div className="p-2.5 rounded-xl bg-slate-950/50 border border-slate-800/60">
                    <span className="text-[10px] text-slate-400 uppercase font-semibold block">Genero</span>
                    <span className="text-slate-200 font-medium capitalize mt-0.5 block">{selectedPatient.gender}</span>
                  </div>
                  <div className="p-2.5 rounded-xl bg-slate-950/50 border border-slate-800/60">
                    <span className="text-[10px] text-slate-400 uppercase font-semibold block">Nacimiento</span>
                    <span className="text-slate-200 font-mono mt-0.5 block">{selectedPatient.birth_date}</span>
                  </div>
                  <div className="p-2.5 rounded-xl bg-slate-950/50 border border-slate-800/60">
                    <span className="text-[10px] text-slate-400 uppercase font-semibold block">Telefono</span>
                    <span className="text-slate-200 font-mono mt-0.5 block">{selectedPatient.phone}</span>
                  </div>
                  <div className="p-2.5 rounded-xl bg-slate-950/50 border border-slate-800/60">
                    <span className="text-[10px] text-slate-400 uppercase font-semibold block">Ingreso</span>
                    <span className="text-slate-200 font-mono mt-0.5 block">{selectedPatient.admission_time}</span>
                  </div>
                </div>
              </div>

              {/* Box Assignment Section */}
              <div className="bg-slate-900/80 border border-slate-800/80 rounded-2xl p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                  <div className="p-2.5 bg-sky-500/10 rounded-xl text-sky-400 border border-sky-500/20 shrink-0">
                    <Bed className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-200">
                      Asignacion de Box / Camilla Hospitalaria
                    </h3>
                    <p className="text-xs text-slate-400 mt-0.5">
                      Ubicacion actual del paciente en urgencias: <span className="font-mono font-semibold text-sky-400">{selectedPatient.assigned_box || 'Sin asignar'}</span>
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-2.5 w-full sm:w-auto">
                  <select
                    value={assignedBox}
                    onChange={(e) => setAssignedBox(e.target.value)}
                    className="px-3.5 py-2 bg-slate-950 border border-slate-700/80 rounded-xl text-xs text-slate-200 font-mono focus:outline-none focus:border-sky-500 transition-colors"
                  >
                    {AVAILABLE_BOXES.map((b) => (
                      <option key={b} value={b}>{b}</option>
                    ))}
                  </select>
                  <button
                    onClick={handleAssignBox}
                    disabled={isSavingBox}
                    className="flex items-center gap-1.5 px-4 py-2 bg-sky-600 hover:bg-sky-500 disabled:opacity-50 text-white text-xs font-semibold rounded-xl transition-all shadow-md shadow-sky-600/20 shrink-0"
                  >
                    {isSavingBox ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />}
                    <span>Asignar Box</span>
                  </button>
                </div>
              </div>

              {/* Vitals and Symptoms */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {/* Vitals */}
                <div className="bg-slate-900/80 border border-slate-800/80 rounded-2xl p-4 space-y-3">
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-300 flex items-center gap-2 pb-2 border-b border-slate-800/80">
                    <Heart className="w-3.5 h-3.5 text-rose-400" />
                    <span>Signos Vitales Registrados</span>
                  </h3>
                  <div className="grid grid-cols-2 gap-2.5 pt-1 text-xs">
                    {selectedPatient.entities?.vitals ? (
                      Object.entries(selectedPatient.entities.vitals).map(([k, v]) => (
                        <div key={k} className="p-3 bg-slate-950/70 border border-slate-800/80 rounded-xl">
                          <span className="text-[10px] text-slate-400 uppercase font-mono block font-semibold">{k}</span>
                          <span className="text-sm font-semibold text-sky-200 font-mono mt-0.5 block">{v}</span>
                        </div>
                      ))
                    ) : (
                      <div className="col-span-2 text-slate-400 text-xs py-3 text-center">
                        Signos vitales normales o no especificados en triaje inicial.
                      </div>
                    )}
                  </div>
                </div>

                {/* Symptoms */}
                <div className="bg-slate-900/80 border border-slate-800/80 rounded-2xl p-4 space-y-3">
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-300 flex items-center gap-2 pb-2 border-b border-slate-800/80">
                    <ShieldAlert className="w-3.5 h-3.5 text-amber-400" />
                    <span>Sintomatologia Extraida por Triaje</span>
                  </h3>
                  <div className="flex flex-wrap gap-2 pt-1">
                    {selectedPatient.entities?.symptoms && selectedPatient.entities.symptoms.length > 0 ? (
                      selectedPatient.entities.symptoms.map((sym, idx) => (
                        <span
                          key={idx}
                          className="px-3 py-1 rounded-lg bg-amber-500/10 text-amber-300 border border-amber-500/20 text-xs font-medium"
                        >
                          {sym}
                        </span>
                      ))
                    ) : (
                      <span className="text-xs text-slate-400 py-3 block text-center w-full">Sin sintomas detallados</span>
                    )}
                  </div>
                </div>
              </div>

              {/* Clinical Justification */}
              <div className="bg-slate-900/80 border border-slate-800/80 rounded-2xl p-4 space-y-2">
                <div className="flex items-center justify-between pb-2 border-b border-slate-800/80">
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-300 flex items-center gap-2">
                    <FileText className="w-3.5 h-3.5 text-sky-400" />
                    <span>Justificacion Clinica del Triaje</span>
                  </h3>
                  <span className="text-[11px] font-mono text-slate-500">
                    Decision Asistida por IA
                  </span>
                </div>
                <div className="p-3.5 bg-slate-950/80 rounded-xl border border-slate-800/80 text-xs text-slate-200 leading-relaxed italic">
                  {selectedPatient.justification || 'Sin justificacion registrada.'}
                </div>
              </div>
            </>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center text-slate-400 text-xs py-20">
              Seleccione un paciente de la cola para visualizar su historia clinica.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
