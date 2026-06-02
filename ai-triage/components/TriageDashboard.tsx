/* eslint-disable react-hooks/set-state-in-effect */
'use client';

import { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Mic, Square, Activity, FileText, Send, AlertTriangle, CheckCircle2, ShieldAlert, Thermometer, Pill, Clock, Save, History, ChevronRight, Download } from 'lucide-react';
import jsPDF from 'jspdf';
import { toast } from 'sonner';
import { useWhisperASR } from '@/hooks/useWhisperASR';

interface TriageSession {
  id: string;
  date: string;
  patientName: string;
  transcript: { speaker: string, text: string }[];
  analysisResult: any;
}

export default function TriageDashboard() {
  const {
    isRecording,
    transcript: liveTranscript,
    interimText,
    startRecording,
    stopRecording,
    resetTranscript,
  } = useWhisperASR();

  const [transcript, setTranscript] = useState<{speaker: string, text: string}[]>([]);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisResult, setAnalysisResult] = useState<any>(null);
  const [syncStatus, setSyncStatus] = useState<'idle' | 'syncing' | 'success'>('idle');


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

  const handleSaveSession = () => {
    if (!analysisResult) return;
    const newSession: TriageSession = {
      id: Date.now().toString(),
      date: new Date().toISOString(),
      patientName: analysisResult.entities?.patientName || 'Paciente Desconocido',
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
    if (isRecording) {
      setTranscript(liveTranscript);
    }
  }, [isRecording, liveTranscript]);

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
    } catch (err) {
      console.error(err);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleToggleRecording = () => {
    if (isRecording) {
      stopRecording();
      // Esperamos un momento para que el último chunk de audio sea enviado y transcrito
      setTimeout(() => {
        setTranscript(prev => {
          if (prev.length > 0) {
            handleAnalyze(prev);
          } else {
            toast.error("No se detectó audio transcrito. Intente de nuevo.");
          }
          return prev;
        });
      }, 800);
    } else {
      setTranscript([]);
      resetTranscript();
      setAnalysisResult(null);
      setSyncStatus('idle');
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
      const fhirPayload = {
        resourceType: "Encounter",
        status: "arrived",
        class: { system: "http://terminology.hl7.org/CodeSystem/v3-ActCode", code: "EMER" },
        priority: {
            coding: [{ system: "http://terminology.hl7.org/CodeSystem/v3-ObservationValue", code: `L${analysisResult.triage?.level}` }]
        },
        reasonCode: analysisResult.entities?.symptoms?.map((s: string) => ({ text: s }))
      };
      
      const res = await fetch('/api/fhir', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(fhirPayload)
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
            <span className={`text-xs font-mono uppercase ${isRecording ? 'text-red-500' : 'text-emerald-500'} hidden sm:inline`}>{isRecording ? 'REC LIVE' : 'ASR ACTIVE'}</span>
          </div>
          <div className="px-3 py-1 bg-slate-700 rounded text-[10px] sm:text-xs font-medium text-slate-300 truncate max-w-[120px] sm:max-w-none">
            User: Dr. Rodriguez
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
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-3 lg:gap-4 h-full min-h-0 overflow-y-auto lg:overflow-hidden pr-1 lg:pr-0">
          
          {/* Left Column: ASR Module */}
          <section className="lg:col-span-5 flex flex-col gap-3 lg:gap-4 min-h-[400px] lg:min-h-0">
            <div className="flex-1 bg-slate-800/50 rounded-lg border border-slate-700 p-4 flex flex-col overflow-hidden">
              <div className="flex justify-between items-center mb-3 shrink-0">
                <h3 className="text-[10px] sm:text-xs font-bold uppercase text-slate-400 tracking-widest flex items-center gap-2">
                  <Mic className="w-4 h-4 text-blue-400" />
                  Transcripción ASR
                </h3>
                <button
                  onClick={handleToggleRecording}
                  disabled={isAnalyzing}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded text-[9px] sm:text-[10px] font-bold uppercase tracking-widest transition-all ${
                    isRecording 
                    ? 'bg-red-500/20 text-red-400 border border-red-500/50 hover:bg-red-500/30' 
                    : 'bg-slate-700 text-slate-300 border border-slate-600 hover:bg-slate-600'
                  } disabled:opacity-50 disabled:cursor-not-allowed`}
                >
                  {isRecording ? <Square className="w-3 h-3 fill-current" /> : <Mic className="w-3 h-3" />}
                  {isRecording ? 'STOP REC' : 'START REC'}
                </button>
              </div>
              
              <div className="flex-1 overflow-y-auto space-y-3 pr-2 scrollbar-thin scrollbar-thumb-slate-700">
                {transcript.length === 0 && !isRecording && (
                    <div className="h-full flex flex-col items-center justify-center text-slate-500 text-xs font-mono uppercase tracking-widest text-center border-2 border-dashed border-slate-700 rounded-lg p-6">
                        <Mic className="w-6 h-6 mb-2 opacity-30" />
                        Awaiting Audio Input...
                    </div>
                )}
                <AnimatePresence>
                  {transcript.map((line, i) => (
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
                  ))}
                  {interimText && (
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
          </section>

          {/* Right Column: NLP & Triage */}
          <section className="lg:col-span-7 flex flex-col gap-3 lg:gap-4 min-h-0">
            
            {/* NER Module */}
            <div className="flex-[0.6] bg-slate-800/50 rounded-lg border border-slate-700 p-4 flex flex-col overflow-hidden">
              <div className="flex justify-between items-center shrink-0 mb-3">
                <h3 className="text-[10px] sm:text-xs font-bold uppercase text-slate-400 tracking-widest flex items-center gap-2">
                  <Activity className="w-4 h-4 text-emerald-400" />
                  Entidades Clínicas (NER)
                </h3>
                {isAnalyzing && <span className="text-[9px] sm:text-[10px] font-mono text-emerald-400/80 animate-pulse flex items-center gap-1"><Activity className="w-3 h-3"/> Parsing...</span>}
              </div>

              <div className="flex-1 overflow-y-auto grid grid-cols-1 md:grid-cols-2 gap-3 pr-1 scrollbar-thin scrollbar-thumb-slate-700">
                <EntityGroup title="Síntomas" icon={<AlertTriangle className="w-3 h-3"/>} color="text-red-400" bg="bg-red-500" border="border-red-500" entities={analysisResult?.entities?.symptoms} loading={isAnalyzing} />
                <EntityGroup title="Antecedentes" icon={<FileText className="w-3 h-3"/>} color="text-amber-400" bg="bg-amber-500" border="border-amber-500" entities={analysisResult?.entities?.history} loading={isAnalyzing} />
                <EntityGroup title="Medicamentos" icon={<Pill className="w-3 h-3"/>} color="text-blue-400" bg="bg-blue-500" border="border-blue-500" entities={analysisResult?.entities?.medications} loading={isAnalyzing} />
                <EntityGroup title="Signos/Vítales" icon={<Thermometer className="w-3 h-3"/>} color="text-emerald-400" bg="bg-emerald-500" border="border-emerald-500" entities={analysisResult?.entities?.vitals} loading={isAnalyzing} />
              </div>
            </div>

            {/* Triage Output */}
            <div className="flex-[0.4] min-h-[200px] bg-slate-800/50 rounded-lg border border-slate-700 p-4 flex flex-col gap-3 overflow-y-auto shrink-0 scrollbar-thin scrollbar-thumb-slate-700">
                <h2 className="text-[10px] sm:text-xs font-bold uppercase text-slate-400 tracking-widest flex items-center gap-2 mb-1 shrink-0">
                  <ShieldAlert className="w-4 h-4 text-orange-400" />
                  Intelligent Triage Engine
                </h2>

                {!analysisResult && !isAnalyzing ? (
                  <div className="flex-1 flex flex-col items-center justify-center text-slate-500 text-[10px] sm:text-xs font-mono uppercase tracking-widest border border-dashed border-slate-700 rounded p-4 text-center">
                    Awaiting consultation data...
                  </div>
                ) : isAnalyzing ? (
                  <div className="flex-1 flex flex-col items-center justify-center text-slate-400 text-[10px] sm:text-xs font-mono uppercase tracking-widest gap-3 py-4">
                     <div className="w-5 h-5 rounded-full border-2 border-t-blue-500 border-slate-700 animate-spin" />
                     Calculating Severity...
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
                 <span className="truncate">Status: {syncStatus === 'success' ? 'Guardado Exitoso' : 'Waiting'}</span>
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
                   {syncStatus === 'success' ? 'SYNCED' : syncStatus === 'syncing' ? 'SYNCING...' : 'SYNC FHIR R4'}
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

function EntityGroup({title, icon, color, bg, border, entities, loading}: {title: string, icon: React.ReactNode, color: string, bg: string, border: string, entities?: string[], loading: boolean}) {
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
          </div>
        ))}
        {!loading && entities?.length === 0 && <span className="text-[10px] text-slate-500 uppercase px-2 py-1 font-mono tracking-wider">No detectado</span>}
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
