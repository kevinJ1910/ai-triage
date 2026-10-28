import { generateFHIRBundle, generateHL7v2Message, parseVital, TRIAGE_LEVEL_METADATA, TriageSession } from '../lib/hl7';

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

  describe('Entidades ampliadas: diagnosticos, alergias, negados y signos vitales codificados', () => {
    const extended: TriageSession = {
      ...mockSession,
      analysisResult: {
        ...mockSession.analysisResult,
        entities: {
          symptoms: ['Dolor toracico'],
          diagnoses: ['Sindrome coronario agudo'],
          allergies: ['Penicilina'],
          negated_findings: ['Disnea'],
          history: [],
          medications: [],
          vitals: ['PA: 160/95 mmHg', 'FC: 98 lpm', 'SpO2: 94%', 'saturacion normal'],
        },
      },
    };

    it('parses compact vitals into LOINC codes and numeric values', () => {
      expect(parseVital('PA: 160/95 mmHg')).toMatchObject({ loinc: '85354-9', systolic: 160, diastolic: 95, ucum: 'mm[Hg]' });
      expect(parseVital('T: 38.9°C')).toMatchObject({ loinc: '8310-5', value: 38.9, ucum: 'Cel' });
      expect(parseVital('saturacion normal')).toBeNull();
      expect(parseVital('PA: 160')).toBeNull();
    });

    it('exports AllergyIntolerance, a provisional diagnosis and a refuted Condition', () => {
      const resources = generateFHIRBundle(extended).entry.map((e: any) => e.resource);
      const allergy = resources.find((r: any) => r.resourceType === 'AllergyIntolerance');
      expect(allergy.code.text).toBe('Penicilina');
      expect(allergy.patient.reference).toBe('Patient/pat-987654');
      expect(allergy.verificationStatus.coding[0].code).toBe('unconfirmed');

      const refuted = resources.find((r: any) => r.resourceType === 'Condition' && r.code.text === 'Disnea');
      expect(refuted.verificationStatus.coding[0].code).toBe('refuted');
      expect(refuted.clinicalStatus).toBeUndefined();

      const dx = resources.find((r: any) => r.resourceType === 'Condition' && r.code.text === 'Sindrome coronario agudo');
      expect(dx.verificationStatus.coding[0].code).toBe('provisional');
    });

    it('codes vital-sign Observations with LOINC and UCUM quantities', () => {
      const vitals = generateFHIRBundle(extended).entry
        .map((e: any) => e.resource)
        .filter((r: any) => r.resourceType === 'Observation' && r.category?.[0]?.coding?.[0]?.code === 'vital-signs');
      const bp = vitals.find((r: any) => r.code.coding?.[0]?.code === '85354-9');
      expect(bp.component.map((c: any) => c.valueQuantity.value)).toEqual([160, 95]);
      const hr = vitals.find((r: any) => r.code.coding?.[0]?.code === '8867-4');
      expect(hr.valueQuantity).toEqual({ value: 98, unit: 'lpm', system: 'http://unitsofmeasure.org', code: '/min' });
      const free = vitals.find((r: any) => r.code.text === 'saturacion normal');
      expect(free.valueString).toBe('saturacion normal');
    });

    it('adds AL1 and DG1 segments and does not export negated findings as diagnoses', () => {
      const segments = generateHL7v2Message(extended).split('\r');
      expect(segments).toContain('AL1|1||^Penicilina^L');
      const dg1 = segments.filter((s: string) => s.startsWith('DG1|'));
      expect(dg1.some((s: string) => s.includes('Sindrome coronario agudo'))).toBe(true);
      expect(dg1.some((s: string) => s.includes('Disnea'))).toBe(false);
      expect(segments.some((s: string) => s.startsWith('OBX|') && s.includes('8480-6^Systolic blood pressure^LN||160|'))).toBe(true);
      const names = segments.map((s: string) => s.split('|')[0]);
      expect(names.indexOf('AL1')).toBeLessThan(names.indexOf('DG1'));
    });
  });

  describe('Codificacion terminologica SNOMED CT, CIE-10 y ATC desde normalized_terms', () => {
    const codedSession: TriageSession = {
      ...mockSession,
      analysisResult: {
        ...mockSession.analysisResult,
        entities: {
          symptoms: ['Dolor torácico', 'Tos'],
          diagnoses: ['Crisis hipertensiva'],
          history: ['Hipertensión arterial'],
          medications: ['Losartán 50mg'],
          allergies: ['Penicilina'],
          negated_findings: ['Disnea'],
          vitals: ['PA: 190/120 mmHg'],
        },
        normalized_terms: [
          {
            raw_term: 'dolor en el pecho',
            medical_term: 'Dolor torácico',
            code: 'R07.4',
            code_system: 'CIE-10',
            code_snomed: '29857009',
            snomed_valid: true,
            valid: true,
          },
          {
            raw_term: 'crisis hipertensiva',
            medical_term: 'Crisis hipertensiva',
            code: 'I16.9',
            code_system: 'CIE-10',
            code_snomed: '706882009',
            snomed_valid: true,
            valid: true,
          },
          {
            raw_term: 'hipertension arterial',
            medical_term: 'Hipertensión arterial',
            code: 'I10',
            code_system: 'CIE-10',
            code_snomed: '38341003',
            snomed_valid: true,
            valid: true,
          },
          {
            raw_term: 'losartan',
            medical_term: 'Losartán',
            code: 'C09CA01',
            code_system: 'ATC',
            code_snomed: '373567002',
            snomed_valid: true,
            valid: true,
          },
          {
            raw_term: 'penicilina',
            medical_term: 'Penicilina',
            code_snomed: '764146007',
            snomed_valid: true,
            valid: false,
          },
          {
            raw_term: 'medicamentos',
            medical_term: 'Medicamentos generales',
            code: 'Z79.899',
            code_system: 'CIE-10',
            valid: false,
          },
        ],
      },
    };

    it('attaches verified SNOMED CT, ICD-10 and ATC codes across Condition, Encounter, MedicationStatement and AllergyIntolerance', () => {
      const bundle = generateFHIRBundle(codedSession);
      const resources = bundle.entry.map((e: any) => e.resource);

      const encounter = resources.find((r: any) => r.resourceType === 'Encounter');
      expect(encounter.reasonCode[0].coding).toEqual([
        { system: 'http://snomed.info/sct', code: '29857009', display: 'Dolor torácico' },
        { system: 'http://hl7.org/fhir/sid/icd-10', code: 'R07.4', display: 'Dolor torácico' },
      ]);
      // "Tos" must NOT falsely match substring inside "medicamentos"
      expect(encounter.reasonCode[1].coding).toEqual([
        { system: 'http://snomed.info/sct', display: 'Tos' },
      ]);

      const dxCond = resources.find((r: any) => r.resourceType === 'Condition' && r.code.text === 'Crisis hipertensiva');
      expect(dxCond.code.coding).toEqual([
        { system: 'http://snomed.info/sct', code: '706882009', display: 'Crisis hipertensiva' },
        { system: 'http://hl7.org/fhir/sid/icd-10', code: 'I16.9', display: 'Crisis hipertensiva' },
      ]);

      const medStmt = resources.find((r: any) => r.resourceType === 'MedicationStatement');
      expect(medStmt.medicationCodeableConcept.coding).toEqual([
        { system: 'http://snomed.info/sct', code: '373567002', display: 'Losartán' },
        { system: 'http://www.whocc.no/atc', code: 'C09CA01', display: 'Losartán' },
      ]);

      const allergy = resources.find((r: any) => r.resourceType === 'AllergyIntolerance');
      expect(allergy.code.coding).toEqual([
        { system: 'http://snomed.info/sct', code: '764146007', display: 'Penicilina' },
      ]);
    });

    it('emits ICD-10 and SNOMED CT codes in HL7 v2.5.1 DG1 and AL1 segments when normalized', () => {
      const segments = generateHL7v2Message(codedSession).split('\r');
      expect(segments).toContain('AL1|1||764146007^Penicilina^SNOMED-CT');
      expect(segments.some((s: string) => s.startsWith('DG1|1|I10|I16.9^Crisis hipertensiva^ICD-10|'))).toBe(true);
      expect(segments.some((s: string) => s.startsWith('DG1|2|I10|R07.4^Dolor torácico^ICD-10|'))).toBe(true);
    });
  });

});
