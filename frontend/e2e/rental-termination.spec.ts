import { expect, test } from "./fixtures";
import type { RentalAgreement, RentalCharge, RentalTermination } from "../src/rental-agreement-types";

for (const mobile of [false, true]) {
  test(`mutual early rental end on ${mobile ? "mobile" : "desktop"}`, async ({ page }) => {
    if (mobile) await page.setViewportSize({ width: 390, height: 844 });
    const inquiry = { id: 1, property_id: 1, title: "Najam stana", monthly_price_cents: 60000, currency: "EUR", move_in: "2030-01-31", duration_months: 3, message: "Najam", owner_reply: "", viewing_at: null, status: "open", version: 1, created_at: "2029-12-01T00:00:00Z" };
    const agreement: RentalAgreement = { id: 1, inquiry_id: 1, title: inquiry.title, currency: "EUR", timezone: "Europe/Belgrade", start_date: inquiry.move_in, end_date: "2030-04-30", months: 3, monthly_cents: 60000, deposit_cents: 60000, notes: "", status: "accepted", version: 2, created_at: inquiry.created_at, accepted_at: inquiry.created_at };
    let termination: RentalTermination | null = null;
    let charges: RentalCharge[] = [0, 1, 2, 3].map(sequence => ({ id: sequence + 1, sequence, due_date: sequence < 2 ? "2030-01-31" : sequence === 2 ? "2030-02-28" : "2030-03-31", amount_cents: 60000, paid: false, version: 1, updated_at: null }));
    await page.route(/\/api\/(owner\/rental-inquiries|rental-inquiries\/mine)\?/, route => route.fulfill({ json: { items: [inquiry], total: 1, has_next: false } }));
    await page.route(/\/api\/rental-inquiries\/1\/agreements\?/, route => route.fulfill({ json: [agreement] }));
    await page.route("**/api/rental-agreements/1/charges", route => route.fulfill({ json: charges }));
    await page.route(/\/api\/rental-agreements\/1\/terminations(?:\?|$)/, route => {
      if (route.request().method() === "POST") {
        expect(route.request().postDataJSON()).toMatchObject({ version: 2, end_date: "2030-02-28", notes: "Sporazumna selidba" });
        termination = { id: 1, end_date: "2030-02-28", notes: "Sporazumna selidba", status: "proposed", version: 1, created_at: inquiry.created_at, decided_at: null };
        return route.fulfill({ status: 201, json: termination });
      }
      return route.fulfill({ json: termination ? [termination] : [] });
    });
    await page.route("**/api/rental-agreements/1/terminations/1/decision", route => {
      expect(route.request().postDataJSON()).toEqual({ version: 1, action: "accept" });
      termination = { ...termination!, status: "accepted", version: 2, decided_at: inquiry.created_at };
      agreement.terminated_on = "2030-02-28"; agreement.version = 3;
      charges = charges.map(c => c.sequence > 1 ? { ...c, voided_at: inquiry.created_at, version: 2 } : c);
      return route.fulfill({ json: termination });
    });
    await page.goto("/owner/rentals");
    await page.getByText("Dogovor o najmu i kirije", { exact: true }).click();
    await page.getByText("Prevremeni završetak najma", { exact: true }).click();
    await page.getByLabel("Novi datum završetka").selectOption("2030-02-28");
    await page.getByLabel("Razlog i dogovorene napomene").fill("Sporazumna selidba");
    await page.getByText("Pregledaj predlog završetka", { exact: true }).click();
    await expect(page.getByText("Odustani od ove odluke", { exact: true })).toBeFocused();
    await page.getByText("Potvrdi odluku o završetku", { exact: true }).click();
    await expect(page.getByRole("heading", { name: "Završetak #1 · Čeka odluku" })).toBeVisible();
    await page.goto("/rentals");
    await page.getByText("Dogovor o najmu i kirije", { exact: true }).click();
    await page.getByText("Prevremeni završetak najma", { exact: true }).click();
    await page.getByText("Prihvati raniji završetak", { exact: true }).click();
    await page.getByText("Potvrdi odluku o završetku", { exact: true }).click();
    await expect(page.getByText(/Dogovoren raniji završetak:/)).toBeVisible();
    await page.getByText("Raspored kirija i depozita", { exact: true }).click();
    await expect(page.getByText(/Ukinuta kirija/)).toHaveCount(2);
    await expect(page.getByRole("button", { name: /Evidentiraj uplatu/ })).toHaveCount(0);
    await page.getByText("Prevremeni završetak najma", { exact: true }).click();
    await expect(page.getByRole("heading", { name: "Završetak #1 · Prihvaćen" })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  });
}
