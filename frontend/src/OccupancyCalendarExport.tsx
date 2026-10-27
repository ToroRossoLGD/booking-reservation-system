import { useRef, useState } from "react";
import { api } from "./api";

export default function OccupancyCalendarExport({ propertyId }: { propertyId: number }) {
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<"error" | "started" | null>(null);
  const inFlight = useRef(false);
  async function download() {
    if (inFlight.current) return;
    inFlight.current = true; setBusy(true); setStatus(null);
    const session = localStorage.getItem("bookica_token");
    let url: string | undefined;
    let anchor: HTMLAnchorElement | undefined;
    try {
      const content = await api.occupancyCalendar(propertyId);
      if (localStorage.getItem("bookica_token") !== session) throw new Error("Session changed");
      url = URL.createObjectURL(new Blob([content], { type: "text/calendar;charset=utf-8" }));
      anchor = document.createElement("a");
      anchor.href = url; anchor.download = `bookica-occupancy-${propertyId}.ics`;
      document.body.append(anchor); anchor.click(); setStatus("started");
    } catch { setStatus("error"); }
    finally {
      anchor?.remove();
      if (url) { const value = url; window.setTimeout(() => URL.revokeObjectURL(value), 1000); }
      inFlight.current = false; setBusy(false);
    }
  }
  return <section aria-label="Izvoz zauzetosti">
    <h4>Izvoz zauzetosti u kalendar</h4>
    <p>Preuzmi zauzete datume za narednih 365 dana: potvrđene boravke, blokade i dane pripreme za sve oglase istog stana. Podaci gostiju i privatni razlozi nisu uključeni.</p>
    <p>Ovo je trenutna kopija, bez automatske sinhronizacije. Izmene i otkazivanja neće ažurirati uvezeni kalendar. Prazni datumi nisu garancija da je rezervacija dozvoljena.</p>
    <button type="button" className="ph-outline" disabled={busy} onClick={() => void download()}>{busy ? "Priprema izvoza…" : "Preuzmi zauzetost (.ics)"}</button>
    {status === "started" && <p role="status">Preuzimanje je pokrenuto. Sačuvaj datoteku i uvezi je u izabrani kalendar.</p>}
    {status === "error" && <p role="alert">Izvoz nije uspeo. Proveri prijavu i pokušaj ponovo.</p>}
  </section>;
}
