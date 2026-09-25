import { expect, test } from "@playwright/test";

test("guests and owners download confirmed stays and viewings, never cancelled or unconfirmed events", async ({ page }) => {
  const stay = { id: 7, property_id: 3, status: "confirmed", title: "Stan pored reke", city: "Novi Sad", contact_email: "owner@example.com", guest_email: "guest@example.com", timezone: "Europe/Belgrade", check_in: "2030-10-04", check_out: "2030-10-07", guests: 2, nightly_rate_cents: 6500, total_cents: 19500, currency: "EUR", payment_method: "pay_on_arrival", created_at: "2030-09-01T00:00:00Z" };
  const inquiry = { id: 9, property_id: 3, title: "Stan za najam", monthly_price_cents: 60000, currency: "EUR", move_in: "2030-10-01", duration_months: 12, message: "Zelim da pogledam stan.", owner_reply: "Vidimo se ispred ulaza.", viewing_at: "2030-09-25T14:00:00+02:00", status: "viewing_confirmed", version: 3, created_at: "2030-09-01T00:00:00Z" };
  await page.route(/\/api\/(stays\/mine|owner\/stays)\?/, route => route.fulfill({ json: { items: [stay, { ...stay, id: 8, status: "cancelled" }], total: 2, has_next: false } }));
  await page.route(/\/api\/(rental-inquiries\/mine|owner\/rental-inquiries)\?/, route => route.fulfill({ json: { items: [inquiry, ...["open", "viewing_proposed", "closed", "withdrawn"].map((status, index) => ({ ...inquiry, id: 10 + index, status }))], total: 5, has_next: false } }));
  for (const [path, filename, expectedStart] of [
    ["/stays", "bookica-boravak-7.ics", "DTSTART;VALUE=DATE:20301004"],
    ["/owner/stays", "bookica-boravak-7.ics", "DTSTART;VALUE=DATE:20301004"],
    ["/rentals", "bookica-razgledanje-9.ics", "DTSTART:20300925T120000Z"],
    ["/owner/rentals", "bookica-razgledanje-9.ics", "DTSTART:20300925T120000Z"],
  ]) {
    await page.goto(path);
    const button = page.getByRole("button", { name: "Dodaj u kalendar (.ics)", exact: true });
    await expect(button).toHaveCount(1);
    const pending = page.waitForEvent("download");
    await button.click();
    const download = await pending;
    expect(download.suggestedFilename()).toBe(filename);
    const stream = await download.createReadStream();
    const chunks = [];
    for await (const chunk of stream) chunks.push(chunk);
    const contents = Buffer.concat(chunks).toString("utf8").replace(/\r\n /g, "");
    expect(contents).toContain(expectedStart);
    expect(contents).toContain(`URL:${new URL(path, page.url()).href}`);
    expect(contents).not.toContain("owner@example.com");
    expect(contents).not.toContain("Vidimo se ispred ulaza.");
  }
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
