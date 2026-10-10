'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Mic, Square, Activity, FileText, Send, AlertTriangle, CheckCircle2, ShieldAlert, Thermometer, Pill, Clock, Save, History, ChevronRight, Download, Play, Pause, RotateCcw, Code, Edit3, Check, X, User, Plus, ChevronDown, ChevronUp, Info, HelpCircle } from 'lucide-react';
import jsPDF from 'jspdf';
import { toast } from 'sonner';
import { useWhisperASR } from '@/hooks/useWhisperASR';
import { fetchWithAuth } from '@/lib/api';
import { validateDocumentId, validateDate, validatePhone, InputWarning } from '@/lib/validation';
import { generateFHIRBundle, downloadFHIRJson, downloadHL7v2Message } from '@/lib/hl7';


// FIX-TEC-008: Interfaces tipadas para datos clinicos criticos.
// Sustituyen useState<any> para garantizar integridad del sistema de tipos.
interface UserPermissions {
  can_use_transcriber: boolean;
  can_edit_symptoms: boolean;
  can_register_patients: boolean;
  can_view_emr: boolean;
  can_view_fhir: boolean;
  can_manage_config: boolean;
}

interface UserProfile {
  id: number;
  email: string;
  first_name?: string;
  last_name?: string;
  full_name?: string;
  name?: string;
  role: string;
  permissions?: UserPermissions;
  [key: string]: any;
}

interface TriageEntities {
  symptoms?: string[];
  medications?: string[];
  vitals?: string[];
  history?: string[];
  patientName?: string;
  [key: string]: any;
}

interface TriageLevelInfo {
  level: number;
  justification?: string;
  ai_level?: number;
  final_level?: number;
  [key: string]: any;
}

interface AnalysisResult {
  session_id?: number;
  ai_level?: number;
  final_level?: number;
  is_level_modified?: boolean;
  agreement_score?: number;
  transcript?: string;
  patientInfo?: PatientInfo;
  analysis?: {
    patientInfo?: PatientInfo;
    entities?: TriageEntities | null;
    triage?: TriageLevelInfo;
    confidence?: number;
    [key: string]: any;
  };
  triage?: TriageLevelInfo;
  entities?: TriageEntities | null;
  [key: string]: any;
}

interface PatientInfo {
  name: string;
  documentId: string;
  birthDate: string;
  gender: string;
  phone: string;
  insurance: string;
}

interface TriageSession {
  id: string;
  date: string;
  patientName: string;
  patientInfo?: PatientInfo;
  transcript: { speaker: string, text: string }[];
  analysisResult: AnalysisResult | null;
}

interface TriageDashboardProps {
  userProfile?: UserProfile | null;
}

