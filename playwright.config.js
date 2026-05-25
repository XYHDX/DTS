// @ts-check
/**
 * Playwright configuration for map tile canary tests.
 * DAM-451: canary guard for workerUrl regression and CDN version drift.
 */

const { defineConfig, devices } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './tests',
  testMatch: '**/*.spec.js',
  timeout: 30_000,
  retries: 0,
  workers: 1,
  reporter: 'list',

  use: {
    headless: true,
    // Block non-essential external resources to keep tests fast/reliable,
    // but allow tile CDNs so tile requests can actually be observed.
    bypassCSP: true,
  },

  webServer: {
    command: 'python3 -m http.server 7799 --directory public',
    port: 7799,
    reuseExistingServer: true,
    timeout: 15_000,
  },
});
