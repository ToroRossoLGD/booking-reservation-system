import { expect, test } from "./fixtures";

test("detail views share a session and owners inspect monthly analytics on mobile", async ({ page }, testInfo) => {
  const listing = { id: 7, venue_id: 1, title: "Stan pored reke", description: "Udoban stan uz reku i centar grada.", city: "Novi Sad", offer_type: "sale", price_cents: 15000000, currency: "EUR", area_sqm: 60, rooms: 2, contact_email: "host@example.com", is_published: true };
  const visitorIds: string[] = [];
  await page.route("**/api/properties?*", route => route.fulfill({ json: { items: [listing], total: 1, limit: 12, offset: 0, has_next: false } }));
  await page.route("**/api/properties/7", route => route.fulfill({ json: listing }));
  await page.route("**/api/properties/7/views", route => { visitorIds.push(route.request().postDataJSON().visitor_id); return route.fulfill({ status: 204 }); });
  await page.goto("/");
  await expect(page.getByRole("link", { name: listing.title, exact: true })).toBeVisible();
  expect(visitorIds).toHaveLength(0);
  await page.getByRole("button", { name: `Detalji: ${listing.title}` }).click();
  await expect.poll(() => visitorIds.length).toBeGreaterThan(0);
  await page.getByRole("link", { name: listing.title, exact: true }).click();
  await expect.poll(() => visitorIds.length).toBeGreaterThan(1);
  expect(new Set(visitorIds).size).toBe(1);
  const requests: URLSearchParams[] = [];
  await page.route("**/api/owner/property-analytics?*", route => {
    const params = new URL(route.request().url()).searchParams; requests.push(params);
    return route.fulfill({ json: { year: Number(params.get("year")), properties: [{ id: 7, title: listing.title, offer_type: "short_stay" }], months: Array.from({ length: 12 }, (_, index) => ({ month: index + 1, views: (index + 1) * 10, reservations: index % 4 + 1, cancelled: index % 2, nights: index * 3 + 2, booked_value_cents: { EUR: 12000 * (index + 1) } })) } });
  });
  await page.goto("/owner/analytics");
  await expect(page.getByRole("table")).toBeVisible();
  await page.getByLabel("Godina", { exact: true }).fill("2025");
  await page.getByRole("button", { name: "Prikaži / osveži" }).click();
  await expect.poll(() => requests.at(-1)?.get("year")).toBe("2025");
  await page.getByRole("combobox", { name: "Oglas", exact: true }).selectOption("7");
  await expect.poll(() => requests.at(-1)?.get("property_id")).toBe("7");
  await page.getByRole("combobox", { name: "Prikaži grafikon", exact: true }).selectOption("views");
  await expect(page.getByText("Pregledi detalja po mesecima")).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("owner-analytics-mobile.png"), fullPage: true });
});