export default function TriageDashboard({ userProfile }: TriageDashboardProps = {}) {
  const [currentUser, setCurrentUser] = useState<UserProfile | null>(userProfile || null);

  const canUseTranscriber = currentUser?.permissions ? currentUser.permissions.can_use_transcriber : true;
  const canEditSymptoms = currentUser?.permissions ? currentUser.permissions.can_edit_symptoms : true;

  useEffect(() => {
    if (userProfile) {
      setCurrentUser(userProfile);
      return;
    }
    try {
      const stored = localStorage.getItem('user_profile');
      if (stored) {
        setCurrentUser(JSON.parse(stored));
      }
    } catch (e) {}
  }, [userProfile]);

  const {
    isRecording,
    isPaused,
    isTranscribing,
    transcript: liveTranscript,
    interimText,
    startRecording,
    stopRecording,
    pauseRecording,
    resumeRecording,
    abortTranscription,
    resetTranscript,
    asrError,
    clearAsrError,
  } = useWhisperASR();

  const [transcript, setTranscript] = useState<{speaker: string, text: string}[]>([]);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisResult, setAnalysisResult] = useState<AnalysisResult | null>(null);
  const [triageError, setTriageError] = useState<string | null>(null);
  const [triageWarning, setTriageWarning] = useState<string | null>(null);
  const [isWarningMinimized, setIsWarningMinimized] = useState(false);
  const [showNewConsultModal, setShowNewConsultModal] = useState(false);
  const [pendingLevelChange, setPendingLevelChange] = useState<number | null>(null);
  const [isEditMode, setIsEditMode] = useState(false);
  const [editedEntities, setEditedEntities] = useState<TriageEntities | null>(null);
  const [isEditingJustification, setIsEditingJustification] = useState(false);
  const [editedJustification, setEditedJustification] = useState('');
  const [syncStatus, setSyncStatus] = useState<'idle' | 'syncing' | 'success'>('idle');
  const [isWaitingForAnalysis, setIsWaitingForAnalysis] = useState(false);
  const [isVerifyingTranscript, setIsVerifyingTranscript] = useState(false);
  const [activeSessionId, setActiveSessionId] = useState<number | null>(null);

  const handlePromptNewConsultation = () => {
    if (transcript.length > 0 || analysisResult) {
      setShowNewConsultModal(true);
    } else {
      executeResetConsultation();
    }
  };

  const executeResetConsultation = () => {
    setTranscript([]);
    resetTranscript();
    setAnalysisResult(null);
    setTriageError(null);
    setTriageWarning(null);
    clearAsrError();
    setEditedEntities(null);
    setIsEditMode(false);
    setIsEditingJustification(false);
    setIsVerifyingTranscript(false);
    setSyncStatus('idle');
    setActiveSessionId(null);
    setPatientInfo({
      name: '',
      documentId: '',
      birthDate: '',
      gender: 'unknown',
      phone: '',
      insurance: ''
    });
    setShowNewConsultModal(false);
    toast.success('Nueva consulta médica iniciada.');
  };

  const handleRequestTriageLevelChange = (newLevel: number) => {
    if (newLevel < 1 || newLevel > 5) return;
    const currentLvl = analysisResult?.triage?.level || 5;
    if (newLevel === currentLvl) return;
    setPendingLevelChange(newLevel);
  };

  const handleConfirmTriageLevelChange = () => {
    if (pendingLevelChange !== null) {
      handleUpdateTriageLevel(pendingLevelChange);
      setPendingLevelChange(null);
    }
  };

  const handleUpdateLine = (index: number, field: 'speaker' | 'text', value: string) => {
    setTranscript(prev => prev.map((line, i) => i === index ? { ...line, [field]: value } : line));
  };

  const handleDeleteLine = (index: number) => {
    setTranscript(prev => prev.filter((_, i) => i !== index));
  };

  const handleAddLine = () => {
    setTranscript(prev => [...prev, { speaker: 'Paciente', text: '' }]);
  };
  const [patientInfo, setPatientInfo] = useState<PatientInfo>({
    name: '',
    documentId: '',
    birthDate: '',
    gender: 'unknown',
    phone: '',
    insurance: ''
  });

  const [leftRatio, setLeftRatio] = useState(55);
  const [rightRatio, setRightRatio] = useState(60);

  const leftContainerRef = useRef<HTMLDivElement>(null);
  const rightContainerRef = useRef<HTMLDivElement>(null);

  const handleLeftResizeStart = (e: React.PointerEvent) => {
    e.preventDefault();
    const startY = e.clientY;
    const container = leftContainerRef.current;
    if (!container) return;
    const containerRect = container.getBoundingClientRect();
    const containerHeight = containerRect.height;
    const initialRatio = leftRatio;

    const handlePointerMove = (moveEvent: PointerEvent) => {
      const deltaY = moveEvent.clientY - startY;
      const deltaRatio = (deltaY / containerHeight) * 100;
      const newRatio = Math.max(20, Math.min(80, initialRatio + deltaRatio));
      setLeftRatio(newRatio);
    };

    const handlePointerUp = () => {
      document.removeEventListener('pointermove', handlePointerMove);
      document.removeEventListener('pointerup', handlePointerUp);
    };

    document.addEventListener('pointermove', handlePointerMove);
    document.addEventListener('pointerup', handlePointerUp);
  };

  const handleRightResizeStart = (e: React.PointerEvent) => {
    e.preventDefault();
    const startY = e.clientY;
    const container = rightContainerRef.current;
    if (!container) return;
    const containerRect = container.getBoundingClientRect();
    const containerHeight = containerRect.height;
    const initialRatio = rightRatio;

    const handlePointerMove = (moveEvent: PointerEvent) => {
      const deltaY = moveEvent.clientY - startY;
      const deltaRatio = (deltaY / containerHeight) * 100;
      const newRatio = Math.max(20, Math.min(80, initialRatio + deltaRatio));
      setRightRatio(newRatio);
    };

    const handlePointerUp = () => {
      document.removeEventListener('pointermove', handlePointerMove);
      document.removeEventListener('pointerup', handlePointerUp);
    };

    document.addEventListener('pointermove', handlePointerMove);
    document.addEventListener('pointerup', handlePointerUp);
  };

  const [colRatio, setColRatio] = useState(41.6);
  const [isDesktop, setIsDesktop] = useState(true);
  const mainContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleResize = () => {
      setIsDesktop(window.innerWidth >= 1024);
    };
    handleResize();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const handleHorizontalResizeStart = (e: React.PointerEvent) => {
    e.preventDefault();
    const startX = e.clientX;
    const container = mainContainerRef.current;
    if (!container) return;
    const containerRect = container.getBoundingClientRect();
    const containerWidth = containerRect.width;
    const initialRatio = colRatio;

    const handlePointerMove = (moveEvent: PointerEvent) => {
      const deltaX = moveEvent.clientX - startX;
      const deltaRatio = (deltaX / containerWidth) * 100;
      const newRatio = Math.max(25, Math.min(75, initialRatio + deltaRatio));
      setColRatio(newRatio);
    };

    const handlePointerUp = () => {
      document.removeEventListener('pointermove', handlePointerMove);
      document.removeEventListener('pointerup', handlePointerUp);
    };

    document.addEventListener('pointermove', handlePointerMove);
    document.addEventListener('pointerup', handlePointerUp);
  };

  useEffect(() => {
    if (analysisResult?.patientInfo) {
      const info = analysisResult.patientInfo;
      setPatientInfo(prev => ({
        name: prev.name || info.name || '',
        documentId: prev.documentId || info.documentId || '',
        birthDate: prev.birthDate || info.birthDate || '',
        gender: prev.gender !== 'unknown' ? prev.gender : (info.gender || 'unknown'),
        phone: prev.phone || info.phone || '',
        insurance: prev.insurance || info.insurance || ''
      }));
    } else if (analysisResult?.entities?.patientName && analysisResult.entities.patientName !== 'Paciente Desconocido') {
      setPatientInfo(prev => ({
        ...prev,
        name: prev.name || analysisResult.entities?.patientName || ''
      }));
    }
  }, [analysisResult]);


  const [savedSessions, setSavedSessions] = useState<TriageSession[]>([]);
  const [showHistory, setShowHistory] = useState(false);
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');

  const filteredSessions = savedSessions.filter(session => {
    const query = searchQuery.toLowerCase();
    const matchName = session.patientName.toLowerCase().includes(query);
    const matchLevel = (session.analysisResult?.triage?.level?.toString() || '').includes(query) || `nivel ${session.analysisResult?.triage?.level || ''}`.includes(query);
    return matchName || matchLevel;
  });

  // El historial se lee de la BD: no se guardan datos clinicos en el navegador.
  const loadHistory = useCallback(async () => {
    try {
      const res = await fetchWithAuth('/api/triage/sessions/history/');
      if (res.ok) {
        setSavedSessions(await res.json());
      }
    } catch (e) {
      console.error('Error cargando historial de triajes:', e);
    }
  }, []);

  useEffect(() => {
    // Purga del historial heredado que versiones anteriores guardaban en localStorage
    localStorage.removeItem('triage_sessions');
    loadHistory();
  }, [loadHistory]);

  const handleDownloadPDF = (session: TriageSession, e: React.MouseEvent) => {
    e.stopPropagation();
    const doc = new jsPDF();
    
    doc.setFontSize(18);
    doc.text('Resumen Clínico de Triaje', 14, 22);
    
    doc.setFontSize(12);
    doc.text(`Paciente: ${session.patientName}`, 14, 32);
    doc.text(`Fecha: ${new Date(session.date).toLocaleString()}`, 14, 38);
    doc.text(`Nivel de Triaje: ${session.analysisResult?.triage?.level || "?"}`, 14, 44);
    
    doc.setFontSize(14);
    doc.text('Justificación Clínica:', 14, 54);
    
    doc.setFontSize(10);
    const splitJustification = doc.splitTextToSize(session.analysisResult?.triage?.justification || "Sin justificación", 180);
    doc.text(splitJustification, 14, 60);
    
    let currentY = 60 + (splitJustification.length * 5) + 6;
    
    doc.setFontSize(14);
    doc.text('Entidades Extraídas:', 14, currentY);
    currentY += 6;
    
    doc.setFontSize(10);
    const entities = session.analysisResult?.entities || {};
    
    Object.keys(entities).forEach(key => {
        if (key === 'patientName') return;
        const items = entities[key] || [];
        if (items.length > 0) {
            doc.text(`${key.toUpperCase()}:`, 14, currentY);
            currentY += 5;
            items.forEach((item: string) => {
               doc.text(`• ${item}`, 18, currentY);
               currentY += 5;
            });
            currentY += 2;
        }
    });
    
    doc.save(`triaje_${session.patientName.replace(/\s+/g, '_')}_${session.id}.pdf`);
  };

  const handleStartEditJustification = () => {
    setEditedJustification(analysisResult?.triage?.justification || '');
    setIsEditingJustification(true);
  };

  const handleCancelEditJustification = () => {
    setIsEditingJustification(false);
    setEditedJustification('');
  };

  const handleSaveJustification = async () => {
    const newJustification = editedJustification.trim();
    if (!newJustification) {
      toast.error('La justificación clínica no puede estar vacía.');
      return;
    }

    setAnalysisResult((prev: any) => {
      if (!prev) return prev;
      return {
        ...prev,
        triage: {
          ...prev.triage,
          justification: newJustification,
        }
      };
    });

    if (activeSessionId) {
      try {
        await fetchWithAuth(`/api/triage/sessions/${activeSessionId}/override_level/`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            justification: newJustification,
            override_reason: 'Actualización de justificación clínica por criterio médico'
          })
        });
        toast.success('Justificación clínica actualizada');
      } catch (e) {
        console.error('Error sincronizando justificación con el servidor:', e);
        toast.error('Error al sincronizar con el servidor, guardado localmente.');
      }
    } else {
      toast.success('Justificación clínica actualizada');
    }

    setIsEditingJustification(false);
  };

  const handleDownloadFHIR = (session: TriageSession, e: React.MouseEvent) => {
    e.stopPropagation();
    downloadFHIRJson(session);
    toast.success('Descargando HL7 FHIR Release 4 JSON');
  };

  const handleDownloadHL7v2 = (session: TriageSession, e: React.MouseEvent) => {
    e.stopPropagation();
    downloadHL7v2Message(session);
    toast.success('Descargando Mensaje HL7 v2.5.1 ER7');
  };

  const handleSaveSession = async () => {
    if (!analysisResult) return;
    // La sesion ya se persiste en BD al analizar; aqui solo se refresca el historial.
    if (!activeSessionId) {
      toast.error('Esta sesión no está registrada en el servidor.');
      return;
    }
    await loadHistory();
    toast.success(`Sesión registrada en el historial para ${patientInfo.name || 'el paciente'}`);
  };

  const chatEndRef = useRef<HTMLDivElement>(null);

  // Sincronizar la transcripción en tiempo real del backend al estado local
  useEffect(() => {
    if (isRecording || isTranscribing) {
      setTranscript(liveTranscript);
    }
  }, [isRecording, isTranscribing, liveTranscript]);

  const handleUpdateTriageLevel = async (newLevel: number) => {
    if (newLevel < 1 || newLevel > 5) return;
    const aiLvl = analysisResult?.triage?.ai_level || analysisResult?.triage?.level || 5;
    
    setAnalysisResult((prev: any) => {
      if (!prev) return prev;
      return {
        ...prev,
        triage: {
          ...prev.triage,
          level: newLevel,
          final_level: newLevel,
          ai_level: aiLvl,
          is_modified: newLevel !== aiLvl,
        }
      };
    });

    if (activeSessionId) {
      try {
        await fetchWithAuth(`/api/triage/sessions/${activeSessionId}/override_level/`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            final_level: newLevel,
            override_reason: 'Ajuste manual de triaje por personal clinico'
          })
        });
        toast.success(`Nivel de triaje ajustado a Nivel ${ROMAN_LEVELS[newLevel] || newLevel}`);
      } catch (e) {
        console.error('Error sincronizando nivel con el servidor:', e);
      }
    }
  };

  const handleAnalyze = async (fullTranscript: {speaker: string, text: string}[]) => {
    setIsAnalyzing(true);
    setTriageError(null);
    setTriageWarning(null);
    try {
      const text = fullTranscript.map(t => `${t.speaker}: ${t.text}`).join('\n');
      const res = await fetchWithAuth('/api/triage/sessions/analyze/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ transcript: text })
      });
      const data = await res.json();
      if (!res.ok || data.error) {
        const errorMsg = data.error || `Error en el servicio de triaje (HTTP ${res.status})`;
        setTriageError(errorMsg);
        toast.error(errorMsg);
        return;
      }
      if (data.session_id) setActiveSessionId(data.session_id);
      const aiAnalysis = data.analysis || data;
      setAnalysisResult(aiAnalysis);
      if (data.warning || aiAnalysis.warning) {
        setTriageWarning(data.warning || aiAnalysis.warning);
      }
      if (aiAnalysis.entities) setEditedEntities(aiAnalysis.entities);
      setIsEditingJustification(false);
    } catch (err) {
      const msg = "Fallo de conexión: La API de IA o el servidor de triaje no está respondiendo.";
      setTriageError(msg);
      toast.error(msg);
      console.error(err);
    } finally {
      setIsAnalyzing(false);
    }
  };

  useEffect(() => {
    if (isWaitingForAnalysis && !isTranscribing) {
      setIsWaitingForAnalysis(false);
      if (transcript.length > 0) {
        setIsVerifyingTranscript(true);
      } else {
        toast.error("No se detectó audio transcrito. Intente de nuevo.");
      }
    }
  }, [isTranscribing, isWaitingForAnalysis, transcript]);

  const handleToggleRecording = () => {
    if (!canUseTranscriber) {
      toast.error('Acceso denegado: Tu perfil no tiene permisos para iniciar grabaciones ASR.');
      return;
    }
    if (isRecording) {
      stopRecording();
      setIsWaitingForAnalysis(true);
    } else {
      setTranscript([]);
      resetTranscript();
      setAnalysisResult(null);
      setTriageError(null);
      setTriageWarning(null);
      clearAsrError();
      setEditedEntities(null);
      setIsEditMode(false);
      setIsEditingJustification(false);
      setIsVerifyingTranscript(false);
      setSyncStatus('idle');
      setPatientInfo({
        name: '',
        documentId: '',
        birthDate: '',
        gender: 'unknown',
        phone: '',
        insurance: ''
      });
      startRecording();
    }
  };

  useEffect(() => {
    if (chatEndRef.current) {
        chatEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [transcript]);

  const handleSyncFHIR = async () => {
    if (!analysisResult) return;
    setSyncStatus('syncing');
    try {
      const tempSession: TriageSession = {
        id: selectedSessionId || Date.now().toString(),
        date: new Date().toISOString(),
        patientName: patientInfo.name || analysisResult.entities?.patientName || 'Paciente Desconocido',
        patientInfo: { ...patientInfo },
        transcript: [...transcript],
        analysisResult: analysisResult,
      };
      const fhirBundle = generateFHIRBundle(tempSession);
      
      const res = await fetchWithAuth('/api/fhir', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(fhirBundle)
      });
      if (res.status === 201) {
        setSyncStatus('success');
        toast.success("Encounter FHIR sincronizado con éxito.");
      } else {
        throw new Error("Bad response status");
      }
    } catch (err) {
      console.error(err);
      setSyncStatus('idle');
      toast.error("Fallo al intentar sincronizar con FHIR.");
    }
  };

  return (
    <div className="flex flex-col h-full w-full bg-[var(--surface-base)] text-slate-200 rounded-2xl overflow-hidden border border-[var(--surface-border)] shadow-xl">
      
      {/* View Toolbar */}
      <header className="h-14 bg-[var(--surface-panel)] border-b border-[var(--surface-border)] flex items-center justify-between px-4 sm:px-6 shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-sky-500/10 border border-sky-500/20 flex items-center justify-center text-sky-400">
            <Activity className="w-4 h-4" />
          </div>
          <div>
            <h2 className="text-xs sm:text-sm font-semibold tracking-wide text-slate-100">
              Triaje Clínico Interactivo
            </h2>
            <p className="text-[10px] text-slate-400 hidden sm:block">
              Christus Sinergia Salud • Estación de Evaluación de Urgencias
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 sm:gap-3 shrink-0">
          <Tooltip text="Reiniciar para evaluar un nuevo paciente" position="bottom">
            <button 
              type="button"
              onClick={handlePromptNewConsultation}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl transition-all text-xs font-medium bg-[var(--surface-card)] hover:bg-slate-800 text-slate-200 border border-[var(--surface-border)] shadow-sm"
              title="Iniciar nueva evaluación de paciente"
            >
              <Plus className="w-3.5 h-3.5 text-sky-400" />
              <span className="hidden sm:inline">Nueva Consulta</span>
            </button>
          </Tooltip>
          <button 
            onClick={() => { if (!showHistory) loadHistory(); setShowHistory(!showHistory); setSelectedSessionId(null); }}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl transition-all text-xs font-medium ${showHistory ? 'bg-sky-600 text-white shadow-md' : 'bg-[var(--surface-card)] text-slate-300 hover:bg-slate-800 border border-[var(--surface-border)]'}`}
          >
            <History className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Historial</span>
          </button>
          <div className="flex items-center gap-2 px-2.5 py-1 rounded-xl bg-[var(--surface-card)] border border-[var(--surface-border)]">
            <span className={`w-2 h-2 rounded-full ${isRecording ? 'bg-red-500 animate-pulse' : 'bg-emerald-500'}`}></span>
            <span className={`text-[11px] font-mono font-medium ${isRecording ? 'text-red-400' : 'text-emerald-400'} hidden sm:inline`}>{isRecording ? 'GRABANDO' : 'ASR ACTIVO'}</span>
          </div>
          <div className="px-3 py-1.5 bg-[var(--surface-card)] rounded-xl border border-[var(--surface-border)] text-xs font-medium text-slate-300 truncate max-w-[140px] sm:max-w-none flex items-center">
              <User className="w-3.5 h-3.5 text-sky-400 shrink-0 inline mr-1.5" />
              <span>{currentUser?.full_name || "Dr. Rodriguez"}</span>
              <span className="ml-2 px-2 py-0.5 rounded-full bg-sky-500/10 border border-sky-500/30 text-sky-400 text-[10px] uppercase font-semibold">
                {currentUser?.role || "Medico"}
              </span>
          </div>
        </div>
      </header>

      <main className="flex-1 p-3 sm:p-5 overflow-hidden flex flex-col">
        {showHistory ? (
          <div className="h-full flex flex-col min-h-0 overflow-y-auto">
             <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4 shrink-0">
               <h2 className="text-sm font-bold uppercase text-slate-300 tracking-widest flex items-center gap-2">
                  <History className="w-4 h-4 text-blue-400" />
                  Sesiones Guardadas ({filteredSessions.length})
               </h2>
               <div className="relative">
                 <input 
                   type="text" 
                   placeholder="Filtrar por paciente o nivel..." 
                   value={searchQuery}
                   onChange={(e) => setSearchQuery(e.target.value)}
                   className="w-full sm:w-64 bg-slate-900 border border-slate-700 rounded py-1.5 px-3 text-xs text-slate-300 focus:outline-none focus:border-blue-500 transition-colors"
                 />
               </div>
             </div>
             {filteredSessions.length === 0 ? (
               <div className="flex-1 flex flex-col items-center justify-center text-slate-500 text-xs font-mono uppercase tracking-widest border border-dashed border-slate-700 rounded-lg p-6">
                 No se encontraron sesiones.
               </div>
             ) : (
               <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 auto-rows-max pr-1 scrollbar-thin scrollbar-thumb-slate-700">
                 {filteredSessions.map(session => (
                    <div key={session.id} className="bg-slate-800/50 rounded-lg border border-slate-700 p-4 flex flex-col hover:border-slate-500 transition-colors cursor-pointer" onClick={() => { 
                      if (isRecording) handleToggleRecording();
                      setTranscript(session.transcript); 
                      setAnalysisResult(session.analysisResult); 
                      setShowHistory(false); 
                      setSelectedSessionId(session.id); 
                      // Los ajustes posteriores deben aplicarse a ESTA sesion, no a la ultima analizada
                      setActiveSessionId(Number(session.id) || null);
                      setIsEditingJustification(false);
                      if (session.patientInfo) {
                        setPatientInfo(session.patientInfo);
                      } else {
                        setPatientInfo({
                          name: session.patientName,
                          documentId: '',
                          birthDate: '',
                          gender: 'unknown',
                          phone: '',
                          insurance: ''
                        });
                      }
                    }}>
                      <div className="flex justify-between items-start mb-2">
                        <span className="text-xs font-bold uppercase text-white truncate pr-2">{session.patientName}</span>
                        <div className={`px-2 py-0.5 rounded text-[9px] font-bold uppercase ${getLevelGradient(session.analysisResult?.triage?.level)}`}>
                          Nivel {session.analysisResult?.triage?.level || "?"}
                        </div>
                      </div>
                      <span className="text-[10px] font-mono text-slate-400 mb-3 flex items-center gap-1.5"><Clock className="w-3 h-3"/> {new Date(session.date).toLocaleString()}</span>
                      <p className="text-[10px] sm:text-xs text-slate-300 line-clamp-3 leading-relaxed opacity-80 mb-3 flex-1">
                        {session.analysisResult?.triage?.justification || "Sin justificación"}
                      </p>
                      <div className="flex items-center gap-1.5 mt-auto">
                        <button 
                          onClick={(e) => handleDownloadPDF(session, e)}
                          className="flex items-center justify-center p-1.5 rounded bg-slate-700 hover:bg-slate-600 transition-colors text-slate-200"
                          title="Descargar PDF Asistencial"
                        >
                          <Download className="w-3.5 h-3.5" />
                        </button>
                        <button 
                          onClick={(e) => handleDownloadFHIR(session, e)}
                          className="flex items-center justify-center p-1.5 rounded bg-slate-700 hover:bg-slate-600 transition-colors text-cyan-400"
                          title="Exportar HL7 FHIR R4 (JSON)"
                        >
                          <Code className="w-3.5 h-3.5" />
                        </button>
                        <button 
                          onClick={(e) => handleDownloadHL7v2(session, e)}
                          className="flex items-center justify-center p-1.5 rounded bg-slate-700 hover:bg-slate-600 transition-colors text-blue-400"
                          title="Exportar HL7 v2.5.1 (ER7)"
                        >
                          <FileText className="w-3.5 h-3.5" />
                        </button>
                        <button className="flex-1 flex items-center justify-center gap-1.5 px-2.5 py-1.5 rounded bg-slate-700 hover:bg-slate-600 text-[10px] font-bold uppercase tracking-widest transition-colors text-slate-200">
                          Cargar <ChevronRight className="w-3 h-3" />
                        </button>
                      </div>
                    </div>
                 ))}
               </div>
             )}
          </div>
        ) : (
          <div 
            ref={mainContainerRef}
            className="flex flex-col lg:flex-row gap-2 h-full min-h-0 overflow-y-auto lg:overflow-hidden pr-1 lg:pr-0"
          >
          
          {/* Left Column: ASR Module */}
          <section 
            ref={leftContainerRef} 
            style={isDesktop ? { width: `${colRatio}%` } : undefined}
            className="flex flex-col gap-2 h-full min-h-[400px] lg:min-h-0 shrink-0 w-full lg:w-[41.6%]"
          >
            {/* ASR Error Banner */}
            {asrError && (
              <div className="shrink-0 p-3 bg-red-950/80 border border-red-500/80 rounded-lg flex items-start justify-between gap-2 text-red-200">
                <div className="flex items-start gap-2">
                  <AlertTriangle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
                  <div className="text-xs">
                    <span className="font-bold block text-red-300">Aviso de Motor de Transcripción (ASR):</span>
                    <span className="text-slate-300">{asrError}</span>
                  </div>
                </div>
                <button 
                  onClick={clearAsrError} 
                  className="p-1 text-red-400 hover:text-white rounded hover:bg-red-800/40 transition-colors"
                  title="Cerrar aviso"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>
            )}

            {/* ASR Transcription Box */}
            <div style={isDesktop ? { height: `${leftRatio}%` } : undefined} className="bg-[var(--surface-panel)] rounded-2xl border border-[var(--surface-border)] p-4 sm:p-5 flex flex-col overflow-hidden min-h-[320px] lg:min-h-0 shrink-0 lg:h-[55%] shadow-sm">
              <div className="flex justify-between items-center mb-3.5 shrink-0">
                <h3 className="text-xs font-semibold text-slate-200 flex items-center gap-2">
                  <div className="w-6 h-6 rounded-lg bg-sky-500/10 border border-sky-500/20 flex items-center justify-center text-sky-400">
                    <Mic className="w-3.5 h-3.5" />
                  </div>
                  <span>{isVerifyingTranscript ? 'Verificación de Transcripción' : 'Transcripción de Consulta (ASR)'}</span>
                </h3>
                <div className="flex gap-2">
                  {isVerifyingTranscript ? (
                    <>
                      <button
                        onClick={() => {
                          setIsVerifyingTranscript(false);
                          setTranscript([]);
                          resetTranscript();
                        }}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded text-[9px] sm:text-[10px] font-bold uppercase tracking-widest transition-all bg-slate-700 text-slate-300 border border-slate-600 hover:bg-red-500/30 hover:text-red-400 hover:border-red-500/50"
                      >
                        <X className="w-3 h-3" />
                        Descartar
                      </button>
                      <button
                        onClick={() => {
                          if (transcript.length > 0) {
                            handleAnalyze(transcript);
                            setIsVerifyingTranscript(false);
                          } else {
                            toast.error("La transcripción no puede estar vacía.");
                          }
                        }}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded text-[9px] sm:text-[10px] font-bold uppercase tracking-widest transition-all bg-emerald-600/20 text-emerald-400 border border-emerald-500/50 hover:bg-emerald-600/30"
                      >
                        <Check className="w-3 h-3" />
                        Confirmar y Analizar
                      </button>
                    </>
                  ) : (
                    <>
                      {!isRecording && isTranscribing && (
                        <>
                          <div className="flex items-center gap-1.5 px-3 py-1.5 text-[9px] sm:text-[10px] font-bold uppercase tracking-widest text-slate-400 animate-pulse">
                            Terminando transcripción...
                          </div>
                          <button
                            onClick={() => {
                              abortTranscription();
                            }}
                            className="flex items-center gap-1.5 px-3 py-1.5 rounded text-[9px] sm:text-[10px] font-bold uppercase tracking-widest transition-all bg-red-500/20 text-red-400 border border-red-500/50 hover:bg-red-500/30"
                          >
                            <Square className="w-3 h-3 fill-current" />
                            TERMINAR
                          </button>
                          <button
                            onClick={() => {
                              abortTranscription();
                              setIsWaitingForAnalysis(false);
                              setTranscript([]);
                              resetTranscript();
                              setAnalysisResult(null);
                              setEditedEntities(null);
                              setIsEditMode(false);
                              setPatientInfo({
                                name: '',
                                documentId: '',
                                birthDate: '',
                                gender: 'unknown',
                                phone: '',
                                insurance: ''
                              });
                            }}
                            className="flex items-center gap-1.5 px-3 py-1.5 rounded text-[9px] sm:text-[10px] font-bold uppercase tracking-widest transition-all bg-slate-700 text-slate-300 border border-slate-600 hover:bg-red-500/30 hover:text-red-400 hover:border-red-500/50"
                          >
                            <X className="w-3 h-3" />
                            CANCELAR
                          </button>
                        </>
                      )}
                      {isRecording && (
                        <>
                          <button
                            onClick={isPaused ? resumeRecording : pauseRecording}
                            className="flex items-center gap-1.5 px-3 py-1.5 rounded text-[9px] sm:text-[10px] font-bold uppercase tracking-widest transition-all bg-amber-500/20 text-amber-400 border border-amber-500/50 hover:bg-amber-500/30"
                          >
                            {isPaused ? <Play className="w-3 h-3" /> : <Pause className="w-3 h-3" />}
                            {isPaused ? 'REANUDAR' : 'PAUSAR'}
                          </button>
                          <button
                            onClick={() => {
                              stopRecording();
                              abortTranscription();
                              setIsWaitingForAnalysis(false);
                              setTranscript([]);
                              resetTranscript();
                              setAnalysisResult(null);
                              setEditedEntities(null);
                              setIsEditMode(false);
                              setPatientInfo({
                                name: '',
                                documentId: '',
                                birthDate: '',
                                gender: 'unknown',
                                phone: '',
                                insurance: ''
                              });
                            }}
                            className="flex items-center gap-1.5 px-3 py-1.5 rounded text-[9px] sm:text-[10px] font-bold uppercase tracking-widest transition-all bg-slate-700 text-slate-300 border border-slate-600 hover:bg-red-500/30 hover:text-red-400 hover:border-red-500/50"
                          >
                            <X className="w-3 h-3" />
                            CANCELAR
                          </button>
                        </>
                      )}
                      {(!isTranscribing || isRecording) && (
                        <button
                          onClick={handleToggleRecording}
                          disabled={isAnalyzing}
                          className={`flex items-center gap-1.5 px-3 py-1.5 rounded text-[9px] sm:text-[10px] font-bold uppercase tracking-widest transition-all ${
                            isRecording 
                            ? 'bg-red-500/20 text-red-400 border border-red-500/50 hover:bg-red-500/30' 
                            : 'bg-blue-600/20 text-blue-400 border border-blue-500/50 hover:bg-blue-600/30'
                          } disabled:opacity-50 disabled:cursor-not-allowed`}
                        >
                          {isRecording ? <Square className="w-3 h-3 fill-current" /> : <Mic className="w-3 h-3" />}
                          {isRecording ? 'DETENER' : 'INICIAR GRABACIÓN'}
                        </button>
                      )}
                    </>
                  )}
                </div>
              </div>

              {isVerifyingTranscript && (
                <div className="bg-blue-500/10 border border-blue-500/30 text-blue-300 rounded p-2.5 text-xs mb-3 flex items-start gap-2 shrink-0">
                  <AlertTriangle className="w-4 h-4 text-blue-400 shrink-0 mt-0.5" />
                  <div>
                    <span className="font-bold">Verificación de Conversación:</span> Edite los textos o cambie los roles de los interlocutores si es necesario. Presione <strong>Confirmar y Analizar</strong> cuando termine.
                  </div>
                </div>
              )}
              
              <div className="flex-1 overflow-y-auto space-y-3 pr-2 scrollbar-thin scrollbar-thumb-slate-700">
                {transcript.length === 0 && !isRecording && (
                    <div className="h-full flex flex-col items-center justify-center p-6 text-center">
                        <div className="w-12 h-12 rounded-2xl bg-sky-500/10 border border-sky-500/20 text-sky-400 flex items-center justify-center mb-3 shadow-inner">
                            <Mic className="w-5 h-5" />
                        </div>
                        <h4 className="text-xs font-semibold text-slate-200">
                          Esperando Entrada de Audio
                        </h4>
                        <p className="text-[11px] text-slate-400 max-w-xs mt-1 leading-relaxed">
                          Inicie la grabación para capturar el diálogo médico en tiempo real con transcripción continua.
                        </p>
                        <button
                          onClick={handleToggleRecording}
                          disabled={isAnalyzing}
                          className="mt-4 px-3.5 py-1.5 rounded-xl bg-sky-600 hover:bg-sky-500 text-white text-xs font-medium flex items-center gap-2 shadow-sm transition-all cursor-pointer disabled:opacity-50"
                        >
                          <Mic className="w-3.5 h-3.5" />
                          <span>Iniciar Grabación</span>
                        </button>
                    </div>
                )}
                <AnimatePresence>
                  {isVerifyingTranscript ? (
                    transcript.map((line, i) => (
                      <motion.div
                        key={i}
                        initial={{ opacity: 0, y: 5 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="flex items-center gap-2 bg-slate-900/60 p-1.5 rounded border border-slate-700"
                      >
                        <select
                          value={line.speaker}
                          onChange={(e) => handleUpdateLine(i, 'speaker', e.target.value)}
                          className="bg-slate-800 text-[10px] font-bold text-slate-300 rounded border border-slate-600 px-1.5 py-1 uppercase"
                        >
                          <option value="Doctor">Doctor</option>
                          <option value="Paciente">Paciente</option>
                          <option value="Familiar">Familiar</option>
                        </select>
                        <input
                          type="text"
                          value={line.text}
                          onChange={(e) => handleUpdateLine(i, 'text', e.target.value)}
                          className="flex-1 bg-slate-950 border border-slate-700 rounded px-2 py-1 text-xs text-slate-200 focus:outline-none focus:border-blue-500"
                        />
                        <button
                          onClick={() => handleDeleteLine(i)}
                          className="p-1 text-slate-400 hover:text-red-400"
                          title="Eliminar línea"
                        >
                          <X className="w-3.5 h-3.5" />
                        </button>
                      </motion.div>
                    ))
                  ) : (
                    transcript.map((line, i) => (
                      <motion.div 
                        key={i} 
                        initial={{ opacity: 0, y: 5 }}
                        animate={{ opacity: 1, y: 0 }}
                        className={`flex flex-col ${line.speaker === 'Doctor' ? 'items-start' : 'items-end'}`}
                      >
                        <span className="text-[9px] font-bold uppercase tracking-wider text-slate-400 mb-1">{line.speaker}</span>
                        <div className={`px-3 py-2 rounded max-w-[95%] text-xs sm:text-sm leading-relaxed border ${
                          line.speaker === 'Doctor' 
                          ? 'bg-slate-800 border-l-2 border-slate-500 border-y-slate-700 border-r-slate-700 text-slate-300'
                          : 'bg-slate-900/80 border-l-2 border-blue-500 border-y-slate-700 border-r-slate-700 text-slate-200'
                        }`}>
                          {line.text}
                        </div>
                      </motion.div>
                    ))
                  )}
                  {interimText && isRecording && (
                    <motion.div
                      initial={{ opacity: 0, y: 5 }}
                      animate={{ opacity: 1, y: 0 }}
                      className="flex flex-col items-start"
                    >
                      <span className="text-[9px] font-bold uppercase tracking-wider text-slate-400 mb-1">Usuario (Escuchando...)</span>
                      <div className="px-3 py-2 rounded max-w-[95%] text-xs sm:text-sm leading-relaxed border border-dashed border-slate-600 bg-slate-800/30 text-slate-400">
                        {interimText}
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
                {isVerifyingTranscript && (
                  <button
                    onClick={handleAddLine}
                    className="w-full flex items-center justify-center gap-1.5 py-2 px-4 border border-dashed border-slate-700 hover:border-slate-500 hover:bg-slate-800/30 rounded-lg text-[10px] font-bold uppercase tracking-widest text-slate-400 hover:text-slate-200 transition-all mt-2"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    Agregar línea
                  </button>
                )}
                {isRecording && (
                  <div className="flex items-center gap-2 text-blue-400/80 text-[10px] font-mono uppercase p-2 mt-2">
                    <div className="flex gap-1">
                      <span className="w-1 h-1 bg-blue-500 rounded-full animate-bounce" style={{animationDelay: '0ms'}}/>
                      <span className="w-1 h-1 bg-blue-500 rounded-full animate-bounce" style={{animationDelay: '150ms'}}/>
                      <span className="w-1 h-1 bg-blue-500 rounded-full animate-bounce" style={{animationDelay: '300ms'}}/>
                    </div>
                    Recibiendo audio...
                  </div>
                )}
                <div ref={chatEndRef} className="h-2" />
              </div>
            </div>

            {/* Resize Handle */}
            <div 
              onPointerDown={handleLeftResizeStart}
              className="hidden lg:flex h-1.5 hover:h-2 bg-slate-950/20 hover:bg-blue-500/60 rounded cursor-row-resize transition-all items-center justify-center shrink-0 group py-1"
            >
              <div className="w-8 h-1 bg-slate-700 group-hover:bg-blue-300 rounded"></div>
            </div>

            {/* Patient Info Box */}
            <div className="flex-1 bg-[var(--surface-panel)] rounded-2xl border border-[var(--surface-border)] p-4 sm:p-5 flex flex-col overflow-hidden min-h-[300px] lg:min-h-0 shadow-sm">
              <div className="flex items-center justify-between mb-3.5 shrink-0">
                <h3 className="text-xs font-semibold text-slate-200 flex items-center gap-2">
                  <div className="w-6 h-6 rounded-lg bg-sky-500/10 border border-sky-500/20 flex items-center justify-center text-sky-400">
                    <User className="w-3.5 h-3.5" />
                  </div>
                  <span>Datos del Paciente</span>
                </h3>
                <span className="text-[10px] text-slate-400 px-2 py-0.5 rounded-md bg-[#0d1422] border border-slate-800">
                  Admisión
                </span>
              </div>
              <div className="flex-1 overflow-y-auto pr-1 scrollbar-thin scrollbar-thumb-slate-700 grid grid-cols-1 sm:grid-cols-2 gap-3.5 text-xs">
                <div>
                  <label htmlFor="patient-name" className="text-xs text-slate-300 font-medium block mb-1.5">Nombre Completo</label>
                  <input
                    id="patient-name"
                    aria-label="Nombre Completo"
                    type="text"
                    value={patientInfo.name}
                    onChange={e => setPatientInfo({ ...patientInfo, name: e.target.value })}
                    className="w-full bg-[#0d1422] border border-slate-800 hover:border-slate-700 rounded-xl p-2.5 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-sky-500 focus:ring-1 focus:ring-sky-500/30 transition-all"
                    placeholder="Nombre del paciente"
                  />
                </div>
                <div>
                  <label htmlFor="patient-document-id" className="text-xs text-slate-300 font-medium block mb-1.5">Documento Identidad</label>
                  <input
                    id="patient-document-id"
                    aria-label="Documento Identidad"
                    type="text"
                    value={patientInfo.documentId}
                    onChange={e => setPatientInfo({ ...patientInfo, documentId: e.target.value })}
                    className="w-full bg-[#0d1422] border border-slate-800 hover:border-slate-700 rounded-xl p-2.5 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-sky-500 focus:ring-1 focus:ring-sky-500/30 font-mono transition-all"
                    placeholder="C.C., T.I., etc."
                  />
                  <InputWarning 
                    warning={patientInfo.documentId ? validateDocumentId(patientInfo.documentId).warning : null} 
                    id="triage-doc-warning" 
                  />
                </div>
                <div>
                  <label htmlFor="patient-birth-date" className="text-xs text-slate-300 font-medium block mb-1.5">Fecha Nacimiento</label>
                  <input
                    id="patient-birth-date"
                    aria-label="Fecha Nacimiento"
                    type="date"
                    value={patientInfo.birthDate}
                    onChange={e => setPatientInfo({ ...patientInfo, birthDate: e.target.value })}
                    className="w-full bg-[#0d1422] border border-slate-800 hover:border-slate-700 rounded-xl p-2.5 text-xs text-slate-100 focus:outline-none focus:border-sky-500 focus:ring-1 focus:ring-sky-500/30 font-mono transition-all"
                  />
                  <InputWarning 
                    warning={patientInfo.birthDate ? validateDate(patientInfo.birthDate, { maxDate: new Date().toISOString().split('T')[0], label: 'Fecha de nacimiento' }).warning : null} 
                    id="triage-birth-warning" 
                  />
                </div>
                <div>
                  <label htmlFor="patient-gender" className="text-xs text-slate-300 font-medium block mb-1.5">Género</label>
                  <select
                    id="patient-gender"
                    aria-label="Género"
                    value={patientInfo.gender}
                    onChange={e => setPatientInfo({ ...patientInfo, gender: e.target.value })}
                    className="w-full bg-[#0d1422] border border-slate-800 hover:border-slate-700 rounded-xl p-2.5 text-xs text-slate-100 focus:outline-none focus:border-sky-500 focus:ring-1 focus:ring-sky-500/30 transition-all"
                  >
                    <option value="unknown">Desconocido</option>
                    <option value="male">Masculino</option>
                    <option value="female">Femenino</option>
                    <option value="other">Otro</option>
                  </select>
                </div>
                <div>
                  <label htmlFor="patient-phone" className="text-xs text-slate-300 font-medium block mb-1.5">Teléfono</label>
                  <input
                    id="patient-phone"
                    aria-label="Teléfono"
                    type="text"
                    value={patientInfo.phone}
                    onChange={e => setPatientInfo({ ...patientInfo, phone: e.target.value })}
                    className="w-full bg-[#0d1422] border border-slate-800 hover:border-slate-700 rounded-xl p-2.5 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-sky-500 focus:ring-1 focus:ring-sky-500/30 font-mono transition-all"
                    placeholder="Número telefónico"
                  />
                  <InputWarning 
                    warning={patientInfo.phone ? validatePhone(patientInfo.phone).warning : null} 
                    id="triage-phone-warning" 
                  />
                </div>
                <div>
                  <label htmlFor="patient-insurance" className="text-xs text-slate-300 font-medium block mb-1.5">Aseguradora / EPS</label>
                  <input
                    id="patient-insurance"
                    aria-label="Aseguradora / EPS"
                    type="text"
                    value={patientInfo.insurance}
                    onChange={e => setPatientInfo({ ...patientInfo, insurance: e.target.value })}
                    className="w-full bg-[#0d1422] border border-slate-800 hover:border-slate-700 rounded-xl p-2.5 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-sky-500 focus:ring-1 focus:ring-sky-500/30 transition-all"
                    placeholder="Empresa promotora de salud"
                  />
                </div>
              </div>
            </div>
          </section>

          {/* Horizontal Resize Handle */}
          <div 
            onPointerDown={handleHorizontalResizeStart}
            className="hidden lg:flex w-1.5 hover:w-2 bg-slate-950/20 hover:bg-blue-500/60 rounded cursor-col-resize transition-all items-center justify-center shrink-0 group px-1 h-full"
          >
            <div className="w-1 h-8 bg-slate-700 group-hover:bg-blue-300 rounded"></div>
          </div>

          {/* Right Column: NLP & Triage */}
          <section 
            ref={rightContainerRef} 
            className="flex-1 flex flex-col gap-2 h-full min-h-0"
          >
            
            {/* NER Module */}
            <div style={isDesktop ? { height: `${rightRatio}%` } : undefined} className="bg-[var(--surface-panel)] rounded-2xl border border-[var(--surface-border)] p-4 sm:p-5 flex flex-col overflow-hidden min-h-[300px] lg:min-h-0 shrink-0 lg:h-[60%] shadow-sm">
              <div className="flex justify-between items-center shrink-0 mb-3.5">
                <h3 className="text-xs font-semibold text-slate-200 flex items-center gap-2">
                  <div className="w-6 h-6 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
                    <Activity className="w-3.5 h-3.5" />
                  </div>
                  <span>Entidades Clínicas Detectadas</span>
                </h3>
                <div className="flex gap-2 items-center">
                  {isAnalyzing && <span className="text-[10px] font-mono text-emerald-400/80 animate-pulse flex items-center gap-1"><Activity className="w-3 h-3"/> Analizando...</span>}
                  {analysisResult && (
                    <button
                      onClick={() => {
                        if (isEditMode) {
                          setAnalysisResult({...analysisResult, entities: editedEntities});
                        }
                        setIsEditMode(!isEditMode);
                      }}
                      className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[10px] font-semibold uppercase tracking-wider transition-all bg-[var(--surface-card)] text-slate-300 hover:bg-slate-800 border border-[var(--surface-border)]"
                    >
                      {isEditMode ? <Check className="w-3 h-3 text-emerald-400" /> : <Edit3 className="w-3 h-3 text-sky-400" />}
                      {isEditMode ? 'ACEPTAR' : 'EDITAR'}
                    </button>
                  )}
                </div>
              </div>

              <div className="flex-1 overflow-y-auto grid grid-cols-1 md:grid-cols-2 gap-3.5 pr-1 scrollbar-thin scrollbar-thumb-slate-700">
                <EntityGroup 
                  title="Síntomas" icon={<AlertTriangle className="w-3.5 h-3.5"/>} color="text-red-400" bg="bg-red-500" border="border-red-500" 
                  entities={(isEditMode ? editedEntities : analysisResult?.entities)?.symptoms} 
                  loading={isAnalyzing} isEditMode={isEditMode}
                  onAdd={val => setEditedEntities(prev => ({ ...(prev || {}), symptoms: [...(prev?.symptoms || []), val] }))}
                  onRemove={idx => setEditedEntities(prev => ({ ...(prev || {}), symptoms: (prev?.symptoms || []).filter((_, i) => i !== idx) }))}
                />
                <EntityGroup 
                  title="Antecedentes" icon={<FileText className="w-3.5 h-3.5"/>} color="text-amber-400" bg="bg-amber-500" border="border-amber-500" 
                  entities={(isEditMode ? editedEntities : analysisResult?.entities)?.history} 
                  loading={isAnalyzing} isEditMode={isEditMode}
                  onAdd={val => setEditedEntities(prev => ({ ...(prev || {}), history: [...(prev?.history || []), val] }))}
                  onRemove={idx => setEditedEntities(prev => ({ ...(prev || {}), history: (prev?.history || []).filter((_, i) => i !== idx) }))}
                />
                <EntityGroup 
                  title="Medicamentos" icon={<Pill className="w-3.5 h-3.5"/>} color="text-sky-400" bg="bg-sky-500" border="border-sky-500" 
                  entities={(isEditMode ? editedEntities : analysisResult?.entities)?.medications} 
                  loading={isAnalyzing} isEditMode={isEditMode}
                  onAdd={val => setEditedEntities(prev => ({ ...(prev || {}), medications: [...(prev?.medications || []), val] }))}
                  onRemove={idx => setEditedEntities(prev => ({ ...(prev || {}), medications: (prev?.medications || []).filter((_, i) => i !== idx) }))}
                />
                <EntityGroup 
                  title="Signos Vitales" icon={<Thermometer className="w-3.5 h-3.5"/>} color="text-emerald-400" bg="bg-emerald-500" border="border-emerald-500" 
                  entities={(isEditMode ? editedEntities : analysisResult?.entities)?.vitals} 
                  loading={isAnalyzing} isEditMode={isEditMode}
                  onAdd={val => setEditedEntities(prev => ({ ...(prev || {}), vitals: [...(prev?.vitals || []), val] }))}
                  onRemove={idx => setEditedEntities(prev => ({ ...(prev || {}), vitals: (prev?.vitals || []).filter((_, i) => i !== idx) }))}
                />
              </div>
            </div>

            {/* Resize Handle */}
            <div 
              onPointerDown={handleRightResizeStart}
              className="hidden lg:flex h-1.5 hover:h-2 bg-slate-950/20 hover:bg-emerald-500/60 rounded cursor-row-resize transition-all items-center justify-center shrink-0 group py-1"
            >
              <div className="w-8 h-1 bg-slate-700 group-hover:bg-emerald-300 rounded"></div>
            </div>

            {/* Triage Output */}
            <div className="flex-1 min-h-[300px] lg:min-h-[100px] bg-[var(--surface-panel)] rounded-2xl border border-[var(--surface-border)] p-4 sm:p-5 flex flex-col gap-3.5 overflow-y-auto shrink-0 scrollbar-thin scrollbar-thumb-slate-700 shadow-sm">
                <div className="flex items-center justify-between gap-2 mb-1 shrink-0 flex-wrap">
                  <h2 className="text-xs font-semibold text-slate-200 flex items-center gap-2">
                    <div className="w-6 h-6 rounded-lg bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400">
                      <ShieldAlert className="w-3.5 h-3.5" />
                    </div>
                    <span>Motor de Triaje Clínico</span>
                  </h2>
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="px-2.5 py-0.5 rounded-full bg-sky-500/10 border border-sky-500/20 text-sky-300 text-[10px] font-medium">
                      Christus Sinergia Salud
                    </span>
                    {analysisResult?.engine_used && (
                      <span className="px-2 py-0.5 rounded-full bg-slate-800/80 border border-slate-700/80 text-slate-400 text-[10px] font-mono">
                        {analysisResult.engine_used}
                      </span>
                    )}
                  </div>
                </div>

                {/* Error Banner if triage failed */}
                {triageError && (
                  <div className="shrink-0 p-3 bg-red-950/70 border border-red-500/70 rounded-lg flex flex-col gap-2 text-red-200">
                    <div className="flex items-start gap-2">
                      <AlertTriangle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
                      <div className="text-xs">
                        <span className="font-bold block text-red-300">Error en Diagnóstico de Triaje:</span>
                        <span className="text-slate-300">{triageError}</span>
                      </div>
                    </div>
                    <div className="flex justify-end gap-2 mt-1">
                      <button
                        onClick={() => handleAnalyze(transcript)}
                        className="px-3 py-1.5 bg-red-600 hover:bg-red-500 text-white rounded text-[10px] font-bold uppercase tracking-wider flex items-center gap-1.5 transition-all shadow-md"
                      >
                        <RotateCcw className="w-3.5 h-3.5" /> Reintentar Diagnóstico
                      </button>
                    </div>
                  </div>
                )}

                {/* Warning Banner if Fallback Rules Engine was triggered */}
                {triageWarning && (
                  <div className="shrink-0 transition-all duration-200">
                    {isWarningMinimized ? (
                      <div className="p-1.5 px-2.5 bg-amber-950/60 border border-amber-500/50 rounded-lg flex items-center justify-between gap-2 text-amber-200 text-[10px]">
                        <div className="flex items-center gap-1.5 truncate">
                          <AlertTriangle className="w-3.5 h-3.5 text-amber-400 shrink-0" />
                          <span className="font-bold text-amber-300">Respaldo Asistencial Activo:</span>
                          <span className="text-amber-200/80 truncate">Protocolo Christus Sinergia Salud</span>
                        </div>
                        <button
                          type="button"
                          onClick={() => setIsWarningMinimized(false)}
                          className="text-[9px] font-bold text-amber-400 hover:text-amber-200 uppercase tracking-wider px-2 py-0.5 rounded hover:bg-amber-900/40 transition-colors flex items-center gap-1 shrink-0"
                          title="Expandir detalle del respaldo asistencial"
                        >
                          <ChevronDown className="w-3 h-3" />
                          <span>Ver Detalle</span>
                        </button>
                      </div>
                    ) : (
                      <div className="p-2.5 bg-amber-950/60 border border-amber-500/60 rounded-lg flex items-start justify-between gap-2 text-amber-200">
                        <div className="flex items-start gap-2">
                          <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                          <div className="text-[11px] leading-relaxed">
                            <span className="font-bold block text-amber-300">Respaldo Asistencial Activo:</span>
                            <span className="text-amber-200/90">{triageWarning}</span>
                          </div>
                        </div>
                        <button
                          type="button"
                          onClick={() => setIsWarningMinimized(true)}
                          className="text-[9px] font-bold text-amber-400/90 hover:text-amber-200 uppercase tracking-wider px-2 py-0.5 rounded border border-amber-500/30 hover:bg-amber-900/40 transition-colors flex items-center gap-1 shrink-0"
                          title="Minimizar aviso"
                        >
                          <ChevronUp className="w-3 h-3" />
                          <span>Minimizar</span>
                        </button>
                      </div>
                    )}
                  </div>
                )}

                {isAnalyzing ? (
                  <div className="flex-1 flex flex-col items-center justify-center text-slate-400 text-[10px] sm:text-xs font-mono uppercase tracking-widest gap-3 py-4">
                     <div className="w-5 h-5 rounded-full border-2 border-t-blue-500 border-slate-700 animate-spin" />
                     Calculando gravedad con protocolo institucional...
                  </div>
                ) : analysisResult && analysisResult.triage && analysisResult.triage.level ? (
                    <div className="flex flex-col sm:flex-row gap-3 items-stretch w-full flex-1 min-h-0">
                      <div className={`flex flex-col items-center justify-between p-3 rounded-xl shadow-lg shrink-0 w-36 sm:w-44 transition-all duration-300 border ${getLevelGradient(analysisResult.triage?.level)}`}>
                         <div className="flex items-center justify-between w-full px-1 mb-1">
                           <span className="text-[9px] font-bold uppercase tracking-widest text-white/80">Prioridad</span>
                           {analysisResult.triage?.is_modified || (analysisResult.triage?.ai_level && analysisResult.triage.level !== analysisResult.triage.ai_level) ? (
                             <span className="text-[8px] font-bold px-1.5 py-0.5 rounded bg-amber-400/20 text-amber-200 border border-amber-400/40">
                               Ajustado
                             </span>
                           ) : (
                             <span className="text-[8px] font-bold px-1.5 py-0.5 rounded bg-emerald-400/20 text-emerald-200 border border-emerald-400/40">
                               IA Concordante
                             </span>
                           )}
                         </div>

                          {/* Stepper controls */}
                          <div className="flex items-center justify-between w-full px-1 py-1">
                            <Tooltip text="Aumentar Urgencia (Nivel más crítico)" position="top">
                              <button
                                type="button"
                                onClick={() => handleRequestTriageLevelChange(Math.max(1, (analysisResult.triage?.level || 5) - 1))}
                                disabled={(analysisResult.triage?.level || 1) <= 1}
                                className="w-7 h-7 rounded-lg bg-black/30 hover:bg-black/50 text-white font-bold text-base flex items-center justify-center border border-white/20 transition-all disabled:opacity-30 disabled:hover:bg-black/30"
                              >
                                -
                              </button>
                            </Tooltip>
                            
                            <Tooltip text={`${getLevelLabel(analysisResult.triage?.level)}: ${getAttentionTime(analysisResult.triage?.level)}`} position="top">
                              <div className="flex flex-col items-center cursor-help">
                                <span className="text-4xl sm:text-5xl font-black text-white leading-none tracking-tight">
                                  {analysisResult.triage?.level ? ROMAN_LEVELS[analysisResult.triage.level] || analysisResult.triage.level : "?"}
                                </span>
                                <span className="text-[9px] font-mono text-white/70">
                                  Nivel {analysisResult.triage?.level || "?"}
                                </span>
                              </div>
                            </Tooltip>

                            <Tooltip text="Disminuir Urgencia (Nivel menos crítico)" position="top">
                              <button
                                type="button"
                                onClick={() => handleRequestTriageLevelChange(Math.min(5, (analysisResult.triage?.level || 1) + 1))}
                                disabled={(analysisResult.triage?.level || 5) >= 5}
                                className="w-7 h-7 rounded-lg bg-black/30 hover:bg-black/50 text-white font-bold text-base flex items-center justify-center border border-white/20 transition-all disabled:opacity-30 disabled:hover:bg-black/30"
                              >
                                +
                              </button>
                            </Tooltip>
                          </div>

                         <span className="mt-1 text-[10px] sm:text-xs font-bold text-white uppercase tracking-wider text-center">
                            {getLevelLabel(analysisResult.triage?.level)}
                         </span>

                         <span className="mt-0.5 px-2 py-0.5 rounded-full bg-black/40 text-[8px] sm:text-[9px] font-bold text-white/90 uppercase tracking-tight text-center">
                            {getAttentionTime(analysisResult.triage?.level)}
                         </span>

                         {analysisResult.triage?.ai_level && analysisResult.triage.level !== analysisResult.triage.ai_level && (
                           <span className="mt-1 text-[8px] text-white/80 italic text-center">
                             Sugerido IA: Nivel {ROMAN_LEVELS[analysisResult.triage.ai_level]}
                           </span>
                         )}
                      </div>
                      <div className="flex-1 min-w-0 bg-slate-900/50 rounded p-3 border border-slate-700 w-full overflow-y-auto flex flex-col justify-between">
                         <div>
                           <div className="flex items-center justify-between gap-2 mb-1.5">
                             <h3 className="text-[9px] sm:text-[10px] font-bold uppercase tracking-widest text-slate-400 flex items-center gap-1.5">
                                Justificación Clínica ({analysisResult.engine_used || 'Protocolo Christus Sinergia'})
                             </h3>
                             {!isEditingJustification ? (
                               <button
                                 type="button"
                                 onClick={handleStartEditJustification}
                                 className="flex items-center gap-1 px-2 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider bg-slate-800 text-blue-400 hover:bg-slate-700 hover:text-blue-300 border border-slate-700 transition-colors"
                                 title="Editar justificación clínica"
                               >
                                 <Edit3 className="w-2.5 h-2.5" />
                                 <span>Editar</span>
                               </button>
                             ) : (
                               <div className="flex items-center gap-1">
                                 <button
                                   type="button"
                                   onClick={handleSaveJustification}
                                   className="flex items-center gap-1 px-2 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider bg-emerald-600/30 text-emerald-300 hover:bg-emerald-600/50 border border-emerald-500/50 transition-colors"
                                   title="Guardar justificación"
                                 >
                                   <Check className="w-2.5 h-2.5" />
                                   <span>Guardar</span>
                                 </button>
                                 <button
                                   type="button"
                                   onClick={handleCancelEditJustification}
                                   className="flex items-center gap-1 px-2 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider bg-slate-800 text-slate-400 hover:bg-slate-700 hover:text-slate-300 border border-slate-700 transition-colors"
                                   title="Cancelar edición"
                                 >
                                   <X className="w-2.5 h-2.5" />
                                   <span>Cancelar</span>
                                 </button>
                               </div>
                             )}
                           </div>

                           {isEditingJustification ? (
                             <textarea
                               value={editedJustification}
                               onChange={(e) => setEditedJustification(e.target.value)}
                               rows={4}
                               className="w-full bg-slate-950/80 border border-blue-500/50 focus:border-blue-400 rounded p-2 text-xs text-slate-200 focus:outline-none transition-colors leading-relaxed resize-y font-sans"
                               placeholder="Escriba o ajuste el criterio médico y la justificación clínica del triaje..."
                             />
                           ) : (
                             <p className="text-[11px] sm:text-xs leading-relaxed text-slate-300 whitespace-pre-wrap">
                                {analysisResult.triage?.justification}
                             </p>
                           )}
                         </div>
                         <div className="mt-3 pt-2 border-t border-slate-700/60 flex items-center justify-between text-[9px] text-slate-400 font-mono">
                           <span>Confianza: {Math.round((analysisResult.confidence || 0.95) * 100)}%</span>
                           <span>Protocolo: Christus Sinergia Salud</span>
                         </div>
                      </div>
                    </div>
                ) : !triageError ? (
                  <div className="flex-1 flex flex-col items-center justify-center p-6 text-center rounded-xl bg-[#0c1322]/50 border border-slate-800/80">
                    <div className="w-10 h-10 rounded-xl bg-slate-800/60 border border-slate-700/60 flex items-center justify-center text-slate-400 mb-3 shadow-inner">
                      <ShieldAlert className="w-5 h-5 text-slate-400" />
                    </div>
                    <p className="text-xs font-semibold text-slate-300">
                      Evaluación de Triaje en Espera
                    </p>
                    <p className="text-[11px] text-slate-400 max-w-sm mt-1 leading-relaxed">
                      El nivel de urgencia según el protocolo Christus Sinergia se determinará al procesar la transcripción y los signos vitales del paciente.
                    </p>
                    <div className="flex items-center gap-1.5 mt-4 text-[10px] text-slate-400 flex-wrap justify-center">
                      <span className="px-2 py-0.5 rounded-md bg-red-950/40 border border-red-800/40 text-red-400 font-semibold">I Reanimación</span>
                      <span className="px-2 py-0.5 rounded-md bg-orange-950/40 border border-orange-800/40 text-orange-400 font-semibold">II Emergencia</span>
                      <span className="px-2 py-0.5 rounded-md bg-amber-950/40 border border-amber-800/40 text-amber-400 font-semibold">III Urgencia</span>
                      <span className="px-2 py-0.5 rounded-md bg-emerald-950/40 border border-emerald-800/40 text-emerald-400 font-semibold">IV Prioritaria</span>
                      <span className="px-2 py-0.5 rounded-md bg-sky-950/40 border border-sky-800/40 text-sky-400 font-semibold">V Externa</span>
                    </div>
                  </div>
                ) : null}

            </div>

            {/* Sync Module */}
            <div className="shrink-0 bg-[var(--surface-panel)] rounded-xl border border-[var(--surface-border)] p-3 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 shadow-sm">
              <div className="text-xs text-slate-400 flex items-center gap-2 truncate">
                 <div className={`w-2 h-2 rounded-full shrink-0 ${syncStatus === 'success' ? 'bg-emerald-500 animate-pulse' : 'bg-slate-600'}`}></div>
                 <span className="truncate font-medium">Estado: <span className="text-slate-300">{syncStatus === 'success' ? 'Guardado Exitoso' : 'En Espera'}</span></span>
              </div>
              <div className="flex w-full sm:w-auto gap-2 shrink-0 flex-wrap">
                <button
                   disabled={!analysisResult}
                   onClick={() => {
                     if (!analysisResult) return;
                     const currentSession: TriageSession = {
                       id: activeSessionId?.toString() || Date.now().toString(),
                       date: new Date().toISOString(),
                       patientName: patientInfo.name || analysisResult.entities?.patientName || 'Paciente Desconocido',
                       patientInfo: { ...patientInfo },
                       transcript: [...transcript],
                       analysisResult: analysisResult,
                     };
                     downloadFHIRJson(currentSession);
                     toast.success('Descargando HL7 FHIR R4 JSON');
                   }}
                   className="flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium bg-[#141e30] hover:bg-[#1a273e] text-cyan-300 border border-slate-800 hover:border-slate-700 disabled:opacity-40 disabled:cursor-not-allowed transition-all shadow-xs"
                   title="Exportar HL7 FHIR Release 4 (JSON Estándar)"
                >
                   <Code className="w-3.5 h-3.5 text-cyan-400" />
                   <span>FHIR R4</span>
                </button>
                <button
                   disabled={!analysisResult}
                   onClick={() => {
                     if (!analysisResult) return;
                     const currentSession: TriageSession = {
                       id: activeSessionId?.toString() || Date.now().toString(),
                       date: new Date().toISOString(),
                       patientName: patientInfo.name || analysisResult.entities?.patientName || 'Paciente Desconocido',
                       patientInfo: { ...patientInfo },
                       transcript: [...transcript],
                       analysisResult: analysisResult,
                     };
                     downloadHL7v2Message(currentSession);
                     toast.success('Descargando HL7 v2.5.1 ER7');
                   }}
                   className="flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium bg-[#141e30] hover:bg-[#1a273e] text-blue-300 border border-slate-800 hover:border-slate-700 disabled:opacity-40 disabled:cursor-not-allowed transition-all shadow-xs"
                   title="Exportar HL7 Version 2.5.1 (ER7 Oficial)"
                >
                   <FileText className="w-3.5 h-3.5 text-blue-400" />
                   <span>HL7 v2.5.1</span>
                </button>
                <button
                   disabled={!analysisResult}
                   onClick={handleSaveSession}
                   className={`flex-1 sm:flex-none flex items-center justify-center gap-1.5 px-3.5 py-1.5 rounded-xl text-xs font-medium transition-all shrink-0 ${
                      !analysisResult 
                      ? 'bg-slate-800/60 text-slate-500 border border-slate-800 cursor-not-allowed opacity-40' 
                      : 'bg-[#141e30] text-slate-200 hover:bg-[#1a273e] border border-slate-800 hover:border-slate-700 shadow-xs'
                   }`}
                >
                   <Save className="w-3.5 h-3.5" />
                   <span>Guardar en Historial</span>
                </button>
                <button
                   disabled={!analysisResult || syncStatus === 'syncing' || syncStatus === 'success'}
                   onClick={handleSyncFHIR}
                   className={`flex-1 sm:flex-none flex items-center justify-center gap-1.5 px-4 py-1.5 rounded-xl text-xs font-medium transition-all shrink-0 ${
                      !analysisResult 
                      ? 'bg-slate-800/60 text-slate-500 border border-slate-800 cursor-not-allowed opacity-40' 
                      : syncStatus === 'success'
                      ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                      : 'bg-sky-600 hover:bg-sky-500 text-white border border-sky-500/40 shadow-sm'
                   }`}
                >
                   {syncStatus === 'success' ? <CheckCircle2 className="w-3.5 h-3.5" /> : <Send className="w-3.5 h-3.5" />}
                   <span>{syncStatus === 'success' ? 'Sincronizado' : syncStatus === 'syncing' ? 'Sincronizando...' : 'Sincronizar FHIR R4'}</span>
                </button>
              </div>
            </div>

          </section>
        </div>
        )}
      </main>

      {/* Modal de Confirmacion: Nueva Consulta */}
      <ConfirmModal
        isOpen={showNewConsultModal}
        title="¿Iniciar Nueva Consulta Médica?"
        message="Se descartarán la transcripción, los signos vitales y el diagnóstico de la sesión actual no guardada. ¿Deseas continuar?"
        confirmText="Iniciar Nueva Consulta"
        cancelText="Continuar en Consulta Actual"
        confirmVariant="danger"
        onConfirm={executeResetConsultation}
        onCancel={() => setShowNewConsultModal(false)}
      />

      {/* Modal de Confirmacion: Ajuste Manual de Nivel */}
      <ConfirmModal
        isOpen={pendingLevelChange !== null}
        title="Confirmar Ajuste Clínico de Nivel"
        message={
          <div className="space-y-2">
            <p>
              Estás modificando el nivel de triaje clínico asignado:
            </p>
            <div className="p-2 rounded bg-slate-950/60 border border-slate-800 text-[11px] space-y-1">
              <div>
                <span className="text-slate-400">Nivel actual: </span>
                <span className="font-bold text-white">Nivel {ROMAN_LEVELS[analysisResult?.triage?.level || 5]} ({getLevelLabel(analysisResult?.triage?.level || 5)})</span>
              </div>
              <div>
                <span className="text-slate-400">Nuevo nivel propuesto: </span>
                <span className="font-bold text-amber-300">Nivel {ROMAN_LEVELS[pendingLevelChange || 5]} ({getLevelLabel(pendingLevelChange || 5)})</span>
              </div>
            </div>
            <p className="text-[10px] text-slate-400 italic">
              Esta modificación quedará registrada en el log de auditoría médica hospitalaria.
            </p>
          </div>
        }
        confirmText="Confirmar Nivel"
        cancelText="Mantener Nivel Actual"
        confirmVariant="warning"
        onConfirm={handleConfirmTriageLevelChange}
        onCancel={() => setPendingLevelChange(null)}
      />
    </div>
  );
}

function EntityGroup({
  title, icon, color, bg, border, entities, loading, isEditMode, onAdd, onRemove
}: {
  title: string, icon: React.ReactNode, color: string, bg: string, border: string, 
  entities?: string[], loading: boolean, isEditMode?: boolean, 
  onAdd?: (val: string) => void, onRemove?: (idx: number) => void
}) {
  const [newVal, setNewVal] = useState("");

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between px-0.5">
        <h3 className={`text-xs font-medium flex items-center gap-1.5 ${color}`}>
          {icon} <span>{title}</span>
        </h3>
        {entities && entities.length > 0 ? (
          <span className="text-[10px] font-mono px-1.5 py-0.2 rounded-full bg-slate-800 text-slate-300 border border-slate-700/60">
            {entities.length}
          </span>
        ) : null}
      </div>
      <div className="flex flex-col gap-1.5 min-h-[48px] bg-[#0c1322]/50 p-2.5 rounded-xl border border-slate-800/80">
        {!entities && !loading && (
          <div className="flex items-center gap-2 py-1.5 px-2 text-slate-500 text-xs">
            <span className="w-1.5 h-1.5 rounded-full bg-slate-700 shrink-0"></span>
            <span className="italic">Sin hallazgos preliminares</span>
          </div>
        )}
        {loading && (
          <div className="w-full flex flex-col gap-1.5 opacity-70">
            <div className={`h-6 w-full ${bg}/20 animate-pulse border-l-2 ${border} rounded-lg`}></div>
            <div className={`h-6 w-3/4 ${bg}/20 animate-pulse border-l-2 ${border} rounded-lg delay-75`}></div>
          </div>
        )}
        {!loading && entities?.map((e, idx) => (
          <div key={idx} className={`flex items-center justify-between px-2.5 py-2 bg-[#131d2e] rounded-lg border-l-2 ${border} border border-slate-800/80 hover:border-slate-700/80 transition-colors shadow-xs`}>
            <span className="text-xs font-medium text-slate-200 truncate">{e}</span>
            {isEditMode && (
              <button onClick={() => onRemove?.(idx)} className="text-red-400 hover:text-red-300 ml-2 shrink-0">
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
        ))}
        {!loading && isEditMode && (
          <div className="flex gap-1.5 mt-1">
            <input 
              type="text" 
              value={newVal} 
              onChange={e => setNewVal(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Enter' && newVal.trim()) {
                  onAdd?.(newVal.trim());
                  setNewVal("");
                }
              }}
              className="flex-1 bg-[#101728] border border-slate-800 hover:border-slate-700 rounded-lg px-2.5 py-1 text-xs text-slate-200 focus:outline-none focus:border-sky-500 focus:ring-1 focus:ring-sky-500/30"
              placeholder="Añadir..."
            />
          </div>
        )}
        {!loading && entities?.length === 0 && !isEditMode && (
          <div className="flex items-center gap-2 py-1 px-2 text-slate-500 text-[11px]">
            <span className="w-1.5 h-1.5 rounded-full bg-slate-700 shrink-0"></span>
            <span>No detectado en transcripción</span>
          </div>
        )}
      </div>
    </div>
  );
}

