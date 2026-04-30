'use client'

import { useState, useCallback, useEffect, useRef } from 'react'
import { Header } from './header'
import { VoiceRecorder } from './voice-recorder'
import { TranscriptionPanel } from './transcription-panel'
import { EntitiesPanel } from './entities-panel'
import { TriageResult } from './triage-result'
import { PatientInfoForm } from './patient-info'
import { FHIRExport } from './fhir-export'
import { SessionHistory } from './session-history'
import { useVoiceRecording } from '@/hooks/use-voice-recording'
import type { 
  TriageSession, 
  PatientInfo, 
  TranscriptionSegment, 
  ClinicalEntity,
  TriagePriority 
} from '@/lib/types'

function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
}

function createNewSession(): TriageSession {
  return {
    id: generateId(),
    patient: { id: generateId() },
    startTime: new Date(),
    transcription: [],
    entities: [],
    status: 'recording'
  }
}

export function TriageContainer() {
  const [session, setSession] = useState<TriageSession>(createNewSession())
  const [sessions, setSessions] = useState<TriageSession[]>([])
  const [isProcessing, setIsProcessing] = useState(false)
  const [duration, setDuration] = useState(0)
  const speakerToggleRef = useRef<'doctor' | 'patient'>('patient')
  const durationIntervalRef = useRef<NodeJS.Timeout | null>(null)

  const handleTranscription = useCallback((text: string, isFinal: boolean) => {
    console.log('[v0] handleTranscription called:', { text, isFinal })
    if (isFinal && text.trim()) {
      const newSegment: TranscriptionSegment = {
        id: generateId(),
        speaker: speakerToggleRef.current,
        text: text.trim(),
        timestamp: new Date(),
        entities: []
      }
      
      console.log('[v0] Adding new segment:', newSegment)
      
      setSession(prev => ({
        ...prev,
        transcription: [...prev.transcription, newSegment]
      }))

      // Toggle speaker for next segment
      speakerToggleRef.current = speakerToggleRef.current === 'doctor' ? 'patient' : 'doctor'
    }
  }, [])

  const {
    isRecording,
    isPaused,
    isSupported,
    interimTranscript,
    startRecording,
    stopRecording,
    pauseRecording,
    resumeRecording,
    error
  } = useVoiceRecording({
    onTranscription: handleTranscription,
    language: 'es-ES'
  })

  // Duration timer
  useEffect(() => {
    if (isRecording && !isPaused) {
      durationIntervalRef.current = setInterval(() => {
        setDuration(prev => prev + 1)
      }, 1000)
    } else if (durationIntervalRef.current) {
      clearInterval(durationIntervalRef.current)
    }

    return () => {
      if (durationIntervalRef.current) {
        clearInterval(durationIntervalRef.current)
      }
    }
  }, [isRecording, isPaused])

  const handleStart = useCallback(() => {
    console.log('[v0] handleStart called')
    setDuration(0)
    speakerToggleRef.current = 'patient'
    setSession(prev => ({ ...prev, status: 'recording', transcription: [], entities: [] }))
    startRecording()
  }, [startRecording])

  const handleStop = useCallback(async () => {
    console.log('[v0] handleStop called')
    stopRecording()
    
    if (session.transcription.length === 0) {
      console.log('[v0] No transcription segments to process')
      return
    }

    setIsProcessing(true)
    setSession(prev => ({ ...prev, status: 'processing' }))

    try {
      console.log('[v0] Sending triage request with:', session.transcription)
      const response = await fetch('/api/triage', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          transcription: session.transcription,
          patientInfo: session.patient
        })
      })

      if (!response.ok) {
        throw new Error('Failed to process triage')
      }

      const data = await response.json()
      console.log('[v0] Triage response:', data)

      setSession(prev => ({
        ...prev,
        triagePriority: data.triagePriority as TriagePriority,
        chiefComplaint: data.chiefComplaint,
        reasoning: data.reasoning,
        entities: data.entities as ClinicalEntity[],
        endTime: new Date(),
        status: 'completed'
      }))

      // Update transcription segments with entities
      setSession(prev => {
        const updatedTranscription = prev.transcription.map(segment => {
          const segmentEntities = data.entities.filter((entity: ClinicalEntity) => 
            segment.text.toLowerCase().includes(entity.text.toLowerCase())
          )
          return { ...segment, entities: segmentEntities }
        })
        return { ...prev, transcription: updatedTranscription }
      })

    } catch (error) {
      console.error('[v0] Triage processing error:', error)
      setSession(prev => ({ ...prev, status: 'recording' }))
    } finally {
      setIsProcessing(false)
    }
  }, [stopRecording, session.transcription, session.patient])

  const handlePatientUpdate = useCallback((patient: PatientInfo) => {
    setSession(prev => ({ ...prev, patient }))
  }, [])

  const handleNewSession = useCallback(() => {
    // Save current session if it has data
    if (session.transcription.length > 0) {
      setSessions(prev => [session, ...prev])
    }
    setSession(createNewSession())
    setDuration(0)
  }, [session])

  const handleSelectSession = useCallback((selectedSession: TriageSession) => {
    // Save current session if it has data and is different
    if (session.id !== selectedSession.id && session.transcription.length > 0) {
      setSessions(prev => {
        const filtered = prev.filter(s => s.id !== session.id)
        return [session, ...filtered]
      })
    }
    setSession(selectedSession)
    setSessions(prev => prev.filter(s => s.id !== selectedSession.id))
  }, [session])

  const handleDeleteSession = useCallback((sessionId: string) => {
    setSessions(prev => prev.filter(s => s.id !== sessionId))
  }, [])

  return (
    <div className="flex min-h-screen flex-col bg-background">
      <Header />
      
      <main className="flex-1 px-4 py-6 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-7xl">
          <div className="mb-6">
            <h2 className="text-xl font-semibold text-foreground sm:text-2xl">
              Triaje Médico Automatizado
            </h2>
            <p className="mt-1 text-sm text-muted-foreground sm:text-base">
              Capture la conversación médico-paciente para generar una clasificación de triaje automática
            </p>
          </div>

          {/* Mobile: Stack all sections vertically */}
          {/* Desktop: 3 column grid */}
          <div className="grid gap-6 lg:grid-cols-3">
            {/* Left Column - Recording and Patient Info */}
            <div className="flex flex-col gap-6">
              <PatientInfoForm 
                patient={session.patient}
                onUpdate={handlePatientUpdate}
                disabled={isRecording || isProcessing}
              />
              <VoiceRecorder
                isRecording={isRecording}
                isPaused={isPaused}
                isSupported={isSupported}
                interimTranscript={interimTranscript}
                error={error}
                onStart={handleStart}
                onStop={handleStop}
                onPause={pauseRecording}
                onResume={resumeRecording}
                duration={duration}
              />
              <SessionHistory
                sessions={sessions}
                currentSessionId={session.id}
                onSelectSession={handleSelectSession}
                onDeleteSession={handleDeleteSession}
                onNewSession={handleNewSession}
              />
            </div>

            {/* Middle Column - Transcription and Entities */}
            <div className="flex flex-col gap-6">
              <TranscriptionPanel segments={session.transcription} />
              <EntitiesPanel entities={session.entities} />
            </div>

            {/* Right Column - Triage Result and Export */}
            <div className="flex flex-col gap-6">
              <TriageResult
                priority={session.triagePriority || null}
                reasoning={session.reasoning || null}
                chiefComplaint={session.chiefComplaint || null}
                isProcessing={isProcessing}
                entities={session.entities}
              />
              <FHIRExport 
                session={session.status === 'completed' ? session : null} 
              />
            </div>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-border bg-card px-4 py-4 sm:px-6">
        <div className="mx-auto flex max-w-7xl flex-col items-center gap-2 text-center sm:flex-row sm:justify-between sm:text-left">
          <p className="text-xs text-muted-foreground">
            AI-TRIAGE v1.0 - Universidad del Valle
          </p>
          <p className="text-xs text-muted-foreground">
            Este sistema es una herramienta de apoyo y no sustituye el juicio clínico profesional
          </p>
        </div>
      </footer>
    </div>
  )
}
