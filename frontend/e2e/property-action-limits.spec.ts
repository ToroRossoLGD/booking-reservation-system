import { expect, test } from "./fixtures";

for (const mobile of [false, true]) {
  test(`limited chat preserves draft and retries on ${mobile ? "mobile" : "desktop"}`, async ({ page }) => {
    if (mobile) await page.setViewportSize({ width: 390, height: 844 });
    const inquiry = { id: 7, property_id: 1, title: "Stan za najam", monthly_price_cents: 60000, currency: "EUR", move_in: "2035-10-01", duration_months: 12, message: "Zelim da pogledam stan.", owner_reply: "", viewing_at: null, status: "open", version: 1, created_at: "2030-01-01T12:00:00Z", unread_count: 0 };
    await page.route(/\/api\/rental-inquiries\/mine\?/, route => route.fulfill({ json: { items: [inquiry], total: 1, has_next: false } }));
    const submissions: unknown[] = [];
    const messages: object[] = [];
    await page.route("**/api/rental-inquiries/7/messages", route => {
      if (route.request().method() !== "POST") return route.fulfill({ json: { items: messages, has_more: false, next_before_id: null, unread_count: 0 } });
      const body = route.request().postDataJSON();
      submissions.push(body);
      if (submissions.length === 1) return route.fulfill({ status: 429, headers: { "Retry-After": "45" }, json: { detail: "limited" } });
      const message = { id: 1, sender: "tenant", kind: "message", body: body.body, viewing_at: null, created_at: "2030-01-01T12:00:00Z", read_at: null };
      messages.push(message);
      return route.fulfill({ status: 201, json: message });
    });
    await page.goto("/rentals");
    await page.getByRole("button", { name: /Otvori razgovor/ }).click();
    await page.getByLabel("Nova poruka").fill("Da li odgovara subota?");
    await page.getByRole("button", { name: "Pošalji poruku" }).click();
    await expect(page.getByRole("alert")).toContainText("Sačekajte 45 sekundi");
    await expect(page.getByLabel("Nova poruka")).toHaveValue("Da li odgovara subota?");
    expect(submissions).toHaveLength(1);
    await page.getByRole("button", { name: "Pošalji poruku" }).click();
    await expect(page.getByRole("list", { name: "Istorija razgovora" })).toContainText("Da li odgovara subota?");
    expect(submissions[0]).toEqual(submissions[1]);
    await expect(page.getByLabel("Nova poruka")).toHaveValue("");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  });
}
