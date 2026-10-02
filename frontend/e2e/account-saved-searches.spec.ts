import { expect, test } from "@playwright/test";

test("explicit transfer is available from a second browser without local storage", async ({ browser, baseURL }, testInfo) => {
  let saved: { id: number; name: string; path: string }[] = [];
  const first = await browser.newContext({ baseURL, viewport: { width: 390, height: 844 } });
  const second = await browser.newContext({ baseURL, viewport: { width: 390, height: 844 } });
  try {
    for (const context of [first, second]) {
      await context.addInitScript(() => localStorage.setItem("bookica_token", "same-account-token"));
      await context.route("**/api/properties?*", route => route.fulfill({ json: { items: [], total: 0, offset: 0, limit: 12, has_next: false } }));
      await context.route("**/api/saved-searches", route => {
        if (route.request().method() === "PUT") {
          saved = [{ ...route.request().postDataJSON(), id: 1 }];
          return route.fulfill({ json: saved[0] });
        }
        return route.fulfill({ json: saved });
      });
      await context.route("**/api/saved-searches/1", route => { saved = []; return route.fulfill({ status: 204 }); });
    }
    const page = await first.newPage();
    await page.goto("/?city=Novi+Sad&offer_type=long_term&rooms=0");
    await page.getByLabel("Naziv pretrage", { exact: true }).fill("Garsonjera");
    await page.getByRole("button", { name: "Sačuvaj trenutnu pretragu", exact: true }).click();
    await page.getByRole("button", { name: "Pretrage na nalogu", exact: true }).click();
    await expect(page.getByText("Još nema pretraga na nalogu.")).toBeVisible();
    expect(saved).toEqual([]);
    await page.getByRole("button", { name: "Sačuvaj na nalogu: Garsonjera" }).click();
    await expect(page.getByText("Pretraga je sačuvana na nalogu.")).toBeVisible();
    const remote = await second.newPage();
    await remote.goto("/");
    await remote.getByRole("button", { name: "Pretrage na nalogu", exact: true }).click();
    const panel = remote.getByRole("region", { name: "Pretrage na nalogu", exact: true });
    await expect(panel.getByRole("link", { name: "Garsonjera" })).toHaveAttribute("href", "/?city=Novi+Sad&offer_type=long_term&rooms=0");
    expect(await remote.evaluate(() => localStorage.getItem("bookica_saved_searches_v1"))).toBeNull();
    expect(await remote.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await panel.screenshot({ path: testInfo.outputPath("account-searches-mobile.png") });
    await panel.getByRole("button", { name: "Ukloni sa naloga: Garsonjera" }).click();
    await expect(panel.getByRole("link", { name: "Garsonjera" })).toHaveCount(0);
    await page.getByRole("button", { name: "Osveži pretrage na nalogu" }).click();
    await expect(page.getByText("Još nema pretraga na nalogu.")).toBeVisible();
    expect(await page.evaluate(() => JSON.parse(localStorage.getItem("bookica_saved_searches_v1")!))).toHaveLength(1);
  } finally { await first.close(); await second.close(); }
});
