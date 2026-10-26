'use client';

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Building2,
  User,
  Activity,
  FileText,
  Clock,
  CheckCircle2,
  RefreshCw,
  Search,
  HeartPulse,
  ShieldAlert,
  ArrowLeft,
  Save,
  Share2,
  Code2,
  Copy,
  Download,
  Pill,
  Stethoscope,
  History,
  Check,
} from 'lucide-react';
import { toast } from 'sonner';
import { fetchWithAuth } from '@/lib/api';
import {
  generateFHIRBundle,
  generateHL7v2Message,
  TRIAGE_LEVEL_METADATA,
  type TriageSession as HL7TriageSession,
} from '@/lib/hl7';

interface ClinicalEntities {
  symptoms?: string[];
  diagnoses?: string[];
  medications?: string[];
  vitals?: string[] | Record<string, string>;
  allergies?: string[];
  history?: string[];
  negated_findings?: string[];
  evolution_notes?: string;
}

export interface EMRPatient {
  id: number;
  patient_id: number;
  document_id: string;
  name: string;
  gender: string;
  birth_date?: string;
  phone: string;
  insurance: string;
  created_at?: string;
  admission_time: string;
  level: number;
  ai_level: number;
  is_level_modified?: boolean;
  status: string;
  justification: string;
  transcript?: string;
  engine_used?: string;
  entities: ClinicalEntities;
  fhir_synced?: boolean;
  fhir_resource_id?: string;
  fhir_synced_at?: string | null;
  fhir_bundle?: Record<string, unknown> | null;
}

const ROMAN_NUMERALS: Record<number, string> = {
  1: 'I',
  2: 'II',
  3: 'III',
  4: 'IV',
  5: 'V',
};

const GENDER_LABELS: Record<string, string> = {
  male: 'Masculino',
  female: 'Femenino',
  other: 'Otro',
  Masculino: 'Masculino',
  Femenino: 'Femenino',
  Otro: 'Otro',
};

const CARE_STATUS_OPTIONS = [
  { value: 'Pendiente de Recepcion', label: 'Pendiente de Recepción' },
  { value: 'Recibido en HCE', label: 'Recibido en HCE' },
  { value: 'En Atencion', label: 'En Atención Médica' },
  { value: 'En Observacion', label: 'En Observación' },
  { value: 'Alta Medica', label: 'Alta Médica' },
];

const STATUS_LABELS: Record<string, string> = {
  'Pendiente de Recepcion': 'Pendiente de Recepción',
  'Pendiente de Box': 'Pendiente de Recepción',
  'En Espera': 'En Espera',
  'Triaje Completado': 'Triaje Completado',
  'Recibido en HCE': 'Recibido en HCE',
  'En Atencion': 'En Atención Médica',
  'En Observacion': 'En Observación',
  'Alta Medica': 'Alta Médica',
};

function getLevelStyle(level: number) {
  switch (level) {
    case 1:
      return {
        badge: 'bg-red-500/15 text-red-400 border-red-500/40',
        pill: 'bg-red-600 text-white border-red-500',
        border: 'border-l-red-500',
      };
    case 2:
      return {
        badge: 'bg-orange-500/15 text-orange-400 border-orange-500/40',
        pill: 'bg-orange-500 text-white border-orange-400',
        border: 'border-l-orange-500',
      };
    case 3:
      return {
        badge: 'bg-amber-500/15 text-amber-400 border-amber-500/40',
        pill: 'bg-amber-500 text-slate-950 border-amber-400',
        border: 'border-l-amber-500',
      };
    case 4:
      return {
        badge: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/40',
        pill: 'bg-emerald-600 text-white border-emerald-500',
        border: 'border-l-emerald-500',
      };
    default:
      return {
        badge: 'bg-sky-500/15 text-sky-400 border-sky-500/40',
        pill: 'bg-sky-600 text-white border-sky-500',
        border: 'border-l-sky-500',
      };
  }
}

function normalizeVitalsList(vitals?: string[] | Record<string, string>): { label: string; value: string }[] {
  if (!vitals) return [];
  const rawItems: string[] = Array.isArray(vitals)
    ? vitals
    : Object.entries(vitals).map(([k, v]) => `${k.toUpperCase()}: ${v}`);

  return rawItems.map((raw) => {
    const idx = raw.indexOf(':');
    if (idx === -1) return { label: 'Signo Vital', value: raw.trim() };
    return {
      label: raw.slice(0, idx).trim(),
      value: raw.slice(idx + 1).trim(),
    };
  });
}

