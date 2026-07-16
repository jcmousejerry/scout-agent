import { API_BASE } from "./types";

export function getStoredAuth(): { token: string; username: string } | null {
  if (typeof window === "undefined") return null;
  const token = localStorage.getItem("token");
  const username = localStorage.getItem("username");
  if (!token || !username) return null;
  return { token, username };
}

export function clearAuth() {
  localStorage.removeItem("token");
  localStorage.removeItem("username");
}

export function setAuth(token: string, username: string) {
  localStorage.setItem("token", token);
  localStorage.setItem("username", username);
}

export async function apiFetch(path: string, options?: RequestInit) {
  const auth = getStoredAuth();
  if (!auth) throw new Error("not authenticated");
  const res = await fetch(API_BASE + path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: "Bearer " + auth.token,
      ...options?.headers,
    },
  });
  if (res.status === 401) {
    clearAuth();
    window.location.href = "/login";
    throw new Error("unauthorized");
  }
  return res;
}

export async function authFetch(path: string, body?: any) {
  return apiFetch(path, {
    method: "POST",
    body: body ? JSON.stringify(body) : undefined,
  });
}