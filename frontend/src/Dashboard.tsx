import { FormEvent, useEffect, useState } from "react";
import { api } from "./api";
import type {
  AddOn,
  AvailabilityException,
  AvailabilityRule,
  Favorite,
  Notification,
  OwnerReservation,
  OwnerResource,
  OwnerStats,
  OwnerVenue,
  Reservation,
  ReservationWorkspace,
  User,
  Venue,
} from "./types";

type AccountTab = "reservations" | "favorites" | "notifications";

function money(cents: number, currency = "EUR") {
  return new Intl.NumberFormat("en", { style: "currency", currency }).format(
    cents / 100,
  );
}

function when(value: string) {
  return new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function Status({ value }: { value: string }) {
  return (
    <span className={`status-badge status-${value}`}>
      {value.replaceAll("_", " ")}
    </span>
  );
}

export function AccountDashboard({
  user,
  initialTab = "reservations",
  onExplore,
  reservationId,
  onOpenReservation,
  onCloseReservation,
}: {
  user: User;
  initialTab?: AccountTab;
  onExplore: () => void;
  reservationId?: number;
  onOpenReservation: (id: number) => void;
  onCloseReservation: () => void;
}) {
  const [tab, setTab] = useState<AccountTab>(initialTab);
  const [reservations, setReservations] = useState<Reservation[]>([]);
  const [favorites, setFavorites] = useState<Favorite[]>([]);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("");

  useEffect(() => {
    const task =
      tab === "reservations"
        ? api.myReservations().then((result) => setReservations(result.items))
        : tab === "favorites"
          ? api.favorites().then(setFavorites)
          : api
              .notifications()
              .then((result) => setNotifications(result.items));
    task
      .catch((error) =>
        setMessage(
          error instanceof Error ? error.message : "Unable to load this page",
        ),
      )
      .finally(() => setLoading(false));
  }, [tab]);

  if (reservationId)
    return (
      <ReservationDetail
        reservationId={reservationId}
        onBack={onCloseReservation}
      />
    );

  function chooseTab(nextTab: AccountTab) {
    setLoading(true);
    setMessage("");
    setTab(nextTab);
  }

  async function cancelReservation(id: number) {
    if (
      !window.confirm(
        "Cancel this reservation? The cancellation policy will be applied.",
      )
    )
      return;
    try {
      await api.cancelReservation(id);
      setReservations((items) =>
        items.map((item) =>
          item.id === id ? { ...item, status: "cancelled" } : item,
        ),
      );
      setMessage("Reservation cancelled.");
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : "Unable to cancel reservation",
      );
    }
  }

  async function payReservation(id: number) {
    try {
      setMessage("Opening Stripe's safe test checkout...");
      const checkout = await api.createCheckout(id);
      window.location.assign(checkout.checkout_url);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to start checkout");
    }
  }

  async function removeFavorite(resourceId: number) {
    try {
      await api.removeFavorite(resourceId);
      setFavorites((items) =>
        items.filter((item) => item.resource_id !== resourceId),
      );
      setMessage("Removed from favorites.");
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : "Unable to update favorites",
      );
    }
  }

  return (
    <main className="dashboard-page">
      <section className="dashboard-hero">
        <div>
          <p className="eyebrow">Your Bookica</p>
          <h1>Plans, places, and updates.</h1>
          <p>{user.email}</p>
        </div>
        <button className="button cream" onClick={onExplore}>
          Explore more spaces
        </button>
      </section>
      <div className="dashboard-layout">
        <aside className="dashboard-nav" aria-label="Account sections">
          <button
            className={tab === "reservations" ? "active" : ""}
            onClick={() => chooseTab("reservations")}
          >
            Reservations
          </button>
          <button
            className={tab === "favorites" ? "active" : ""}
            onClick={() => chooseTab("favorites")}
          >
            Favorites
          </button>
          <button
            className={tab === "notifications" ? "active" : ""}
            onClick={() => chooseTab("notifications")}
          >
            Notifications
          </button>
        </aside>
        <section className="dashboard-content" aria-live="polite">
          {message && <p className="dashboard-message">{message}</p>}
          {loading ? (
            <div className="dashboard-loading">Loading your {tab}…</div>
          ) : tab === "reservations" ? (
            <>
              <div className="dashboard-title">
                <div>
                  <p className="eyebrow">Bookings</p>
                  <h2>My reservations</h2>
                </div>
                <span>{reservations.length} total</span>
              </div>
              {reservations.length ? (
                <div className="data-list">
                  {reservations.map((item) => (
                    <article className="data-card" key={item.id}>
                      <div>
                        <Status value={item.status} />
                        <button
                          className="reservation-link"
                          onClick={() => onOpenReservation(item.id)}
                        >
                          Reservation #{item.id}
                        </button>
                        <p>
                          {when(item.start_time)} – {when(item.end_time)}
                        </p>
                        <small>
                          {item.party_size} guest
                          {item.party_size === 1 ? "" : "s"} ·{" "}
                          {money(
                            item.quoted_amount_cents,
                            item.quoted_currency,
                          )}
                        </small>
                      </div>
                    <div className="reservation-actions">
                    {item.status === "pending" && (
                      <button className="pay-button" onClick={() => payReservation(item.id)}>
                        Pay in test mode
                      </button>
                    )}
                    {["pending", "confirmed"].includes(item.status) && (
                        <button
                          className="danger-button"
                          onClick={() => cancelReservation(item.id)}
                        >
                          Cancel
                        </button>
                    )}
                    </div>
                    </article>
                  ))}
                </div>
              ) : (
                <Empty
                  title="No reservations yet"
                  copy="Find a space and your bookings will appear here."
                  action={onExplore}
                />
              )}
            </>
          ) : tab === "favorites" ? (
            <>
              <div className="dashboard-title">
                <div>
                  <p className="eyebrow">Saved</p>
                  <h2>Favorite spaces</h2>
                </div>
                <span>{favorites.length} saved</span>
              </div>
              {favorites.length ? (
                <div className="data-grid">
                  {favorites.map((item) => (
                    <article className="favorite-card" key={item.favorite_id}>
                      <div className="favorite-monogram">
                        {item.resource_name.slice(0, 2).toUpperCase()}
                      </div>
                      <div>
                        <small>{item.venue_name}</small>
                        <h3>{item.resource_name}</h3>
                        <p>
                          {item.resource_type} · up to {item.capacity} guests
                        </p>
                        <span>{item.venue_address}</span>
                      </div>
                      <button
                        onClick={() => removeFavorite(item.resource_id)}
                        aria-label={`Remove ${item.resource_name} from favorites`}
                      >
                        Remove
                      </button>
                    </article>
                  ))}
                </div>
              ) : (
                <Empty
                  title="Nothing saved yet"
                  copy="Favorite spaces will be kept here for later."
                  action={onExplore}
                />
              )}
            </>
          ) : (
            <>
              <div className="dashboard-title">
                <div>
                  <p className="eyebrow">Inbox</p>
                  <h2>Notifications</h2>
                </div>
                <span>
                  {notifications.filter((item) => !item.is_read).length} unread
                </span>
              </div>
              {notifications.length ? (
                <div className="notification-list">
                  {notifications.map((item) => (
                    <article
                      className={item.is_read ? "read" : ""}
                      key={item.id}
                    >
                      <span />
                      <div>
                        <h3>{item.title}</h3>
                        <p>{item.message}</p>
                        <small>{when(item.created_at)}</small>
                      </div>
                    </article>
                  ))}
                </div>
              ) : (
                <Empty
                  title="You’re all caught up"
                  copy="Booking updates and reminders will appear here."
                />
              )}
            </>
          )}
        </section>
      </div>
    </main>
  );
}

