import { expect, test } from "@playwright/test";
import { propertyToday, shiftDate } from "../src/stay-types";

test("owner creates and removes a private block from the listing manager", async ({ page }, testInfo) => {
  const today = propertyToday();
  const listing = { id: 7, venue_id: 1, title: "Moj apartman", city: "Beograd", description: "Ceo stan za odmor i posao.", offer_type: "short_stay", area_sqm: 50, rooms: 2, price_cents: 6500, currency: "EUR", contact_email: "owner@example.com", is_published: true, timezone: "Europe/Belgrade" };
  let blocked = false;
  const block = { id: 1, venue_id: 1, check_in: today, check_out: shiftDate(today, 3), reason: "Renoviranje", active: true, created_at: new Date().toISOString() };
  await page.route("**/api/auth/me", route => route.fulfill({ json: { id: 1, email: "owner@example.com", role: "owner" } }));
  await page.route("**/api/venues", route => route.fulfill({ json: [] }));
  await page.route("**/api/promotions/active", route => route.fulfill({ json: [] }));
  await page.route("**/api/owner/stats", route => route.fulfill({ json: { total_venues: 1, total_resources: 0, total_reservations: 0, total_revenue_cents: 0, reservations_by_status: {}, top_resources: [] } }));
  await page.route("**/api/owner/venues", route => route.fulfill({ json: [{ id: 1, name: "Moj objekat", address: "Centar", owner_id: 1 }] }));
  await page.route("**/api/owner/resources", route => route.fulfill({ json: [] }));
  await page.route("**/api/owner/reservations", route => route.fulfill({ json: [] }));
  await page.route("**/api/owner/properties?*", route => route.fulfill({ json: { items: [listing], total: 1, limit: 20, offset: 0, has_next: false } }));
  await page.route("**/api/owner/properties/7/stay-blocks?*", route => route.fulfill({ json: { items: blocked ? [block] : [], total: blocked ? 1 : 0, has_next: false } }));
  await page.route("**/api/owner/properties/7/stay-blocks", route => {
    expect(route.request().postDataJSON()).toMatchObject({ check_in: today, check_out: block.check_out, reason: block.reason });
    expect(route.request().postDataJSON().request_id).toMatch(/^[0-9a-f-]{36}$/);
    blocked = true; return route.fulfill({ status: 201, json: block });
  });
  await page.route("**/api/owner/properties/7/stay-blocks/1", route => { blocked = false; return route.fulfill({ status: 204 }); });
  await page.goto("/owner");
  await page.getByRole("button", { name: "Blokade: Moj apartman" }).click();
  await page.getByLabel("Kraj blokade").fill(block.check_out);
  await page.getByLabel("Privatni razlog (opciono)").fill(block.reason);
  await page.getByRole("button", { name: "Blokiraj termin" }).click();
  await expect(page.getByText("Aktivnih blokada: 1")).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("owner-stay-blocks.png"), fullPage: true });
  await page.getByRole("button", { name: "Ukloni blokadu" }).click();
  expect(blocked).toBe(true);
  await page.getByRole("button", { name: "Potvrdi uklanjanje" }).click();
  await expect(page.getByText("Aktivnih blokada: 0")).toBeVisible();
});
