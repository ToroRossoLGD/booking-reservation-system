import { expect, test } from "@playwright/test";
import type { PropertyListing } from "../src/property-types";

const listing: PropertyListing = { id: 1, venue_id: 1, title: "Stan na mapi", city: "Beograd", description: "Svetao stan sa terasom i pogledom na park.", offer_type: "sale", area_sqm: 60, rooms: 2, price_cents: 15000000, currency: "EUR", contact_email: "owner@example.com", is_published: true, map_latitude: 44.81, map_longitude: 20.46 };
const tile = '<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256"><rect width="256" height="256" fill="#e9eee4"/><path d="M0 128h256M128 0v256" stroke="#bacbbc" stroke-width="12"/></svg>';

for (const mobile of [false, true]) {
  test(`map filters, page markers, history and tile errors on ${mobile ? "mobile" : "desktop"}`, async ({ page }, testInfo) => {
    if (mobile) await page.setViewportSize({ width: 390, height: 844 });
    let tileRequests = 0;
    let tilesAvailable = false;
    await page.route("https://tile.openstreetmap.org/**", route => { tileRequests++; return tilesAvailable ? route.fulfill({ contentType: "image/svg+xml", body: tile }) : route.abort(); });
    const rows = Array.from({ length: 13 }, (_, index) => ({ ...listing, id: index + 1, title: index === 0 ? '<img src=x onerror="alert(1)">' : `Stan ${index + 1}` }));
    const hidden = { ...listing, id: 14, title: "Bez lokacije", map_latitude: null, map_longitude: null };
    await page.route("**/api/properties?*", route => {
      const params = new URL(route.request().url()).searchParams;
      let items = params.get("map_only") === "true" ? rows : [...rows, hidden];
      if (params.has("map_south")) items = items.filter(item => item.map_latitude != null && item.map_longitude != null && item.map_latitude >= Number(params.get("map_south")) && item.map_latitude <= Number(params.get("map_north")) && item.map_longitude >= Number(params.get("map_west")) && item.map_longitude <= Number(params.get("map_east")));
      const offset = Number(params.get("offset") ?? 0);
      return route.fulfill({ json: { items: items.slice(offset, offset + 12), total: items.length, offset, limit: 12, has_next: offset + 12 < items.length } });
    });
    await page.goto("/?offer_type=sale&rooms=2");
    await expect(page.getByText("Pronađeno oglasa: 14", { exact: true })).toBeVisible();
    expect(tileRequests).toBe(0);
    await page.getByRole("button", { name: "Prikaži mapu", exact: true }).click();
    await expect(page.getByText("Pronađeno oglasa: 13", { exact: true })).toBeVisible();
    const map = page.getByRole("region", { name: "Mapa nekretnina", exact: true });
    await expect(map.locator(".leaflet-marker-icon")).toHaveCount(1);
    await map.locator(".leaflet-marker-icon").click();
    await expect(map.getByRole("link", { name: rows[0].title, exact: true })).toHaveAttribute("href", "/properties/1");
    await expect(map.locator(".leaflet-popup img")).toHaveCount(0);
    await expect(map.getByRole("alert")).toContainText("Podloga mape nije dostupna");
    await page.getByRole("button", { name: "Sledeća", exact: true }).click();
    await expect(page.getByText("Stranica 2", { exact: true })).toBeVisible();
    await map.locator(".leaflet-marker-icon").click();
    await expect(map.getByRole("link", { name: "Stan 13", exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Pretraži ovaj deo mape" }).click();
    await expect(page).toHaveURL(/map_south=/);
    expect(new URL(page.url()).searchParams.get("offset")).toBeNull();
    expect(new URL(page.url()).searchParams.get("rooms")).toBe("2");
    await expect(page.getByText("Stranica 1", { exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Ukloni ograničenje mape" }).click();
    await expect(page.getByText("Pronađeno oglasa: 14", { exact: true })).toBeVisible();
    await page.goBack();
    await expect(page).toHaveURL(/map_south=/);
    await expect(page.getByText("Pronađeno oglasa: 13", { exact: true })).toBeVisible();
    await page.reload();
    await expect(page.getByText("Pronađeno oglasa: 13", { exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Prikaži mapu", exact: true }).click();
    await expect(map.locator(".leaflet-marker-icon")).toHaveCount(1);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    tilesAvailable = true;
    await expect(map.getByRole("alert")).toBeVisible();
    await map.getByRole("button", { name: /Ponovo/ }).click();
    await expect(map.getByRole("alert")).toHaveCount(0);
    await map.screenshot({ path: testInfo.outputPath("property-map.png") });
  });

  test(`owner opts into approximate map location and removes it on ${mobile ? "mobile" : "desktop"}`, async ({ page }) => {
    if (mobile) await page.setViewportSize({ width: 390, height: 844 });
    let current = { ...listing, map_latitude: null, map_longitude: null } as PropertyListing;
    let writes = 0;
    await page.route("https://tile.openstreetmap.org/**", route => route.fulfill({ contentType: "image/svg+xml", body: tile }));
    await page.route("**/api/auth/me", route => route.fulfill({ json: { id: 1, email: "owner@example.com", role: "owner" } }));
    await page.route("**/api/owner/stats", route => route.fulfill({ json: { total_venues: 1, total_resources: 0, total_reservations: 0, total_revenue_cents: 0, reservations_by_status: {}, top_resources: [] } }));
    await page.route("**/api/owner/venues", route => route.fulfill({ json: [{ id: 1, name: "Objekat", address: "Centar", owner_id: 1 }] }));
    await page.route("**/api/owner/resources", route => route.fulfill({ json: [] }));
    await page.route("**/api/owner/reservations", route => route.fulfill({ json: [] }));
    await page.route("**/api/owner/properties?*", route => route.fulfill({ json: { items: [current], total: 1, offset: 0, limit: 20, has_next: false } }));
    await page.route("**/api/properties/1", route => {
      const body = route.request().postDataJSON(); writes++;
      if (writes === 1) { expect(typeof body.map_latitude).toBe("number"); expect(typeof body.map_longitude).toBe("number"); }
      else { expect(body.map_latitude).toBeNull(); expect(body.map_longitude).toBeNull(); }
      current = { ...current, ...body };
      return route.fulfill({ json: current });
    });
    await page.goto("/owner");
    await page.getByRole("button", { name: "Izmeni: Stan na mapi" }).click();
    const toggle = page.getByRole("checkbox", { name: "Prikaži približnu lokaciju na javnoj mapi" });
    await expect(toggle).not.toBeChecked();
    await toggle.check();
    await page.getByRole("button", { name: "Izaberi lokaciju na mapi" }).click();
    const canvas = page.getByLabel("Interaktivna mapa", { exact: true });
    await canvas.click({ position: { x: 150, y: 150 } });
    await expect(page.getByLabel("Geografska širina", { exact: true })).not.toHaveValue("");
    expect(Number(await page.getByLabel("Geografska širina", { exact: true }).inputValue()) * 100).toBeCloseTo(Math.round(Number(await page.getByLabel("Geografska širina", { exact: true }).inputValue()) * 100), 5);
    await page.getByRole("button", { name: "Sačuvaj oglas", exact: true }).click();
    await expect(page.getByText("Oglas je objavljen na naslovnoj strani.")).toBeVisible();
    await page.getByRole("button", { name: "Izmeni: Stan na mapi" }).click();
    await expect(toggle).toBeChecked();
    await toggle.uncheck();
    await page.getByRole("button", { name: "Sačuvaj oglas", exact: true }).click();
    await expect(page.getByText("Oglas je objavljen na naslovnoj strani.")).toBeVisible();
    expect(writes).toBe(2);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  });
}