function buildHL7Session(patient: EMRPatient): HL7TriageSession {
  const cleanDoc = patient.document_id?.startsWith('anon-') ? '' : patient.document_id;
  const vitalsList = Array.isArray(patient.entities?.vitals)
    ? patient.entities.vitals
    : patient.entities?.vitals
      ? Object.entries(patient.entities.vitals).map(([k, v]) => `${k.toUpperCase()}: ${v}`)
      : [];

  const transcriptTurns = (patient.transcript || '')
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const sep = line.indexOf(': ');
      if (sep !== -1) {
        return { speaker: line.slice(0, sep), text: line.slice(sep + 2) };
      }
      return { speaker: 'Consulta', text: line };
    });

  return {
    id: String(patient.id),
    date: patient.created_at || new Date().toISOString(),
    patientName: patient.name,
    patientInfo: {
      name: patient.name,
      documentId: cleanDoc,
      birthDate: patient.birth_date || '',
      gender: patient.gender || 'unknown',
      phone: patient.phone && patient.phone !== 'N/A' ? patient.phone : '',
      insurance: patient.insurance || '',
    },
    transcript: transcriptTurns,
    analysisResult: {
      triage: {
        level: patient.level,
        final_level: patient.level,
        ai_level: patient.ai_level,
        justification: patient.justification,
      },
      entities: {
        symptoms: patient.entities?.symptoms || [],
        diagnoses: patient.entities?.diagnoses || [],
        medications: patient.entities?.medications || [],
        allergies: patient.entities?.allergies || [],
        vitals: vitalsList,
        history: patient.entities?.history || [],
        negated_findings: patient.entities?.negated_findings || [],
      },
      engine_used: patient.engine_used || '',
    },
  };
}

