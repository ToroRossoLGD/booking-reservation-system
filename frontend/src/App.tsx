import { FormEvent, ReactNode, useEffect, useMemo, useState } from "react";
import { api } from "./api";
import type { Quote, Resource, User, Venue } from "./types";

const categories = [
  { icon: "work", label: "Workspaces", copy: "Desks, studios & meeting rooms" },
  { icon: "sport", label: "Sports", copy: "Courts, fields & training spaces" },
  { icon: "event", label: "Events", copy: "Venues made for gathering" },
  { icon: "wellness", label: "Wellness", copy: "Calm spaces for body & mind" },
];

function Icon({ name, size = 20 }: { name: string; size?: number }) {
  const paths: Record<string, ReactNode> = {
    search: <><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></>,
    pin: <><path d="M20 10c0 5-8 11-8 11S4 15 4 10a8 8 0 1 1 16 0Z"/><circle cx="12" cy="10" r="2.5"/></>,
    arrow: <><path d="M5 12h14M14 7l5 5-5 5"/></>,
    close: <path d="m6 6 12 12M18 6 6 18"/>,
    user: <><circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/></>,
    users: <><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/></>,
    work: <><rect x="3" y="7" width="18" height="12" rx="2"/><path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M3 12h18"/></>,
    sport: <><circle cx="12" cy="12" r="9"/><path d="M8 4.8c4 3.2 6 7.5 6 12.9M4 14c5-1 9.7-4.2 12.6-8M5.5 18c3-1.7 7.8-2 12.7-.2"/></>,
    event: <><path d="M4 5h16v16H4zM8 3v4M16 3v4M4 10h16"/><path d="m9 16 2 2 4-5"/></>,
    wellness: <><path d="M12 21c0-7-4-10-9-11 0 6 3 10 9 11ZM12 21c0-8 4-13 9-15 0 7-3 13-9 15Z"/></>,
    clock: <><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></>,
    shield: <><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z"/><path d="m9 12 2 2 4-4"/></>,
    spark: <path d="m12 3 1.5 5.5L19 10l-5.5 1.5L12 17l-1.5-5.5L5 10l5.5-1.5L12 3Z"/>,
    chevron: <path d="m9 18 6-6-6-6"/>,
  };
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>;
}

function formatMoney(cents: number, currency: string) {
  return new Intl.NumberFormat("en", { style: "currency", currency, maximumFractionDigits: 0 }).format(cents / 100);
}

function AuthModal({ onClose, onAuthenticated }: { onClose: () => void; onAuthenticated: (user: User) => void }) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError("");
    try {
      if (mode === "register") await api.register(email, password);
      await api.login(email, password);
      onAuthenticated(await api.me()); onClose();
    } catch (err) { setError(err instanceof Error ? err.message : "Unable to continue"); }
    finally { setBusy(false); }
  }
  return <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
    <section className="auth-modal" role="dialog" aria-modal="true" aria-label="Account access">
      <button className="icon-button modal-close" onClick={onClose} aria-label="Close"><Icon name="close" /></button>
      <div className="mini-mark"><span>BL</span></div>
      <p className="eyebrow">Welcome to Booklane</p>
      <h2>{mode === "login" ? "Good to see you again." : "Your next space is waiting."}</h2>
      <p className="modal-copy">{mode === "login" ? "Sign in to manage reservations and saved places." : "Create an account to book in a few simple steps."}</p>
      <form onSubmit={submit} className="auth-form">
        <label>Email address<input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" required /></label>
        <label>Password<input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="At least 8 characters" minLength={8} required /></label>
        {error && <p className="form-error">{error}</p>}
        <button className="button primary full" disabled={busy}>{busy ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}</button>
      </form>
      <button className="text-button" onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(""); }}>
        {mode === "login" ? "New here? Create an account" : "Already have an account? Sign in"}
      </button>
    </section>
  </div>;
}

