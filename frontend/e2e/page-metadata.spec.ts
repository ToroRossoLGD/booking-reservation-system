import { expect, test } from "./fixtures";

test("direct links have route-specific titles without copying recovery tokens", async ({ page }) => {
  await page.route("**/api/auth/me", route => route.fulfill({ status: 401, json: { detail: "Sign in" } }));
  await page.goto("/forgot-password");
  await expect(page).toHaveTitle("Zaboravljena lozinka | Bookica");
  await expect(page.locator('meta[property="og:title"]')).toHaveAttribute("content", "Zaboravljena lozinka | Bookica");
  await page.goto("/reset-password#token=private-test-token");
  await expect(page).toHaveTitle("Nova lozinka | Bookica");
  expect(await page.locator("head").innerHTML()).not.toContain("private-test-token");
});

test("public listing metadata follows loading and missing states", async ({ page }) => {
  await page.route("**/api/properties/7", route => route.fulfill({ json: {
    id: 7, venue_id: 1, title: "Stan pored reke", city: "Novi Sad", description: "Svetao stan.",
    offer_type: "sale", area_sqm: 60, rooms: 2, price_cents: 14000000, currency: "EUR",
    contact_email: "owner@example.com", is_published: true,
  } }));
  await page.goto("/properties/7?check_in=2030-01-01");
  await expect(page).toHaveTitle("Stan pored reke | Bookica");
  await expect(page.locator('meta[name="description"]')).toHaveAttribute("content", /Prodaja · Novi Sad · 60 m²/);
  await expect(page.locator('meta[property="og:title"]')).toHaveCount(1);
  expect(await page.locator("head").innerHTML()).not.toContain("owner@example.com");
  await page.route("**/api/properties/8", route => route.fulfill({ status: 404, json: { detail: "Missing" } }));
  await page.goto("/properties/8");
  await expect(page).toHaveTitle("Oglas nije dostupan | Bookica");
  await expect(page.locator('meta[property="og:description"]')).not.toHaveAttribute("content", /Novi Sad/);
});
