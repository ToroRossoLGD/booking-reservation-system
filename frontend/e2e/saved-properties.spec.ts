import { expect, test } from "./fixtures";

test("saved pages recover from withdrawals, failures and an empty account", async ({ page }) => {
  const property = { id: 4, venue_id: 1, title: "Preostali stan", description: "Stan sa terasom.", city: "Beograd", offer_type: "long_term", area_sqm: 50, rooms: 2, price_cents: 65000, currency: "EUR", contact_email: "owner@example.com", is_published: true };
  let total = 13;
  let failed = false;
  const offsets: number[] = [];
  await page.route("**/api/favorites/properties?*", route => {
    const offset = Number(new URL(route.request().url()).searchParams.get("offset"));
    offsets.push(offset);
    if (failed) return route.fulfill({ status: 503, json: { detail: "unavailable" } });
    return route.fulfill({ json: { items: offset < total ? [property] : [], total, limit: 12, offset, has_next: offset + 12 < total } });
  });
  await page.goto("/saved");
  await page.getByRole("button", { name: "Sledeća" }).click();
  await expect(page.getByText("Stranica 2", { exact: true })).toBeVisible();
  total = 1;
  await page.getByRole("button", { name: "Osveži oglase" }).click();
  await expect(page.getByRole("status")).toHaveText("Sačuvano oglasa: 1");
  expect(offsets.slice(-2)).toEqual([12, 0]);
  await expect(page.getByRole("heading", { name: "Sačuvani oglasi", exact: true })).toBeFocused();
  await expect(page.getByRole("heading", { name: property.title })).toBeVisible();
  failed = true;
  await page.getByRole("button", { name: "Osveži oglase" }).click();
  await expect(page.getByRole("alert")).toContainText("Sačuvani oglasi nisu učitani");
  failed = false; total = 0;
  await page.getByRole("button", { name: "Pokušaj ponovo" }).click();
  await expect(page.getByRole("heading", { name: "Još nema sačuvanih oglasa za prikaz." })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Sačuvani oglasi", exact: true })).toBeFocused();
});

for (const mobile of [false, true]) {
  test(`saved listings follow session changes on ${mobile ? "mobile" : "desktop"}`, async ({ page, context }) => {
    if (mobile) await page.setViewportSize({ width: 390, height: 844 });
    const property = { id: 4, venue_id: 1, title: "Privatni izbor prvog naloga", description: "Stan sa terasom.", city: "Beograd", offer_type: "long_term", area_sqm: 50, rooms: 2, price_cents: 65000, currency: "EUR", is_published: true };
    const offsets: number[] = [];
    let release!: () => void;
    const pending = new Promise<void>(resolve => { release = resolve; });
    await context.route("**/api/favorites/properties?*", async route => {
      const token = route.request().headers().authorization;
      const offset = Number(new URL(route.request().url()).searchParams.get("offset"));
      if (!token) return route.fulfill({ status: 401, json: { detail: "unauthorized" } });
      if (token === "Bearer second") {
        offsets.push(offset);
        return route.fulfill({ json: { items: [], total: 0, limit: 12, offset, has_next: false } });
      }
      if (offset === 12) await pending;
      await route.fulfill({ json: { items: [property], total: 13, limit: 12, offset, has_next: offset === 0 } }).catch(() => {});
    });
    await page.goto("/saved");
    const other = await context.newPage();
    await other.goto("/help");
    await other.evaluate(() => localStorage.setItem("bookica_token", "first"));
    await expect(page.getByRole("heading", { name: property.title })).toBeVisible();
    const oldRequest = page.waitForRequest(request => request.url().includes("favorites/properties?") && new URL(request.url()).searchParams.get("offset") === "12");
    await page.getByRole("button", { name: "Sledeća" }).click();
    await oldRequest;
    await other.evaluate(() => localStorage.setItem("bookica_token", "second"));
    await expect(page.getByRole("heading", { name: "Još nema sačuvanih oglasa za prikaz." })).toBeVisible();
    release();
    await expect(page.getByRole("heading", { name: property.title })).toHaveCount(0);
    expect(offsets.length).toBeGreaterThan(0);
    expect(offsets.every(offset => offset === 0)).toBe(true);
    await other.evaluate(() => localStorage.removeItem("bookica_token"));
    await expect(page.getByRole("alert")).toContainText("Prijavi se da vidiš");
    await expect(page.getByRole("heading", { name: property.title })).toHaveCount(0);
    // A same-tab change is picked up when the window receives focus again.
    await page.evaluate(() => {
      localStorage.setItem("bookica_token", "first");
      window.dispatchEvent(new Event("focus"));
    });
    await expect(page.getByRole("heading", { name: property.title })).toBeVisible();
  });

  test(`save and revisit property on ${mobile ? "mobile" : "desktop"}`, async ({ page }, testInfo) => {
    if (mobile) await page.setViewportSize({ width: 390, height: 844 });
    await page.addInitScript(() => localStorage.setItem("bookica_token", "fixture-token"));
    const property = { id: 4, venue_id: 1, title: "Stan pored parka", description: "Svetao stan pored parka sa velikom terasom.", city: "Beograd", offer_type: "long_term", area_sqm: 50, rooms: 2, price_cents: 65000, currency: "EUR", contact_email: "owner@example.com", is_published: true };
    let saved = false;
    await page.route("**/api/properties?*", route => route.fulfill({ json: { items: [property], total: 1, limit: 12, offset: 0, has_next: false } }));
    await page.route("**/api/favorites/properties/status?*", route => route.fulfill({ json: { property_ids: saved ? [4] : [] } }));
    await page.route("**/api/favorites/properties?*", route => route.fulfill({ json: { items: saved ? [property] : [], total: saved ? 1 : 0, limit: 12, offset: 0, has_next: false } }));
    await page.route("**/api/favorites/properties/4", route => {
      expect(route.request().headers().authorization).toBe("Bearer fixture-token");
      saved = route.request().method() === "PUT";
      return saved ? route.fulfill({ json: { property_id: 4, saved: true } }) : route.fulfill({ status: 204 });
    });
    await page.goto("/");
    await page.getByRole("button", { name: `Sačuvaj oglas: ${property.title}` }).click();
    await expect(page.getByRole("button", { name: `Ukloni iz sačuvanih: ${property.title}` })).toHaveAttribute("aria-pressed", "true");
    await page.reload();
    await expect(page.getByRole("button", { name: `Ukloni iz sačuvanih: ${property.title}` })).toHaveAttribute("aria-pressed", "true");
    const navigation = page.getByRole("navigation", { name: mobile ? "Mobilna navigacija" : "Glavna navigacija", exact: true });
    await navigation.getByRole("link", { name: mobile ? "Sačuvano" : "Sačuvani oglasi", exact: true }).click();
    await expect(page).toHaveURL(/\/saved$/);
    await expect(page.getByRole("heading", { name: property.title })).toBeVisible();
    await page.getByRole("button", { name: `Detalji: ${property.title}` }).click();
    await expect(page.getByRole("button", { name: "Pošalji upit za najam" })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.screenshot({ path: testInfo.outputPath("saved-property.png"), fullPage: true });
    await page.getByRole("button", { name: `Ukloni iz sačuvanih: ${property.title}` }).click();
    await expect(page.getByRole("heading", { name: "Još nema sačuvanih oglasa za prikaz." })).toBeVisible();
    await page.getByRole("link", { name: "Istraži ponudu" }).click();
    await expect(page.getByRole("button", { name: `Sačuvaj oglas: ${property.title}` })).toHaveAttribute("aria-pressed", "false");
  });
}
