import { FormEvent, useEffect, useState } from "react";
import { api } from "./api";
import type {
  Favorite,
  Notification,
  OwnerReservation,
  OwnerResource,
  OwnerStats,
  OwnerVenue,
  Reservation,
  User,
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
}: {
  user: User;
  initialTab?: AccountTab;
  onExplore: () => void;
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
                        <h3>Resource #{item.resource_id}</h3>
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

export function OwnerDashboard({ onExplore }: { onExplore: () => void }) {
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
                  <article className="compact-row" key={venue.id}>
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
                  </article>
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
