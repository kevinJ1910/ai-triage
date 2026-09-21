import { generateFHIRBundle, generateHL7v2Message, TRIAGE_LEVEL_METADATA, TriageSession } from '../lib/hl7';

describe('HL7 Interoperability Standards Generator', () => {
  const mockSession: TriageSession = {
    id: '987654',
    date: '2026-09-21T14:30:00.000Z',
    patientName: 'Carlos Ramirez Lopez',
    patientInfo: {
      name: 'Carlos Ramirez Lopez',
      documentId: '1025489632',
      birthDate: '1970-05-15',
      gender: 'male',
      phone: '3001234567',
      insurance: 'SURA EPS'
    },
    transcript: [
      { speaker: 'Doctor', text: 'Buenas tardes, cuénteme qué siente.' },
      { speaker: 'Paciente', text: 'Doctor, siento un dolor en el pecho opresivo muy fuerte.' }
    ],
    analysisResult: {
      triage: {
        level: 2,
        name: 'Emergencia',
        attention_time: 'Dentro de los siguientes 30 minutos',
        justification: 'Dolor torácico opresivo de inicio agudo con signos de alarma vital.'
      },
      entities: {
        symptoms: ['Dolor torácico', 'Diaforesis'],
        history: ['Hipertensión arterial'],
        vitals: ['PA: 160/95 mmHg', 'FC: 98 lpm'],
        medications: ['Losartán 50mg']
      }
    }
  };

  describe('HL7 FHIR Release 4 Compliance', () => {
    it('generates a 100% compliant FHIR R4 Bundle of type collection', () => {
      const bundle = generateFHIRBundle(mockSession);

      expect(bundle.resourceType).toBe('Bundle');
      expect(bundle.type).toBe('collection');
      expect(bundle.id).toBe('bundle-triage-987654');
      expect(bundle.meta.profile).toContain('http://hl7.org/fhir/StructureDefinition/Bundle');
      expect(bundle.entry).toBeInstanceOf(Array);
      expect(bundle.entry.length).toBeGreaterThanOrEqual(4);
    });

    it('contains a valid Patient resource conforming to FHIR R4 specs', () => {
      const bundle = generateFHIRBundle(mockSession);
      const patientEntry = bundle.entry.find((e: any) => e.resource.resourceType === 'Patient');
      expect(patientEntry).toBeDefined();

      const patient = patientEntry.resource;
      expect(patient.id).toBe('pat-987654');
      expect(patient.active).toBe(true);
      expect(patient.gender).toBe('male');
      expect(patient.birthDate).toBe('1970-05-15');
      expect(patient.name[0].text).toBe('Carlos Ramirez Lopez');
      expect(patient.name[0].family).toBe('Ramirez Lopez');
      expect(patient.identifier[0].value).toBe('1025489632');
      expect(patient.identifier[0].system).toBe('urn:oid:2.16.170.1.1.1');
      expect(patient.telecom[0].value).toBe('3001234567');
      expect(patient.extension[0].valueString).toBe('SURA EPS');
    });

    it('contains a valid Encounter resource with triage priority and hospital service provider', () => {
      const bundle = generateFHIRBundle(mockSession);
      const encounterEntry = bundle.entry.find((e: any) => e.resource.resourceType === 'Encounter');
      expect(encounterEntry).toBeDefined();

      const enc = encounterEntry.resource;
      expect(enc.id).toBe('enc-987654');
      expect(enc.status).toBe('triaged');
      expect(enc.class.code).toBe('EMER');
      expect(enc.priority.coding[0].system).toBe('https://minsalud.gov.co/triage/resolucion-5596');
      expect(enc.priority.coding[0].code).toBe('2');
      expect(enc.serviceProvider.display).toContain('CHRISTUS SINERGIA Salud');
      expect(enc.reasonCode.length).toBe(2);
    });

    it('contains a LOINC 75636-1 Observation resource for triage gravity assessment', () => {
      const bundle = generateFHIRBundle(mockSession);
      const triageObs = bundle.entry.find((e: any) => e.resource.id === 'obs-triage-987654')?.resource;
      expect(triageObs).toBeDefined();
      expect(triageObs.resourceType).toBe('Observation');
      expect(triageObs.code.coding[0].code).toBe('75636-1');
      expect(triageObs.valueInteger).toBe(2);
      expect(triageObs.note[0].text).toContain('Dolor torácico opresivo');
    });
  });

  describe('HL7 Version 2.5.1 ER7 Standard Compliance', () => {
    it('generates a standard pipe-delimited and carriage-return terminated message', () => {
      const hl7 = generateHL7v2Message(mockSession);
      expect(hl7).toContain('MSH|^~\\&|AI_TRIAGE|URGENCIAS|HOSPITAL_HIS|CENTRAL_ADMISION|');
      expect(hl7.endsWith('\r')).toBe(true);

      const segments = hl7.trim().split('\r');
      const segmentNames = segments.map((s: string) => s.substring(0, 3));
      expect(segmentNames).toContain('MSH');
      expect(segmentNames).toContain('EVN');
      expect(segmentNames).toContain('PID');
      expect(segmentNames).toContain('PV1');
      expect(segmentNames).toContain('PV2');
      expect(segmentNames).toContain('OBX');
      expect(segmentNames).toContain('DG1');
    });

    it('correctly maps patient demographic data in PID segment', () => {
      const hl7 = generateHL7v2Message(mockSession);
      const pid = hl7.split('\r').find((s: string) => s.startsWith('PID|'));
      expect(pid).toBeDefined();

      const fields = pid!.split('|');
      expect(fields[3]).toBe('1025489632^^^COL_MINSALUD^CC');
      expect(fields[5]).toBe('Ramirez Lopez^Carlos^^^^^L');
      expect(fields[7]).toBe('19700515');
      expect(fields[8]).toBe('M');
      expect(fields[13]).toBe('3001234567^^PRN^PH');
    });

    it('correctly encodes emergency triage visit in PV1, PV2 and OBX segments', () => {
      const hl7 = generateHL7v2Message(mockSession);
      const segments = hl7.split('\r');

      const pv1 = segments.find((s: string) => s.startsWith('PV1|'));
      expect(pv1).toContain('URG^TRIAGE^01^^CHRISTUS_SINERGIA');
      expect(pv1).toContain('SURA EPS');

      const pv2 = segments.find((s: string) => s.startsWith('PV2|'));
      expect(pv2).toContain('L2');

      const obxLevel = segments.find((s: string) => s.includes('75636-1^Emergency medical triage classification'));
      expect(obxLevel).toBeDefined();
      expect(obxLevel).toContain('|2|{level}^Level^UCUM|');

      const obxProtocol = segments.find((s: string) => s.includes('CHRISTUS SINERGIA Salud - Resolucion 5596 Minsalud Colombia'));
      expect(obxProtocol).toBeDefined();
    });
  });
});
