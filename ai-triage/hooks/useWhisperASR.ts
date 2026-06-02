import { useState, useRef, useEffect, useCallback } from 'react';

interface UseWhisperASRReturn {
  isRecording: boolean;
  transcript: { speaker: string; text: string }[];
  interimText: string;
  startRecording: () => Promise<void>;
  stopRecording: () => void;
  resetTranscript: () => void;
  sessionId: string;
}

export function useWhisperASR(): UseWhisperASRReturn {
  const [isRecording, setIsRecording] = useState(false);
  const [transcript, setTranscript] = useState<{ speaker: string; text: string }[]>([]);
  const [interimText, setInterimText] = useState('');
  const [sessionId, setSessionId] = useState('');

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);
  const audioChunksQueueRef = useRef<Blob[]>([]);
  const isProcessingQueueRef = useRef(false);
  const sessionIdRef = useRef<string>('');

  // FIFO Audio processing queue
  const processQueue = useCallback(async () => {
    if (isProcessingQueueRef.current || audioChunksQueueRef.current.length === 0) {
      return;
    }

    isProcessingQueueRef.current = true;
    const currentSessionId = sessionIdRef.current;

    while (audioChunksQueueRef.current.length > 0) {
      const audioBlob = audioChunksQueueRef.current.shift();
      if (!audioBlob || audioBlob.size === 0) continue;

      setInterimText('Procesando audio...');

      try {
        const formData = new FormData();
        // Convert blob to wav file name for backend validation compat
        const audioFile = new File([audioBlob], `chunk-${Date.now()}.webm`, { type: audioBlob.type });
        formData.append('audio', audioFile);
        formData.append('session_id', currentSessionId);

        const response = await fetch('/api/transcribe', {
          method: 'POST',
          body: formData,
        });

        if (!response.ok) {
          throw new Error(`ASR response error: ${response.statusText}`);
        }

        const data = await response.json();
        
        if (data && data.text && data.text.trim()) {
          const formattedText = data.text.trim();
          setTranscript(prev => [...prev, { speaker: 'Usuario', text: formattedText }]);
        }
      } catch (error) {
        console.error('Error sending audio chunk to ASR backend:', error);
      } finally {
        setInterimText('');
      }
    }

    isProcessingQueueRef.current = false;
  }, []);

  const startRecording = useCallback(async () => {
    try {
      // Clear queue and states
      audioChunksQueueRef.current = [];
      isProcessingQueueRef.current = false;
      setTranscript([]);
      setInterimText('');

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
          audioChunksQueueRef.current.push(event.data);
          processQueue();
        }
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

    } catch (error) {
      console.error('Failed to start MediaRecorder:', error);
      alert('No se pudo acceder al micrófono. Por favor verifica los permisos.');
      setIsRecording(false);
    }
  }, [processQueue]);

  const stopRecording = useCallback(() => {
    // Clear interval timer
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }

    // Stop MediaRecorder
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
    }

    // Stop audio tracks
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
    }

    setIsRecording(false);
    setInterimText('');

    // Call reset endpoint to clear backend session context cleanly after brief delay
    const currentSessionId = sessionIdRef.current;
    if (currentSessionId) {
      fetch('/api/transcribe/reset', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: currentSessionId }),
      }).catch(err => console.error('Error resetting backend session:', err));
    }
  }, []);

  const resetTranscript = useCallback(() => {
    setTranscript([]);
    setInterimText('');
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
    transcript,
    interimText,
    startRecording,
    stopRecording,
    resetTranscript,
    sessionId,
  };
}
