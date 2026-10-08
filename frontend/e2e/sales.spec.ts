import { expect, test } from "./fixtures";
import { propertyToday, shiftDate } from "../src/stay-types";

for (const mobile of [false, true]) {
  test(`purchase inquiry, seller viewing and private conversation on ${mobile ? "mobile" : "desktop"}`, async ({ page }, testInfo) => {
    if (mobile) await page.setViewportSize({ width: 390, height: 844 });
    const property = { id: 1, venue_id: 1, title: "Stan za prodaju", description: "Svetao stan sa terasom u centru grada.", city: "Beograd", offer_type: "sale", area_sqm: 50, rooms: 2, price_cents: 15000000, currency: "EUR", contact_email: "owner@example.com", is_published: true };
    let created = false;
    const inquiry = { id: 1, property_id: 1, title: property.title, asking_price_cents: property.price_cents, currency: "EUR", message: "Zainteresovan sam za razgledanje stana.", owner_reply: "", viewing_at: null as string | null, status: "open", version: 1, created_at: new Date().toISOString() };
    await page.route("**/api/properties?*", route => route.fulfill({ json: { items: [property], total: 1, limit: 12, offset: 0, has_next: false } }));
    await page.route("**/api/properties/1/sale-inquiries", route => {
      expect(route.request().postDataJSON()).toEqual({ message: inquiry.message, request_id: expect.any(String) });
      created = true;
      return route.fulfill({ status: 201, json: inquiry });
    });
    await page.route(/\/api\/(owner\/sale-inquiries|sale-inquiries\/mine)\?/, route => route.fulfill({ json: { items: created ? [inquiry] : [], total: created ? 1 : 0, has_next: false } }));
    await page.route("**/api/sale-inquiries/1", route => {
      const data = route.request().postDataJSON();
      expect(data.version).toBe(inquiry.version);
      if (data.action === "propose") { inquiry.status = "viewing_proposed"; inquiry.owner_reply = data.owner_reply; inquiry.viewing_at = data.viewing_at; }
      if (data.action === "confirm") inquiry.status = "viewing_confirmed";
      if (data.action === "withdraw") inquiry.status = "withdrawn";
      inquiry.version += 1;
      return route.fulfill({ json: inquiry });
    });
    await page.route("**/api/sale-inquiries/1/messages", route => route.fulfill({ json: { items: [
      { id: 1, sender: "buyer", kind: "message", body: inquiry.message, created_at: inquiry.created_at, read_at: null },
      { id: 2, sender: "owner", kind: "message", body: "Dokumentaciju donosim na razgledanje.", created_at: inquiry.created_at, read_at: null },
    ], has_more: false, next_before_id: null, unread_count: 1 } }));
    await page.route("**/api/sale-inquiries/1/messages/read", route => {
      expect(route.request().postDataJSON()).toEqual({ message_ids: [2] });
      return route.fulfill({ json: { unread_count: 0 } });
    });
    await page.goto("/");
    await page.getByRole("button", { name: `Detalji: ${property.title}` }).click();
    await expect(page.getByLabel("Željeno useljenje")).toHaveCount(0);
    await page.getByLabel("Poruka prodavcu").fill(inquiry.message);
    await page.getByRole("button", { name: "Pošalji upit za kupovinu" }).click();
    await expect(page.getByText("Upit za kupovinu je poslat")).toBeVisible();
    await page.getByRole("link", { name: "Moji upiti za kupovinu", exact: true }).click();
    await expect(page.getByText("Otvoren upit", { exact: true })).toBeVisible();
    await expect(page.getByText(/mesec|Željeno useljenje/)).toHaveCount(0);
    await page.goto("/owner/sales");
    await page.getByLabel("Odgovor kupcu").fill("Razgledanje ispred glavnog ulaza.");
    await page.getByLabel("Predloži termin razgledanja (opciono)").fill(`${shiftDate(propertyToday(), 5)}T14:00`);
    await page.getByRole("button", { name: "Pošalji predlog termina" }).click();
    await expect(page.getByText("Predložen termin", { exact: true })).toBeVisible();
    await page.goto("/sales");
    await page.getByRole("button", { name: "Prihvati termin" }).click();
    await expect(page.getByText("Razgledanje potvrđeno", { exact: true })).toBeVisible();
    const download = page.waitForEvent("download");
    await page.getByRole("button", { name: /Dodaj u kalendar/ }).click();
    expect((await download).suggestedFilename()).toBe("bookica-prodaja-razgledanje-1.ics");
    await page.getByRole("button", { name: /Otvori razgovor/ }).click();
    await expect(page.getByRole("list", { name: "Istorija razgovora" }).getByText("Ti", { exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Označi prikazane poruke kao pročitane" }).click();
    await expect(page.getByText("1 nepročitanih")).toHaveCount(0);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.screenshot({ path: testInfo.outputPath("sales-viewing.png"), fullPage: true });
    await page.getByRole("button", { name: "Povuci upit" }).click();
    await page.getByRole("button", { name: "Potvrdi", exact: true }).click();
    await expect(page.getByText("Povučen upit", { exact: true })).toBeVisible();
  });
}
