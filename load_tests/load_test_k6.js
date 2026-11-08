import http from 'k6/http';
import { check, sleep, group } from 'k6';

export const options = {
  stages: [
    { duration: '10s', target: 5 },  // Ramp-up to 5 users
    { duration: '20s', target: 15 }, // Peak load 15 users
    { duration: '10s', target: 0 },  // Ramp-down to 0
  ],
  thresholds: {
    http_req_duration: ['p(95)<500'], // 95% of requests must complete below 500ms
    http_req_failed: ['rate<0.01'],   // Error rate must remain under 1%
  },
};

const BASE_URL = __ENV.TARGET_URL || 'http://127.0.0.1:8000';
const PARTS = ['PMP-0001', 'PMP-0010', 'PMP-0290', 'PMP-0050'];

function generateW3CHeaders() {
  const traceId = '4bf92f3577b34da6a3ce929d0e0e4736';
  const spanId = '00f067aa0ba902b7';
  return {
    'Content-Type': 'application/json',
    'traceparent': `00-${traceId}-${spanId}-01`,
    'X-Request-ID': `k6-run-${Date.now()}`,
  };
}

export default function () {
  const headers = generateW3CHeaders();

  group('Part Catalog Search & Retrieval', function () {
    const res = http.get(`${BASE_URL}/parts?query=pump&page=1`, { headers });
    check(res, { 'parts search status 200': (r) => r.status === 200 });

    const part = PARTS[Math.floor(Math.random() * PARTS.length)];
    const detailRes = http.get(`${BASE_URL}/parts/${part}`, { headers });
    check(detailRes, { 'part detail status 200': (r) => r.status === 200 });
  });

  group('BOM Exploration & Compare', function () {
    const bomRes = http.get(`${BASE_URL}/parts/PMP-0001/bom?levels=2`, { headers });
    check(bomRes, { 'bom tree status 200': (r) => r.status === 200 });

    const comparePayload = JSON.stringify({
      assembly_a: 'PMP-0001',
      assembly_b: 'PMP-0002',
    });
    const compareRes = http.post(`${BASE_URL}/bom/compare`, comparePayload, { headers });
    check(compareRes, { 'bom compare status 200': (r) => r.status === 200 });
  });

  group('Change Impact Analysis', function () {
    const impactPayload = JSON.stringify({ part_number: 'PMP-0010' });
    const impactRes = http.post(`${BASE_URL}/impact`, impactPayload, { headers });
    check(impactRes, { 'impact analysis status 200': (r) => r.status === 200 });
  });

  group('AI Assistant Chat', function () {
    const chatPayload = JSON.stringify({
      message: 'What is the blast radius impact of part PMP-0010?',
      history: [],
    });
    const chatRes = http.post(`${BASE_URL}/chat`, chatPayload, { headers });
    check(chatRes, { 'chat streaming status 200': (r) => r.status === 200 });
  });

  group('Closed-Loop Lifecycle Scenario', function () {
    const dtRes = http.get(`${BASE_URL}/digital-thread/PMP-0290`, { headers });
    check(dtRes, { 'digital thread status 200': (r) => r.status === 200 });

    const draftPayload = JSON.stringify({
      title: 'k6 Automated ECR for PMP-0290 Bearing',
      reason: 'Remediating bearing vibration anomaly DEF-2025-0042',
      category: 'DESIGN_IMPROVEMENT',
      priority: 'HIGH',
      affected_parts: ['PMP-0290'],
    });
    const draftRes = http.post(`${BASE_URL}/changes/draft`, draftPayload, { headers });
    check(draftRes, { 'draft ECR status 200': (r) => r.status === 200 });

    if (draftRes.status === 200) {
      const draftId = draftRes.json('draft_id');
      if (draftId) {
        const confirmRes = http.post(`${BASE_URL}/changes/${draftId}/confirm`, null, { headers });
        check(confirmRes, { 'confirm ECR status 200 or 201': (r) => r.status === 200 || r.status === 201 });
      }
    }
  });

  sleep(1);
}
