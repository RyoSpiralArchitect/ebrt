import assert from "node:assert/strict";
import test from "node:test";

import worker from "./index.js";

const textEncoder = new TextEncoder();
const secrets = {
  EBRT_BACKEND_URL: "https://backend.example/",
  EBRT_CLIENT_KEY_SECRET: "client-key-secret-for-worker-tests",
  EBRT_RELAY_TOKEN: "relay-token-for-worker-tests",
};

async function digest(bytes) {
  const value = await crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(value)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

async function sealedResponse(value, init = {}) {
  const body = textEncoder.encode(`${JSON.stringify(value)}\n`);
  return new Response(body, {
    status: init.status ?? 200,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "X-EBRT-Body-SHA256": await digest(body),
      ...(init.headers ?? {}),
    },
  });
}

async function assertHashedError(response, status, code) {
  assert.equal(response.status, status);
  const bytes = new Uint8Array(await response.arrayBuffer());
  assert.equal(response.headers.get("X-EBRT-Body-SHA256"), await digest(bytes));
  const value = JSON.parse(new TextDecoder().decode(bytes));
  assert.equal(value.error.code, code);
  assert.deepEqual(Object.keys(value.error), ["code"]);
  assert.equal(response.headers.get("Cache-Control"), "no-store");
}

test("non-API requests delegate unchanged to ASSETS", async () => {
  const request = new Request("https://site.example/index.html");
  let observed;
  const response = await worker.fetch(request, {
    ASSETS: {
      fetch(candidate) {
        observed = candidate;
        return new Response("asset");
      },
    },
  });
  assert.equal(observed, request);
  assert.equal(await response.text(), "asset");
});

test("API route and method allowlists fail closed with hashed JSON", async () => {
  await assertHashedError(
    await worker.fetch(new Request("https://site.example/api/unknown"), secrets),
    404,
    "ROUTE_NOT_FOUND",
  );
  const response = await worker.fetch(
    new Request("https://site.example/api/health", { method: "POST", body: "{}" }),
    secrets,
  );
  await assertHashedError(response, 405, "METHOD_NOT_ALLOWED");
  assert.equal(response.headers.get("Allow"), "GET");
});

