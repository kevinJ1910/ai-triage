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
1. "patientInfo": Información básica del paciente mencionada en la conversación. Extrae y normaliza los siguientes campos:
   - "name": Nombre completo del paciente. Si no se menciona, devuelve null o "".
   - "documentId": Documento de identidad (cédula, pasaporte, etc.). Extrae únicamente los dígitos numéricos. Si no se menciona, devuelve null.
   - "birthDate": Fecha de nacimiento del paciente. Normaliza siempre al formato "YYYY-MM-DD" (por ejemplo, "11 de diciembre del 2004" debe ser "2004-12-11"). Si no se menciona, devuelve null.
   - "gender": Género del paciente. Clasifica estrictamente en una de estas opciones: "male" (si refiere ser hombre, varón, masculino), "female" (si refiere ser mujer, femenina, femenino), "other" (si es otro género), o "unknown" (si no se menciona o no está claro).
   - "phone": Número de teléfono. Extrae únicamente los dígitos numéricos. Si no se menciona, devuelve null.
   - "insurance": Aseguradora médica o EPS mencionada (por ejemplo, Sura, Sanitas, Nueva EPS, etc.). Si no se menciona, devuelve null.

2. "entities":
   - "symptoms": Lista de síntomas mencionados.
   - "medications": Lista de medicamentos mencionados.
   - "vitals": Constantes vitales o signos físicos descritos (por ejemplo, tensión arterial, frecuencia cardíaca, etc.).
   - "history": Antecedentes médicos o diagnósticos previos.

Asigna un nivel de prioridad de triaje clínico del 1 al 5:
Nivel 1: Resucitación (Riesgo vital inminente)
Nivel 2: Emergencia (Alto riesgo, dolor severo)
Nivel 3: Urgencia (Requiere múltiples recursos)
Nivel 4: Menos Urgente (Requiere un recurso)
Nivel 5: No Urgente (No requiere recursos)

Proporciona una justificación clínica concisa en español de por qué se asignó este nivel, detallando los factores de riesgo identificados.

Devuelve estrictamente un objeto JSON con esta estructura exacta (solo el JSON validado):
{
  "patientInfo": {
    "name": "string or null",
    "documentId": "string or null",
    "birthDate": "string or null",
    "gender": "male | female | other | unknown",
    "phone": "string or null",
    "insurance": "string or null"
  },
  "entities": {
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
