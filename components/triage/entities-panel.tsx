'use client'

import { 
  Activity, 
  Stethoscope, 
  Pill, 
  HeartPulse, 
  AlertTriangle, 
  FolderClock,
  Layers
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'
import type { ClinicalEntity, EntityType } from '@/lib/types'
import { ENTITY_CONFIG } from '@/lib/types'

interface EntitiesPanelProps {
  entities: ClinicalEntity[]
}

const ENTITY_ICONS: Record<EntityType, React.ReactNode> = {
  symptom: <Activity className="h-3.5 w-3.5" />,
  diagnosis: <Stethoscope className="h-3.5 w-3.5" />,
  medication: <Pill className="h-3.5 w-3.5" />,
  vital_sign: <HeartPulse className="h-3.5 w-3.5" />,
  allergy: <AlertTriangle className="h-3.5 w-3.5" />,
  medical_history: <FolderClock className="h-3.5 w-3.5" />
}

export function EntitiesPanel({ entities }: EntitiesPanelProps) {
  // Group entities by type
  const groupedEntities = entities.reduce((acc, entity) => {
    if (!acc[entity.type]) {
      acc[entity.type] = []
    }
    acc[entity.type].push(entity)
    return acc
  }, {} as Record<EntityType, ClinicalEntity[]>)

  const entityTypes: EntityType[] = [
    'symptom',
    'vital_sign',
    'diagnosis',
    'medication',
    'allergy',
    'medical_history'
  ]

  return (
    <Card className="flex h-full flex-col border-border bg-card">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base font-medium">
          <Layers className="h-4 w-4 text-primary" />
          Entidades Clínicas Extraídas
          {entities.length > 0 && (
            <Badge variant="secondary" className="ml-auto">
              {entities.length} entidades
            </Badge>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent className="flex-1 overflow-hidden p-0">
        <ScrollArea className="h-[300px] px-4 pb-4 sm:h-[350px] sm:px-6 lg:h-[400px]">
          {entities.length === 0 ? (
            <div className="flex h-full flex-col items-center justify-center py-12 text-center">
              <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-muted">
                <Layers className="h-8 w-8 text-muted-foreground" />
              </div>
              <p className="font-medium text-muted-foreground">
                Sin entidades detectadas
              </p>
              <p className="mt-1 max-w-sm text-sm text-muted-foreground/70">
                Las entidades clínicas se extraerán automáticamente durante la transcripción
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {entityTypes.map((type) => {
                const typeEntities = groupedEntities[type]
                if (!typeEntities || typeEntities.length === 0) return null

                return (
                  <div key={type}>
                    <div className="mb-2 flex items-center gap-2">
                      <div 
                        className={cn(
                          "flex h-6 w-6 items-center justify-center rounded",
                          ENTITY_CONFIG[type].color
                        )}
                      >
                        {ENTITY_ICONS[type]}
                      </div>
                      <span className="text-sm font-medium text-foreground">
                        {ENTITY_CONFIG[type].label}s
                      </span>
                      <Badge variant="outline" className="ml-auto text-xs">
                        {typeEntities.length}
                      </Badge>
                    </div>
                    <div className="ml-8 flex flex-wrap gap-2">
                      {typeEntities.map((entity) => (
                        <Badge
                          key={entity.id}
                          variant="outline"
                          className={cn(
                            "cursor-default transition-colors hover:opacity-80",
                            ENTITY_CONFIG[entity.type].color
                          )}
                        >
                          <span>{entity.text}</span>
                          {entity.normalizedText && entity.normalizedText !== entity.text && (
                            <span className="ml-1.5 opacity-70">
                              ({entity.normalizedText})
                            </span>
                          )}
                          {entity.code && (
                            <span className="ml-1.5 font-mono text-[10px] opacity-60">
                              [{entity.code}]
                            </span>
                          )}
                        </Badge>
                      ))}
                    </div>
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
