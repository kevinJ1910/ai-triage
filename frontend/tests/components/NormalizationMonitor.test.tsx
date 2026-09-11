import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import NormalizationMonitor from '../../components/NormalizationMonitor';

describe('NormalizationMonitor Component', () => {
  const mockNormalizationResponse = {
    normalized_text: 'Paciente refiere dolor toracico y disnea.',
    summary: 'Sindrome coronario evaluado.',
    mappings: [
      {
        raw_term: 'dolor de pecho',
        medical_term: 'dolor toracico',
        code_snomed: '29857009',
        category: 'Sintoma',
      },
      {
        raw_term: 'falta de aire',
        medical_term: 'disnea',
        code_snomed: '267036007',
        category: 'Sintoma',
      },
      {
        raw_term: 'aspirina',
        medical_term: 'acido acetilsalicilico',
        code_snomed: '387458008',
        category: 'Medicamento',
      },
    ],
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

  it('renders normalization monitor and initial SNOMED-CT mappings', () => {
    render(<NormalizationMonitor />);

    expect(screen.getByText('Motor de Normalizacion Clinica')).toBeInTheDocument();
    expect(screen.getByText('opresion toracica')).toBeInTheDocument();
    expect(screen.getByText('29857009')).toBeInTheDocument();
  });

  it('filters mappings by category button', () => {
    render(<NormalizationMonitor />);

    // Click on 'Medicamento' filter button
    const medFilterBtn = screen.getByRole('button', { name: 'Medicamento' });
    fireEvent.click(medFilterBtn);

    expect(screen.getByText('losartan potasico')).toBeInTheDocument();
    expect(screen.queryByText('disnea de medianos esfuerzos')).not.toBeInTheDocument();
  });

  it('sends normalization request on button click and updates mappings', async () => {
    render(<NormalizationMonitor />);

    const runBtn = screen.getByRole('button', { name: /Normalizar Terminologia/i });
    fireEvent.click(runBtn);

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        '/api/transcribe/normalize/',
        expect.objectContaining({
          method: 'POST',
        })
      );
      expect(screen.getByText('acido acetilsalicilico')).toBeInTheDocument();
      expect(screen.getByText('387458008')).toBeInTheDocument();
    });
  });
});
