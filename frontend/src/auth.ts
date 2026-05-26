import type { User } from "./types";

const TOKEN_KEY = "my_vllm_token";
const USER_KEY = "my_vllm_user";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function getStoredUser(): User | null {
  try {
    const raw = localStorage.getItem(USER_KEY);
    if (raw) return JSON.parse(raw) as User;
  } catch {
    /* ignore */
  }
  return null;
}

export function setAuth(token: string, user: User): void {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearAuth(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

export function authHeaders(): HeadersInit {
  const token = getToken();
  if (!token) return {};
  return { Authorization: `Bearer ${token}` };
}