export default function EMRSimulator() {
  const [patients, setPatients] = useState<EMRPatient[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [syncFilter, setSyncFilter] = useState<'all' | 'synced' | 'pending'>('all');
  const [mobileDetailOpen, setMobileDetailOpen] = useState(false);

  const [detailTab, setDetailTab] = useState<'clinical' | 'interop'>('clinical');
  const [interopFormat, setInteropFormat] = useState<'fhir' | 'hl7v2'>('fhir');
  const [copiedPayload, setCopiedPayload] = useState(false);

  const [careStatusInput, setCareStatusInput] = useState('Pendiente de Recepcion');
  const [evolutionNotes, setEvolutionNotes] = useState('');
  const [savingEvolution, setSavingEvolution] = useState(false);
  const [syncingFhir, setSyncingFhir] = useState(false);

  const fetchPatients = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fetchWithAuth('/api/triage/sessions/emr_patients/');
      if (!response.ok) {
        toast.error('No se pudieron cargar las admisiones de la HCE.');
        return;
      }
      const data: EMRPatient[] = await response.json();
      setPatients(data);
      setSelectedId((prev) => {
        if (prev && data.some((p) => p.id === prev)) return prev;
        return data.length > 0 ? data[0].id : null;
      });
    } catch (error) {
      console.error('Error cargando admisiones HCE:', error);
      toast.error('Error de conexión con el servidor HCE.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPatients();
  }, [fetchPatients]);

  const selectedPatient = useMemo(
    () => patients.find((p) => p.id === selectedId) || null,
    [patients, selectedId]
  );

  useEffect(() => {
    if (selectedPatient) {
      const normalized = CARE_STATUS_OPTIONS.some((o) => o.value === selectedPatient.status)
        ? selectedPatient.status
        : 'Pendiente de Recepcion';
      setCareStatusInput(normalized);
      setEvolutionNotes(selectedPatient.entities?.evolution_notes || '');
    }
  }, [selectedPatient]);

  const filteredPatients = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    return patients.filter((p) => {
      if (syncFilter === 'synced' && !p.fhir_synced) return false;
      if (syncFilter === 'pending' && p.fhir_synced) return false;
      if (!q) return true;
      return (
        p.name.toLowerCase().includes(q) ||
        p.document_id.toLowerCase().includes(q) ||
        (p.fhir_resource_id || '').toLowerCase().includes(q)
      );
    });
  }, [patients, searchQuery, syncFilter]);

  const syncedCount = useMemo(
    () => patients.filter((p) => p.fhir_synced).length,
    [patients]
  );

  const generatedBundle = useMemo(() => {
    if (!selectedPatient) return null;
    if (selectedPatient.fhir_bundle) return selectedPatient.fhir_bundle;
    return generateFHIRBundle(buildHL7Session(selectedPatient));
  }, [selectedPatient]);

  const generatedHL7v2 = useMemo(() => {
    if (!selectedPatient) return '';
    return generateHL7v2Message(buildHL7Session(selectedPatient));
  }, [selectedPatient]);

  const fhirResourceCounts = useMemo(() => {
    const entries = (generatedBundle as { entry?: { resource?: { resourceType?: string } }[] } | null)?.entry || [];
    const counts: Record<string, number> = {};
    entries.forEach((item) => {
      const rt = item?.resource?.resourceType;
      if (rt) counts[rt] = (counts[rt] || 0) + 1;
    });
    return counts;
  }, [generatedBundle]);

  const handleSyncToFHIR = async () => {
    if (!selectedPatient) return;
    setSyncingFhir(true);
    try {
      const bundle = generateFHIRBundle(buildHL7Session(selectedPatient));
      const res = await fetchWithAuth('/api/fhir/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(bundle),
      });
      const data = await res.json().catch(() => ({}));
      if (res.status === 201 || res.ok) {
        const nextStatus =
          selectedPatient.status === 'Pendiente de Recepcion' ||
          selectedPatient.status === 'Pendiente de Box' ||
          !selectedPatient.status
            ? 'Recibido en HCE'
            : selectedPatient.status;

        setPatients((prev) =>
          prev.map((p) =>
            p.id === selectedPatient.id
              ? {
                  ...p,
                  fhir_synced: true,
                  fhir_resource_id: data.id || p.fhir_resource_id || `fhir-enc-${p.id}`,
                  fhir_synced_at: new Date().toLocaleString('sv-SE').slice(0, 19),
                  fhir_bundle: bundle as unknown as Record<string, unknown>,
                  status: nextStatus,
                }
              : p
          )
        );
        setCareStatusInput(nextStatus);
        toast.success(`Admisión sincronizada con HCE vía HL7 FHIR R4 (${data.id || 'OK'}).`);
      } else {
        toast.error(data.error || 'Error validando el Bundle FHIR R4.');
      }
    } catch (err) {
      console.error('Error sincronizando FHIR desde HCE:', err);
      toast.error('Error de red al sincronizar el Bundle FHIR R4.');
    } finally {
      setSyncingFhir(false);
    }
  };

  const handleSaveEvolution = async () => {
    if (!selectedPatient) return;
    setSavingEvolution(true);
    try {
      const res = await fetchWithAuth(
        `/api/triage/sessions/${selectedPatient.id}/update_care_status/`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            status: careStatusInput,
            evolution_notes: evolutionNotes,
          }),
        }
      );
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        toast.error(data.error || 'No se pudo actualizar el registro clínico en HCE.');
        return;
      }
      setPatients((prev) =>
        prev.map((p) =>
          p.id === selectedPatient.id
            ? {
                ...p,
                status: careStatusInput,
                entities: {
                  ...p.entities,
                  evolution_notes: evolutionNotes,
                },
              }
            : p
        )
      );
      toast.success('Evolución clínica registrada en HCE.');
    } catch (err) {
      console.error('Error guardando evolucion HCE:', err);
      toast.error('Error de conexión al guardar en HCE.');
    } finally {
      setSavingEvolution(false);
    }
  };

  const activePayloadText = useMemo(() => {
    if (interopFormat === 'fhir') {
      return generatedBundle ? JSON.stringify(generatedBundle, null, 2) : '';
    }
    return generatedHL7v2;
  }, [interopFormat, generatedBundle, generatedHL7v2]);

  const handleCopyPayload = async () => {
    if (!activePayloadText) return;
    try {
      await navigator.clipboard.writeText(activePayloadText);
      setCopiedPayload(true);
      toast.success('Mensaje de interoperabilidad copiado al portapapeles.');
      setTimeout(() => setCopiedPayload(false), 1800);
    } catch {
      toast.error('No se pudo copiar al portapapeles.');
    }
  };

  const handleDownloadPayload = () => {
    if (!selectedPatient || !activePayloadText) return;
    const isFhir = interopFormat === 'fhir';
    const blob = new Blob([activePayloadText], {
      type: isFhir ? 'application/fhir+json;charset=utf-8' : 'text/plain;charset=utf-8',
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = isFhir
      ? `fhir-r4-session-${selectedPatient.id}.json`
      : `hl7-v2-adt-a08-session-${selectedPatient.id}.hl7`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const vitalsItems = useMemo(
    () => normalizeVitalsList(selectedPatient?.entities?.vitals),
    [selectedPatient]
  );

  return (
    <div className="flex flex-col h-full w-full bg-[var(--surface-base)] border border-[var(--surface-border)] rounded-2xl overflow-hidden shadow-xl">
      {/* Header */}
      <header className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 px-4 sm:px-6 py-4 bg-[var(--surface-panel)] border-b border-[var(--surface-border)] shrink-0">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-sky-500/10 border border-sky-500/20 text-sky-400 shrink-0">
            <Building2 className="w-5 h-5" />
          </div>
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-base md:text-lg font-semibold text-slate-100 tracking-tight">
                Simulador de Historia Clínica Electrónica (HCE)
              </h1>
              <span className="px-2 py-0.5 rounded-md bg-sky-500/10 border border-sky-500/25 text-sky-400 text-[10px] font-mono font-semibold">
                HL7 FHIR R4 · v2.5.1
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-0.5">
              Receptor hospitalario simulado de admisiones de triaje e interoperabilidad clínica estructurada.
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2 self-end sm:self-auto">
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[var(--surface-sunken)] border border-[var(--surface-border)] text-xs font-mono text-slate-300">
            <User className="w-3.5 h-3.5 text-sky-400" />
            <span>{patients.length} admisiones</span>
          </div>
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[var(--surface-sunken)] border border-[var(--surface-border)] text-xs font-mono text-slate-300">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
            <span>{syncedCount} FHIR R4</span>
          </div>
          <button
            type="button"
            onClick={fetchPatients}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[var(--surface-card)] hover:bg-[var(--surface-card-hover)] border border-[var(--surface-border)] text-xs font-medium text-slate-200 transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span>Actualizar</span>
          </button>
        </div>
      </header>

      {/* Main Master-Detail Content */}
      <div className="flex flex-1 min-h-0 overflow-hidden">
        {/* Left Master Queue */}
        <aside
          aria-label="Cola de admisiones en HCE"
          className={`w-full lg:w-[360px] xl:w-[390px] shrink-0 flex flex-col border-r border-[var(--surface-border)] bg-[var(--surface-panel)] ${
            mobileDetailOpen ? 'hidden lg:flex' : 'flex'
          }`}
        >
          <div className="p-3.5 space-y-2.5 border-b border-[var(--surface-border)]">
            <div className="relative">
              <Search className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
              <input
                type="search"
                aria-label="Buscar paciente en HCE"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Buscar por nombre, documento o ID FHIR..."
                className="w-full pl-9 pr-3 py-2 rounded-xl bg-[var(--surface-input)] border border-[var(--surface-border)] text-xs text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-sky-500/60"
              />
            </div>

            <div className="grid grid-cols-3 gap-1.5">
              {[
                { key: 'all', label: 'Todos' },
                { key: 'synced', label: 'FHIR Activo' },
                { key: 'pending', label: 'Sin FHIR' },
              ].map((item) => {
                const active = syncFilter === item.key;
                return (
                  <button
                    key={item.key}
                    type="button"
                    aria-pressed={active}
                    onClick={() => setSyncFilter(item.key as 'all' | 'synced' | 'pending')}
                    className={`py-1.5 px-2 rounded-lg text-[11px] font-medium border transition-colors ${
                      active
                        ? 'bg-sky-600 border-sky-500 text-white'
                        : 'bg-[var(--surface-card)] border-[var(--surface-border)] text-slate-300 hover:bg-[var(--surface-card-hover)]'
                    }`}
                  >
                    {item.label}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="flex-1 overflow-y-auto p-3 space-y-2">
            {loading ? (
              <div className="flex flex-col items-center justify-center py-16 gap-2.5 text-slate-400">
                <div className="w-7 h-7 border-2 border-sky-500/30 border-t-sky-500 rounded-full animate-spin" />
                <span className="text-xs font-mono">Consultando admisiones...</span>
              </div>
            ) : filteredPatients.length === 0 ? (
              <div className="text-center py-14 px-4 space-y-1.5">
                <p className="text-xs font-medium text-slate-300">Sin admisiones coincidentes</p>
                <p className="text-[11px] text-slate-500">
                  Los triajes registrados en la estación de voz aparecerán aquí automáticamente.
                </p>
              </div>
            ) : (
              filteredPatients.map((patient) => {
                const isSelected = patient.id === selectedId;
                const levelStyle = getLevelStyle(patient.level);
                const cleanDoc = patient.document_id?.startsWith('anon-')
                  ? 'Sin documento'
                  : patient.document_id;

                return (
                  <button
                    key={patient.id}
                    type="button"
                    onClick={() => {
                      setSelectedId(patient.id);
                      setMobileDetailOpen(true);
                    }}
                    className={`w-full text-left p-3 rounded-xl border border-l-4 transition-all ${levelStyle.border} ${
                      isSelected
                        ? 'bg-[var(--surface-card-hover)] border-[var(--surface-border-active)] shadow-md'
                        : 'bg-[var(--surface-card)] border-[var(--surface-border)] hover:bg-[var(--surface-card-hover)]'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="text-xs font-semibold text-slate-100 truncate">{patient.name}</p>
                        <p className="text-[11px] font-mono text-slate-400 truncate mt-0.5">
                          ID: {cleanDoc}
                        </p>
                      </div>
                      <span
                        className={`px-2 py-0.5 rounded-md border text-[11px] font-mono font-bold shrink-0 ${levelStyle.badge}`}
                      >
                        Nivel {ROMAN_NUMERALS[patient.level] || patient.level}
                      </span>
                    </div>

                    <div className="flex items-center justify-between gap-2 mt-2.5 pt-2 border-t border-[var(--surface-border-subtle)] text-[10px]">
                      <span className="text-slate-300 font-medium truncate">
                        {STATUS_LABELS[patient.status] || patient.status || 'Pendiente de Recepción'}
                      </span>
                      <div className="flex items-center gap-1.5 shrink-0 font-mono">
                        {patient.fhir_synced ? (
                          <span className="px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                            FHIR R4
                          </span>
                        ) : (
                          <span className="px-1.5 py-0.5 rounded bg-slate-500/10 text-slate-400 border border-[var(--surface-border)]">
                            Sin sincronizar
                          </span>
                        )}
                        <span className="text-slate-500">{patient.admission_time}</span>
                      </div>
                    </div>
                  </button>
                );
              })
            )}
          </div>
        </aside>

        {/* Right Detail Panel */}
        <section
          aria-label="Expediente clínico en HCE"
          className={`flex-1 flex flex-col min-w-0 overflow-y-auto bg-[var(--surface-base)] ${
            mobileDetailOpen ? 'flex' : 'hidden lg:flex'
          }`}
        >
          {!selectedPatient ? (
            <div className="flex-1 flex flex-col items-center justify-center p-8 text-center gap-3 text-slate-400">
              <div className="p-4 rounded-2xl bg-[var(--surface-panel)] border border-[var(--surface-border)] text-sky-400">
                <FileText className="w-8 h-8" />
              </div>
              <div className="space-y-1 max-w-sm">
                <p className="text-sm font-semibold text-slate-200">Sin admisión seleccionada</p>
                <p className="text-xs text-slate-400">
                  Seleccione un paciente en la cola de admisiones para inspeccionar su ficha clínica estructurada y sus recursos HL7 FHIR R4 / v2.5.1.
                </p>
              </div>
            </div>
          ) : (
            <div className="p-4 sm:p-6 space-y-5 max-w-5xl w-full mx-auto">
              {/* Mobile Back Navigation */}
              <div className="lg:hidden">
                <button
                  type="button"
                  onClick={() => setMobileDetailOpen(false)}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[var(--surface-panel)] border border-[var(--surface-border)] text-xs font-medium text-slate-200"
                >
                  <ArrowLeft className="w-3.5 h-3.5" />
                  <span>Volver a Cola de Admisiones</span>
                </button>
              </div>

              {/* Patient Demographics & Sync Header Card */}
              <div className="p-4 sm:p-5 rounded-2xl bg-[var(--surface-panel)] border border-[var(--surface-border)] space-y-4">
                <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
                  <div className="space-y-1.5">
                    <div className="flex flex-wrap items-center gap-2.5">
                      <h2 className="text-lg font-semibold text-slate-100 tracking-tight">
                        {selectedPatient.name}
                      </h2>
                      <span
                        className={`px-2.5 py-0.5 rounded-lg border text-xs font-mono font-bold ${
                          getLevelStyle(selectedPatient.level).pill
                        }`}
                      >
                        Nivel {ROMAN_NUMERALS[selectedPatient.level] || selectedPatient.level} ·{' '}
                        {TRIAGE_LEVEL_METADATA[selectedPatient.level]?.name || 'Triaje'}
                      </span>
                      {selectedPatient.ai_level !== selectedPatient.level || selectedPatient.is_level_modified ? (
                        <span className="px-2 py-0.5 rounded-md bg-amber-500/15 border border-amber-500/30 text-amber-300 text-[11px] font-mono">
                          Ajustado por Médico (IA: Nivel {ROMAN_NUMERALS[selectedPatient.ai_level] || selectedPatient.ai_level})
                        </span>
                      ) : (
                        <span className="px-2 py-0.5 rounded-md bg-sky-500/10 border border-sky-500/25 text-sky-300 text-[11px] font-mono">
                          Concordante con IA
                        </span>
                      )}
                    </div>

                    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-400 font-mono">
                      <span>
                        Doc:{' '}
                        <strong className="text-slate-200">
                          {selectedPatient.document_id?.startsWith('anon-')
                            ? 'No registrado'
                            : selectedPatient.document_id}
                        </strong>
                      </span>
                      <span>
                        Sexo:{' '}
                        <strong className="text-slate-200">
                          {GENDER_LABELS[selectedPatient.gender] || 'No registrado'}
                        </strong>
                      </span>
                      <span>
                        Nacimiento:{' '}
                        <strong className="text-slate-200">
                          {selectedPatient.birth_date || 'No registrada'}
                        </strong>
                      </span>
                      <span>
                        Tel:{' '}
                        <strong className="text-slate-200">
                          {selectedPatient.phone && selectedPatient.phone !== 'N/A'
                            ? selectedPatient.phone
                            : 'No registrado'}
                        </strong>
                      </span>
                      <span>
                        EPS:{' '}
                        <strong className="text-slate-200">
                          {selectedPatient.insurance || 'No registrada'}
                        </strong>
                      </span>
                    </div>
                  </div>

                  <div className="flex flex-col sm:flex-row md:flex-col items-stretch sm:items-center md:items-end gap-2 shrink-0">
                    <button
                      type="button"
                      onClick={handleSyncToFHIR}
                      disabled={syncingFhir}
                      className="inline-flex items-center justify-center gap-2 px-4 py-2 rounded-xl bg-sky-600 hover:bg-sky-500 disabled:opacity-50 text-white text-xs font-semibold transition-colors shadow-sm"
                    >
                      <Share2 className="w-3.5 h-3.5" />
                      <span>
                        {syncingFhir
                          ? 'Sincronizando...'
                          : selectedPatient.fhir_synced
                            ? 'Re-sincronizar FHIR R4'
                            : 'Sincronizar con HCE (FHIR R4)'}
                      </span>
                    </button>

                    {selectedPatient.fhir_synced ? (
                      <span className="text-[11px] font-mono text-emerald-400 flex items-center gap-1">
                        <CheckCircle2 className="w-3.5 h-3.5 shrink-0" />
                        <span>ID FHIR: {selectedPatient.fhir_resource_id}</span>
                      </span>
                    ) : (
                      <span className="text-[11px] font-mono text-slate-400 flex items-center gap-1">
                        <Clock className="w-3.5 h-3.5 shrink-0" />
                        <span>Admisión pendiente de envío FHIR</span>
                      </span>
                    )}
                  </div>
                </div>

                {/* View Selector Tabs */}
                <div
                  role="tablist"
                  aria-label="Secciones del expediente HCE"
                  className="flex items-center gap-2 pt-3 border-t border-[var(--surface-border)]"
                >
                  <button
                    type="button"
                    role="tab"
                    aria-selected={detailTab === 'clinical'}
                    onClick={() => setDetailTab('clinical')}
                    className={`inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-semibold border transition-colors ${
                      detailTab === 'clinical'
                        ? 'bg-sky-600 border-sky-500 text-white'
                        : 'bg-[var(--surface-card)] border-[var(--surface-border)] text-slate-300 hover:bg-[var(--surface-card-hover)]'
                    }`}
                  >
                    <Stethoscope className="w-3.5 h-3.5" />
                    <span>Ficha Clínica Estructurada</span>
                  </button>

                  <button
                    type="button"
                    role="tab"
                    aria-selected={detailTab === 'interop'}
                    onClick={() => setDetailTab('interop')}
                    className={`inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-semibold border transition-colors ${
                      detailTab === 'interop'
                        ? 'bg-sky-600 border-sky-500 text-white'
                        : 'bg-[var(--surface-card)] border-[var(--surface-border)] text-slate-300 hover:bg-[var(--surface-card-hover)]'
                    }`}
                  >
                    <Code2 className="w-3.5 h-3.5" />
                    <span>Interoperabilidad (FHIR R4 / HL7 v2)</span>
                  </button>
                </div>
              </div>

              {detailTab === 'clinical' ? (
                <div className="space-y-5">
                  {/* Vitals Grid */}
                  <div className="p-4 sm:p-5 rounded-2xl bg-[var(--surface-panel)] border border-[var(--surface-border)] space-y-3">
                    <div className="flex items-center justify-between">
                      <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-300 flex items-center gap-2">
                        <HeartPulse className="w-4 h-4 text-rose-400" />
                        <span>Signos Vitales al Ingreso (LOINC / UCUM)</span>
                      </h3>
                      <span className="text-[11px] font-mono text-slate-400">
                        Ingreso: {selectedPatient.admission_time}
                      </span>
                    </div>

                    {vitalsItems.length === 0 ? (
                      <p className="text-xs text-slate-500 italic">
                        Sin signos vitales estructurados registrados en la consulta.
                      </p>
                    ) : (
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
                        {vitalsItems.map((vital, idx) => (
                          <div
                            key={`${vital.label}-${idx}`}
                            className="p-3 rounded-xl bg-[var(--surface-card)] border border-[var(--surface-border)]"
                          >
                            <span className="text-[10px] font-mono uppercase text-slate-400 block">
                              {vital.label}
                            </span>
                            <span className="text-sm font-mono font-bold text-slate-100 tabular-nums mt-0.5 block">
                              {vital.value}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Clinical Justification */}
                  <div className="p-4 sm:p-5 rounded-2xl bg-[var(--surface-panel)] border border-[var(--surface-border)] space-y-2.5">
                    <div className="flex items-center justify-between gap-2">
                      <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-300 flex items-center gap-2">
                        <Activity className="w-4 h-4 text-sky-400" />
                        <span>Sustento Clínico de Clasificación</span>
                      </h3>
                      {selectedPatient.engine_used && (
                        <span className="text-[10px] font-mono text-slate-400">
                          Motor: {selectedPatient.engine_used}
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-slate-200 leading-relaxed whitespace-pre-wrap bg-[var(--surface-sunken)] p-3.5 rounded-xl border border-[var(--surface-border)]">
                      {selectedPatient.justification || 'Sin justificación clínica registrada.'}
                    </p>
                  </div>

                  {/* Structured Clinical Entities Grid */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {/* Symptoms & Diagnoses */}
                    <div className="p-4 rounded-2xl bg-[var(--surface-panel)] border border-[var(--surface-border)] space-y-3">
                      <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-300 flex items-center gap-2">
                        <Stethoscope className="w-4 h-4 text-sky-400" />
                        <span>Hallazgos Clínicos y Diagnósticos</span>
                      </h3>
                      <div className="space-y-2.5">
                        <div>
                          <span className="text-[11px] text-slate-400 block mb-1">Síntomas activos</span>
                          {(selectedPatient.entities?.symptoms || []).length > 0 ? (
                            <div className="flex flex-wrap gap-1.5">
                              {selectedPatient.entities.symptoms!.map((sym, i) => (
                                <span
                                  key={`${sym}-${i}`}
                                  className="px-2.5 py-1 rounded-lg bg-sky-500/10 border border-sky-500/25 text-sky-300 text-xs"
                                >
                                  {sym}
                                </span>
                              ))}
                            </div>
                          ) : (
                            <span className="text-xs text-slate-500">No referidos</span>
                          )}
                        </div>

                        {(selectedPatient.entities?.diagnoses || []).length > 0 && (
                          <div>
                            <span className="text-[11px] text-slate-400 block mb-1">Impresión diagnóstica / Lesiones</span>
                            <div className="flex flex-wrap gap-1.5">
                              {selectedPatient.entities.diagnoses!.map((dx, i) => (
                                <span
                                  key={`${dx}-${i}`}
                                  className="px-2.5 py-1 rounded-lg bg-indigo-500/10 border border-indigo-500/25 text-indigo-300 text-xs"
                                >
                                  {dx}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}

                        <div>
                          <span className="text-[11px] text-slate-400 block mb-1">Hallazgos descartados (negación clínica)</span>
                          {(selectedPatient.entities?.negated_findings || []).length > 0 ? (
                            <div className="flex flex-wrap gap-1.5">
                              {selectedPatient.entities.negated_findings!.map((nf, i) => (
                                <span
                                  key={`${nf}-${i}`}
                                  className="px-2.5 py-1 rounded-lg bg-[var(--surface-card)] border border-[var(--surface-border)] text-slate-300 text-xs line-through decoration-slate-500"
                                >
                                  {nf}
                                </span>
                              ))}
                            </div>
                          ) : (
                            <span className="text-xs text-slate-500">Sin negaciones explícitas</span>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* Allergies, Medications & History */}
                    <div className="p-4 rounded-2xl bg-[var(--surface-panel)] border border-[var(--surface-border)] space-y-3">
                      <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-300 flex items-center gap-2">
                        <ShieldAlert className="w-4 h-4 text-amber-400" />
                        <span>Alergias, Medicación y Antecedentes</span>
                      </h3>

                      <div className="space-y-2.5">
                        <div>
                          <span className="text-[11px] text-slate-400 block mb-1">Alergias reportadas</span>
                          {(selectedPatient.entities?.allergies || []).length > 0 ? (
                            <div className="flex flex-wrap gap-1.5">
                              {selectedPatient.entities.allergies!.map((alg, i) => (
                                <span
                                  key={`${alg}-${i}`}
                                  className="px-2.5 py-1 rounded-lg bg-rose-500/15 border border-rose-500/35 text-rose-300 text-xs font-medium"
                                >
                                  {alg}
                                </span>
                              ))}
                            </div>
                          ) : (
                            <span className="text-xs text-slate-500">No referidas</span>
                          )}
                        </div>

                        <div>
                          <span className="text-[11px] text-slate-400 flex items-center gap-1 mb-1">
                            <Pill className="w-3 h-3 text-emerald-400" />
                            <span>Medicamentos en uso</span>
                          </span>
                          {(selectedPatient.entities?.medications || []).length > 0 ? (
                            <div className="flex flex-wrap gap-1.5">
                              {selectedPatient.entities.medications!.map((med, i) => (
                                <span
                                  key={`${med}-${i}`}
                                  className="px-2.5 py-1 rounded-lg bg-emerald-500/10 border border-emerald-500/25 text-emerald-300 text-xs"
                                >
                                  {med}
                                </span>
                              ))}
                            </div>
                          ) : (
                            <span className="text-xs text-slate-500">Sin medicación reportada</span>
                          )}
                        </div>

                        <div>
                          <span className="text-[11px] text-slate-400 flex items-center gap-1 mb-1">
                            <History className="w-3 h-3 text-sky-400" />
                            <span>Antecedentes patológicos</span>
                          </span>
                          {(selectedPatient.entities?.history || []).length > 0 ? (
                            <div className="flex flex-wrap gap-1.5">
                              {selectedPatient.entities.history!.map((hist, i) => (
                                <span
                                  key={`${hist}-${i}`}
                                  className="px-2.5 py-1 rounded-lg bg-[var(--surface-card)] border border-[var(--surface-border)] text-slate-200 text-xs"
                                >
                                  {hist}
                                </span>
                              ))}
                            </div>
                          ) : (
                            <span className="text-xs text-slate-500">Sin antecedentes referidos</span>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* HCE Reception & Clinical Evolution Form */}
                  <div className="p-4 sm:p-5 rounded-2xl bg-[var(--surface-panel)] border border-[var(--surface-border)] space-y-3.5">
                    <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-300 flex items-center gap-2">
                      <FileText className="w-4 h-4 text-sky-400" />
                      <span>Recepción y Evolución en HCE</span>
                    </h3>

                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                      <div className="space-y-1">
                        <label
                          htmlFor="hce-care-status"
                          className="text-[11px] font-medium text-slate-400 block"
                        >
                          Estado asistencial en HCE
                        </label>
                        <select
                          id="hce-care-status"
                          value={careStatusInput}
                          onChange={(e) => setCareStatusInput(e.target.value)}
                          className="w-full px-3 py-2 rounded-xl bg-[var(--surface-input)] border border-[var(--surface-border)] text-xs text-slate-200 focus:outline-none focus:border-sky-500/60"
                        >
                          {CARE_STATUS_OPTIONS.map((opt) => (
                            <option key={opt.value} value={opt.value}>
                              {opt.label}
                            </option>
                          ))}
                        </select>
                      </div>

                      <div className="sm:col-span-2 space-y-1">
                        <label
                          htmlFor="hce-evolution-notes"
                          className="text-[11px] font-medium text-slate-400 block"
                        >
                          Notas de recepción / evolución médica
                        </label>
                        <textarea
                          id="hce-evolution-notes"
                          rows={2}
                          value={evolutionNotes}
                          onChange={(e) => setEvolutionNotes(e.target.value)}
                          placeholder="Registre observaciones clínicas de ingreso, conductas iniciales o direccionamiento..."
                          className="w-full px-3 py-2 rounded-xl bg-[var(--surface-input)] border border-[var(--surface-border)] text-xs text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-sky-500/60"
                        />
                      </div>
                    </div>

                    <div className="flex justify-end">
                      <button
                        type="button"
                        onClick={handleSaveEvolution}
                        disabled={savingEvolution}
                        className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-xs font-semibold transition-colors"
                      >
                        <Save className="w-3.5 h-3.5" />
                        <span>{savingEvolution ? 'Guardando...' : 'Guardar en HCE'}</span>
                      </button>
                    </div>
                  </div>
                </div>
              ) : (
                /* Interoperability Inspector Tab */
                <div className="p-4 sm:p-5 rounded-2xl bg-[var(--surface-panel)] border border-[var(--surface-border)] space-y-4">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        aria-pressed={interopFormat === 'fhir'}
                        onClick={() => setInteropFormat('fhir')}
                        className={`px-3 py-1.5 rounded-lg text-xs font-mono font-semibold border transition-colors ${
                          interopFormat === 'fhir'
                            ? 'bg-sky-600 border-sky-500 text-white'
                            : 'bg-[var(--surface-card)] border-[var(--surface-border)] text-slate-300'
                        }`}
                      >
                        Bundle HL7 FHIR R4 (JSON)
                      </button>
                      <button
                        type="button"
                        aria-pressed={interopFormat === 'hl7v2'}
                        onClick={() => setInteropFormat('hl7v2')}
                        className={`px-3 py-1.5 rounded-lg text-xs font-mono font-semibold border transition-colors ${
                          interopFormat === 'hl7v2'
                            ? 'bg-sky-600 border-sky-500 text-white'
                            : 'bg-[var(--surface-card)] border-[var(--surface-border)] text-slate-300'
                        }`}
                      >
                        Mensaje HL7 v2.5.1 (ADT^A08 ER7)
                      </button>
                    </div>

                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={handleCopyPayload}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[var(--surface-card)] hover:bg-[var(--surface-card-hover)] border border-[var(--surface-border)] text-xs font-medium text-slate-200"
                      >
                        {copiedPayload ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                        <span>{copiedPayload ? 'Copiado' : 'Copiar'}</span>
                      </button>
                      <button
                        type="button"
                        onClick={handleDownloadPayload}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[var(--surface-card)] hover:bg-[var(--surface-card-hover)] border border-[var(--surface-border)] text-xs font-medium text-slate-200"
                      >
                        <Download className="w-3.5 h-3.5" />
                        <span>Descargar</span>
                      </button>
                    </div>
                  </div>

                  {interopFormat === 'fhir' && (
                    <div className="flex flex-wrap items-center gap-2 text-[11px] font-mono">
                      <span className="text-slate-400">Recursos incluidos:</span>
                      {Object.entries(fhirResourceCounts).map(([rtype, count]) => (
                        <span
                          key={rtype}
                          className="px-2 py-0.5 rounded-md bg-[var(--surface-card)] border border-[var(--surface-border)] text-sky-300"
                        >
                          {rtype} ({count})
                        </span>
                      ))}
                      <span className="ml-auto text-slate-400">
                        {selectedPatient.fhir_synced
                          ? `Persistido en servidor (${selectedPatient.fhir_synced_at || 'OK'})`
                          : 'Vista previa generada lista para enviar'}
                      </span>
                    </div>
                  )}

                  <pre className="p-4 rounded-xl bg-[var(--surface-sunken)] border border-[var(--surface-border)] text-xs font-mono text-slate-200 overflow-x-auto max-h-[460px] leading-relaxed">
                    {activePayloadText}
                  </pre>
                </div>
              )}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
