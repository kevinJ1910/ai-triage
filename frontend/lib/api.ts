/**
 * Cliente HTTP autenticado.
 * - El access token vive solo en memoria (nunca en localStorage): un XSS no puede leerlo de almacenamiento.
 * - El refresh token esta en una cookie httpOnly (SameSite=Strict, path /api/auth/) que fija el backend.
 * - Si no hay access token o el backend responde 401, se renueva con /api/auth/refresh/ y se reintenta una vez.
 */

interface FetchOptions extends RequestInit {
    requireAuth?: boolean;
    _isRetry?: boolean;
}

let accessToken: string | null = null;
let refreshInFlight: Promise<string | null> | null = null;

// Claves que versiones anteriores guardaban en localStorage; se purgan al iniciar.
const LEGACY_TOKEN_KEYS = ['access_token', 'refresh_token'];

export function setAccessToken(token: string | null) {
    accessToken = token;
    if (typeof window !== 'undefined') {
        LEGACY_TOKEN_KEYS.forEach(key => localStorage.removeItem(key));
    }
}

export function getAccessToken(): string | null {
    return accessToken;
}

/**
 * Renueva el access token con la cookie de refresh.
 * Las peticiones concurrentes comparten una sola renovacion: con rotacion + blacklist,
 * dos refresh simultaneos invalidarian la sesion.
 */
export function tryRefreshToken(): Promise<string | null> {
    if (typeof window === 'undefined') return Promise.resolve(null);
    if (!refreshInFlight) {
        refreshInFlight = (async () => {
            try {
                const res = await fetch('/api/auth/refresh/', {
                    method: 'POST',
                    credentials: 'same-origin',
                });
                if (!res.ok) return null;
                const data = await res.json();
                setAccessToken(data.access || null);
                return accessToken;
            } catch {
                return null;
            } finally {
                refreshInFlight = null;
            }
        })();
    }
    return refreshInFlight;
}

function redirectToLogin() {
    accessToken = null;
    if (typeof window !== 'undefined') {
        localStorage.removeItem('user_profile');
        window.location.href = '/login';
    }
}

/** Cierra sesion en el servidor (blacklist del refresh + borrado de cookie) y limpia el estado local. */
export async function logout(): Promise<void> {
    try {
        await fetch('/api/auth/logout/', { method: 'POST', credentials: 'same-origin' });
    } catch {
        // Aunque falle la red, la sesion local se limpia igualmente
    }
    accessToken = null;
    if (typeof window !== 'undefined') {
        localStorage.removeItem('user_profile');
        LEGACY_TOKEN_KEYS.forEach(key => localStorage.removeItem(key));
    }
}

export async function fetchWithAuth(url: string, options: FetchOptions = {}) {
    const { requireAuth = true, _isRetry = false, headers, ...restOptions } = options;
    const finalHeaders = new Headers(headers as HeadersInit);

    if (requireAuth) {
        const token = accessToken ?? (await tryRefreshToken());
        if (token) {
            finalHeaders.set('Authorization', `Bearer ${token}`);
        }
    }

    const response = await fetch(url, {
        headers: finalHeaders,
        credentials: 'same-origin',
        ...restOptions,
    });

    if (response.status === 401 && requireAuth && !_isRetry) {
        accessToken = null;
        const newToken = await tryRefreshToken();
        if (newToken) {
            return fetchWithAuth(url, { ...options, _isRetry: true });
        }
        redirectToLogin();
    }

    return response;
}
