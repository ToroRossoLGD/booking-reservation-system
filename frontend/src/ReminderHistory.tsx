import { useEffect, useState } from "react";
import { api } from "./api";
import { displayDate } from "./stay-types";

export type ReminderHistoryPage = {
  items: { id: number; kind: "arrival" | "departure" | "rental_viewing" | "sale_viewing"; reference_id: number; scheduled_for: string; created_at: string }[];
  offset: number; has_next: boolean;
};
const labels = { arrival: "Dolazak · rezervacija", departure: "Odlazak · rezervacija", rental_viewing: "Razgledanje za najam · upit", sale_viewing: "Razgledanje za kupovinu · upit" };
const timestamp = (value: string) => new Intl.DateTimeFormat("sr-Latn-RS", { dateStyle: "medium", timeStyle: "short", timeZone: "UTC" }).format(new Date(value)) + " UTC";

export default function ReminderHistory({ viewing }: { viewing: boolean }) {
  const [open, setOpen] = useState(false);
  const [offset, setOffset] = useState(0);
  const [version, setVersion] = useState(0);
  const [page, setPage] = useState<ReminderHistoryPage | null>(null);
  const [error, setError] = useState(false);
  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    api.reminderHistory(viewing, offset, controller.signal).then(value => { if (!controller.signal.aborted) setPage(value); })
      .catch(() => { if (!controller.signal.aborted) setError(true); });
    return () => controller.abort();
  }, [open, offset, version, viewing]);
  function load(next: number) { setPage(null); setError(false); setOffset(next); setVersion(value => value + 1); }
  return <section aria-label="Istorija isporuke podsetnika">
    <button className="ph-outline" aria-expanded={open} onClick={() => { setPage(null); setError(false); setOffset(0); setOpen(value => !value); }}>Istorija isporuke podsetnika</button>
    {open && <>
      <p>Zapisi potvrđuju kreiranje podsetnika u aplikaciji. Ne potvrđuju čitanje, email ili push isporuku. Ostaju i nakon brisanja obaveštenja. Prikazani termini su istorijski; aktuelni dogovor proveri u rezervaciji ili upitu.</p>
      {error ? <p role="alert">Istorija nije učitana. Pokušaj ponovo.</p> : !page ? <p role="status">Učitavanje istorije podsetnika…</p> : <>
        {!page.items.length && <p>Nema zabeleženih podsetnika na ovoj stranici.</p>}
        <ul>{page.items.map(item => <li key={item.id}><strong>{labels[item.kind]} #{item.reference_id}</strong><p>Termin: {item.kind === "arrival" || item.kind === "departure" ? displayDate(item.scheduled_for) : timestamp(item.scheduled_for)}.</p><p>Kreirano u aplikaciji: {timestamp(item.created_at)}.</p></li>)}</ul>
      </>}
      <nav aria-label="Stranice istorije podsetnika"><button disabled={!page || offset === 0} onClick={() => load(Math.max(0, offset - 20))}>Prethodnih 20 podsetnika</button><button disabled={!page?.has_next} onClick={() => load(offset + 20)}>Sledećih 20 podsetnika</button></nav>
      <button onClick={() => load(0)}>Osveži istoriju podsetnika</button>
    </>}
  </section>;
}
