import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import NormalizationMonitor from '../../components/NormalizationMonitor';

describe('NormalizationMonitor Component', () => {
  const mapping = (overrides: Record<string, unknown>) => ({
    code_system: 'CIE-10',
    code_snomed: null,
    snomed_valid: null,
    category: 'Sintoma',
    source: 'diccionario',
    valid: true,
    negated: false,
    allergy: false,
    ...overrides,
  });

  const mockNormalizationResponse = {
    normalized_text: 'Paciente refiere dolor torácico y niega fiebre.',
    summary: 'Dolor torácico sin fiebre.',
    mappings: [
      mapping({ raw_term: 'dolor de pecho', medical_term: 'dolor torácico', code: 'R07.4', code_snomed: '29857009', snomed_valid: true }),
      mapping({ raw_term: 'fiebre', medical_term: 'fiebre', code: 'R50.9', category: 'Signo', negated: true }),
      mapping({ raw_term: 'aspirina', medical_term: 'ácido acetilsalicílico', code: 'B01AC06', code_system: 'ATC', category: 'Medicamento' }),
      mapping({ raw_term: 'dolor punzante en el talón', medical_term: 'talalgia', code: 'M79.67', code_snomed: '267036008', source: 'llm', valid: false, snomed_valid: false }),
      mapping({ raw_term: 'penicilina', medical_term: 'penicilina', code: 'J01CE01', code_system: 'ATC', category: 'Medicamento', allergy: true }),
    ],
    layers: { correccion_asr: 0, abreviatura: 0, diccionario: 4, llm: 1 },
    engine: 'Catálogo terminológico local + LLM (gemini-3.5-flash-lite)',
  };

  beforeEach(() => {
    vi.restoreAllMocks();
    global.fetch = vi.fn().mockImplementation((url: string, options?: any) => {
      if (url.includes('/api/transcribe/normalize/') && options?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => mockNormalizationResponse,
        } as Response);
      }
      return Promise.resolve({
        ok: false,
        json: async () => ({}),
      } as Response);
    });
  });

  it('renders the initial catalog result with SNOMED-CT and CIE-10 codes', () => {
    render(<NormalizationMonitor />);

    expect(screen.getByText('Motor de Normalizacion Clinica')).toBeInTheDocument();
    expect(screen.getByText('SNOMED-CT / CIE-10 / ATC')).toBeInTheDocument();
    expect(screen.getByText('dolor torácico opresivo')).toBeInTheDocument();
    expect(screen.getByText('R07.4')).toBeInTheDocument();
    expect(screen.getByText('23924001')).toBeInTheDocument();
    expect(screen.getByText('Corrección ASR')).toBeInTheDocument();
  });

  it('filters mappings by category button', () => {
    render(<NormalizationMonitor />);

    fireEvent.click(screen.getByRole('button', { name: 'Medicamento' }));

    expect(screen.getByText('losartán')).toBeInTheDocument();
    expect(screen.queryByText('disnea')).not.toBeInTheDocument();
  });

  it('sends normalization request and shows layer, validity, negation and allergy', async () => {
    render(<NormalizationMonitor />);

    fireEvent.click(screen.getByRole('button', { name: /Normalizar Terminologia/i }));

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        '/api/transcribe/normalize/',
        expect.objectContaining({ method: 'POST' })
      );
      expect(screen.getByText('ácido acetilsalicílico')).toBeInTheDocument();
    });
    expect(screen.getByText('B01AC06')).toBeInTheDocument();
    expect(screen.getByText('29857009')).toBeInTheDocument();
    // El talón del LLM trae CIE-10 y SNOMED invalidos: ambos se marcan.
    expect(screen.getAllByText('inválido')).toHaveLength(2);
    expect(screen.getByText('negado')).toBeInTheDocument();
    expect(screen.getByText('alergia')).toBeInTheDocument();
    expect(screen.getByText(/LLM: 1/)).toBeInTheDocument();
    expect(screen.getByText('Catálogo terminológico local + LLM (gemini-3.5-flash-lite)')).toBeInTheDocument();
  });
});
