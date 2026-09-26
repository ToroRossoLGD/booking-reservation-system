import { lazy, Suspense, useEffect, useState } from "react";
import type { FormEvent } from "react";
import { api, ApiError } from "./api";
import { offerLabels, priceUnits, propertyPrice } from "./property-types";
import type { OfferType, PropertyInput, PropertyListing, PropertyPage } from "./property-types";
import type { OwnerVenue } from "./types";
import "./property-home.css";

const StayBlockManager = lazy(() => import("./StayBlockManager"));
const PropertyPhotoManager = lazy(() => import("./PropertyPhotoManager"));

export default function PropertyManager({ venues }: { venues: OwnerVenue[] }) {
  const [page, setPage] = useState<PropertyPage | null>(null);
  const [offset, setOffset] = useState(0);
  const [version, setVersion] = useState(0);
  const [editing, setEditing] = useState<PropertyListing | "new" | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [type, setType] = useState<OfferType>("short_stay");
  const [blockListing, setBlockListing] = useState<PropertyListing | null>(null);
  const [photoListing, setPhotoListing] = useState<PropertyListing | null>(null);

  useEffect(() => {
    let cancelled = false;
    api.ownerProperties(offset).then(result => {
      if (!cancelled) { setPage(result); setLoading(false); }
    }).catch(() => {
      if (!cancelled) { setError("Oglasi nisu učitani. Pokušaj ponovo."); setLoading(false); }
    });
    return () => { cancelled = true; };
  }, [offset, version]);

  function refresh(nextOffset = offset) {
    setError(""); setLoading(true); setOffset(nextOffset); setVersion(value => value + 1);
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const fields = new FormData(event.currentTarget);
    const data: PropertyInput = {
      venue_id: Number(fields.get("venue_id")), title: String(fields.get("title")),
      description: String(fields.get("description")), city: String(fields.get("city")),
      offer_type: type, area_sqm: Number(fields.get("area_sqm")), rooms: Number(fields.get("rooms")),
      price_cents: Math.round(Number(fields.get("price")) * 100),
      currency: String(fields.get("currency")) as PropertyInput["currency"],
      contact_email: String(fields.get("contact_email")), is_published: fields.get("is_published") === "on",
      booking_enabled: type === "short_stay" && fields.get("booking_enabled") === "on",
      max_guests: Number(fields.get("max_guests") ?? current?.max_guests ?? 2),
      minimum_nights: Number(fields.get("minimum_nights") ?? current?.minimum_nights ?? 1),
      timezone: String(fields.get("timezone") ?? current?.timezone ?? "Europe/Belgrade"),
      check_in_time: type === "short_stay" ? String(fields.get("check_in_time") ?? "") || null : null,
      check_out_time: type === "short_stay" ? String(fields.get("check_out_time") ?? "") || null : null,
    };
    setBusy(true); setError(""); setMessage("");
    try {
      if (editing && editing !== "new") await api.updateProperty(editing.id, data);
      else await api.createProperty(data);
      setEditing(null); setMessage(data.is_published ? "Oglas je objavljen na naslovnoj strani." : "Nacrt je sačuvan. Nije vidljiv posetiocima."); refresh(0);
    } catch (err) {
      setError(err instanceof ApiError && err.status === 422 ? "Proveri sva polja, vremensku zonu i pravila boravka. Opis mora imati najmanje 20 znakova, a kontakt ispravnu email adresu." : err instanceof ApiError && err.status === 409 ? "Objekat ima satne resurse ili oglas ima rezervacije ili aktivne blokade. Za noćenja koristi objekat bez satnih resursa. Pre promene objekta ukloni blokade; oglas sa istorijom rezervacija ne može promeniti objekat." : "Čuvanje nije uspelo. Proveri prijavu i pokušaj ponovo.");
    } finally { setBusy(false); }
  }

  const current = editing && editing !== "new" ? editing : null;
  return <section className="ph-manager owner-panel" aria-label="Oglasi za nekretnine">
    <div className="ph-section-heading"><div><p className="eyebrow">NEKRETNINE</p><h2>Tvoji oglasi</h2></div><button className="button primary" disabled={!venues.length || busy} onClick={() => { setEditing("new"); setType("short_stay"); setError(""); setMessage(""); }}>Novi oglas</button></div>
    <p className="muted-copy">Poveži oglas sa svojim objektom, odredi cenu i objavi ponudu za prodaju ili najam. <a href="/">Pogledaj javnu ponudu ↗</a></p>
    <p><a href="/owner/stays">Pregledaj rezervacije stanova ↗</a> · <a href="/owner/rentals">Upiti za dugoročni najam ↗</a></p>
    {!venues.length && <p>Prvo dodaj objekat preko dugmeta „Add venue“, pa kreiraj oglas.</p>}
    {error && <p role="alert" className="error-message">{error}</p>}
    {message && <p role="status">{message}</p>}
    {blockListing && <><Suspense fallback={<p role="status">Učitavanje...</p>}><StayBlockManager key={blockListing.id} property={blockListing} /></Suspense><button className="ph-outline" onClick={() => setBlockListing(null)}>Zatvori blokade</button></>}
    {photoListing && <><Suspense fallback={<p role="status">Učitavanje fotografija…</p>}><PropertyPhotoManager key={photoListing.id} propertyId={photoListing.id} title={photoListing.title} /></Suspense><button className="ph-outline" type="button" onClick={() => setPhotoListing(null)}>Zatvori fotografije</button></>}
    {editing && <form key={current?.id ?? "new"} className="ph-property-form" onSubmit={save}>
      <h3>{current ? "Izmeni oglas" : "Nova nekretnina"}</h3>
      <fieldset disabled={busy}>
        <label>Objekat<select name="venue_id" required defaultValue={current?.venue_id ?? venues[0]?.id}>{venues.map(v => <option value={v.id} key={v.id}>{v.name}</option>)}</select></label>
        <label>Vrsta ponude<select value={type} onChange={e => setType(e.target.value as OfferType)}>{(Object.keys(offerLabels) as OfferType[]).map(value => <option key={value} value={value}>{offerLabels[value]}</option>)}</select></label>
        <label>Naslov oglasa<input name="title" minLength={3} maxLength={160} required defaultValue={current?.title} /></label>
        <label>Grad ili destinacija<input name="city" minLength={2} maxLength={100} required defaultValue={current?.city} /></label>
        <label>Površina (m²)<input name="area_sqm" type="number" min={1} max={100000} step={1} required defaultValue={current?.area_sqm} /></label>
        <label>Broj soba (0 za garsonjeru)<input name="rooms" type="number" min={0} max={100} step={1} required defaultValue={current?.rooms} /></label>
        <label>Cena / {priceUnits[type]}<input name="price" type="number" min="0.01" max="10000000000" step="0.01" required defaultValue={current ? current.price_cents / 100 : undefined} /></label>
        <label>Valuta<select name="currency" defaultValue={current?.currency ?? "EUR"}><option>EUR</option><option>RSD</option><option>USD</option></select></label>
        <label className="ph-form-wide">Opis<textarea name="description" minLength={20} maxLength={5000} rows={4} required defaultValue={current?.description} /></label>
        <label className="ph-form-wide">Javna kontakt email adresa<input name="contact_email" type="email" maxLength={254} required defaultValue={current?.contact_email} /><small>Ova adresa će biti dostupna posetiocima kada objaviš oglas.</small></label>
        <label className="ph-publish ph-form-wide"><input name="is_published" type="checkbox" defaultChecked={current?.is_published ?? false} />Objavi oglas (isključi da ga povučeš iz javne ponude)</label>
        {type === "short_stay" && <>
          <label>Prijava od<input name="check_in_time" type="time" step="60" defaultValue={current ? current.check_in_time ?? "" : "14:00"} /></label>
          <label>Odjava do<input name="check_out_time" type="time" step="60" defaultValue={current ? current.check_out_time ?? "" : "11:00"} /></label>
          <small className="ph-form-wide">Unesi oba vremena ili ostavi oba prazna za dogovor sa gostom. Važe u vremenskoj zoni smeštaja. Izmene važe samo za nove rezervacije.</small>
          <label>Maksimalan broj gostiju<input name="max_guests" type="number" min={1} max={100} required defaultValue={current?.max_guests ?? 2} /></label>
          <label>Minimalan broj noćenja<input name="minimum_nights" type="number" min={1} max={30} required defaultValue={current?.minimum_nights ?? 1} /></label>
          <label className="ph-form-wide">Vremenska zona<input name="timezone" required defaultValue={current?.timezone ?? "Europe/Belgrade"} maxLength={64} /><small>Na primer Europe/Belgrade, Europe/Podgorica ili Europe/Athens.</small></label>
          <label className="ph-publish ph-form-wide"><input name="booking_enabled" type="checkbox" defaultChecked={current?.booking_enabled ?? false} />Uključi rezervacije celog stana sa plaćanjem kod domaćina</label>
        </>}
      </fieldset>
      {type === "short_stay" && <p className="muted-copy">Cena je po noćenju. Svi oglasi povezani sa istim objektom dele zauzetost jednog celog stana. Rezervacije se potvrđuju odmah, uz besplatno otkazivanje pre dana dolaska i plaćanje kod domaćina.</p>}
      <div className="ph-form-actions"><button className="button primary" disabled={busy}>{busy ? "Čuvanje…" : "Sačuvaj oglas"}</button><button className="ph-outline" type="button" disabled={busy} onClick={() => setEditing(null)}>Odustani</button></div>
    </form>}
    {loading ? <p role="status">Učitavanje oglasa…</p> : <>
      {page?.items.map(p => <article key={p.id} className="ph-owner-listing"><div><strong>{p.title}</strong><p>{p.city} · {offerLabels[p.offer_type]} · {propertyPrice(p)} / {priceUnits[p.offer_type]}</p><small>{p.is_published ? "Objavljen" : "Nacrt"}</small></div><button className="ph-outline" disabled={busy} aria-label={`Blokade: ${p.title}`} onClick={() => setBlockListing(p)}>Zauzetost</button><button className="ph-outline" disabled={busy} aria-label={`Fotografije: ${p.title}`} onClick={() => setPhotoListing(p)}>Fotografije</button><button className="ph-outline" disabled={busy} onClick={() => { setEditing(p); setType(p.offer_type); setError(""); setMessage(""); }} aria-label={`Izmeni: ${p.title}`}>Izmeni</button></article>)}
      {page?.total === 0 && <p>Još nemaš oglase. Kreiraj prvi i sačuvaj ga kao nacrt ili objavi.</p>}
      <div className="ph-pagination"><button className="ph-outline" disabled={offset === 0 || busy} onClick={() => refresh(Math.max(0, offset - 20))}>Prethodna</button><button className="ph-outline" disabled={busy} onClick={() => refresh()}>Osveži oglase</button><button className="ph-outline" disabled={!page?.has_next || busy} onClick={() => refresh(offset + 20)}>Sledeća</button></div>
    </>}
  </section>;
}
