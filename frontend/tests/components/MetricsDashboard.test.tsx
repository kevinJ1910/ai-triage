import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import MetricsDashboard from '../../components/MetricsDashboard';

describe('MetricsDashboard Component', () => {
  const mockMetrics = {
    total_triages: 10,
    concordance_rate: 90.0,
    severity_drift: 0.1,
    symptom_retention: 95.0,
    cohen_kappa: 0.88,
    kappa_interpretation: 'Concordancia casi perfecta (Landis & Koch)',
    modified_count: 1,
    unmodified_count: 9,
    distribution_ai: { 1: 1, 2: 3, 3: 4, 4: 2, 5: 0 },
    distribution_physician: { 1: 1, 2: 4, 3: 3, 4: 2, 5: 0 },
    recent_evaluations: [
      {
        id: 1,
        patient: 'Paciente Uno',
        ai_level: 2,
        final_level: 2,
        is_modified: false,
        agreement_score: 1.0,
        date: '2026-09-10 10:00',
      },
      {
        id: 2,
        patient: 'Paciente Dos',
        ai_level: 3,
        final_level: 2,
        is_modified: true,
        agreement_score: 0.75,
        date: '2026-09-10 11:00',
      },
    ],
  };

  beforeEach(() => {
    vi.restoreAllMocks();
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/api/triage/sessions/evaluation_metrics/')) {
        return Promise.resolve({
          ok: true,
          json: async () => mockMetrics,
        } as Response);
      }
      return Promise.resolve({
        ok: false,
        json: async () => ({}),
      } as Response);
    });
  });

  it('renders clinical metrics overview, concordance rate, and kappa index', async () => {
    render(<MetricsDashboard />);

    await waitFor(() => {
      expect(screen.getByText('Panel de Evaluacion Clinica y Metricas de Triaje')).toBeInTheDocument();
      expect(screen.getByText('90%')).toBeInTheDocument();
      expect(screen.getAllByText('0.88').length).toBeGreaterThan(0);
      expect(screen.getByText('Concordancia casi perfecta (Landis & Koch)')).toBeInTheDocument();
      expect(screen.getByText('+0.1')).toBeInTheDocument();
      expect(screen.getByText('95%')).toBeInTheDocument();
    });
  });

  it('shows triage safety metrics (under/overtriage, critical sensitivity)', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        ...mockMetrics,
        undertriage_rate: 12.5,
        overtriage_rate: 7.5,
        critical_cases: 4,
        critical_sensitivity: 75.0,
        critical_undertriage_count: 1,
      }),
    } as Response);
    render(<MetricsDashboard />);

    await waitFor(() => {
      expect(screen.getByText('12.5%')).toBeInTheDocument();
      expect(screen.getByText('7.5%')).toBeInTheDocument();
      expect(screen.getByText('75%')).toBeInTheDocument();
      expect(screen.getByText(/1 de 4 casos criticos/)).toBeInTheDocument();
    });
  });

  it('shows a placeholder instead of fabricated values when there is no data', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        ...mockMetrics,
        total_triages: 0,
        concordance_rate: null,
        severity_drift: null,
        symptom_retention: null,
        cohen_kappa: null,
        kappa_interpretation: 'Sin datos suficientes',
        undertriage_rate: null,
        overtriage_rate: null,
        critical_sensitivity: null,
        recent_evaluations: [],
      }),
    } as Response);
    render(<MetricsDashboard />);

    await waitFor(() => {
      expect(screen.getByText('Sin datos suficientes')).toBeInTheDocument();
      expect(screen.getAllByText('—').length).toBeGreaterThanOrEqual(7);
      expect(screen.queryByText('0.88')).not.toBeInTheDocument();
    });
  });

  it('renders recent evaluation sessions table', async () => {
    render(<MetricsDashboard />);

    await waitFor(() => {
      expect(screen.getByText('Paciente Uno')).toBeInTheDocument();
      expect(screen.getByText('Paciente Dos')).toBeInTheDocument();
    });
  });

  it('triggers metrics refresh when clicking recalculate button', async () => {
    render(<MetricsDashboard />);

    await waitFor(() => {
      expect(screen.getByText('Recalcular Metricas')).toBeInTheDocument();
    });

    const refreshBtn = screen.getByText('Recalcular Metricas');
    fireEvent.click(refreshBtn);

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        '/api/triage/sessions/evaluation_metrics/',
        expect.any(Object)
      );
    });
  });
  it('muestra la validacion contra el nivel de referencia ciego', async () => {
    const agreement = (exact: number, under: number) => ({
      n: 4, exact_agreement: exact, cohen_kappa: 0.61, kappa_interpretation: 'Concordancia sustancial',
      undertriage_rate: under, overtriage_rate: 0, critical_cases: 2, critical_sensitivity: 50.0,
      critical_undertriage_count: 1,
    });
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        ...mockMetrics,
        reference_validation: {
          referenced_count: 4,
          ai_vs_reference: agreement(62.5, 37.5),
          physician_vs_reference: agreement(87.5, 12.5),
        },
      }),
    } as Response);
    render(<MetricsDashboard />);

    await waitFor(() => {
      expect(screen.getByText('4 de 10 casos adjudicados')).toBeInTheDocument();
      expect(screen.getByText('62.5%')).toBeInTheDocument();
      expect(screen.getByText('87.5%')).toBeInTheDocument();
      expect(screen.getByText('37.5%')).toBeInTheDocument();
    });
  });

  it('indica cuando aun no hay casos adjudicados', async () => {
    render(<MetricsDashboard />);
    await waitFor(() => {
      expect(screen.getByText(/Aún no hay casos adjudicados/)).toBeInTheDocument();
    });
  });
});
