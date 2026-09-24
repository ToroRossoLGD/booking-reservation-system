import { expect, test } from "@playwright/test";
import { propertyToday, shiftDate } from "../src/stay-types";

for (const detailPage of [false, true]) {
test(`guest quotes, reserves, views and cancels from ${detailPage ? "listing page" : "catalog"}`, async ({ page }, testInfo) => {
  const today = propertyToday();
  const arrival = shiftDate(today, 3);
  const departure = shiftDate(today, 6);
  const property = { id: 4, venue_id: 1, title: "Apartman na planini", city: "Zlatibor", description: "Ceo apartman za odmor sa porodicom.", offer_type: "short_stay", area_sqm: 50, rooms: 2, price_cents: 6500, currency: "EUR", contact_email: "host@example.com", is_published: true, booking_enabled: true, max_guests: 4, minimum_nights: 2, timezone: "Europe/Belgrade" };
  let confirmed = false;
  let cancelled = false;
  const reservation = () => ({ id: 9, property_id: 4, title: property.title, city: property.city, contact_email: property.contact_email, timezone: property.timezone, check_in: arrival, check_out: departure, guests: 2, status: cancelled ? "cancelled" : "confirmed", nightly_rate_cents: 6500, total_cents: 19500, currency: "EUR", payment_method: "pay_on_arrival", created_at: new Date().toISOString() });
  await page.route("**/api/properties?*", route => route.fulfill({ json: { items: [property], total: 1, limit: 12, offset: 0, has_next: false } }));
  await page.route("**/api/properties/4/calendar?*", route => {
    const params = new URL(route.request().url()).searchParams;
    return route.fulfill({ json: { start: params.get("start"), end: params.get("end"), occupied: confirmed && !cancelled ? [{ check_in: arrival, check_out: departure }] : [] } });
  });
  await page.route("**/api/properties/4/stay-quote", route => {
    expect(route.request().postDataJSON()).toEqual({ check_in: arrival, check_out: departure, guests: 2 });
    return route.fulfill({ json: { nights: 3, nightly_rate_cents: 6500, total_cents: 19500, currency: "EUR", timezone: "Europe/Belgrade", payment_method: "pay_on_arrival" } });
  });
  await page.route("**/api/properties/4/stays", route => {
    expect(route.request().postDataJSON()).toMatchObject({ expected_total_cents: 19500, expected_currency: "EUR", check_in: arrival, check_out: departure, guests: 2 });
    confirmed = true;
    return route.fulfill({ status: 201, json: reservation() });
  });
  await page.route("**/api/stays/mine?*", route => route.fulfill({ json: { items: confirmed ? [reservation()] : [], total: confirmed ? 1 : 0, has_next: false } }));
  await page.route("**/api/stays/9/cancel", route => { cancelled = true; return route.fulfill({ json: reservation() }); });
  await page.route("**/api/properties/4", route => route.fulfill({ json: property }));
  await page.goto(detailPage ? "/properties/4" : "/");
  if (!detailPage) await page.getByRole("button", { name: "Detalji: Apartman na planini" }).click();
  await page.getByLabel("Dolazak", { exact: true }).fill(arrival);
  await page.getByLabel("Odlazak", { exact: true }).fill(departure);
  await page.getByLabel("Broj gostiju", { exact: true }).fill("2");
  await page.getByRole("button", { name: "Proveri dostupnost i cenu" }).click();
  await expect(page.getByText(/Ukupno/).last()).toContainText("195");
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("nightly-booking-mobile.png"), fullPage: true });
  await page.getByRole("button", { name: "Potvrdi rezervaciju" }).click();
  await expect(page.getByText(/Rezervacija je potvrđena/)).toBeVisible();
  await page.getByRole("link", { name: /Pregledaj svoje boravke/ }).click();
  await expect(page.getByRole("heading", { name: property.title })).toBeVisible();
  await page.getByRole("button", { name: "Otkaži rezervaciju" }).click();
  await page.getByRole("button", { name: "Potvrdi otkazivanje" }).click();
  await expect(page.getByText("#9 · Otkazano")).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("nightly-stay-cancelled.png"), fullPage: true });
});

}