test("GET proxy strips browser credentials and derives an opaque client key", async () => {
  const originalFetch = globalThis.fetch;
  let observed;
  globalThis.fetch = async (input, init) => {
    observed = { input, init };
    return sealedResponse({ status: "READY" });
  };
  try {
    const response = await worker.fetch(
      new Request("https://site.example/api/health", {
        headers: {
          Authorization: "Bearer browser-secret",
          Cookie: "session=browser-secret",
          "CF-Connecting-IP": "2001:db8::1",
          "X-EBRT-Client-Key": "attacker-client-key",
          "X-EBRT-Relay-Token": "attacker-relay-token",
        },
      }),
      secrets,
    );
    assert.equal(response.status, 200);
    assert.equal(observed.input.href, "https://backend.example/api/health");
    assert.equal(observed.init.redirect, "manual");
    assert.equal(observed.init.cache, "no-store");
    assert.equal(observed.init.headers.get("Authorization"), null);
    assert.equal(observed.init.headers.get("Cookie"), null);
    assert.equal(observed.init.headers.get("X-EBRT-Relay-Token"), secrets.EBRT_RELAY_TOKEN);
    assert.match(observed.init.headers.get("X-EBRT-Client-Key"), /^[0-9a-f]{64}$/u);
    assert.notEqual(observed.init.headers.get("X-EBRT-Client-Key"), "attacker-client-key");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("POST proxy preserves request and response bytes plus idempotency", async () => {
  const originalFetch = globalThis.fetch;
  const requestBody =
    '{"schema_version":"ebrt-live-apply-revision-request-v0.6.2.5","request_id":"request-1","case_id":"sealed-case","number":1.00}\n';
  const upstreamBody = textEncoder.encode('{"status":"OK","number":1.00}\n');
  const upstreamHash = await digest(upstreamBody);
  let observed;
  let fetchCalls = 0;
  globalThis.fetch = async (input, init) => {
    fetchCalls += 1;
    if (new URL(input).pathname === "/api/demo-request") {
      return sealedResponse({
        request: {
          schema_version: "ebrt-live-apply-revision-request-v0.6.2.5",
          request_id: "template-request",
          case_id: "sealed-case",
          number: 1,
        },
      });
    }
    observed = init;
    return new Response(upstreamBody, {
      status: 200,
      headers: {
        "Content-Type": "application/json; charset=utf-8",
        "X-EBRT-Body-SHA256": upstreamHash,
        "X-EBRT-Idempotent-Replay": "true",
      },
    });
  };
  try {
    const response = await worker.fetch(
      new Request("https://site.example/api/apply-revision", {
        method: "POST",
        headers: {
          "CF-Connecting-IP": "203.0.113.9",
          "Content-Type": "application/json; charset=utf-8",
          "Idempotency-Key": "request-1",
        },
        body: requestBody,
      }),
      secrets,
    );
    assert.equal(new TextDecoder().decode(observed.body), requestBody);
    assert.equal(fetchCalls, 2);
    assert.equal(observed.headers.get("Idempotency-Key"), "request-1");
    assert.deepEqual(new Uint8Array(await response.arrayBuffer()), upstreamBody);
    assert.equal(response.headers.get("X-EBRT-Body-SHA256"), upstreamHash);
    assert.equal(response.headers.get("X-EBRT-Idempotent-Replay"), "true");
    assert.equal(response.headers.get("Cache-Control"), "no-store");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("oversized requests and backend failures return sanitized hashed errors", async () => {
  let fetchCalls = 0;
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => {
    fetchCalls += 1;
    throw new Error("sensitive backend detail");
  };
  try {
    const oversized = await worker.fetch(
      new Request("https://site.example/api/apply-revision", {
        method: "POST",
        headers: {
          "CF-Connecting-IP": "203.0.113.10",
          "Content-Type": "application/json",
          "Content-Length": String(256 * 1024 + 1),
          "Idempotency-Key": "request-large",
        },
        body: "{}",
      }),
      secrets,
    );
    await assertHashedError(oversized, 413, "REQUEST_BODY_TOO_LARGE");
    assert.equal(fetchCalls, 0);

    const failed = await worker.fetch(
      new Request("https://site.example/api/health", {
        headers: { "CF-Connecting-IP": "203.0.113.10" },
      }),
      secrets,
    );
    const failedClone = failed.clone();
    await assertHashedError(failed, 502, "LIVE_BACKEND_UNAVAILABLE");
    assert.doesNotMatch(await failedClone.text(), /sensitive/u);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("public POST rejects any request that differs from the fresh sealed demo", async () => {
  const originalFetch = globalThis.fetch;
  let fetchCalls = 0;
  globalThis.fetch = async (input) => {
    fetchCalls += 1;
    assert.equal(new URL(input).pathname, "/api/demo-request");
    return sealedResponse({
      request: {
        schema_version: "ebrt-live-apply-revision-request-v0.6.2.5",
        request_id: "template-id",
        case_id: "sealed-case",
        evidence: [{ evidence_id: "R1", text: "sealed" }],
      },
    });
  };
  try {
    const response = await worker.fetch(
      new Request("https://site.example/api/apply-revision", {
        method: "POST",
        headers: {
          "CF-Connecting-IP": "203.0.113.12",
          "Content-Type": "application/json",
          "Idempotency-Key": "attacker-id",
        },
        body: JSON.stringify({
          schema_version: "ebrt-live-apply-revision-request-v0.6.2.5",
          request_id: "attacker-id",
          case_id: "sealed-case",
          evidence: [{ evidence_id: "R1", text: "modified" }],
        }),
      }),
      secrets,
    );
    await assertHashedError(response, 403, "PUBLIC_DEMO_REQUEST_REQUIRED");
    assert.equal(fetchCalls, 1);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("redirects and response hash mismatches are never relayed", async () => {
  const originalFetch = globalThis.fetch;
  try {
    globalThis.fetch = async () =>
      new Response(null, { status: 302, headers: { Location: "https://unexpected.example" } });
    await assertHashedError(
      await worker.fetch(
        new Request("https://site.example/api/health", {
          headers: { "CF-Connecting-IP": "203.0.113.11" },
        }),
        secrets,
      ),
      502,
      "LIVE_BACKEND_REDIRECT_REFUSED",
    );

    globalThis.fetch = async () =>
      new Response("{}\n", {
        headers: { "X-EBRT-Body-SHA256": "0".repeat(64) },
      });
    await assertHashedError(
      await worker.fetch(
        new Request("https://site.example/api/health", {
          headers: { "CF-Connecting-IP": "203.0.113.11" },
        }),
        secrets,
      ),
      502,
      "LIVE_BACKEND_INTEGRITY_FAILURE",
    );
  } finally {
    globalThis.fetch = originalFetch;
  }
});
