/**
 * Motor de Interoperabilidad Clínica HL7 (Health Level Seven International)
 * 
 * Implementa dos estándares internacionales oficiales:
 * 1. HL7 FHIR Release 4 (Fast Healthcare Interoperability Resources - JSON)
 * 2. HL7 Version 2.5.1 ER7 (Formato delimitado por barras verticales / tuberías)
 * 
 * Compatible con la Resolución 5596 del Ministerio de Salud de Colombia
 * y el protocolo institucional de Urgencias CHRISTUS SINERGIA Salud.
 */

export interface PatientInfo {
  name: string;
  documentId: string;
  birthDate: string;
  gender: string;
  phone: string;
  insurance: string;
}

export interface TriageSession {
  id: string;
  date: string;
  patientName: string;
  patientInfo?: PatientInfo;
  transcript: { speaker: string; text: string }[];
  analysisResult: any;
}

/**
 * Mapeo de niveles de triaje según CHRISTUS SINERGIA Salud / Res. 5596 Colombia
 */
export const TRIAGE_LEVEL_METADATA: Record<number, { name: string; color: string; attentionTime: string; fhirPriority: string; hl7Priority: string }> = {
  1: {
    name: "Reanimación",
    color: "Rojo",
    attentionTime: "Inmediata",
    fhirPriority: "EM",
    hl7Priority: "L1"
  },
  2: {
    name: "Emergencia",
    color: "Naranja",
    attentionTime: "Dentro de los siguientes 30 minutos",
    fhirPriority: "EM",
    hl7Priority: "L2"
  },
  3: {
    name: "Urgencia",
    color: "Amarillo",
    attentionTime: "Hasta 120 minutos",
    fhirPriority: "UR",
    hl7Priority: "L3"
  },
  4: {
    name: "Consulta Prioritaria",
    color: "Verde",
    attentionTime: "Direccionamiento a su EPS",
    fhirPriority: "PRN",
    hl7Priority: "L4"
  },
  5: {
    name: "Consulta Externa",
    color: "Azul",
    attentionTime: "Direccionamiento a su EPS",
    fhirPriority: "R",
    hl7Priority: "L5"
  }
};

/**
 * Formatea una fecha a timestamp compacto estándar HL7 v2 (YYYYMMDDHHMMSS)
 */
function toHL7Timestamp(dateStr?: string): string {
  const d = dateStr ? new Date(dateStr) : new Date();
  if (isNaN(d.getTime())) return new Date().toISOString().replace(/[-:T]/g, '').slice(0, 14);
  const pad = (n: number) => n.toString().padStart(2, '0');
  return `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`;
}

/**
 * Formatea una fecha a formato YYYYMMDD para campos de nacimiento en HL7 v2
 */
function toHL7Date(dateStr?: string): string {
  if (!dateStr) return "";
  const clean = dateStr.trim();
  const match = clean.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (match) {
    return `${match[1]}${match[2]}${match[3]}`;
  }
  const digitsOnly = clean.replace(/[^0-9]/g, '');
  if (digitsOnly.length === 8) {
    return digitsOnly;
  }
  const d = new Date(clean);
  if (isNaN(d.getTime())) return digitsOnly.slice(0, 8);
  const pad = (n: number) => n.toString().padStart(2, '0');
  return `${d.getUTCFullYear()}${pad(d.getUTCMonth() + 1)}${pad(d.getUTCDate())}`;
}

/**
 * Escapa caracteres especiales reservados en cadenas de texto HL7 v2
 */
function escapeHL7v2Text(text: string): string {
  if (!text) return "";
  return text
    .replace(/\\/g, '\\E\\')
    .replace(/\|/g, '\\F\\')
    .replace(/\^/g, '\\S\\')
    .replace(/~/g, '\\R\\')
    .replace(/&/g, '\\T\\')
    .replace(/\r?\n/g, '\\X0D\\\\X0A\\');
}

/**
 * Divide el nombre completo del paciente en Apellidos y Nombres para HL7 PID-5
 */
function splitPatientName(fullName?: string): { family: string; given: string } {
  const clean = (fullName || "").trim();
  if (!clean || clean.toLowerCase() === "paciente desconocido") {
    return { family: "Desconocido", given: "Paciente" };
  }
  const parts = clean.split(/\s+/);
  if (parts.length === 1) return { family: parts[0], given: "" };
  if (parts.length === 2) return { family: parts[1], given: parts[0] };
  // En paises hispanos habitualmente los ultimos 2 tokens son los dos apellidos
  const family = parts.slice(-2).join(" ");
  const given = parts.slice(0, -2).join(" ");
  return { family, given };
}

