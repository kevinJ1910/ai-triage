import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import AppNavigation from '../../components/AppNavigation';

const mockPush = vi.fn();

vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockPush,
    replace: vi.fn(),
    prefetch: vi.fn(),
  }),
}));

vi.mock('@/components/TriageDashboard', () => ({
  default: () => <div data-testid="triage-view">Triage Dashboard Content</div>,
}));
vi.mock('@/components/ConfigPanel', () => ({
  default: () => <div data-testid="config-view">Config Panel Content</div>,
}));
vi.mock('@/components/SecurityPanel', () => ({
  default: () => <div data-testid="security-view">Security Panel Content</div>,
}));
vi.mock('@/components/NormalizationMonitor', () => ({
  default: () => <div data-testid="norm-view">Normalization Content</div>,
}));
vi.mock('@/components/FHIRMonitor', () => ({
  default: () => <div data-testid="fhir-view">FHIR Monitor Content</div>,
}));
vi.mock('@/components/EMRSimulator', () => ({
  default: () => <div data-testid="emr-view">EMR Simulator Content</div>,
}));
vi.mock('@/components/MetricsDashboard', () => ({
  default: () => <div data-testid="metrics-view">Metrics Dashboard Content</div>,
}));

describe('AppNavigation Component', () => {
  const mockUser = {
    id: 1,
    email: 'dr.rodriguez@hospital.com',
    first_name: 'Carlos',
    last_name: 'Rodriguez',
    full_name: 'Dr. Carlos Rodriguez',
    role: 'admin',
    permissions: {
      can_use_transcriber: true,
      can_edit_symptoms: true,
      can_register_patients: true,
      can_view_emr: true,
      can_view_fhir: true,
      can_manage_config: true,
    },
  };

  beforeEach(() => {
    vi.restoreAllMocks();
    mockPush.mockReset();
    localStorage.clear();
  });

  it('redirects to /login if no access token is present', async () => {
    render(<AppNavigation />);

    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith('/login');
    });
  });

  it('authenticates user and renders navigation with doctor profile', async () => {
    localStorage.setItem('access_token', 'valid-jwt-token');

    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/api/auth/me/')) {
        return Promise.resolve({
          ok: true,
          json: async () => mockUser,
        } as Response);
      }
      return Promise.resolve({ ok: false } as Response);
    });

    render(<AppNavigation />);

    await waitFor(() => {
      expect(screen.getByText('Dr. Carlos Rodriguez')).toBeInTheDocument();
      expect(screen.getByText('admin')).toBeInTheDocument();
      expect(screen.getByTestId('triage-view')).toBeInTheDocument();
    });
  });

  it('navigates between modules on tab click', async () => {
    localStorage.setItem('access_token', 'valid-jwt-token');

    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/api/auth/me/')) {
        return Promise.resolve({
          ok: true,
          json: async () => mockUser,
        } as Response);
      }
      return Promise.resolve({ ok: false } as Response);
    });

    render(<AppNavigation />);

    await waitFor(() => {
      expect(screen.getByTestId('triage-view')).toBeInTheDocument();
    });

    // Switch to Config tab
    const configTab = screen.getByRole('button', { name: /Configuracion/i });
    fireEvent.click(configTab);

    await waitFor(() => {
      expect(screen.getByTestId('config-view')).toBeInTheDocument();
      expect(screen.queryByTestId('triage-view')).not.toBeInTheDocument();
    });

    // Switch to Metrics tab
    const metricsTab = screen.getByRole('button', { name: /Metricas y Evaluacion/i });
    fireEvent.click(metricsTab);

    await waitFor(() => {
      expect(screen.getByTestId('metrics-view')).toBeInTheDocument();
    });
  });

  it('clears credentials and redirects on logout click', async () => {
    localStorage.setItem('access_token', 'valid-jwt-token');

    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/api/auth/me/')) {
        return Promise.resolve({
          ok: true,
          json: async () => mockUser,
        } as Response);
      }
      return Promise.resolve({ ok: false } as Response);
    });

    render(<AppNavigation />);

    await waitFor(() => {
      expect(screen.getByText('Cerrar Sesion')).toBeInTheDocument();
    });

    const logoutBtn = screen.getByRole('button', { name: /Cerrar Sesion/i });
    fireEvent.click(logoutBtn);

    expect(localStorage.getItem('access_token')).toBeNull();
    expect(mockPush).toHaveBeenCalledWith('/login');
  });

  it('opens mobile drawer and navigates from mobile drawer', async () => {
    localStorage.setItem('access_token', 'valid-jwt-token');

    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/api/auth/me/')) {
        return Promise.resolve({
          ok: true,
          json: async () => mockUser,
        } as Response);
      }
      return Promise.resolve({ ok: false } as Response);
    });

    render(<AppNavigation />);

    await waitFor(() => {
      expect(screen.getByTestId('triage-view')).toBeInTheDocument();
    });

    // Open mobile menu
    const menuBtn = screen.getByLabelText(/Abrir menu de navegacion/i);
    fireEvent.click(menuBtn);

    // Click on EMR simulator in mobile drawer
    const emrTabs = screen.getAllByRole('button', { name: /Simulador HCE/i });
    fireEvent.click(emrTabs[emrTabs.length - 1]);

    await waitFor(() => {
      expect(screen.getByTestId('emr-view')).toBeInTheDocument();
    });
  });
});