function ReservationDetail({
  reservationId,
  onBack,
}: {
  reservationId: number;
  onBack: () => void;
}) {
  const [workspace, setWorkspace] = useState<ReservationWorkspace | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [confirmingCancel, setConfirmingCancel] = useState(false);
  const [rescheduling, setRescheduling] = useState(false);

  function load() {
    setError("");
    api.reservationWorkspace(reservationId).then(setWorkspace).catch((reason) =>
      setError(reason instanceof Error ? reason.message : "Unable to load reservation"),
    );
  }

  useEffect(() => {
    api.reservationWorkspace(reservationId).then(setWorkspace).catch((reason) =>
      setError(reason instanceof Error ? reason.message : "Unable to load reservation"),
    );
  }, [reservationId]);

  async function cancel() {
    setBusy(true);
    try {
      await api.cancelReservation(reservationId);
      setConfirmingCancel(false);
      load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to cancel reservation");
    } finally {
      setBusy(false);
    }
  }

  async function pay() {
    setBusy(true);
    try {
      const checkout = await api.createCheckout(reservationId);
      window.location.assign(checkout.checkout_url);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to start checkout");
      setBusy(false);
    }
  }

  async function reschedule(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const start = new Date(String(form.get("start")));
    const duration = Number(form.get("duration"));
    setBusy(true);
    try {
      await api.rescheduleReservation(
        reservationId,
        start.toISOString(),
        new Date(start.getTime() + duration * 60_000).toISOString(),
      );
      setRescheduling(false);
      load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to reschedule reservation");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="dashboard-page reservation-detail-page">
      <section className="dashboard-hero reservation-detail-hero">
        <div>
          <button className="back-link" onClick={onBack}>← My reservations</button>
          <p className="eyebrow">Reservation #{reservationId}</p>
          <h1>{workspace?.resource.name ?? "Reservation details"}</h1>
          {workspace && <p>{workspace.venue.name} · {workspace.venue.address}</p>}
        </div>
        {workspace && <Status value={workspace.reservation.status} />}
      </section>
      <section className="reservation-workspace" aria-live="polite">
        {error && <p className="dashboard-message error-message">{error}</p>}
        {!workspace ? (
          !error && <div className="dashboard-loading standalone">Loading reservation…</div>
        ) : (
          <>
            <div className="reservation-overview">
              <article>
                <small>When</small>
                <strong>{when(workspace.reservation.start_time)}</strong>
                <span>Until {when(workspace.reservation.end_time)}</span>
              </article>
              <article>
                <small>Guests</small>
                <strong>{workspace.reservation.party_size}</strong>
                <span>Capacity {workspace.resource.capacity}</span>
              </article>
              <article>
                <small>Total</small>
                <strong>{money(workspace.reservation.quoted_amount_cents, workspace.reservation.quoted_currency)}</strong>
                <span>{workspace.payment ? `Payment ${workspace.payment.status}` : "Not paid"}</span>
              </article>
            </div>
            <div className="reservation-detail-grid">
              <section className="owner-panel">
                <div className="dashboard-title"><div><p className="eyebrow">Progress</p><h2>Reservation history</h2></div></div>
                <div className="timeline-list">
                  {workspace.timeline.map((event) => (
                    <article key={event.id}>
                      <span />
                      <div><strong>{event.event_type.replaceAll("_", " ")}</strong><small>{when(event.occurred_at)} · {event.actor_role}</small></div>
                    </article>
                  ))}
                </div>
              </section>
              <aside className="owner-panel action-panel">
                <div className="dashboard-title"><div><p className="eyebrow">Manage</p><h2>Available actions</h2></div></div>
                {workspace.allowed_actions.includes("pay") && <button className="button primary" disabled={busy} onClick={pay}>Pay reservation</button>}
                {workspace.allowed_actions.includes("reschedule") && <button className="button secondary" disabled={busy} onClick={() => setRescheduling(true)}>Reschedule</button>}
                {workspace.allowed_actions.includes("cancel") && <button className="danger-button" disabled={busy} onClick={() => setConfirmingCancel(true)}>Cancel reservation</button>}
                {!workspace.allowed_actions.some((action) => ["pay", "reschedule", "cancel"].includes(action)) && <p className="muted-copy">This reservation has no pending actions.</p>}
              </aside>
            </div>
          </>
        )}
      </section>
      {confirmingCancel && workspace?.cancellation_preview && (
        <div className="modal-backdrop">
          <div className="management-modal" role="dialog" aria-modal="true" aria-labelledby="cancel-title">
            <h2 id="cancel-title">Cancel reservation?</h2>
            <p className="modal-copy">This applies the policy saved when you booked.</p>
            <div className="cancellation-preview">
              <span>Refund <strong>{money(workspace.cancellation_preview.refund_amount_cents, workspace.reservation.quoted_currency)}</strong></span>
              <span>Cancellation fee <strong>{money(workspace.cancellation_preview.cancellation_fee_cents, workspace.reservation.quoted_currency)}</strong></span>
            </div>
            <div className="modal-actions"><button className="button secondary" onClick={() => setConfirmingCancel(false)}>Keep reservation</button><button className="danger-button" disabled={busy} onClick={cancel}>Confirm cancellation</button></div>
          </div>
        </div>
      )}
      {rescheduling && workspace && (
        <FormModal title="Reschedule reservation" onClose={() => setRescheduling(false)} onSubmit={reschedule}>
          <label>New date and time<input name="start" type="datetime-local" required /></label>
          <label>Duration<select name="duration" defaultValue={(new Date(workspace.reservation.end_time).getTime() - new Date(workspace.reservation.start_time).getTime()) / 60_000}><option value="60">1 hour</option><option value="90">1.5 hours</option><option value="120">2 hours</option><option value="180">3 hours</option></select></label>
        </FormModal>
      )}
    </main>
  );
}

function Empty({
  title,
  copy,
  action,
}: {
  title: string;
  copy: string;
  action?: () => void;
}) {
  return (
    <div className="dashboard-empty">
      <span>✦</span>
      <h3>{title}</h3>
      <p>{copy}</p>
      {action && (
        <button className="button primary" onClick={action}>
          Explore spaces
        </button>
      )}
    </div>
  );
}

export function OwnerDashboard({
  onExplore,
  venueId,
  onOpenVenue,
  onCloseVenue,
}: {
  onExplore: () => void;
  venueId?: number;
  onOpenVenue: (id: number) => void;
  onCloseVenue: () => void;
}) {
  const [stats, setStats] = useState<OwnerStats | null>(null);
  const [venues, setVenues] = useState<OwnerVenue[]>([]);
  const [resources, setResources] = useState<OwnerResource[]>([]);
  const [reservations, setReservations] = useState<OwnerReservation[]>([]);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("");
  const [showVenueForm, setShowVenueForm] = useState(false);
  const [showResourceForm, setShowResourceForm] = useState(false);

  function fetchOwnerData() {
    return Promise.all([
      api.ownerStats(),
      api.ownerVenues(),
      api.ownerResources(),
      api.ownerReservations(),
    ]);
  }
  function applyOwnerData([
    nextStats,
    nextVenues,
    nextResources,
    nextReservations,
  ]: Awaited<ReturnType<typeof fetchOwnerData>>) {
    setStats(nextStats);
    setVenues(nextVenues);
    setResources(nextResources);
    setReservations(nextReservations);
  }
  function load() {
    setLoading(true);
    fetchOwnerData()
      .then(applyOwnerData)
      .catch((error) =>
        setMessage(
          error instanceof Error
            ? error.message
            : "Unable to load owner workspace",
        ),
      )
      .finally(() => setLoading(false));
  }
  useEffect(() => {
    Promise.all([
      api.ownerStats(),
      api.ownerVenues(),
      api.ownerResources(),
      api.ownerReservations(),
    ])
      .then(([nextStats, nextVenues, nextResources, nextReservations]) => {
        setStats(nextStats);
        setVenues(nextVenues);
        setResources(nextResources);
        setReservations(nextReservations);
      })
      .catch((error) =>
        setMessage(
          error instanceof Error
            ? error.message
            : "Unable to load owner workspace",
        ),
      )
      .finally(() => setLoading(false));
  }, []);

  if (venueId)
    return <OwnerVenueManager venueId={venueId} onBack={onCloseVenue} />;

  async function createVenue(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    try {
      const latitude = String(form.get("latitude") ?? "").trim();
      const longitude = String(form.get("longitude") ?? "").trim();
      const venue = await api.createVenue({
        name: String(form.get("name")),
        address: String(form.get("address")),
        description: String(form.get("description")),
        ...(latitude && longitude
          ? { latitude: Number(latitude), longitude: Number(longitude) }
          : {}),
      });
      const image = form.get("image");
      if (image instanceof File && image.size)
        await api.uploadVenueMedia(venue.id, image);
      setShowVenueForm(false);
      setMessage("Venue created.");
      load();
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : "Unable to create venue",
      );
    }
  }
  async function createResource(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    try {
      const resource = await api.createResource(Number(form.get("venue_id")), {
        name: String(form.get("name")),
        resource_type: String(form.get("resource_type")),
        capacity: Number(form.get("capacity")),
        hourly_rate_cents: Math.round(Number(form.get("hourly_rate")) * 100),
        currency: String(form.get("currency")),
      });
      const image = form.get("image");
      if (image instanceof File && image.size)
        await api.uploadResourceMedia(resource.id, image);
      setShowResourceForm(false);
      setMessage("Resource created.");
      load();
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : "Unable to create resource",
      );
    }
  }

  return (
    <main className="dashboard-page owner-page">
      <section className="dashboard-hero">
        <div>
          <p className="eyebrow">Owner workspace</p>
          <h1>Run every space from one place.</h1>
          <p>Catalog, bookings, and performance at a glance.</p>
        </div>
        <div className="owner-actions">
          <button
            className="button cream"
            onClick={() => setShowVenueForm(true)}
          >
            Add venue
          </button>
          <button
            className="button outline-light"
            onClick={() => setShowResourceForm(true)}
            disabled={!venues.length}
          >
            Add resource
          </button>
        </div>
      </section>
      {message && <p className="dashboard-message owner-message">{message}</p>}
      {loading ? (
        <div className="dashboard-loading standalone">
          Loading owner workspace…
        </div>
      ) : (
        <>
          <section className="stat-grid">
            <article>
              <small>Venues</small>
              <strong>{stats?.total_venues ?? 0}</strong>
            </article>
            <article>
              <small>Resources</small>
              <strong>{stats?.total_resources ?? 0}</strong>
            </article>
            <article>
              <small>Reservations</small>
              <strong>{stats?.total_reservations ?? 0}</strong>
            </article>
            <article>
              <small>Revenue</small>
              <strong>{money(stats?.total_revenue_cents ?? 0)}</strong>
            </article>
          </section>
          <section className="owner-columns">
            <div className="owner-panel">
              <div className="dashboard-title">
                <div>
                  <p className="eyebrow">Catalog</p>
                  <h2>Your venues</h2>
                </div>
              </div>
              {venues.length ? (
                venues.map((venue) => (
                  <button
                    className="compact-row compact-row-button"
                    key={venue.id}
                    onClick={() => onOpenVenue(venue.id)}
                  >
                    <span>{venue.name.slice(0, 2).toUpperCase()}</span>
                    <div>
                      <strong>{venue.name}</strong>
                      <small>{venue.address}</small>
                    </div>
                    <em>
                      {
                        resources.filter((item) => item.venue_id === venue.id)
                          .length
                      }{" "}
                      resources
                    </em>
                  </button>
                ))
              ) : (
                <Empty
                  title="Add your first venue"
                  copy="Create a venue, then add its bookable resources."
                />
              )}
            </div>
            <div className="owner-panel">
              <div className="dashboard-title">
                <div>
                  <p className="eyebrow">Activity</p>
                  <h2>Recent reservations</h2>
                </div>
              </div>
              {reservations.slice(0, 6).map((item) => (
                <article className="compact-row" key={item.id}>
                  <span>{item.venue_name.slice(0, 2).toUpperCase()}</span>
                  <div>
                    <strong>{item.resource_name}</strong>
                    <small>{when(item.start_time)}</small>
                  </div>
                  <Status value={item.status} />
                </article>
              ))}
              {!reservations.length && (
                <Empty
                  title="No reservations yet"
                  copy="New bookings will show up here."
                  action={onExplore}
                />
              )}
            </div>
          </section>
        </>
      )}
      {showVenueForm && (
        <FormModal
          title="Add a venue"
          onClose={() => setShowVenueForm(false)}
          onSubmit={createVenue}
        >
          <label>
            Name
            <input name="name" minLength={2} required />
          </label>
          <label>
            Address
            <input name="address" minLength={2} required />
          </label>
          <label>
            Description
            <textarea name="description" rows={3} />
          </label>
          <div className="form-pair">
            <label>Latitude<input name="latitude" type="number" min="-90" max="90" step="any" placeholder="44.8125" /></label>
            <label>Longitude<input name="longitude" type="number" min="-180" max="180" step="any" placeholder="20.4612" /></label>
          </div>
          <p className="upload-note">Optional: add both coordinates to place this venue on the map.</p>
          <label>
            Cover image
            <input
              name="image"
              type="file"
              accept="image/jpeg,image/png,image/webp,image/avif"
            />
          </label>
        </FormModal>
      )}
      {showResourceForm && (
        <FormModal
          title="Add a resource"
          onClose={() => setShowResourceForm(false)}
          onSubmit={createResource}
        >
          <label>
            Venue
            <select name="venue_id" required>
              {venues.map((venue) => (
                <option value={venue.id} key={venue.id}>
                  {venue.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Name
            <input name="name" minLength={2} required />
          </label>
          <label>
            Type
            <input
              name="resource_type"
              placeholder="Meeting room, court…"
              required
            />
          </label>
          <div className="form-pair">
            <label>
              Capacity
              <input
                name="capacity"
                type="number"
                min={1}
                defaultValue={1}
                required
              />
            </label>
            <label>
              Hourly price
              <input
                name="hourly_rate"
                type="number"
                min="0.01"
                step="0.01"
                required
              />
            </label>
          </div>
          <label>
            Currency
            <select name="currency">
              <option>EUR</option>
              <option>USD</option>
              <option>GBP</option>
            </select>
          </label>
          <label>
            Cover image
            <input
              name="image"
              type="file"
              accept="image/jpeg,image/png,image/webp,image/avif"
            />
          </label>
        </FormModal>
      )}
    </main>
  );
}

const weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

function OwnerVenueManager({ venueId, onBack }: { venueId: number; onBack: () => void }) {
  const [venue, setVenue] = useState<Venue | null>(null);
  const [resources, setResources] = useState<OwnerResource[]>([]);
  const [selectedResource, setSelectedResource] = useState<number | null>(null);
  const [rules, setRules] = useState<AvailabilityRule[]>([]);
  const [exceptions, setExceptions] = useState<AvailabilityException[]>([]);
  const [promotions, setPromotions] = useState<import("./types").Promotion[]>([]);
  const [addOns, setAddOns] = useState<AddOn[]>([]);
  const [tab, setTab] = useState<"details" | "availability" | "offers">("details");
  const [message, setMessage] = useState("");

  function loadVenue() {
    Promise.all([api.venue(venueId), api.ownerResources(), api.venuePromotions(venueId), api.managedAddOns(venueId)])
      .then(([nextVenue, allResources, nextPromotions, nextAddOns]) => {
        const ownResources = allResources.filter((item) => item.venue_id === venueId);
        setVenue(nextVenue);
        setResources(ownResources);
        setPromotions(nextPromotions);
        setAddOns(nextAddOns);
        setSelectedResource((current) => current ?? ownResources[0]?.id ?? null);
      })
      .catch((error) => setMessage(error instanceof Error ? error.message : "Unable to load venue"));
  }

  useEffect(loadVenue, [venueId]);
  useEffect(() => {
    if (!selectedResource) return;
    Promise.all([api.availabilityRules(selectedResource), api.availabilityExceptions(selectedResource)])
      .then(([nextRules, nextExceptions]) => { setRules(nextRules); setExceptions(nextExceptions); })
      .catch((error) => setMessage(error instanceof Error ? error.message : "Unable to load availability"));
  }, [selectedResource]);

  async function saveDetails(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    try {
      const coordinates = [String(form.get("latitude") ?? "").trim(), String(form.get("longitude") ?? "").trim()];
      await api.updateVenue(venueId, {
        name: String(form.get("name")), address: String(form.get("address")), description: String(form.get("description")),
        latitude: coordinates[0] ? Number(coordinates[0]) : null,
        longitude: coordinates[1] ? Number(coordinates[1]) : null,
      });
      await api.updateBookingRules(venueId, {
        minimum_booking_notice_minutes: Number(form.get("minimum_notice")), maximum_advance_booking_days: Number(form.get("maximum_advance")),
        minimum_booking_duration_minutes: Number(form.get("minimum_duration")), maximum_booking_duration_minutes: Number(form.get("maximum_duration")),
        max_active_reservations_per_customer: Number(form.get("maximum_active")),
      });
      await api.updateCancellationPolicy(venueId, { free_cancellation_hours: Number(form.get("free_cancellation")), late_cancellation_refund_percent: Number(form.get("late_refund")) });
      setMessage("Venue settings saved."); loadVenue();
    } catch (error) { setMessage(error instanceof Error ? error.message : "Unable to save venue"); }
  }

  async function addRule(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!selectedResource) return;
    const form = new FormData(event.currentTarget);
    try { const rule = await api.createAvailabilityRule(selectedResource, { weekday: Number(form.get("weekday")), start_time: String(form.get("start")), end_time: String(form.get("end")) }); setRules((items) => [...items, rule]); event.currentTarget.reset(); }
    catch (error) { setMessage(error instanceof Error ? error.message : "Unable to add hours"); }
  }
  async function removeRule(rule: AvailabilityRule) { await api.deleteAvailabilityRule(rule.resource_id, rule.id); setRules((items) => items.filter((item) => item.id !== rule.id)); }
  async function addException(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!selectedResource) return; const form = new FormData(event.currentTarget);
    try { const exception = await api.createAvailabilityException(selectedResource, { start_time: new Date(String(form.get("start"))).toISOString(), end_time: new Date(String(form.get("end"))).toISOString(), reason: String(form.get("reason")) }); setExceptions((items) => [...items, exception]); event.currentTarget.reset(); }
    catch (error) { setMessage(error instanceof Error ? error.message : "Unable to add closure"); }
  }
  async function removeException(item: AvailabilityException) { await api.deleteAvailabilityException(item.resource_id, item.id); setExceptions((items) => items.filter((value) => value.id !== item.id)); }
  async function addPromotion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = new FormData(event.currentTarget);
    try { const promotion = await api.createPromotion(venueId, { code: String(form.get("code")), discount_percent: Number(form.get("discount")), valid_from: new Date(String(form.get("from"))).toISOString(), valid_until: new Date(String(form.get("until"))).toISOString(), max_redemptions: form.get("maximum") ? Number(form.get("maximum")) : null }); setPromotions((items) => [...items, promotion]); event.currentTarget.reset(); }
    catch (error) { setMessage(error instanceof Error ? error.message : "Unable to add promotion"); }
  }
  async function addAddOn(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = new FormData(event.currentTarget);
    try { const item = await api.createAddOn(venueId, { name: String(form.get("name")), description: String(form.get("description")), price_cents: Math.round(Number(form.get("price")) * 100), stock: Number(form.get("stock")) }); setAddOns((items) => [...items, item]); event.currentTarget.reset(); }
    catch (error) { setMessage(error instanceof Error ? error.message : "Unable to add extra"); }
  }

  return <main className="dashboard-page owner-page">
    <section className="dashboard-hero"><div><button className="back-link" onClick={onBack}>← Owner dashboard</button><p className="eyebrow">Venue management</p><h1>{venue?.name ?? "Loading venue…"}</h1><p>{venue?.address}</p></div></section>
    <div className="owner-manager">
      {message && <p className="dashboard-message">{message}</p>}
      <nav className="owner-manager-tabs"><button className={tab === "details" ? "active" : ""} onClick={() => setTab("details")}>Details & policies</button><button className={tab === "availability" ? "active" : ""} onClick={() => setTab("availability")}>Availability</button><button className={tab === "offers" ? "active" : ""} onClick={() => setTab("offers")}>Offers & extras</button></nav>
      {venue && tab === "details" && <form className="owner-panel settings-form" onSubmit={saveDetails}>
        <div className="dashboard-title"><div><p className="eyebrow">Settings</p><h2>Venue details and policies</h2></div></div>
        <div className="settings-grid"><label>Name<input name="name" defaultValue={venue.name} required /></label><label>Address<input name="address" defaultValue={venue.address} required /></label><label className="wide">Description<textarea name="description" defaultValue={venue.description ?? ""} rows={3} /></label><label>Latitude<input name="latitude" type="number" step="any" defaultValue={venue.latitude ?? ""} /></label><label>Longitude<input name="longitude" type="number" step="any" defaultValue={venue.longitude ?? ""} /></label><label>Minimum notice (minutes)<input name="minimum_notice" type="number" defaultValue={venue.minimum_booking_notice_minutes} /></label><label>Advance window (days)<input name="maximum_advance" type="number" defaultValue={venue.maximum_advance_booking_days} /></label><label>Minimum duration (minutes)<input name="minimum_duration" type="number" defaultValue={venue.minimum_booking_duration_minutes} /></label><label>Maximum duration (minutes)<input name="maximum_duration" type="number" defaultValue={venue.maximum_booking_duration_minutes} /></label><label>Active bookings per customer<input name="maximum_active" type="number" defaultValue={venue.max_active_reservations_per_customer} /></label><label>Free cancellation (hours)<input name="free_cancellation" type="number" defaultValue={venue.free_cancellation_hours} /></label><label>Late refund (%)<input name="late_refund" type="number" defaultValue={venue.late_cancellation_refund_percent} /></label></div><button className="button primary">Save settings</button>
      </form>}
      {tab === "availability" && <div className="management-columns"><section className="owner-panel"><div className="dashboard-title"><div><p className="eyebrow">Weekly schedule</p><h2>Opening hours</h2></div></div><label className="resource-picker">Resource<select value={selectedResource ?? ""} onChange={(event) => setSelectedResource(Number(event.target.value))}>{resources.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><form className="inline-management-form" onSubmit={addRule}><select name="weekday">{weekdays.map((day, index) => <option value={index} key={day}>{day}</option>)}</select><input name="start" type="time" required /><input name="end" type="time" required /><button className="button primary">Add hours</button></form><div className="management-list">{rules.sort((a,b) => a.weekday-b.weekday).map((rule) => <article key={rule.id}><div><strong>{weekdays[rule.weekday]}</strong><small>{rule.start_time.slice(0,5)}–{rule.end_time.slice(0,5)}</small></div><button onClick={() => removeRule(rule)}>Remove</button></article>)}</div></section><section className="owner-panel"><div className="dashboard-title"><div><p className="eyebrow">Closures</p><h2>Exceptions</h2></div></div><form className="stacked-management-form" onSubmit={addException}><label>From<input name="start" type="datetime-local" required /></label><label>Until<input name="end" type="datetime-local" required /></label><label>Reason<input name="reason" placeholder="Maintenance, holiday…" /></label><button className="button primary">Add closure</button></form><div className="management-list">{exceptions.map((item) => <article key={item.id}><div><strong>{item.reason || "Unavailable"}</strong><small>{when(item.start_time)} – {when(item.end_time)}</small></div><button onClick={() => removeException(item)}>Remove</button></article>)}</div></section></div>}
      {tab === "offers" && <div className="management-columns"><section className="owner-panel"><div className="dashboard-title"><div><p className="eyebrow">Marketing</p><h2>Promotions</h2></div></div><form className="stacked-management-form" onSubmit={addPromotion}><label>Code<input name="code" minLength={3} required /></label><label>Discount %<input name="discount" type="number" min="1" max="100" required /></label><label>Starts<input name="from" type="datetime-local" required /></label><label>Ends<input name="until" type="datetime-local" required /></label><label>Maximum uses<input name="maximum" type="number" min="1" /></label><button className="button primary">Create promotion</button></form><div className="management-list">{promotions.map((item) => <article key={item.id}><div><strong>{item.code} · {item.discount_percent}% off</strong><small>{item.redemption_count}{item.max_redemptions ? ` / ${item.max_redemptions}` : ""} uses</small></div>{item.is_active && <button onClick={async () => { await api.deactivatePromotion(item.id); loadVenue(); }}>Deactivate</button>}</article>)}</div></section><section className="owner-panel"><div className="dashboard-title"><div><p className="eyebrow">Upsell</p><h2>Add-ons</h2></div></div><form className="stacked-management-form" onSubmit={addAddOn}><label>Name<input name="name" required /></label><label>Description<input name="description" /></label><label>Price<input name="price" type="number" min="0" step="0.01" required /></label><label>Stock<input name="stock" type="number" min="1" required /></label><button className="button primary">Create add-on</button></form><div className="management-list">{addOns.map((item) => <article key={item.id}><div><strong>{item.name} · {money(item.price_cents)}</strong><small>{item.stock} available · {item.is_active ? "Active" : "Inactive"}</small></div><button onClick={async () => { await api.updateAddOn(item.id, { is_active: !item.is_active }); loadVenue(); }}>{item.is_active ? "Disable" : "Enable"}</button></article>)}</div></section></div>}
    </div>
  </main>;
}

function FormModal({
  title,
  onClose,
  onSubmit,
  children,
}: {
  title: string;
  onClose: () => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  children: React.ReactNode;
}) {
  return (
    <div
      className="modal-backdrop"
      onMouseDown={(event) => event.target === event.currentTarget && onClose()}
    >
      <form className="management-modal" onSubmit={onSubmit}>
        <button
          type="button"
          className="management-close"
          onClick={onClose}
          aria-label="Close"
        >
          ×
        </button>
        <p className="eyebrow">Owner tools</p>
        <h2>{title}</h2>
        <div className="management-fields">{children}</div>
        <button className="button primary full">Save</button>
      </form>
    </div>
  );
}
