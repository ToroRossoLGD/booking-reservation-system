import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { api, ApiError } from "./api";
import type { PropertyPage } from "./property-types";
import PropertyCard from "./PropertyCard";
import SavePropertyButton from "./SavePropertyButton";
import "./property-home.css";
import "./property-refresh.css";
import "./saved-properties.css";

function sessionSnapshot() { return localStorage.getItem("bookica_token") ?? ""; }
function subscribeSession(callback: () => void) {
  window.addEventListener("storage", callback);
  window.addEventListener("focus", callback);
  return () => {
    window.removeEventListener("storage", callback);
    window.removeEventListener("focus", callback);
  };
}
export default function SavedPropertiesPage() {
  const session = useSyncExternalStore(subscribeSession, sessionSnapshot);
  return <SavedContent key={session} session={session} />;
}
function SavedContent({ session }: { session: string }) {
  const [page, setPage] = useState<PropertyPage | null>(null);
  const [offset, setOffset] = useState(0);
  const [version, setVersion] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [login, setLogin] = useState(false);
  const heading = useRef<HTMLHeadingElement>(null);
  const restoreFocus = useRef(false);
  useEffect(() => {
    if (!loading && restoreFocus.current) {
      heading.current?.focus();
      restoreFocus.current = false;
    }
  }, [loading]);
  useEffect(() => {
    const controller = new AbortController();
    api.savedProperties(offset, controller.signal).then(result => {
      if (controller.signal.aborted || sessionSnapshot() !== session) return;
      // Listings can be withdrawn or removed on another device between pages.
      if (result.items.length === 0 && offset > 0) {
        setOffset(Math.min(offset - 12, Math.max(0, Math.floor((result.total - 1) / 12) * 12)));
        return;
      }
      setPage(result); setLoading(false);
    }).catch(err => {
      if (!controller.signal.aborted && sessionSnapshot() === session) {
        const unauthorized = err instanceof ApiError && err.status === 401;
        setLogin(unauthorized); setLoading(false);
        setError(unauthorized ? "Prijavi se da vidiš svoje sačuvane oglase." : "Sačuvani oglasi nisu učitani. Pokušaj ponovo.");
      }
    });
    return () => controller.abort();
  }, [offset, version, session]);
  function reload(nextOffset = offset) { restoreFocus.current = true; setLoading(true); setError(""); setLogin(false); setOffset(nextOffset); setVersion(value => value + 1); }
  return <div className="property-home saved-properties-page">
    <header className="ph-header"><a href="/" className="ph-brand">bookica.</a><a className="ph-outline" href="/account">Moj nalog</a></header>
    <main id="main-content" tabIndex={-1}>
      <div className="saved-properties-heading"><p className="ph-eyebrow">TVOJ IZBOR</p><h1 ref={heading} tabIndex={-1}>Sačuvani oglasi</h1><p>Stanovi koje želiš da pogledaš ponovo — za odmor, najam ili novi dom.</p><a href="/">Pronađi još nekretnina ↗</a></div>
      <p className="saved-properties-note">Prikazujemo trenutno objavljene oglase i aktuelne cene. Čuvanje oglasa ne rezerviše nekretninu.</p>
      <button className="ph-outline" disabled={loading} onClick={() => reload()}>Osveži oglase</button>
      {loading ? <p role="status">Učitavanje sačuvanih oglasa…</p> : error ? <div className="ph-empty" role="alert"><p>{error}</p>{login && <a className="ph-outline" href="/account">Prijavi se</a>}<button className="ph-outline" onClick={() => reload()}>Pokušaj ponovo</button></div> : page && <>
        <p role="status">Sačuvano oglasa: {page.total}</p>
        {page.items.length === 0 ? <div className="ph-empty"><h2>Još nema sačuvanih oglasa za prikaz.</h2><p>Izaberi „Sačuvaj oglas“ na nekretnini koja ti se dopada. Povučeni oglasi nisu vidljivi dok ih vlasnik ponovo ne objavi.</p><a className="ph-primary" href="/">Istraži ponudu</a></div> : <div className="ph-grid">{page.items.map(property => <PropertyCard key={property.id} property={property} saveAction={<SavePropertyButton propertyId={property.id} title={property.title} saved onChange={() => reload(page.items.length === 1 && offset > 0 ? Math.max(0, offset - 12) : offset)} />} />)}</div>}
        {(offset > 0 || page.has_next) && <nav className="ph-pagination" aria-label="Stranice sačuvanih oglasa"><button className="ph-outline" disabled={offset === 0} onClick={() => reload(Math.max(0, offset - 12))}>Prethodna</button><span>Stranica {Math.floor(offset / 12) + 1}</span><button className="ph-outline" disabled={!page.has_next} onClick={() => reload(offset + 12)}>Sledeća</button></nav>}
      </>}
    </main>
  </div>;
}
