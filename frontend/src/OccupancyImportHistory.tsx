import { useEffect, useState } from "react";
import { api } from "./api";

export type OccupancyImportRun = {
  id: number;
  created_at: string;
  status: "applied" | "conflict";
  created: number;
  existing: number;
  conflicts: number;
  ignored: number;
  clipped: number;
};

export default function OccupancyImportHistory({ propertyId, revision }: { propertyId: number; revision: number }) {
  const [open, setOpen] = useState(false);
  return <section aria-label="Istorija ručnog uvoza">
    <button aria-expanded={open} onClick={() => setOpen(value => !value)}>{open ? "Sakrij istoriju uvoza" : "Istorija uvoza kalendara"}</button>
    {open && <History key={`${propertyId}:${revision}`} propertyId={propertyId} />}
  </section>;
}

function History({ propertyId }: { propertyId: number }) {
  const [rows, setRows] = useState<OccupancyImportRun[] | null>(null);
  const [error, setError] = useState(false);
  const [version, setVersion] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    api.occupancyImportHistory(propertyId, controller.signal).then(value => {
      if (!controller.signal.aborted) setRows(value);
    }).catch(() => { if (!controller.signal.aborted) setError(true); });
    return () => controller.abort();
  }, [propertyId, version]);
  const loading = rows === null && !error;
  const format = new Intl.DateTimeFormat("sr-Latn-RS", { dateStyle: "medium", timeStyle: "short", timeZone: "UTC" });
  return <div>
    <h4>Poslednjih 10 potvrđenih pokušaja uvoza</h4>
    <p>Istorija važi za sve oglase istog objekta. Ovo je ručni uvoz, ne automatska sinhronizacija. Pregledi i neispravni fajlovi nisu u istoriji. Raniji uvozi pre uvođenja istorije nisu zabeleženi.</p>
    {loading && <p role="status">Učitavanje istorije…</p>}
    {error && <p role="alert">Istorija nije učitana. Pokušaj ponovo.</p>}
    {rows?.length === 0 && <p role="status">Još nema zabeleženih pokušaja uvoza.</p>}
    {rows && rows.length > 0 && <ol>{rows.map(row => <li key={row.id}>
      <p><time dateTime={row.created_at}>{format.format(new Date(row.created_at))} UTC</time> — {row.status === "conflict" ? "Sprečen uvoz zbog preklapanja" : row.created === 0 ? "Završen uvoz bez novih blokada" : "Uspešan uvoz"}</p>
      <p>Novih blokada: {row.created}. Već blokirano: {row.existing}. Preklapanja: {row.conflicts}. Preskočenih događaja: {row.ignored}. Skraćenih događaja: {row.clipped}.</p>
      {row.status === "conflict" && <p>Nijedna blokada nije dodata ovim pokušajem. Ponovi pregled fajla da proveriš trenutna preklapanja.</p>}
    </li>)}</ol>}
    <button disabled={loading} onClick={() => { setRows(null); setError(false); setVersion(value => value + 1); }}>Osveži istoriju uvoza</button>
  </div>;
}
