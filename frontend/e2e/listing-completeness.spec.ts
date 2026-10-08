import { expect, test } from "./fixtures";

test("owner completeness shortcuts work on mobile without blocking publication", async ({ page }, testInfo) => {
  let listing = { id: 7, venue_id: 1, title: "Stan", description: "Udoban stan u centru grada.", city: "Beograd", offer_type: "long_term", area_sqm: 60, rooms: 2, price_cents: 65000, currency: "EUR", contact_email: "owner@example.com", is_published: true, photos: [] };
  await page.route("**/api/auth/me", route => route.fulfill({ json: { id: 1, email: "owner@example.com", role: "owner" } }));
  await page.route("**/api/venues", route => route.fulfill({ json: [] }));
  await page.route("**/api/promotions/active", route => route.fulfill({ json: [] }));
  await page.route("**/api/owner/stats", route => route.fulfill({ json: { total_venues: 1, total_resources: 0, total_reservations: 0, total_revenue_cents: 0, reservations_by_status: {}, top_resources: [] } }));
  await page.route("**/api/owner/venues", route => route.fulfill({ json: [{ id: 1, name: "Moj stan", address: "Centar", description: null, owner_id: 1 }] }));
  await page.route("**/api/owner/resources", route => route.fulfill({ json: [] }));
  await page.route("**/api/owner/reservations", route => route.fulfill({ json: [] }));
  await page.route("**/api/owner/properties?*", route => route.fulfill({ json: { items: [listing], total: 1, limit: 20, offset: 0, has_next: false } }));
  await page.route("**/api/properties/7", route => {
    listing = { ...listing, ...route.request().postDataJSON() };
    return route.fulfill({ json: listing });
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/owner");
  await page.getByRole("button", { name: "Izmeni: Stan", exact: true }).click();
  const hints = page.getByRole("complementary", { name: "Preporuke za oglas" });
  await expect(hints.getByRole("button", { name: "Navedi pravilo za ljubimce" })).toBeVisible();
  await hints.getByRole("button", { name: "Navedi grejanje" }).click();
  await expect(page.getByRole("combobox", { name: /^Grejanje/ })).toBeFocused();
  await page.getByRole("combobox", { name: /^Grejanje/ }).selectOption("gas");
  await expect(hints.getByText("Navedi grejanje")).toHaveCount(0);
  await page.getByLabel("Vrsta ponude").selectOption("sale");
  await expect(hints.getByText("Navedi pravilo za ljubimce")).toHaveCount(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await hints.screenshot({ path: testInfo.outputPath("listing-hints-mobile.png") });
  await page.getByRole("button", { name: "Sačuvaj oglas" }).click();
  await expect(page.getByText("Oglas je objavljen na naslovnoj strani.")).toBeVisible();
  expect(listing.offer_type).toBe("sale");
});
