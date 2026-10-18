import { useState, useRef, useEffect, useCallback } from 'react';
import { fetchWithAuth } from '@/lib/api';

interface UseWhisperASRReturn {
  isRecording: boolean;
  isPaused: boolean;
  transcript: { speaker: string; text: string }[];
  interimText: string;
  startRecording: () => Promise<void>;
  stopRecording: () => void;
  pauseRecording: () => void;
  resumeRecording: () => void;
  abortTranscription: () => void;
  resetTranscript: () => void;
  sessionId: string;
  isTranscribing: boolean;
  asrError: string | null;
  clearAsrError: () => void;
  // Retraso de la transcripcion: segundos entre el fin de un fragmento y la llegada de su texto,
  // y fragmentos que aun esperan turno. En CPU el modelo puede tardar mas que el propio audio.
  asrLagSeconds: number;
  pendingChunks: number;
}

interface QueuedChunk {
  blob: Blob;
  recordedAt: number;
}

export function useWhisperASR(): UseWhisperASRReturn {
  const [isRecording, setIsRecording] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [transcript, setTranscript] = useState<{ speaker: string; text: string }[]>([]);
  const [interimText, setInterimText] = useState('');
  const [sessionId, setSessionId] = useState('');
  const [asrError, setAsrError] = useState<string | null>(null);
  const [asrLagSeconds, setAsrLagSeconds] = useState(0);
  const [pendingChunks, setPendingChunks] = useState(0);

  const clearAsrError = useCallback(() => {
    setAsrError(null);
  }, []);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);
  const audioChunksQueueRef = useRef<QueuedChunk[]>([]);
  const isProcessingQueueRef = useRef(false);
  const sessionIdRef = useRef<string>('');
  const isStoppingRef = useRef(false);
  const onStopFiredRef = useRef(false);

  // FIFO Audio processing queue
  const processQueue = useCallback(async () => {
    if (isProcessingQueueRef.current) {
      return;
    }
    if (audioChunksQueueRef.current.length === 0) {
      if (isStoppingRef.current) {
        if (onStopFiredRef.current) {
          setIsTranscribing(false);
          isStoppingRef.current = false;
        }
      } else {
        setIsTranscribing(false);
      }
      return;
    }

    isProcessingQueueRef.current = true;
    setIsTranscribing(true);
    const currentSessionId = sessionIdRef.current;

    while (audioChunksQueueRef.current.length > 0) {
      const chunk = audioChunksQueueRef.current.shift();
      setPendingChunks(audioChunksQueueRef.current.length);
      const audioBlob = chunk?.blob;
      if (!chunk || !audioBlob || audioBlob.size === 0) continue;

      setInterimText('Procesando audio...');

      try {
        const formData = new FormData();
        // Convert blob to wav file name for backend validation compat
        const audioFile = new File([audioBlob], `chunk-${Date.now()}.webm`, { type: audioBlob.type });
        formData.append('audio', audioFile);
        formData.append('session_id', currentSessionId);

        const response = await fetchWithAuth('/api/transcribe', {
          method: 'POST',
          body: formData,
        });

        if (!response.ok) {
          let errorMsg = `Error en el servicio de transcripción (HTTP ${response.status})`;
          try {
            const errData = await response.json();
            if (errData && errData.error) {
              errorMsg = errData.error;
            }
          } catch {
            // keep default errorMsg
          }
          if (response.status === 503 || errorMsg.toLowerCase().includes('whisper')) {
            errorMsg = 'El motor de transcripción Faster-Whisper no pudo iniciar o está temporalmente no disponible.';
          }
          setAsrError(errorMsg);
          throw new Error(errorMsg);
        }

        const data = await response.json();
        setAsrLagSeconds((Date.now() - chunk.recordedAt) / 1000);
        
        if (data && data.text && data.text.trim()) {
          const formattedText = data.text.trim();
          setTranscript(prev => [...prev, { speaker: 'Usuario', text: formattedText }]);
        }
      } catch (error: any) {
        console.error('Error sending audio chunk to ASR backend:', error);
      } finally {
        setInterimText('');
      }
    }

    isProcessingQueueRef.current = false;
    if (isStoppingRef.current) {
      if (onStopFiredRef.current && audioChunksQueueRef.current.length === 0) {
        setIsTranscribing(false);
        isStoppingRef.current = false;
      }
    } else {
      setIsTranscribing(false);
    }
  }, []);

  const startRecording = useCallback(async () => {
    try {
      // Clear queue and states
      audioChunksQueueRef.current = [];
      isProcessingQueueRef.current = false;
      setAsrLagSeconds(0);
      setPendingChunks(0);
      setTranscript([]);
      setInterimText('');
      setIsPaused(false);
      isStoppingRef.current = false;
      onStopFiredRef.current = false;

      // Generate a new Session ID
      const newSessionId = typeof crypto.randomUUID === 'function' 
        ? crypto.randomUUID() 
        : Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15);
      
      setSessionId(newSessionId);
      sessionIdRef.current = newSessionId;

      // Get user audio stream
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      // Check supported formats
      let options = { mimeType: 'audio/webm;codecs=opus' };
      if (!MediaRecorder.isTypeSupported(options.mimeType)) {
        options = { mimeType: 'audio/webm' };
      }
      if (!MediaRecorder.isTypeSupported(options.mimeType)) {
        // Fallback to default
        mediaRecorderRef.current = new MediaRecorder(stream);
      } else {
        mediaRecorderRef.current = new MediaRecorder(stream, options);
      }

      mediaRecorderRef.current.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) {
          audioChunksQueueRef.current.push({ blob: event.data, recordedAt: Date.now() });
          setPendingChunks(audioChunksQueueRef.current.length);
          processQueue();
        }
      };

      mediaRecorderRef.current.onstop = () => {
        onStopFiredRef.current = true;
        processQueue();
      };

      // Start recorder (and capture audio dynamically)
      mediaRecorderRef.current.start();
      setIsRecording(true);

      // Setup chunk timer (every 4 seconds, cycle recorder to trigger dataavailable)
      intervalRef.current = setInterval(() => {
        if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
          // Stop and immediately restart creates a completed chunk
          mediaRecorderRef.current.stop();
          mediaRecorderRef.current.start();
        }
      }, 4000);

    } catch (error: any) {
      console.error('Failed to start MediaRecorder:', error);
      const msg = error.name === 'NotAllowedError'
        ? 'Acceso denegado: Por favor permite el acceso al micrófono en el navegador.'
        : `No se pudo iniciar la captura de audio: ${error.message || 'Error desconocido'}`;
      setAsrError(msg);
      setIsRecording(false);
      setIsPaused(false);
    }
  }, [processQueue]);

  const pauseRecording = useCallback(() => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
      mediaRecorderRef.current.pause();
      setIsPaused(true);
      setInterimText('Grabación en pausa...');
    }
  }, []);

  const resumeRecording = useCallback(() => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'paused') {
      mediaRecorderRef.current.resume();
      setIsPaused(false);
      setInterimText('');
    }
  }, []);

  const abortTranscription = useCallback(() => {
    audioChunksQueueRef.current = [];
    setPendingChunks(0);
    setIsTranscribing(false);
    isProcessingQueueRef.current = false;
    setInterimText('');
  }, []);

  const stopRecording = useCallback(() => {
    // Clear interval timer
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }

    isStoppingRef.current = true;
    setIsTranscribing(true); // Prevent race condition with useEffect in UI

    // Stop MediaRecorder
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
    } else {
      onStopFiredRef.current = true;
      processQueue();
    }

    // Stop audio tracks with a slight delay
    const activeStream = streamRef.current;
    setTimeout(() => {
      if (activeStream) {
        activeStream.getTracks().forEach(track => track.stop());
      }
    }, 500);

    streamRef.current = null;
    setIsRecording(false);
    setIsPaused(false);
    setInterimText('');
  }, [processQueue]);

  const resetTranscript = useCallback(() => {
    setTranscript([]);
    setInterimText('');
    setAsrError(null);
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
        mediaRecorderRef.current.stop();
      }
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(track => track.stop());
      }
    };
  }, []);

  return {
    isRecording,
    isPaused,
    transcript,
    interimText,
    startRecording,
    stopRecording,
    pauseRecording,
    resumeRecording,
    abortTranscription,
    resetTranscript,
    sessionId,
    isTranscribing,
    asrError,
    clearAsrError,
    asrLagSeconds,
    pendingChunks,
  };
}
