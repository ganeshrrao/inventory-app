// VITE_API_URL is set at build time by Railway (or any CI/CD).
// Locally it falls back to your dev server. Note: Vite only exposes env vars
// prefixed with VITE_ to the browser bundle — others are stripped for security.
export const API = import.meta.env.VITE_API_URL || "http://localhost:8000/api";

export async function apiFetch(path, opts = {}) {
  const token = localStorage.getItem("token");

  const res = await fetch(`${API}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    ...opts,
  });

  if (res.status === 401) {
    localStorage.removeItem("token");
    window.location.href = "/login";
    throw new Error("Session expired — please log in again");
  }

  if (!res.ok) {
    let msg = `API error ${res.status}`;
    try { const body = await res.json(); msg = body.detail || msg; } catch {}
    throw new Error(msg);
  }

  if (res.status === 204 || res.headers.get("content-length") === "0") {
    return null;
  }
  return res.json();
}
