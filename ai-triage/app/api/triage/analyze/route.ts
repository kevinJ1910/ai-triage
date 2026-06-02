import { GoogleGenAI } from "@google/genai";
import { NextRequest, NextResponse } from "next/server";

export async function POST(req: NextRequest) {
  try {
    const ai = new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY });
    const { transcript } = await req.json();
    
    const prompt = `
Eres un Asistente Médico de Triaje basado en el protocolo AI-Triage (similar a ESI y Manchester).
Analiza la siguiente conversación transcrita entre un médico y un paciente.
Extrae la siguiente información:
1. "patientName": Nombre del paciente si se menciona en la conversación, de lo contrario devuelve "Paciente Desconocido".
2. "symptoms": Lista de síntomas mencionados.
3. "medications": Lista de medicamentos mencionados.
4. "vitals": Constantes vitales o signos físicos descritos.
5. "history": Antecedentes médicos o diagnósticos previos.

Asigna un nivel de prioridad de triaje clínico del 1 al 5:
Nivel 1: Resucitación (Riesgo vital inminente)
Nivel 2: Emergencia (Alto riesgo, dolor severo)
Nivel 3: Urgencia (Requiere múltiples recursos)
Nivel 4: Menos Urgente (Requiere un recurso)
Nivel 5: No Urgente (No requiere recursos)

Proporciona una justificación clínica concisa en español de por qué se asignó este nivel, detallando los factores de riesgo identificados.

Devuelve estrictamente un objeto JSON con esta estructura exacta (solo el JSON validado):
{
  "entities": {
    "patientName": "string",
    "symptoms": ["string"],
    "medications": ["string"],
    "vitals": ["string"],
    "history": ["string"]
  },
  "triage": {
    "level": number,
    "justification": "string"
  }
}

Transcripción:
"${transcript}"
`;

    const response = await ai.models.generateContent({
      model: "gemini-2.5-flash",
      contents: prompt,
      config: {
          responseMimeType: "application/json",
      }
    });

    const data = JSON.parse(response.text || '{}');
    return NextResponse.json(data);
  } catch (error: any) {
    console.error("AI Analysis error:", error);
    return NextResponse.json({ error: "Failed to analyze" }, { status: 500 });
  }
}
