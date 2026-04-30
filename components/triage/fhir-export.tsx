'use client'

import { useState } from 'react'
import { Download, Copy, Check, FileJson, Send, ExternalLink } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import type { TriageSession, FHIREncounter, ClinicalEntity } from '@/lib/types'
import { TRIAGE_LEVELS } from '@/lib/types'

interface FHIRExportProps {
  session: TriageSession | null
}

function generateFHIREncounter(session: TriageSession): FHIREncounter {
  const priorityMapping = {
    1: { code: 'imm', display: 'Inmediato' },
    2: { code: 'emerg', display: 'Emergencia' },
    3: { code: 'urgent', display: 'Urgente' },
    4: { code: 'semi-urgent', display: 'Semi-urgente' },
    5: { code: 'non-urgent', display: 'No urgente' }
  }

  const priority = session.triagePriority 
    ? priorityMapping[session.triagePriority] 
    : undefined

  const reasonCodes = session.entities
    .filter(e => e.type === 'symptom' || e.type === 'diagnosis')
    .slice(0, 5)
    .map(entity => ({
      coding: [{
        system: entity.code?.startsWith('SNOMED') 
          ? 'http://snomed.info/sct' 
          : 'http://hl7.org/fhir/sid/icd-10',
        code: entity.code || 'unknown',
        display: entity.normalizedText || entity.text
      }],
      text: entity.text
    }))

  return {
    resourceType: 'Encounter',
    id: session.id,
    status: session.status === 'completed' ? 'finished' : 'in-progress',
    class: {
      system: 'http://terminology.hl7.org/CodeSystem/v3-ActCode',
      code: 'EMER',
      display: 'emergency'
    },
    priority: priority ? {
      coding: [{
        system: 'http://terminology.hl7.org/CodeSystem/v3-ActPriority',
        code: priority.code,
        display: priority.display
      }]
    } : undefined,
    subject: {
      reference: `Patient/${session.patient.id}`,
      display: session.patient.name
    },
    period: {
      start: session.startTime.toISOString(),
      end: session.endTime?.toISOString()
    },
    reasonCode: reasonCodes.length > 0 ? reasonCodes : undefined
  }
}

function generateHL7Message(session: TriageSession): string {
  const now = new Date()
  const dateStr = now.toISOString().replace(/[-:T]/g, '').slice(0, 14)
  
  const msh = `MSH|^~\\&|AI-TRIAGE|HOSPITAL|EHR|HOSPITAL|${dateStr}||ADT^A04|${session.id}|P|2.5`
  const pid = `PID|||${session.patient.documentId || ''}^^^||${session.patient.name?.replace(' ', '^') || ''}||${session.patient.gender || ''}||||||||||||||||||`
  const pv1 = `PV1||E|URGENCIAS|||||||||||||||${session.triagePriority || ''}|||||||||||||||||||||||||`
  
  const symptoms = session.entities
    .filter(e => e.type === 'symptom')
    .map((e, i) => `DG1|${i + 1}||${e.code || ''}|${e.text}|`)
    .join('\n')

  return [msh, pid, pv1, symptoms].filter(Boolean).join('\n')
}

export function FHIRExport({ session }: FHIRExportProps) {
  const [copied, setCopied] = useState<'fhir' | 'hl7' | null>(null)

  const handleCopy = async (content: string, type: 'fhir' | 'hl7') => {
    await navigator.clipboard.writeText(content)
    setCopied(type)
    setTimeout(() => setCopied(null), 2000)
  }

  const handleDownload = (content: string, filename: string, type: string) => {
    const blob = new Blob([content], { type })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  const fhirContent = session 
    ? JSON.stringify(generateFHIREncounter(session), null, 2) 
    : ''
  const hl7Content = session ? generateHL7Message(session) : ''

  return (
    <Card className="border-border bg-card">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base font-medium">
          <FileJson className="h-4 w-4 text-primary" />
          Exportar a Historia Clínica
          <div className="ml-auto flex gap-1">
            <Badge variant="outline" className="text-[10px]">FHIR R4</Badge>
            <Badge variant="outline" className="text-[10px]">HL7 v2.5</Badge>
          </div>
        </CardTitle>
      </CardHeader>
      <CardContent>
        {!session || session.status !== 'completed' ? (
          <div className="flex flex-col items-center justify-center py-8 text-center">
            <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-muted">
              <Send className="h-8 w-8 text-muted-foreground" />
            </div>
            <p className="font-medium text-muted-foreground">
              Sin datos para exportar
            </p>
            <p className="mt-1 max-w-sm text-sm text-muted-foreground/70">
              Complete el proceso de triaje para generar los documentos de interoperabilidad
            </p>
          </div>
        ) : (
          <Tabs defaultValue="fhir" className="w-full">
            <TabsList className="grid w-full grid-cols-2">
              <TabsTrigger value="fhir" className="gap-2">
                <FileJson className="h-3.5 w-3.5" />
                FHIR R4
              </TabsTrigger>
              <TabsTrigger value="hl7" className="gap-2">
                <FileJson className="h-3.5 w-3.5" />
                HL7 v2.5
              </TabsTrigger>
            </TabsList>
            <TabsContent value="fhir" className="mt-4 space-y-4">
              <ScrollArea className="h-[150px] rounded-lg border border-border bg-muted/30 p-3 sm:h-[180px] sm:p-4">
                <pre className="font-mono text-[10px] text-muted-foreground sm:text-xs">
                  {fhirContent}
                </pre>
              </ScrollArea>
              <div className="flex flex-col gap-2 sm:flex-row">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleCopy(fhirContent, 'fhir')}
                  className="flex-1"
                >
                  {copied === 'fhir' ? (
                    <Check className="mr-2 h-4 w-4" />
                  ) : (
                    <Copy className="mr-2 h-4 w-4" />
                  )}
                  {copied === 'fhir' ? 'Copiado' : 'Copiar'}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleDownload(fhirContent, `encounter-${session.id}.json`, 'application/json')}
                  className="flex-1"
                >
                  <Download className="mr-2 h-4 w-4" />
                  Descargar JSON
                </Button>
              </div>
            </TabsContent>
            <TabsContent value="hl7" className="mt-4 space-y-4">
              <ScrollArea className="h-[150px] rounded-lg border border-border bg-muted/30 p-3 sm:h-[180px] sm:p-4">
                <pre className="whitespace-pre-wrap font-mono text-[10px] text-muted-foreground sm:text-xs">
                  {hl7Content}
                </pre>
              </ScrollArea>
              <div className="flex flex-col gap-2 sm:flex-row">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleCopy(hl7Content, 'hl7')}
                  className="flex-1"
                >
                  {copied === 'hl7' ? (
                    <Check className="mr-2 h-4 w-4" />
                  ) : (
                    <Copy className="mr-2 h-4 w-4" />
                  )}
                  {copied === 'hl7' ? 'Copiado' : 'Copiar'}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleDownload(hl7Content, `encounter-${session.id}.hl7`, 'text/plain')}
                  className="flex-1"
                >
                  <Download className="mr-2 h-4 w-4" />
                  Descargar HL7
                </Button>
              </div>
            </TabsContent>
          </Tabs>
        )}

        {/* Integration Info */}
        <div className="mt-4 flex items-center gap-2 rounded-lg bg-primary/5 p-3 text-xs text-muted-foreground">
          <ExternalLink className="h-4 w-4 shrink-0 text-primary" />
          <p>
            Los documentos generados son compatibles con sistemas de Historia Clínica Electrónica 
            que soporten los estándares FHIR R4 y HL7 v2.5.
          </p>
        </div>
      </CardContent>
    </Card>
  )
}
