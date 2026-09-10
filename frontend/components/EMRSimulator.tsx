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
  RefreshCw
} from 'lucide-react';
import { toast } from 'sonner';

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
  'bg-red-500/20 text-red-300 border-red-500/40',
  'bg-orange-500/20 text-orange-300 border-orange-500/40',
  'bg-amber-500/20 text-amber-300 border-amber-500/40',
  'bg-emerald-500/20 text-emerald-300 border-emerald-500/40',
  'bg-blue-500/20 text-blue-300 border-blue-500/40'
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

  const fetchPatients = useCallback(async () => {
    try {
      const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null;
      const headers: Record<string, string> = {};
      if (token) headers['Authorization'] = `Bearer ${token}`;

      const res = await fetch('/api/triage/sessions/emr_patients/', { headers });
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
  };

  const handleAssignBox = () => {
    if (!selectedPatient) return;
    setIsSavingBox(true);
    setTimeout(() => {
      setPatients(prev => prev.map(p => 
        p.id === selectedPatient.id 
          ? { ...p, assigned_box: assignedBox, status: 'En Atencion' } 
          : p
      ));
      setSelectedPatient(prev => prev ? { ...prev, assigned_box: assignedBox, status: 'En Atencion' } : null);
      setIsSavingBox(false);
      toast.success(`Paciente asignado a ${assignedBox} exitosamente.`);
    }, 600);
  };

  const filteredPatients = patients.filter(p => 
    p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    p.document_id.includes(searchQuery)
  );

  return (
    <div className="flex flex-col h-full w-full bg-slate-950 border border-slate-800 rounded-xl overflow-hidden font-sans shadow-2xl">
      {/* Top Banner */}
      <div className="h-14 bg-slate-900 border-b border-slate-800 flex items-center justify-between px-5 shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-blue-600/20 border border-blue-500/30 flex items-center justify-center text-blue-400">
            <Database className="w-4 h-4" />
          </div>
          <div>
            <h1 className="text-xs font-bold uppercase tracking-wider text-slate-100 flex items-center gap-2">
              Simulador HCE / HIS Clinico Integrado
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20">
                Urgencias Core v5.4
              </span>
            </h1>
            <p className="text-[10px] text-slate-400">
              Conexion directa con Admisiones, Triaje Automatizado y Asignacion de Camillas
            </p>
          </div>
        </div>

        <button
          onClick={fetchPatients}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-800/80 hover:bg-slate-800 text-slate-300 text-xs rounded-lg border border-slate-700 transition-colors"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Actualizar Lista
        </button>
      </div>

      {/* Main Workspace */}
      <div className="flex-1 grid grid-cols-1 md:grid-cols-12 overflow-hidden">
        {/* Left Column: Patient Queue (4 cols) */}
        <div className="md:col-span-4 border-r border-slate-800 bg-slate-900/60 flex flex-col overflow-hidden">
          {/* Search box */}
          <div className="p-3 border-b border-slate-800/80">
            <div className="relative">
              <Search className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                placeholder="Buscar por nombre o cedula..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-9 pr-3 py-1.5 bg-slate-950/80 border border-slate-800 rounded-lg text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-blue-500"
              />
            </div>
          </div>

          <div className="px-4 py-2 text-[10px] font-bold uppercase tracking-wider text-slate-400 border-b border-slate-800/40 flex justify-between items-center">
            <span>Pacientes en Sala / Triaje ({filteredPatients.length})</span>
            <span className="text-emerald-400 flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
              En Espera
            </span>
          </div>

          {/* Patient list */}
          <div className="flex-1 overflow-y-auto p-3 space-y-2">
            {loading ? (
              <div className="flex flex-col items-center justify-center p-8 text-slate-500 text-xs gap-2">
                <RefreshCw className="w-4 h-4 animate-spin" />
                Cargando admisiones...
              </div>
            ) : filteredPatients.length === 0 ? (
              <div className="p-6 text-center text-slate-500 text-xs">
                No hay pacientes en la cola de urgencias.
              </div>
            ) : (
              filteredPatients.map((p) => {
                const isSelected = selectedPatient?.id === p.id;
                return (
                  <button
                    key={p.id}
                    onClick={() => handleSelectPatient(p)}
                    className={`w-full text-left p-3 rounded-xl border transition-all relative overflow-hidden flex flex-col gap-1.5 ${
                      isSelected
                        ? 'bg-blue-600/15 border-blue-500/50 shadow-md shadow-blue-600/10'
                        : 'bg-slate-900/90 border-slate-800/80 hover:bg-slate-800/60'
                    }`}
                  >
                    <div className="flex items-start justify-between">
                      <div className="font-semibold text-xs text-slate-100 truncate pr-2">
                        {p.name}
                      </div>
                      <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded border shrink-0 ${LEVEL_STYLES[p.level] || 'bg-slate-800 text-slate-400'}`}>
                        Nivel {ROMAN_LEVELS[p.level] || p.level}
                      </span>
                    </div>

                    <div className="flex items-center justify-between text-[11px] text-slate-400 font-mono">
                      <span>Doc: {p.document_id}</span>
                      <span className="text-slate-500 flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {p.admission_time}
                      </span>
                    </div>

                    <div className="flex items-center justify-between pt-1 border-t border-slate-800/60 text-[10px]">
                      <span className="text-slate-400 flex items-center gap-1">
                        <Bed className="w-3 h-3 text-slate-500" />
                        {p.assigned_box || 'Sin Box'}
                      </span>
                      <span className={`font-semibold ${
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
        <div className="md:col-span-8 bg-slate-950 p-6 flex flex-col overflow-y-auto space-y-6">
          {selectedPatient ? (
            <>
              {/* Header profile card */}
              <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 shadow-lg space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-800">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full bg-gradient-to-tr from-blue-600 to-indigo-600 flex items-center justify-center text-white font-bold text-sm shadow-md">
                      {selectedPatient.name[0]}
                    </div>
                    <div>
                      <h2 className="text-base font-bold text-slate-100 flex items-center gap-2">
                        {selectedPatient.name}
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded border ${LEVEL_STYLES[selectedPatient.level]}`}>
                          Triaje Nivel {ROMAN_LEVELS[selectedPatient.level]}
                        </span>
                      </h2>
                      <p className="text-xs text-slate-400">
                        Identificacion: <span className="font-mono text-slate-200">{selectedPatient.document_id}</span> | EPS: <span className="text-slate-300">{selectedPatient.insurance}</span>
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <span className="text-xs px-3 py-1 rounded-full font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center gap-1.5">
                      <Activity className="w-3.5 h-3.5" />
                      {selectedPatient.status}
                    </span>
                  </div>
                </div>

                {/* Patient Demographics Grid */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs">
                  <div>
                    <span className="text-[10px] text-slate-500 uppercase font-semibold block">Genero</span>
                    <span className="text-slate-200 font-medium capitalize">{selectedPatient.gender}</span>
                  </div>
                  <div>
                    <span className="text-[10px] text-slate-500 uppercase font-semibold block">Nacimiento</span>
                    <span className="text-slate-200 font-mono">{selectedPatient.birth_date}</span>
                  </div>
                  <div>
                    <span className="text-[10px] text-slate-500 uppercase font-semibold block">Telefono</span>
                    <span className="text-slate-200 font-mono">{selectedPatient.phone}</span>
                  </div>
                  <div>
                    <span className="text-[10px] text-slate-500 uppercase font-semibold block">Ingreso</span>
                    <span className="text-slate-200 font-mono">{selectedPatient.admission_time}</span>
                  </div>
                </div>
              </div>

              {/* Box Assignment Section */}
              <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-blue-500/10 rounded-lg text-blue-400 border border-blue-500/20">
                    <Bed className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="text-xs font-bold uppercase tracking-wider text-slate-200">
                      Asignacion de Box / Camilla Hospitalaria
                    </h3>
                    <p className="text-xs text-slate-400">
                      Ubicacion actual del paciente en urgencias: <span className="font-bold text-blue-400">{selectedPatient.assigned_box}</span>
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-2 w-full sm:w-auto">
                  <select
                    value={assignedBox}
                    onChange={(e) => setAssignedBox(e.target.value)}
                    className="px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-blue-500"
                  >
                    {AVAILABLE_BOXES.map((b) => (
                      <option key={b} value={b}>{b}</option>
                    ))}
                  </select>
                  <button
                    onClick={handleAssignBox}
                    disabled={isSavingBox}
                    className="flex items-center gap-1.5 px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-xs font-bold rounded-lg transition-colors shadow-md shadow-blue-600/20"
                  >
                    {isSavingBox ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />}
                    Asignar Box
                  </button>
                </div>
              </div>

              {/* Vitals and Symptoms */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {/* Vitals */}
                <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 space-y-3">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center gap-1.5 pb-2 border-b border-slate-800">
                    <Heart className="w-3.5 h-3.5 text-rose-400" />
                    Signos Vitales Registrados
                  </h3>
                  <div className="grid grid-cols-2 gap-3 pt-1 text-xs">
                    {selectedPatient.entities?.vitals ? (
                      Object.entries(selectedPatient.entities.vitals).map(([k, v]) => (
                        <div key={k} className="p-2.5 bg-slate-950/70 border border-slate-800/80 rounded-lg">
                          <span className="text-[10px] text-slate-500 uppercase font-mono block font-semibold">{k}</span>
                          <span className="text-sm font-bold text-slate-100 font-mono">{v}</span>
                        </div>
                      ))
                    ) : (
                      <div className="col-span-2 text-slate-500 text-xs py-2">
                        Signos vitales normales o no especificados en triaje inicial.
                      </div>
                    )}
                  </div>
                </div>

                {/* Symptoms */}
                <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 space-y-3">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center gap-1.5 pb-2 border-b border-slate-800">
                    <ShieldAlert className="w-3.5 h-3.5 text-amber-400" />
                    Sintomatologia Extraida por Triaje
                  </h3>
                  <div className="flex flex-wrap gap-2 pt-1">
                    {selectedPatient.entities?.symptoms && selectedPatient.entities.symptoms.length > 0 ? (
                      selectedPatient.entities.symptoms.map((sym, idx) => (
                        <span
                          key={idx}
                          className="px-2.5 py-1 rounded-lg bg-amber-500/10 text-amber-300 border border-amber-500/20 text-xs font-medium"
                        >
                          {sym}
                        </span>
                      ))
                    ) : (
                      <span className="text-xs text-slate-500">Sin sintomas detallados</span>
                    )}
                  </div>
                </div>
              </div>

              {/* Clinical Justification */}
              <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 space-y-2">
                <div className="flex items-center justify-between pb-2 border-b border-slate-800">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
                    <Sparkles className="w-3.5 h-3.5 text-blue-400" />
                    Justificacion Clinica del Triaje
                  </h3>
                  <span className="text-[10px] font-mono text-slate-500">
                    Decision Asistida por IA
                  </span>
                </div>
                <div className="p-3 bg-slate-950/80 rounded-lg border border-slate-800 text-xs text-slate-300 font-serif leading-relaxed italic">
                  {selectedPatient.justification || 'Sin justificacion registrada.'}
                </div>
              </div>
            </>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center text-slate-500 text-xs">
              Seleccione un paciente de la cola para visualizar su historia clinica.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
