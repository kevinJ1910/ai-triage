'use client'

import { Clock, FileText, Trash2 } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'
import type { TriageSession } from '@/lib/types'
import { TRIAGE_LEVELS } from '@/lib/types'

interface SessionHistoryProps {
  sessions: TriageSession[]
  currentSessionId: string | null
  onSelectSession: (session: TriageSession) => void
  onDeleteSession: (sessionId: string) => void
  onNewSession: () => void
}

export function SessionHistory({
  sessions,
  currentSessionId,
  onSelectSession,
  onDeleteSession,
  onNewSession
}: SessionHistoryProps) {
  return (
    <Card className="flex h-full flex-col border-border bg-card">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-base font-medium">
            <Clock className="h-4 w-4 text-primary" />
            Historial de Sesiones
          </CardTitle>
          <Button size="sm" onClick={onNewSession}>
            Nueva Sesión
          </Button>
        </div>
      </CardHeader>
      <CardContent className="flex-1 overflow-hidden p-0">
        <ScrollArea className="h-[200px] px-4 pb-4 sm:h-[250px] lg:h-[300px]">
          {sessions.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-8 text-center">
              <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-muted">
                <FileText className="h-6 w-6 text-muted-foreground" />
              </div>
              <p className="text-sm text-muted-foreground">
                Sin sesiones anteriores
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              {sessions.map((session) => {
                const level = session.triagePriority 
                  ? TRIAGE_LEVELS[session.triagePriority] 
                  : null
                
                return (
                  <div
                    key={session.id}
                    className={cn(
                      "group flex cursor-pointer items-center gap-3 rounded-lg border p-3 transition-colors hover:bg-secondary/50",
                      currentSessionId === session.id 
                        ? "border-primary bg-primary/5" 
                        : "border-border"
                    )}
                    onClick={() => onSelectSession(session)}
                  >
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="truncate text-sm font-medium text-foreground">
                          {session.patient.name || 'Paciente sin nombre'}
                        </span>
                        {level && (
                          <Badge 
                            className={cn("shrink-0 text-[10px]", level.color)}
                          >
                            N{session.triagePriority}
                          </Badge>
                        )}
                      </div>
                      <div className="mt-1 flex items-center gap-2 text-xs text-muted-foreground">
                        <span>
                          {new Date(session.startTime).toLocaleDateString('es-ES', {
                            day: '2-digit',
                            month: 'short',
                            hour: '2-digit',
                            minute: '2-digit'
                          })}
                        </span>
                        <span className="text-muted-foreground/50">|</span>
                        <span>{session.transcription.length} segmentos</span>
                      </div>
                      {session.chiefComplaint && (
                        <p className="mt-1 truncate text-xs text-muted-foreground">
                          {session.chiefComplaint}
                        </p>
                      )}
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="shrink-0 opacity-0 transition-opacity group-hover:opacity-100"
                      onClick={(e) => {
                        e.stopPropagation()
                        onDeleteSession(session.id)
                      }}
                    >
                      <Trash2 className="h-4 w-4 text-muted-foreground hover:text-destructive" />
                    </Button>
                  </div>
                )
              })}
            </div>
          )}
        </ScrollArea>
      </CardContent>
    </Card>
  )
}
