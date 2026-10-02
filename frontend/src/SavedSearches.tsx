import { useEffect, useState } from "react";
import AccountSavedSearches from "./AccountSavedSearches";
import { MAX_SAVED_SEARCHES, normalizedSearchPath, readSavedSearches, SAVED_SEARCHES_KEY, writeSavedSearches } from "./saved-searches";
import type { SavedSearch } from "./saved-searches";
import "./saved-searches.css";

const storageError = "Pretrage nisu sačuvane. Proveri da li pregledač dozvoljava lokalno čuvanje i pokušaj ponovo.";

function load() {
  try { return { items: readSavedSearches(), error: "" }; }
  catch { return { items: [] as SavedSearch[], error: "Sačuvane pretrage trenutno nisu dostupne u ovom pregledaču." }; }
}

export default function SavedSearches({ path }: { path: string }) {
  const [state, setState] = useState(load);
  const [name, setName] = useState("");
  const [message, setMessage] = useState("");
  const normalized = normalizedSearchPath(path);
  const existing = state.items.find(item => item.path === normalized);

  useEffect(() => {
    function sync(event: StorageEvent) {
      if (event.key === SAVED_SEARCHES_KEY || event.key === null) { setState(load()); setMessage(""); }
    }
    window.addEventListener("storage", sync);
    return () => window.removeEventListener("storage", sync);
  }, []);

  function change(update: (items: SavedSearch[]) => SavedSearch[], success: string) {
    setMessage("");
    try {
      const items = update(readSavedSearches());
      writeSavedSearches(items);
      setState({ items, error: "" }); setMessage(success);
    } catch (error) {
      setState(current => ({ ...current, error: error instanceof RangeError ? error.message : storageError }));
    }
  }

  return <section className="saved-searches" aria-label="Sačuvane pretrage">
    <h2>Sačuvane pretrage</h2>
    <p>Sačuvaj do {MAX_SAVED_SEARCHES} pretraga u ovom pregledaču. Otvaraju se od prve stranice, sa istim filterima i datumima. Za nove oglase se ne šalju obaveštenja.</p>
    <form onSubmit={event => {
      event.preventDefault();
      if (!name.trim() || normalized === null) return;
      change(items => {
        const previous = items.find(item => item.path === normalized);
        if (!previous && items.length >= MAX_SAVED_SEARCHES) throw new RangeError("Sačuvano je 10 pretraga. Ukloni jednu da dodaš novu.");
        const entry = { name: name.trim(), path: normalized };
        return previous ? items.map(item => item.path === normalized ? entry : item) : [...items, entry];
      }, "Pretraga je sačuvana u ovom pregledaču.");
    }}>
      <label>Naziv pretrage<input required maxLength={60} value={name} onChange={event => { setName(event.target.value); setMessage(""); }} placeholder="Na primer: Dvosoban stan u Novom Sadu" /></label>
      <button className="ph-outline" type="submit" disabled={!name.trim() || normalized === null}>{existing ? "Promeni naziv sačuvane pretrage" : "Sačuvaj trenutnu pretragu"}</button>
    </form>
    {existing && <p>Ovi filteri su već sačuvani kao „{existing.name}“.</p>}
    {state.error && <p role="alert">{state.error} <button type="button" onClick={() => { setState(load()); setMessage(""); }}>Osveži sačuvane pretrage</button></p>}
    {message && <p role="status">{message}</p>}
    {!state.items.length && !state.error && <p>Još nema sačuvanih pretraga.</p>}
    <ul>{state.items.map(item => <li key={item.path}>
      <a href={item.path}>{item.name}</a>
      <button type="button" className="ph-outline" aria-label={`Ukloni pretragu: ${item.name}`} onClick={() => change(items => items.filter(saved => saved.path !== item.path), "Pretraga je uklonjena.")}>Ukloni</button>
    </li>)}</ul>
    <small>Pretrage nisu povezane sa nalogom. Dostupne su svakome ko koristi ovaj profil pregledača; brisanjem podataka pregledača uklanjaš i njih. Sačuvane datume po potrebi promeni pre nove pretrage.</small>
    <AccountSavedSearches path={path} localItems={state.items} />
  </section>;
}