const ROMAN_LEVELS = ['', 'I', 'II', 'III', 'IV', 'V'];

function getLevelGradient(level?: number) {
  switch (level) {
    case 1: return 'bg-gradient-to-br from-red-600 to-red-950 border-red-500 shadow-red-900/50';
    case 2: return 'bg-gradient-to-br from-orange-600 to-orange-950 border-orange-500 shadow-orange-900/50';
    case 3: return 'bg-gradient-to-br from-amber-500 to-amber-950 border-amber-500 shadow-amber-900/50';
    case 4: return 'bg-gradient-to-br from-emerald-600 to-emerald-950 border-emerald-500 shadow-emerald-900/50';
    case 5: return 'bg-gradient-to-br from-blue-600 to-blue-950 border-blue-500 shadow-blue-900/50';
    default: return 'bg-slate-800 border-slate-700 text-slate-400';
  }
}

function getLevelLabel(level?: number) {
  switch (level) {
    case 1: return 'Reanimación';
    case 2: return 'Emergencia';
    case 3: return 'Urgencia';
    case 4: return 'Consulta Prioritaria';
    case 5: return 'Consulta Externa';
    default: return 'Sin Clasificar';
  }
}

function getAttentionTime(level?: number) {
  switch (level) {
    case 1: return 'Atención Inmediata';
    case 2: return 'Atención < 30 min';
    case 3: return 'Atención < 120 min';
    case 4: return 'Direccionamiento EPS';
    case 5: return 'Direccionamiento EPS';
    default: return '';
  }
}

