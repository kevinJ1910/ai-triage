import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import EMRSimulator from '../../components/EMRSimulator';

vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

describe('EMRSimulator Component (HCE FHIR R4 / HL7 v2 Receiver)', () => {
  const mockPatients = [
    {
      id: 1,
      patient_id: 10,
      document_id: '1098765432',
      name: 'Maria Elena Gomez',
      gender: 'female',
      birth_date: '1985-04-12',
      phone: '+573105558899',
      insurance: 'EPS Sanitas',
      created_at: '2026-10-25T14:20:00-05:00',
      admission_time: '2026-10-25 14:20',
      level: 2,
      ai_level: 2,
      is_level_modified: false,
      status: 'Pendiente de Recepcion',
      justification: 'Dolor toracico opresivo con irradiacion al brazo izquierdo.',
      transcript: 'Medico: Que siente\nPaciente: Dolor en el pecho',
      engine_used: 'gemma4:e4b-it-qat',
      fhir_synced: false,
      fhir_resource_id: '',
      fhir_synced_at: null,
      fhir_bundle: null,
      entities: {
        symptoms: ['Dolor toracico', 'Diaforesis', 'Disnea'],
        vitals: ['PA: 145/95 mmHg', 'FC: 102 lpm', 'SpO2: 94%', 'T: 36.8°C'],
        allergies: ['Penicilina'],
        medications: ['Losartan 50 mg'],
        history: ['Hipertension arterial'],
        negated_findings: ['Fiebre'],
      },
    },
    {
      id: 2,
      patient_id: 11,
      document_id: '80123456',
      name: 'Jorge Ramirez',
      gender: 'male',
      birth_date: '1972-11-05',
      phone: '+573151112233',
      insurance: 'Sura EPS',
      created_at: '2026-10-25T14:35:00-05:00',
      admission_time: '2026-10-25 14:35',
      level: 4,
      ai_level: 4,
      is_level_modified: false,
      status: 'Recibido en HCE',
      justification: 'Cuadro de rinitis y odinofagia leve de 3 dias de evolucion.',
      transcript: 'Paciente: Tengo congestion nasal hace tres dias',
      engine_used: 'gemma4:e4b-it-qat',
      fhir_synced: true,
      fhir_resource_id: 'fhir-enc-8899',
      fhir_synced_at: '2026-10-25 14:36:10',
      fhir_bundle: null,
      entities: {
        symptoms: ['Rinorrea', 'Congestion nasal'],
        vitals: ['PA: 120/80 mmHg', 'FC: 75 lpm', 'SpO2: 98%', 'T: 37.0°C'],
      },
    },
  ];

  beforeEach(() => {
    vi.restoreAllMocks();
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/api/triage/sessions/emr_patients/')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => mockPatients,
        } as Response);
      }
      return Promise.resolve({
        ok: false,
        status: 404,
        json: async () => ({}),
      } as Response);
    });
  });

  it('renders HCE simulator queue and FHIR counters', async () => {
    render(<EMRSimulator />);

    await waitFor(() => {
      expect(screen.getByText('Simulador de Historia Clínica Electrónica (HCE)')).toBeInTheDocument();
      expect(screen.getAllByText('Maria Elena Gomez').length).toBeGreaterThan(0);
      expect(screen.getAllByText('Jorge Ramirez').length).toBeGreaterThan(0);
      expect(screen.getByText('2 admisiones')).toBeInTheDocument();
      expect(screen.getByText('1 FHIR R4')).toBeInTheDocument();
    });
  });

  it('filters patients by search query and FHIR synchronization state', async () => {
    render(<EMRSimulator />);

    await waitFor(() => {
      expect(screen.getAllByText('Maria Elena Gomez').length).toBeGreaterThan(0);
    });

    const searchInput = screen.getByPlaceholderText('Buscar por nombre, documento o ID FHIR...');
    fireEvent.change(searchInput, { target: { value: 'fhir-enc-8899' } });

    await waitFor(() => {
      expect(screen.getAllByText('Jorge Ramirez').length).toBeGreaterThan(0);
    });

    fireEvent.change(searchInput, { target: { value: '' } });
    fireEvent.click(screen.getByRole('button', { name: 'FHIR Activo' }));

    await waitFor(() => {
      expect(screen.getAllByText('Jorge Ramirez').length).toBeGreaterThan(0);
    });
  });

  it('displays structured clinical entities and localized patient demographics', async () => {
    render(<EMRSimulator />);

    await waitFor(() => {
      expect(screen.getAllByText('Maria Elena Gomez').length).toBeGreaterThan(0);
    });

    expect(screen.getByText('Femenino')).toBeInTheDocument();
    expect(screen.getByText('Dolor toracico opresivo con irradiacion al brazo izquierdo.')).toBeInTheDocument();
    expect(screen.getByText('145/95 mmHg')).toBeInTheDocument();
    expect(screen.getByText('102 lpm')).toBeInTheDocument();
    expect(screen.getByText('Penicilina')).toBeInTheDocument();
    expect(screen.getByText('Losartan 50 mg')).toBeInTheDocument();
    expect(screen.getByText('Hipertension arterial')).toBeInTheDocument();
    expect(screen.getByText('Fiebre')).toBeInTheDocument();

    fireEvent.click(screen.getAllByText('Jorge Ramirez')[0]);

    await waitFor(() => {
      expect(screen.getByText('Cuadro de rinitis y odinofagia leve de 3 dias de evolucion.')).toBeInTheDocument();
      expect(screen.getByText('ID FHIR: fhir-enc-8899')).toBeInTheDocument();
      expect(screen.getByText('No referidas')).toBeInTheDocument();
    });
  });

  it('synchronizes selected patient admission via HL7 FHIR R4 POST /api/fhir/', async () => {
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/api/triage/sessions/emr_patients/')) {
        return Promise.resolve({ ok: true, status: 200, json: async () => mockPatients } as Response);
      }
      if (url.includes('/api/fhir/')) {
        return Promise.resolve({
          ok: true,
          status: 201,
          json: async () => ({ id: 'fhir-enc-nuevo-101', message: 'Resource created' }),
        } as Response);
      }
      return Promise.resolve({ ok: false, status: 404, json: async () => ({}) } as Response);
    });

    render(<EMRSimulator />);
    await waitFor(() => expect(screen.getAllByText('Maria Elena Gomez').length).toBeGreaterThan(0));

    fireEvent.click(screen.getByRole('button', { name: /Sincronizar con HCE \(FHIR R4\)/i }));

    await waitFor(() => {
      expect(screen.getByText('ID FHIR: fhir-enc-nuevo-101')).toBeInTheDocument();
    });

    const fhirCall = (global.fetch as ReturnType<typeof vi.fn>).mock.calls.find(([url]) =>
      String(url).includes('/api/fhir/')
    );
    expect(fhirCall).toBeDefined();
    const sentBundle = JSON.parse(fhirCall![1].body);
    expect(sentBundle.resourceType).toBe('Bundle');
    expect(sentBundle.entry.some((e: { resource: { id: string } }) => e.resource.id === 'enc-1')).toBe(true);
  });

  it('saves HCE reception status and clinical evolution notes', async () => {
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/api/triage/sessions/emr_patients/')) {
        return Promise.resolve({ ok: true, status: 200, json: async () => mockPatients } as Response);
      }
      if (url.includes('/update_care_status/')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({ status: 'En Atencion', evolution_notes: 'Monitorizacion ECG continua' }),
        } as Response);
      }
      return Promise.resolve({ ok: false, status: 404, json: async () => ({}) } as Response);
    });

    render(<EMRSimulator />);
    await waitFor(() => expect(screen.getAllByText('Maria Elena Gomez').length).toBeGreaterThan(0));

    fireEvent.change(screen.getByLabelText('Estado asistencial en HCE'), {
      target: { value: 'En Atencion' },
    });
    fireEvent.change(screen.getByLabelText('Notas de recepción / evolución médica'), {
      target: { value: 'Monitorizacion ECG continua' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Guardar en HCE/i }));

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/triage/sessions/1/update_care_status/'),
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({
            status: 'En Atencion',
            evolution_notes: 'Monitorizacion ECG continua',
          }),
        })
      );
    });
  });

  it('inspects FHIR R4 JSON Bundle and HL7 v2.5.1 ADT^A08 ER7 message', async () => {
    render(<EMRSimulator />);
    await waitFor(() => expect(screen.getAllByText('Maria Elena Gomez').length).toBeGreaterThan(0));

    fireEvent.click(screen.getByRole('tab', { name: /Interoperabilidad \(FHIR R4 \/ HL7 v2\)/i }));

    await waitFor(() => {
      expect(screen.getByText(/Encounter \(1\)/)).toBeInTheDocument();
      expect(screen.getByText(/"resourceType": "Bundle"/)).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /Mensaje HL7 v2\.5\.1/i }));

    await waitFor(() => {
      expect(screen.getByText(/MSH\|\^~\\&\|AI_TRIAGE/)).toBeInTheDocument();
    });
  });

  it('supports mobile navigation back to admissions queue', async () => {
    render(<EMRSimulator />);
    await waitFor(() => expect(screen.getAllByText('Maria Elena Gomez').length).toBeGreaterThan(0));

    fireEvent.click(screen.getAllByText('Jorge Ramirez')[0]);
    const backBtn = screen.getByRole('button', { name: /Volver a Cola de Admisiones/i });
    expect(backBtn).toBeInTheDocument();
    fireEvent.click(backBtn);
  });
});
