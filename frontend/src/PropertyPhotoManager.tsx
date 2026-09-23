import { useEffect, useState } from "react";
import { api, ApiError } from "./api";
import type { PropertyPhoto } from "./property-types";
import "./property-photos.css";

function OwnerPhoto({ photo }: { photo: PropertyPhoto }) {
  const [url, setUrl] = useState("");
  const [error, setError] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    let objectUrl = "";
    api.ownerPhotoBlob(photo.property_id, photo.id, controller.signal).then(blob => {
      if (!controller.signal.aborted) { objectUrl = URL.createObjectURL(blob); setUrl(objectUrl); }
    }).catch(() => { if (!controller.signal.aborted) setError(true); });
    return () => { controller.abort(); if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [photo.id, photo.property_id]);
  return url && !error ? <img src={url} alt={`Fotografija ${photo.position + 1}`} onError={() => setError(true)} /> : <p>{error ? "Pregled nije dostupan" : "Učitavanje fotografije…"}</p>;
}

type PendingPhoto = { file: File; requestId: string };
function errorMessage(err: unknown) {
  const status = err instanceof ApiError ? err.status : 0;
  return status === 413 ? "Fotografija je prevelika: do 10 MB i 20 megapiksela." : status === 415 ? "Fajl nije ispravna JPEG, PNG ili WebP fotografija." : status === 409 ? "Lista fotografija se promenila ili je dostignut limit od 12. Osveži fotografije." : status === 503 ? "Čuvanje fotografija još nije podešeno na serveru." : status === 401 || status === 403 ? "Proveri prijavu i pristup ovom oglasu." : "Izmena nije uspela. Pokušaj ponovo.";
}

export default function PropertyPhotoManager({ propertyId, title }: { propertyId: number; title: string }) {
  const [photos, setPhotos] = useState<PropertyPhoto[]>([]);
  const [pending, setPending] = useState<PendingPhoto[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [version, setVersion] = useState(0);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [deleteId, setDeleteId] = useState<number | null>(null);
  useEffect(() => {
    let active = true;
    api.ownerPhotos(propertyId).then(result => { if (active) { setPhotos(result); setLoading(false); } }).catch(err => { if (active) { setError(errorMessage(err)); setLoading(false); } });
    return () => { active = false; };
  }, [propertyId, version]);
  async function upload() {
    setBusy(true); setError(""); setNotice("");
    let uploaded = 0;
    for (const item of pending) {
      try {
        const photo = await api.uploadPropertyPhoto(propertyId, item.file, item.requestId);
        setPhotos(current => [...current.filter(existing => existing.id !== photo.id), photo].sort((a, b) => a.position - b.position));
        setPending(current => current.filter(candidate => candidate.requestId !== item.requestId));
        uploaded += 1;
      } catch (err) { setError(`${item.file.name}: ${errorMessage(err)} Preostali fajlovi su sačuvani za ponovni pokušaj.`); break; }
    }
    if (uploaded) setNotice(`Dodato fotografija: ${uploaded}.`);
    setBusy(false);
  }
  async function reorder(ids: number[]) {
    setBusy(true); setError(""); setNotice("");
    try { setPhotos(await api.reorderPropertyPhotos(propertyId, ids)); setNotice("Redosled je sačuvan. Prva fotografija je naslovna."); }
    catch (err) { setError(errorMessage(err)); }
    finally { setBusy(false); }
  }
  function move(index: number, step: number) {
    const ids = photos.map(photo => photo.id);
    [ids[index], ids[index + step]] = [ids[index + step], ids[index]];
    void reorder(ids);
  }
  async function remove(id: number) {
    setBusy(true); setError(""); setNotice("");
    try { await api.deletePropertyPhoto(propertyId, id); setPhotos(current => current.filter(photo => photo.id !== id)); setDeleteId(null); setNotice("Fotografija je uklonjena."); }
    catch (err) { setError(errorMessage(err)); }
    finally { setBusy(false); }
  }
  return <section className="property-photo-manager" aria-label={`Fotografije: ${title}`}>
    <h3>Fotografije: {title}</h3><p>Do 12 fotografija. JPEG, PNG ili WebP, do 10 MB i 20 megapiksela po fajlu. Prva fotografija je naslovna.</p>
    <button type="button" disabled={busy || loading} onClick={() => { setLoading(true); setError(""); setVersion(value => value + 1); }}>Osveži fotografije</button>
    {loading ? <p role="status">Učitavanje fotografija…</p> : <fieldset disabled={busy}>
      <label>Dodaj fotografije<input type="file" accept="image/jpeg,image/png,image/webp" multiple onChange={event => {
        const files = Array.from(event.target.files ?? []); event.target.value = ""; setError("");
        if (files.some(file => file.size > 10 * 1024 * 1024) || files.length + photos.length + pending.length > 12) { setError("Izaberi fajlove do 10 MB, najviše 12 fotografija ukupno."); return; }
        setPending(current => [...current, ...files.map(file => ({ file, requestId: crypto.randomUUID() }))]);
      }} /></label>
      {pending.length > 0 && <div><ul>{pending.map(item => <li key={item.requestId}>{item.file.name} <button type="button" aria-label={`Ukloni iz reda: ${item.file.name}`} onClick={() => setPending(current => current.filter(candidate => candidate.requestId !== item.requestId))}>Ukloni iz reda</button></li>)}</ul><button type="button" onClick={() => void upload()}>Otpremi fotografije ({pending.length})</button></div>}
      {photos.length === 0 && <p>Još nema fotografija. Oglas trenutno prikazuje ilustraciju.</p>}
      <ol className="property-photo-editor-grid">{photos.map((photo, index) => <li key={photo.id}>
        <OwnerPhoto photo={photo} /><strong>{index === 0 ? "Naslovna fotografija" : `Fotografija ${index + 1}`}</strong>
        <div><button type="button" disabled={index === 0} aria-label={`Postavi fotografiju ${index + 1} kao naslovnu`} onClick={() => void reorder([photo.id, ...photos.filter(item => item.id !== photo.id).map(item => item.id)])}>Naslovna</button>
          <button type="button" disabled={index === 0} aria-label={`Pomeri fotografiju ${index + 1} ranije`} onClick={() => move(index, -1)}>←</button><button type="button" disabled={index === photos.length - 1} aria-label={`Pomeri fotografiju ${index + 1} kasnije`} onClick={() => move(index, 1)}>→</button>
          <button type="button" aria-label={`Obriši fotografiju ${index + 1}`} onClick={() => setDeleteId(photo.id)}>Obriši</button></div>
        {deleteId === photo.id && <div><p>Trajno ukloniti ovu fotografiju iz oglasa?</p><button type="button" onClick={() => void remove(photo.id)}>Potvrdi brisanje</button><button type="button" onClick={() => setDeleteId(null)}>Odustani</button></div>}
      </li>)}</ol>
    </fieldset>}
    {busy && <p role="status">Čuvanje fotografija…</p>}{error && <p role="alert">{error}</p>}{notice && <p role="status">{notice}</p>}
  </section>;
}
