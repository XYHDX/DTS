// @ts-check
// Step 47 — driver flow Playwright test.
//
//   BASE_URL=http://localhost:8000 npx playwright test tests/driver_flow.spec.js

const { test, expect } = require('@playwright/test');
const AxeBuilder = require('@axe-core/playwright').default;

const BASE = process.env.BASE_URL || 'http://localhost:8000';

test.describe('Driver PWA — Claude-designed', () => {
  test('login pane renders by default', async ({ page }) => {
    await page.goto(`${BASE}/driver/`);
    await expect(page.getByText('دخول السائق')).toBeVisible();
    await expect(page.locator('#login-form #email')).toBeVisible();
    await expect(page.locator('#login-form #password')).toBeVisible();
  });

  test('failing login surfaces error inline', async ({ page }) => {
    await page.goto(`${BASE}/driver/`);
    await page.locator('#email').fill('not-a-real-user@example.com');
    await page.locator('#password').fill('wrongpassword');
    await page.locator('#login-form button[type="submit"]').click();
    // Either we get a backend error, or we're offline — both reveal #login-error
    await expect(page.locator('#login-error')).not.toHaveClass(/hidden/, {
      timeout: 5000,
    });
  });

  test('GPS pill and vehicle badge are present', async ({ page }) => {
    await page.goto(`${BASE}/driver/`);
    // Topbar pieces render regardless of login state
    await expect(page.locator('#gps-pill')).toBeVisible();
    await expect(page.locator('#bar-vehicle')).toBeVisible();
  });

  test('no serious axe-core violations on driver login', async ({ page }) => {
    await page.goto(`${BASE}/driver/`);
    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa'])
      .disableRules(['color-contrast'])
      .analyze();
    const serious = results.violations.filter(v =>
      v.impact === 'critical' || v.impact === 'serious');
    expect(serious, JSON.stringify(serious, null, 2)).toEqual([]);
  });
});
