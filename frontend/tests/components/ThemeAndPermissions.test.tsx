import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import AppNavigation from '../../components/AppNavigation';
import { setAccessToken } from '../../lib/api';

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), prefetch: vi.fn() }),
}));
vi.mock('@/components/TriageDashboard', () => ({ default: () => <div data-testid="TriageDashboard-view" /> }));
vi.mock('@/components/ConfigPanel', () => ({ default: () => <div data-testid="ConfigPanel-view" /> }));
vi.mock('@/components/SecurityPanel', () => ({ default: () => <div data-testid="SecurityPanel-view" /> }));
vi.mock('@/components/NormalizationMonitor', () => ({ default: () => <div data-testid="NormalizationMonitor-view" /> }));
vi.mock('@/components/FHIRMonitor', () => ({ default: () => <div data-testid="FHIRMonitor-view" /> }));
vi.mock('@/components/EMRSimulator', () => ({ default: () => <div data-testid="EMRSimulator-view" /> }));
vi.mock('@/components/MetricsDashboard', () => ({ default: () => <div data-testid="MetricsDashboard-view" /> }));
vi.mock('@/components/BlindReview', () => ({ default: () => <div data-testid="BlindReview-view" /> }));

const nurse = {
  id: 2, email: 'enfermera@hospital.com', first_name: 'Ana', last_name: 'Gil', full_name: 'Ana Gil', role: 'enfermero',
  permissions: {
    can_use_transcriber: true, can_edit_symptoms: false, can_register_patients: true,
    can_view_emr: false, can_view_fhir: false, can_manage_config: false,
  },
};

describe('Menú según permisos', () => {
  beforeEach(() => {
    localStorage.clear();
    setAccessToken('token');
  });

  it('oculta los paneles que el servidor no permite al rol', async () => {
    global.fetch = vi.fn().mockImplementation((url: string) =>
      Promise.resolve(url.includes('/api/auth/me/')
        ? ({ ok: true, status: 200, json: async () => nurse } as Response)
        : ({ ok: false, status: 403, json: async () => ({}) } as Response)));
    render(<AppNavigation />);

    await waitFor(() => expect(screen.getAllByText('Modulo de Triaje').length).toBeGreaterThan(0));
    expect(screen.getAllByText('Monitor Normalizacion').length).toBeGreaterThan(0);
    for (const hidden of ['Simulador HCE', 'Validacion Ciega', 'Monitor FHIR/HL7', 'Seguridad y RBAC', 'Configuracion']) {
      expect(screen.queryByText(hidden)).not.toBeInTheDocument();
    }
    expect(screen.queryByText('Administración')).not.toBeInTheDocument();
  });
});
