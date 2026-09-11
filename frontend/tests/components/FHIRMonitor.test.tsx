import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import FHIRMonitor from '../../components/FHIRMonitor';

describe('FHIRMonitor Component', () => {
  const mockLogs = [
    {
      id: 1,
      session_id: 10,
      resource_type: 'Bundle',
      direction: 'OUTBOUND',
      status_code: 201,
      fhir_resource_id: 'bundle-test-001',
      validation_status: 'VALID',
      validation_details: 'Bundle verificado contra especificacion HL7 FHIR Release 4.',
      payload: {
        resourceType: 'Bundle',
        type: 'transaction',
        entry: [
          {
            resource: {
              resourceType: 'Patient',
              id: 'pat-100',
              name: [{ text: 'Juan Perez' }],
            },
          },
        ],
      },
      created_at: '2026-09-10 12:00:00',
    },
    {
      id: 2,
      session_id: 11,
      resource_type: 'Observation',
      direction: 'INBOUND',
      status_code: 200,
      fhir_resource_id: 'obs-test-002',
      validation_status: 'VALID',
      validation_details: 'Validacion correcta',
      payload: {
        resourceType: 'Observation',
        status: 'final',
        valueInteger: 3,
      },
      created_at: '2026-09-10 12:30:00',
    },
  ];

  beforeEach(() => {
    vi.restoreAllMocks();
    global.fetch = vi.fn().mockImplementation((url: string, options?: any) => {
      if (url.includes('/api/triage/sessions/fhir_logs/')) {
        return Promise.resolve({
          ok: true,
          json: async () => mockLogs,
        } as Response);
      }
      if (url.includes('/api/fhir/') && options?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ status: 'success', bundle_id: 'bundle-live-999' }),
        } as Response);
      }
      return Promise.resolve({
        ok: false,
        json: async () => ({}),
      } as Response);
    });
  });

  it('renders FHIR monitor header and loads transaction list', async () => {
    render(<FHIRMonitor />);

    await waitFor(() => {
      expect(screen.getByText('Monitor de Interoperabilidad Clinica (HL7 FHIR R4)')).toBeInTheDocument();
      expect(screen.getByText('bundle-test-001')).toBeInTheDocument();
      expect(screen.getByText('obs-test-002')).toBeInTheDocument();
      expect(screen.getAllByText('VALID').length).toBeGreaterThan(0);
    });
  });

  it('displays selected log payload inspection and schema details', async () => {
    render(<FHIRMonitor />);

    await waitFor(() => {
      expect(screen.getByText('Validacion de Conformidad FHIR R4')).toBeInTheDocument();
      expect(screen.getByText('bundle-test-001')).toBeInTheDocument();
      expect(screen.getByText('Bundle verificado contra especificacion HL7 FHIR Release 4.')).toBeInTheDocument();
    });
  });

  it('sends test transaction bundle when button is clicked', async () => {
    render(<FHIRMonitor />);

    await waitFor(() => {
      expect(screen.getByText('Transmitir Bundle Test')).toBeInTheDocument();
    });

    const sendBtn = screen.getByText('Transmitir Bundle Test');
    fireEvent.click(sendBtn);

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        '/api/fhir/',
        expect.objectContaining({
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
        })
      );
    });
  });
});
