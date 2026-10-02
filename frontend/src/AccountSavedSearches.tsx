import { useEffect, useState, useSyncExternalStore } from "react";
import { api, ApiError } from "./api";
import { normalizedSearchPath } from "./saved-searches";
import type { AccountSearch, SavedSearch } from "./saved-searches";

function tokenSnapshot() {
  try { return localStorage.getItem("bookica_token") ?? ""; } catch { return ""; }
}
function subscribe(callback: () => void) {
  window.addEventListener("storage", callback);
  window.addEventListener("focus", callback);
  return () => { window.removeEventListener("storage", callback); window.removeEventListener("focus", callback); };
}

export default function AccountSavedSearches(props: { path: string; localItems: SavedSearch[] }) {
  const token = useSyncExternalStore(subscribe, tokenSnapshot);
  return token ? <AccountSearchPanel key={token} {...props} token={token} /> : <p><a href="/account">Prijavi se</a> da sačuvaš pretrage na nalogu i otvaraš ih na drugim uređajima.</p>;
}

function AccountSearchPanel({ path, localItems, token }: { path: string; localItems: SavedSearch[]; token: string }) {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<AccountSearch[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [version, setVersion] = useState(0);
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const normalized = normalizedSearchPath(path);
  const existing = items.find(item => normalizedSearchPath(item.path) === normalized);

  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    api.accountSearches(controller.signal).then(result => {
      if (!controller.signal.aborted && tokenSnapshot() === token) { setItems(result); setLoading(false); }
    }).catch(() => {
      if (!controller.signal.aborted && tokenSnapshot() === token) { setError("Pretrage sa naloga nisu učitane. Proveri prijavu i pokušaj ponovo."); setLoading(false); }
    });
    return () => controller.abort();
  }, [open, version, token]);

  async function mutate(data: SavedSearch | number | { searchId: number; enabled: boolean }) {
    if (busy || loading || tokenSnapshot() !== token) return;
    setBusy(true); setError(""); setMessage("");
    try {
      if (typeof data === "number") {
        await api.removeAccountSearch(data);
        if (tokenSnapshot() === token) { setItems(current => current.filter(item => item.id !== data)); setMessage("Pretraga je uklonjena sa naloga."); }
      } else {
        const saved = "searchId" in data ? await api.setSearchAlerts(data.searchId, data.enabled) : await api.saveAccountSearch({ name: data.name, path: data.path });
        if (tokenSnapshot() === token) {
          setItems(current => [...current.filter(item => item.id !== saved.id), saved].sort((a, b) => a.id - b.id));
          setMessage("searchId" in data ? (saved.alerts_enabled ? "Obaveštenja su uključena." : "Obaveštenja su isključena.") : "Pretraga je sačuvana na nalogu.");
        }
      }
    } catch (err) {
      if (tokenSnapshot() === token) setError(err instanceof ApiError && err.status === 409 ? "Na nalogu već imaš 10 pretraga. Ukloni neku ili osveži listu." : "Izmena nije potvrđena. Proveri prijavu i pokušaj ponovo.");
    } finally { if (tokenSnapshot() === token) setBusy(false); }
  }

  return <div className="account-searches">
    <button className="ph-outline" type="button" aria-expanded={open} onClick={() => { if (!open) { setLoading(true); setError(""); setMessage(""); } setOpen(value => !value); }}>Pretrage na nalogu</button>
    {open && <section aria-label="Pretrage na nalogu">
      <h3>Pretrage na nalogu</h3>
      <p>Do 10 pretraga dostupnih na svim uređajima na kojima se prijaviš. Lokalne pretrage prenosiš pojedinačno; ostaju sačuvane i u pregledaču.</p>
      <p>Obaveštenja uključuješ posebno za svaku pretragu. Stižu u <a href="/account/notifications">inbox u aplikaciji</a> za nove oglase objavljene nakon uključivanja. Stariji oglasi i kasnije izmene ne šalju nova obaveštenja. Obrada može potrajati nekoliko minuta; dostupnost proveri na oglasu.</p>
      <button className="ph-outline" type="button" disabled={busy || loading} onClick={() => { setLoading(true); setError(""); setMessage(""); setVersion(value => value + 1); }}>Osveži pretrage na nalogu</button>
      {loading && <p role="status">Učitavanje pretraga sa naloga…</p>}
      {error && <p role="alert">{error}</p>}
      {message && <p role="status">{message}</p>}
      <form onSubmit={event => { event.preventDefault(); if (normalized && name.trim()) void mutate({ name: name.trim(), path: normalized }); }}>
        <label>Naziv pretrage na nalogu<input required maxLength={60} value={name} onChange={event => setName(event.target.value)} /></label>
        <button type="submit" className="ph-outline" disabled={busy || loading || !name.trim()}>{existing ? "Promeni naziv na nalogu" : "Sačuvaj pretragu na nalogu"}</button>
      </form>
      {!loading && !error && !items.length && <p>Još nema pretraga na nalogu.</p>}
      <ul>{items.map(item => <li key={item.id} className="account-search-row"><a href={normalizedSearchPath(item.path) ?? "/"}>{item.name}</a><span>Obaveštenja: {item.alerts_enabled ? "uključena" : "isključena"}</span><div><button className="ph-outline" type="button" disabled={busy || loading} aria-pressed={!!item.alerts_enabled} aria-label={`${item.alerts_enabled ? "Isključi" : "Uključi"} obaveštenja: ${item.name}`} onClick={() => void mutate({ searchId: item.id, enabled: !item.alerts_enabled })}>{item.alerts_enabled ? "Isključi obaveštenja" : "Uključi obaveštenja"}</button><button className="ph-outline" type="button" disabled={busy || loading} aria-label={`Ukloni sa naloga: ${item.name}`} onClick={() => void mutate(item.id)}>Ukloni</button></div></li>)}</ul>
      {!!localItems.length && <><h4>Prenesi iz ovog pregledača</h4><ul>{localItems.map(item => <li key={item.path}><span>{item.name}</span><button className="ph-outline" type="button" disabled={busy || loading || items.some(saved => normalizedSearchPath(saved.path) === item.path)} aria-label={`Sačuvaj na nalogu: ${item.name}`} onClick={() => void mutate(item)}>Sačuvaj na nalogu</button></li>)}</ul></>}
    </section>}
  </div>;
}
