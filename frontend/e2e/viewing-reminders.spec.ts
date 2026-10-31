import { expect, test } from "./fixtures";

for (const path of ["/rentals", "/sales", "/owner/rentals", "/owner/sales"]) {
  test(`viewing reminders can be disabled and restored from ${path}`, async ({ page }) => {
    await page.setViewportSize({ width: path.includes("owner") ? 1280 : 390, height: 900 });
    let enabled = true;
    await page.route(/\/api\/(owner\/)?(rental|sale)-inquiries(\/mine)?\?/, route => route.fulfill({ json: { items: [], total: 0, has_next: false } }));
    await page.route("**/api/notifications/viewing-reminders", route => {
      if (route.request().method() === "PUT") enabled = route.request().postDataJSON().enabled;
      return route.fulfill({ json: { enabled } });
    });
    await page.goto(path);
    await page.getByRole("button", { name: "Podsetnici za razgledanja" }).click();
    await page.getByRole("button", { name: "Isključi podsetnike" }).click();
    await expect(page.getByText("Podsetnici su isključeni.")).toBeVisible();
    await page.reload();
    await page.getByRole("button", { name: "Podsetnici za razgledanja" }).click();
    await expect(page.getByText("Podsetnici su isključeni.")).toBeVisible();
    await page.getByRole("button", { name: "Uključi podsetnike" }).click();
    await expect(page.getByText("Podsetnici su uključeni.")).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  });
}
