import { expect, test } from "@playwright/test";

test("property storefront links to the existing booking and authentication flow", async ({ page }) => {
  await page.goto("/");

  await expect(
    page.getByRole("heading", { name: /negde te čeka/i }),
  ).toBeVisible();
  await page.getByRole("link", { name: /postojeći sistem rezervacija/i }).click();
  await expect(page).toHaveURL(/\/booking$/);

  await expect(
    page.getByRole("heading", { name: /the right space/i }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(
    page.getByRole("heading", { name: /good to see you again/i }),
  ).toBeVisible();
  await expect(page.getByLabel("Email address")).toBeVisible();
});
