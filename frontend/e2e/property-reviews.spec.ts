import { expect, test } from "./fixtures";
import { propertyToday, shiftDate } from "../src/stay-types";

test("only a completed stay offers review submission and the result is public on mobile", async ({ page }, testInfo) => {
  const today = propertyToday();
  const stay = { id: 9, property_id: 7, status: "confirmed", title: "Stan pored parka", city: "Novi Sad", check_in: shiftDate(today, -5), check_out: shiftDate(today, -2), check_in_time: "14:00", check_out_time: "11:00", guests: 2, timezone: "Europe/Belgrade", total_cents: 18000, currency: "EUR", contact_email: "owner@example.com" };
  const review = { id: 1, rating: 5, comment: "Cist i miran stan, sve po dogovoru.", created_at: new Date().toISOString() };
  let saved = false;
  await page.route("**/api/stays/mine?*", route => route.fulfill({ json: { items: [stay, { ...stay, id: 10, status: "cancelled" }, { ...stay, id: 11, check_out: today }], total: 3, has_next: false } }));
  await page.route("**/api/stays/9/review", route => {
    if (route.request().method() === "POST") { expect(route.request().postDataJSON()).toEqual({ rating: 5, comment: review.comment }); saved = true; }
    return route.fulfill({ status: route.request().method() === "POST" ? 201 : 200, json: saved ? review : null });
  });
  await page.route("**/api/properties/7", route => route.fulfill({ json: { id: 7, venue_id: 1, title: stay.title, city: stay.city, description: "Ceo stan za prijatan odmor uz park.", offer_type: "short_stay", area_sqm: 50, rooms: 2, price_cents: 6000, currency: "EUR", contact_email: "owner@example.com", is_published: true, booking_enabled: false } }));
  await page.route("**/api/properties/7/reviews?*", route => route.fulfill({ json: { items: saved ? [review] : [], total: saved ? 1 : 0, average_rating: saved ? 5 : null, has_next: false } }));
  await page.goto("/stays");
  const button = page.getByRole("button", { name: "Oceni boravak / moja recenzija" });
  await expect(button).toHaveCount(1);
  await button.click();
  await page.getByRole("combobox", { name: "Ocena", exact: true }).selectOption("5");
  await page.getByLabel("Komentar", { exact: true }).fill(review.comment);
  await page.getByRole("button", { name: "Objavi recenziju" }).click();
  await expect(page.getByText("Tvoja ocena: 5 / 5")).toBeVisible();
  await page.reload();
  await page.getByRole("button", { name: "Oceni boravak / moja recenzija" }).click();
  await expect(page.getByText(review.comment)).toBeVisible();
  await expect(page.getByRole("button", { name: "Objavi recenziju" })).toHaveCount(0);
  await page.goto("/properties/7");
  await page.getByRole("button", { name: "Prikaži recenzije gostiju" }).click();
  await expect(page.getByText(/Prosečna ocena: 5/)).toBeVisible();
  await expect(page.getByText(review.comment)).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("property-reviews-mobile.png"), fullPage: true });
});
