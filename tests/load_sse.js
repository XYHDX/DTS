// k6 load test — SSE endpoint /api/stream.
//
// Run locally:
//   k6 run -e BASE_URL=https://syrian-transit-system.vercel.app tests/load_sse.js
//
// Run with profile:
//   k6 run -e PROFILE=spike tests/load_sse.js
//
// What it does:
//   Ramps a wave of virtual users connecting to the SSE feed. Each VU holds
//   the connection for 30 seconds and counts the number of `vehicles` events
//   it receives. Asserts that connections succeed and that the median client
//   sees at least one event per second.

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Counter, Rate, Trend } from 'k6/metrics';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const PROFILE  = __ENV.PROFILE || 'soak';

const eventsCounter = new Counter('sse_events_received');
const connectOk     = new Rate('sse_connect_ok');
const eventsPerSec  = new Trend('sse_events_per_second');

const profiles = {
  smoke: {
    vus: 5,
    duration: '30s',
  },
  soak: {
    stages: [
      { duration: '30s', target: 20 },
      { duration: '2m',  target: 20 },
      { duration: '30s', target: 0  },
    ],
  },
  spike: {
    stages: [
      { duration: '10s', target: 5  },
      { duration: '20s', target: 100 },
      { duration: '40s', target: 100 },
      { duration: '10s', target: 0  },
    ],
  },
};

export const options = {
  ...profiles[PROFILE],
  thresholds: {
    sse_connect_ok:    ['rate>0.97'],   // ≥97% of connects must succeed
    http_req_failed:   ['rate<0.05'],   // <5% transport failures
    sse_events_per_second: ['p(50)>1'], // median client sees at least 1/sec
  },
};

export default function () {
  const HOLD_SECONDS = 30;
  const url = `${BASE_URL}/api/stream`;

  // k6 doesn't ship native SSE — use a streaming HTTP GET and parse frames.
  const params = {
    headers: { Accept: 'text/event-stream' },
    timeout: `${HOLD_SECONDS + 5}s`,
  };
  const start = Date.now();
  const res = http.get(url, params);
  const elapsed = (Date.now() - start) / 1000;

  const ok = res.status === 200 &&
             /text\/event-stream/.test(res.headers['Content-Type'] || '');
  connectOk.add(ok);

  if (!ok) {
    check(res, { 'connect 200 + text/event-stream': r => false });
    sleep(1);
    return;
  }

  // Count "event: vehicles" occurrences in the buffered body.
  const body = res.body || '';
  const count = (body.match(/^event:\s*vehicles/gm) || []).length;
  eventsCounter.add(count);
  eventsPerSec.add(count / Math.max(1, elapsed));

  check(res, {
    'received >=1 vehicles event': () => count >= 1,
  });

  sleep(1);
}

export function handleSummary(data) {
  const out = JSON.stringify(data.metrics, null, 2);
  return {
    'stdout': `\nSSE load summary (${PROFILE})\n=========================\n${out}\n`,
  };
}
