import { generateText, Output } from 'ai'
import { google } from '@ai-sdk/google'
import { z } from 'zod'

const triageOutputSchema = z.object({
  triagePriority: z
    .number()
    .min(1)
    .max(5)
    .describe('Manchester Triage System priority level: 1=Immediate, 2=Very Urgent, 3=Urgent, 4=Normal, 5=Non-urgent'),
  chiefComplaint: z.string().describe('Primary reason for the medical consultation in Spanish'),
  reasoning: z.string().describe('Explanation of the triage decision in Spanish'),
  entities: z.array(
    z.object({
      type: z.enum(['symptom', 'diagnosis', 'medication', 'vital_sign', 'allergy', 'medical_history']),
      text: z.string().describe('Original text from the conversation'),
      normalizedText: z.string().nullable().describe('Standardized medical term (SNOMED CT terminology)'),
      code: z.string().nullable().describe('SNOMED CT or ICD-10 code if applicable'),
      confidence: z.number().min(0).max(1).describe('Confidence level of the extraction')
    })
  ).describe('Extracted clinical entities from the conversation')
})

export async function POST(req: Request) {
  try {
    const { transcription, patientInfo } = await req.json()

    if (!transcription || transcription.length === 0) {
      return Response.json(
        { error: 'No transcription provided' },
        { status: 400 }
      )
    }

    const conversationText = transcription
      .map((seg: { speaker: string; text: string }) => 
        `${seg.speaker === 'doctor' ? 'Médico' : 'Paciente'}: ${seg.text}`
      )
      .join('\n')

    const patientContext = patientInfo
      ? `\nInformación del paciente:
        - Nombre: ${patientInfo.name || 'No especificado'}
        - Edad: ${patientInfo.age || 'No especificada'}
        - Sexo: ${patientInfo.gender === 'M' ? 'Masculino' : patientInfo.gender === 'F' ? 'Femenino' : 'No especificado'}`
      : ''

    const result = await generateText({
      model: google('models/gemini-flash-lite-latest'),
      output: Output.object({ schema: triageOutputSchema }),
      system: `Eres un sistema experto de triaje médico basado en el Sistema de Triaje de Manchester (MTS).
Tu tarea es analizar la conversación médico-paciente y:

1. EXTRAER ENTIDADES CLÍNICAS:
   - Síntomas (symptom): dolor, fiebre, náuseas, etc.
   - Diagnósticos (diagnosis): sospecha diagnóstica mencionada
   - Medicamentos (medication): medicamentos que toma o ha tomado
   - Signos vitales (vital_sign): presión arterial, frecuencia cardíaca, temperatura, saturación
   - Alergias (allergy): alergias conocidas
   - Antecedentes (medical_history): condiciones previas, cirugías, enfermedades crónicas

2. NORMALIZAR TERMINOLOGÍA:
   - Convierte términos coloquiales a terminología médica estándar
   - Por ejemplo: "dolor de barriga" → "Dolor abdominal"
   - Asigna códigos SNOMED CT o ICD-10 cuando sea posible

3. ASIGNAR PRIORIDAD DE TRIAJE:
   - Nivel 1 (Inmediato): Riesgo vital inmediato - paro cardíaco, shock, vía aérea comprometida
   - Nivel 2 (Muy Urgente): Emergencia - dolor torácico, dificultad respiratoria severa, ACV
   - Nivel 3 (Urgente): Requiere atención pronta - fracturas, dolor severo, fiebre alta
   - Nivel 4 (Normal): Atención estándar - síntomas moderados, heridas menores
   - Nivel 5 (No Urgente): Sin urgencia - síntomas leves, consultas de seguimiento

4. RAZONAMIENTO:
   - Explica claramente por qué asignaste ese nivel de prioridad
   - Menciona los discriminadores clave del Sistema de Manchester utilizados

Responde SIEMPRE en español.`,
      prompt: `Analiza la siguiente conversación médico-paciente y proporciona la clasificación de triaje:
${patientContext}

CONVERSACIÓN:
${conversationText}

Extrae todas las entidades clínicas relevantes, normaliza la terminología médica y asigna el nivel de prioridad de triaje apropiado según el Sistema de Manchester.`
    })

    const output = result.output
    
    if (!output) {
      return Response.json(
        { error: 'Failed to generate triage analysis' },
        { status: 500 }
      )
    }

    // Add unique IDs and timestamps to entities
    const entitiesWithIds = output.entities.map((entity, index) => ({
      ...entity,
      id: `entity-${Date.now()}-${index}`,
      timestamp: new Date()
    }))

    return Response.json({
      triagePriority: output.triagePriority,
      chiefComplaint: output.chiefComplaint,
      reasoning: output.reasoning,
      entities: entitiesWithIds
    })
  } catch (error) {
    console.error('Triage API error:', error)
    return Response.json(
      { error: 'Error processing triage request' },
      { status: 500 }
    )
  }
}
