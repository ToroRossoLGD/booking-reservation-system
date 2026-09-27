import { useEffect, useState } from "react";
import { api } from "./api";
import type { PropertyReviewPage } from "./property-review-types";

export default function PropertyReviews({ propertyId }: { propertyId: number }) {
  const [open, setOpen] = useState(false);
  const [page, setPage] = useState<PropertyReviewPage | null>(null);
  const [offset, setOffset] = useState(0);
  const [retry, setRetry] = useState(0);
  const [error, setError] = useState(false);
  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    api.propertyReviews(propertyId, offset, controller.signal).then(value => { if (!controller.signal.aborted) setPage(value); }).catch(() => { if (!controller.signal.aborted) setError(true); });
    return () => controller.abort();
  }, [propertyId, offset, open, retry]);
  function refresh(next = offset) { setPage(null); setError(false); setOffset(next); setRetry(value => value + 1); }
  return <section className="property-reviews" aria-label="Recenzije gostiju">
    <button className="ph-outline" aria-expanded={open} onClick={() => { if (!open) refresh(); setOpen(!open); }}>{open ? "Sakrij recenzije" : "Prikaži recenzije gostiju"}</button>
    {open && <><h3>Iskustva gostiju</h3><p>Recenzije su vezane za potvrđene rezervacije nakon dana odlaska.</p>
      {error ? <p role="alert">Recenzije nisu učitane. <button onClick={() => refresh()}>Pokušaj ponovo</button></p> : !page ? <p role="status">Učitavanje recenzija…</p> : <>
        <p>{page.total ? `Prosečna ocena: ${page.average_rating?.toLocaleString("sr-Latn", { maximumFractionDigits: 2 })} / 5 · Recenzija: ${page.total}` : "Još nema recenzija."}</p>
        {page.items.map(review => <article key={review.id} className="property-review"><strong>{review.rating} / 5 · Potvrđena rezervacija</strong><p className="ph-description">{review.comment}</p></article>)}
        <nav className="ph-pagination" aria-label="Stranice recenzija"><button className="ph-outline" disabled={offset === 0} onClick={() => refresh(Math.max(0, offset - 10))}>Prethodne recenzije</button><button className="ph-outline" disabled={!page.has_next} onClick={() => refresh(offset + 10)}>Sledeće recenzije</button></nav>
      </>}
    </>}
  </section>;
}
