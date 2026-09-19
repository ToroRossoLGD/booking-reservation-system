import { useState } from "react";
import "./property-home.css";

const offers = ["Sve nekretnine", "Stan na dan", "Dugoročni najam", "Prodaja"] as const;
const properties = [
  { id: 1, name: "Jutro iznad borova", location: "Zlatibor", type: "Stan na dan", area: 48, rooms: 2, price: "65 €", unit: "noć", scene: "mountain", tag: "Planinski predah" },
  { id: 2, name: "Dom sa pogledom na grad", location: "Beograd", type: "Dugoročni najam", area: 72, rooms: 3, price: "850 €", unit: "mesec", scene: "city", tag: "Za novo poglavlje" },
  { id: 3, name: "Na korak od mora", location: "Budva", type: "Stan na dan", area: 56, rooms: 2, price: "90 €", unit: "noć", scene: "sea", tag: "Miris leta" },
  { id: 4, name: "Tvoj kutak na Limanu", location: "Novi Sad", type: "Prodaja", area: 64, rooms: 3, price: "156.000 €", unit: "ukupno", scene: "home", tag: "Mesto za život" },
];

export default function PropertyHome() {
  const [offer, setOffer] = useState<string>(offers[0]);
  const [location, setLocation] = useState("");
  const [query, setQuery] = useState("");
  const [saved, setSaved] = useState<number[]>([]);
  const [onlySaved, setOnlySaved] = useState(false);
  const [selected, setSelected] = useState<number | null>(null);
  const normalize = (value: string) => value.toLocaleLowerCase("sr-Latn").normalize("NFD").replace(/[\u0300-\u036f]/g, "");
  const visible = properties.filter(p => (offer === offers[0] || p.type === offer) && normalize(p.location).includes(normalize(query.trim())) && (!onlySaved || saved.includes(p.id)));

  return <div className="property-home">
    <header className="ph-header">
      <a className="ph-brand" href="/" aria-label="Bookica početna"><span>⌂</span> bookica<span className="ph-brand-dot">.</span></a>
      <nav aria-label="Glavna navigacija"><a href="#ponuda">Pronađi nekretninu</a><a href="#destinacije">Destinacije</a></nav>
      <a className="ph-outline" href="/owner">Za vlasnike ↗</a>
    </header>
    <main>
      <section className="ph-hero">
        <div className="ph-hero-copy"><p className="ph-eyebrow">TVOJE MESTO. TVOJ RITAM.</p><h1>Negde te čeka<br />tvoj <em>novi pogled.</em></h1><p>Za nekoliko dana, novo poglavlje ili ceo život.<br />Pronađi prostor u kom želiš da budeš.</p><a href="#ponuda" className="ph-text-link">Pronađi svoje mesto <span>↗</span></a></div>
        <div className="ph-hero-art" role="img" aria-label="Ilustracija sunčane kuće među zelenim brdima"><div className="ph-sun" /><div className="ph-hill ph-hill-back" /><div className="ph-hill" /><div className="ph-house"><div className="ph-window" /><div className="ph-door" /></div><span className="ph-art-caption">Manje svakodnevice. Više tvog sveta.</span></div>
      </section>
      <section className="ph-search" aria-label="Pretraga nekretnina">
        <div className="ph-tabs">{offers.map(item => <button key={item} type="button" aria-pressed={offer === item} className={offer === item ? "is-active" : ""} onClick={() => { setOffer(item); setSelected(null); }}>{item}</button>)}</div>
        <form onSubmit={e => { e.preventDefault(); setQuery(location); setSelected(null); document.getElementById("ponuda")?.scrollIntoView({ behavior: "smooth" }); }}><label>GDE ŽELIŠ DA BUDEŠ?<input value={location} onChange={e => setLocation(e.target.value)} placeholder="Grad ili destinacija" /></label><div className="ph-search-hint">Od gradskih adresa do mirnih obala.<br /><span>Pronađi mesto po svom ukusu.</span></div><button className="ph-primary" type="submit">Pretraži ponudu <span>↗</span></button></form>
      </section>
      <section className="ph-listings" id="ponuda">
        <div className="ph-section-heading"><div><p className="ph-eyebrow">PROSTORI ZA TVOJE PLANOVE</p><h2>Mesto koje ti pristaje.</h2></div><button className="ph-outline" aria-pressed={onlySaved} onClick={() => setOnlySaved(!onlySaved)}>{onlySaved ? "Prikaži sve" : `Sačuvano (${saved.length})`}</button></div>
        <p className="ph-demo">Primeri oglasa · Prikazane nekretnine i cene služe za pregled buduće ponude. Rezervacije i upiti još nisu dostupni na ovim oglasima.</p>
        <div className="ph-grid">{visible.map(p => <article className="ph-card" key={p.id}>
          <div className={`ph-card-art ph-scene-${p.scene}`}><span className="ph-tag">{p.tag}</span><button className="ph-save" aria-label={`${saved.includes(p.id) ? "Ukloni iz sačuvanih" : "Sačuvaj"}: ${p.name}`} aria-pressed={saved.includes(p.id)} onClick={() => setSaved(saved.includes(p.id) ? saved.filter(id => id !== p.id) : [...saved, p.id])}>{saved.includes(p.id) ? "♥" : "♡"}</button><div className="ph-mini-house"><i /><i /><i /></div><span className="ph-art-label">ILUSTRACIJA</span></div>
          <div className="ph-card-body"><p className="ph-location">{p.location} <span>· {p.type}</span></p><h3>{p.name}</h3><p className="ph-facts">{p.area} m² <span>·</span> {p.rooms} sobe</p><div className="ph-card-bottom"><p><strong>{p.price}</strong> / {p.unit}</p><button aria-expanded={selected === p.id} onClick={() => setSelected(selected === p.id ? null : p.id)} aria-label={`Detalji: ${p.name}`}>↗</button></div>{selected === p.id && <p className="ph-detail">Primer {p.type === "Prodaja" ? "oglasa za prodaju" : "smeštaja"} u mestu {p.location}. Galerija, opis i {p.type === "Stan na dan" ? "kalendar dostupnosti" : "kontakt vlasnika"} dolaze u sledećoj fazi.</p>}</div>
        </article>)}</div>
        {visible.length === 0 && <div className="ph-empty"><h3>Nema oglasa za ovaj izbor.</h3><p>Probaj drugu lokaciju ili pogledaj sve primere.</p><button className="ph-outline" onClick={() => { setOffer(offers[0]); setLocation(""); setQuery(""); setOnlySaved(false); }}>Prikaži sve primere</button></div>}
      </section>
      <section className="ph-destinations" id="destinacije"><div><p className="ph-eyebrow">PROMENI OKRUŽENJE</p><h2>Gde te vodi sledeći plan?</h2><p>Gradski ritam, planinska tišina ili dani uz more.</p></div><div className="ph-destination-links">{["Beograd", "Novi Sad", "Zlatibor", "Budva"].map(city => <a href="#ponuda" key={city} onClick={() => { setLocation(city); setQuery(city); setOffer(offers[0]); setOnlySaved(false); }}>{city}<span>↗</span></a>)}</div></section>
    </main>
    <footer className="ph-footer"><span className="ph-brand">bookica.</span><p>Mesto za odmor. Prostor za život.</p><a href="/booking">Postojeći sistem rezervacija ↗</a></footer>
  </div>;
}
