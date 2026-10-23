import { expect, test } from "./fixtures";

for (const mobile of [false, true]) {
  test(`review pages recover on ${mobile ? "mobile" : "desktop"}`, async ({ page }) => {
    if (mobile) await page.setViewportSize({ width: 390, height: 844 });
    await page.route("**/api/properties/7", route => route.fulfill({ json: { id: 7, venue_id: 1, title: "Stan za odmor", city: "Novi Sad", description: "Stan sa terasom.", offer_type: "short_stay", booking_enabled: false, area_sqm: 60, rooms: 2, price_cents: 6500, currency: "EUR", is_published: true } }));
    let empty = false;
    let failed = false;
    const offsets: number[] = [];
    await page.route("**/api/properties/7/reviews?*", route => {
      const offset = Number(new URL(route.request().url()).searchParams.get("offset"));
      offsets.push(offset);
      if (failed) return route.fulfill({ status: 503, json: { detail: "unavailable" } });
      return route.fulfill({ json: { items: empty ? [] : [{ id: offset + 1, rating: 5, comment: "Odličan boravak." }], total: empty ? 0 : 11, average_rating: empty ? null : 5, has_next: !empty && offset === 0 } });
    });
    await page.goto("/properties/7");
    expect(offsets).toHaveLength(0);
    await page.getByRole("button", { name: "Prikaži recenzije gostiju" }).click();
    const heading = page.getByRole("heading", { name: "Iskustva gostiju" });
    await expect(heading).toBeFocused();
    await page.getByRole("button", { name: "Sledeće recenzije" }).click();
    await expect(page.getByRole("button", { name: "Sledeće recenzije" })).toBeDisabled();
    await expect(heading).toBeFocused();
    await page.getByRole("button", { name: "Prethodne recenzije" }).click();
    await expect(page.getByRole("button", { name: "Prethodne recenzije" })).toBeDisabled();
    failed = true;
    await page.getByRole("button", { name: "Sledeće recenzije" }).click();
    await expect(page.getByRole("alert")).toContainText("Recenzije nisu učitane");
    await expect(heading).toBeFocused();
    failed = false; empty = true;
    await page.getByRole("button", { name: "Pokušaj ponovo" }).click();
    await expect(page.getByText("Još nema recenzija.")).toBeVisible();
    await expect(page.getByRole("status")).toContainText("Prikazana je prva stranica");
    await expect(heading).toBeFocused();
    expect(offsets).toEqual([0, 10, 0, 10, 10, 0]);
    await expect(page.getByRole("button", { name: "Prethodne recenzije" })).toBeDisabled();
    await expect(page.getByRole("button", { name: "Sledeće recenzije" })).toBeDisabled();
  });
}
