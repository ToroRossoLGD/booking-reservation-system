const shortcuts = [
  { href: "/saved", icon: "♡", title: "Sačuvano za kasnije", description: "Vrati se oglasima koji su ti privukli pažnju.", action: "Otvori sačuvane oglase" },
  { href: "/stays", icon: "⌂", title: "Planirani boravci", description: "Pregledaj datume, potvrde i detalje rezervacija.", action: "Pregledaj boravke" },
  { href: "/rentals", icon: "↔", title: "Dogovori za najam", description: "Nastavi razgovor i dogovori razgledanje stana.", action: "Pregledaj upite" },
  { href: "/account/notifications", icon: "◎", title: "Tvoja obaveštenja", description: "Proveri potvrde, predloge termina i promene.", action: "Otvori obaveštenja" },
];

export default function PropertyShortcuts() {
  return <section className="ph-shortcuts" aria-labelledby="shortcuts-title">
    <div className="ph-section-heading"><div><p className="ph-eyebrow">TVOJA BOOKICA</p><h2 id="shortcuts-title">Nastavi gde si stao.</h2><p>Oglasi, boravci i dogovori na jednom mestu. Za lične podatke potrebna je prijava.</p></div></div>
    <div className="ph-shortcut-grid">{shortcuts.map(item => <a className="ph-shortcut" href={item.href} key={item.href}>
      <span className="ph-shortcut-icon" aria-hidden="true">{item.icon}</span>
      <h3>{item.title}</h3><p>{item.description}</p><span className="ph-shortcut-action">{item.action} <span aria-hidden="true">↗</span></span>
    </a>)}</div>
  </section>;
}
