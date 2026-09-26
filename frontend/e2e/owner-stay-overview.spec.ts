import { expect, test } from "@playwright/test";

test("owner filters all reservations and opens blocks for an unpublished property on mobile", async ({ page }, testInfo) => {
  const listing = { id: 7, venue_id: 1, title: "Stan pored reke", city: "Novi Sad", description: "Ceo stan blizu centra i reke.", offer_type: "short_stay", area_sqm: 50, rooms: 2, price_cents: 6500, currency: "EUR", contact_email: "host@example.com", is_published: false, timezone: "Europe/Belgrade" };
  const stay = { id: 9, property_id: 7, title: listing.title, city: listing.city, status: "confirmed", check_in: "2030-10-04", check_out: "2030-10-07", check_in_time: "14:00", check_out_time: "11:00", timezone: "Europe/Belgrade", guests: 2, total_cents: 19500, currency: "EUR", contact_email: "host@example.com", guest_email: "guest@example.com" };
  await page.route("**/api/owner/stays?*", route => {
    const params = new URL(route.request().url()).searchParams;
    const filtered = params.get("day") === "arrivals";
    return route.fulfill({ json: { items: [{ ...stay, status: params.get("status") ?? "confirmed" }], total: filtered ? 23 : 30, has_next: params.get("offset") === "0", arrivals_today: 23, departures_today: 4, properties: [{ id: 7, title: listing.title }] } });
  });
  await page.goto("/owner/stays");
  await expect(page.getByRole("button", { name: "Danas dolaze 23" })).toBeVisible();
  await page.getByRole("button", { name: "Sledeća" }).click();
  await expect(page.getByRole("button", { name: "Prethodna" })).toBeEnabled();
  await page.getByRole("combobox", { name: "Stan", exact: true }).selectOption("7");
  await expect(page.getByRole("button", { name: "Prethodna" })).toBeDisabled();
  await page.getByRole("button", { name: "Danas dolaze 23" }).click();
  await expect(page.getByText("Ukupno: 23")).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("owner-overview-mobile.png"), fullPage: true });
  await page.route("**/api/auth/me", route => route.fulfill({ json: { id: 1, email: "owner@example.com", role: "owner" } }));
  for (const path of ["venues", "promotions/active", "owner/resources", "owner/reservations"]) await page.route(`**/api/${path}`, route => route.fulfill({ json: [] }));
  await page.route("**/api/owner/venues", route => route.fulfill({ json: [{ id: 1, name: "Stan", address: "Centar", owner_id: 1 }] }));
  await page.route("**/api/owner/stats", route => route.fulfill({ json: { total_venues: 1, total_resources: 0, total_reservations: 0, total_revenue_cents: 0, reservations_by_status: {}, top_resources: [] } }));
  await page.route("**/api/owner/properties?*", route => route.fulfill({ json: { items: [], total: 0, limit: 20, offset: 0, has_next: false } }));
  await page.route("**/api/owner/properties/7", route => route.fulfill({ json: listing }));
  await page.route("**/api/owner/properties/7/stay-blocks?*", route => route.fulfill({ json: { items: [], total: 0, has_next: false } }));
  await page.getByRole("link", { name: "Upravljaj blokadama" }).click();
  await expect(page).toHaveURL(/\/owner\?blocks=7$/);
  await expect(page.getByRole("region", { name: `Blokade: ${listing.title}` })).toBeVisible();
  await expect(page.getByText("Aktivnih blokada: 0")).toBeVisible();
});
