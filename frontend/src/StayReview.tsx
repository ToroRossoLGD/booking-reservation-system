import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "./api";
import type { PropertyReview } from "./property-review-types";

export default function StayReview({ stayId }: { stayId: number }) {
  const [open, setOpen] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [review, setReview] = useState<PropertyReview | null>(null);
  const [rating, setRating] = useState("");
  const [comment, setComment] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [retry, setRetry] = useState(0);
  const inFlight = useRef(false);
  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    api.stayReview(stayId, controller.signal).then(value => { if (!controller.signal.aborted) { setReview(value); setLoaded(true); } }).catch(() => { if (!controller.signal.aborted) setError("Recenzija nije učitana. Pokušaj ponovo."); });
    return () => controller.abort();
  }, [stayId, open, retry]);
  function refresh() { setLoaded(false); setError(""); setRetry(value => value + 1); }
  async function submit() {
    if (inFlight.current) return;
    inFlight.current = true; setBusy(true); setError("");
    try { setReview(await api.createPropertyReview(stayId, { rating: Number(rating), comment: comment.trim() })); }
    catch (err) { setError(err instanceof ApiError && err.status === 409 ? "Ovaj boravak već ima recenziju. Osveži recenziju da je vidiš." : err instanceof ApiError && [400, 404, 422].includes(err.status) ? "Proveri ocenu i komentar. Recenzija je dostupna samo gostu, od dana nakon odlaska." : "Potvrda nije stigla. Pokušaj ponovo; isti komentar neće napraviti duplikat."); }
    finally { inFlight.current = false; setBusy(false); }
  }
  return <section className="property-reviews" aria-label={`Moja recenzija boravka ${stayId}`}>
    <button className="ph-outline" disabled={busy} aria-expanded={open} onClick={() => { if (!open) refresh(); setOpen(!open); }}>{open ? "Zatvori recenziju" : "Oceni boravak / moja recenzija"}</button>
    {open && <>
      {error && <p role="alert">{error} <button disabled={busy} onClick={refresh}>Osveži recenziju</button></p>}
      {!loaded ? !error && <p role="status">Učitavanje recenzije…</p> : review ? <div className="property-review" role="status"><strong>Tvoja ocena: {review.rating} / 5</strong><p className="ph-description">{review.comment}</p></div> : <form onSubmit={event => { event.preventDefault(); void submit(); }}>
        <p>Jedna recenzija po boravku. Ocena i komentar su javni, bez tvog imena, emaila i datuma boravka. Objavljena recenzija se ovde ne može menjati.</p>
        <fieldset disabled={busy}>
          <label>Ocena<select required value={rating} onChange={event => setRating(event.target.value)}><option value="">Izaberi ocenu</option>{[1, 2, 3, 4, 5].map(value => <option key={value} value={value}>{value} / 5</option>)}</select></label>
          <label>Komentar<textarea required minLength={10} maxLength={2000} rows={4} value={comment} onChange={event => setComment(event.target.value)} /></label>
          <button className="ph-primary" disabled={busy}>{busy ? "Objavljivanje…" : "Objavi recenziju"}</button>
        </fieldset>
      </form>}
    </>}
  </section>;
}
