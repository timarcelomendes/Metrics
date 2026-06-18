const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

export function getUserEmail(): string {
  if (typeof window === 'undefined') return '';
  return window.localStorage.getItem('gauge_metrics_email') ?? '';
}

export function setUserEmail(email: string) {
  window.localStorage.setItem('gauge_metrics_email', email.trim().toLowerCase());
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      'X-User-Email': getUserEmail(),
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    throw new Error(errorBody?.detail ?? `Erro HTTP ${response.status}`);
  }

  return response.json();
}
