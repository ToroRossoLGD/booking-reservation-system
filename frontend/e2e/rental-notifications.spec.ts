import { expect, test } from "./fixtures";

test("tenant opens a viewing notification and returns to rental inquiries on mobile", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.route("**/api/auth/me", route => route.fulfill({ json: { id: 2, email: "tenant@example.com", role: "customer" } }));
  await page.route("**/api/venues*", route => route.fulfill({ json: [] }));
  await page.route("**/api/rental-inquiries/mine?*", route => route.fulfill({ json: { items: [], total: 0, has_next: false } }));
  await page.route("**/api/notifications/my?*", route => route.fulfill({ json: { items: [{ id: 1, title: "Predložen termin razgledanja", message: "Upit #42: Stan pored reke. Termin: 03.10.2026. 12:00 UTC.", action_path: "/rentals", is_read: false, created_at: "2026-09-29T10:00:00Z" }], total: 1, offset: 0, limit: 50, has_next: false } }));
  await page.goto("/rentals");
  await page.getByRole("link", { name: "Obaveštenja", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Predložen termin razgledanja" })).toBeVisible();
  await page.getByRole("link", { name: "Moji upiti za najam ↗", exact: true }).click();
  await expect(page).toHaveURL(/\/rentals$/);
  await expect(page.getByRole("heading", { name: "Moji upiti za najam" })).toBeVisible();
});
