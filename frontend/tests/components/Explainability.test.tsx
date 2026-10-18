import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import ExplainabilityPanel from '../../components/ExplainabilityPanel';
import EngineStatus, { ENGINES_CHANGED_EVENT } from '../../components/EngineStatus';
import EvaluationResults from '../../components/EvaluationResults';

const analysis = {
  engine_used: 'LLM (gemini-2.5-flash) + Christus Sinergia',
  ner_engine: 'roberta:ai_triage_ner_roberta',
  rag_criteria: [
    { id: 'c2_chest_pain_sca', level: 2, name: 'Emergencia', criterion: 'Dolor torácico típico de síndrome coronario.' },
  ],
  normalized_terms: [
    { raw_term: 'dolor en el pecho', medical_term: 'Dolor torácico', code: 'R07.4', code_system: 'CIE-10',
      code_snomed: '29857009', snomed_valid: true, source: 'diccionario', valid: true, negated: false, allergy: false },
    { raw_term: 'mareo', medical_term: 'Mareo', code: 'X99.9', code_system: 'CIE-10', code_snomed: null,
      snomed_valid: false, source: 'llm', valid: false, negated: true, allergy: false },
  ],
  ner_spans: [
    { text: 'dolor en el pecho', label: 'SINTOMA', score: 0.97, kept: true, confirmed_by: ['catalogo'] },
    { text: 'ayer', label: 'SINTOMA', score: 0.31, kept: false, confirmed_by: [] },
  ],
};

describe('ExplainabilityPanel', () => {
  it('resume y despliega criterios, códigos verificados y menciones del NER', () => {
    render(<ExplainabilityPanel analysis={analysis} />);
    expect(screen.getByText(/1 criterios · 2 códigos · NER: RoBERTa/)).toBeInTheDocument();
    expect(screen.queryByText('Dolor torácico')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /En qué se basa este resultado/ }));
    expect(screen.getByText(/Dolor torácico típico de síndrome coronario/)).toBeInTheDocument();
    expect(screen.getByText('R07.4').closest('span')).toHaveAttribute('title', 'Código verificado en el catálogo');
    expect(screen.getByText('X99.9').closest('span')).toHaveAttribute('title', 'Código no verificado');
    expect(screen.getByText('negado')).toBeInTheDocument();
    expect(screen.getByText(/RoBERTa clínico \(ai_triage_ner_roberta\)/)).toBeInTheDocument();
    expect(screen.getByText(/ayer · Síntoma · 31%/)).toHaveClass('line-through');
  });

  it('indica el respaldo cuando no hay modelo NER', () => {
    render(<ExplainabilityPanel analysis={{ engine_used: 'Motor de Reglas Clínico (Christus Sinergia)', ner_engine: null }} />);
    fireEvent.click(screen.getByRole('button', { name: /En qué se basa este resultado/ }));
    expect(screen.getByText(/sin modelo, se usan el catálogo y el LLM/)).toBeInTheDocument();
    expect(screen.getByText(/No hay criterios registrados/)).toBeInTheDocument();
  });
});

describe('ExplainabilityPanel desde el historial', () => {
  it('no atribuye el resultado al respaldo cuando los datos no se guardaron', () => {
    render(<ExplainabilityPanel analysis={{ engine_used: 'Motor de reglas', rag_criteria: analysis.rag_criteria }} />);
    expect(screen.getByText('1 criterios · historial')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /En qué se basa este resultado/ }));
    expect(screen.queryByText(/sin modelo/)).not.toBeInTheDocument();
    expect(screen.getByText(/no se guardan en el historial/)).toBeInTheDocument();
  });
});

describe('EngineStatus', () => {
  it('muestra cada motor y si se usa el respaldo, sin la clave', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true, status: 200,
      json: async () => ({
        inference_mode: 'worker',
        asr: { model_loaded: true, model_size: 'small', device: 'cpu' },
        ner: { model_loaded: false, detail: 'NER_MODEL_PATH no definido' },
        llm: { configured: false, model: 'gemini-2.5-flash' },
      }),
    } as Response);
    render(<EngineStatus />);
    await waitFor(() => expect(screen.getByText('Whisper small · CPU')).toBeInTheDocument());
    expect(screen.getByText('Respaldo (catálogo)')).toBeInTheDocument();
    expect(screen.getByText('Sin clave: reglas')).toBeInTheDocument();
    const urls = (global.fetch as ReturnType<typeof vi.fn>).mock.calls.map(([url]) => String(url));
    expect(urls.some(url => url.includes('/api/config/engines/'))).toBe(true);
  });
});

