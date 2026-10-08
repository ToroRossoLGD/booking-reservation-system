import { expect, test } from "@playwright/test";

for (const enabled of [false, true]) {
  test(`login offers only configured providers (Google: ${enabled})`, async ({ page }) => {
    await page.route("**/api/auth/me", route => route.fulfill({ status: 401, json: { detail: "Not signed in" } }));
    await page.route("**/api/venues", route => route.fulfill({ json: [] }));
    await page.route("**/api/promotions/active", route => route.fulfill({ json: [] }));
    await page.route("**/api/auth/providers", route => route.fulfill({ json: { google: enabled } }));
    await page.route("**/api/auth/google/login", route => route.fulfill({ contentType: "text/html", body: "<h1>OAuth navigation reached</h1>" }));
    await page.goto("/booking");
    const discovery = page.waitForResponse("**/api/auth/providers");
    await page.getByRole("button", { name: "Log in", exact: true }).click();
    await discovery;
    await expect(page.getByLabel("Email address")).toBeVisible();
    for (const name of ["LinkedIn", "Facebook", "X"]) {
      await expect(page.getByRole("button", { name: `Log in with ${name}`, exact: true })).toHaveCount(0);
    }
    const google = page.getByRole("button", { name: "Log in with Google" });
    if (enabled) {
      await expect(google).toBeVisible();
      await google.click();
      await expect(page).toHaveURL(/\/api\/auth\/google\/login$/);
      await expect(page.getByRole("heading", { name: "OAuth navigation reached" })).toBeVisible();
    } else {
      await expect(google).toHaveCount(0);
      await expect(page.getByText("or log in with email")).toHaveCount(0);
    }
  });
}
