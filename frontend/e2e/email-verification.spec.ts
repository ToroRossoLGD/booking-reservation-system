import { expect, test } from "./fixtures";

for (const mobile of [false, true]) {
  test(`email verification on ${mobile ? "mobile" : "desktop"}`, async ({ page }) => {
    if (mobile) await page.setViewportSize({ width: 390, height: 844 });
    await page.route("**/api/auth/me", route => route.fulfill({ json: { id: 5, email: "guest@example.com", role: "customer", email_verified: false } }));
    await page.route("**/api/auth/email-verification/request", route => route.fulfill({ json: { message: "generic" } }));
    const token = "a".repeat(43);
    let confirmations = 0;
    await page.route("**/api/auth/email-verification/confirm", route => {
      expect(route.request().postDataJSON()).toEqual({ token });
      confirmations++;
      return route.fulfill({ json: { message: "ok" } });
    });
    await page.goto("/verify-email");
    await page.getByRole("button", { name: "Pošalji novi link" }).click();
    await expect(page.getByRole("status")).toContainText("spam folder");
    await page.goto(`/verify-email#token=${token}`);
    await expect(page).toHaveURL(/\/verify-email$/);
    expect(confirmations).toBe(0);
    await page.getByRole("button", { name: "Potvrdi email" }).click();
    await expect(page.getByRole("status")).toContainText("Email adresa je potvrđena");
    expect(confirmations).toBe(1);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  });
}
