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
    await page.goto(`/reset-password${mobile ? "/" : ""}#token=${token}`);
    await expect(page).toHaveURL(/\/reset-password\/?$/);
    await page.getByLabel("Nova lozinka", { exact: true }).fill("Changed-password-42");
    await expect(page.getByLabel("Nova lozinka", { exact: true })).toHaveAttribute("type", "password");
    await page.getByLabel("Ponovite lozinku").fill("Different-password-42");
    const visibility = page.getByRole("button", { name: "Prikaži lozinke" });
    await visibility.focus();
    await page.keyboard.press("Space");
    await expect(visibility).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByLabel("Ponovite lozinku")).toHaveAttribute("type", "text");
    await page.getByRole("button", { name: "Sačuvaj lozinku" }).click();
    await expect(page.getByLabel("Ponovite lozinku")).toBeFocused();
    await expect(page.getByLabel("Ponovite lozinku")).toHaveAttribute("aria-invalid", "true");
    await expect(page.getByLabel("Ponovite lozinku")).toHaveAttribute("aria-describedby", "reset-error");
    await expect(page.getByRole("alert")).toHaveText("Lozinke se ne poklapaju.");
    await expect(visibility).toHaveAttribute("aria-pressed", "false");
    await expect(page.getByLabel("Nova lozinka", { exact: true })).toHaveAttribute("type", "password");
    await page.getByLabel("Ponovite lozinku").fill("Changed-password-42");
    await expect(page.getByLabel("Ponovite lozinku")).toHaveAttribute("aria-invalid", "false");
    await page.getByRole("button", { name: "Sačuvaj lozinku" }).click();
    await expect(page.getByRole("status")).toContainText("Lozinka je promenjena");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  });
}
