import { expect, test } from "./fixtures";

test("Serbian registration preserves input after a conflict and completes the existing flow", async ({ page }) => {
  let authenticated = false;
  let registrations = 0;
  await page.route("**/api/venues", route => route.fulfill({ json: [] }));
  await page.route("**/api/promotions/active", route => route.fulfill({ json: [] }));
  await page.route("**/api/auth/me", route => authenticated
    ? route.fulfill({ json: { id: 1, email: "guest@example.com", role: "customer" } })
    : route.fulfill({ status: 401, json: { detail: "Not signed in" } }));
  await page.route("**/api/auth/register", route => {
    registrations++;
    expect(route.request().postDataJSON()).toMatchObject({ email: "guest@example.com", password: "Sample-secret-42!" });
    return registrations === 1
      ? route.fulfill({ status: 409, json: { detail: "User with this email already exists" } })
      : route.fulfill({ status: 201, json: { id: 1, email: "guest@example.com", role: "customer" } });
  });
  await page.route("**/api/auth/login", route => {
    authenticated = true;
    return route.fulfill({ json: { access_token: "test-token", token_type: "bearer" } });
  });
  await page.goto("/booking");
  await page.getByRole("button", { name: "Registracija", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Pristup nalogu" });
  await dialog.getByLabel("Email adresa").fill("guest@example.com");
  await dialog.getByLabel("Lozinka", { exact: true }).fill("Sample-secret-42!");
  await dialog.getByRole("button", { name: "Napravi nalog", exact: true }).click();
  await expect(dialog.getByRole("alert")).toContainText("Nalog sa ovom email adresom već postoji");
  await expect(dialog.getByLabel("Email adresa")).toHaveValue("guest@example.com");
  await expect(dialog.getByLabel("Lozinka", { exact: true })).toHaveValue("Sample-secret-42!");
  await dialog.getByRole("button", { name: "Napravi nalog", exact: true }).click();
  await expect(dialog).toHaveCount(0);
  await page.locator(".profile-menu summary").click();
  await expect(page.getByRole("button", { name: "Odjavi se", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Odjavi se", exact: true }).click();
  await expect(page.getByRole("button", { name: "Prijava", exact: true })).toBeVisible();
});
