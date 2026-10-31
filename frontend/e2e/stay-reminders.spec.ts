import { expect, test } from "./fixtures";

for (const width of [390, 1280]) {
  test(`personal stay reminder settings persist at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    let enabled = true;
    let reads = 0;
    await page.route("**/api/stays/mine?*", route => route.fulfill({ json: { items: [], total: 0, has_next: false } }));
    await page.route("**/api/notifications/stay-reminders", route => {
      if (route.request().method() === "PUT") enabled = route.request().postDataJSON().enabled;
      else reads++;
      return route.fulfill({ json: { enabled } });
    });
    await page.goto("/stays");
    expect(reads).toBe(0);
    await page.getByRole("button", { name: "Podsetnici za dolazak i odlazak" }).click();
    await page.getByRole("button", { name: "Isključi podsetnike" }).click();
    await expect(page.getByText("Podsetnici su isključeni.")).toBeVisible();
    await page.reload();
    await page.getByRole("button", { name: "Podsetnici za dolazak i odlazak" }).click();
    await expect(page.getByText("Podsetnici su isključeni.")).toBeVisible();
    await page.getByRole("button", { name: "Uključi podsetnike" }).click();
    await expect(page.getByText("Podsetnici su uključeni.")).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  });
}
