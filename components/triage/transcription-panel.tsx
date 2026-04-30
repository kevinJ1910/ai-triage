'use client'

import { useRef, useEffect } from 'react'
import { FileText } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import type { TranscriptionSegment } from '@/lib/types'
import { ENTITY_CONFIG } from '@/lib/types'

interface TranscriptionPanelProps {
  segments: TranscriptionSegment[]
}

export function TranscriptionPanel({ segments }: TranscriptionPanelProps) {
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    // Auto-scroll to bottom when new segments arrive
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [segments])

  return (
    <Card className="flex h-full flex-col border-border bg-card">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base font-medium">
          <FileText className="h-4 w-4 text-primary" />
          Transcripción en Tiempo Real
          {segments.length > 0 && (
            <Badge variant="secondary" className="ml-auto">
              {segments.length} segmentos
            </Badge>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent className="flex-1 overflow-hidden p-0">
        <ScrollArea className="h-[300px] px-4 pb-4 sm:h-[350px] sm:px-6 lg:h-[400px]" ref={scrollRef}>
          {segments.length === 0 ? (
            <div className="flex h-full flex-col items-center justify-center py-12 text-center">
              <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-muted">
                <FileText className="h-8 w-8 text-muted-foreground" />
              </div>
              <p className="font-medium text-muted-foreground">
                Sin transcripción aún
              </p>
              <p className="mt-1 max-w-sm text-sm text-muted-foreground/70">
                Inicie la grabación para comenzar a transcribir la conversación médico-paciente
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {segments.map((segment) => (
                <div
                  key={segment.id}
                  className="flex gap-3 justify-start"
                >
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-muted">
                    <FileText className="h-4 w-4 text-muted-foreground" />
                  </div>
                  <div className="flex-1 rounded-lg px-4 py-3 bg-secondary/50 text-secondary-foreground">
                    <div className="mb-1 flex items-center gap-2">
                      <span className="text-xs font-medium">
                        Transcripción
                      </span>
                      <span className="text-xs text-muted-foreground">
                        {new Date(segment.timestamp).toLocaleTimeString('es-ES', {
                          hour: '2-digit',
                          minute: '2-digit',
                          second: '2-digit'
                        })}
                      </span>
                    </div>
                    <p className="text-sm leading-relaxed">{segment.text}</p>
                    {segment.entities.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1">
                        {segment.entities.map((entity) => (
                          <Badge
                            key={entity.id}
                            variant="outline"
                            className={cn(
                              "text-[10px] font-normal",
                              ENTITY_CONFIG[entity.type].color
                            )}
                          >
                            {entity.text}
                          </Badge>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </ScrollArea>
      </CardContent>
    </Card>
  )
}
