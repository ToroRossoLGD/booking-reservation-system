import { expect, test } from "./fixtures";
import { displayDate, propertyToday, shiftDate } from "../src/stay-types";
import type { Stay, StayChange, StayQuote } from "../src/stay-types";

test("guest requests new dates on mobile and owner approves before the booking changes", async ({ browser, baseURL }, testInfo) => {
  const today = propertyToday();
  const original: Stay = { id: 42, property_id: 7, check_in: shiftDate(today, 7), check_out: shiftDate(today, 10), guests: 2, status: "confirmed", title: "Stan pored reke", city: "Novi Sad", timezone: "Europe/Belgrade", contact_email: "owner@example.com", guest_email: "guest@example.com", nightly_rate_cents: 6500, total_cents: 19500, currency: "EUR", created_at: "2026-10-01T10:00:00Z", payment_method: "pay_on_arrival" };
  const current = { ...original };
  const quote: StayQuote = { nights: 3, nightly_rate_cents: 7000, total_cents: 21000, currency: "EUR", timezone: current.timezone, check_in_time: "15:00", check_out_time: "10:00", payment_method: "pay_on_arrival" };
  const arrival = shiftDate(today, 9), departure = shiftDate(today, 12);
  let change: StayChange | null = null;
  const guest = await browser.newContext({ baseURL, viewport: { width: 390, height: 844 } });
  const owner = await browser.newContext({ baseURL });
  try {
    for (const [context, isOwner] of [[guest, false], [owner, true]] as const) {
      await context.addInitScript(() => localStorage.setItem("bookica_token", "test-member"));
      await context.route("**/api/auth/me", route => route.fulfill({ json: { id: isOwner ? 1 : 2, email: isOwner ? current.contact_email : current.guest_email, role: isOwner ? "owner" : "customer" } }));
      await context.route(/\/api\/(stays\/mine|owner\/stays)\?/, route => route.fulfill({ json: { items: [current], total: 1, has_next: false, arrivals_today: 0, departures_today: 0, properties: [{ id: 7, title: current.title }] } }));
      await context.route("**/api/stays/42/date-changes?*", route => route.fulfill({ json: { items: change ? [change] : [], total: change ? 1 : 0, has_next: false } }));
      await context.route("**/api/stays/42/date-change-quote", route => {
        expect(route.request().postDataJSON()).toEqual({ check_in: arrival, check_out: departure, guests: 2 });
        return route.fulfill({ json: quote });
      });
      await context.route("**/api/stays/42/date-changes", route => {
        const body = route.request().postDataJSON();
        expect(body.quote).toEqual(quote);
        expect(body.request_id).toBeTruthy();
        change = { id: 5, stay_id: 42, check_in: body.check_in, check_out: body.check_out, original: { ...original }, quote, status: "pending", created_at: original.created_at, resolved_at: null };
        return route.fulfill({ status: 201, json: change });
      });
      await context.route("**/api/stays/42/date-changes/5/decision", route => {
        expect(isOwner).toBe(true);
        expect(route.request().postDataJSON()).toEqual({ action: "accept" });
        change!.status = "accepted";
        Object.assign(current, quote, { check_in: arrival, check_out: departure });
        return route.fulfill({ json: change });
      });
    }
    const guestPage = await guest.newPage();
    await guestPage.goto("/stays");
    await guestPage.getByRole("button", { name: "Promene termina" }).click();
    await guestPage.getByLabel("Novi dolazak").fill(arrival);
    await guestPage.getByLabel("Novi odlazak").fill(departure);
    await guestPage.getByRole("button", { name: "Proveri novi termin i cenu" }).click();
    const send = guestPage.getByRole("button", { name: "Pošalji zahtev za promenu" });
    await expect(send).toBeDisabled();
    await guestPage.getByRole("checkbox").check();
    await send.click();
    await expect(guestPage.getByRole("heading", { name: "Zahtev #5 · Čeka vlasnika" })).toBeVisible();
    await expect(guestPage.locator(".stay-dates")).toContainText(displayDate(original.check_in));
    expect(await guestPage.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await guestPage.screenshot({ path: testInfo.outputPath("guest-date-change-mobile.png"), fullPage: true });
    const ownerPage = await owner.newPage();
    await ownerPage.goto("/owner/stays");
    await ownerPage.getByRole("button", { name: "Promene termina" }).click();
    await ownerPage.getByRole("button", { name: "Odobri termin i cenu" }).click();
    await expect(ownerPage.locator(".stay-dates")).toContainText(displayDate(arrival));
    await guestPage.reload();
    await expect(guestPage.locator(".stay-dates")).toContainText(displayDate(arrival));
    await guestPage.getByRole("button", { name: "Promene termina" }).click();
    await expect(guestPage.getByRole("heading", { name: "Zahtev #5 · Odobreno" })).toBeVisible();
    await expect(guestPage.getByRole("button", { name: "Povuci zahtev" })).toHaveCount(0);
  } finally { await guest.close(); await owner.close(); }
});
