import { expect, test } from "@playwright/test";

for (const mobile of [false, true]) {
  test(`demo notice stays visible on ${mobile ? "mobile" : "desktop"}`, async ({ page }) => {
    if (mobile) await page.setViewportSize({ width: 390, height: 844 });
    await page.route("**/api/runtime-config", route => route.fulfill({ json: { demo: true } }));
    await page.route("**/api/properties?*", route => route.fulfill({ json: { items: [], total: 0, has_next: false } }));
    await page.goto("/");
    const banner = page.getByRole("note").filter({ hasText: "DEMO" });
    await expect(banner).toBeVisible();
    await expect(banner).toContainText("ne unosite lične podatke");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.goto("/booking");
    await expect(banner).toBeVisible();
  });
}
