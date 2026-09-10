import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import EMRSimulator from '../../components/EMRSimulator';

describe('EMRSimulator Component', () => {
  const mockPatients = [
    {
      id: 1,
      patient_id: 10,
      document_id: '1098765432',
      name: 'Maria Elena Gomez',
      gender: 'Femenino',
      birth_date: '1985-04-12',
      phone: '+573105558899',
      insurance: 'EPS Sanitas',
      level: 2,
      ai_level: 2,
      assigned_box: 'BOX-01',
      status: 'En Espera',
      admission_time: '14:20',
      justification: 'Dolor toracico opresivo con irradiacion al brazo izquierdo.',
      entities: {
        symptoms: ['Dolor toracico', 'Diaforesis', 'Disnea'],
        vitals: {
          ta: '145/95',
          fc: '102 lpm',
          spo2: '94%',
          temp: '36.8 C',
        },
      },
    },
    {
      id: 2,
      patient_id: 11,
      document_id: '80123456',
      name: 'Jorge Ramirez',
      gender: 'Masculino',
      birth_date: '1972-11-05',
      phone: '+573151112233',
      insurance: 'Sura EPS',
      level: 4,
      ai_level: 4,
      assigned_box: '',
      status: 'Triaje Completado',
      admission_time: '14:35',
      justification: 'Cuadro de rinitis y odinofagia leve de 3 dias de evolucion.',
      entities: {
        symptoms: ['Rinorrea', 'Congestion nasal'],
        vitals: {
          ta: '120/80',
          fc: '75 lpm',
          spo2: '98%',
          temp: '37.0 C',
        },
      },
    },
  ];

  beforeEach(() => {
    vi.restoreAllMocks();
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/api/triage/sessions/emr_patients/')) {
        return Promise.resolve({
          ok: true,
          json: async () => mockPatients,
        } as Response);
      }
      return Promise.resolve({
        ok: false,
        json: async () => ({}),
      } as Response);
    });
  });

  it('renders EMR simulator and displays patients queue', async () => {
    render(<EMRSimulator />);

    await waitFor(() => {
      expect(screen.getByText('Simulador HCE / HIS Clinico Integrado')).toBeInTheDocument();
      expect(screen.getAllByText('Maria Elena Gomez').length).toBeGreaterThan(0);
      expect(screen.getAllByText('Jorge Ramirez').length).toBeGreaterThan(0);
      expect(screen.getAllByText(/1098765432/).length).toBeGreaterThan(0);
    });
  });

  it('filters patients in the queue by search query', async () => {
    render(<EMRSimulator />);

    await waitFor(() => {
      expect(screen.getAllByText('Maria Elena Gomez').length).toBeGreaterThan(0);
      expect(screen.getAllByText('Jorge Ramirez').length).toBeGreaterThan(0);
    });

    const searchInput = screen.getByPlaceholderText('Buscar por nombre o cedula...');
    fireEvent.change(searchInput, { target: { value: 'Jorge' } });

    await waitFor(() => {
      // Maria should no longer be in the filtered left list (only Jorge is displayed)
      const matches = screen.queryAllByText('Jorge Ramirez');
      expect(matches.length).toBeGreaterThan(0);
    });
  });

  it('selects a patient and displays their clinical record and vitals', async () => {
    render(<EMRSimulator />);

    await waitFor(() => {
      expect(screen.getAllByText('Maria Elena Gomez').length).toBeGreaterThan(0);
    });

    // Default first patient is selected
    expect(screen.getByText('Dolor toracico opresivo con irradiacion al brazo izquierdo.')).toBeInTheDocument();
    expect(screen.getByText('145/95')).toBeInTheDocument();
    expect(screen.getByText('102 lpm')).toBeInTheDocument();

    // Click on second patient in queue
    const jorgeCards = screen.getAllByText('Jorge Ramirez');
    fireEvent.click(jorgeCards[0]);

    await waitFor(() => {
      expect(screen.getByText('Cuadro de rinitis y odinofagia leve de 3 dias de evolucion.')).toBeInTheDocument();
      expect(screen.getByText('120/80')).toBeInTheDocument();
      expect(screen.getByText('75 lpm')).toBeInTheDocument();
    });
  });
});
