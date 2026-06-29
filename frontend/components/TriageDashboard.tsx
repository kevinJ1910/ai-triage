/* eslint-disable react-hooks/set-state-in-effect */
'use client';

import { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Mic, Square, Activity, FileText, Send, AlertTriangle, CheckCircle2, ShieldAlert, Thermometer, Pill, Clock, Save, History, ChevronRight, Download, Play, Pause, RotateCcw, Code, Edit3, Check, X, User, Plus } from 'lucide-react';
import jsPDF from 'jspdf';
import { toast } from 'sonner';
import { useWhisperASR } from '@/hooks/useWhisperASR';

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
  analysisResult: any;
}

export default function TriageDashboard() {
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
  } = useWhisperASR();

  const [transcript, setTranscript] = useState<{speaker: string, text: string}[]>([]);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisResult, setAnalysisResult] = useState<any>(null);
  const [isEditMode, setIsEditMode] = useState(false);
  const [editedEntities, setEditedEntities] = useState<any>(null);
  const [syncStatus, setSyncStatus] = useState<'idle' | 'syncing' | 'success'>('idle');
  const [isWaitingForAnalysis, setIsWaitingForAnalysis] = useState(false);
  const [isVerifyingTranscript, setIsVerifyingTranscript] = useState(false);

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
  const [isDesktop, setIsDesktop] = useState(false);
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
        name: prev.name || analysisResult.entities.patientName
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

  useEffect(() => {
    const data = localStorage.getItem('triage_sessions');
    if (data) {
      try {
        setSavedSessions(JSON.parse(data));
      } catch (e) {
        console.error("Failed to load sessions", e);
      }
    }
  }, []);

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

  const handleDownloadJSON = (session: TriageSession, e: React.MouseEvent) => {
    e.stopPropagation();
    const fhirBundle = generateFHIRBundle(session);
    const jsonStr = JSON.stringify(fhirBundle, null, 2);
    const blob = new Blob([jsonStr], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `triaje_fhir_${session.patientName.replace(/\s+/g, '_')}_${session.id}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleSaveSession = () => {
    if (!analysisResult) return;
    const newSession: TriageSession = {
      id: Date.now().toString(),
      date: new Date().toISOString(),
      patientName: patientInfo.name || analysisResult.entities?.patientName || 'Paciente Desconocido',
      patientInfo: { ...patientInfo },
      transcript: [...transcript],
      analysisResult: analysisResult,
    };
    const updated = [newSession, ...savedSessions];
    setSavedSessions(updated);
    localStorage.setItem('triage_sessions', JSON.stringify(updated));
    setSyncStatus('success');
    toast.success(`Sesión guardada para ${newSession.patientName}`);
  };

  const chatEndRef = useRef<HTMLDivElement>(null);

  // Sincronizar la transcripción en tiempo real del backend al estado local
  useEffect(() => {
    if (isRecording || isTranscribing) {
      setTranscript(liveTranscript);
    }
  }, [isRecording, isTranscribing, liveTranscript]);

  const handleAnalyze = async (fullTranscript: {speaker: string, text: string}[]) => {
    setIsAnalyzing(true);
    try {
      const text = fullTranscript.map(t => `${t.speaker}: ${t.text}`).join('\n');
      const res = await fetch('/api/triage/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ transcript: text })
      });
      const data = await res.json();
      setAnalysisResult(data);
      if (data.entities) setEditedEntities(data.entities);
    } catch (err) {
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
    if (isRecording) {
      stopRecording();
      setIsWaitingForAnalysis(true);
    } else {
      setTranscript([]);
      resetTranscript();
      setAnalysisResult(null);
      setEditedEntities(null);
      setIsEditMode(false);
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
      
      const res = await fetch('/api/fhir', {
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
    <div className="flex flex-col h-full w-full bg-slate-900 text-slate-200 rounded-lg overflow-hidden border border-slate-700">
      
      {/* View Toolbar */}
      <header className="h-12 bg-slate-800 border-b border-slate-700 flex items-center justify-between px-4 shrink-0">
        <div className="flex items-center gap-3">
          <h2 className="text-[11px] font-bold tracking-widest uppercase text-slate-300">
            Triaje Clínico Interactivo
          </h2>
        </div>
        <div className="flex items-center gap-4 lg:gap-6 shrink-0">
          <button 
            onClick={() => { setShowHistory(!showHistory); setSelectedSessionId(null); }}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded transition-all text-[10px] sm:text-xs font-bold uppercase tracking-widest ${showHistory ? 'bg-blue-600 text-white shadow-md' : 'bg-slate-700 text-slate-300 hover:bg-slate-600'}`}
          >
            <History className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Historial</span>
          </button>
          <div className="flex items-center gap-2">
            <span className={`w-2 h-2 rounded-full ${isRecording ? 'bg-red-500 shadow-[0_0_8px_#ef4444] animate-pulse' : 'bg-emerald-500 shadow-[0_0_8px_#10b981]'}`}></span>
            <span className={`text-xs font-mono uppercase ${isRecording ? 'text-red-500' : 'text-emerald-500'} hidden sm:inline`}>{isRecording ? 'GRABANDO' : 'ASR ACTIVO'}</span>
          </div>
          <div className="px-3 py-1 bg-slate-700 rounded text-[10px] sm:text-xs font-medium text-slate-300 truncate max-w-[120px] sm:max-w-none">
            Usuario: Dr. Rodriguez
          </div>
        </div>
      </header>

      <main className="flex-1 p-3 lg:p-4 overflow-hidden flex flex-col">
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
                      <div className="flex items-center gap-2 mt-auto">
                        <button 
                          onClick={(e) => handleDownloadPDF(session, e)}
                          className="flex items-center justify-center p-1.5 rounded bg-slate-700 hover:bg-slate-600 transition-colors text-slate-200"
                          title="Descargar PDF"
                        >
                          <Download className="w-3.5 h-3.5" />
                        </button>
                        <button 
                          onClick={(e) => handleDownloadJSON(session, e)}
                          className="flex items-center justify-center p-1.5 rounded bg-slate-700 hover:bg-slate-600 transition-colors text-slate-200"
                          title="Descargar JSON / HL-7 Simulado"
                        >
                          <Code className="w-3.5 h-3.5" />
                        </button>
                        <button className="flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 rounded bg-slate-700 hover:bg-slate-600 text-[10px] font-bold uppercase tracking-widest transition-colors text-slate-200">
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
            className="flex flex-col gap-2 h-full min-h-[400px] lg:min-h-0 shrink-0 w-full lg:w-auto"
          >
            {/* ASR Transcription Box */}
            <div style={{ height: `${leftRatio}%` }} className="bg-slate-800/50 rounded-lg border border-slate-700 p-4 flex flex-col overflow-hidden min-h-0 shrink-0">
              <div className="flex justify-between items-center mb-3 shrink-0">
                <h3 className="text-[10px] sm:text-xs font-bold uppercase text-slate-400 tracking-widest flex items-center gap-2">
                  <Mic className="w-4 h-4 text-blue-400" />
                  {isVerifyingTranscript ? 'Verificación de Transcripción' : 'Transcripción ASR'}
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
                    <div className="h-full flex flex-col items-center justify-center text-slate-500 text-xs font-mono uppercase tracking-widest text-center border-2 border-dashed border-slate-700 rounded-lg p-6">
                        <Mic className="w-6 h-6 mb-2 opacity-30" />
                        Esperando entrada de audio...
                    </div>
                )}
                <AnimatePresence>
                  {isVerifyingTranscript ? (
                    transcript.map((line, i) => (
                      <motion.div
                        key={i}
                        initial={{ opacity: 0, y: 5 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="flex flex-col gap-2 p-3 bg-slate-900/40 border border-slate-700/60 rounded-lg w-full"
                      >
                        <div className="flex justify-between items-center gap-3 w-full">
                          <div className="flex items-center gap-2">
                            <select
                              value={line.speaker}
                              onChange={e => handleUpdateLine(i, 'speaker', e.target.value)}
                              className="bg-slate-800 border border-slate-700 rounded py-1 px-2 text-[10px] text-slate-300 font-bold uppercase focus:outline-none focus:border-blue-500"
                            >
                              <option value="Doctor">Doctor</option>
                              <option value="Paciente">Paciente</option>
                              <option value="Usuario">Usuario</option>
                            </select>
                          </div>
                          <button
                            onClick={() => handleDeleteLine(i)}
                            className="p-1 rounded hover:bg-slate-800 text-slate-400 hover:text-red-400 transition-colors"
                            title="Eliminar línea"
                          >
                            <X className="w-3.5 h-3.5" />
                          </button>
                        </div>
                        <textarea
                          value={line.text}
                          onChange={e => handleUpdateLine(i, 'text', e.target.value)}
                          rows={2}
                          className="w-full bg-slate-900 border border-slate-700 rounded p-2 text-xs sm:text-sm text-slate-200 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500/30 resize-none leading-relaxed"
                          placeholder="Texto de la transcripción..."
                        />
                      </motion.div>
                    ))
                  ) : (
                    transcript.map((line, i) => (
                      <motion.div
                        key={i}
                        initial={{ opacity: 0, y: 5 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="flex flex-col items-start"
                      >
                        <span className="text-[9px] font-bold uppercase tracking-wider text-slate-500 mb-1">{line.speaker}</span>
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
                      <span className="text-[9px] font-bold uppercase tracking-wider text-slate-500 mb-1">Usuario (Escuchando...)</span>
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
              className="h-1.5 hover:h-2 bg-slate-950/20 hover:bg-blue-500/60 rounded cursor-row-resize transition-all flex items-center justify-center shrink-0 group py-1"
            >
              <div className="w-8 h-1 bg-slate-700 group-hover:bg-blue-300 rounded"></div>
            </div>

            {/* Patient Info Box */}
            <div className="flex-1 bg-slate-800/50 rounded-lg border border-slate-700 p-4 flex flex-col overflow-hidden min-h-0">
              <h3 className="text-[10px] sm:text-xs font-bold uppercase text-slate-400 tracking-widest flex items-center gap-2 mb-3 shrink-0">
                <User className="w-4 h-4 text-blue-400" />
                Información del Paciente
              </h3>
              <div className="flex-1 overflow-y-auto pr-1 scrollbar-thin scrollbar-thumb-slate-700 grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                <div>
                  <label className="text-[9px] text-slate-500 uppercase block mb-1">Nombre Completo</label>
                  <input
                    type="text"
                    value={patientInfo.name}
                    onChange={e => setPatientInfo({ ...patientInfo, name: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-600 rounded p-1.5 text-xs text-slate-200 focus:outline-none focus:border-blue-500"
                    placeholder="Nombre del paciente"
                  />
                </div>
                <div>
                  <label className="text-[9px] text-slate-500 uppercase block mb-1">Documento Identidad</label>
                  <input
                    type="text"
                    value={patientInfo.documentId}
                    onChange={e => setPatientInfo({ ...patientInfo, documentId: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-600 rounded p-1.5 text-xs text-slate-200 focus:outline-none focus:border-blue-500"
                    placeholder="C.C., T.I., etc."
                  />
                </div>
                <div>
                  <label className="text-[9px] text-slate-500 uppercase block mb-1">Fecha Nacimiento</label>
                  <input
                    type="date"
                    value={patientInfo.birthDate}
                    onChange={e => setPatientInfo({ ...patientInfo, birthDate: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-600 rounded p-1.5 text-xs text-slate-200 focus:outline-none focus:border-blue-500"
                  />
                </div>
                <div>
                  <label className="text-[9px] text-slate-500 uppercase block mb-1">Género</label>
                  <select
                    value={patientInfo.gender}
                    onChange={e => setPatientInfo({ ...patientInfo, gender: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-600 rounded p-1.5 text-xs text-slate-200 focus:outline-none focus:border-blue-500"
                  >
                    <option value="unknown">Desconocido</option>
                    <option value="male">Masculino</option>
                    <option value="female">Femenino</option>
                    <option value="other">Otro</option>
                  </select>
                </div>
                <div>
                  <label className="text-[9px] text-slate-500 uppercase block mb-1">Teléfono</label>
                  <input
                    type="text"
                    value={patientInfo.phone}
                    onChange={e => setPatientInfo({ ...patientInfo, phone: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-600 rounded p-1.5 text-xs text-slate-200 focus:outline-none focus:border-blue-500"
                    placeholder="Número telefónico"
                  />
                </div>
                <div>
                  <label className="text-[9px] text-slate-500 uppercase block mb-1">Aseguradora / EPS</label>
                  <input
                    type="text"
                    value={patientInfo.insurance}
                    onChange={e => setPatientInfo({ ...patientInfo, insurance: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-600 rounded p-1.5 text-xs text-slate-200 focus:outline-none focus:border-blue-500"
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
            <div style={{ height: `${rightRatio}%` }} className="bg-slate-800/50 rounded-lg border border-slate-700 p-4 flex flex-col overflow-hidden min-h-0 shrink-0">
              <div className="flex justify-between items-center shrink-0 mb-3">
                <h3 className="text-[10px] sm:text-xs font-bold uppercase text-slate-400 tracking-widest flex items-center gap-2">
                  <Activity className="w-4 h-4 text-emerald-400" />
                  Entidades Clínicas (NER)
                </h3>
                <div className="flex gap-2 items-center">
                  {isAnalyzing && <span className="text-[9px] sm:text-[10px] font-mono text-emerald-400/80 animate-pulse flex items-center gap-1"><Activity className="w-3 h-3"/> Analizando...</span>}
                  {analysisResult && (
                    <button
                      onClick={() => {
                        if (isEditMode) {
                          setAnalysisResult({...analysisResult, entities: editedEntities});
                        }
                        setIsEditMode(!isEditMode);
                      }}
                      className="flex items-center gap-1.5 px-2 py-1 rounded text-[9px] font-bold uppercase tracking-widest transition-all bg-slate-700 text-slate-300 hover:bg-slate-600"
                    >
                      {isEditMode ? <Check className="w-3 h-3 text-emerald-400" /> : <Edit3 className="w-3 h-3 text-blue-400" />}
                      {isEditMode ? 'ACEPTAR' : 'EDITAR'}
                    </button>
                  )}
                </div>
              </div>

              <div className="flex-1 overflow-y-auto grid grid-cols-1 md:grid-cols-2 gap-3 pr-1 scrollbar-thin scrollbar-thumb-slate-700">
                <EntityGroup 
                  title="Síntomas" icon={<AlertTriangle className="w-3 h-3"/>} color="text-red-400" bg="bg-red-500" border="border-red-500" 
                  entities={(isEditMode ? editedEntities : analysisResult?.entities)?.symptoms} 
                  loading={isAnalyzing} isEditMode={isEditMode}
                  onAdd={val => setEditedEntities({...editedEntities, symptoms: [...(editedEntities?.symptoms || []), val]})}
                  onRemove={idx => setEditedEntities({...editedEntities, symptoms: editedEntities.symptoms.filter((_: any, i: number) => i !== idx)})}
                />
                <EntityGroup 
                  title="Antecedentes" icon={<FileText className="w-3 h-3"/>} color="text-amber-400" bg="bg-amber-500" border="border-amber-500" 
                  entities={(isEditMode ? editedEntities : analysisResult?.entities)?.history} 
                  loading={isAnalyzing} isEditMode={isEditMode}
                  onAdd={val => setEditedEntities({...editedEntities, history: [...(editedEntities?.history || []), val]})}
                  onRemove={idx => setEditedEntities({...editedEntities, history: editedEntities.history.filter((_: any, i: number) => i !== idx)})}
                />
                <EntityGroup 
                  title="Medicamentos" icon={<Pill className="w-3 h-3"/>} color="text-blue-400" bg="bg-blue-500" border="border-blue-500" 
                  entities={(isEditMode ? editedEntities : analysisResult?.entities)?.medications} 
                  loading={isAnalyzing} isEditMode={isEditMode}
                  onAdd={val => setEditedEntities({...editedEntities, medications: [...(editedEntities?.medications || []), val]})}
                  onRemove={idx => setEditedEntities({...editedEntities, medications: editedEntities.medications.filter((_: any, i: number) => i !== idx)})}
                />
                <EntityGroup 
                  title="Signos Vitales" icon={<Thermometer className="w-3 h-3"/>} color="text-emerald-400" bg="bg-emerald-500" border="border-emerald-500" 
                  entities={(isEditMode ? editedEntities : analysisResult?.entities)?.vitals} 
                  loading={isAnalyzing} isEditMode={isEditMode}
                  onAdd={val => setEditedEntities({...editedEntities, vitals: [...(editedEntities?.vitals || []), val]})}
                  onRemove={idx => setEditedEntities({...editedEntities, vitals: editedEntities.vitals.filter((_: any, i: number) => i !== idx)})}
                />
              </div>
            </div>

            {/* Resize Handle */}
            <div 
              onPointerDown={handleRightResizeStart}
              className="h-1.5 hover:h-2 bg-slate-950/20 hover:bg-emerald-500/60 rounded cursor-row-resize transition-all flex items-center justify-center shrink-0 group py-1"
            >
              <div className="w-8 h-1 bg-slate-700 group-hover:bg-emerald-300 rounded"></div>
            </div>

            {/* Triage Output */}
            <div className="flex-1 min-h-[100px] bg-slate-800/50 rounded-lg border border-slate-700 p-4 flex flex-col gap-3 overflow-y-auto shrink-0 scrollbar-thin scrollbar-thumb-slate-700">
                <h2 className="text-[10px] sm:text-xs font-bold uppercase text-slate-400 tracking-widest flex items-center gap-2 mb-1 shrink-0">
                  <ShieldAlert className="w-4 h-4 text-orange-400" />
                  Motor de Triaje Inteligente
                </h2>

                {!analysisResult && !isAnalyzing ? (
                  <div className="flex-1 flex flex-col items-center justify-center text-slate-500 text-[10px] sm:text-xs font-mono uppercase tracking-widest border border-dashed border-slate-700 rounded p-4 text-center">
                    Esperando datos de la consulta...
                  </div>
                ) : isAnalyzing ? (
                  <div className="flex-1 flex flex-col items-center justify-center text-slate-400 text-[10px] sm:text-xs font-mono uppercase tracking-widest gap-3 py-4">
                     <div className="w-5 h-5 rounded-full border-2 border-t-blue-500 border-slate-700 animate-spin" />
                     Calculando gravedad...
                  </div>
                ) : (
                    <div className="flex flex-col sm:flex-row gap-3 items-stretch w-full flex-1 min-h-0">
                      <div className={`flex flex-col items-center justify-center p-4 rounded shadow-lg shrink-0 w-32 sm:w-40 ${getLevelGradient(analysisResult.triage?.level)}`}>
                         <span className="text-[9px] font-bold uppercase tracking-widest text-white/70 mb-1">Prioridad</span>
                         <span className="text-6xl sm:text-7xl font-black text-white leading-none">
                           {analysisResult.triage?.level || "?"}
                         </span>
                         <span className={`mt-2 text-[10px] sm:text-xs font-bold text-white uppercase italic text-center`}>
                            {getLevelLabel(analysisResult.triage?.level)}
                         </span>
                      </div>
                      <div className="flex-1 min-w-0 bg-slate-900/50 rounded p-3 border border-slate-700 w-full overflow-y-auto">
                         <h3 className="text-[9px] sm:text-[10px] font-bold uppercase tracking-widest text-slate-400 mb-1.5 flex items-center gap-1.5">
                            Justificación Clínica (LLM)
                         </h3>
                         <p className="text-[11px] sm:text-xs leading-relaxed text-slate-300">
                            {analysisResult.triage?.justification}
                         </p>
                      </div>
                    </div>
                )}
            </div>

            {/* Sync Module */}
            <div className="shrink-0 bg-slate-800/50 rounded-lg border border-slate-700 p-3 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
              <div className="text-[9px] sm:text-[10px] uppercase font-mono tracking-widest text-slate-400 flex items-center gap-2 truncate">
                 <div className={`w-1.5 h-1.5 rounded-full shrink-0 ${syncStatus === 'success' ? 'bg-emerald-500' : 'bg-slate-600'}`}></div>
                 <span className="truncate">Estado: {syncStatus === 'success' ? 'Guardado Exitoso' : 'Esperando'}</span>
              </div>
              <div className="flex w-full sm:w-auto gap-2 shrink-0">
                <button
                   disabled={!analysisResult}
                   onClick={handleSaveSession}
                   className={`flex-1 sm:flex-none flex items-center justify-center gap-1.5 px-3 py-1.5 rounded text-[9px] sm:text-[10px] font-bold uppercase tracking-widest transition-all shrink-0 ${
                      !analysisResult 
                      ? 'bg-slate-700 text-slate-500 cursor-not-allowed opacity-50' 
                      : 'bg-slate-700 text-slate-300 hover:bg-slate-600 border border-slate-600'
                   }`}
                >
                   <Save className="w-3 h-3" />
                   Guardar Local
                </button>
                <button
                   disabled={!analysisResult || syncStatus === 'syncing' || syncStatus === 'success'}
                   onClick={handleSyncFHIR}
                   className={`flex-1 sm:flex-none flex items-center justify-center gap-1.5 px-3 py-1.5 rounded text-[9px] sm:text-[10px] font-bold uppercase tracking-widest transition-all shrink-0 ${
                      !analysisResult 
                      ? 'bg-slate-700 text-slate-500 cursor-not-allowed opacity-50' 
                      : syncStatus === 'success'
                      ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/50'
                      : 'bg-blue-600 text-white hover:bg-blue-500 border border-blue-500 shadow-md'
                   }`}
                >
                   {syncStatus === 'success' ? <CheckCircle2 className="w-3 h-3" /> : <Send className="w-3 h-3" />}
                   {syncStatus === 'success' ? 'SINCRONIZADO' : syncStatus === 'syncing' ? 'SINCRONIZANDO...' : 'SINCRONIZAR FHIR R4'}
                </button>
              </div>
            </div>

          </section>
        </div>
        )}
      </main>
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
      <h3 className={`text-[10px] font-bold uppercase tracking-widest flex items-center gap-1.5 ${color}`}>
        {icon} {title}
      </h3>
      <div className={`flex flex-col gap-1 min-h-[40px] bg-slate-900/30 p-1.5 rounded-md border border-slate-700/50`}>
        {!entities && !loading && <span className="text-[10px] text-slate-600 italic px-2 py-1">Pendiente...</span>}
        {loading && (
            <div className="w-full flex flex-col gap-1.5 opacity-70">
                <div className={`h-6 w-full ${bg}/20 animate-pulse border-l-2 ${border} rounded-sm`}></div>
                <div className={`h-6 w-3/4 ${bg}/20 animate-pulse border-l-2 ${border} rounded-sm delay-75`}></div>
            </div>
        )}
        {!loading && entities?.map((e, idx) => (
          <div key={idx} className={`flex items-center justify-between p-1.5 bg-slate-900 rounded-sm border-l-2 ${border}`}>
            <span className="text-[10px] sm:text-xs font-medium text-slate-200 truncate">{e}</span>
            {isEditMode && (
              <button onClick={() => onRemove?.(idx)} className="text-red-400 hover:text-red-300 ml-2 shrink-0">
                <X className="w-3 h-3" />
              </button>
            )}
          </div>
        ))}
        {!loading && isEditMode && (
          <div className="flex gap-1 mt-1">
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
              className="flex-1 bg-slate-800 border border-slate-700 rounded px-1.5 py-1 text-[10px] text-slate-200 focus:outline-none focus:border-blue-500"
              placeholder="Añadir..."
            />
          </div>
        )}
        {!loading && entities?.length === 0 && !isEditMode && <span className="text-[10px] text-slate-500 uppercase px-2 py-1 font-mono tracking-wider">No detectado</span>}
      </div>
    </div>
  )
}

function getLevelGradient(level?: number) {
  switch (level) {
    case 1: return 'bg-gradient-to-br from-red-600 to-red-900 border border-red-500 shadow-red-900/50';
    case 2: return 'bg-gradient-to-br from-orange-600 to-orange-900 border border-orange-500 shadow-orange-900/50';
    case 3: return 'bg-gradient-to-br from-yellow-600 to-yellow-900 border border-yellow-500 shadow-yellow-900/50';
    case 4: return 'bg-gradient-to-br from-emerald-600 to-emerald-900 border border-emerald-500 shadow-emerald-900/50';
    case 5: return 'bg-gradient-to-br from-blue-600 to-blue-900 border border-blue-500 shadow-blue-900/50';
    default: return 'bg-slate-800 border-slate-700 border text-slate-400';
  }
}

function getLevelLabel(level?: number) {
  switch (level) {
    case 1: return 'Resucitación';
    case 2: return 'Emergencia';
    case 3: return 'Urgencia';
    case 4: return 'Urgencia Menor';
    case 5: return 'No Urgente';
    default: return 'Desconocido';
  }
}

function generateFHIRBundle(session: TriageSession): any {
  const patientId = "pat-" + session.id;
  const encounterId = "enc-" + session.id;
  
  const patInfo = session.patientInfo || {
    name: session.patientName,
    documentId: '',
    birthDate: '',
    gender: 'unknown',
    phone: '',
    insurance: ''
  };

  // 1. Patient Resource
  const patientResource: any = {
    resourceType: "Patient",
    id: patientId,
    active: true,
    name: [
      {
        use: "official",
        text: patInfo.name || "Paciente Desconocido"
      }
    ]
  };

  if (patInfo.documentId) {
    patientResource.identifier = [
      {
        use: "official",
        type: {
          coding: [
            {
              system: "http://terminology.hl7.org/CodeSystem/v2-0203",
              code: "MC",
              display: "Identificación del Paciente"
            }
          ]
        },
        value: patInfo.documentId
      }
    ];
  }

  if (patInfo.gender && patInfo.gender !== 'unknown') {
    patientResource.gender = patInfo.gender;
  }

  if (patInfo.birthDate) {
    patientResource.birthDate = patInfo.birthDate;
  }

  if (patInfo.phone) {
    patientResource.telecom = [
      {
        system: "phone",
        value: patInfo.phone,
        use: "mobile"
      }
    ];
  }

  if (patInfo.insurance) {
    patientResource.extension = [
      {
        url: "http://hl7.org/fhir/StructureDefinition/patient-insurance",
        valueString: patInfo.insurance
      }
    ];
  }

  // 2. Encounter Resource
  const triageLevel = session.analysisResult?.triage?.level;
  let triageLabel = "Desconocido";
  switch (triageLevel) {
    case 1: triageLabel = "Resucitación"; break;
    case 2: triageLabel = "Emergencia"; break;
    case 3: triageLabel = "Urgencia"; break;
    case 4: triageLabel = "Urgencia Menor"; break;
    case 5: triageLabel = "No Urgente"; break;
  }

  const encounterResource: any = {
    resourceType: "Encounter",
    id: encounterId,
    status: "triaged",
    class: {
      system: "http://terminology.hl7.org/CodeSystem/v3-ActCode",
      code: "EMER",
      display: "emergency"
    },
    subject: {
      reference: `Patient/${patientId}`,
      display: patInfo.name || "Paciente Desconocido"
    },
    priority: {
      coding: [
        {
          system: "http://terminology.hl7.org/CodeSystem/v3-ObservationValue",
          code: triageLevel ? `L${triageLevel}` : "unknown",
          display: triageLabel
        }
      ]
    }
  };

  const symptoms = session.analysisResult?.entities?.symptoms || [];
  if (symptoms.length > 0) {
    encounterResource.reasonCode = symptoms.map((symptom: string) => ({
      text: symptom
    }));
  }

  if (session.analysisResult?.triage?.justification) {
    encounterResource.text = {
      status: "generated",
      div: `<div xmlns="http://www.w3.org/1999/xhtml"><h3>Justificación de Triaje:</h3><p>${session.analysisResult.triage.justification}</p></div>`
    };
  }

  const entries: any[] = [
    {
      fullUrl: `urn:uuid:${patientId}`,
      resource: patientResource
    },
    {
      fullUrl: `urn:uuid:${encounterId}`,
      resource: encounterResource
    }
  ];

  // 3. Condition Resources (Symptoms and History)
  const history = session.analysisResult?.entities?.history || [];
  symptoms.forEach((symptom: string, idx: number) => {
    entries.push({
      fullUrl: `urn:uuid:cond-symptom-${idx}-${session.id}`,
      resource: {
        resourceType: "Condition",
        id: `cond-symptom-${idx}-${session.id}`,
        clinicalStatus: {
          coding: [
            {
              system: "http://terminology.hl7.org/CodeSystem/condition-clinical",
              code: "active"
            }
          ]
        },
        category: [
          {
            coding: [
              {
                system: "http://terminology.hl7.org/CodeSystem/condition-category",
                code: "encounter-diagnosis",
                display: "Encounter Diagnosis"
              }
            ]
          }
        ],
        code: {
          text: symptom
        },
        subject: {
          reference: `Patient/${patientId}`
        },
        encounter: {
          reference: `Encounter/${encounterId}`
        }
      }
    });
  });

  history.forEach((hist: string, idx: number) => {
    entries.push({
      fullUrl: `urn:uuid:cond-history-${idx}-${session.id}`,
      resource: {
        resourceType: "Condition",
        id: `cond-history-${idx}-${session.id}`,
        clinicalStatus: {
          coding: [
            {
              system: "http://terminology.hl7.org/CodeSystem/condition-clinical",
              code: "active"
            }
          ]
        },
        category: [
          {
            coding: [
              {
                system: "http://terminology.hl7.org/CodeSystem/condition-category",
                code: "problem-list-item",
                display: "Problem List Item"
              }
            ]
          }
        ],
        code: {
          text: hist
        },
        subject: {
          reference: `Patient/${patientId}`
        }
      }
    });
  });

  // 4. Observation Resources (Vitals)
  const vitals = session.analysisResult?.entities?.vitals || [];
  vitals.forEach((vital: string, idx: number) => {
    entries.push({
      fullUrl: `urn:uuid:obs-vital-${idx}-${session.id}`,
      resource: {
        resourceType: "Observation",
        id: `obs-vital-${idx}-${session.id}`,
        status: "final",
        category: [
          {
            coding: [
              {
                system: "http://terminology.hl7.org/CodeSystem/observation-category",
                code: "vital-signs",
                display: "Vital Signs"
              }
            ]
          }
        ],
        code: {
          text: vital
        },
        subject: {
          reference: `Patient/${patientId}`
        },
        encounter: {
          reference: `Encounter/${encounterId}`
        },
        valueString: vital
      }
    });
  });

  // 5. MedicationStatement Resources (Medications)
  const medications = session.analysisResult?.entities?.medications || [];
  medications.forEach((med: string, idx: number) => {
    entries.push({
      fullUrl: `urn:uuid:med-${idx}-${session.id}`,
      resource: {
        resourceType: "MedicationStatement",
        id: `med-${idx}-${session.id}`,
        status: "active",
        subject: {
          reference: `Patient/${patientId}`
        },
        medicationCodeableConcept: {
          text: med
        }
      }
    });
  });

  return {
    resourceType: "Bundle",
    id: `bundle-${session.id}`,
    type: "collection",
    timestamp: new Date(session.date).toISOString(),
    entry: entries
  };
}
