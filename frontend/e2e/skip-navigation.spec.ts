import { expect, test } from "./fixtures";

test("keyboard skip link focuses the single main landmark without changing the search URL", async ({ page }, testInfo) => {
  await page.route("**/api/properties?*", route => route.fulfill({ json: { items: [], total: 0, offset: 0, limit: 12, has_next: false } }));
  for (const path of ["/?city=Novi+Sad", "/properties/0", "/saved", "/stays", "/rentals"]) {
    await page.goto(path);
    const main = page.getByRole("main");
    await expect(main).toHaveCount(1);
    await expect(main.getByRole("heading").first()).toBeVisible();
    const originalUrl = page.url();
    await page.keyboard.press("Tab");
    const skip = page.getByRole("link", { name: "Preskoči na sadržaj" });
    await expect(skip).toBeFocused();
    await expect(skip).toBeInViewport();
    await page.keyboard.press("Enter");
    await expect(main).toBeFocused();
    expect(page.url()).toBe(originalUrl);
    await page.keyboard.press("Tab");
    expect(await main.evaluate(element => element.contains(document.activeElement))).toBe(true);
  }
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Preskoči na sadržaj" })).toBeInViewport();
  await page.screenshot({ path: testInfo.outputPath("skip-link-mobile.png") });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
