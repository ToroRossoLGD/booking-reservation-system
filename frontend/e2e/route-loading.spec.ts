import { expect, test } from "./fixtures";

test.beforeEach(async ({ page }) => {
  await page.route("**/api/properties?*", route => route.fulfill({ json: { items: [], total: 0, limit: 12, offset: 0, has_next: false } }));
  await page.route("**/api/auth/me", route => route.fulfill({ status: 401, json: { detail: "Not signed in" } }));
  await page.route("**/api/venues", route => route.fulfill({ json: [] }));
  await page.route("**/api/promotions/active", route => route.fulfill({ json: [] }));
});

test("home does not fetch deferred routes; opening booking loads them", async ({ page }) => {
  const scripts: string[] = [];
  page.on("request", request => { if (request.resourceType() === "script") scripts.push(new URL(request.url()).pathname); });
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /negde te čeka/i })).toBeVisible();
  expect(scripts.some(path => /\/(App|Dashboard|StaysPage|RentalInquiriesPage|PasswordRecovery)\.tsx$/.test(path))).toBe(false);
  expect(scripts.some(path => path.includes("leaflet"))).toBe(false);
  await page.getByRole("link", { name: /postojeći sistem rezervacija/i }).click();
  await expect(page.getByRole("button", { name: "Prijava", exact: true })).toBeVisible();
  expect(scripts.some(path => path.endsWith("/App.tsx"))).toBe(true);
});

test("failed route download shows a recoverable error", async ({ page }) => {
  await page.route("**/src/App.tsx*", route => route.abort("failed"), { times: 1 });
  await page.goto("/booking");
  await expect(page.getByRole("heading", { name: "Stranica nije učitana." })).toBeVisible();
  await expect(page.getByRole("link", { name: "Vrati se na početnu" })).toHaveAttribute("href", "/");
  await page.getByRole("button", { name: "Učitaj ponovo" }).click();
  await expect(page.getByRole("button", { name: "Prijava", exact: true })).toBeVisible();
});

test("OAuth fragment is consumed before the booking module finishes loading", async ({ page }) => {
  let release!: () => void;
  const ready = new Promise<void>(resolve => { release = resolve; });
  await page.route("**/src/App.tsx*", async route => { await ready; await route.continue(); });
  try {
    await page.goto("/booking#auth_token=test-only-oauth-token", { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("status")).toHaveText("Učitavanje stranice…");
    await expect(page).toHaveURL(/\/booking$/);
    expect(await page.evaluate(() => localStorage.getItem("bookica_token"))).toBe("test-only-oauth-token");
  } finally { release(); }
  await expect(page.getByRole("button", { name: "Prijava", exact: true })).toBeVisible();
});
