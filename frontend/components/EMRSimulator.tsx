'use client';

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { 
  Database, 
  Search, 
  Clock, 
  Activity, 
  FileText, 
  Check, 
  Heart, 
  ShieldAlert, 
  Bed, 
  RefreshCw,
  ChevronLeft,
  LayoutGrid,
  Plus,
  X,
  Sparkles,
  Trash2,
  Users,
  LogOut,
  HelpCircle,
  Layers,
  Edit3,
  ClipboardEdit,
  Save,
  CheckCircle2
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
    // El backend guarda los signos vitales como texto compacto: "PA: 145/95 mmHg".
    vitals?: string[];
    evolution_notes?: string;
  };
}

// "PA: 145/95 mmHg" -> ["PA", "145/95 mmHg"]; el texto libre del LLM sin etiqueta queda como valor.
function splitVital(vital: string): [string, string] {
  const sep = vital.indexOf(':');
  if (sep <= 0) return ['Signo vital', vital.trim()];
  return [vital.slice(0, sep).trim(), vital.slice(sep + 1).trim()];
}

interface HospitalBox {
  code: string;
  area: string;
  type: string;
  equipment: string;
  status: 'Libre' | 'Ocupado' | 'En Desinfeccion' | 'Mantenimiento';
  occupant?: {
    session_id: number;
    patient_id: number;
    patient_name: string;
    document_id: string;
    triage_level: number;
    care_status: string;
    admission_time: string;
  } | null;
  is_custom?: boolean;
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

const DEFAULT_BOXES_DATA: HospitalBox[] = [
  { code: 'REAN-01', area: 'Reanimacion', type: 'Box Vital', equipment: 'Monitor invasivo, Desfibrilador, Ventilador', status: 'Libre' },
  { code: 'REAN-02', area: 'Reanimacion', type: 'Box Vital', equipment: 'Monitor invasivo, Carro de paro', status: 'Libre' },
  { code: 'BOX-01', area: 'Boxes Generales', type: 'Camilla Urgencias', equipment: 'Monitor de signos vitales, Oxigeno', status: 'Libre' },
  { code: 'BOX-02', area: 'Boxes Generales', type: 'Camilla Urgencias', equipment: 'Monitor de signos vitales, Oxigeno', status: 'Libre' },
  { code: 'BOX-03', area: 'Boxes Generales', type: 'Camilla Urgencias', equipment: 'Monitor de signos vitales, Oxigeno', status: 'Libre' },
  { code: 'BOX-04', area: 'Boxes Generales', type: 'Camilla Urgencias', equipment: 'Monitor de signos vitales', status: 'Libre' },
  { code: 'BOX-05', area: 'Boxes Generales', type: 'Camilla Urgencias', equipment: 'Monitor de signos vitales', status: 'Libre' },
  { code: 'BOX-06', area: 'Boxes Generales', type: 'Camilla Urgencias', equipment: 'Monitor de signos vitales', status: 'Libre' },
  { code: 'SALA-OBSERVACION', area: 'Observacion', type: 'Cama Hospitalaria', equipment: 'Toma de oxigeno, Succion', status: 'Libre' },
  { code: 'AISL-01', area: 'Aislamiento', type: 'Box Presion Negativa', equipment: 'Filtro HEPA, Monitor de signos', status: 'Libre' },
];

const AREA_OPTIONS = [
  'Todas',
  'Reanimacion',
  'Boxes Generales',
  'Observacion',
  'Aislamiento',
  'Urgencias Pediatria'
];

const EQUIPMENT_PRESETS = [
  'Monitor de signos vitales',
  'Oxigeno Central',
  'Ventilador Mecanico',
  'Desfibrilador',
  'Bomba de Infusion',
  'Succion Central',
  'Monitor Invasivo',
  'Filtro HEPA'
];

const CARE_STATUS_OPTIONS = [
  'En Espera',
  'En Atencion',
  'Pendiente Paraclinicos',
  'En Observacion',
  'Alta Medica'
];

export default function EMRSimulator() {
  const [activeTab, setActiveTab] = useState<'patients' | 'census'>('patients');
  const [patients, setPatients] = useState<PatientEMR[]>([]);
  const [boxes, setBoxes] = useState<HospitalBox[]>(DEFAULT_BOXES_DATA);
  const [selectedPatient, setSelectedPatient] = useState<PatientEMR | null>(null);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [assignedBox, setAssignedBox] = useState('BOX-01');
  const [isSavingBox, setIsSavingBox] = useState(false);
  const [mobileView, setMobileView] = useState<'list' | 'detail'>('list');

  // Interactive patient care state & clinical evolution
  const [patientCareStatus, setPatientCareStatus] = useState<string>('En Atencion');
  const [evolutionNote, setEvolutionNote] = useState<string>('');
  const [isSavingClinicalCare, setIsSavingClinicalCare] = useState(false);

  // Census view customization and filters
  const [censusFilterStatus, setCensusFilterStatus] = useState<string>('Todos');
  const [censusFilterArea, setCensusFilterArea] = useState<string>('Todas');
  const [censusViewMode, setCensusViewMode] = useState<'grouped' | 'grid'>('grouped');
  const [showExplanation, setShowExplanation] = useState(false);

  // Modals state
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [editingBox, setEditingBox] = useState<HospitalBox | null>(null);

  // Form states for Box creation / edition
  const [boxFormCode, setBoxFormCode] = useState('');
  const [boxFormArea, setBoxFormArea] = useState('Boxes Generales');
  const [boxFormType, setBoxFormType] = useState('Camilla Urgencias');
  const [boxFormEquipment, setBoxFormEquipment] = useState<string[]>(['Monitor de signos vitales']);

  // Quick assign modal from Census
  const [quickAssignBoxCode, setQuickAssignBoxCode] = useState<string | null>(null);
  const [quickAssignSessionId, setQuickAssignSessionId] = useState<number | ''>('');

  const fetchCensus = useCallback(async () => {
    try {
      const res = await fetchWithAuth('/api/triage/sessions/boxes_census/');
      if (res.ok) {
        const data = await res.json();
        if (data.boxes && Array.isArray(data.boxes)) {
          setBoxes(data.boxes);
          return;
        }
      }
    } catch {
      // Census endpoint fallback logic handled gracefully
    }
  }, []);

  const fetchPatients = useCallback(async () => {
    try {
      const res = await fetchWithAuth('/api/triage/sessions/emr_patients/');
      if (res.ok) {
        const data = await res.json();
        setPatients(data);
        setSelectedPatient(prev => {
          if (!prev && data.length > 0) {
            setAssignedBox(data[0].assigned_box || 'BOX-01');
            setPatientCareStatus(data[0].status || 'En Atencion');
            setEvolutionNote(data[0].entities?.evolution_notes || '');
            return data[0];
          }
          if (prev) {
            const updated = data.find((p: PatientEMR) => p.id === prev.id);
            if (updated) {
              setPatientCareStatus(updated.status || 'En Atencion');
              setEvolutionNote(updated.entities?.evolution_notes || '');
              return updated;
            }
            return prev;
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

  const loadAll = useCallback(() => {
    fetchPatients();
    fetchCensus();
  }, [fetchPatients, fetchCensus]);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  // Derived available boxes list
  const availableBoxCodes = useMemo(() => {
    const set = new Set<string>();
    DEFAULT_BOXES_DATA.forEach(b => set.add(b.code));
    boxes.forEach(b => set.add(b.code));
    patients.forEach(p => {
      if (p.assigned_box) set.add(p.assigned_box);
    });
    return Array.from(set).sort();
  }, [boxes, patients]);

  const handleSelectPatient = (p: PatientEMR) => {
    setSelectedPatient(p);
    setAssignedBox(p.assigned_box || 'BOX-01');
    setPatientCareStatus(p.status || 'En Atencion');
    setEvolutionNote(p.entities?.evolution_notes || '');
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
      if (!res.ok) throw new Error(data.detail || data.error || 'Error al asignar box hospitalario');

      setPatients(prev => prev.map(p => 
        p.id === selectedPatient.id 
          ? { ...p, assigned_box: assignedBox, status: patientCareStatus } 
          : p
      ));
      setSelectedPatient(prev => prev ? { ...prev, assigned_box: assignedBox, status: patientCareStatus } : null);
      
      // Actualizar censo local
      setBoxes(prev => prev.map(b => {
        if (b.code === assignedBox) {
          return {
            ...b,
            status: 'Ocupado',
            occupant: {
              session_id: selectedPatient.id,
              patient_id: selectedPatient.patient_id,
              patient_name: selectedPatient.name,
              document_id: selectedPatient.document_id,
              triage_level: selectedPatient.level,
              care_status: patientCareStatus,
              admission_time: selectedPatient.admission_time
            }
          };
        }
        return b;
      }));

      toast.success(data.message || `Paciente asignado a ${assignedBox} exitosamente.`);
    } catch (err: any) {
      toast.error(err.message || 'Fallo de comunicacion con el servidor HCE');
    } finally {
      setIsSavingBox(false);
    }
  };

  const handleUpdateCareStatusAndNotes = async () => {
    if (!selectedPatient) return;
    setIsSavingClinicalCare(true);
    try {
      const res = await fetchWithAuth(`/api/triage/sessions/${selectedPatient.id}/update_care_status/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          status: patientCareStatus,
          evolution_notes: evolutionNote
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || data.error || 'Error al actualizar ficha de atencion');

      setPatients(prev => prev.map(p => 
        p.id === selectedPatient.id 
          ? { 
              ...p, 
              status: patientCareStatus, 
              entities: { ...p.entities, evolution_notes: evolutionNote } 
            } 
          : p
      ));
      setSelectedPatient(prev => prev ? {
        ...prev,
        status: patientCareStatus,
        entities: { ...prev.entities, evolution_notes: evolutionNote }
      } : null);

      toast.success(data.message || 'Estado asistencial y notas clinicas guardadas.');
    } catch (err: any) {
      toast.error(err.message || 'Error guardando estado clinico');
    } finally {
      setIsSavingClinicalCare(false);
    }
  };

  const handleReleaseBox = async (sessionId: number, currentBox: string) => {
    try {
      const res = await fetchWithAuth(`/api/triage/sessions/${sessionId}/release_box/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: 'Alta Medica' }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || data.error || 'Error al liberar box');

      setPatients(prev => prev.map(p => 
        p.id === sessionId ? { ...p, assigned_box: '', status: 'Alta Medica' } : p
      ));
      if (selectedPatient?.id === sessionId) {
        setSelectedPatient(prev => prev ? { ...prev, assigned_box: '', status: 'Alta Medica' } : null);
        setPatientCareStatus('Alta Medica');
      }

      setBoxes(prev => prev.map(b => {
        if (b.code === currentBox) {
          return { ...b, status: 'Libre', occupant: null };
        }
        return b;
      }));

      toast.success(data.message || `Box ${currentBox} liberado exitosamente.`);
    } catch (err: any) {
      toast.error(err.message || 'Error liberando box');
    }
  };

  const handleToggleCleaning = async (boxCode: string, currentStatus: string) => {
    const nextState = currentStatus === 'En Desinfeccion' ? 'Libre' : 'En Desinfeccion';
    try {
      await fetchWithAuth('/api/triage/sessions/manage_boxes/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'update_state', code: boxCode, state: nextState }),
      });
      setBoxes(prev => prev.map(b => b.code === boxCode ? { ...b, status: nextState as any } : b));
      toast.success(`Box ${boxCode} marcado como ${nextState}.`);
    } catch {
      setBoxes(prev => prev.map(b => b.code === boxCode ? { ...b, status: nextState as any } : b));
    }
  };

  const openCreateBoxModal = () => {
    setBoxFormCode('');
    setBoxFormArea('Boxes Generales');
    setBoxFormType('Camilla Urgencias');
    setBoxFormEquipment(['Monitor de signos vitales']);
    setIsCreateModalOpen(true);
  };

  const openEditBoxModal = (box: HospitalBox) => {
    setEditingBox(box);
    setBoxFormCode(box.code);
    setBoxFormArea(box.area);
    setBoxFormType(box.type);
    const eqList = box.equipment ? box.equipment.split(',').map(s => s.trim()).filter(Boolean) : [];
    setBoxFormEquipment(eqList);
    setIsEditModalOpen(true);
  };

  const handleCreateBox = async (e: React.FormEvent) => {
    e.preventDefault();
    const code = boxFormCode.trim().toUpperCase();
    if (!code) {
      toast.error('Ingrese un codigo o identificador para el box');
      return;
    }
    if (boxes.some(b => b.code === code)) {
      toast.error(`El box ${code} ya existe en el censo.`);
      return;
    }

    const payload = {
      action: 'create',
      code,
      area: boxFormArea,
      type: boxFormType,
      equipment: boxFormEquipment.join(', ')
    };

    try {
      const res = await fetchWithAuth('/api/triage/sessions/manage_boxes/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (res.ok) {
        const data = await res.json();
        toast.success(data.message || `Box ${code} creado exitosamente.`);
      }
    } catch {
      // Local fallback
    }

    const created: HospitalBox = {
      code,
      area: boxFormArea,
      type: boxFormType,
      equipment: boxFormEquipment.join(', '),
      status: 'Libre',
      is_custom: true
    };
    setBoxes(prev => [...prev, created]);
    setAssignedBox(code); // Seleccionar automáticamente el box creado
    setIsCreateModalOpen(false);
  };

  const handleSaveEditBox = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingBox) return;

    const payload = {
      action: 'update',
      code: editingBox.code,
      area: boxFormArea,
      type: boxFormType,
      equipment: boxFormEquipment.join(', ')
    };

    try {
      const res = await fetchWithAuth('/api/triage/sessions/manage_boxes/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (res.ok) {
        toast.success(`Box ${editingBox.code} actualizado exitosamente.`);
      }
    } catch {
      // Local fallback
    }

    setBoxes(prev => prev.map(b => {
      if (b.code === editingBox.code) {
        return {
          ...b,
          area: boxFormArea,
          type: boxFormType,
          equipment: boxFormEquipment.join(', ')
        };
      }
      return b;
    }));

    setIsEditModalOpen(false);
    setEditingBox(null);
  };

  const handleDeleteBox = async (boxCode: string) => {
    try {
      await fetchWithAuth('/api/triage/sessions/manage_boxes/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'delete', code: boxCode }),
      });
      toast.success(`Box ${boxCode} eliminado.`);
    } catch {
      // local fallback
    }
    setBoxes(prev => prev.filter(b => b.code !== boxCode));
  };

  const handleQuickAssignFromCensus = async () => {
    if (!quickAssignBoxCode || !quickAssignSessionId) return;
    const targetSession = patients.find(p => p.id === Number(quickAssignSessionId));
    if (!targetSession) return;

    try {
      const res = await fetchWithAuth(`/api/triage/sessions/${targetSession.id}/assign_box/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ box_name: quickAssignBoxCode }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || data.error || 'Error al asignar');

      setPatients(prev => prev.map(p => 
        p.id === targetSession.id ? { ...p, assigned_box: quickAssignBoxCode, status: 'En Atencion' } : p
      ));
      setBoxes(prev => prev.map(b => {
        if (b.code === quickAssignBoxCode) {
          return {
            ...b,
            status: 'Ocupado',
            occupant: {
              session_id: targetSession.id,
              patient_id: targetSession.patient_id,
              patient_name: targetSession.name,
              document_id: targetSession.document_id,
              triage_level: targetSession.level,
              care_status: 'En Atencion',
              admission_time: targetSession.admission_time
            }
          };
        }
        return b;
      }));

      toast.success(`Paciente ${targetSession.name} asignado a ${quickAssignBoxCode}.`);
      setQuickAssignBoxCode(null);
      setQuickAssignSessionId('');
    } catch (err: any) {
      toast.error(err.message || 'Error en asignacion rapida');
    }
  };

  const filteredPatients = patients.filter(p => 
    p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    p.document_id.includes(searchQuery)
  );

  // Synchronize occupied status in boxes from active patients
  const displayedBoxes = useMemo(() => {
    const occupiedByPatient: Record<string, PatientEMR> = {};
    patients.forEach(p => {
      if (p.assigned_box && !p.status.includes('Alta')) {
        occupiedByPatient[p.assigned_box] = p;
      }
    });

    return boxes.map(b => {
      const occ = occupiedByPatient[b.code];
      if (occ) {
        return {
          ...b,
          status: 'Ocupado' as const,
          occupant: {
            session_id: occ.id,
            patient_id: occ.patient_id,
            patient_name: occ.name,
            document_id: occ.document_id,
            triage_level: occ.level,
            care_status: occ.status,
            admission_time: occ.admission_time
          }
        };
      }
      return b;
    });
  }, [boxes, patients]);

  const censusFilteredBoxes = useMemo(() => {
    return displayedBoxes.filter(b => {
      if (censusFilterStatus !== 'Todos' && b.status !== censusFilterStatus) return false;
      if (censusFilterArea !== 'Todas' && b.area !== censusFilterArea) return false;
      return true;
    });
  }, [displayedBoxes, censusFilterStatus, censusFilterArea]);

  // Grouped boxes by hospital area for organized visual navigation
  const groupedBoxesByArea = useMemo(() => {
    const groups: Record<string, HospitalBox[]> = {};
    censusFilteredBoxes.forEach(box => {
      const area = box.area || 'Boxes Generales';
      if (!groups[area]) groups[area] = [];
      groups[area].push(box);
    });
    return groups;
  }, [censusFilteredBoxes]);

  const censusMetrics = useMemo(() => {
    const total = displayedBoxes.length;
    const occupied = displayedBoxes.filter(b => b.status === 'Ocupado').length;
    const available = displayedBoxes.filter(b => b.status === 'Libre').length;
    const cleaning = displayedBoxes.filter(b => b.status === 'En Desinfeccion').length;
    const rate = total > 0 ? Math.round((occupied / total) * 100) : 0;
    return { total, occupied, available, cleaning, rate };
  }, [displayedBoxes]);

  const unassignedPatients = useMemo(() => {
    return patients.filter(p => !p.assigned_box || p.status.includes('Alta'));
  }, [patients]);

  return (
    <div className="flex flex-col h-full w-full bg-slate-900/90 border border-slate-800/80 rounded-2xl overflow-hidden font-sans shadow-xl backdrop-blur-md">
      {/* Top Banner & Tab Navigation */}
      <div className="bg-slate-900 border-b border-slate-800/80 flex flex-col md:flex-row md:items-center justify-between px-4 sm:px-6 py-3.5 gap-3.5 shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-sky-500/10 border border-sky-500/20 flex items-center justify-center text-sky-400 shrink-0">
            <Database className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-sm sm:text-base font-semibold text-slate-100 flex items-center gap-2">
              <span>Simulador HCE / HIS Clinico Integrado</span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-sky-500/10 text-sky-400 border border-sky-500/20 font-medium">
                Urgencias Core v5.4
              </span>
            </h1>
            <p className="text-xs text-slate-400 mt-0.5">
              Conexión directa con Admisiones, Triaje Automatizado y Censo de Camillas Hospitalarias
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2 self-start md:self-auto">
          {/* Prominent Segmented Main Tabs */}
          <div className="flex items-center bg-slate-950 p-1 rounded-xl border border-slate-800 shadow-inner">
            <button
              onClick={() => setActiveTab('patients')}
              className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                activeTab === 'patients'
                  ? 'bg-sky-600 text-white shadow-md shadow-sky-600/30'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Users className="w-4 h-4" />
              <span>Cola de Pacientes</span>
              <span className={`text-[10px] px-1.5 py-0.2 rounded-full font-mono ${
                activeTab === 'patients' ? 'bg-sky-700 text-white' : 'bg-slate-800 text-slate-400'
              }`}>
                {patients.length}
              </span>
            </button>
            <button
              onClick={() => setActiveTab('census')}
              className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                activeTab === 'census'
                  ? 'bg-sky-600 text-white shadow-md shadow-sky-600/30'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <LayoutGrid className="w-4 h-4" />
              <span>Censo de Boxes</span>
              <span className={`text-[10px] px-1.5 py-0.2 rounded-full font-mono ${
                activeTab === 'census' ? 'bg-sky-700 text-white' : 'bg-slate-800 text-slate-400'
              }`}>
                {censusMetrics.rate}% Ocup.
              </span>
            </button>
          </div>

          <button
            onClick={() => setShowExplanation(prev => !prev)}
            className={`flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border font-medium transition-colors ${
              showExplanation 
                ? 'bg-sky-500/20 text-sky-300 border-sky-500/40' 
                : 'bg-slate-800/80 hover:bg-slate-700 text-slate-300 border-slate-700/60'
            }`}
            title="¿Cómo funciona el simulador HCE?"
          >
            <HelpCircle className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Guía del Módulo</span>
          </button>

          <button
            onClick={loadAll}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-800/80 hover:bg-slate-700 text-slate-200 text-xs rounded-lg border border-slate-700/60 font-medium transition-colors"
            title="Actualizar datos desde el servidor"
          >
            <RefreshCw className="w-3.5 h-3.5 text-slate-400" />
            <span className="hidden sm:inline">Actualizar</span>
          </button>
        </div>
      </div>

      {/* Expandable Explanation Callout */}
      {showExplanation && (
        <div className="bg-sky-950/40 border-b border-sky-800/40 px-4 sm:px-6 py-3.5 text-xs text-sky-200 flex items-start justify-between gap-3 animate-fadeIn">
          <div className="space-y-1.5 max-w-4xl">
            <div className="flex items-center gap-2 font-semibold text-sky-300">
              <CheckCircle2 className="w-4 h-4 text-sky-400 shrink-0" />
              <span>Arquitectura y Flujo Operativo del Simulador HCE:</span>
            </div>
            <p className="text-slate-300 leading-relaxed">
              1. <strong className="text-white">Cola de Pacientes:</strong> Recibe los triajes procesados por la IA. Permite consultar la historia clínica, evolucionar la nota médica y asignar la camilla hospitalaria correspondiente.
            </p>
            <p className="text-slate-300 leading-relaxed">
              2. <strong className="text-white">Censo y Gestión de Boxes:</strong> Representa la infraestructura física instalada (Reanimación, Boxes de Urgencias, Observación, Aislamiento). Permite crear nuevos boxes, editar equipamiento, asignar pacientes directamente o alternar ciclos de desinfección/higiene.
            </p>
          </div>
          <button 
            onClick={() => setShowExplanation(false)}
            className="text-sky-400 hover:text-white p-1 rounded-lg"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* View 1: Patient Queue & Clinical Details */}
      {activeTab === 'patients' ? (
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

                {/* Box Assignment Section with in-place Create Box Action */}
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

                  <div className="flex flex-wrap items-center gap-2 w-full sm:w-auto">
                    <select
                      value={assignedBox}
                      onChange={(e) => setAssignedBox(e.target.value)}
                      className="px-3.5 py-2 bg-slate-950 border border-slate-700/80 rounded-xl text-xs text-slate-200 font-mono focus:outline-none focus:border-sky-500 transition-colors"
                    >
                      {availableBoxCodes.map((b) => (
                        <option key={b} value={b}>{b}</option>
                      ))}
                    </select>

                    <button
                      onClick={openCreateBoxModal}
                      type="button"
                      className="flex items-center gap-1 px-2.5 py-2 bg-slate-800 hover:bg-slate-700 text-sky-300 border border-slate-700 text-xs font-medium rounded-xl transition-colors shrink-0"
                      title="Crear un nuevo Box de Urgencias directamente"
                    >
                      <Plus className="w-3.5 h-3.5" />
                      <span>Crear Box</span>
                    </button>

                    <button
                      onClick={handleAssignBox}
                      disabled={isSavingBox}
                      className="flex items-center gap-1.5 px-4 py-2 bg-sky-600 hover:bg-sky-500 disabled:opacity-50 text-white text-xs font-semibold rounded-xl transition-all shadow-md shadow-sky-600/20 shrink-0"
                    >
                      {isSavingBox ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />}
                      <span>Asignar Box</span>
                    </button>

                    {selectedPatient.assigned_box && (
                      <button
                        onClick={() => handleReleaseBox(selectedPatient.id, selectedPatient.assigned_box)}
                        className="flex items-center gap-1.5 px-3 py-2 bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 border border-rose-500/30 text-xs font-semibold rounded-xl transition-all shrink-0"
                        title="Liberar cama y dar alta asistencial"
                      >
                        <LogOut className="w-3.5 h-3.5" />
                        <span>Liberar Box</span>
                      </button>
                    )}
                  </div>
                </div>

                {/* Patient Care Status & Clinical Evolution Section */}
                <div className="bg-slate-900/80 border border-slate-800/80 rounded-2xl p-4 space-y-3">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-2 border-b border-slate-800/80">
                    <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-300 flex items-center gap-2">
                      <ClipboardEdit className="w-4 h-4 text-emerald-400" />
                      <span>Seguimiento Asistencial y Evolución Médica</span>
                    </h3>
                    <div className="flex flex-wrap items-center gap-1.5">
                      <span className="text-[11px] text-slate-400 font-medium mr-1">Estado Asistencial:</span>
                      {CARE_STATUS_OPTIONS.map(st => {
                        const isSelected = patientCareStatus === st;
                        return (
                          <button
                            type="button"
                            key={st}
                            onClick={() => setPatientCareStatus(st)}
                            className={`px-2 py-0.5 rounded-lg text-[11px] font-medium transition-colors ${
                              isSelected
                                ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 shadow-sm'
                                : 'bg-slate-950 text-slate-400 hover:text-slate-200 border border-slate-800'
                            }`}
                          >
                            {st}
                          </button>
                        );
                      })}
                    </div>
                  </div>

                  <div className="space-y-2">
                    <label className="text-[11px] text-slate-400 block font-medium">
                      Notas de Evolución Médica / Conducta en Urgencias:
                    </label>
                    <textarea
                      rows={3}
                      value={evolutionNote}
                      onChange={(e) => setEvolutionNote(e.target.value)}
                      placeholder="Escriba la evolución clínica del paciente, paraclínicos solicitados o respuesta a tratamientos..."
                      className="w-full p-3 bg-slate-950/80 border border-slate-800 rounded-xl text-xs text-slate-200 focus:outline-none focus:border-emerald-500 transition-colors placeholder-slate-600 resize-none"
                    />
                    <div className="flex justify-end">
                      <button
                        onClick={handleUpdateCareStatusAndNotes}
                        disabled={isSavingClinicalCare}
                        className="flex items-center gap-1.5 px-3.5 py-1.5 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white rounded-lg text-xs font-semibold transition-all shadow-sm shadow-emerald-600/30"
                      >
                        {isSavingClinicalCare ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
                        <span>Guardar Evolución</span>
                      </button>
                    </div>
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
                      {selectedPatient.entities?.vitals?.length ? (
                        selectedPatient.entities.vitals.map((vital, idx) => {
                          const [label, value] = splitVital(vital);
                          return (
                            <div key={`${vital}-${idx}`} className="p-3 bg-slate-950/70 border border-slate-800/80 rounded-xl">
                              <span className="text-[10px] text-slate-400 uppercase font-mono block font-semibold">{label}</span>
                              <span className="text-sm font-semibold text-sky-200 font-mono mt-0.5 block">{value}</span>
                            </div>
                          );
                        })
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
      ) : (
        /* View 2: Hospital Bed Census & Box Management */
        <div className="flex-1 flex flex-col p-4 sm:p-6 overflow-y-auto space-y-6">
          {/* KPI Summary Cards */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-4">
            <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 flex flex-col gap-1">
              <span className="text-[11px] text-slate-400 font-semibold uppercase tracking-wider">Total Unidades</span>
              <div className="flex items-baseline justify-between mt-1">
                <span className="text-2xl font-bold font-mono text-slate-100">{censusMetrics.total}</span>
                <span className="text-xs text-slate-500">Boxes y Camillas</span>
              </div>
            </div>

            <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 flex flex-col gap-1">
              <span className="text-[11px] text-slate-400 font-semibold uppercase tracking-wider">Ocupadas</span>
              <div className="flex items-baseline justify-between mt-1">
                <span className="text-2xl font-bold font-mono text-amber-400">{censusMetrics.occupied}</span>
                <span className="text-xs font-mono px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-300 border border-amber-500/20">
                  {censusMetrics.rate}% tasa
                </span>
              </div>
            </div>

            <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 flex flex-col gap-1">
              <span className="text-[11px] text-slate-400 font-semibold uppercase tracking-wider">Disponibles / Libres</span>
              <div className="flex items-baseline justify-between mt-1">
                <span className="text-2xl font-bold font-mono text-emerald-400">{censusMetrics.available}</span>
                <span className="text-xs text-emerald-400/80 font-mono">Listos para ingreso</span>
              </div>
            </div>

            <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 flex flex-col gap-1">
              <span className="text-[11px] text-slate-400 font-semibold uppercase tracking-wider">En Desinfeccion</span>
              <div className="flex items-baseline justify-between mt-1">
                <span className="text-2xl font-bold font-mono text-purple-400">{censusMetrics.cleaning}</span>
                <span className="text-xs text-purple-400/80 font-mono">Higiene en curso</span>
              </div>
            </div>
          </div>

          {/* Action Bar: Filters, Organization Layout Toggle, and Create Box Button */}
          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3 p-3.5 rounded-xl bg-slate-950/40 border border-slate-800/80">
            <div className="flex flex-wrap items-center gap-3">
              {/* Status Filter */}
              <div className="flex items-center gap-1 text-xs">
                <span className="text-slate-400 text-[11px] mr-1">Estado:</span>
                {['Todos', 'Libre', 'Ocupado', 'En Desinfeccion'].map((st) => (
                  <button
                    key={st}
                    onClick={() => setCensusFilterStatus(st)}
                    className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-colors ${
                      censusFilterStatus === st
                        ? 'bg-sky-500/20 text-sky-300 border border-sky-500/30'
                        : 'bg-slate-900 text-slate-400 hover:text-slate-200 border border-slate-800'
                    }`}
                  >
                    {st}
                  </button>
                ))}
              </div>

              <div className="h-4 w-[1px] bg-slate-800 hidden sm:block" />

              {/* Area Filter */}
              <div className="flex items-center gap-1.5 text-xs">
                <span className="text-slate-400 text-[11px]">Area:</span>
                <select
                  value={censusFilterArea}
                  onChange={(e) => setCensusFilterArea(e.target.value)}
                  className="px-2.5 py-1 bg-slate-900 border border-slate-800 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-sky-500"
                >
                  {AREA_OPTIONS.map((a) => (
                    <option key={a} value={a}>{a}</option>
                  ))}
                </select>
              </div>

              <div className="h-4 w-[1px] bg-slate-800 hidden sm:block" />

              {/* Organization Mode Toggle */}
              <div className="flex items-center bg-slate-900 p-0.5 rounded-lg border border-slate-800">
                <button
                  onClick={() => setCensusViewMode('grouped')}
                  className={`flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${
                    censusViewMode === 'grouped' ? 'bg-sky-600 text-white' : 'text-slate-400 hover:text-slate-200'
                  }`}
                  title="Organizar boxes por áreas hospitalarias"
                >
                  <Layers className="w-3.5 h-3.5" />
                  <span>Por Áreas</span>
                </button>
                <button
                  onClick={() => setCensusViewMode('grid')}
                  className={`flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${
                    censusViewMode === 'grid' ? 'bg-sky-600 text-white' : 'text-slate-400 hover:text-slate-200'
                  }`}
                  title="Ver cuadrícula unificada"
                >
                  <LayoutGrid className="w-3.5 h-3.5" />
                  <span>Cuadrícula</span>
                </button>
              </div>
            </div>

            <button
              onClick={openCreateBoxModal}
              className="flex items-center gap-1.5 px-3.5 py-2 bg-sky-600 hover:bg-sky-500 text-white rounded-xl text-xs font-semibold transition-all shadow-md shadow-sky-600/20 shrink-0 self-start lg:self-auto"
            >
              <Plus className="w-4 h-4" />
              <span>Nuevo Box / Camilla</span>
            </button>
          </div>

          {/* Render Boxes: Grouped View or Flat Grid */}
          {censusFilteredBoxes.length === 0 ? (
            <div className="py-16 text-center text-slate-500 text-xs">
              No hay unidades registradas con los filtros seleccionados.
            </div>
          ) : censusViewMode === 'grouped' ? (
            <div className="space-y-6">
              {Object.entries(groupedBoxesByArea).map(([areaName, areaBoxes]) => {
                const areaOccupied = areaBoxes.filter(b => b.status === 'Ocupado').length;
                const areaTotal = areaBoxes.length;

                return (
                  <div key={areaName} className="space-y-3">
                    {/* Area Header Banner */}
                    <div className="flex items-center justify-between pb-2 border-b border-slate-800">
                      <div className="flex items-center gap-2">
                        <span className="w-2.5 h-2.5 rounded-full bg-sky-400"></span>
                        <h2 className="text-xs font-bold uppercase tracking-wider text-slate-200">
                          {areaName} ({areaTotal} {areaTotal === 1 ? 'unidad' : 'unidades'})
                        </h2>
                      </div>
                      <span className="text-[11px] font-mono text-slate-400">
                        Ocupación: <span className="text-amber-400 font-semibold">{areaOccupied}</span> / {areaTotal}
                      </span>
                    </div>

                    {/* Area Grid */}
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                      {areaBoxes.map((box) => renderBoxCard(box))}
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
              {censusFilteredBoxes.map((box) => renderBoxCard(box))}
            </div>
          )}

          {/* Quick Assign Drawer / Dialog */}
          {quickAssignBoxCode && (
            <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
              <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 max-w-md w-full shadow-2xl space-y-4">
                <div className="flex items-center justify-between pb-3 border-b border-slate-800">
                  <div className="flex items-center gap-2">
                    <Bed className="w-4 h-4 text-sky-400" />
                    <h3 className="text-sm font-semibold text-slate-100">
                      Asignar Paciente a <span className="font-mono text-sky-400">{quickAssignBoxCode}</span>
                    </h3>
                  </div>
                  <button onClick={() => setQuickAssignBoxCode(null)} className="text-slate-400 hover:text-slate-200">
                    <X className="w-4 h-4" />
                  </button>
                </div>

                <div className="space-y-3">
                  <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider block">
                    Seleccione Paciente en Espera
                  </label>
                  {unassignedPatients.length === 0 ? (
                    <p className="text-xs text-slate-400 py-3">
                      No hay pacientes pendientes de asignacion en la cola.
                    </p>
                  ) : (
                    <select
                      value={quickAssignSessionId}
                      onChange={(e) => setQuickAssignSessionId(Number(e.target.value))}
                      className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-xl text-xs text-slate-200 focus:outline-none focus:border-sky-500"
                    >
                      <option value="">-- Seleccionar Paciente --</option>
                      {unassignedPatients.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.name} (Doc: {p.document_id}) - Nivel {ROMAN_LEVELS[p.level]}
                        </option>
                      ))}
                    </select>
                  )}
                </div>

                <div className="flex items-center justify-end gap-2 pt-3 border-t border-slate-800">
                  <button
                    onClick={() => setQuickAssignBoxCode(null)}
                    className="px-3 py-1.5 text-xs text-slate-400 hover:text-slate-200 font-medium"
                  >
                    Cancelar
                  </button>
                  <button
                    onClick={handleQuickAssignFromCensus}
                    disabled={!quickAssignSessionId}
                    className="px-4 py-2 bg-sky-600 hover:bg-sky-500 disabled:opacity-50 text-white rounded-xl text-xs font-semibold"
                  >
                    Confirmar Asignacion
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Create Box Modal */}
          {isCreateModalOpen && (
            <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
              <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 max-w-lg w-full shadow-2xl space-y-4">
                <div className="flex items-center justify-between pb-3 border-b border-slate-800">
                  <div className="flex items-center gap-2">
                    <Plus className="w-4 h-4 text-sky-400" />
                    <h3 className="text-sm font-semibold text-slate-100">
                      Registrar Nueva Unidad de Urgencias (Box / Camilla)
                    </h3>
                  </div>
                  <button onClick={() => setIsCreateModalOpen(false)} className="text-slate-400 hover:text-slate-200">
                    <X className="w-4 h-4" />
                  </button>
                </div>

                <form onSubmit={handleCreateBox} className="space-y-4">
                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-1.5">
                      <label className="text-xs font-semibold text-slate-300">Codigo / Identificador *</label>
                      <input
                        type="text"
                        placeholder="Ej. BOX-07, AISL-02"
                        value={boxFormCode}
                        onChange={(e) => setBoxFormCode(e.target.value)}
                        required
                        className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-xs font-mono text-slate-200 focus:outline-none focus:border-sky-500 uppercase"
                      />
                    </div>
                    <div className="space-y-1.5">
                      <label className="text-xs font-semibold text-slate-300">Area Hospitalaria</label>
                      <select
                        value={boxFormArea}
                        onChange={(e) => setBoxFormArea(e.target.value)}
                        className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-xs text-slate-200 focus:outline-none focus:border-sky-500"
                      >
                        {AREA_OPTIONS.filter(a => a !== 'Todas').map(a => (
                          <option key={a} value={a}>{a}</option>
                        ))}
                      </select>
                    </div>
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-xs font-semibold text-slate-300">Tipo de Unidad</label>
                    <select
                      value={boxFormType}
                      onChange={(e) => setBoxFormType(e.target.value)}
                      className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-xs text-slate-200 focus:outline-none focus:border-sky-500"
                    >
                      <option value="Camilla Urgencias">Camilla de Urgencias</option>
                      <option value="Box Vital">Box de Reanimacion / Vital</option>
                      <option value="Cama Hospitalaria">Cama de Observacion Hospitalaria</option>
                      <option value="Box Presion Negativa">Box de Aislamiento (Presion Negativa)</option>
                      <option value="Sillon de Triage">Sillon de Triage Rapido</option>
                    </select>
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-xs font-semibold text-slate-300">Equipamiento Disponible</label>
                    <div className="flex flex-wrap gap-2 pt-1">
                      {EQUIPMENT_PRESETS.map((item) => {
                        const checked = boxFormEquipment.includes(item);
                        return (
                          <button
                            type="button"
                            key={item}
                            onClick={() => {
                              if (checked) {
                                setBoxFormEquipment(prev => prev.filter(x => x !== item));
                              } else {
                                setBoxFormEquipment(prev => [...prev, item]);
                              }
                            }}
                            className={`px-2.5 py-1 rounded-lg text-xs font-medium border transition-colors ${
                              checked
                                ? 'bg-sky-500/20 text-sky-300 border-sky-500/30'
                                : 'bg-slate-950 text-slate-400 border-slate-800 hover:text-slate-200'
                            }`}
                          >
                            {item}
                          </button>
                        );
                      })}
                    </div>
                  </div>

                  <div className="flex items-center justify-end gap-2 pt-3 border-t border-slate-800">
                    <button
                      type="button"
                      onClick={() => setIsCreateModalOpen(false)}
                      className="px-3 py-1.5 text-xs text-slate-400 hover:text-slate-200 font-medium"
                    >
                      Cancelar
                    </button>
                    <button
                      type="submit"
                      className="px-4 py-2 bg-sky-600 hover:bg-sky-500 text-white rounded-xl text-xs font-semibold transition-all shadow-md shadow-sky-600/20"
                    >
                      Registrar y Activar Box
                    </button>
                  </div>
                </form>
              </div>
            </div>
          )}

          {/* Edit Box Modal */}
          {isEditModalOpen && editingBox && (
            <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
              <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 max-w-lg w-full shadow-2xl space-y-4">
                <div className="flex items-center justify-between pb-3 border-b border-slate-800">
                  <div className="flex items-center gap-2">
                    <Edit3 className="w-4 h-4 text-sky-400" />
                    <h3 className="text-sm font-semibold text-slate-100">
                      Editar Configuración de Box <span className="font-mono text-sky-400">{editingBox.code}</span>
                    </h3>
                  </div>
                  <button onClick={() => { setIsEditModalOpen(false); setEditingBox(null); }} className="text-slate-400 hover:text-slate-200">
                    <X className="w-4 h-4" />
                  </button>
                </div>

                <form onSubmit={handleSaveEditBox} className="space-y-4">
                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-1.5">
                      <label className="text-xs font-semibold text-slate-300">Codigo</label>
                      <input
                        type="text"
                        disabled
                        value={editingBox.code}
                        className="w-full px-3 py-2 bg-slate-950/60 border border-slate-800 rounded-xl text-xs font-mono text-slate-400 opacity-80 cursor-not-allowed"
                      />
                    </div>
                    <div className="space-y-1.5">
                      <label className="text-xs font-semibold text-slate-300">Area Hospitalaria</label>
                      <select
                        value={boxFormArea}
                        onChange={(e) => setBoxFormArea(e.target.value)}
                        className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-xs text-slate-200 focus:outline-none focus:border-sky-500"
                      >
                        {AREA_OPTIONS.filter(a => a !== 'Todas').map(a => (
                          <option key={a} value={a}>{a}</option>
                        ))}
                      </select>
                    </div>
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-xs font-semibold text-slate-300">Tipo de Unidad</label>
                    <select
                      value={boxFormType}
                      onChange={(e) => setBoxFormType(e.target.value)}
                      className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-xs text-slate-200 focus:outline-none focus:border-sky-500"
                    >
                      <option value="Camilla Urgencias">Camilla de Urgencias</option>
                      <option value="Box Vital">Box de Reanimacion / Vital</option>
                      <option value="Cama Hospitalaria">Cama de Observacion Hospitalaria</option>
                      <option value="Box Presion Negativa">Box de Aislamiento (Presion Negativa)</option>
                      <option value="Sillon de Triage">Sillon de Triage Rapido</option>
                    </select>
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-xs font-semibold text-slate-300">Equipamiento Disponible</label>
                    <div className="flex flex-wrap gap-2 pt-1">
                      {EQUIPMENT_PRESETS.map((item) => {
                        const checked = boxFormEquipment.includes(item);
                        return (
                          <button
                            type="button"
                            key={item}
                            onClick={() => {
                              if (checked) {
                                setBoxFormEquipment(prev => prev.filter(x => x !== item));
                              } else {
                                setBoxFormEquipment(prev => [...prev, item]);
                              }
                            }}
                            className={`px-2.5 py-1 rounded-lg text-xs font-medium border transition-colors ${
                              checked
                                ? 'bg-sky-500/20 text-sky-300 border-sky-500/30'
                                : 'bg-slate-950 text-slate-400 border-slate-800 hover:text-slate-200'
                            }`}
                          >
                            {item}
                          </button>
                        );
                      })}
                    </div>
                  </div>

                  <div className="flex items-center justify-between gap-2 pt-3 border-t border-slate-800">
                    {editingBox && (!editingBox.occupant || editingBox.status === 'Libre') ? (
                      <button
                        type="button"
                        onClick={() => {
                          handleDeleteBox(editingBox.code);
                          setIsEditModalOpen(false);
                          setEditingBox(null);
                        }}
                        className="px-3 py-1.5 text-xs text-rose-400 hover:text-rose-300 border border-rose-500/30 hover:bg-rose-500/10 rounded-xl font-medium transition-colors flex items-center gap-1.5"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                        <span>Eliminar Box</span>
                      </button>
                    ) : <div />}

                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => { setIsEditModalOpen(false); setEditingBox(null); }}
                        className="px-3 py-1.5 text-xs text-slate-400 hover:text-slate-200 font-medium"
                      >
                        Cancelar
                      </button>
                      <button
                        type="submit"
                        className="px-4 py-2 bg-sky-600 hover:bg-sky-500 text-white rounded-xl text-xs font-semibold transition-all shadow-md shadow-sky-600/20"
                      >
                        Guardar Cambios
                      </button>
                    </div>
                  </div>
                </form>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );

  // Helper renderer for each Box Card
  function renderBoxCard(box: HospitalBox) {
    const isOccupied = box.status === 'Ocupado';
    const isCleaning = box.status === 'En Desinfeccion';
    const isFree = box.status === 'Libre';

    return (
      <div
        key={box.code}
        className={`rounded-2xl border p-4 flex flex-col justify-between transition-all relative ${
          isOccupied
            ? 'bg-slate-900/90 border-amber-500/30 shadow-md shadow-amber-950/20'
            : isCleaning
            ? 'bg-slate-900/80 border-purple-500/30'
            : 'bg-slate-900/60 border-slate-800/80 hover:border-emerald-500/30'
        }`}
      >
        <div>
          {/* Box Card Header */}
          <div className="flex items-start justify-between gap-2 pb-3 border-b border-slate-800/60">
            <div className="flex items-center gap-2">
              <div className={`p-2 rounded-xl ${
                isOccupied
                  ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                  : isCleaning
                  ? 'bg-purple-500/10 text-purple-400 border border-purple-500/20'
                  : 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
              }`}>
                <Bed className="w-4 h-4" />
              </div>
              <div>
                <span className="font-mono font-bold text-sm text-slate-100">{box.code}</span>
                <span className="text-[10px] text-slate-400 block font-medium">{box.area}</span>
              </div>
            </div>

            <div className="flex items-center gap-1.5">
              <span className={`text-[10px] font-semibold px-2.5 py-0.5 rounded-full border ${
                isOccupied
                  ? 'bg-amber-500/10 text-amber-300 border-amber-500/30'
                  : isCleaning
                  ? 'bg-purple-500/10 text-purple-300 border-purple-500/30'
                  : 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30'
              }`}>
                {box.status}
              </span>

              <button
                onClick={() => openEditBoxModal(box)}
                className="text-slate-400 hover:text-sky-300 p-1 rounded-md transition-colors"
                title="Editar configuración del box"
              >
                <Edit3 className="w-3.5 h-3.5" />
              </button>

              {isFree && (
                <button
                  onClick={() => handleDeleteBox(box.code)}
                  className="text-slate-400 hover:text-rose-400 p-1 rounded-md transition-colors"
                  title={`Eliminar box ${box.code}`}
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          </div>

          {/* Box Content / Occupant Details */}
          <div className="py-3 text-xs space-y-2">
            <div className="text-[11px] text-slate-400 flex items-center justify-between">
              <span>Tipo: {box.type}</span>
            </div>

            {box.occupant ? (
              <div className="p-3 rounded-xl bg-slate-950/70 border border-slate-800/80 space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-semibold text-slate-200 truncate">{box.occupant.patient_name}</span>
                  <span className={`text-[10px] font-mono px-2 py-0.2 rounded border ${LEVEL_STYLES[box.occupant.triage_level]}`}>
                    Nivel {ROMAN_LEVELS[box.occupant.triage_level]}
                  </span>
                </div>
                <div className="flex items-center justify-between text-[11px] text-slate-400 font-mono">
                  <span>Doc: {box.occupant.document_id}</span>
                  <span>{box.occupant.admission_time}</span>
                </div>
              </div>
            ) : isCleaning ? (
              <div className="p-3 rounded-xl bg-purple-950/20 border border-purple-800/30 text-purple-300 text-xs flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-purple-400 shrink-0" />
                <span>Protocolo de higiene en proceso. No apto para ingreso.</span>
              </div>
            ) : (
              <div className="p-3 rounded-xl bg-emerald-950/20 border border-emerald-800/30 text-emerald-300 text-xs flex items-center gap-2">
                <Check className="w-4 h-4 text-emerald-400 shrink-0" />
                <span>Unidad desinfectada y lista para admision.</span>
              </div>
            )}

            {box.equipment && (
              <p className="text-[10px] text-slate-500 truncate" title={box.equipment}>
                Eq: {box.equipment}
              </p>
            )}
          </div>
        </div>

        {/* Box Card Actions */}
        <div className="pt-3 border-t border-slate-800/60 flex items-center justify-between gap-2">
          {isOccupied && box.occupant ? (
            <>
              <button
                onClick={() => {
                  const found = patients.find(p => p.id === box.occupant?.session_id);
                  if (found) {
                    handleSelectPatient(found);
                    setActiveTab('patients');
                  }
                }}
                className="flex-1 py-1.5 px-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium rounded-lg text-center transition-colors"
              >
                Ver Ficha
              </button>
              <button
                onClick={() => handleReleaseBox(box.occupant!.session_id, box.code)}
                className="flex items-center justify-center gap-1 py-1.5 px-2.5 bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 border border-rose-500/30 text-xs font-medium rounded-lg transition-colors"
              >
                <LogOut className="w-3.5 h-3.5" />
                <span>Liberar</span>
              </button>
            </>
          ) : isFree ? (
            <>
              <button
                onClick={() => setQuickAssignBoxCode(box.code)}
                className="flex-1 py-1.5 px-2 bg-sky-600/90 hover:bg-sky-500 text-white text-xs font-medium rounded-lg transition-colors"
              >
                Asignar Paciente
              </button>
              <button
                onClick={() => handleToggleCleaning(box.code, box.status)}
                className="py-1.5 px-2.5 bg-slate-800 hover:bg-slate-700 text-purple-300 text-xs font-medium rounded-lg transition-colors"
                title="Marcar para desinfeccion"
              >
                Higiene
              </button>
            </>
          ) : (
            <button
              onClick={() => handleToggleCleaning(box.code, box.status)}
              className="w-full py-1.5 px-2 bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-300 border border-emerald-500/30 text-xs font-medium rounded-lg transition-colors flex items-center justify-center gap-1.5"
            >
              <Check className="w-3.5 h-3.5" />
              <span>Habilitar Disponible</span>
            </button>
          )}
        </div>
      </div>
    );
  }
}
