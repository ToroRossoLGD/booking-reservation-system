import { expect, test } from "@playwright/test";

test("real OAuth callback budget returns a safe mobile page and clears stale state", async ({ page, context, request }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  // No state cookie: these requests cannot reach Google's token endpoint.
  // Varying query parameters and spoofed IP headers must not refresh the budget.
  for (let index = 0; index < 20; index++) {
    const response = await request.get(`/api/auth/google/callback?code=ci-private-${index}&state=ci-state-${index}`, {
      maxRedirects: 0, headers: { "X-Forwarded-For": `192.0.2.${index + 1}` },
    });
    expect(response.status()).toBe(307);
    expect(response.headers().location).toContain("#auth_error=");
    expect(response.headers().location).not.toContain("ci-private");
  }
  await context.addCookies([{ name: "google_oauth_state", value: "stale-test-state", domain: "127.0.0.1", path: "/api/auth/google", httpOnly: true, secure: true, sameSite: "Lax" }]);
  expect((await context.cookies()).some(cookie => cookie.name === "google_oauth_state")).toBe(true);
  const response = await page.goto("/api/auth/google/callback?code=ci-private&state=ci-state");
  expect(response?.status()).toBe(429);
  expect(Number(response?.headers()["retry-after"])).toBeGreaterThan(0);
  expect(response?.headers()["cache-control"]).toBe("no-store");
  expect(await response?.headerValue("set-cookie")).toContain("Path=/api/auth/google");
  await expect(page.getByRole("alert")).toContainText("Previše pokušaja Google prijave");
  await expect(page.locator("body")).not.toContainText("ci-private");
  await expect(page.locator("body")).not.toContainText("ci-state");
  expect((await context.cookies()).some(cookie => cookie.name === "google_oauth_state")).toBe(false);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  let referer: string | undefined = "not visited";
  await page.route("https://bookica.test/account", route => {
    referer = route.request().headers().referer;
    return route.fulfill({ contentType: "text/html", body: "<h1>Prijava</h1>" });
  });
  await page.getByRole("link", { name: "Vrati se na prijavu" }).click();
  await expect(page.getByRole("heading", { name: "Prijava" })).toBeVisible();
  expect(referer).toBeUndefined();
});
