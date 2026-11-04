import { expect, test } from "./fixtures";
import type { RentalAgreement, RentalCharge } from "../src/rental-agreement-types";

for (const mobile of [false, true]) {
  test(`rental agreement and manual payment on ${mobile ? "mobile" : "desktop"}`, async ({ page }) => {
    if (mobile) await page.setViewportSize({ width: 390, height: 844 });
    const inquiry = { id: 1, property_id: 1, title: "Dugoročni najam", monthly_price_cents: 60000, currency: "EUR", move_in: "2030-01-31", duration_months: 3, message: "Upit za stan", owner_reply: "", viewing_at: null, status: "open", version: 1, created_at: "2029-12-01T00:00:00Z" };
    let agreement: RentalAgreement | null = null;
    let charge: RentalCharge = { id: 1, sequence: 1, due_date: "2030-01-31", amount_cents: 60000, paid: false, version: 1, updated_at: null };
    await page.route(/\/api\/(owner\/rental-inquiries|rental-inquiries\/mine)\?/, route => route.fulfill({ json: { items: [inquiry], total: 1, has_next: false } }));
    await page.route(/\/api\/rental-inquiries\/1\/agreements(?:\?|$)/, route => {
      if (route.request().method() === "POST") {
        const data = route.request().postDataJSON();
        expect(data).toMatchObject({ months: 3, monthly_cents: 60000, deposit_cents: 0 });
        agreement = { ...data, id: 1, inquiry_id: 1, title: inquiry.title, currency: "EUR", timezone: "Europe/Belgrade", end_date: "2030-04-30", status: "proposed", version: 1, created_at: inquiry.created_at, accepted_at: null };
        return route.fulfill({ status: 201, json: agreement });
      }
      return route.fulfill({ json: agreement ? [agreement] : [] });
    });
    await page.route("**/api/rental-agreements/1/decision", route => {
      expect(route.request().postDataJSON()).toEqual({ version: 1, action: "accept" });
      agreement = { ...agreement!, status: "accepted", version: 2, accepted_at: inquiry.created_at };
      return route.fulfill({ json: agreement });
    });
    await page.route("**/api/rental-agreements/1/charges", route => route.fulfill({ json: [charge] }));
    await page.route("**/api/rental-agreements/1/charges/1", route => {
      expect(route.request().postDataJSON()).toEqual({ version: 1, paid: true });
      charge = { ...charge, paid: true, version: 2, updated_at: inquiry.created_at };
      return route.fulfill({ json: charge });
    });
    await page.route("**/api/rental-agreements/1/charges/1/events", route => route.fulfill({ json: [{ id: 1, paid: true, version: 2, created_at: inquiry.created_at }] }));
    await page.goto("/owner/rentals");
    await page.getByText("Dogovor o najmu i kirije", { exact: true }).click();
    await page.getByText("Pošalji predlog najma", { exact: true }).click();
    await expect(page.getByRole("heading", { name: "Dogovor #1 · Predlog" })).toBeVisible();
    await page.goto("/rentals");
    await page.getByText("Dogovor o najmu i kirije", { exact: true }).click();
    await page.getByText("Prihvati uslove najma", { exact: true }).click();
    await page.getByText("Potvrdi odluku o najmu", { exact: true }).click();
    await expect(page.getByRole("heading", { name: "Dogovor #1 · Prihvaćeno" })).toBeVisible();
    await page.goto("/owner/rentals");
    await page.getByText("Dogovor o najmu i kirije", { exact: true }).click();
    await page.getByText("Raspored kirija i depozita", { exact: true }).click();
    await page.getByRole("button", { name: /Evidentiraj uplatu/ }).click();
    await page.getByText("Potvrdi evidenciju", { exact: true }).click();
    await expect(page.getByText(/Vlasnik je evidentirao uplatu/)).toBeVisible();
    await page.getByText("Istorija evidencije", { exact: true }).click();
    await expect(page.getByText(/Uplata evidentirana/)).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  });
}
