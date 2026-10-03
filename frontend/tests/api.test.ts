import { fetchWithAuth, setAccessToken, getAccessToken, logout } from '../lib/api';

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

describe('fetchWithAuth utility', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
    setAccessToken(null);
  });

  it('injects the in-memory Bearer token when requireAuth is true', async () => {
    setAccessToken('mocked-jwt-token-123');
    const mockFetch = vi.fn().mockResolvedValue(json({ success: true }));
    global.fetch = mockFetch;

    await fetchWithAuth('/api/test/', { requireAuth: true });

    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [calledUrl, calledOptions] = mockFetch.mock.calls[0];
    expect(calledUrl).toBe('/api/test/');
    expect(calledOptions.headers.get('Authorization')).toBe('Bearer mocked-jwt-token-123');
  });

  it('never persists tokens in localStorage and purges legacy keys', async () => {
    localStorage.setItem('access_token', 'legacy');
    localStorage.setItem('refresh_token', 'legacy-refresh');
    setAccessToken('in-memory');
    expect(localStorage.getItem('access_token')).toBeNull();
    expect(localStorage.getItem('refresh_token')).toBeNull();
    expect(getAccessToken()).toBe('in-memory');
  });

  it('does not inject Authorization header when requireAuth is false', async () => {
    setAccessToken('mocked-jwt-token-123');
    const mockFetch = vi.fn().mockResolvedValue(json({ success: true }));
    global.fetch = mockFetch;

    await fetchWithAuth('/api/public/', { requireAuth: false });

    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [, calledOptions] = mockFetch.mock.calls[0];
    expect(calledOptions.headers.get('Authorization')).toBeNull();
  });

  it('preserves additional custom headers passed in options', async () => {
    setAccessToken('t');
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

  it('obtains an access token from the refresh cookie when none is in memory', async () => {
    const mockFetch = vi.fn().mockImplementation((url: string) =>
      Promise.resolve(url === '/api/auth/refresh/' ? json({ access: 'fresh-token' }) : json({ ok: true }))
    );
    global.fetch = mockFetch;

    await fetchWithAuth('/api/protected/');

    expect(mockFetch.mock.calls[0][0]).toBe('/api/auth/refresh/');
    const [, calledOptions] = mockFetch.mock.calls[1];
    expect(calledOptions.headers.get('Authorization')).toBe('Bearer fresh-token');
  });

  it('shares a single refresh between concurrent requests', async () => {
    const mockFetch = vi.fn().mockImplementation((url: string) =>
      Promise.resolve(url === '/api/auth/refresh/' ? json({ access: 'fresh-token' }) : json({ ok: true }))
    );
    global.fetch = mockFetch;

    await Promise.all([fetchWithAuth('/api/a/'), fetchWithAuth('/api/b/'), fetchWithAuth('/api/c/')]);

    const refreshCalls = mockFetch.mock.calls.filter(([url]) => url === '/api/auth/refresh/');
    expect(refreshCalls).toHaveLength(1);
  });

  it('retries once with a refreshed token after a 401', async () => {
    setAccessToken('expired-token');
    const mockFetch = vi.fn()
      .mockResolvedValueOnce(new Response(null, { status: 401 }))
      .mockResolvedValueOnce(json({ access: 'new-token' }))
      .mockResolvedValueOnce(json({ ok: true }));
    global.fetch = mockFetch;

    const res = await fetchWithAuth('/api/protected/');

    expect(res.status).toBe(200);
    expect(mockFetch.mock.calls[2][1].headers.get('Authorization')).toBe('Bearer new-token');
  });

  it('redirects to /login when the session cannot be refreshed', async () => {
    setAccessToken('expired-token');
    localStorage.setItem('user_profile', '{"id":1}');
    global.fetch = vi.fn().mockResolvedValue(new Response(null, { status: 401 }));

    delete (window as any).location;
    window.location = { href: '' } as any;

    await fetchWithAuth('/api/protected/', { requireAuth: true });

    expect(getAccessToken()).toBeNull();
    expect(localStorage.getItem('user_profile')).toBeNull();
    expect(window.location.href).toBe('/login');
  });

  it('logout calls the server and clears local session state', async () => {
    setAccessToken('t');
    localStorage.setItem('user_profile', '{"id":1}');
    const mockFetch = vi.fn().mockResolvedValue(json({ detail: 'ok' }));
    global.fetch = mockFetch;

    await logout();

    expect(mockFetch).toHaveBeenCalledWith('/api/auth/logout/', expect.objectContaining({ method: 'POST' }));
    expect(getAccessToken()).toBeNull();
    expect(localStorage.getItem('user_profile')).toBeNull();
  });
});
