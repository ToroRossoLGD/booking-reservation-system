import { expect, test } from "./fixtures";

test("property details are searchable, shareable and visible on mobile listings", async ({ page }, testInfo) => {
  const listing = { id: 7, venue_id: 1, title: "Kuća uz park", description: "Porodična kuća sa terasom i parkingom.", city: "Novi Sad", offer_type: "sale", area_sqm: 100, rooms: 4, price_cents: 18000000, currency: "EUR", contact_email: "owner@example.com", is_published: true, property_type: "house", neighborhood: "Liman", floor: 0, heating: "gas", furnishing: "partial", has_elevator: false, has_parking: true, has_terrace: true };
  const requests: URLSearchParams[] = [];
  await page.route("**/api/properties?*", route => {
    const params = new URL(route.request().url()).searchParams; requests.push(params);
    return route.fulfill({ json: { items: [listing], total: 13, limit: 12, offset: Number(params.get("offset")), has_next: params.get("offset") === "0" } });
  });
  await page.route("**/api/properties/7", route => route.fulfill({ json: listing }));
  await page.goto("/?offer_type=sale");
  await page.getByText("Napredni filteri i sortiranje").click();
  await page.getByRole("combobox", { name: "Tip nekretnine", exact: true }).selectOption("house");
  await page.getByLabel("Naselje", { exact: true }).fill("Liman");
  await page.getByRole("spinbutton", { name: /Sprat/ }).fill("0");
  await page.getByRole("combobox", { name: "Lift", exact: true }).selectOption("false");
  await page.getByRole("button", { name: "Primeni filtere" }).click();
  await expect.poll(() => requests.at(-1)?.get("has_elevator")).toBe("false");
  await expect(page).toHaveURL(/floor=0/);
  await page.getByRole("button", { name: "Sledeća" }).click();
  await expect.poll(() => requests.at(-1)?.get("offset")).toBe("12");
  expect(requests.at(-1)?.get("property_type")).toBe("house");
  await page.reload();
  await page.getByText("Napredni filteri i sortiranje").click();
  await expect(page.getByRole("combobox", { name: "Lift", exact: true })).toHaveValue("false");
  await page.getByRole("button", { name: "Dugoročni najam", exact: true }).click();
  await expect.poll(() => requests.at(-1)?.get("offer_type")).toBe("long_term");
  expect(requests.at(-1)?.get("floor")).toBe("0");
  expect(requests.at(-1)?.get("property_type")).toBe("house");
  await page.getByRole("button", { name: "Obriši filtere" }).click();
  await expect.poll(() => requests.at(-1)?.has("floor")).toBe(false);
  await page.getByRole("link", { name: listing.title, exact: true }).click();
  await expect(page.getByText("Prizemlje", { exact: true })).toBeVisible();
  await expect(page.getByText("Polunamešteno", { exact: true })).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("property-details-mobile.png"), fullPage: true });
});
