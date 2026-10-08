import { useEffect, useState } from "react";
import { googleLoginUrl } from "./api";

export function GoogleLoginOption() {
  const [enabled, setEnabled] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    fetch(`${import.meta.env.VITE_API_URL ?? "/api"}/auth/providers`, {
      signal: controller.signal,
      cache: "no-store",
    })
      .then(async (response) => {
        if (!response.ok) return;
        const providers = await response.json();
        if (active) setEnabled(providers?.google === true);
      })
      .catch(() => { /* Email login remains available if discovery fails. */ });
    return () => {
      active = false;
      controller.abort();
    };
  }, []);

  if (!enabled) return null;
  return (
    <>
      <div className="social-grid">
        <button type="button" className="social-button" aria-label="Log in with Google"
          onClick={() => window.location.assign(googleLoginUrl)}>
          <span className="social-mark google">G</span><strong>Google</strong>
        </button>
      </div>
      <div className="auth-divider"><span>or log in with email</span></div>
    </>
  );
}
