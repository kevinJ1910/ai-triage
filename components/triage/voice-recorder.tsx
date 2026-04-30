'use client'

import { Mic, MicOff, Pause, Play, Square, AlertCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { cn } from '@/lib/utils'

interface VoiceRecorderProps {
  isRecording: boolean
  isPaused: boolean
  isSupported: boolean
  interimTranscript: string
  error: string | null
  onStart: () => void
  onStop: () => void
  onPause: () => void
  onResume: () => void
  duration: number
}

function formatDuration(seconds: number): string {
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
}

export function VoiceRecorder({
  isRecording,
  isPaused,
  isSupported,
  interimTranscript,
  error,
  onStart,
  onStop,
  onPause,
  onResume,
  duration
}: VoiceRecorderProps) {
  return (
    <Card className="border-border bg-card">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base font-medium">
          <Mic className="h-4 w-4 text-primary" />
          Captura de Voz
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Recording Status */}
        <div className="flex items-center justify-between rounded-lg bg-secondary/50 p-4">
          <div className="flex items-center gap-3">
            <div 
              className={cn(
                "flex h-12 w-12 items-center justify-center rounded-full transition-all",
                isRecording && !isPaused 
                  ? "bg-destructive animate-pulse-recording" 
                  : "bg-muted"
              )}
            >
              {isRecording && !isPaused ? (
                <Mic className="h-6 w-6 text-destructive-foreground" />
              ) : (
                <MicOff className="h-6 w-6 text-muted-foreground" />
              )}
            </div>
            <div>
              <p className="font-medium text-foreground">
                {!isRecording 
                  ? 'Listo para grabar' 
                  : isPaused 
                    ? 'Grabación pausada' 
                    : 'Grabando...'}
              </p>
              <p className="text-sm text-muted-foreground">
                {isRecording ? formatDuration(duration) : 'Inicie la grabación para comenzar'}
              </p>
            </div>
          </div>
          
          {/* Sound Wave Visualization */}
          {isRecording && !isPaused && (
            <div className="flex items-center gap-1">
              {[0, 1, 2, 3, 4].map((i) => (
                <div
                  key={i}
                  className={cn(
                    "w-1 rounded-full bg-primary",
                    i === 0 && "animate-soundwave",
                    i === 1 && "animate-soundwave-delay-1",
                    i === 2 && "animate-soundwave-delay-2",
                    i === 3 && "animate-soundwave-delay-3",
                    i === 4 && "animate-soundwave-delay-4"
                  )}
                  style={{ height: '8px' }}
                />
              ))}
            </div>
          )}
        </div>

        {/* Interim Transcript */}
        {isRecording && interimTranscript && (
          <div className="rounded-lg border border-dashed border-primary/30 bg-primary/5 p-3">
            <p className="text-sm italic text-muted-foreground">
              {interimTranscript}
            </p>
          </div>
        )}

        {/* Error Display */}
        {error && (
          <div className="flex items-center gap-2 rounded-lg bg-destructive/10 p-3 text-sm text-destructive">
            <AlertCircle className="h-4 w-4 shrink-0" />
            {error}
          </div>
        )}

        {/* Browser Support Warning */}
        {!isSupported && (
          <div className="flex items-center gap-2 rounded-lg bg-destructive/10 p-3 text-sm text-destructive">
            <AlertCircle className="h-4 w-4 shrink-0" />
            El reconocimiento de voz no está disponible en este navegador. Por favor, use Chrome o Edge.
          </div>
        )}

        {/* Controls */}
        <div className="flex items-center justify-center gap-3">
          {!isRecording ? (
            <Button
              onClick={onStart}
              disabled={!isSupported}
              size="lg"
              className="gap-2 bg-primary hover:bg-primary/90"
            >
              <Mic className="h-5 w-5" />
              Iniciar Grabación
            </Button>
          ) : (
            <>
              <Button
                onClick={isPaused ? onResume : onPause}
                variant="outline"
                size="icon"
                className="h-12 w-12 rounded-full"
              >
                {isPaused ? (
                  <Play className="h-5 w-5" />
                ) : (
                  <Pause className="h-5 w-5" />
                )}
              </Button>
              <Button
                onClick={onStop}
                variant="destructive"
                size="icon"
                className="h-12 w-12 rounded-full"
              >
                <Square className="h-5 w-5" />
              </Button>
            </>
          )}
        </div>

        {/* Instructions */}
        <p className="text-center text-xs text-muted-foreground">
          Hable claramente cerca del micrófono. El sistema transcribirá automáticamente 
          la conversación médico-paciente y extraerá las entidades clínicas relevantes.
        </p>
      </CardContent>
    </Card>
  )
}
