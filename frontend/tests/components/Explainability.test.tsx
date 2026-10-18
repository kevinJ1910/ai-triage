import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import ExplainabilityPanel from '../../components/ExplainabilityPanel';

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
