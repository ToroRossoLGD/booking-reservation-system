// Consume credentials before deferred route code loads, just as the eager App did.
function consumeOAuthRedirect() {
  const params = new URLSearchParams(window.location.hash.slice(1));
  const token = params.get("auth_token");
  const error = params.get("auth_error") ?? "";
  if (token || error) window.history.replaceState(null, "", `${window.location.pathname}${window.location.search}`);
  if (token) localStorage.setItem("bookica_token", token);
  return { error };
}
export const oauthRedirect = consumeOAuthRedirect();
