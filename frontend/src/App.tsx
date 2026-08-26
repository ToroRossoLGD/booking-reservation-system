import { FormEvent, ReactNode, useEffect, useMemo, useState } from "react";
import { api, googleLoginUrl } from "./api";
import type { PopularVenue, Promotion, Quote, Resource, User, Venue } from "./types";

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
    menu: <><path d="M4 7h16M4 12h16M4 17h16"/></>,
    logout: <><path d="M10 17l5-5-5-5M15 12H3"/><path d="M14 4h5a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-5"/></>,
  };
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>;
}

function formatMoney(cents: number, currency: string) {
  return new Intl.NumberFormat("en", { style: "currency", currency, maximumFractionDigits: 0 }).format(cents / 100);
}

function formatAvailability(value: string | null) {
  if (!value) return "Check availability";
  const date = new Date(value);
  const today = new Date();
  const tomorrow = new Date(today); tomorrow.setDate(today.getDate() + 1);
  const day = date.toDateString() === today.toDateString() ? "Today" : date.toDateString() === tomorrow.toDateString() ? "Tomorrow" : new Intl.DateTimeFormat("en", { weekday: "short", month: "short", day: "numeric" }).format(date);
  return `${day}, ${new Intl.DateTimeFormat("en", { hour: "numeric", minute: "2-digit" }).format(date)}`;
}

