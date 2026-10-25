import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import ConfigPanel from '../../components/ConfigPanel';

describe('ConfigPanel Component', () => {
  const mockConfigData = {
    config: {
      active_asr_model: 'large-v3-turbo',
      active_llm_engine: 'gemini-2.5-flash',
      active_ner_model: 'auto',
      snomed_version: 'SNOMED CT International Edition',
      snomed_updated_at: '2026-09-10T12:00:00Z',
      icd10_version: 'CIE-10 (OMS)',
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
    runtime_status: {
      cuda_available: false, hardware_device: 'CPU (INT8)', gemini_configured: true, active_keys_count: 1,
      system_timezone: 'America/Bogota', ner_status: { model_loaded: false, detail: 'NER_MODEL_PATH no definido' },
    },
    vocabularies: {
      snomed: {
        code: 'snomed_ct', title: 'SNOMED CT International Edition 20250201', provider: 'SNOMED International; verificado',
        updated_at: '2026-10-15T12:00:00Z', total_terms: 299, indexed_emergency_terms: 302,
        status: 'SUBCONJUNTO VERIFICADO', update_available: false, latest_release: '2026-10-15', token_notice: 'Sin tokens en el catalogo.',
      },
      icd10: {
        code: 'cie10_oms', title: 'CIE-10 (OMS)', provider: 'Subconjunto de la CIE-10', updated_at: '2026-10-15T12:00:00Z',
        total_terms: 188, indexed_emergency_terms: 242, status: 'SUBCONJUNTO', update_available: false,
        latest_release: '2026-10-15', token_notice: 'Sin tokens en el catalogo.',
      },
    },
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
      expect(screen.getByText('SNOMED CT International Edition 20250201')).toBeInTheDocument();
    });
  });

  it('shows real catalog figures instead of fixed demo numbers', async () => {
    render(<ConfigPanel />);

    await waitFor(() => {
      expect(screen.getByText('299')).toBeInTheDocument();
      expect(screen.getByText('188')).toBeInTheDocument();
      expect(screen.getByText('SUBCONJUNTO VERIFICADO')).toBeInTheDocument();
      expect(screen.getByText('Sin modelo: catalogo')).toBeInTheDocument();
    });
    expect(screen.queryByText('352.267')).not.toBeInTheDocument();
    expect(screen.queryByText(/ClinicalBERT|GPT-4o|Claude 3.5/)).not.toBeInTheDocument();
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

  it('muestra el estado del servidor LLM local y avisa del respaldo de reglas', async () => {
    const localData = {
      ...mockConfigData,
      config: { ...mockConfigData.config, active_llm_engine: 'local' },
      available_options: {
        asr_models: [{ id: 'auto', name: 'Segun entorno' }],
        llm_engines: [
          { id: 'gemini-2.5-flash', name: 'Google Gemini 2.5 Flash' },
          { id: 'local', name: 'LLM local (qwen2.5:7b-instruct-q4_K_M)' },
        ],
        ner_models: [{ id: 'auto', name: 'RoBERTa clinico + catalogo' }],
      },
      runtime_status: {
        ...mockConfigData.runtime_status,
        local_llm: { configured: true, reachable: false, model: 'qwen2.5:7b-instruct-q4_K_M', model_available: false },
      },
    };
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => localData } as Response);
    render(<ConfigPanel />);

    await waitFor(() => expect(screen.getByTestId('local-llm-status')).toHaveTextContent('Servidor local no disponible'));
    expect(screen.getByText('LLM local (qwen2.5:7b-instruct-q4_K_M)')).toBeInTheDocument();
    expect(screen.getByRole('alert')).toHaveTextContent('clasificará el motor de reglas');
  });

  it('permite elegir el modelo local entre los instalados en el servidor', async () => {
    const localData = {
      ...mockConfigData,
      config: { ...mockConfigData.config, active_llm_engine: 'local', local_llm_model: '' },
      available_options: {
        asr_models: [{ id: 'auto', name: 'Segun entorno' }],
        llm_engines: [{ id: 'local', name: 'LLM local (Ollama / servidor propio)' }],
        ner_models: [{ id: 'auto', name: 'RoBERTa clinico + catalogo' }],
        local_llm_models: ['gemma4:e4b-it-qat', 'qwen2.5:7b-instruct-q4_K_M'],
      },
      runtime_status: {
        ...mockConfigData.runtime_status,
        local_llm: { configured: true, reachable: true, model: 'qwen2.5:7b-instruct-q4_K_M', model_available: true,
                     models: ['gemma4:e4b-it-qat', 'qwen2.5:7b-instruct-q4_K_M'] },
      },
    };
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => localData } as Response);
    global.fetch = fetchMock;
    render(<ConfigPanel />);

    const select = await screen.findByLabelText('Modelo local');
    expect(select).toHaveValue('qwen2.5:7b-instruct-q4_K_M');
    fireEvent.change(select, { target: { value: 'gemma4:e4b-it-qat' } });
    expect(select).toHaveValue('gemma4:e4b-it-qat');

    fireEvent.click(screen.getByRole('button', { name: /guardar/i }));
    await waitFor(() => {
      const post = fetchMock.mock.calls.find(([url, init]) =>
        String(url).endsWith('/api/config/') && (init as RequestInit | undefined)?.method === 'POST');
      expect(post).toBeTruthy();
      expect(JSON.parse(String((post![1] as RequestInit).body)).local_llm_model).toBe('gemma4:e4b-it-qat');
    });
  });
});
