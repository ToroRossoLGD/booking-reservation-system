import { expect, test } from "@playwright/test";
import { propertyToday, shiftDate } from "../src/stay-types";
import type { PropertyListing } from "../src/property-types";

test("owner window controls guest arrival and departure dates", async ({ page }) => {
  let listing: PropertyListing = { id: 7, venue_id: 1, title: "Stan", description: "Udoban stan u centru grada.", city: "Beograd", offer_type: "short_stay", area_sqm: 50, rooms: 2, price_cents: 6500, currency: "EUR", contact_email: "owner@example.com", is_published: true, booking_enabled: true, minimum_nights: 2 };
  await page.route("**/api/auth/me", route => route.fulfill({ json: { id: 1, email: "owner@example.com", role: "owner" } }));
  await page.route("**/api/venues", route => route.fulfill({ json: [] }));
  await page.route("**/api/promotions/active", route => route.fulfill({ json: [] }));
  await page.route("**/api/owner/stats", route => route.fulfill({ json: { total_venues: 1, total_resources: 0, total_reservations: 0, total_revenue_cents: 0, reservations_by_status: {}, top_resources: [] } }));
  await page.route("**/api/owner/venues", route => route.fulfill({ json: [{ id: 1, name: "Moj stan", address: "Centar", description: null, owner_id: 1 }] }));
  await page.route("**/api/owner/resources", route => route.fulfill({ json: [] }));
  await page.route("**/api/owner/reservations", route => route.fulfill({ json: [] }));
  await page.route("**/api/owner/properties?*", route => route.fulfill({ json: { items: [listing], total: 1, limit: 20, offset: 0, has_next: false } }));
  await page.route("**/api/properties/7", route => {
    if (route.request().method() === "PUT") listing = { ...route.request().postDataJSON(), id: 7 };
    return route.fulfill({ json: listing });
  });
  await page.route("**/api/properties/7/calendar?*", route => route.fulfill({ json: { occupied: [] } }));
  await page.route("**/api/properties/7/views", route => route.fulfill({ status: 204 }));
  await page.route("**/api/properties/7/reviews?*", route => route.fulfill({ json: { items: [], total: 0, average_rating: null, has_next: false } }));
  await page.goto("/owner");
  await page.getByRole("button", { name: "Izmeni: Stan", exact: true }).click();
  await page.getByLabel("Najava dolaska (dana unapred)").fill("7");
  await page.getByLabel("Rok odlaska (dana unapred)").fill("30");
  await page.getByRole("button", { name: "Sačuvaj oglas" }).click();
  await expect(page.getByText("Oglas je objavljen na naslovnoj strani.")).toBeVisible();
  expect(listing.advance_notice_days).toBe(7);
  expect(listing.booking_window_days).toBe(30);
  await page.goto("/properties/7");
  const today = propertyToday();
  await expect(page.getByLabel("Dolazak", { exact: true })).toHaveValue(shiftDate(today, 7));
  await expect(page.getByLabel("Dolazak", { exact: true })).toHaveAttribute("min", shiftDate(today, 7));
  await expect(page.getByLabel("Odlazak", { exact: true })).toHaveAttribute("max", shiftDate(today, 30));
});
