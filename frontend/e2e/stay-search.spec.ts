import { expect, test } from "@playwright/test";
import { propertyToday, shiftDate } from "../src/stay-types";

test("availability search carries dates into inline and direct booking forms", async ({ page }, testInfo) => {
  const arrival = shiftDate(propertyToday(), 10);
  const departure = shiftDate(arrival, 3);
  const listing = { id: 7, venue_id: 1, title: "Slobodan apartman", city: "Novi Sad", description: "Ceo apartman za odmor sa porodicom.", offer_type: "short_stay", area_sqm: 60, rooms: 2, price_cents: 6500, currency: "EUR", contact_email: "owner@example.com", is_published: true, booking_enabled: true, max_guests: 4, minimum_nights: 2, timezone: "Europe/Belgrade" };
  const searches: URLSearchParams[] = [];
  await page.route("**/api/properties?*", route => {
    searches.push(new URL(route.request().url()).searchParams);
    return route.fulfill({ json: { items: [listing], total: 1, limit: 12, offset: 0, has_next: false } });
  });
  await page.route("**/api/properties/7", route => route.fulfill({ json: listing }));
  await page.route("**/api/properties/7/calendar?*", route => route.fulfill({ json: { occupied: [] } }));
  await page.route("**/api/properties/7/stay-quote", route => {
    expect(route.request().postDataJSON()).toEqual({ check_in: arrival, check_out: departure, guests: 3 });
    return route.fulfill({ json: { nights: 3, nightly_rate_cents: 6500, total_cents: 19500, currency: "EUR", timezone: "Europe/Belgrade", payment_method: "pay_on_arrival" } });
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Stan na dan", exact: true }).click();
  await page.getByText("Napredni filteri i sortiranje").click();
  await page.getByLabel("Dolazak u pretrazi").fill(arrival);
  await page.getByLabel("Odlazak u pretrazi").fill(departure);
  await page.getByLabel("Broj gostiju u pretrazi").fill("3");
  await page.getByRole("button", { name: "Primeni filtere" }).click();
  await expect.poll(() => searches.at(-1)?.get("check_in")).toBe(arrival);
  expect(searches.at(-1)?.get("guests")).toBe("3");
  await page.getByRole("button", { name: `Detalji: ${listing.title}` }).click();
  await expect(page.getByLabel("Dolazak", { exact: true })).toHaveValue(arrival);
  await expect(page.getByLabel("Broj gostiju", { exact: true })).toHaveValue("3");
  await page.getByRole("link", { name: listing.title, exact: true }).click();
  await page.reload();
  await expect(page.getByLabel("Dolazak", { exact: true })).toHaveValue(arrival);
  await expect(page.getByLabel("Odlazak", { exact: true })).toHaveValue(departure);
  await expect(page.getByLabel("Broj gostiju", { exact: true })).toHaveValue("3");
  await page.getByRole("button", { name: "Proveri dostupnost i cenu" }).click();
  await expect(page.getByRole("button", { name: "Potvrdi rezervaciju" })).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("stay-search-booking.png"), fullPage: true });
});
