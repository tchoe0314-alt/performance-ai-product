import { expect, test, type APIRequestContext } from "@playwright/test";

const DEFAULT_API_URL = "https://api.civoraai.com";
const email = process.env.CIVORA_EMAIL || "";
const password = process.env.CIVORA_PASSWORD || "";
const apiBaseUrl = (process.env.PLAYWRIGHT_API_BASE_URL || process.env.NEXT_PUBLIC_API_BASE_URL || DEFAULT_API_URL).replace(/\/+$/, "");

type LoadResult = {
  label: string;
  status: number;
  ok: boolean;
  ms: number;
  body: string;
};

async function login(request: APIRequestContext) {
  const response = await request.post(`${apiBaseUrl}/api/auth/login`, {
    data: { email, password },
  });
  expect(response.status(), "hosted login should succeed").toBe(200);
  const payload = (await response.json()) as { token?: string };
  const token = String(payload.token || "");
  expect(token, "hosted login returned a bearer token").toBeTruthy();
  return token;
}

async function runPool<T>(items: T[], limit: number, worker: (item: T) => Promise<void>) {
  let cursor = 0;
  const workers = Array.from({ length: limit }, async () => {
    while (cursor < items.length) {
      const index = cursor;
      cursor += 1;
      await worker(items[index]);
    }
  });
  await Promise.all(workers);
}

async function timed(label: string, request: APIRequestContext, url: string, expectedStatus: number, headers?: Record<string, string>): Promise<LoadResult> {
  const started = Date.now();
  try {
    const response = await request.get(url, { headers });
    const body = (await response.text()).slice(0, 180);
    return {
      label,
      status: response.status(),
      ok: response.status() === expectedStatus,
      ms: Date.now() - started,
      body,
    };
  } catch (error) {
    return {
      label,
      status: 0,
      ok: false,
      ms: Date.now() - started,
      body: String(error instanceof Error ? error.message : error).slice(0, 180),
    };
  }
}

function percentile(values: number[], ratio: number) {
  const sorted = [...values].sort((left, right) => left - right);
  return sorted[Math.min(sorted.length - 1, Math.max(0, Math.floor(sorted.length * ratio)))];
}

test.describe("hosted load stability", () => {
  test("handles below-limit concurrent read traffic without bad statuses or severe latency", async ({ request }) => {
    test.skip(!email || !password, "CIVORA_EMAIL and CIVORA_PASSWORD are required for hosted load stability proof.");

    const token = await login(request);
    await expect
      .poll(async () => (await request.get(`${apiBaseUrl}/api/debug/runtime`, { headers: { Authorization: `Bearer ${token}` } })).status(), {
        timeout: 30_000,
        message: "hosted runtime should be warm before load proof",
      })
      .toBe(200);
    await expect
      .poll(async () => (await request.get(`${apiBaseUrl}/api/health`)).status(), {
        timeout: 70_000,
        intervals: [1000, 2000, 5000],
        message: "health bucket should be available before below-limit load proof",
      })
      .toBe(200);
    await expect
      .poll(async () => (await request.get(`${apiBaseUrl}/api/auth/status`)).status(), {
        timeout: 70_000,
        intervals: [1000, 2000, 5000],
        message: "auth bucket should be available before below-limit load proof",
      })
      .toBe(200);

    const tasks: Array<{ label: string; url: string; expected: number; headers?: Record<string, string> }> = [];
    for (let index = 0; index < 90; index += 1) {
      tasks.push({ label: `health-${index}`, url: `${apiBaseUrl}/api/health`, expected: 200 });
    }
    for (let index = 0; index < 20; index += 1) {
      tasks.push({ label: `auth-${index}`, url: `${apiBaseUrl}/api/auth/status`, expected: 200, headers: { Authorization: `Bearer ${token}` } });
    }
    for (let index = 0; index < 180; index += 1) {
      tasks.push({ label: `jobs-${index}`, url: `${apiBaseUrl}/api/jobs`, expected: 200, headers: { Authorization: `Bearer ${token}` } });
    }
    for (let index = 0; index < 30; index += 1) {
      tasks.push({ label: `unauth-jobs-${index}`, url: `${apiBaseUrl}/api/jobs`, expected: 401 });
    }

    const results: LoadResult[] = [];
    const started = Date.now();
    await runPool(tasks, 35, async (task) => {
      results.push(await timed(task.label, request, task.url, task.expected, task.headers));
    });
    const wallMs = Date.now() - started;
    const bad = results.filter((result) => !result.ok);
    const p95 = percentile(
      results.map((result) => result.ms),
      0.95,
    );
    const max = Math.max(...results.map((result) => result.ms));
    console.log(JSON.stringify({ total: results.length, badCount: bad.length, p95Ms: p95, maxMs: max, wallMs }, null, 2));

    expect(bad.slice(0, 5)).toEqual([]);
    expect(results).toHaveLength(320);
    expect(p95, "hosted p95 latency under bounded read concurrency").toBeLessThan(2500);
    expect(max, "hosted max latency under bounded read concurrency").toBeLessThan(10_000);
  });

  test("throttles over-limit auth bursts gracefully instead of failing open or returning 5xx", async ({ request }) => {
    test.skip(!email || !password, "CIVORA_EMAIL and CIVORA_PASSWORD are required for hosted load stability proof.");

    await expect
      .poll(async () => (await request.get(`${apiBaseUrl}/api/auth/status`)).status(), {
        timeout: 70_000,
        intervals: [1000, 2000, 5000],
        message: "auth bucket should be available before burst-throttle proof",
      })
      .toBe(200);

    const tasks = Array.from({ length: 45 }, (_, index) => ({
      label: `auth-burst-${index}`,
      url: `${apiBaseUrl}/api/auth/status`,
      expected: 200,
    }));
    const results: LoadResult[] = [];
    await runPool(tasks, 45, async (task) => {
      results.push(await timed(task.label, request, task.url, task.expected));
    });
    const throttled = results.filter((result) => result.status === 429);
    const unexpected = results.filter((result) => ![200, 429].includes(result.status));
    const p95 = percentile(
      results.map((result) => result.ms),
      0.95,
    );
    console.log(JSON.stringify({ total: results.length, throttled: throttled.length, unexpected: unexpected.length, p95Ms: p95 }, null, 2));

    expect(unexpected).toEqual([]);
    expect(throttled.length, "auth burst above configured 30/minute limit should be throttled").toBeGreaterThan(0);
    expect(throttled.every((result) => /Rate limit exceeded for auth/i.test(result.body))).toBe(true);
    expect(p95, "hosted p95 latency while throttling auth bursts").toBeLessThan(2500);
  });
});
