import { expect, test } from "@playwright/test";
import { propertyToday, shiftDate } from "../src/stay-types";

for (const mobile of [false, true]) {
  test(`rental inquiry and agreed viewing on ${mobile ? "mobile" : "desktop"}`, async ({ page }, testInfo) => {
    if (mobile) await page.setViewportSize({ width: 390, height: 844 });
    const property = { id: 1, venue_id: 1, title: "Stan za dugoročni najam", description: "Svetao stan sa terasom u centru grada.", city: "Beograd", offer_type: "long_term", area_sqm: 50, rooms: 2, price_cents: 60000, currency: "EUR", contact_email: "owner@example.com", is_published: true };
    let created = false;
    const inquiry = { id: 1, property_id: 1, title: property.title, monthly_price_cents: 60000, currency: "EUR", move_in: shiftDate(propertyToday(), 30), duration_months: 12, message: "Zainteresovan sam za razgledanje stana.", owner_reply: "", viewing_at: null as string | null, status: "open", version: 1, created_at: new Date().toISOString() };
    await page.route("**/api/properties?*", route => route.fulfill({ json: { items: [property], total: 1, limit: 12, offset: 0, has_next: false } }));
    await page.route("**/api/properties/1/rental-inquiries", route => {
      expect(route.request().postDataJSON()).toMatchObject({ move_in: inquiry.move_in, message: inquiry.message, duration_months: 12 });
      created = true;
      return route.fulfill({ status: 201, json: inquiry });
    });
    await page.route(/\/api\/(owner\/rental-inquiries|rental-inquiries\/mine)\?/, route => route.fulfill({ json: { items: created ? [inquiry] : [], total: created ? 1 : 0, has_next: false } }));
    await page.route("**/api/rental-inquiries/1", route => {
      const data = route.request().postDataJSON();
      expect(data.version).toBe(inquiry.version);
      if (data.action === "propose") { inquiry.status = "viewing_proposed"; inquiry.owner_reply = data.owner_reply; inquiry.viewing_at = data.viewing_at; }
      if (data.action === "confirm") inquiry.status = "viewing_confirmed";
      inquiry.version += 1;
      return route.fulfill({ json: inquiry });
    });
    await page.goto("/");
    await page.getByRole("button", { name: `Detalji: ${property.title}` }).click();
    await page.getByLabel("Željeno useljenje").fill(inquiry.move_in);
    await page.getByLabel("Poruka vlasniku").fill(inquiry.message);
    await page.getByRole("button", { name: "Pošalji upit za najam" }).click();
    await expect(page.getByText("Upit je poslat vlasniku")).toBeVisible();
    await page.getByRole("link", { name: "Moji upiti za najam", exact: true }).click();
    await expect(page.getByText("Otvoren upit", { exact: true })).toBeVisible();
    await page.goto("/owner/rentals");
    await page.getByLabel("Odgovor zakupcu").fill("Razgledanje ispred glavnog ulaza.");
    await page.getByLabel("Predloži termin razgledanja (opciono)").fill(`${shiftDate(propertyToday(), 5)}T14:00`);
    await page.getByRole("button", { name: "Pošalji predlog termina" }).click();
    await expect(page.getByText("Predložen termin", { exact: true })).toBeVisible();
    await page.goto("/rentals");
    await page.getByRole("button", { name: "Prihvati termin" }).click();
    await expect(page.getByText("Razgledanje potvrđeno", { exact: true })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.screenshot({ path: testInfo.outputPath("rental-viewing-confirmed.png"), fullPage: true });
  });
}
