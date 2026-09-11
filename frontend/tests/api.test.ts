import { fetchWithAuth } from '../lib/api';

describe('fetchWithAuth utility', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
  });

  it('injects Bearer token when requireAuth is true and token exists', async () => {
    localStorage.setItem('access_token', 'mocked-jwt-token-123');

    const mockFetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ success: true }), { status: 200 }));
    global.fetch = mockFetch;

    await fetchWithAuth('/api/test/', { requireAuth: true });

    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [calledUrl, calledOptions] = mockFetch.mock.calls[0];
    expect(calledUrl).toBe('/api/test/');
    expect(calledOptions.headers.get('Authorization')).toBe('Bearer mocked-jwt-token-123');
  });

  it('does not inject Authorization header when requireAuth is false', async () => {
    localStorage.setItem('access_token', 'mocked-jwt-token-123');

    const mockFetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ success: true }), { status: 200 }));
    global.fetch = mockFetch;

    await fetchWithAuth('/api/public/', { requireAuth: false });

    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [, calledOptions] = mockFetch.mock.calls[0];
    expect(calledOptions.headers.get('Authorization')).toBeNull();
  });

  it('preserves additional custom headers passed in options', async () => {
    const mockFetch = vi.fn().mockResolvedValue(new Response(null, { status: 200 }));
    global.fetch = mockFetch;

    await fetchWithAuth('/api/data/', {
      headers: {
        'Content-Type': 'application/json',
        'X-Custom-Header': 'Triage-Test',
      },
    });

    const [, calledOptions] = mockFetch.mock.calls[0];
    expect(calledOptions.headers.get('Content-Type')).toBe('application/json');
    expect(calledOptions.headers.get('X-Custom-Header')).toBe('Triage-Test');
  });

  it('clears localStorage tokens on 401 Unauthorized response', async () => {
    localStorage.setItem('access_token', 'expired-token');
    localStorage.setItem('refresh_token', 'expired-refresh');

    const mockFetch = vi.fn().mockResolvedValue(new Response(null, { status: 401 }));
    global.fetch = mockFetch;

    // Mock window.location
    delete (window as any).location;
    window.location = { href: '' } as any;

    await fetchWithAuth('/api/protected/', { requireAuth: true });

    expect(localStorage.getItem('access_token')).toBeNull();
    expect(localStorage.getItem('refresh_token')).toBeNull();
    expect(window.location.href).toBe('/login');
  });
});