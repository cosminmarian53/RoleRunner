export const API_BASE = (import.meta.env.VITE_API_BASE_URL || "/api").replace(/\/$/, "");

/**
 * Get or generate a persistent anonymous session UUID for this browser.
 * Ensures zero-friction privacy isolation across all users without requiring account signups.
 */
export function getOrCreateSessionId() {
  if (typeof window === "undefined") return "00000000-0000-0000-0000-000000000001";
  let sessionId = localStorage.getItem("rolerunner-session-id");
  if (!sessionId) {
    if (typeof crypto !== "undefined" && crypto.randomUUID) {
      sessionId = crypto.randomUUID();
    } else {
      sessionId = "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
        const r = (Math.random() * 16) | 0;
        const v = c === "x" ? r : (r & 0x3) | 0x8;
        return v.toString(16);
      });
    }
    localStorage.setItem("rolerunner-session-id", sessionId);
  }
  return sessionId;
}

export async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  const sessionId = getOrCreateSessionId();

  // Attach session identity headers for seamless anonymous multi-tenancy
  if (!headers.has("X-Session-ID")) {
    headers.set("X-Session-ID", sessionId);
  }
  if (!headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${sessionId}`);
  }

  if (options.body && !(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const error = await response.json();
      message = typeof error.detail === "string" ? error.detail : (error.detail?.detail || message);
    } catch {
      // The response was not JSON.
    }
    throw new Error(message);
  }
  if (response.status === 204) return null;
  return response.json();
}

export async function download(path) {
  const sessionId = getOrCreateSessionId();
  const headers = {
    "X-Session-ID": sessionId,
    "Authorization": `Bearer ${sessionId}`,
  };

  const response = await fetch(`${API_BASE}${path}`, { headers });
  if (!response.ok) throw new Error(`Export failed (${response.status})`);
  const blob = await response.blob();
  const disposition = response.headers.get("content-disposition") || "";
  const filename = disposition.match(/filename="?([^";]+)"?/i)?.[1] || "cv-export";
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

export function eventUrl(path) {
  const sessionId = getOrCreateSessionId();
  const separator = path.includes("?") ? "&" : "?";
  return `${API_BASE}${path}${separator}session_id=${sessionId}`;
}
