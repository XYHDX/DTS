/**
 * Canary test: map pages actually issue tile requests after load.
 *
 * Regression guard for the workerUrl fix documented in public/index.html:
 *   "MapLibre v4 CDN fix: worker URL must be set explicitly; without it the
 *    worker blob URL fails to importScripts() the CDN bundle and the
 *    tile-fetching thread never starts (map canvas initialises fine but
 *    no tile requests are ever made)."
 *
 * Without this guard, removing the workerUrl assignment — or upgrading
 * maplibre-gl to a version where the CSP worker bundle path changes —
 * produces a blank map with NO visible error. This test catches that.
 *
 * DAM-451
 */

'use strict';

const { test, expect } = require('@playwright/test');

// Tile patterns per page.
// Each entry: { path, tilePattern, description }
// tilePattern is matched against the full request URL.
const MAP_PAGES = [
  {
    path: '/',
    tilePattern: /tile\.openstreetmap\.org\/\d+\/\d+\/\d+\.png/,
    description: 'hero map (index) — OSM raster tiles',
  },
  {
    path: '/driver',
    tilePattern: /basemaps\.cartocdn\.com\/.+\/\d+\/\d+\/\d+\.(png|pbf|mvt)/,
    description: 'driver page — CartoCDN vector tiles',
  },
  {
    path: '/passenger',
    tilePattern: /basemaps\.cartocdn\.com\/.+\/\d+\/\d+\/\d+\.(png|pbf|mvt)/,
    description: 'passenger page — CartoCDN vector tiles',
  },
];

const BASE_URL = process.env.CANARY_BASE_URL || 'http://localhost:7799';

// How long to wait (ms) for the first tile request after the map fires 'load'.
const TILE_WAIT_MS = 20_000;

for (const { path, tilePattern, description } of MAP_PAGES) {
  test(`tile requests fire: ${description}`, async ({ page }) => {
    // Collect all matching tile request URLs observed during the test.
    const tileRequests = [];
    page.on('request', (req) => {
      if (tilePattern.test(req.url())) {
        tileRequests.push(req.url());
      }
    });

    // Navigate to the page. waitUntil:'load' ensures the document and all
    // synchronous scripts have run (including the workerUrl assignment).
    await page.goto(`${BASE_URL}${path}`, { waitUntil: 'load' });

    // Wait up to TILE_WAIT_MS for at least one tile request to appear.
    // MapLibre starts fetching tiles when the 'load' event fires on the map
    // object, which follows the page load event by a short time.
    await expect
      .poll(
        () => tileRequests.length,
        {
          message:
            `No tile requests matching ${tilePattern} observed within ` +
            `${TILE_WAIT_MS / 1000}s of map load on ${path}. ` +
            `This likely means maplibregl.workerUrl was removed or the ` +
            `CDN bundle URL has drifted. Restore the workerUrl assignment ` +
            `(see public/index.html line ~822 and public/driver/index.html ` +
            `line ~669 and public/passenger/index.html line ~479).`,
          timeout: TILE_WAIT_MS,
          intervals: [250, 500, 1000],
        }
      )
      .toBeGreaterThan(0);

    // Surface the first tile URL in the output so regressions are easy to diagnose.
    console.log(`  [${path}] first tile: ${tileRequests[0]}`);
    console.log(`  [${path}] total tile requests captured: ${tileRequests.length}`);
  });
}
