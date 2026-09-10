/**
 * Wrapper for fetch API to automatically inject JWT tokens,
 * attempt silent token refresh on 401, and handle Unauthorized responses.
 * FIX-SEC-004: Implementa renovacion automatica de access_token usando refresh_token
 * antes de redirigir al login, evitando sesiones interrumpidas por expiracion normal.
 */

interface FetchOptions extends RequestInit {
    requireAuth?: boolean;
    _isRetry?: boolean;
}

async function tryRefreshToken(): Promise<string | null> {
    if (typeof window === 'undefined') return null;
    const refreshToken = localStorage.getItem('refresh_token');
    if (!refreshToken) return null;
    try {
        const res = await fetch('/api/auth/refresh/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ refresh: refreshToken }),
        });
        if (!res.ok) return null;
        const data = await res.json();
        if (data.access) {
            localStorage.setItem('access_token', data.access);
            return data.access;
        }
        return null;
    } catch {
        return null;
    }
}

function clearSession() {
    if (typeof window !== 'undefined') {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        localStorage.removeItem('user_profile');
        window.location.href = '/login';
    }
}

export async function fetchWithAuth(url: string, options: FetchOptions = {}) {
    const { requireAuth = true, _isRetry = false, headers, ...restOptions } = options;
    const finalHeaders = new Headers(headers as HeadersInit);

    if (requireAuth) {
        let token: string | null = null;
        if (typeof window !== 'undefined') {
            token = localStorage.getItem('access_token');
        }
        if (token) {
            finalHeaders.set('Authorization', `Bearer ${token}`);
        }
    }

    const response = await fetch(url, {
        headers: finalHeaders,
        ...restOptions,
    });

    if (response.status === 401 && requireAuth && !_isRetry) {
        // Intentar renovacion silenciosa del access token con el refresh token.
        const newToken = await tryRefreshToken();
        if (newToken) {
            // Reintentar la peticion original con el nuevo token.
            return fetchWithAuth(url, { ...options, _isRetry: true });
        }
        // Si el refresh tambien fallo, limpiar sesion y redirigir al login.
        clearSession();
    }

    return response;
}
