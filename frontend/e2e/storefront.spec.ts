import { expect, test } from "@playwright/test";
import type { PropertyListing } from "../src/property-types";

test.beforeEach(async ({ page }) => {
  await page.route("**/api/properties?*", route => route.fulfill({ json: { items: [], total: 0, limit: 12, offset: 0, has_next: false } }));
  await page.route("**/api/auth/me", route => route.fulfill({ status: 401, json: { detail: "Not signed in" } }));
  await page.route("**/api/venues", route => route.fulfill({ json: [] }));
  await page.route("**/api/promotions/active", route => route.fulfill({ json: [] }));
});

test("property storefront links to the existing booking and authentication flow", async ({ page }) => {
  await page.goto("/");

  await expect(
    page.getByRole("heading", { name: /negde te čeka/i }),
  ).toBeVisible();
  await page.getByRole("link", { name: /postojeći sistem rezervacija/i }).click();
  await expect(page).toHaveURL(/\/booking$/);

  await expect(
    page.getByRole("heading", { name: /the right space/i }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(
    page.getByRole("heading", { name: /good to see you again/i }),
  ).toBeVisible();
  await expect(page.getByLabel("Email address")).toBeVisible();
});

test("property search and contact work on desktop and mobile", async ({ page }, testInfo) => {
  const listing = { id: 42, venue_id: 1, title: "Stan za novi početak", description: "Svetao stan sa terasom i pogledom na park.", city: "Novi Sad", offer_type: "sale", area_sqm: 64, rooms: 3, price_cents: 15600000, currency: "EUR", contact_email: "owner@example.com", is_published: true };
  await page.route("**/api/properties?*", route => {
    const params = new URL(route.request().url()).searchParams;
    const matches = (!params.get("city") || params.get("city") === "Novi Sad") && (!params.get("offer_type") || params.get("offer_type") === "sale");
    return route.fulfill({ json: { items: matches ? [listing] : [], total: matches ? 1 : 0, limit: 12, offset: 0, has_next: false } });
  });
  await page.goto("/");
  await expect(page.getByRole("heading", { name: listing.title })).toBeVisible();
  await page.getByRole("button", { name: "Stan na dan", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Nema oglasa za ovaj izbor." })).toBeVisible();
  await page.getByRole("button", { name: "Prodaja", exact: true }).click();
  await page.getByPlaceholder("Grad ili destinacija").fill("Novi Sad");
  await page.getByRole("button", { name: /Pretraži ponudu/ }).click();
  await page.getByRole("button", { name: `Detalji: ${listing.title}` }).click();
  await expect(page.getByText(listing.description)).toBeVisible();
  await expect(page.getByRole("link", { name: /Kontaktiraj vlasnika/ })).toHaveAttribute("href", /mailto:owner%40example.com/);
  await page.screenshot({ path: testInfo.outputPath("properties-desktop.png"), fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByRole("link", { name: /Kontaktiraj vlasnika/ })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("properties-mobile.png"), fullPage: true });
});

test("owner can publish a property from the existing dashboard", async ({ page }, testInfo) => {
  const listings: PropertyListing[] = [];
  await page.route("**/api/auth/me", route => route.fulfill({ json: { id: 1, email: "owner@example.com", role: "owner" } }));
  await page.route("**/api/owner/stats", route => route.fulfill({ json: { total_venues: 1, total_resources: 0, total_reservations: 0, total_revenue_cents: 0, reservations_by_status: {}, top_resources: [] } }));
  await page.route("**/api/owner/venues", route => route.fulfill({ json: [{ id: 1, name: "Moj objekat", address: "Centar", description: null, owner_id: 1 }] }));
  await page.route("**/api/owner/resources", route => route.fulfill({ json: [] }));
  await page.route("**/api/owner/reservations", route => route.fulfill({ json: [] }));
  await page.route("**/api/owner/properties?*", route => route.fulfill({ json: { items: listings, total: listings.length, limit: 20, offset: 0, has_next: false } }));
  await page.route("**/api/properties", route => {
    const listing = { ...route.request().postDataJSON(), id: 1 };
    listings.push(listing);
    return route.fulfill({ status: 201, json: listing });
  });
  await page.goto("/owner");
  await page.getByRole("button", { name: "Novi oglas" }).click();
  await page.getByLabel("Vrsta ponude").selectOption("long_term");
  await page.getByLabel("Naslov oglasa").fill("Stan za najam");
  await page.getByLabel("Grad ili destinacija").fill("Beograd");
  await page.getByLabel("Površina (m²)").fill("60");
  await page.getByLabel("Broj soba (0 za garsonjeru)").fill("2");
  await page.getByLabel("Cena / mesec").fill("850");
  await page.getByLabel("Opis", { exact: true }).fill("Udoban stan u centru grada sa terasom.");
  await page.getByLabel(/Javna kontakt email adresa/).fill("owner@example.com");
  await page.getByRole("checkbox").check();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("property-owner-mobile.png"), fullPage: true });
  await page.getByRole("button", { name: "Sačuvaj oglas" }).click();
  await expect(page.getByText("Oglas je objavljen na naslovnoj strani.")).toBeVisible();
  expect(listings[0]).toMatchObject({ price_cents: 85000, offer_type: "long_term", is_published: true });
  await expect(page.getByRole("button", { name: "Izmeni: Stan za najam" })).toBeVisible();
});
