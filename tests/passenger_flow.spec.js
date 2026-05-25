// @ts-check
// Step 46 + 51 — passenger flow + axe-core accessibility assertion.
//
// Runs against the static `public/` build served by the FastAPI dev server.
//   BASE_URL=http://localhost:8000 npx playwright test tests/passenger_flow.spec.js

const { test, expect } = require('@playwright/test');
const AxeBuilder = require('@axe-core/playwright').default;

const BASE = process.env.BASE_URL || 'http://localhost:8000';

test.describe('Passenger PWA — Claude-designed', () => {
  test('landing renders RTL hero, stats, and live map', async ({ page }) => {
    await page.goto(`${BASE}/`);
    await expect(page.locator('html')).toHaveAttribute('dir', 'rtl');
    await expect(page.locator('html')).toHaveAttribute('lang', 'ar');

    // Hero headline is the prose-style line about real-time tracking
    await expect(page.getByText('تتبع حافلات دمشق في الوقت الحقيقي')).toBeVisible();

    // Stats grid mounts even before data arrives (skeletons present)
    await expect(page.locator('#stat-active')).toBeVisible();
    await expect(page.locator('#stat-routes')).toBeVisible();
    await expect(page.locator('#stat-stops')).toBeVisible();

    // The map container exists
    await expect(page.locator('#map')).toBeVisible();

    // Connection badge is rendered (success or danger depending on backend)
    await expect(page.locator('#conn-badge')).toBeVisible();
  });

  test('passenger PWA shell loads with bottom tab bar', async ({ page }) => {
    await page.goto(`${BASE}/passenger/`);
    await expect(page.getByText('أهلاً 👋')).toBeVisible();
    await expect(page.locator('.tabbar')).toBeVisible();
    // Search input is focusable
    const search = page.locator('#q');
    await search.focus();
    await search.fill('مزة');
    await expect(search).toHaveValue('مزة');
  });

  test('lang toggle flips dir and lang attributes', async ({ page }) => {
    await page.goto(`${BASE}/`);
    await page.locator('#lang-toggle').click();
    await expect(page.locator('html')).toHaveAttribute('lang', 'en');
    await expect(page.locator('html')).toHaveAttribute('dir', 'ltr');
    await page.locator('#lang-toggle').click();
    await expect(page.locator('html')).toHaveAttribute('lang', 'ar');
    await expect(page.locator('html')).toHaveAttribute('dir', 'rtl');
  });

  test('landing page has no serious axe-core violations', async ({ page }) => {
    await page.goto(`${BASE}/`);
    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'best-practice'])
      .disableRules(['color-contrast'])  // covered by Lighthouse CI separately
      .analyze();
    const serious = results.violations.filter(v =>
      v.impact === 'critical' || v.impact === 'serious');
    expect(serious, JSON.stringify(serious, null, 2)).toEqual([]);
  });

  test('passenger PWA has no serious axe-core violations', async ({ page }) => {
    await page.goto(`${BASE}/passenger/`);
    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa'])
      .disableRules(['color-contrast'])
      .analyze();
    const serious = results.violations.filter(v =>
      v.impact === 'critical' || v.impact === 'serious');
    expect(serious, JSON.stringify(serious, null, 2)).toEqual([]);
  });
});
