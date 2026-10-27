import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { api, occupancySubscriptionUrl } from "./api";

export default function OccupancySubscription({ propertyId }: { propertyId: number }) {
  const session = useSyncExternalStore(subscribe, snapshot);
  return <SubscriptionPanel key={`${propertyId}:${session}`} propertyId={propertyId} />;
}
function snapshot() { return localStorage.getItem("bookica_token") ?? ""; }
function subscribe(callback: () => void) {
  window.addEventListener("storage", callback); window.addEventListener("focus", callback);
  return () => { window.removeEventListener("storage", callback); window.removeEventListener("focus", callback); };
}
function SubscriptionPanel({ propertyId }: { propertyId: number }) {
  const [open, setOpen] = useState(false);
  return <><button aria-expanded={open} onClick={() => setOpen(value => !value)}>{open ? "Sakrij iCal pretplatu" : "Podesi iCal pretplatu"}</button>{open && <SubscriptionContent propertyId={propertyId} />}</>;
}
function SubscriptionContent({ propertyId }: { propertyId: number }) {
  const session = useRef(snapshot());
  const [active, setActive] = useState<boolean | null>(null);
  const [version, setVersion] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [url, setUrl] = useState("");
  const [confirm, setConfirm] = useState<"rotate" | "revoke" | null>(null);
  const cancel = useRef<HTMLButtonElement>(null);
  const link = useRef<HTMLInputElement>(null);
  const request = useRef(false);
  useEffect(() => { if (confirm) cancel.current?.focus(); }, [confirm]);
  useEffect(() => { if (url) link.current?.focus(); }, [url]);
  useEffect(() => {
    let live = true;
    api.occupancyFeedStatus(propertyId).then(value => { if (live) setActive(value.active); })
      .catch(() => { if (live) setError("Status pretplate nije učitan. Pokušaj ponovo."); });
    return () => { live = false; };
  }, [propertyId, version]);
  async function change(action: "rotate" | "revoke") {
    if (request.current || snapshot() !== session.current) return;
    request.current = true; setBusy(true); setError(""); setUrl("");
    try {
      if (action === "rotate") {
        const result = await api.rotateOccupancyFeed(propertyId);
        if (snapshot() !== session.current) return;
        setUrl(occupancySubscriptionUrl(result.path)); setActive(true);
      } else { await api.revokeOccupancyFeed(propertyId); setActive(false); }
      setConfirm(null);
    } catch { setError("Promena nije potvrđena. Proveri status ili pokušaj ponovo. Zamena linka poništava prethodni link."); }
    finally { request.current = false; setBusy(false); }
  }
  return <section aria-label="Pretplata na zauzetost">
    <h4>Pretplatni iCal link</h4>
    <p>Spoljni kalendar preko linka čita trenutnu zauzetost za narednih 365 dana. Učestalost osvežavanja određuje taj kalendar; kašnjenje može dovesti do preklapanja rezervacija.</p>
    <p>Svako ko ima link vidi zauzete datume. Čuvaj ga kao lozinku. Link se prikazuje samo nakon kreiranja ili zamene. Opoziv ne briše već preuzete podatke.</p>
    {active !== null && <p role="status">{active ? "Pretplata je aktivna." : "Pretplata nije aktivna."}</p>}
    <button disabled={busy} onClick={() => { setError(""); setVersion(value => value + 1); }}>Proveri status pretplate</button>
    {active !== null && !confirm && <><button disabled={busy} onClick={() => setConfirm("rotate")}>{active ? "Zameni pretplatni link" : "Kreiraj pretplatni link"}</button>{active && <button disabled={busy} onClick={() => setConfirm("revoke")}>Opozovi pretplatu</button>}</>}
    {confirm && <fieldset disabled={busy}><legend>{confirm === "rotate" ? "Novi link odmah poništava prethodni. Ažuriraj ga u spoljnim kalendarima." : "Prethodni link prestaje da radi. Već uvezeni termini ostaju u spoljnim kalendarima."}</legend><button onClick={() => void change(confirm)}>Potvrdi promenu</button><button ref={cancel} onClick={() => setConfirm(null)}>Odustani</button></fieldset>}
    {url && <label>Tajni pretplatni link<input ref={link} readOnly value={url} onFocus={event => event.target.select()} /></label>}
    {error && <p role="alert">{error}</p>}
  </section>;
}
