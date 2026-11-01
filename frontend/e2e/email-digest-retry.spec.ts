import { expect, test } from "./fixtures";

for (const width of [390, 1280]) {
  test(`failed email digest recovery at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    let retried = false;
    const status = () => ({ enabled: retried, interval_hours: 24, next_run_at: retried ? "2030-01-01T10:00:00Z" : null, verified: true, available: true, last_status: retried ? "pending" : "failed", last_attempt_at: "2026-11-01T09:00:00Z", last_accepted_at: null });
    await page.route("**/api/auth/me", route => route.fulfill({ json: { id: 2, email: "member@example.com", role: "customer", email_verified: true } }));
    await page.route("**/api/venues*", route => route.fulfill({ json: [] }));
    await page.route("**/api/promotions/active", route => route.fulfill({ json: [] }));
    await page.route("**/api/notifications/my?*", route => route.fulfill({ json: { items: [], total: 0, offset: 0, limit: 50, has_next: false } }));
    await page.route("**/api/notifications/email-digest", route => {
      expect(route.request().method()).toBe("GET");
      return route.fulfill({ json: status() });
    });
    await page.route("**/api/notifications/email-digest/retry", route => {
      expect(route.request().method()).toBe("POST");
      retried = true;
      return route.fulfill({ json: status() });
    });
    await page.goto("/account/notifications");
    await page.getByRole("button", { name: "Email sažetak obaveštenja" }).click();
    await expect(page.getByText(/Ponovni pokušaj zadržava/)).toBeVisible();
    await page.getByRole("button", { name: "Ponovi i uključi slanje" }).click();
    await expect(page.getByText("Email sažetak je uključen.")).toBeVisible();
    await expect(page.getByRole("button", { name: "Ponovi i uključi slanje" })).toHaveCount(0);
    await expect(page.getByLabel("Učestalost email sažetka")).toHaveValue("24");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  });
}
