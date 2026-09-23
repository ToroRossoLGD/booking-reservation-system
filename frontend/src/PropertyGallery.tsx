import { useEffect, useRef, useState } from "react";
import { api } from "./api";
import type { PropertyPhoto } from "./property-types";
import "./property-photos.css";

export default function PropertyGallery({ photos, title }: { photos: PropertyPhoto[]; title: string }) {
  const [index, setIndex] = useState(0);
  const [open, setOpen] = useState(false);
  const [failed, setFailed] = useState<Set<string>>(new Set());
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const element = dialog.current;
    const previousOverflow = document.body.style.overflow;
    if (open) document.body.style.overflow = "hidden";
    if (open) element?.showModal(); else element?.close();
    return () => { element?.close(); if (open) document.body.style.overflow = previousOverflow; };
  }, [open]);
  function source(photo: PropertyPhoto, thumbnail = false) { return api.propertyPhotoUrl(photo.property_id, photo.id, thumbnail); }
  function fail(url: string) { setFailed(current => new Set(current).add(url)); }
  const current = photos[index] ?? photos[0];
  if (!current) return null;
  const cover = source(photos[0], true);
  const full = source(current);
  function move(amount: number) { setIndex(value => (value + amount + photos.length) % photos.length); }
  return <>
    <button type="button" className="property-photo-cover" aria-label={`Otvori galeriju: ${title}`} onClick={() => { setIndex(0); setOpen(true); }}>
      {failed.has(cover) ? <span>Fotografija trenutno nije dostupna</span> : <img src={cover} alt={title} loading="lazy" onError={() => fail(cover)} />}
      <span className="property-photo-count">Fotografije: {photos.length}</span>
    </button>
    <dialog ref={dialog} className="property-photo-dialog" aria-label={`Galerija: ${title}`} onCancel={() => setOpen(false)} onClick={event => { if (event.target === event.currentTarget) setOpen(false); }} onKeyDown={event => { if (event.key === "ArrowRight") { event.preventDefault(); move(1); } if (event.key === "ArrowLeft") { event.preventDefault(); move(-1); } }}>
      {open && <div className="property-photo-dialog-panel">
        <header><h2>{title}</h2><button autoFocus type="button" onClick={() => setOpen(false)}>Zatvori galeriju</button></header>
        <div className="property-photo-stage">{failed.has(full) ? <p role="alert">Fotografija nije dostupna. <button onClick={() => setFailed(new Set())}>Pokušaj ponovo</button></p> : <img src={full} alt={`${title} — fotografija ${index + 1}`} onError={() => fail(full)} />}</div>
        <div className="property-photo-controls"><button disabled={photos.length < 2} onClick={() => move(-1)}>Prethodna fotografija</button><span role="status">{index + 1} / {photos.length}</span><button disabled={photos.length < 2} onClick={() => move(1)}>Sledeća fotografija</button></div>
        <div className="property-photo-thumbnails">{photos.map((photo, photoIndex) => <button key={photo.id} aria-label={`Prikaži fotografiju ${photoIndex + 1}`} aria-pressed={photoIndex === index} onClick={() => setIndex(photoIndex)}>{failed.has(source(photo, true)) ? <span>{photoIndex + 1}</span> : <img src={source(photo, true)} alt="" loading="lazy" onError={() => fail(source(photo, true))} />}</button>)}</div>
      </div>}
    </dialog>
  </>;
}
