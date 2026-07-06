/**
 * Wrapper for fetch API to automatically inject JWT tokens
 * and handle 401 Unauthorized responses.
 */

interface FetchOptions extends RequestInit {
    requireAuth?: boolean;
}

export async function fetchWithAuth(url: string, options: FetchOptions = {}) {
    const { requireAuth = true, headers, ...restOptions } = options;
    const finalHeaders = new Headers(headers as HeadersInit);

    if (requireAuth) {
        let token = null;
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

    if (response.status === 401 && requireAuth) {
        // Handle token expiration / unauthorized
        if (typeof window !== 'undefined') {
            localStorage.removeItem('access_token');
            localStorage.removeItem('refresh_token');
            window.location.href = '/login';
        }
    }

    return response;
}
