import { useEffect, useState } from "react";
import type { OccupancySource } from "./OccupancySources";

export default function CalendarImportFreshness({ source }: { source: OccupancySource }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const update = () => setNow(Date.now());
    const timer = window.setInterval(update, 60_000);
    window.addEventListener("focus", update);
    return () => { window.clearInterval(timer); window.removeEventListener("focus", update); };
  }, []);
  const success = source.last_success_at ? Date.parse(source.last_success_at) : NaN;
  let message: string;
  if (source.last_status === "conflict") {
    message = "Potreban pregled: poslednji pokušaj je imao preklapanje. Prethodne blokade su sačuvane.";
  } else if (!source.last_success_at) {
    message = "Izvor još nema uspešan uvoz. Preuzmi kompletan kalendar i pregledaj termine.";
  } else if (!Number.isFinite(success) || success > now) {
    message = "Starost uvoza nije pouzdano utvrđena. Osveži izvore i proveri vreme poslednjeg uvoza.";
  } else if (now - success >= 24 * 60 * 60 * 1000) {
    message = "Uvoz je star najmanje 24 sata. Preporučujemo novi pregled kompletnog kalendara.";
  } else {
    message = "Uspešan uvoz u poslednja 24 sata.";
  }
  return <div aria-label="Starost uvoza kalendara">
    <p role="status">{message}</p>
    <p>Ovo je starost poslednjeg učitanog uvoza, ne potvrda trenutne zauzetosti kod drugog provajdera. Stanje automatike proveri u posebnom panelu.</p>
  </div>;
}
