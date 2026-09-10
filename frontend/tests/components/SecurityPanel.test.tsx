import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import SecurityPanel from '../../components/SecurityPanel';

describe('SecurityPanel Component', () => {
  const mockUsers = [
    {
      id: 1,
      email: 'doctor.carlos@hospital.com',
      first_name: 'Carlos',
      last_name: 'Rodriguez',
      full_name: 'Dr. Carlos Rodriguez',
      document_id: 'DOC-12345',
      phone: '+573001234567',
      role: 'medico',
      is_verified: true,
      permissions: {
        can_use_transcriber: true,
        can_edit_symptoms: true,
        can_register_patients: true,
        can_view_emr: true,
        can_view_fhir: false,
        can_manage_config: false,
      },
      date_joined: '2026-09-10T10:00:00Z',
    },
  ];

  const mockLogs = [
    {
      id: 101,
      timestamp: '2026-09-10 14:00:00',
      user: 'Auditor Jefe',
      user_email: 'auditor@hospital.com',
      role: 'admin',
      action: 'LOGIN_SUCCESS',
      resource: 'Auth/JWT',
      status: 'SUCCESS',
      ip_address: '127.0.0.1',
      details: 'Inicio de sesion exitoso',
    },
  ];

  beforeEach(() => {
    vi.restoreAllMocks();
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/api/security/users/')) {
        return Promise.resolve({
          ok: true,
          json: async () => mockUsers,
        } as Response);
      }
      if (url.includes('/api/security/audit-logs/')) {
        return Promise.resolve({
          ok: true,
          json: async () => mockLogs,
        } as Response);
      }
      return Promise.resolve({
        ok: true,
        json: async () => ({}),
      } as Response);
    });
  });

  it('renders users list and security header', async () => {
    render(<SecurityPanel />);

    await waitFor(() => {
      expect(screen.getByText('Seguridad y Control de Acceso (RBAC)')).toBeInTheDocument();
      expect(screen.getByText('Dr. Carlos Rodriguez')).toBeInTheDocument();
      expect(screen.getByText('doctor.carlos@hospital.com')).toBeInTheDocument();
    });
  });

  it('displays audit logs in the activity table', async () => {
    render(<SecurityPanel />);

    await waitFor(() => {
      expect(screen.getByText('LOGIN_SUCCESS')).toBeInTheDocument();
      expect(screen.getByText('Inicio de sesion exitoso')).toBeInTheDocument();
      expect(screen.getByText('Auditor Jefe')).toBeInTheDocument();
    });
  });

  it('displays granular permissions and toggles visibility on click', async () => {
    render(<SecurityPanel />);

    await waitFor(() => {
      expect(screen.getByText('Dr. Carlos Rodriguez')).toBeInTheDocument();
      // First user is auto-expanded on load
      expect(screen.getByText('Transcriptor ASR en Vivo')).toBeInTheDocument();
      expect(screen.getByText('Editar Sintomas y Nivel de Triaje')).toBeInTheDocument();
      expect(screen.getByText('Registrar Nuevos Pacientes')).toBeInTheDocument();
      expect(screen.getByText('Ocultar')).toBeInTheDocument();
    });

    // Collapse user card
    const toggleBtn = screen.getByText('Ocultar');
    fireEvent.click(toggleBtn);

    await waitFor(() => {
      expect(screen.getByText('Configurar')).toBeInTheDocument();
      expect(screen.queryByText('Transcriptor ASR en Vivo')).not.toBeInTheDocument();
    });
  });
});