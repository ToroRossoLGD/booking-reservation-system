import { expect, test } from "./fixtures";

test.beforeEach(async ({ page }) => {
  await page.route("**/api/auth/me", route => route.fulfill({ status: 401, json: { detail: "Not signed in" } }));
  await page.route("**/api/venues", route => route.fulfill({ json: [] }));
  await page.route("**/api/promotions/active", route => route.fulfill({ json: [] }));
  await page.goto("/booking");
});

test("account dialog contains keyboard focus and restores its opener on Escape", async ({ page }) => {
  const opener = page.getByRole("button", { name: "Prijava", exact: true });
  await opener.click();
  const dialog = page.getByRole("dialog", { name: "Pristup nalogu" });
  const close = dialog.getByRole("button", { name: "Zatvori", exact: true });
  await expect(close).toBeFocused();
  await expect(dialog).toHaveJSProperty("open", true);
  // Even a programmatic focus request cannot move focus to the inert page.
  await opener.evaluate(element => element.focus());
  await expect(close).toBeFocused();
  await page.keyboard.press("Shift+Tab");
  await expect(dialog.getByRole("button", { name: "Nemaš nalog? Registruj se" })).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(close).toBeFocused();
  await dialog.getByLabel("Email adresa").fill("guest@example.com");
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await expect(opener).toBeFocused();
  expect(await page.evaluate(() => document.body.style.overflow)).not.toBe("hidden");
});

test("switching forms retains modal behavior and explicit close restores focus", async ({ page }) => {
  const opener = page.getByRole("button", { name: "Prijava", exact: true });
  await opener.click();
  const dialog = page.getByRole("dialog", { name: "Pristup nalogu" });
  await dialog.getByRole("button", { name: "Nemaš nalog? Registruj se" }).click();
  await expect(dialog.getByRole("heading", { name: "Napravi svoj nalog." })).toBeVisible();
  await dialog.getByRole("button", { name: "Zatvori", exact: true }).click();
  await expect(dialog).toHaveCount(0);
  await expect(opener).toBeFocused();
  await opener.click();
  await expect(dialog).toBeVisible();
  await page.mouse.click(5, 5);
  await expect(dialog).toHaveCount(0);
  await expect(opener).toBeFocused();
});

test("small screens keep account fields and close action reachable", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 664 });
  await page.getByRole("button", { name: "Registracija", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Pristup nalogu" });
  await expect(dialog).toBeVisible();
  await dialog.getByLabel("Email adresa").fill("mobile@example.com");
  await dialog.getByRole("button", { name: "Već imaš nalog? Prijavi se" }).click();
  await dialog.getByRole("button", { name: "Zatvori", exact: true }).click();
  await expect(dialog).toHaveCount(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test("reservation cancellation starts on the safe action; reschedule has a named dialog", async ({ page }) => {
  await page.route("**/api/auth/me", route => route.fulfill({ json: { id: 1, email: "guest@example.com", role: "customer" } }));
  await page.route("**/api/reservations/my?*", route => route.fulfill({ json: { items: [], has_next: false } }));
  await page.route("**/api/reservations/1/workspace", route => route.fulfill({ json: {
    reservation: { id: 1, status: "confirmed", start_time: "2030-01-01T10:00:00Z", end_time: "2030-01-01T11:00:00Z", party_size: 1, quoted_amount_cents: 1000, quoted_currency: "EUR" },
    resource: { id: 1, name: "Test space", capacity: 2 }, venue: { id: 1, name: "Venue", address: "Address" },
    payment: null, timeline: [], allowed_actions: ["cancel", "reschedule"],
    cancellation_preview: { refund_amount_cents: 1000, cancellation_fee_cents: 0 },
  } }));
  await page.goto("/account/reservations/1");
  const cancel = page.getByRole("button", { name: "Cancel reservation", exact: true });
  await cancel.click();
  const dialog = page.getByRole("dialog", { name: "Cancel reservation?", exact: true });
  await expect(dialog.getByRole("button", { name: "Keep reservation" })).toBeFocused();
  await page.route("**/api/reservations/1/cancel", route => route.fulfill({ status: 503, json: { detail: "Please retry later" } }));
  await dialog.getByRole("button", { name: "Confirm cancellation" }).click();
  await expect(dialog.getByRole("alert")).toContainText("Please retry later");
  await page.keyboard.press("Escape");
  await expect(cancel).toBeFocused();
  const reschedule = page.getByRole("button", { name: "Reschedule", exact: true });
  await reschedule.click();
  await expect(page.getByRole("dialog", { name: "Reschedule reservation" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(reschedule).toBeFocused();
});
