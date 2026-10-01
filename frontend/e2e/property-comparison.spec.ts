import { expect, test } from "@playwright/test";

test("compares across result pages and filters on mobile", async ({ page }, testInfo) => {
  const base = { venue_id: 1, city: "Beograd", description: "Stan u centru grada sa terasom.", offer_type: "sale", area_sqm: 50, rooms: 2, currency: "EUR", price_cents: 10000000, contact_email: "owner@example.com", is_published: true };
  await page.route("**/api/properties?*", route => {
    const url = new URL(route.request().url());
    const later = Number(url.searchParams.get("offset")) > 0;
    return route.fulfill({ json: { items: [{ ...base, id: later ? 2 : 1, title: later ? "Stan B" : "Stan A", offer_type: url.searchParams.get("offer_type") || "sale" }], total: 13, offset: later ? 12 : 0, limit: 12, has_next: !later } });
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await page.getByRole("button", { name: "Poredi: Stan A" }).click();
  await expect(page.getByRole("button", { name: "Prikaži poređenje" })).toBeDisabled();
  await page.getByRole("button", { name: "Sledeća", exact: true }).click();
  await page.getByRole("button", { name: "Poredi: Stan B" }).click();
  await page.getByRole("button", { name: "Prikaži poređenje" }).click();
  const comparison = page.getByRole("region", { name: "Poređenje oglasa", exact: true });
  await expect(comparison.getByRole("link", { name: "Stan A" })).toBeVisible();
  await expect(comparison.getByRole("link", { name: "Stan B" })).toHaveAttribute("href", "/properties/2");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await comparison.screenshot({ path: testInfo.outputPath("comparison-mobile.png") });
  await page.getByRole("button", { name: "Ukloni iz poređenja: Stan A" }).click();
  await page.getByRole("button", { name: "Stan na dan", exact: true }).click();
  await page.getByRole("button", { name: "Poredi: Stan A" }).click();
  await expect(page.getByRole("alert")).toContainText("iste vrste ponude i valute");
  await page.getByRole("button", { name: "Očisti poređenje" }).click();
  await page.getByRole("button", { name: "Poredi: Stan A" }).click();
  await expect(page.getByRole("heading", { name: "Poređenje oglasa (1/3)" })).toBeVisible();
});
