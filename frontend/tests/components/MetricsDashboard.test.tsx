import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
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
});
