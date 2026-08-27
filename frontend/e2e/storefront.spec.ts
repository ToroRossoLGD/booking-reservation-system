import { expect, test } from "@playwright/test";

test("storefront and authentication dialog remain usable", async ({ page }) => {
  await page.goto("/");

  await expect(
    page.getByRole("heading", { name: /the right space/i }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(
    page.getByRole("heading", { name: /good to see you again/i }),
  ).toBeVisible();
  await expect(page.getByLabel("Email address")).toBeVisible();
});
