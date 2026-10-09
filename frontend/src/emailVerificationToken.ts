// Capture before StrictMode mounts; fragments are never sent to the server.
export function takeEmailVerificationToken(): string {
  if (window.location.pathname !== "/verify-email") return "";
  const token = new URLSearchParams(window.location.hash.slice(1)).get("token") ?? "";
  if (window.location.hash) window.history.replaceState(window.history.state, "", window.location.pathname + window.location.search);
  return /^[A-Za-z0-9_-]{32,255}$/.test(token) ? token : "";
}

let currentToken = takeEmailVerificationToken();
const listeners = new Set<() => void>();

export function syncEmailVerificationToken(): void {
  const next = window.location.pathname !== "/verify-email" ? ""
    : window.location.hash ? takeEmailVerificationToken() : currentToken;
  if (next === currentToken) return;
  currentToken = next;
  listeners.forEach(listener => listener());
}

export function subscribeEmailVerificationToken(listener: () => void): () => void {
  listeners.add(listener);
  window.addEventListener("hashchange", syncEmailVerificationToken);
  window.addEventListener("popstate", syncEmailVerificationToken);
  syncEmailVerificationToken();
  return () => {
    listeners.delete(listener);
    if (!listeners.size) {
      window.removeEventListener("hashchange", syncEmailVerificationToken);
      window.removeEventListener("popstate", syncEmailVerificationToken);
    }
  };
}

export function getEmailVerificationToken(): string { return currentToken; }
