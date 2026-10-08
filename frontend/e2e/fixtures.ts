import { test as base, expect } from "@playwright/test";

// Browser tests use mocked APIs; no backend listens on port 8000 here.
// Individual scenarios can override these defaults with page.route().
export const test = base.extend({
  page: async ({ page }, providePage) => {
    await page.route("**/api/runtime-config", route => route.fulfill({ json: { demo: false } }));
    await page.route("**/api/auth/providers", route => route.fulfill({ json: { google: false } }));
    await page.route(/\/api\/properties\/\d+\/views$/, route => {
      if (route.request().method() === "POST") return route.fulfill({ status: 204 });
      return route.fallback();
    });
    await providePage(page);
  },
});

export { expect };