/**
 * Genera un Bundle HL7 FHIR Release 4 (JSON) 100% válido y conforme a la especificación oficial.
 */
export function generateFHIRBundle(session: TriageSession): Record<string, any> {
  const patientId = `pat-${session.id}`;
  const encounterId = `enc-${session.id}`;
  const patInfo = session.patientInfo || {
    name: session.patientName || "Paciente Desconocido",
    documentId: "",
    birthDate: "",
    gender: "unknown",
    phone: "",
    insurance: ""
  };

  const triageLevel = Number(session.analysisResult?.triage?.level) || 5;
  const metaLevel = TRIAGE_LEVEL_METADATA[triageLevel] || TRIAGE_LEVEL_METADATA[5];
  const triageJustification = session.analysisResult?.triage?.justification || "Sin justificación registrada";
  const nameParts = splitPatientName(patInfo.name);

  // 1. Recurso Patient
  const patientResource: Record<string, any> = {
    resourceType: "Patient",
    id: patientId,
    active: true,
    name: [
      {
        use: "official",
        text: patInfo.name || "Paciente Desconocido",
        family: nameParts.family,
        given: nameParts.given ? [nameParts.given] : []
      }
    ]
  };

  if (patInfo.documentId) {
    patientResource.identifier = [
      {
        use: "official",
        type: {
          coding: [
            {
              system: "http://terminology.hl7.org/CodeSystem/v2-0203",
              code: "NNCOL",
              display: "Documento Nacional de Identidad / Cédula"
            }
          ],
          text: "Cédula de Ciudadanía / TI"
        },
        system: "urn:oid:2.16.170.1.1.1",
        value: patInfo.documentId
      }
    ];
  }

  const validGenders = ['male', 'female', 'other', 'unknown'];
  patientResource.gender = validGenders.includes(patInfo.gender) ? patInfo.gender : 'unknown';

  if (patInfo.birthDate) {
    patientResource.birthDate = patInfo.birthDate;
  }

  if (patInfo.phone) {
    patientResource.telecom = [
      {
        system: "phone",
        value: patInfo.phone,
        use: "mobile"
      }
    ];
  }

  if (patInfo.insurance) {
    patientResource.extension = [
      {
        url: "https://minsalud.gov.co/fhir/StructureDefinition/aseguradora-eps",
        valueString: patInfo.insurance
      }
    ];
  }

  // 2. Recurso Encounter (Atención de Urgencias)
  const encounterResource: Record<string, any> = {
    resourceType: "Encounter",
    id: encounterId,
    status: "triaged",
    class: {
      system: "http://terminology.hl7.org/CodeSystem/v3-ActCode",
      code: "EMER",
      display: "Emergency"
    },
    subject: {
      reference: `Patient/${patientId}`,
      display: patInfo.name || "Paciente Desconocido"
    },
    priority: {
      coding: [
        {
          system: "https://minsalud.gov.co/triage/resolucion-5596",
          code: String(triageLevel),
          display: metaLevel.name
        },
        {
          system: "http://terminology.hl7.org/CodeSystem/v3-ObservationValue",
          code: metaLevel.fhirPriority,
          display: metaLevel.name
        }
      ],
      text: `Triage Nivel ${triageLevel}: ${metaLevel.name} (${metaLevel.attentionTime})`
    },
    period: {
      start: new Date(session.date).toISOString()
    },
    serviceProvider: {
      display: "Servicio de Urgencias - CHRISTUS SINERGIA Salud"
    },
    text: {
      status: "generated",
      div: `<div xmlns="http://www.w3.org/1999/xhtml"><h3>Clasificación de Triaje: Nivel ${triageLevel} - ${metaLevel.name}</h3><p><strong>Tiempo de atención:</strong> ${metaLevel.attentionTime}</p><p><strong>Justificación Clínica:</strong> ${triageJustification}</p></div>`
    }
  };

  const symptoms = session.analysisResult?.entities?.symptoms || [];
  if (symptoms.length > 0) {
    encounterResource.reasonCode = symptoms.map((symptom: string) => ({
      coding: [
        {
          system: "http://snomed.info/sct",
          display: symptom
        }
      ],
      text: symptom
    }));
  }

  const entries: any[] = [
    {
      fullUrl: `urn:uuid:${patientId}`,
      resource: patientResource
    },
    {
      fullUrl: `urn:uuid:${encounterId}`,
      resource: encounterResource
    }
  ];

  // 3. Recurso Observation: Puntuación de Triaje (LOINC 75636-1)
  const triageObservationId = `obs-triage-${session.id}`;
  entries.push({
    fullUrl: `urn:uuid:${triageObservationId}`,
    resource: {
      resourceType: "Observation",
      id: triageObservationId,
      status: "final",
      category: [
        {
          coding: [
            {
              system: "http://terminology.hl7.org/CodeSystem/observation-category",
              code: "exam",
              display: "Exam"
            }
          ]
        }
      ],
      code: {
        coding: [
          {
            system: "http://loinc.org",
            code: "75636-1",
            display: "Emergency medical triage classification"
          }
        ],
        text: "Clasificación de Gravedad de Triaje"
      },
      subject: {
        reference: `Patient/${patientId}`
      },
      encounter: {
        reference: `Encounter/${encounterId}`
      },
      effectiveDateTime: new Date(session.date).toISOString(),
      valueInteger: triageLevel,
      interpretation: [
        {
          coding: [
            {
              system: "https://minsalud.gov.co/triage/resolucion-5596",
              code: String(triageLevel),
              display: metaLevel.name
            }
          ],
          text: metaLevel.name
        }
      ],
      note: [
        {
          text: triageJustification
        }
      ]
    }
  });

  // 4. Recursos Condition: Síntomas y Antecedentes Clínicos
  symptoms.forEach((symptom: string, idx: number) => {
    entries.push({
      fullUrl: `urn:uuid:cond-symptom-${idx}-${session.id}`,
      resource: {
        resourceType: "Condition",
        id: `cond-symptom-${idx}-${session.id}`,
        clinicalStatus: {
          coding: [
            {
              system: "http://terminology.hl7.org/CodeSystem/condition-clinical",
              code: "active",
              display: "Active"
            }
          ]
        },
        verificationStatus: {
          coding: [
            {
              system: "http://terminology.hl7.org/CodeSystem/condition-ver-status",
              code: "provisional",
              display: "Provisional"
            }
          ]
        },
        category: [
          {
            coding: [
              {
                system: "http://terminology.hl7.org/CodeSystem/condition-category",
                code: "encounter-diagnosis",
                display: "Encounter Diagnosis"
              }
            ]
          }
        ],
        code: {
          coding: [
            {
              system: "http://snomed.info/sct",
              display: symptom
            }
          ],
          text: symptom
        },
        subject: {
          reference: `Patient/${patientId}`
        },
        encounter: {
          reference: `Encounter/${encounterId}`
        },
        recordedDate: new Date(session.date).toISOString()
      }
    });
  });

  const history = session.analysisResult?.entities?.history || [];
  history.forEach((hist: string, idx: number) => {
    entries.push({
      fullUrl: `urn:uuid:cond-history-${idx}-${session.id}`,
      resource: {
        resourceType: "Condition",
        id: `cond-history-${idx}-${session.id}`,
        clinicalStatus: {
          coding: [
            {
              system: "http://terminology.hl7.org/CodeSystem/condition-clinical",
              code: "active",
              display: "Active"
            }
          ]
        },
        category: [
          {
            coding: [
              {
                system: "http://terminology.hl7.org/CodeSystem/condition-category",
                code: "problem-list-item",
                display: "Problem List Item"
              }
            ]
          }
        ],
        code: {
          coding: [
            {
              system: "http://snomed.info/sct",
              display: hist
            }
          ],
          text: hist
        },
        subject: {
          reference: `Patient/${patientId}`
        }
      }
    });
  });

  // 5. Recursos Observation: Signos Vitales
  const vitals = session.analysisResult?.entities?.vitals || [];
  vitals.forEach((vital: string, idx: number) => {
    entries.push({
      fullUrl: `urn:uuid:obs-vital-${idx}-${session.id}`,
      resource: {
        resourceType: "Observation",
        id: `obs-vital-${idx}-${session.id}`,
        status: "final",
        category: [
          {
            coding: [
              {
                system: "http://terminology.hl7.org/CodeSystem/observation-category",
                code: "vital-signs",
                display: "Vital Signs"
              }
            ]
          }
        ],
        code: {
          text: vital
        },
        subject: {
          reference: `Patient/${patientId}`
        },
        encounter: {
          reference: `Encounter/${encounterId}`
        },
        valueString: vital,
        effectiveDateTime: new Date(session.date).toISOString()
      }
    });
  });

  // 6. Recursos MedicationStatement: Medicamentos
  const medications = session.analysisResult?.entities?.medications || [];
  medications.forEach((med: string, idx: number) => {
    entries.push({
      fullUrl: `urn:uuid:med-${idx}-${session.id}`,
      resource: {
        resourceType: "MedicationStatement",
        id: `med-${idx}-${session.id}`,
        status: "active",
        subject: {
          reference: `Patient/${patientId}`
        },
        medicationCodeableConcept: {
          text: med
        },
        dateAsserted: new Date(session.date).toISOString()
      }
    });
  });

  return {
    resourceType: "Bundle",
    id: `bundle-triage-${session.id}`,
    meta: {
      lastUpdated: new Date().toISOString(),
      profile: ["http://hl7.org/fhir/StructureDefinition/Bundle"]
    },
    type: "collection",
    timestamp: new Date(session.date).toISOString(),
    entry: entries
  };
}

