import { expect, test } from "./fixtures";

for (const mobile of [false, true]) {
  test(`verification status refresh recovers and detects another tab on ${mobile ? "mobile" : "desktop"}`, async ({ page }) => {
    if (mobile) await page.setViewportSize({ width: 390, height: 844 });
    let state: "error" | "unverified" | "verified" | "guest" = "error";
    let sends = 0;
    await page.route("**/api/auth/me", route => state === "error" || state === "guest"
      ? route.fulfill({ status: state === "guest" ? 401 : 503, json: { detail: "unavailable" } })
      : route.fulfill({ json: { id: 5, email: "guest@example.com", role: "customer", email_verified: state === "verified" } }));
    await page.route("**/api/auth/email-verification/request", route => { sends++; return route.fulfill({ json: { message: "generic" } }); });
    await page.goto("/verify-email");
    await expect(page.getByRole("alert")).toContainText("Nalog nije učitan");
    const refresh = page.getByRole("button", { name: "Proveri status potvrde" });
    state = "unverified";
    await refresh.click();
    const resend = page.getByRole("button", { name: "Pošalji novi link" });
    await expect(resend).toBeEnabled();
    expect(sends).toBe(0);
    await resend.click();
    await expect(resend).toBeDisabled();
    await refresh.click();
    await expect(resend).toBeDisabled();
    expect(sends).toBe(1);
    state = "verified";
    await refresh.click();
    await expect(page.getByRole("status")).toContainText("Email adresa je potvrđena");
    await expect(resend).toHaveCount(0);
    await expect(refresh).toBeFocused();
    state = "guest";
    await refresh.click();
    await expect(page.getByText("Prijavite se da zatražite novi link za svoj nalog.")).toBeVisible();
    await expect(resend).toHaveCount(0);
    expect(sends).toBe(1);
  });
}

test("resend respects server cooldown without automatically sending again", async ({ page }) => {
  await page.route("**/api/auth/me", route => route.fulfill({ json: { id: 5, email: "guest@example.com", role: "customer", email_verified: false } }));
  let requests = 0;
  await page.route("**/api/auth/email-verification/request", route => {
    requests++;
    return requests === 1
      ? route.fulfill({ status: 429, headers: { "Retry-After": "120" }, json: { detail: "limited" } })
      : route.fulfill({ json: { message: "generic" } });
  });
  await page.goto("/verify-email");
  await page.clock.install();
  const resend = page.getByRole("button", { name: "Pošalji novi link" });
  await resend.click();
  await expect(page.getByRole("alert")).toContainText("120 sekundi");
  await page.clock.fastForward(60000);
  await expect(resend).toBeDisabled();
  await page.clock.fastForward(60000);
  await expect(resend).toBeEnabled();
  expect(requests).toBe(1);
  await resend.click();
  await expect(page.getByRole("alert")).toHaveCount(0);
  await expect(resend).toBeDisabled();
  expect(requests).toBe(2);
});

for (const mobile of [false, true]) {
  test(`email verification on ${mobile ? "mobile" : "desktop"}`, async ({ page }) => {
    if (mobile) await page.setViewportSize({ width: 390, height: 844 });
    await page.route("**/api/auth/me", route => route.fulfill({ json: { id: 5, email: "guest@example.com", role: "customer", email_verified: false } }));
    let requests = 0;
    await page.route("**/api/auth/email-verification/request", route => { requests++; return route.fulfill({ json: { message: "generic" } }); });
    const token = "a".repeat(43);
    let confirmations = 0;
    await page.route("**/api/auth/email-verification/confirm", route => {
      expect(route.request().postDataJSON()).toEqual({ token });
      confirmations++;
      return route.fulfill({ json: { message: "ok" } });
    });
    await page.goto("/verify-email");
    await page.clock.install();
    await page.getByRole("button", { name: "Pošalji novi link" }).click();
    await expect(page.getByRole("status")).toContainText("spam folder");
    await expect(page.getByRole("button", { name: "Pošalji novi link" })).toBeDisabled();
    await page.clock.fastForward(59000);
    await expect(page.getByRole("button", { name: "Pošalji novi link" })).toBeDisabled();
    expect(requests).toBe(1);
    await page.clock.fastForward(1000);
    await expect(page.getByText("Možete ponovo zatražiti link.")).toBeVisible();
    await page.getByRole("button", { name: "Pošalji novi link" }).click();
    await expect(page.getByRole("button", { name: "Pošalji novi link" })).toBeDisabled();
    expect(requests).toBe(2);
    await page.goto(`/verify-email${mobile ? "/" : ""}#token=${token}`);
    await expect(page).toHaveURL(/\/verify-email\/?$/);
    expect(confirmations).toBe(0);
    await page.getByRole("button", { name: "Potvrdi email" }).click();
    await expect(page.getByRole("status")).toContainText("Email adresa je potvrđena");
    expect(confirmations).toBe(1);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  });
}