function BookingModal({ resource, user, onClose, requestLogin }: { resource: Resource; user: User | null; onClose: () => void; requestLogin: () => void }) {
  const [tomorrow] = useState(() => new Date(Date.now() + 86400000).toISOString().slice(0, 10));
  const [date, setDate] = useState(tomorrow); const [start, setStart] = useState("10:00");
  const [duration, setDuration] = useState(60); const [party, setParty] = useState(1);
  const [quote, setQuote] = useState<Quote | null>(null); const [error, setError] = useState("");
  const [busy, setBusy] = useState(false); const [complete, setComplete] = useState(false);
  const times = useMemo(() => {
    const startTime = new Date(`${date}T${start}:00`); const endTime = new Date(startTime.getTime() + duration * 60000);
    return [startTime.toISOString(), endTime.toISOString()] as const;
  }, [date, start, duration]);
  useEffect(() => { let active = true; const timer = setTimeout(() => { setQuote(null); setError(""); api.quote(resource.id, times[0], times[1], party).then((q) => active && setQuote(q)).catch((e) => active && setError(e.message)); }, 300); return () => { active = false; clearTimeout(timer); }; }, [resource.id, times, party]);
  async function reserve() {
    if (!user) { onClose(); requestLogin(); return; }
    setBusy(true); setError("");
    try { await api.reserve(resource.id, times[0], times[1], party); setComplete(true); }
    catch (err) { setError(err instanceof Error ? err.message : "Booking failed"); }
    finally { setBusy(false); }
  }
  return <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
    <section className="booking-modal" role="dialog" aria-modal="true">
      <button className="icon-button modal-close" onClick={onClose} aria-label="Close"><Icon name="close" /></button>
      {complete ? <div className="success-state"><div className="success-icon"><Icon name="shield" size={32} /></div><p className="eyebrow">Reservation started</p><h2>Your space is on hold.</h2><p>Head to your reservations to complete payment before the hold expires.</p><button className="button primary" onClick={onClose}>Done</button></div> : <>
        <p className="eyebrow">Reserve your time</p><h2>{resource.name}</h2><p className="modal-copy">Choose what works for you. You’ll see the exact price before confirming.</p>
        <div className="booking-grid">
          <label>Date<input type="date" min={tomorrow} value={date} onChange={(e) => setDate(e.target.value)} /></label>
          <label>Start time<input type="time" value={start} onChange={(e) => setStart(e.target.value)} /></label>
          <label>Duration<select value={duration} onChange={(e) => setDuration(Number(e.target.value))}><option value="60">1 hour</option><option value="90">1.5 hours</option><option value="120">2 hours</option><option value="180">3 hours</option></select></label>
          <label>Guests<input type="number" min="1" max={resource.capacity} value={party} onChange={(e) => setParty(Number(e.target.value))} /></label>
        </div>
        <div className="quote-box"><span>{quote ? `${quote.duration_minutes} minutes · total` : "Checking price…"}</span><strong>{quote ? formatMoney(quote.amount_cents, quote.currency) : "—"}</strong></div>
        {error && <p className="form-error">{error}</p>}
        <button className="button primary full" onClick={reserve} disabled={!quote || busy}>{busy ? "Reserving…" : user ? "Reserve this space" : "Sign in to reserve"}</button>
        <p className="fine-print"><Icon name="shield" size={15} /> Your slot is held for 15 minutes after reservation.</p>
      </>}
    </section>
  </div>;
}

