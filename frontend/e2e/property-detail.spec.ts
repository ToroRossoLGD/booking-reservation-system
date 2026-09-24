import { expect, test } from "@playwright/test";
import { propertyToday, shiftDate } from "../src/stay-types";

for (const mobile of [false, true]) {
  test(`listing links open a shareable page with rental inquiry on ${mobile ? "mobile" : "desktop"}`, async ({ page }, testInfo) => {
    if (mobile) await page.setViewportSize({ width: 390, height: 844 });
    const listing = { id: 7, venue_id: 1, title: "Stan pored reke", city: "Novi Sad", description: "Svetao stan sa terasom i pogledom na reku.", offer_type: "long_term", area_sqm: 60, rooms: 2, price_cents: 65000, currency: "EUR", contact_email: "owner@example.com", is_published: true };
    await page.route("**/api/properties?*", route => route.fulfill({ json: { items: [listing], total: 1, limit: 12, offset: 0, has_next: false } }));
    await page.route("**/api/properties/7", route => route.fulfill({ json: listing }));
    await page.route("**/api/properties/7/rental-inquiries", route => {
      expect(route.request().postDataJSON()).toMatchObject({ message: "Zanima me razgledanje ovog stana.", duration_months: 12 });
      return route.fulfill({ status: 201, json: { id: 1 } });
    });
    await page.goto("/");
    await page.getByRole("link", { name: listing.title, exact: true }).click();
    await expect(page).toHaveURL(/\/properties\/7$/);
    await page.reload();
    await expect(page.getByRole("heading", { name: listing.title, exact: true })).toBeVisible();
    await expect(page).toHaveTitle(`${listing.title} | Bookica`);
    await page.getByLabel("Željeno useljenje").fill(shiftDate(propertyToday(), 30));
    await page.getByLabel("Poruka vlasniku").fill("Zanima me razgledanje ovog stana.");
    await page.getByRole("button", { name: "Pošalji upit za najam" }).click();
    await expect(page.getByText("Upit je poslat vlasniku")).toBeVisible();
    await page.getByRole("button", { name: "Kopiraj link oglasa" }).click();
    await expect(page.getByText("Link je kopiran.").or(page.getByLabel("Kopiraj adresu ručno"))).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: testInfo.outputPath("property-detail.png"), fullPage: true });
    await page.route("**/api/properties/7", route => route.fulfill({ status: 404, json: { detail: "Listing not found" } }));
    await page.reload();
    await expect(page.getByRole("heading", { name: "Oglas nije dostupan." })).toBeVisible();
    await expect(page.getByRole("heading", { name: listing.title })).toHaveCount(0);
    await page.goto("/properties/not-a-number");
    await expect(page.getByRole("heading", { name: "Oglas nije dostupan." })).toBeVisible();
  });
}
