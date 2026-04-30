'use client'

import { useState, useCallback, useRef, useEffect } from 'react'

interface UseVoiceRecordingOptions {
  onTranscription?: (text: string, isFinal: boolean) => void
  language?: string
}

interface UseVoiceRecordingReturn {
  isRecording: boolean
  isSupported: boolean
  isPaused: boolean
  interimTranscript: string
  startRecording: () => void
  stopRecording: () => void
  pauseRecording: () => void
  resumeRecording: () => void
  error: string | null
}

export function useVoiceRecording({
  onTranscription,
  language = 'es-ES'
}: UseVoiceRecordingOptions = {}): UseVoiceRecordingReturn {
  const [isRecording, setIsRecording] = useState(false)
  const [isPaused, setIsPaused] = useState(false)
  const [interimTranscript, setInterimTranscript] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isSupported, setIsSupported] = useState(false)
  
  const recognitionRef = useRef<SpeechRecognition | null>(null)
  const onTranscriptionRef = useRef(onTranscription)
  const isRecordingRef = useRef(false)
  const isPausedRef = useRef(false)
  const shouldRestartRef = useRef(false)

  // Keep refs in sync with state
  useEffect(() => {
    onTranscriptionRef.current = onTranscription
  }, [onTranscription])

  useEffect(() => {
    isRecordingRef.current = isRecording
  }, [isRecording])

  useEffect(() => {
    isPausedRef.current = isPaused
  }, [isPaused])

  // Initialize speech recognition once
  useEffect(() => {
    const SpeechRecognitionAPI = window.SpeechRecognition || window.webkitSpeechRecognition
    
    if (!SpeechRecognitionAPI) {
      setIsSupported(false)
      return
    }

    setIsSupported(true)

    const recognition = new SpeechRecognitionAPI()
    recognition.continuous = true
    recognition.interimResults = true
    recognition.lang = language
    recognition.maxAlternatives = 1

    recognition.onstart = () => {
      setError(null)
    }

    recognition.onresult = (event) => {
      let interim = ''
      let final = ''
      
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const transcript = event.results[i][0].transcript
        
        if (event.results[i].isFinal) {
          final += transcript
        } else {
          interim += transcript
        }
      }
      
      setInterimTranscript(interim)
      
      if (final && onTranscriptionRef.current) {
        onTranscriptionRef.current(final, true)
      }
    }

    recognition.onerror = (event) => {
      if (event.error === 'not-allowed') {
        setError('Permiso de micrófono denegado. Por favor, habilite el acceso al micrófono.')
        setIsRecording(false)
        isRecordingRef.current = false
      } else if (event.error === 'no-speech') {
        // Common error, just restart if still recording
      } else if (event.error === 'aborted') {
        // Ignore aborted errors when stopping
      } else if (event.error === 'network') {
        setError('Error de red. Verifique su conexión a internet.')
      } else {
        setError(`Error de reconocimiento: ${event.error}`)
      }
    }

    recognition.onend = () => {
      // Auto-restart if still recording and not paused
      if (isRecordingRef.current && !isPausedRef.current && shouldRestartRef.current) {
        setTimeout(() => {
          if (isRecordingRef.current && !isPausedRef.current && recognitionRef.current) {
            try {
              recognitionRef.current.start()
            } catch {
              // Ignore
            }
          }
        }, 100)
      }
    }

    recognitionRef.current = recognition

    return () => {
      shouldRestartRef.current = false
      if (recognitionRef.current) {
        try {
          recognitionRef.current.stop()
        } catch {
          // Ignore
        }
      }
    }
  }, [language])

  const startRecording = useCallback(() => {
    if (!recognitionRef.current) {
      setError('El reconocimiento de voz no está disponible en este navegador.')
      return
    }
    
    setError(null)
    setInterimTranscript('')
    setIsRecording(true)
    setIsPaused(false)
    isRecordingRef.current = true
    isPausedRef.current = false
    shouldRestartRef.current = true
    
    try {
      recognitionRef.current.start()
    } catch {
      // May already be running, try stopping and restarting
      try {
        recognitionRef.current.stop()
        setTimeout(() => {
          if (recognitionRef.current && isRecordingRef.current) {
            recognitionRef.current.start()
          }
        }, 100)
      } catch {
        // Ignore
      }
    }
  }, [])

  const stopRecording = useCallback(() => {
    shouldRestartRef.current = false
    isRecordingRef.current = false
    isPausedRef.current = false
    
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop()
      } catch {
        // Ignore
      }
    }
    
    setIsRecording(false)
    setIsPaused(false)
    setInterimTranscript('')
  }, [])

  const pauseRecording = useCallback(() => {
    shouldRestartRef.current = false
    isPausedRef.current = true
    
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop()
      } catch {
        // Ignore
      }
    }
    setIsPaused(true)
  }, [])

  const resumeRecording = useCallback(() => {
    isPausedRef.current = false
    shouldRestartRef.current = true
    setIsPaused(false)
    
    if (recognitionRef.current && isRecordingRef.current) {
      try {
        recognitionRef.current.start()
      } catch {
        // May already be running
      }
    }
  }, [])

  return {
    isRecording,
    isSupported,
    isPaused,
    interimTranscript,
    startRecording,
    stopRecording,
    pauseRecording,
    resumeRecording,
    error
  }
}

// Type declarations for Web Speech API
declare global {
  interface Window {
    SpeechRecognition: typeof SpeechRecognition
    webkitSpeechRecognition: typeof SpeechRecognition
  }
}
