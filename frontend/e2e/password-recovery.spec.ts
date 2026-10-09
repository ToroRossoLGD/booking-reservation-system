import { expect, test } from "./fixtures";

for (const mobile of [false, true]) {
  test(`password recovery request and confirmation on ${mobile ? "mobile" : "desktop"}`, async ({ page }) => {
    if (mobile) await page.setViewportSize({ width: 390, height: 844 });
    await page.route("**/api/auth/password-reset/request", route => {
      expect(route.request().postDataJSON()).toEqual({ email: "user@example.com" });
      return route.fulfill({ json: { message: "generic" } });
    });
    const token = "a".repeat(43);
    await page.route("**/api/auth/password-reset/confirm", route => {
      expect(route.request().postDataJSON()).toEqual({ token, new_password: "Changed-password-42" });
      return route.fulfill({ json: { message: "ok" } });
    });
    await page.goto("/forgot-password");
    await page.getByLabel("Email adresa").fill("user@example.com");
    await page.getByRole("button", { name: "Pošalji link" }).click();
    await expect(page.getByRole("status")).toContainText("Ako postoji nalog");
    await page.goto(`/reset-password#token=${token}`);
    await expect(page).toHaveURL(/\/reset-password$/);
    await page.getByLabel("Nova lozinka", { exact: true }).fill("Changed-password-42");
    await page.getByLabel("Ponovite lozinku").fill("Changed-password-42");
    await page.getByRole("button", { name: "Sačuvaj lozinku" }).click();
    await expect(page.getByRole("status")).toContainText("Lozinka je promenjena");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  });
}
