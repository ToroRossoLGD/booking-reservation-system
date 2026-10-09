import { expect, test } from "./fixtures";

for (const mobile of [false, true]) {
  test(`rate limited recovery allows an explicit retry on ${mobile ? "mobile" : "desktop"}`, async ({ page }) => {
    if (mobile) await page.setViewportSize({ width: 390, height: 844 });
    let attempts = 0;
    await page.route("**/api/auth/password-reset/request", route => {
      attempts++;
      expect(route.request().postDataJSON()).toEqual({ email: "guest@example.com" });
      return attempts === 1
        ? route.fulfill({ status: 429, headers: { "Retry-After": "30" }, json: { detail: "Too many" } })
        : route.fulfill({ json: { message: "generic" } });
    });
    await page.goto("/forgot-password");
    await page.getByLabel("Email adresa").fill("guest@example.com");
    await page.getByRole("button", { name: "Pošalji link" }).click();
    await expect(page.getByRole("alert")).toContainText("Sačekajte 30 sekundi");
    expect(attempts).toBe(1);
    await expect(page.getByLabel("Email adresa")).toHaveValue("guest@example.com");
    await page.getByRole("button", { name: "Pošalji link" }).click();
    await expect(page.getByRole("status")).toContainText("Ako postoji nalog");
    expect(attempts).toBe(2);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  });
}
