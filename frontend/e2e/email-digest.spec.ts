import { expect, test } from "./fixtures";

for (const width of [390, 1280]) {
  test(`email digest consent at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    let enabled = false;
    let interval = 1;
    await page.route("**/api/auth/me", route => route.fulfill({ json: { id: 2, email: "member@example.com", role: "customer", email_verified: true } }));
    await page.route("**/api/venues*", route => route.fulfill({ json: [] }));
    await page.route("**/api/promotions/active", route => route.fulfill({ json: [] }));
    await page.route("**/api/notifications/my?*", route => route.fulfill({ json: { items: [], total: 0, offset: 0, limit: 50, has_next: false } }));
    await page.route("**/api/notifications/email-digest", route => {
      if (route.request().method() === "PUT") { enabled = route.request().postDataJSON().enabled; interval = route.request().postDataJSON().interval_hours ?? interval; }
      return route.fulfill({ json: { enabled, interval_hours: interval, next_run_at: enabled ? "2030-01-01T10:00:00Z" : null, verified: true, available: true, last_status: "pending", last_attempt_at: null, last_accepted_at: null } });
    });
    await page.goto("/account/notifications");
    await page.getByRole("button", { name: "Email sažetak obaveštenja" }).click();
    await expect(page.getByText("Email sažetak je isključen.")).toBeVisible();
    await page.getByLabel("Učestalost email sažetka").selectOption("24");
    await expect(page.getByLabel("Učestalost email sažetka")).toHaveValue("24");
    await page.getByRole("button", { name: "Uključi email sažetak" }).click();
    await expect(page.getByText("Email sažetak je uključen.")).toBeVisible();
    await page.reload();
    await page.getByRole("button", { name: "Email sažetak obaveštenja" }).click();
    await expect(page.getByLabel("Učestalost email sažetka")).toHaveValue("24");
    await page.getByRole("button", { name: "Isključi email sažetak" }).click();
    await expect(page.getByText("Email sažetak je isključen.")).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  });
}
