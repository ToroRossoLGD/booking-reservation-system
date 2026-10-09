// Capture before StrictMode mounts; fragments are never sent to the server.
export function takeEmailVerificationToken(): string {
  if (window.location.pathname !== "/verify-email") return "";
  const token = new URLSearchParams(window.location.hash.slice(1)).get("token") ?? "";
  if (window.location.hash) window.history.replaceState(null, "", window.location.pathname + window.location.search);
  return /^[A-Za-z0-9_-]{32,255}$/.test(token) ? token : "";
}

export const initialEmailVerificationToken = takeEmailVerificationToken();
