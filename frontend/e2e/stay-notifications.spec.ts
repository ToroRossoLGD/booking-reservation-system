import { expect, test } from "./fixtures";

for (const owner of [false, true]) {
  test(`${owner ? "owner" : "guest"} opens stay notifications and follows the reservation link`, async ({ page }, testInfo) => {
    if (owner) await page.setViewportSize({ width: 390, height: 844 });
    const path = owner ? "/owner/stays" : "/stays";
    const title = owner ? "Nova rezervacija stana" : "Boravak je potvrđen";
    const notification = { id: 1, user_id: owner ? 1 : 2, title, message: "Rezervacija #42: Stan pored reke. 03.10.2026. – 06.10.2026. (Europe/Belgrade). Ukupno: 195.00 EUR. Plaćanje kod domaćina.", action_path: path, is_read: false, created_at: "2026-09-28T10:00:00Z" };
    await page.route("**/api/auth/me", route => route.fulfill({ json: { id: notification.user_id, email: "member@example.com", role: owner ? "owner" : "customer" } }));
    await page.route("**/api/venues*", route => route.fulfill({ json: [] }));
    await page.route("**/api/notifications/my?*", route => route.fulfill({ json: { items: [notification], total: 1, offset: 0, limit: 50, has_next: false } }));
    await page.route("**/api/notifications/1/read", route => {
      expect(route.request().method()).toBe("PATCH");
      notification.is_read = true;
      return route.fulfill({ json: notification });
    });
    await page.route(/\/api\/(owner\/stays|stays\/mine)\?/, route => route.fulfill({ json: { items: [], total: 0, has_next: false, properties: [], arrivals_today: 0, departures_today: 0 } }));
    await page.goto(path);
    await page.getByRole("link", { name: "Obaveštenja", exact: true }).click();
    await expect(page).toHaveURL(/\/account\/notifications$/);
    await expect(page.getByRole("heading", { name: title })).toBeVisible();
    await page.getByRole("button", { name: "Mark read", exact: true }).click();
    await expect(page.getByText("0 unread on this page")).toBeVisible();
    await page.getByRole("button", { name: "Refresh notifications" }).click();
    await expect(page.getByRole("heading", { name: title })).toBeVisible();
    await expect(page.getByRole("button", { name: "Mark read", exact: true })).toHaveCount(0);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.screenshot({ path: testInfo.outputPath(`stay-notifications-${owner ? "mobile" : "desktop"}.png`), fullPage: true });
    await page.getByRole("link", { name: owner ? "Rezervacije tvojih stanova ↗" : "Moji boravci ↗", exact: true }).click();
    await expect(page).toHaveURL(new RegExp(`${path}$`));
    await expect(page.getByRole("heading", { name: owner ? "Rezervacije tvojih stanova" : "Moji boravci", exact: true })).toBeVisible();
  });
}
