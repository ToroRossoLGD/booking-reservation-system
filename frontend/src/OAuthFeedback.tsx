import { useState } from "react";
import { Link } from "react-router-dom";
import { GoogleLoginOption } from "./GoogleLoginOption";
import { oauthRedirect } from "./oauthRedirect";
import "./oauth-feedback.css";

function oauthFeedbackMessage(error: string): string {
  if (error === "Google login was cancelled") return "Google prijava je otkazana. Možeš da započneš novi pokušaj ili da se prijaviš email adresom.";
  if (error === "Google login expired" || error === "Invalid Google login state") return "Google prijava je istekla ili link više nije važeći. Započni novi pokušaj prijave.";
  return "Google prijava nije uspela. Pokušaj ponovo ili koristi prijavu email adresom.";
}

export default function OAuthFeedback() {
  const [visible, setVisible] = useState(Boolean(oauthRedirect.error));
  if (!visible) return null;
  return <section className="oauth-feedback" aria-labelledby="oauth-feedback-title">
    <h2 id="oauth-feedback-title">Google prijava</h2>
    <p role="alert">{oauthFeedbackMessage(oauthRedirect.error)}</p>
    <GoogleLoginOption />
    <div className="oauth-feedback-actions">
      <Link to="/account" onClick={() => setVisible(false)}>Prijava email adresom</Link>
      <button type="button" onClick={() => setVisible(false)}>Zatvori obaveštenje</button>
    </div>
  </section>;
}
