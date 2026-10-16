import { expect, test } from "./fixtures";

for (const mobile of [false, true]) {
  test(`account verification budget keeps explicit retry on ${mobile ? "mobile" : "desktop"}`, async ({ page }) => {
    if (mobile) await page.setViewportSize({ width: 390, height: 844 });
    await page.route("**/api/auth/me", route => route.fulfill({ json: { id: 5, email: "guest@example.com", role: "customer", email_verified: false } }));
    let attempts = 0;
    await page.route("**/api/auth/email-verification/request", route => {
      attempts++;
      return attempts === 1
        ? route.fulfill({ status: 429, headers: { "Retry-After": "900" }, json: { detail: "Too many" } })
        : route.fulfill({ json: { message: "generic" } });
    });
    await page.goto("/verify-email");
    await page.clock.install();
    await page.getByRole("button", { name: "Pošalji novi link" }).click();
    await expect(page.getByRole("alert")).toContainText("Sačekajte 900 sekundi");
    expect(attempts).toBe(1);
    await expect(page.getByRole("button", { name: "Pošalji novi link" })).toBeDisabled();
    await page.clock.fastForward(899000);
    await expect(page.getByRole("button", { name: "Pošalji novi link" })).toBeDisabled();
    expect(attempts).toBe(1);
    await page.clock.fastForward(1000);
    await expect(page.getByRole("button", { name: "Pošalji novi link" })).toBeEnabled();
    expect(attempts).toBe(1);
    await page.getByRole("button", { name: "Pošalji novi link" }).click();
    await expect(page.getByRole("status")).toContainText("spam folder");
    expect(attempts).toBe(2);
  });
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