describe('EngineStatus con el LLM local', () => {
  const status = (configured: boolean) => ({
    ok: true, status: 200,
    json: async () => ({
      inference_mode: 'worker',
      asr: { model_loaded: true, model_size: 'small', device: 'cpu' },
      ner: { model_loaded: true, active: true },
      llm: { provider: 'local', configured, model: 'qwen2.5:7b-instruct-q4_K_M' },
    }),
  } as Response);

  it('muestra el modelo local cuando el servidor responde', async () => {
    global.fetch = vi.fn().mockResolvedValue(status(true));
    render(<EngineStatus />);
    await waitFor(() => expect(screen.getByText('Local · qwen2.5:7b-instruct-q4_K_M')).toBeInTheDocument());
  });

  it('avisa del respaldo de reglas cuando el servidor local no responde', async () => {
    global.fetch = vi.fn().mockResolvedValue(status(false));
    render(<EngineStatus />);
    await waitFor(() => expect(screen.getByText('Local no disponible: reglas')).toBeInTheDocument());
  });
});

describe('EngineStatus tras cambiar la configuración', () => {
  const status = (asr: object, ner: object) => ({
    ok: true, status: 200,
    json: async () => ({ inference_mode: 'worker', asr, ner, llm: { configured: true, model: 'gemini-2.5-flash' } }),
  } as Response);

  it('muestra el modo solo catálogo aunque RoBERTa siga cargado y la recarga del ASR', async () => {
    global.fetch = vi.fn().mockResolvedValue(status(
      { model_loaded: true, loading: false, model_size: 'small', device: 'cpu', configured: 'base', requested: 'small' },
      { model_loaded: true, active: false, mode: 'catalogo' },
    ));
    render(<EngineStatus />);
    await waitFor(() => expect(screen.getByText('Solo catálogo y LLM')).toBeInTheDocument());
    expect(screen.getByText('Cargando Whisper base…')).toBeInTheDocument();
  });

  it('se refresca al guardar la configuración y avisa si se cargó un respaldo', async () => {
    const fetchMock = vi.fn().mockResolvedValue(status(
      { model_loaded: true, model_size: 'small', device: 'cpu', configured: 'auto', requested: 'small' },
      { model_loaded: true, active: true, mode: 'auto' },
    ));
    global.fetch = fetchMock;
    render(<EngineStatus />);
    await waitFor(() => expect(screen.getByText('Whisper small · CPU')).toBeInTheDocument());

    fetchMock.mockResolvedValue(status(
      { model_loaded: true, model_size: 'small', device: 'cpu', configured: 'large-v3', requested: 'large-v3' },
      { model_loaded: true, active: true, mode: 'auto' },
    ));
    window.dispatchEvent(new Event(ENGINES_CHANGED_EVENT));
    await waitFor(() => expect(screen.getByTitle(/No se pudo cargar Whisper large-v3/)).toBeInTheDocument());
  });
});

describe('EvaluationResults', () => {
  it('muestra las corridas guardadas de extracción y de ASR', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true, status: 200,
      json: async () => ({
        extraction: [{
          name: 'test_hibrido', updated_at: '2026-10-17T00:00:00Z', engine: 'hibrido', model: null, ner_engine: null,
          split: 'test', match: 'relaxed', cases: 60,
          entities: { precision: 0.8, recall: 0.7, f1: 0.751, f1_ci95: [0.7, 0.796], macro_f1: 0.818,
                      by_type: { symptoms: 0.8 }, negation_accuracy: 1, cie10_accuracy: 0.839 },
          triage: { n: 60, exact_agreement: 50, cohen_kappa: 0.6, cohen_kappa_ci95: [0.4, 0.8],
                    critical_sensitivity: 80, critical_sensitivity_ci95: [60, 92], undertriage_rate: 10, overtriage_rate: 5 },
          performance: { latency_ms_mean: 900 },
        }],
        asr: [{
          name: 'resultado_small_cpu', updated_at: '2026-10-17T00:00:00Z', model_size: 'small', device: 'cpu',
          chunk_seconds: 4, initial_prompt: true,
          global: { audios: 40, wer: 0.12, cer: 0.05, error_terminos_clinicos: 0.1, rtf: 1.3, latencia_media_s: 5 },
          by_condition: { ruido: { audios: 20, wer: 0.2, cer: 0.1, error_terminos_clinicos: 0.2, rtf: 1.3, latencia_media_s: 5 } },
        }],
      }),
    } as Response);
    render(<EvaluationResults />);
    await waitFor(() => expect(screen.getByText('test_hibrido')).toBeInTheDocument());
    expect(screen.getByText('[0.700–0.796]')).toBeInTheDocument();
    expect(screen.getByText('83.9%')).toBeInTheDocument();
    expect(screen.getByText('resultado_small_cpu')).toBeInTheDocument();
    expect(screen.getByText('ruido: 20.0%')).toBeInTheDocument();
  });

  it('explica cómo generar resultados cuando no hay', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({ extraction: [], asr: [] }) } as Response);
    render(<EvaluationResults />);
    await waitFor(() => expect(screen.getByText(/Aún no hay corridas guardadas/)).toBeInTheDocument());
    expect(screen.getByText(/Aún no hay mediciones de WER/)).toBeInTheDocument();
  });
});