function Tooltip({ children, text, position = 'top' }: { children: React.ReactNode; text: string; position?: 'top' | 'bottom' | 'left' | 'right' }) {
  const positionClasses = {
    top: 'bottom-full left-1/2 -translate-x-1/2 mb-2',
    bottom: 'top-full left-1/2 -translate-x-1/2 mt-2',
    left: 'right-full top-1/2 -translate-y-1/2 mr-2',
    right: 'left-full top-1/2 -translate-y-1/2 ml-2',
  }[position];

  return (
    <div className="relative group/tooltip inline-flex items-center">
      {children}
      <div className={`absolute ${positionClasses} hidden group-hover/tooltip:flex pointer-events-none z-50 whitespace-nowrap bg-slate-950/95 text-slate-200 text-[10px] font-sans font-medium px-2.5 py-1 rounded shadow-xl border border-slate-700/80 backdrop-blur-sm transition-all duration-150`}>
        {text}
      </div>
    </div>
  );
}

function ConfirmModal({
  isOpen,
  title,
  message,
  confirmText = "Confirmar",
  cancelText = "Cancelar",
  confirmVariant = "danger",
  onConfirm,
  onCancel,
}: {
  isOpen: boolean;
  title: string;
  message: React.ReactNode;
  confirmText?: string;
  cancelText?: string;
  confirmVariant?: "danger" | "warning" | "primary";
  onConfirm: () => void;
  onCancel: () => void;
}) {
  if (!isOpen) return null;

  const btnClasses = {
    danger: "bg-red-600 hover:bg-red-500 text-white shadow-red-900/30",
    warning: "bg-amber-600 hover:bg-amber-500 text-white shadow-amber-900/30",
    primary: "bg-sky-600 hover:bg-sky-500 text-white shadow-sky-900/30",
  }[confirmVariant];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-in fade-in duration-150">
      <div className="bg-[var(--surface-panel)] border border-[var(--surface-border)] rounded-2xl max-w-md w-full p-5 shadow-2xl space-y-4">
        <div className="flex items-start gap-3">
          <div className="p-2 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-400 shrink-0">
            <AlertTriangle className="w-5 h-5" />
          </div>
          <div className="space-y-1">
            <h3 className="text-sm font-semibold text-slate-100">{title}</h3>
            <div className="text-xs text-slate-400 leading-relaxed">{message}</div>
          </div>
        </div>
        <div className="flex justify-end gap-2.5 pt-2 border-t border-[var(--surface-border)]">
          <button
            type="button"
            onClick={onCancel}
            className="px-3.5 py-2 rounded-xl text-xs font-medium text-slate-300 hover:bg-[var(--surface-card)] transition-colors border border-[var(--surface-border)]"
          >
            {cancelText}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            className={`px-4 py-2 rounded-xl text-xs font-semibold transition-all shadow-sm ${btnClasses}`}
          >
            {confirmText}
          </button>
        </div>
      </div>
    </div>
  );
}
