import { expect, test } from "./fixtures";

for (const mobile of [false, true]) {
  test(`security follows cross-tab sessions on ${mobile ? "mobile" : "desktop"}`, async ({ page, context }) => {
    if (mobile) await page.setViewportSize({ width: 390, height: 844 });
    await context.route("**/api/auth/me", route => {
      const token = route.request().headers().authorization;
      return token
        ? route.fulfill({ json: { id: token === "Bearer first" ? 1 : 2, email: token === "Bearer first" ? "first@example.com" : "second@example.com", role: "customer" } })
        : route.fulfill({ status: 401, json: { detail: "unauthorized" } });
    });
    let calls = 0;
    await context.route("**/api/auth/logout-all", route => { calls++; return route.fulfill({ status: 204 }); });
    await page.goto("/account/security");
    const other = await context.newPage();
    await other.goto("/help");
    await other.evaluate(() => localStorage.setItem("bookica_token", "first"));
    await expect(page.getByText("first@example.com", { exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Odjavi sve uređaje" }).click();
    await other.evaluate(() => localStorage.setItem("bookica_token", "second"));
    await expect(page.getByText("second@example.com", { exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Potvrdi odjavu svuda" })).toHaveCount(0);
    await expect(page.getByText("first@example.com", { exact: true })).toHaveCount(0);
    await other.evaluate(() => localStorage.removeItem("bookica_token"));
    await expect(page.getByRole("alert")).toContainText("Prijavi se");
    await expect(page.getByRole("button", { name: "Odjavi sve uređaje" })).toHaveCount(0);
    expect(calls).toBe(0);
  });

  test(`old revocation preserves a new session on ${mobile ? "mobile" : "desktop"}`, async ({ page }) => {
    if (mobile) await page.setViewportSize({ width: 390, height: 844 });
    await page.addInitScript(() => localStorage.setItem("bookica_token", "first"));
    await page.route("**/api/auth/me", route => route.fulfill({ json: { id: 1, email: "member@example.com", role: "customer" } }));
    let release!: () => void;
    const pending = new Promise<void>(resolve => { release = resolve; });
    await page.route("**/api/auth/logout-all", async route => {
      await pending;
      await route.fulfill({ status: 204 });
    });
    await page.goto("/account/security");
    await page.getByRole("button", { name: "Odjavi sve uređaje" }).click();
    const request = page.waitForRequest("**/api/auth/logout-all");
    await page.getByRole("button", { name: "Potvrdi odjavu svuda" }).click();
    await request;
    await page.evaluate(() => localStorage.setItem("bookica_token", "second"));
    release();
    await expect(page.getByRole("button", { name: "Odjavi sve uređaje" })).toBeVisible();
    expect(await page.evaluate(() => localStorage.getItem("bookica_token"))).toBe("second");
    await expect(page.getByText(/Sve sesije i API ključevi su poništeni/)).toHaveCount(0);
  });

  test(`revoke account sessions on ${mobile ? "mobile" : "desktop"}`, async ({ page }) => {
    if (mobile) await page.setViewportSize({ width: 390, height: 844 });
    await page.addInitScript(() => localStorage.setItem("bookica_token", "session"));
    let unavailable = true;
    await page.route("**/api/auth/me", route => unavailable
      ? route.fulfill({ status: 503, json: { detail: "unavailable" } })
      : route.fulfill({ json: { id: 1, email: "guest@example.com", role: "customer", email_verified: false } }));
    let calls = 0;
    await page.route("**/api/auth/logout-all", route => {
      expect(route.request().method()).toBe("POST");
      expect(route.request().headers().authorization).toBe("Bearer session");
      calls++;
      return route.fulfill({ status: 204 });
    });
    await page.goto("/account/security");
    await expect(page.getByRole("alert")).toContainText("Nalog nije učitan");
    await expect(page.getByRole("button", { name: "Odjavi sve uređaje" })).toHaveCount(0);
    unavailable = false;
    await page.getByRole("button", { name: "Pokušaj ponovo" }).click();
    await expect(page.getByRole("heading", { name: "Bezbednost naloga" })).toBeFocused();
    expect(await page.evaluate(() => localStorage.getItem("bookica_token"))).toBe("session");
    await page.getByRole("button", { name: "Odjavi sve uređaje" }).click();
    await expect(page.getByRole("button", { name: "Odustani" })).toBeFocused();
    await page.keyboard.press("Enter");
    await expect(page.getByRole("button", { name: "Odjavi sve uređaje" })).toBeFocused();
    expect(calls).toBe(0);
    await page.getByRole("button", { name: "Odjavi sve uređaje" }).click();
    await page.getByRole("button", { name: "Potvrdi odjavu svuda" }).click();
    await expect(page.getByRole("status")).toContainText("Sve sesije i API ključevi su poništeni");
    await expect(page.getByRole("heading", { name: "Bezbednost naloga" })).toBeFocused();
    expect(calls).toBe(1);
    expect(await page.evaluate(() => localStorage.getItem("bookica_token"))).toBeNull();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  });
}
