// Read before React/StrictMode mounts. A fragment never reaches HTTP access logs.
export function takePasswordResetToken(): string {
  if (window.location.pathname !== "/reset-password") return "";
  const token = new URLSearchParams(window.location.hash.slice(1)).get("token") ?? "";
  if (window.location.hash) {
    window.history.replaceState(null, "", window.location.pathname + window.location.search);
  }
  return /^[A-Za-z0-9_-]{32,255}$/.test(token) ? token : "";
}

export const initialPasswordResetToken = takePasswordResetToken();
