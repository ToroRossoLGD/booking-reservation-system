import { expect, test } from "./fixtures";

test.beforeEach(async ({ page }) => {
  await page.route("**/api/properties?*", route => route.fulfill({ json: { items: [], total: 0, limit: 12, offset: 0, has_next: false } }));
  await page.route("**/api/auth/me", route => route.fulfill({ status: 401, json: { detail: "Not signed in" } }));
  await page.route("**/api/venues", route => route.fulfill({ json: [] }));
  await page.route("**/api/promotions/active", route => route.fulfill({ json: [] }));
});

test("unknown routes show safe recovery instead of downloading legacy screens", async ({ page }) => {
  const modules: string[] = [];
  page.on("request", request => { if (request.resourceType() === "script") modules.push(new URL(request.url()).pathname); });
  for (const path of ["/missing?private=value#private-fragment", "/account/unknown", "/owner/unknown", "/booking/unknown", "/saved//"]) {
    await page.goto(path);
    await expect(page.getByRole("heading", { name: "Stranica nije pronađena." })).toBeVisible();
    await expect(page).toHaveTitle("Stranica nije pronađena | Bookica");
    await expect(page.getByRole("main")).toHaveCount(1);
    expect(await page.locator("body").innerText()).not.toContain("private-fragment");
    expect(await page.locator("head").innerHTML()).not.toContain("private=value");
  }
  expect(modules.some(path => path.endsWith("/App.tsx"))).toBe(false);
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Preskoči na sadržaj" })).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("main")).toBeFocused();
  await page.getByRole("link", { name: "Pogledaj ponudu nekretnina" }).click();
  await expect(page.getByRole("heading", { name: /negde te čeka/i })).toBeVisible();
  await expect(page).toHaveTitle("Bookica — Nekretnine za život i odmor");
  await page.goBack();
  await expect(page.getByRole("heading", { name: "Stranica nije pronađena." })).toBeVisible();
});

test("trailing slash keeps the intended page and recovery fragment handling", async ({ page }) => {
  await page.goto("/forgot-password/");
  await expect(page).toHaveTitle("Zaboravljena lozinka | Bookica");
  await expect(page.getByRole("heading", { name: "Zaboravljena lozinka" })).toBeVisible();
  await page.goto("/saved/");
  await expect(page).toHaveTitle("Sačuvani oglasi | Bookica");
  await expect(page.getByRole("heading", { name: "Stranica nije pronađena." })).toHaveCount(0);
  await page.goto("/properties/invalid");
  await expect(page.getByRole("heading", { name: "Oglas nije dostupan." })).toBeVisible();
  await page.setViewportSize({ width: 390, height: 664 });
  await page.goto("/does-not-exist");
  await expect(page.getByRole("link", { name: "Moj nalog", exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.getByRole("link", { name: "Moj nalog", exact: true }).click();
  await expect(page.getByRole("button", { name: "Registracija", exact: true })).toBeVisible();
});