/**
 * Genera un mensaje HL7 Version 2.5.1 ER7 oficial (ADT^A08: Actualización de admisión y triaje clínico)
 * Estándar hospitalario clásico delimitado por tuberías (|) y retorno de carro (\r).
 */
export function generateHL7v2Message(session: TriageSession): string {
  const timestamp = toHL7Timestamp(session.date);
  const patInfo = session.patientInfo || {
    name: session.patientName || "Paciente Desconocido",
    documentId: "",
    birthDate: "",
    gender: "unknown",
    phone: "",
    insurance: ""
  };

  const nameParts = splitPatientName(patInfo.name);
  const birthDateHL7 = toHL7Date(patInfo.birthDate);
  const genderHL7 = patInfo.gender === 'male' ? 'M' : patInfo.gender === 'female' ? 'F' : patInfo.gender === 'other' ? 'O' : 'U';

  const triageLevel = Number(session.analysisResult?.triage?.level) || 5;
  const metaLevel = TRIAGE_LEVEL_METADATA[triageLevel] || TRIAGE_LEVEL_METADATA[5];
  const triageJustification = session.analysisResult?.triage?.justification || "Sin justificación registrada";
  const symptoms = session.analysisResult?.entities?.symptoms || [];
  const vitals = session.analysisResult?.entities?.vitals || [];

  const segments: string[] = [];

  // MSH: Message Header
  // MSH-1: |
  // MSH-2: ^~\&
  // MSH-3: Sending App (AI_TRIAGE)
  // MSH-4: Sending Facility (URGENCIAS)
  // MSH-5: Receiving App (HOSPITAL_HIS)
  // MSH-6: Receiving Facility (CENTRAL_ADMISION)
  // MSH-7: Message Date/Time
  // MSH-9: Message Type (ADT^A08^ADT_A01)
  // MSH-10: Message Control ID
  // MSH-11: Processing ID (P = Production)
  // MSH-12: Version ID (2.5.1)
  // MSH-18: Character Set (UNICODE UTF-8)
  const msgControlId = `MSG${session.id.replace(/[^0-9]/g, '') || Date.now()}`;
  segments.push(`MSH|^~\\&|AI_TRIAGE|URGENCIAS|HOSPITAL_HIS|CENTRAL_ADMISION|${timestamp}||ADT^A08^ADT_A01|${msgControlId}|P|2.5.1|||AL|NE||UNICODE UTF-8`);

  // EVN: Event Type
  // EVN-1: Event Type Code (A08 = Update Patient Information)
  // EVN-2: Recorded Date/Time
  segments.push(`EVN|A08|${timestamp}|||DR_TRIAGE^MEDICO^TRIAGE`);

  // PID: Patient Identification
  // PID-1: Set ID
  // PID-2: Internal ID
  // PID-3: Patient Identifier List (Document ID)
  // PID-5: Patient Name (Family^Given)
  // PID-7: Date of Birth
  // PID-8: Administrative Sex
  // PID-13: Phone Number
  const docVal = patInfo.documentId ? `${patInfo.documentId}^^^COL_MINSALUD^CC` : `pat-${session.id}^^^LOCAL^MR`;
  const nameField = `${escapeHL7v2Text(nameParts.family)}^${escapeHL7v2Text(nameParts.given)}^^^^^L`;
  const phoneField = patInfo.phone ? `${escapeHL7v2Text(patInfo.phone)}^^PRN^PH` : "";
  segments.push(`PID|1||${docVal}||${nameField}||${birthDateHL7}|${genderHL7}|||||${phoneField}|||S`);

  // PV1: Patient Visit (Emergency Admission)
  // PV1-1: Set ID
  // PV1-2: Patient Class (E = Emergency)
  // PV1-3: Assigned Patient Location
  // PV1-4: Admission Type (E = Emergency)
  // PV1-7: Attending Doctor
  // PV1-10: Hospital Service (URG)
  // PV1-19: Visit Number
  // PV1-20: Financial Class / Insurance (EPS)
  // PV1-44: Admit Date/Time
  const insuranceVal = patInfo.insurance ? escapeHL7v2Text(patInfo.insurance) : "PARTICULAR";
  segments.push(`PV1|1|E|URG^TRIAGE^01^^CHRISTUS_SINERGIA|E|||1234^MEDICO^TRIAGE|||URG||||||||enc-${session.id}|${insuranceVal}|||||||||||||||||||||||||${timestamp}`);

  // PV2: Patient Visit - Additional Information
  // PV2-3: Admit Reason / Chief Complaint
  // PV2-8: Expected Admit Date/Time
  // PV2-24: Patient Status / Triage Level Code
  const complaint = symptoms.length > 0 ? escapeHL7v2Text(symptoms.join(', ')) : "EVALUACION DE TRIAJE";
  segments.push(`PV2|||${complaint}|||||${timestamp}|||||||||||||||${metaLevel.hl7Priority}`);

  // OBX: Observation Results (Clinical Findings & Triage Classification)
  let obxSeq = 1;

  // OBX 1: Nivel de Triaje (LOINC 75636-1)
  segments.push(`OBX|${obxSeq++}|NM|75636-1^Emergency medical triage classification^LN||${triageLevel}|{level}^Level^UCUM|||F|||${timestamp}`);

  // OBX 2: Nombre de Nivel Institucional
  segments.push(`OBX|${obxSeq++}|ST|TRIAGE_LEVEL_NAME^Clasificacion de Triaje^L||${escapeHL7v2Text(metaLevel.name)}||||F|||${timestamp}`);

  // OBX 3: Tiempo Estimado de Atencion
  segments.push(`OBX|${obxSeq++}|ST|ATTENTION_TIME^Tiempo Estimado de Atencion^L||${escapeHL7v2Text(metaLevel.attentionTime)}||||F|||${timestamp}`);

  // OBX 4: Justificacion Clinica del Medico / IA
  segments.push(`OBX|${obxSeq++}|TX|TRIAGE_JUSTIFICATION^Justificacion Clinica^L||${escapeHL7v2Text(triageJustification)}||||F|||${timestamp}`);

  // OBX 5: Protocolo de Clasificacion
  segments.push(`OBX|${obxSeq++}|ST|TRIAGE_PROTOCOL^Protocolo Asistencial^L||CHRISTUS SINERGIA Salud - Resolucion 5596 Minsalud Colombia||||F|||${timestamp}`);

  // OBX 6+: Signos Vitales
  vitals.forEach((vital: string, idx: number) => {
    segments.push(`OBX|${obxSeq++}|ST|VITAL_SIGN_${idx + 1}^Signo Vital^L||${escapeHL7v2Text(vital)}||||F|||${timestamp}`);
  });

  // DG1: Diagnostico provisional / Motivo de consulta (SNOMED-CT)
  if (symptoms.length > 0) {
    symptoms.forEach((symptom: string, idx: number) => {
      segments.push(`DG1|${idx + 1}|SCT|TRIAGE_DX^${escapeHL7v2Text(symptom)}^SNOMED-CT||${timestamp}|A`);
    });
  }

  // Estándar HL7 v2 utiliza Retorno de Carro (\r = ASCII 13) como terminador obligatorio de segmento
  return segments.join('\r') + '\r';
}

/**
 * Descarga en el navegador el archivo HL7 FHIR R4 Bundle (.json)
 */
export function downloadFHIRJson(session: TriageSession): void {
  const bundle = generateFHIRBundle(session);
  const jsonStr = JSON.stringify(bundle, null, 2);
  const blob = new Blob([jsonStr], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  const safeName = (session.patientName || "paciente").replace(/\s+/g, '_');
  a.download = `triaje_hl7_fhir_r4_${safeName}_${session.id}.json`;
  a.click();
  URL.revokeObjectURL(url);
}

/**
 * Descarga en el navegador el mensaje HL7 v2.5.1 oficial (.hl7 / ER7)
 */
export function downloadHL7v2Message(session: TriageSession): void {
  const hl7Message = generateHL7v2Message(session);
  const blob = new Blob([hl7Message], { type: 'text/plain;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  const safeName = (session.patientName || "paciente").replace(/\s+/g, '_');
  a.download = `triaje_hl7_v251_${safeName}_${session.id}.hl7`;
  a.click();
  URL.revokeObjectURL(url);
}
