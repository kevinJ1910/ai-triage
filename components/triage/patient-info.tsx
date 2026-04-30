'use client'

import { User, Calendar, Hash, Users } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import type { PatientInfo } from '@/lib/types'

interface PatientInfoFormProps {
  patient: PatientInfo
  onUpdate: (patient: PatientInfo) => void
  disabled?: boolean
}

export function PatientInfoForm({ patient, onUpdate, disabled }: PatientInfoFormProps) {
  return (
    <Card className="border-border bg-card">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base font-medium">
          <User className="h-4 w-4 text-primary" />
          Información del Paciente
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="name" className="flex items-center gap-2 text-sm">
              <User className="h-3.5 w-3.5 text-muted-foreground" />
              Nombre Completo
            </Label>
            <Input
              id="name"
              placeholder="Nombre del paciente"
              value={patient.name || ''}
              onChange={(e) => onUpdate({ ...patient, name: e.target.value })}
              disabled={disabled}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="documentId" className="flex items-center gap-2 text-sm">
              <Hash className="h-3.5 w-3.5 text-muted-foreground" />
              Documento de Identidad
            </Label>
            <Input
              id="documentId"
              placeholder="Número de documento"
              value={patient.documentId || ''}
              onChange={(e) => onUpdate({ ...patient, documentId: e.target.value })}
              disabled={disabled}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="age" className="flex items-center gap-2 text-sm">
              <Calendar className="h-3.5 w-3.5 text-muted-foreground" />
              Edad
            </Label>
            <Input
              id="age"
              type="number"
              placeholder="Años"
              min={0}
              max={150}
              value={patient.age || ''}
              onChange={(e) => onUpdate({ ...patient, age: parseInt(e.target.value) || undefined })}
              disabled={disabled}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="gender" className="flex items-center gap-2 text-sm">
              <Users className="h-3.5 w-3.5 text-muted-foreground" />
              Sexo
            </Label>
            <Select
              value={patient.gender || ''}
              onValueChange={(value) => onUpdate({ ...patient, gender: value as 'M' | 'F' | 'O' })}
              disabled={disabled}
            >
              <SelectTrigger id="gender">
                <SelectValue placeholder="Seleccionar" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="M">Masculino</SelectItem>
                <SelectItem value="F">Femenino</SelectItem>
                <SelectItem value="O">Otro</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
