import { expect, test } from "@playwright/test";

for (const mobile of [false, true]) {
  test(`password visibility preserves credentials and resets on ${mobile ? "mobile" : "desktop"}`, async ({ page }) => {
    if (mobile) await page.setViewportSize({ width: 390, height: 844 });
    await page.route("**/api/auth/me", route => route.fulfill({ status: 401, json: { detail: "Not signed in" } }));
    await page.route("**/api/venues", route => route.fulfill({ json: [] }));
    await page.route("**/api/promotions/active", route => route.fulfill({ json: [] }));
    let submissions = 0;
    await page.route("**/api/auth/login", route => {
      submissions++;
      const data = new URLSearchParams(route.request().postData()!);
      expect(data.get("password")).toBe("Sample-secret-42!");
      return route.fulfill({ status: 401, json: { detail: "Invalid credentials" } });
    });
    await page.goto("/booking");
    await page.getByRole("button", { name: "Log in", exact: true }).click();
    const password = page.getByLabel("Password", { exact: true });
    const toggle = page.getByRole("button", { name: "Show password", exact: true });
    await page.getByLabel("Email address").fill("buyer@example.com");
    await password.fill("Sample-secret-42!");
    await expect(password).toHaveAttribute("type", "password");
    await expect(password).toHaveAttribute("autocomplete", "current-password");
    await password.press("Tab");
    await expect(toggle).toBeFocused();
    await toggle.press("Space");
    await expect(password).toHaveAttribute("type", "text");
    await expect(toggle).toHaveAttribute("aria-pressed", "true");
    await expect(password).toHaveValue("Sample-secret-42!");
    expect(submissions).toBe(0);
    await toggle.press("Enter");
    await expect(password).toHaveAttribute("type", "password");
    await toggle.click();
    await page.getByRole("button", { name: "New here? Create an account" }).click();
    await expect(password).toHaveAttribute("type", "password");
    await expect(password).toHaveAttribute("autocomplete", "new-password");
    await toggle.click();
    await expect(password).toHaveAttribute("type", "text");
    await page.getByRole("button", { name: "Already have an account? Sign in" }).click();
    await expect(password).toHaveAttribute("type", "password");
    await toggle.click();
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await expect(page.getByText("Invalid credentials", { exact: true })).toBeVisible();
    expect(submissions).toBe(1);
    await expect(password).toHaveAttribute("type", "password");
    await expect(password).toHaveValue("Sample-secret-42!");
    await toggle.click();
    await page.getByRole("button", { name: "Close", exact: true }).click();
    await page.getByRole("button", { name: "Log in", exact: true }).click();
    await expect(password).toHaveAttribute("type", "password");
    await expect(password).toHaveValue("");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  });
}
