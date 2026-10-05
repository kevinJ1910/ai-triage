import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import BlindReview from '../../components/BlindReview';

vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

const queue = {
  pending_total: 2,
  results: [
    { id: 7, date: '2026-10-01 08:00', gender: 'female', age: 54, transcript: 'dolor toracico opresivo' },
    { id: 8, date: '2026-10-01 09:00', gender: 'male', age: null, transcript: 'tos leve' },
  ],
};

function mockFetch(referenceResponse: { ok: boolean; status: number; body: object }) {
  const fetchMock = vi.fn().mockImplementation((url: string) => {
    if (url.includes('/blind_review_queue/')) {
      return Promise.resolve({ ok: true, status: 200, json: async () => queue } as Response);
    }
    if (url.includes('/reference_level/')) {
      return Promise.resolve({
        ok: referenceResponse.ok,
        status: referenceResponse.status,
        json: async () => referenceResponse.body,
      } as Response);
    }
    return Promise.resolve({ ok: false, status: 401, json: async () => ({}) } as Response);
  });
  global.fetch = fetchMock;
  return fetchMock;
}

describe('BlindReview Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('muestra la transcripcion sin niveles y registra el nivel elegido', async () => {
    const fetchMock = mockFetch({ ok: true, status: 200, body: { session_id: 7, reference_level: 2 } });
    render(<BlindReview />);

    await waitFor(() => expect(screen.getByText('dolor toracico opresivo')).toBeInTheDocument());
    expect(screen.getByText('2 pendientes')).toBeInTheDocument();
    expect(screen.getByText('54 años')).toBeInTheDocument();

    const submit = screen.getByRole('button', { name: /Registrar nivel de referencia/i });
    expect(submit).toBeDisabled();

    fireEvent.click(screen.getByRole('button', { name: /Emergencia/i }));
    fireEvent.click(submit);

    await waitFor(() => expect(screen.getByText('tos leve')).toBeInTheDocument());
    const call = fetchMock.mock.calls.find(([url]) => String(url).includes('/7/reference_level/'));
    expect(call).toBeDefined();
    expect(JSON.parse(call![1].body)).toEqual({ reference_level: 2 });
    expect(screen.getByText('1 pendientes')).toBeInTheDocument();
  });

  it('mantiene el caso si el servidor rechaza el registro', async () => {
    mockFetch({ ok: false, status: 403, body: { error: 'No puede adjudicar un triaje realizado por usted' } });
    const { toast } = await import('sonner');
    render(<BlindReview />);

    await waitFor(() => expect(screen.getByText('dolor toracico opresivo')).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: /Urgencia Menor/i }));
    fireEvent.click(screen.getByRole('button', { name: /Registrar nivel de referencia/i }));

    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith('No puede adjudicar un triaje realizado por usted')
    );
    expect(screen.getByText('dolor toracico opresivo')).toBeInTheDocument();
  });
});
