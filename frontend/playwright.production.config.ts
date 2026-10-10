import { defineConfig, devices } from "@playwright/test";

// The production workflow starts the actual nginx image. API and map fixtures
// in the selected interaction tests remain mocked; CSP comes from real nginx.
export default defineConfig({
  testDir: ".",
  testMatch: [
    "e2e-production/**/*.spec.ts",
    "e2e/account-security.spec.ts",
    "e2e/email-verification.spec.ts",
    "e2e/password-recovery.spec.ts",
    "e2e/property-map.spec.ts",
    "e2e/owner-preview.spec.ts",
  ],
  workers: 2,
  use: { baseURL: "http://127.0.0.1:18080", trace: "retain-on-failure" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
