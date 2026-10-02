import { expect, test } from "@playwright/test";

test("mobile user opts in, opens a matching property from the inbox and opts out", async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.addInitScript(() => localStorage.setItem("bookica_token", "alert-user"));
  const search = { id: 1, name: "Moj stan", path: "/?city=Novi+Sad&offer_type=long_term", alerts_enabled: false };
  const listing = { id: 7, venue_id: 1, title: "Stan pored reke", city: "Novi Sad", description: "Stan sa terasom.", offer_type: "long_term", area_sqm: 60, rooms: 2, price_cents: 65000, currency: "EUR", contact_email: "owner@example.com", is_published: true };
  const changes: boolean[] = [];
  await page.route("**/api/auth/me", route => route.fulfill({ json: { id: 2, email: "member@example.com", role: "customer" } }));
  await page.route("**/api/venues*", route => route.fulfill({ json: [] }));
  await page.route("**/api/properties?*", route => route.fulfill({ json: { items: [], total: 0, offset: 0, limit: 12, has_next: false } }));
  await page.route("**/api/properties/7", route => route.fulfill({ json: listing }));
  await page.route("**/api/saved-searches", route => route.fulfill({ json: [search] }));
  await page.route("**/api/saved-searches/1/alerts", route => {
    expect(route.request().method()).toBe("PATCH");
    search.alerts_enabled = route.request().postDataJSON().enabled;
    changes.push(search.alerts_enabled);
    return route.fulfill({ json: search });
  });
  await page.route("**/api/notifications/my?*", route => route.fulfill({ json: {
    items: [{ id: 1, user_id: 2, title: "Novi oglas: Moj stan", message: "Stan pored reke odgovara tvojoj pretrazi.", action_path: "/properties/7", is_read: false, created_at: "2026-10-03T10:00:00Z" }],
    total: 1, offset: 0, limit: 50, has_next: false,
  } }));
  await page.goto("/");
  await page.getByRole("button", { name: "Pretrage na nalogu", exact: true }).click();
  const panel = page.getByRole("region", { name: "Pretrage na nalogu", exact: true });
  await expect(panel.getByText("Obaveštenja: isključena", { exact: true })).toBeVisible();
  expect(changes).toEqual([]);
  await panel.getByRole("button", { name: "Uključi obaveštenja: Moj stan" }).click();
  await expect(panel.getByRole("button", { name: "Isključi obaveštenja: Moj stan" })).toHaveAttribute("aria-pressed", "true");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await panel.screenshot({ path: testInfo.outputPath("search-alerts-mobile.png") });
  await panel.getByRole("link", { name: "inbox u aplikaciji" }).click();
  await expect(page.getByRole("heading", { name: "Novi oglas: Moj stan" })).toBeVisible();
  await page.getByRole("link", { name: "Pogledaj oglas ↗" }).click();
  await expect(page).toHaveURL(/\/properties\/7$/);
  await expect(page.getByRole("heading", { name: listing.title, exact: true })).toBeVisible();
  await page.goto("/");
  await page.getByRole("button", { name: "Pretrage na nalogu", exact: true }).click();
  await panel.getByRole("button", { name: "Isključi obaveštenja: Moj stan" }).click();
  await expect(panel.getByText("Obaveštenja: isključena", { exact: true })).toBeVisible();
  expect(changes).toEqual([true, false]);
});
