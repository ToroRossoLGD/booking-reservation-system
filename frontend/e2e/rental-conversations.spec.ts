import { expect, test } from "@playwright/test";
import type { RentalMessage } from "../src/rental-types";

for (const mobile of [false, true]) {
  test(`rental participants exchange messages on ${mobile ? "mobile" : "desktop"}`, async ({ page }, testInfo) => {
    if (mobile) await page.setViewportSize({ width: 390, height: 844 });
    let role: "owner" | "tenant" = "owner";
    const inquiry = { id: 7, property_id: 1, title: "Stan za dugoročni najam", monthly_price_cents: 60000, currency: "EUR", move_in: "2030-10-01", duration_months: 12, message: "Da li je stan dostupan od oktobra?", owner_reply: "", viewing_at: null, status: "open", version: 1, created_at: new Date().toISOString() };
    const messages: RentalMessage[] = [{ id: 1, sender: "tenant", kind: "message", body: inquiry.message, viewing_at: null, created_at: inquiry.created_at, read_at: null }];
    const unread = () => messages.filter(message => message.sender !== role && !message.read_at).length;
    await page.route(/\/api\/(owner\/rental-inquiries|rental-inquiries\/mine)\?/, route => route.fulfill({ json: { items: [{ ...inquiry, unread_count: unread() }], total: 1, has_next: false } }));
    await page.route("**/api/rental-inquiries/7/messages", route => {
      if (route.request().method() === "POST") {
        const data = route.request().postDataJSON();
        expect(data.request_id).toMatch(/^[0-9a-f-]{36}$/);
        const message: RentalMessage = { id: messages.length + 1, sender: role, kind: "message", body: data.body, viewing_at: null, created_at: new Date().toISOString(), read_at: null };
        messages.push(message);
        return route.fulfill({ status: 201, json: message });
      }
      return route.fulfill({ json: { items: messages, has_more: false, next_before_id: null, unread_count: unread() } });
    });
    await page.route("**/api/rental-inquiries/7/messages/read", route => {
      const ids = route.request().postDataJSON().message_ids;
      messages.forEach(message => { if (ids.includes(message.id) && message.sender !== role) message.read_at = new Date().toISOString(); });
      return route.fulfill({ json: { unread_count: unread() } });
    });
    await page.goto("/owner/rentals");
    await page.getByRole("button", { name: /Otvori razgovor.*1 nepročitanih/ }).click();
    const history = page.getByRole("list", { name: "Istorija razgovora" });
    await expect(history.getByText(inquiry.message)).toBeVisible();
    await page.getByRole("button", { name: "Označi prikazane poruke kao pročitane" }).click();
    await expect(page.getByText("1 nepročitanih")).toHaveCount(0);
    await page.getByLabel("Nova poruka").fill("Stan je dostupan, da li vam odgovara subota?");
    await page.getByRole("button", { name: "Pošalji poruku" }).click();
    await expect(history.getByText("Stan je dostupan, da li vam odgovara subota?")).toBeVisible();
    role = "tenant";
    await page.goto("/rentals");
    await page.getByRole("button", { name: /Otvori razgovor.*1 nepročitanih/ }).click();
    await expect(history.getByText("Stan je dostupan, da li vam odgovara subota?")).toBeVisible();
    await page.getByLabel("Nova poruka").fill("Odgovara mi subota u 14 časova.");
    await page.getByRole("button", { name: "Pošalji poruku" }).click();
    await expect(history.getByText("Odgovara mi subota u 14 časova.")).toBeVisible();
    await expect(history.getByRole("listitem")).toHaveCount(3);
    await page.getByRole("button", { name: "Označi prikazane poruke kao pročitane" }).click();
    await expect(page.getByText("1 nepročitanih")).toHaveCount(0);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.screenshot({ path: testInfo.outputPath("rental-conversation.png"), fullPage: true });
    role = "owner";
    await page.goto("/owner/rentals");
    await page.getByRole("button", { name: /Otvori razgovor.*1 nepročitanih/ }).click();
    await expect(history.getByText("Odgovara mi subota u 14 časova.")).toBeVisible();
  });
}