async function getPopularVenues(venues: Venue[]): Promise<PopularVenue[]> {
  const upcomingDates = Array.from({ length: 7 }, (_, offset) => {
    const date = new Date(); date.setDate(date.getDate() + offset);
    const year = date.getFullYear(); const month = String(date.getMonth() + 1).padStart(2, "0"); const day = String(date.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
  });
  const enriched = await Promise.all(venues.map(async (venue) => {
    const resources = await api.resources(venue.id).catch(() => []);
    const summaries = await Promise.all(resources.map((resource) => api.ratingSummary(resource.id).catch(() => ({ resource_id: resource.id, average_rating: 0, review_count: 0 }))));
    const reviewCount = summaries.reduce((total, summary) => total + summary.review_count, 0);
    const ratingTotal = summaries.reduce((total, summary) => total + summary.average_rating * summary.review_count, 0);
    let firstAvailableAt: string | null = null;
    for (const date of upcomingDates) {
      const slots = (await Promise.all(resources.map((resource) => api.availableSlots(resource.id, date).catch(() => [])))).flat();
      const first = slots.filter((slot) => slot.available && new Date(slot.start_time) > new Date()).sort((a, b) => a.start_time.localeCompare(b.start_time))[0];
      if (first) { firstAvailableAt = first.start_time; break; }
    }
    return { ...venue, average_rating: reviewCount ? ratingTotal / reviewCount : null, review_count: reviewCount, first_available_at: firstAvailableAt };
  }));
  return enriched.sort((a, b) => (b.average_rating ?? 0) - (a.average_rating ?? 0) || b.review_count - a.review_count).slice(0, 3);
}

function consumeOAuthRedirect() {
  const params = new URLSearchParams(window.location.hash.slice(1));
  const token = params.get("auth_token"); const error = params.get("auth_error") ?? "";
  if (token || error) window.history.replaceState(null, "", `${window.location.pathname}${window.location.search}`);
  if (token) localStorage.setItem("bookica_token", token);
  return { error };
}

const oauthRedirect = consumeOAuthRedirect();

function AuthModal({ initialMode, initialError = "", onClose, onAuthenticated }: { initialMode: "login" | "register"; initialError?: string; onClose: () => void; onAuthenticated: (user: User) => void }) {
  const [mode, setMode] = useState<"login" | "register">(initialMode);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(initialError);
  const [busy, setBusy] = useState(false);
  const socialProviders = [
    { name: "Google", mark: "G", url: googleLoginUrl },
    { name: "LinkedIn", mark: "in", url: import.meta.env.VITE_LINKEDIN_AUTH_URL },
    { name: "X", mark: "X", url: import.meta.env.VITE_X_AUTH_URL },
    { name: "Facebook", mark: "f", url: import.meta.env.VITE_FACEBOOK_AUTH_URL },
  ];
  function socialLogin(provider: (typeof socialProviders)[number]) {
    if (!provider.url) {
      setError(`${provider.name} login is not configured yet.`);
      return;
    }
    window.location.assign(provider.url);
  }
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
      <div className="mini-mark"><span>B</span></div>
      <p className="eyebrow">Welcome to Bookica</p>
      <h2>{mode === "login" ? "Good to see you again." : "Your next space is waiting."}</h2>
      <p className="modal-copy">{mode === "login" ? "Sign in to manage reservations and saved places." : "Create an account to book in a few simple steps."}</p>
      {mode === "login" && <>
        <div className="social-grid">
          {socialProviders.map((provider) => <button type="button" className="social-button" key={provider.name} onClick={() => socialLogin(provider)} aria-label={`Log in with ${provider.name}`}><span className={`social-mark ${provider.name.toLowerCase()}`}>{provider.mark}</span><strong>{provider.name}</strong></button>)}
        </div>
        <div className="auth-divider"><span>or log in with email</span></div>
      </>}
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
  const [coupon, setCoupon] = useState("");
  const [quote, setQuote] = useState<Quote | null>(null); const [error, setError] = useState("");
  const [busy, setBusy] = useState(false); const [complete, setComplete] = useState(false);
  const times = useMemo(() => {
    const startTime = new Date(`${date}T${start}:00`); const endTime = new Date(startTime.getTime() + duration * 60000);
    return [startTime.toISOString(), endTime.toISOString()] as const;
  }, [date, start, duration]);
  useEffect(() => { let active = true; const timer = setTimeout(() => { setQuote(null); setError(""); api.quote(resource.id, times[0], times[1], party, coupon.trim()).then((q) => active && setQuote(q)).catch((e) => active && setError(e.message)); }, 300); return () => { active = false; clearTimeout(timer); }; }, [resource.id, times, party, coupon]);
  async function reserve() {
    if (!user) { onClose(); requestLogin(); return; }
    setBusy(true); setError("");
    try { await api.reserve(resource.id, times[0], times[1], party, coupon.trim()); setComplete(true); }
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
          <label className="coupon-field">Coupon code <span>Optional</span><input value={coupon} onChange={(e) => setCoupon(e.target.value.toUpperCase())} placeholder="Enter coupon" /></label>
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
  const [user, setUser] = useState<User | null>(null); const [authMode, setAuthMode] = useState<"login" | "register" | null>(oauthRedirect.error ? "login" : null); const [authError, setAuthError] = useState(oauthRedirect.error);
  const [popularVenues, setPopularVenues] = useState<PopularVenue[]>([]); const [popularLoading, setPopularLoading] = useState(true);
  const [promotions, setPromotions] = useState<Promotion[]>([]); const [copiedCode, setCopiedCode] = useState<string | null>(null);
  const [query, setQuery] = useState(""); const [loading, setLoading] = useState(true); const [apiOffline, setApiOffline] = useState(false);
  useEffect(() => { api.venues().then(setVenues).catch(() => setApiOffline(true)).finally(() => setLoading(false)); api.me().then(setUser).catch(() => localStorage.removeItem("bookica_token")); }, []);
  useEffect(() => { api.activePromotions().then(setPromotions).catch(() => setPromotions([])); }, []);
  useEffect(() => { if (!venues.length) return; let active = true; getPopularVenues(venues).then((items) => active && setPopularVenues(items)).finally(() => active && setPopularLoading(false)); return () => { active = false; }; }, [venues]);
  useEffect(() => { if (selectedVenue) api.resources(selectedVenue.id).then(setResources).catch(() => setResources([])); }, [selectedVenue]);
  const filtered = venues.filter((v) => `${v.name} ${v.address} ${v.description ?? ""}`.toLowerCase().includes(query.toLowerCase()));
  function scrollToExplore() { document.getElementById("explore")?.scrollIntoView({ behavior: "smooth" }); }
  function exploreCategory(label = "") { setQuery(label); scrollToExplore(); }
  function logOut() { localStorage.removeItem("bookica_token"); setUser(null); }
  async function copyCoupon(code: string) { await navigator.clipboard.writeText(code); setCopiedCode(code); window.setTimeout(() => setCopiedCode((current) => current === code ? null : current), 1800); }
  return <div className="app-shell">
    <header className="site-header"><a className="brand" href="#top" aria-label="Bookica home"><span className="brand-mark">B</span><span>Bookica</span></a><nav>
      <details className="nav-dropdown"><summary>Explore <Icon name="chevron" size={14}/></summary><div className="dropdown-panel explore-menu"><button onClick={() => exploreCategory()}>All spaces<small>Browse every available venue</small></button>{categories.map((category) => <button key={category.label} onClick={() => exploreCategory(category.label.slice(0, -1))}><Icon name={category.icon} size={18}/><span>{category.label}<small>{category.copy}</small></span></button>)}</div></details>
      <a href="#how">How it works</a><a href="#host">List your space</a>
    </nav><div className="nav-actions"><details className="mobile-menu"><summary aria-label="Open navigation"><Icon name="menu"/></summary><div className="dropdown-panel mobile-panel"><strong>Explore</strong><button onClick={() => exploreCategory()}>All spaces</button>{categories.map((category) => <button key={category.label} onClick={() => exploreCategory(category.label.slice(0, -1))}>{category.label}</button>)}<a href="#how">How it works</a><a href="#host">List your space</a></div></details>{user ? <details className="profile-menu"><summary className="profile-pill"><span>{user.email[0].toUpperCase()}</span>{user.email.split("@")[0]}<Icon name="chevron" size={14}/></summary><div className="dropdown-panel profile-panel"><div className="profile-identity"><strong>{user.email.split("@")[0]}</strong><small>{user.email}</small></div><button disabled>My reservations <small>Coming soon</small></button><button disabled>Favorites <small>Coming soon</small></button><button disabled>Notifications <small>Coming soon</small></button><button disabled>Account settings <small>Coming soon</small></button><a href="#host">List or manage my space</a><button className="logout-item" onClick={logOut}><Icon name="logout" size={16}/>Log out</button></div></details> : <><button className="button ghost" onClick={() => setAuthMode("login")}>Log in</button><button className="button dark" onClick={() => setAuthMode("register")}>Sign up</button></>}</div></header>
    <main id="top">
      <section className="hero"><div className="hero-glow one"/><div className="hero-glow two"/><div className="hero-copy"><div className="availability-pill"><span/> Spaces available near you</div><h1>The right space.<br/><em>Right when you need it.</em></h1><p>Discover and reserve remarkable places for work, play, and everything in between—all in a few effortless clicks.</p><div className="hero-search"><Icon name="search" size={23}/><input value={query} onChange={(e) => setQuery(e.target.value)} onKeyDown={(e) => e.key === "Enter" && scrollToExplore()} placeholder="Search spaces or locations" aria-label="Search venues"/><button onClick={scrollToExplore}>Find a space <Icon name="arrow"/></button></div><div className="trust-row"><span><Icon name="shield" size={17}/> Secure booking</span><span><Icon name="clock" size={17}/> Instant confirmation</span><span><Icon name="spark" size={17}/> Handpicked spaces</span></div></div>
        <div className="hero-art" aria-hidden="true"><div className="art-card main-art"><div className="art-window"><span/><span/><span/></div><div className="art-table"><i/><i/><i/></div><div className="sun-patch"/></div><div className="floating-card"><div className="float-icon"><Icon name="event"/></div><div><small>Next available</small><strong>Today, 2:30 PM</strong></div><span className="live-dot"/></div><div className="rating-chip"><strong>4.9</strong><span>★★★★★</span><small>top-rated spaces</small></div></div>
      </section>
      <section className="popular-section" aria-labelledby="popular-title"><div className="section-heading"><div><p className="eyebrow">Popular now</p><h2 id="popular-title">Guest favorites, ready when you are.</h2></div><p>Ranked by verified ratings and review activity.</p></div>
        {popularLoading && venues.length > 0 ? <div className="popular-grid">{[1,2,3].map((item) => <div className="popular-skeleton" key={item}/>)}</div> : popularVenues.length > 0 && <div className="popular-grid">{popularVenues.map((venue, index) => <button className="popular-card" key={venue.id} onClick={() => setSelectedVenue(venue)}><span className={`popular-visual visual-${index%3}`}><span className="popular-rank">#{index + 1} popular</span><strong>{venue.name.slice(0,2).toUpperCase()}</strong></span><span className="popular-content"><span className="popular-title"><span><strong>{venue.name}</strong><small><Icon name="pin" size={14}/>{venue.address}</small></span><span className="popular-rating"><strong>{venue.average_rating?.toFixed(1) ?? "New"}</strong><small>{venue.review_count ? `★ ${venue.review_count} review${venue.review_count === 1 ? "" : "s"}` : "No reviews yet"}</small></span></span><span className="popular-availability"><Icon name="clock" size={17}/><span><small>First availability</small><strong>{formatAvailability(venue.first_available_at)}</strong></span><Icon name="arrow" size={18}/></span></span></button>)}</div>}
      </section>
      {promotions.length > 0 && <section className="offers-section" aria-labelledby="offers-title"><div className="offers-heading"><div><p className="eyebrow light">Limited-time offers</p><h2 id="offers-title">A little more room in your budget.</h2><p>Copy a coupon and enter it when you reserve the matching venue.</p></div><span className="offer-mark">%</span></div><div className="offers-grid">{promotions.slice(0,3).map((promotion) => { const venue = venues.find((item) => item.id === promotion.venue_id); return <article className="offer-card" key={promotion.id}><div className="offer-value"><strong>{promotion.discount_percent}%</strong><span>off</span></div><div className="offer-copy"><small>{venue?.name ?? "Selected venue"}</small><strong>Save on your next reservation</strong><span>Valid until {new Intl.DateTimeFormat("en", { month: "short", day: "numeric" }).format(new Date(promotion.valid_until))}</span></div><button className="coupon-button" onClick={() => copyCoupon(promotion.code)} aria-label={`Copy coupon ${promotion.code}`}><span>{promotion.code}</span><strong>{copiedCode === promotion.code ? "Copied!" : "Copy code"}</strong></button>{venue && <button className="offer-arrow" onClick={() => setSelectedVenue(venue)} aria-label={`View ${venue.name}`}><Icon name="arrow" size={18}/></button>}</article>; })}</div></section>}
      <section className="category-section"><div className="section-heading compact"><p className="eyebrow">Find your fit</p><h2>What are you making space for?</h2></div><div className="category-grid">{categories.map((c) => <button className="category-card" key={c.label} onClick={() => { setQuery(c.label.slice(0, -1)); scrollToExplore(); }}><span className="category-icon"><Icon name={c.icon} size={25}/></span><span><strong>{c.label}</strong><small>{c.copy}</small></span><Icon name="chevron" size={18}/></button>)}</div></section>
      <section className="explore-section" id="explore"><div className="section-heading"><div><p className="eyebrow">Explore nearby</p><h2>Spaces worth showing up for</h2></div><p>Flexible, trusted, and ready when you are.</p></div>
        {loading ? <div className="loading-grid">{[1,2,3].map((i)=><div className="venue-skeleton" key={i}/>)}</div> : apiOffline ? <div className="empty-state"><span><Icon name="spark" size={28}/></span><h3>We’re getting the spaces ready.</h3><p>Start the backend to load live venues. The frontend is connected and waiting.</p></div> : filtered.length === 0 ? <div className="empty-state"><span><Icon name="search" size={28}/></span><h3>{venues.length ? "No spaces match that search." : "The first spaces are coming soon."}</h3><p>{venues.length ? "Try a location, venue name, or a broader category." : "Create a venue in the API and it will appear here automatically."}</p>{query && <button className="text-button" onClick={()=>setQuery("")}>Clear search</button>}</div> : <div className="venue-grid">{filtered.slice(0,6).map((venue,index)=><article className="venue-card" key={venue.id} onClick={()=>setSelectedVenue(venue)}><div className={`venue-visual visual-${index%3}`}><span className="venue-type">Bookable venue</span><span className="visual-monogram">{venue.name.slice(0,2).toUpperCase()}</span></div><div className="venue-body"><div><h3>{venue.name}</h3><p><Icon name="pin" size={15}/>{venue.address}</p></div><span className="card-arrow"><Icon name="arrow"/></span><p className="venue-description">{venue.description || "A flexible space ready for your next plan."}</p><div className="venue-meta"><span><Icon name="clock" size={16}/> From {venue.minimum_booking_duration_minutes} min</span><span>Free cancellation · {venue.free_cancellation_hours}h</span></div></div></article>)}</div>}
      </section>
      <section className="how-section" id="how"><div className="section-heading compact centered"><p className="eyebrow">Simple by design</p><h2>From idea to booked in minutes.</h2></div><div className="steps"><div><span>01</span><h3>Discover</h3><p>Find a space by location, purpose, capacity, and time.</p></div><i/><div><span>02</span><h3>Choose your time</h3><p>See live availability and a clear price before you commit.</p></div><i/><div><span>03</span><h3>Show up</h3><p>Reserve securely, get confirmation, and focus on your plan.</p></div></div></section>
      <section className="host-section" id="host"><div><p className="eyebrow light">For space owners</p><h2>Your empty hours<br/>could be someone’s<br/>perfect moment.</h2><p>Put your venue to work with flexible rules, real-time scheduling, and tools built to keep operations simple.</p><button className="button cream" onClick={()=>setAuthMode("register")}>List your space <Icon name="arrow"/></button></div><div className="host-art"><div className="host-stat"><small>Bookings this month</small><strong>+38%</strong><div className="bars"><i/><i/><i/><i/><i/><i/></div></div><div className="host-orbit"><span>B</span></div></div></section>
    </main>
    <footer><a className="brand footer-brand" href="#top"><span className="brand-mark">B</span><span>Bookica</span></a><p>Make room for what matters.</p><div><a href="#explore">Explore</a><a href="#how">How it works</a><a href="#host">For owners</a></div><small>© {new Date().getFullYear()} Bookica</small></footer>
    {selectedVenue && <div className="drawer-backdrop" onMouseDown={(e)=>e.target===e.currentTarget&&setSelectedVenue(null)}><aside className="venue-drawer"><button className="icon-button drawer-close" onClick={()=>setSelectedVenue(null)}><Icon name="close"/></button><div className="drawer-hero"><span>{selectedVenue.name.slice(0,2).toUpperCase()}</span></div><p className="eyebrow">Venue details</p><h2>{selectedVenue.name}</h2><p className="location-line"><Icon name="pin" size={17}/>{selectedVenue.address}</p><p className="drawer-copy">{selectedVenue.description || "A flexible, reservable venue for your next plan."}</p><div className="policy-row"><span><Icon name="clock"/><small>Minimum booking</small><strong>{selectedVenue.minimum_booking_duration_minutes} minutes</strong></span><span><Icon name="shield"/><small>Free cancellation</small><strong>Up to {selectedVenue.free_cancellation_hours}h before</strong></span></div><div className="resource-heading"><h3>Choose a space</h3><span>{resources.length} available</span></div><div className="resource-list">{resources.length ? resources.map((resource)=><button className="resource-row" key={resource.id} onClick={()=>setBooking(resource)}><span className="resource-icon"><Icon name={resource.resource_type.toLowerCase().includes("court")?"sport":"work"}/></span><span><strong>{resource.name}</strong><small>{resource.resource_type} · up to {resource.capacity} guests</small></span><span className="resource-price"><strong>{formatMoney(resource.hourly_rate_cents,resource.currency)}</strong><small>/ hour</small></span><Icon name="chevron" size={17}/></button>) : <p className="drawer-empty">No resources have been added to this venue yet.</p>}</div></aside></div>}
    {authMode && <AuthModal initialMode={authMode} initialError={authError} onClose={()=>{setAuthMode(null);setAuthError("");}} onAuthenticated={setUser}/>}
    {booking && <BookingModal resource={booking} user={user} onClose={()=>setBooking(null)} requestLogin={()=>setAuthMode("login")}/>}
  </div>;
}
