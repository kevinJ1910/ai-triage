'use client'

import { AlertCircle, Clock, Sparkles, ChevronDown, ChevronUp } from 'lucide-react'
import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import type { TriagePriority, ClinicalEntity } from '@/lib/types'
import { TRIAGE_LEVELS, ENTITY_CONFIG } from '@/lib/types'

interface TriageResultProps {
  priority: TriagePriority | null
  reasoning: string | null
  chiefComplaint: string | null
  isProcessing: boolean
  entities: ClinicalEntity[]
}

export function TriageResult({
  priority,
  reasoning,
  chiefComplaint,
  isProcessing,
  entities
}: TriageResultProps) {
  const [showDetails, setShowDetails] = useState(false)
  const level = priority ? TRIAGE_LEVELS[priority] : null

  // Count entities by type for summary
  const entityCounts = entities.reduce((acc, entity) => {
    acc[entity.type] = (acc[entity.type] || 0) + 1
    return acc
  }, {} as Record<string, number>)

  return (
    <Card className="border-border bg-card">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base font-medium">
          <Sparkles className="h-4 w-4 text-primary" />
          Resultado del Triaje
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {isProcessing ? (
          <div className="flex flex-col items-center justify-center py-8">
            <div className="mb-4 h-12 w-12 animate-spin rounded-full border-4 border-primary border-t-transparent" />
            <p className="text-sm font-medium text-foreground">Analizando información clínica...</p>
            <p className="text-xs text-muted-foreground">
              Extrayendo entidades y calculando prioridad
            </p>
          </div>
        ) : priority && level ? (
          <>
            {/* Priority Level Display */}
            <div className={cn("rounded-lg p-4 text-center", level.color)}>
              <div className="mb-2 text-4xl font-bold">Nivel {priority}</div>
              <div className="text-xl font-semibold">{level.name}</div>
              <div className="mt-1 text-sm opacity-90">{level.description}</div>
            </div>

            {/* Wait Time */}
            <div className="flex items-center justify-center gap-2 rounded-lg bg-secondary/50 p-3">
              <Clock className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm text-muted-foreground">
                Tiempo máximo de espera: <strong className="text-foreground">{level.maxWaitTime}</strong>
              </span>
            </div>

            {/* Chief Complaint */}
            {chiefComplaint && (
              <div className="rounded-lg border border-border p-3">
                <p className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Motivo de Consulta Principal
                </p>
                <p className="text-sm text-foreground">{chiefComplaint}</p>
              </div>
            )}

            {/* Entity Summary */}
            {Object.keys(entityCounts).length > 0 && (
              <div className="rounded-lg border border-border p-3">
                <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Resumen de Entidades Detectadas
                </p>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(entityCounts).map(([type, count]) => (
                    <Badge 
                      key={type} 
                      variant="outline"
                      className={cn(
                        "text-xs",
                        ENTITY_CONFIG[type as keyof typeof ENTITY_CONFIG].color
                      )}
                    >
                      {count} {ENTITY_CONFIG[type as keyof typeof ENTITY_CONFIG].label}
                      {count > 1 ? 's' : ''}
                    </Badge>
                  ))}
                </div>
              </div>
            )}

            {/* AI Reasoning */}
            {reasoning && (
              <div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setShowDetails(!showDetails)}
                  className="mb-2 w-full justify-between"
                >
                  <span className="text-xs font-medium">Razonamiento del Sistema</span>
                  {showDetails ? (
                    <ChevronUp className="h-4 w-4" />
                  ) : (
                    <ChevronDown className="h-4 w-4" />
                  )}
                </Button>
                {showDetails && (
                  <div className="rounded-lg bg-muted/50 p-3">
                    <p className="text-xs leading-relaxed text-muted-foreground">
                      {reasoning}
                    </p>
                  </div>
                )}
              </div>
            )}

            {/* Disclaimer */}
            <div className="flex items-start gap-2 rounded-lg bg-destructive/5 p-3 text-xs text-destructive">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
              <p>
                Este resultado es una recomendación basada en IA y debe ser validado por 
                un profesional médico. No sustituye el juicio clínico.
              </p>
            </div>
          </>
        ) : (
          <div className="flex flex-col items-center justify-center py-8 text-center">
            <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-muted">
              <Sparkles className="h-8 w-8 text-muted-foreground" />
            </div>
            <p className="font-medium text-muted-foreground">
              Sin clasificación aún
            </p>
            <p className="mt-1 max-w-sm text-sm text-muted-foreground/70">
              Complete la grabación para obtener una clasificación de triaje automática
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