export default function App() {
  const [venues, setVenues] = useState<Venue[]>([]); const [resources, setResources] = useState<Resource[]>([]);
  const [selectedVenue, setSelectedVenue] = useState<Venue | null>(null); const [booking, setBooking] = useState<Resource | null>(null);
  const [user, setUser] = useState<User | null>(null); const [authOpen, setAuthOpen] = useState(false);
  const [query, setQuery] = useState(""); const [loading, setLoading] = useState(true); const [apiOffline, setApiOffline] = useState(false);
  useEffect(() => { api.venues().then(setVenues).catch(() => setApiOffline(true)).finally(() => setLoading(false)); api.me().then(setUser).catch(() => localStorage.removeItem("booklane_token")); }, []);
  useEffect(() => { if (selectedVenue) api.resources(selectedVenue.id).then(setResources).catch(() => setResources([])); }, [selectedVenue]);
  const filtered = venues.filter((v) => `${v.name} ${v.address} ${v.description ?? ""}`.toLowerCase().includes(query.toLowerCase()));
  function scrollToExplore() { document.getElementById("explore")?.scrollIntoView({ behavior: "smooth" }); }
  return <div className="app-shell">
    <header className="site-header"><a className="brand" href="#top" aria-label="Booklane home"><span className="brand-mark">BL</span><span>booklane</span></a><nav><a href="#explore">Explore</a><a href="#how">How it works</a><a href="#host">List your space</a></nav><div className="nav-actions">{user ? <button className="profile-pill"><span>{user.email[0].toUpperCase()}</span>{user.email.split("@")[0]}</button> : <><button className="button ghost" onClick={() => setAuthOpen(true)}>Sign in</button><button className="button dark" onClick={() => setAuthOpen(true)}>Get started</button></>}</div></header>
    <main id="top">
      <section className="hero"><div className="hero-glow one"/><div className="hero-glow two"/><div className="hero-copy"><div className="availability-pill"><span/> Spaces available near you</div><h1>The right space.<br/><em>Right when you need it.</em></h1><p>Discover and reserve remarkable places for work, play, and everything in between—all in a few effortless clicks.</p><div className="hero-search"><Icon name="search" size={23}/><input value={query} onChange={(e) => setQuery(e.target.value)} onKeyDown={(e) => e.key === "Enter" && scrollToExplore()} placeholder="Search spaces or locations" aria-label="Search venues"/><button onClick={scrollToExplore}>Find a space <Icon name="arrow"/></button></div><div className="trust-row"><span><Icon name="shield" size={17}/> Secure booking</span><span><Icon name="clock" size={17}/> Instant confirmation</span><span><Icon name="spark" size={17}/> Handpicked spaces</span></div></div>
        <div className="hero-art" aria-hidden="true"><div className="art-card main-art"><div className="art-window"><span/><span/><span/></div><div className="art-table"><i/><i/><i/></div><div className="sun-patch"/></div><div className="floating-card"><div className="float-icon"><Icon name="event"/></div><div><small>Next available</small><strong>Today, 2:30 PM</strong></div><span className="live-dot"/></div><div className="rating-chip"><strong>4.9</strong><span>★★★★★</span><small>top-rated spaces</small></div></div>
      </section>
      <section className="category-section"><div className="section-heading compact"><p className="eyebrow">Find your fit</p><h2>What are you making space for?</h2></div><div className="category-grid">{categories.map((c) => <button className="category-card" key={c.label} onClick={() => { setQuery(c.label.slice(0, -1)); scrollToExplore(); }}><span className="category-icon"><Icon name={c.icon} size={25}/></span><span><strong>{c.label}</strong><small>{c.copy}</small></span><Icon name="chevron" size={18}/></button>)}</div></section>
      <section className="explore-section" id="explore"><div className="section-heading"><div><p className="eyebrow">Explore nearby</p><h2>Spaces worth showing up for</h2></div><p>Flexible, trusted, and ready when you are.</p></div>
        {loading ? <div className="loading-grid">{[1,2,3].map((i)=><div className="venue-skeleton" key={i}/>)}</div> : apiOffline ? <div className="empty-state"><span><Icon name="spark" size={28}/></span><h3>We’re getting the spaces ready.</h3><p>Start the backend to load live venues. The frontend is connected and waiting.</p></div> : filtered.length === 0 ? <div className="empty-state"><span><Icon name="search" size={28}/></span><h3>{venues.length ? "No spaces match that search." : "The first spaces are coming soon."}</h3><p>{venues.length ? "Try a location, venue name, or a broader category." : "Create a venue in the API and it will appear here automatically."}</p>{query && <button className="text-button" onClick={()=>setQuery("")}>Clear search</button>}</div> : <div className="venue-grid">{filtered.slice(0,6).map((venue,index)=><article className="venue-card" key={venue.id} onClick={()=>setSelectedVenue(venue)}><div className={`venue-visual visual-${index%3}`}><span className="venue-type">Bookable venue</span><span className="visual-monogram">{venue.name.slice(0,2).toUpperCase()}</span></div><div className="venue-body"><div><h3>{venue.name}</h3><p><Icon name="pin" size={15}/>{venue.address}</p></div><span className="card-arrow"><Icon name="arrow"/></span><p className="venue-description">{venue.description || "A flexible space ready for your next plan."}</p><div className="venue-meta"><span><Icon name="clock" size={16}/> From {venue.minimum_booking_duration_minutes} min</span><span>Free cancellation · {venue.free_cancellation_hours}h</span></div></div></article>)}</div>}
      </section>
      <section className="how-section" id="how"><div className="section-heading compact centered"><p className="eyebrow">Simple by design</p><h2>From idea to booked in minutes.</h2></div><div className="steps"><div><span>01</span><h3>Discover</h3><p>Find a space by location, purpose, capacity, and time.</p></div><i/><div><span>02</span><h3>Choose your time</h3><p>See live availability and a clear price before you commit.</p></div><i/><div><span>03</span><h3>Show up</h3><p>Reserve securely, get confirmation, and focus on your plan.</p></div></div></section>
      <section className="host-section" id="host"><div><p className="eyebrow light">For space owners</p><h2>Your empty hours<br/>could be someone’s<br/>perfect moment.</h2><p>Put your venue to work with flexible rules, real-time scheduling, and tools built to keep operations simple.</p><button className="button cream" onClick={()=>setAuthOpen(true)}>List your space <Icon name="arrow"/></button></div><div className="host-art"><div className="host-stat"><small>Bookings this month</small><strong>+38%</strong><div className="bars"><i/><i/><i/><i/><i/><i/></div></div><div className="host-orbit"><span>BL</span></div></div></section>
    </main>
    <footer><a className="brand footer-brand" href="#top"><span className="brand-mark">BL</span><span>booklane</span></a><p>Make room for what matters.</p><div><a href="#explore">Explore</a><a href="#how">How it works</a><a href="#host">For owners</a></div><small>© {new Date().getFullYear()} Booklane</small></footer>
    {selectedVenue && <div className="drawer-backdrop" onMouseDown={(e)=>e.target===e.currentTarget&&setSelectedVenue(null)}><aside className="venue-drawer"><button className="icon-button drawer-close" onClick={()=>setSelectedVenue(null)}><Icon name="close"/></button><div className="drawer-hero"><span>{selectedVenue.name.slice(0,2).toUpperCase()}</span></div><p className="eyebrow">Venue details</p><h2>{selectedVenue.name}</h2><p className="location-line"><Icon name="pin" size={17}/>{selectedVenue.address}</p><p className="drawer-copy">{selectedVenue.description || "A flexible, reservable venue for your next plan."}</p><div className="policy-row"><span><Icon name="clock"/><small>Minimum booking</small><strong>{selectedVenue.minimum_booking_duration_minutes} minutes</strong></span><span><Icon name="shield"/><small>Free cancellation</small><strong>Up to {selectedVenue.free_cancellation_hours}h before</strong></span></div><div className="resource-heading"><h3>Choose a space</h3><span>{resources.length} available</span></div><div className="resource-list">{resources.length ? resources.map((resource)=><button className="resource-row" key={resource.id} onClick={()=>setBooking(resource)}><span className="resource-icon"><Icon name={resource.resource_type.toLowerCase().includes("court")?"sport":"work"}/></span><span><strong>{resource.name}</strong><small>{resource.resource_type} · up to {resource.capacity} guests</small></span><span className="resource-price"><strong>{formatMoney(resource.hourly_rate_cents,resource.currency)}</strong><small>/ hour</small></span><Icon name="chevron" size={17}/></button>) : <p className="drawer-empty">No resources have been added to this venue yet.</p>}</div></aside></div>}
    {authOpen && <AuthModal onClose={()=>setAuthOpen(false)} onAuthenticated={setUser}/>} {booking && <BookingModal resource={booking} user={user} onClose={()=>setBooking(null)} requestLogin={()=>setAuthOpen(true)}/>} 
  </div>;
}
