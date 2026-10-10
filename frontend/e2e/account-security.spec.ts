import { expect, test } from "./fixtures";

for (const mobile of [false, true]) {
  test(`revoke account sessions on ${mobile ? "mobile" : "desktop"}`, async ({ page }) => {
    if (mobile) await page.setViewportSize({ width: 390, height: 844 });
    await page.addInitScript(() => localStorage.setItem("bookica_token", "session"));
    await page.route("**/api/auth/me", route => route.fulfill({ json: { id: 1, email: "guest@example.com", role: "customer", email_verified: false } }));
    let calls = 0;
    await page.route("**/api/auth/logout-all", route => {
      expect(route.request().method()).toBe("POST");
      expect(route.request().headers().authorization).toBe("Bearer session");
      calls++;
      return route.fulfill({ status: 204 });
    });
    await page.goto("/account/security");
    await page.getByRole("button", { name: "Odjavi sve uređaje" }).click();
    await page.getByRole("button", { name: "Odustani" }).click();
    expect(calls).toBe(0);
    await page.getByRole("button", { name: "Odjavi sve uređaje" }).click();
    await page.getByRole("button", { name: "Potvrdi odjavu svuda" }).click();
    await expect(page.getByRole("status")).toContainText("Sve sesije i API ključevi su poništeni");
    expect(calls).toBe(1);
    expect(await page.evaluate(() => localStorage.getItem("bookica_token"))).toBeNull();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  });
}
