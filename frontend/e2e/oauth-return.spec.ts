import { expect, test } from "./fixtures";

test.beforeEach(async ({ page }) => {
  await page.route("**/api/properties?*", route => route.fulfill({ json: { items: [], total: 0, limit: 12, offset: 0, has_next: false } }));
  await page.route("**/api/venues", route => route.fulfill({ json: [] }));
  await page.route("**/api/promotions/active", route => route.fulfill({ json: [] }));
  await page.route("**/api/auth/me", route => route.fulfill({ status: 401, json: { detail: "Not signed in" } }));
});

for (const mobile of [false, true]) {
  test(`cancelled Google return is visible and offers email recovery on ${mobile ? "mobile" : "desktop"}`, async ({ page }) => {
    if (mobile) await page.setViewportSize({ width: 390, height: 664 });
    await page.goto("/#auth_error=Google%20login%20was%20cancelled");
    await expect(page.getByRole("alert")).toContainText("Google prijava je otkazana");
    await expect(page).toHaveURL(/\/$/);
    await expect(page.getByRole("button", { name: "Prijavi se pomoću Google naloga" })).toHaveCount(0);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.getByRole("link", { name: "Prijava email adresom" }).click();
    await expect(page).toHaveURL(/\/account$/);
    await page.getByRole("button", { name: mobile ? "Registracija" : "Prijava", exact: true }).click();
    if (mobile) await page.getByRole("button", { name: "Već imaš nalog? Prijavi se" }).click();
    await expect(page.getByRole("dialog", { name: "Pristup nalogu" })).toBeVisible();
    await expect(page.getByLabel("Email adresa")).toBeVisible();
    await expect(page.getByText("Google prijava je otkazana", { exact: false })).toHaveCount(0);
  });
}

test("expired state offers a fresh configured Google flow only after a click", async ({ page }) => {
  await page.route("**/api/auth/providers", route => route.fulfill({ json: { google: true } }));
  let starts = 0;
  await page.route("**/api/auth/google/login", route => {
    starts++;
    return route.fulfill({ contentType: "text/html", body: "<h1>New OAuth flow</h1>" });
  });
  await page.goto("/#auth_error=Invalid%20Google%20login%20state");
  await expect(page.getByRole("alert")).toContainText("istekla ili link više nije važeći");
  const google = page.getByRole("button", { name: "Prijavi se pomoću Google naloga" });
  await expect(google).toBeVisible();
  expect(starts).toBe(0);
  await google.click();
  await expect(page.getByRole("heading", { name: "New OAuth flow" })).toBeVisible();
  expect(starts).toBe(1);
});

test("unknown provider text is not displayed and dismissal preserves an existing session", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("bookica_token", "existing-session"));
  const diagnostic = '<script>secret-provider-diagnostic</script>';
  await page.goto(`/#auth_error=${encodeURIComponent(diagnostic)}`);
  await expect(page.getByRole("alert")).toHaveText("Google prijava nije uspela. Pokušaj ponovo ili koristi prijavu email adresom.");
  expect(await page.locator("body").innerText()).not.toContain("secret-provider-diagnostic");
  await expect(page).toHaveURL(/\/$/);
  await page.getByRole("button", { name: "Zatvori obaveštenje" }).click();
  await expect(page.getByRole("alert")).toHaveCount(0);
  expect(await page.evaluate(() => localStorage.getItem("bookica_token"))).toBe("existing-session");
  await page.reload();
  await expect(page.getByRole("heading", { name: /negde te čeka/i })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Google prijava", exact: true })).toHaveCount(0);
});
