import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import ConfigPanel from '../../components/ConfigPanel';

describe('ConfigPanel Component', () => {
  const mockConfigData = {
    config: {
      active_asr_model: 'large-v3-turbo',
      active_llm_engine: 'gemini-2.5-flash',
      active_ner_model: 'ClinicalBERT (v2.1 - Recomendado)',
      snomed_version: 'SNOMED CT (Edicion en Espanol)',
      snomed_updated_at: '2026-09-10T12:00:00Z',
      icd10_version: 'ICD-10 (CIE-10)',
      icd10_updated_at: '2026-09-10T12:00:00Z',
    },
    api_keys: [
      {
        id: 1,
        provider: 'gemini',
        provider_display: 'Google Gemini',
        name: 'Gemini Primary Cloud',
        masked_key: '...90ab',
        is_active: true,
        created_at: '2026-09-10T10:00:00Z',
      },
    ],
  };

  beforeEach(() => {
    vi.restoreAllMocks();
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockConfigData,
    } as Response);
  });

  it('renders model selection and masked API keys on initial load', async () => {
    render(<ConfigPanel />);

    await waitFor(() => {
      expect(screen.getByText('Configuracion del Sistema y Motores IA')).toBeInTheDocument();
      expect(screen.getByText('Gemini Primary Cloud')).toBeInTheDocument();
      expect(screen.getByText('...90ab')).toBeInTheDocument();
      expect(screen.getByText('SNOMED CT (Edicion en Espanol)')).toBeInTheDocument();
    });
  });

  it('opens register modal when clicking Agregar Llave', async () => {
    render(<ConfigPanel />);

    await waitFor(() => {
      expect(screen.getByText('Agregar Llave')).toBeInTheDocument();
    });

    const addBtn = screen.getByText('Agregar Llave');
    fireEvent.click(addBtn);

    expect(screen.getByText('Registrar Llave API Cifrada')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Ej: Google Gemini Pro Produccion')).toBeInTheDocument();
  });

  it('autodetects provider as Google Gemini when entering an AIza key', async () => {
    render(<ConfigPanel />);

    await waitFor(() => {
      expect(screen.getByText('Agregar Llave')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Agregar Llave'));

    const keyInput = screen.getByPlaceholderText('AIzaSy... o sk-...');
    fireEvent.change(keyInput, { target: { value: 'AIzaSyDemoKey123456789' } });

    const geminiBadges = screen.getAllByText('Google Gemini');
    expect(geminiBadges.length).toBeGreaterThanOrEqual(2);
  });
});