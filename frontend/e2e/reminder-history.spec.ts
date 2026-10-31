import { expect, test } from "./fixtures";

for (const viewing of [false, true]) {
  test(`personal reminder history for ${viewing ? "viewings" : "stays"}`, async ({ page }) => {
    await page.setViewportSize({ width: viewing ? 1280 : 390, height: 900 });
    const kind = viewing ? "viewing" : "stay";
    await page.route("**/api/stays/mine?*", route => route.fulfill({ json: { items: [], total: 0, has_next: false } }));
    await page.route("**/api/sale-inquiries/mine?*", route => route.fulfill({ json: { items: [], total: 0, has_next: false } }));
    await page.route(`**/api/notifications/${kind}-reminders`, route => route.fulfill({ json: { enabled: true } }));
    let historyReads = 0;
    await page.route(`**/api/notifications/${kind}-reminders/history?*`, route => {
      historyReads++;
      const offset = Number(new URL(route.request().url()).searchParams.get("offset"));
      return route.fulfill({ json: { items: offset ? [] : [{ id: 1, kind: viewing ? "sale_viewing" : "arrival", reference_id: 7, scheduled_for: viewing ? "2026-11-02T12:00:00Z" : "2026-11-02", created_at: "2026-11-01T09:00:00Z" }], offset, has_next: !offset } });
    });
    await page.goto(viewing ? "/sales" : "/stays");
    await page.getByRole("button", { name: viewing ? "Podsetnici za razgledanja" : "Podsetnici za dolazak i odlazak" }).click();
    expect(historyReads).toBe(0);
    await page.getByRole("button", { name: "Istorija isporuke podsetnika" }).click();
    await expect(page.getByText(viewing ? "Razgledanje za kupovinu · upit #7" : "Dolazak · rezervacija #7")).toBeVisible();
    await page.getByRole("button", { name: "Sledećih 20 podsetnika" }).click();
    await expect(page.getByText("Nema zabeleženih podsetnika na ovoj stranici.")).toBeVisible();
    await page.getByRole("button", { name: "Osveži istoriju podsetnika" }).click();
    await expect(page.getByText(/Kreirano u aplikaciji:/)).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  });
}
