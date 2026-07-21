const MAX_REQUEST_BYTES = 256 * 1024;
const BODY_SHA256_HEADER = "X-EBRT-Body-SHA256";
const IDEMPOTENT_REPLAY_HEADER = "X-EBRT-Idempotent-Replay";
const RELAY_TOKEN_HEADER = "X-EBRT-Relay-Token";
const CLIENT_KEY_HEADER = "X-EBRT-Client-Key";
const ERROR_SCHEMA = "ebrt-sites-relay-error-v0.1";

const API_ROUTES = new Map([
  ["/api/health", "GET"],
  ["/api/capabilities", "GET"],
  ["/api/demo-request", "GET"],
  ["/api/apply-revision", "POST"],
]);

class RelayError extends Error {
  constructor(code, status) {
    super(code);
    this.name = "RelayError";
    this.code = code;
    this.status = status;
  }
}

function bytesToHex(bytes) {
  return [...bytes].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

async function sha256(bytes) {
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return bytesToHex(new Uint8Array(digest));
}

function responseHeaders(bodySha256) {
  return new Headers({
    "Cache-Control": "no-store",
    "Content-Security-Policy": "default-src 'none'",
    "Content-Type": "application/json; charset=utf-8",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Referrer-Policy": "no-referrer",
    [BODY_SHA256_HEADER]: bodySha256,
    "X-Content-Type-Options": "nosniff",
  });
}

async function errorResponse(status, code, extraHeaders = undefined) {
  const body = new TextEncoder().encode(
    `${JSON.stringify({
      schema_version: ERROR_SCHEMA,
      status: "ERROR",
      error: { code },
    })}\n`,
  );
  const headers = responseHeaders(await sha256(body));
  headers.set("Content-Length", String(body.byteLength));
  if (extraHeaders) {
    for (const [name, value] of Object.entries(extraHeaders)) headers.set(name, value);
  }
  return new Response(body, { status, headers });
}

function requireSecret(env, key) {
  const value = env?.[key];
  if (typeof value !== "string" || value.length < 16 || value.length > 4096) {
    throw new RelayError("RELAY_CONFIGURATION_UNAVAILABLE", 503);
  }
  return value;
}

function backendUrl(env, pathname) {
  const raw = env?.EBRT_BACKEND_URL;
  if (typeof raw !== "string" || raw.length === 0 || raw.length > 2048) {
    throw new RelayError("RELAY_CONFIGURATION_UNAVAILABLE", 503);
  }
  let base;
  try {
    base = new URL(raw);
  } catch {
    throw new RelayError("RELAY_CONFIGURATION_UNAVAILABLE", 503);
  }
  if (
    base.protocol !== "https:" ||
    base.username ||
    base.password ||
    base.search ||
    base.hash
  ) {
    throw new RelayError("RELAY_CONFIGURATION_UNAVAILABLE", 503);
  }
  base.pathname = `${base.pathname.replace(/\/$/u, "")}${pathname}`;
  return base;
}

async function clientKey(request, env) {
  const clientIp = request.headers.get("CF-Connecting-IP")?.trim();
  if (!clientIp || clientIp.length > 128) {
    throw new RelayError("CLIENT_IDENTITY_UNAVAILABLE", 400);
  }
  const secret = requireSecret(env, "EBRT_CLIENT_KEY_SECRET");
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const signature = await crypto.subtle.sign(
    "HMAC",
    key,
    new TextEncoder().encode(clientIp),
  );
  return bytesToHex(new Uint8Array(signature));
}

function declaredLength(request) {
  const raw = request.headers.get("Content-Length");
  if (raw === null) return null;
  if (!/^(0|[1-9][0-9]*)$/u.test(raw)) {
    throw new RelayError("CONTENT_LENGTH_INVALID", 400);
  }
  const length = Number(raw);
  if (!Number.isSafeInteger(length)) {
    throw new RelayError("CONTENT_LENGTH_INVALID", 400);
  }
  if (length > MAX_REQUEST_BYTES) {
    throw new RelayError("REQUEST_BODY_TOO_LARGE", 413);
  }
  return length;
}

async function readBoundedBody(request) {
  const expectedLength = declaredLength(request);
  if (!request.body) {
    if (expectedLength && expectedLength > 0) {
      throw new RelayError("REQUEST_BODY_TRUNCATED", 400);
    }
    return new Uint8Array();
  }

  const reader = request.body.getReader();
  const chunks = [];
  let total = 0;
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      total += value.byteLength;
      if (total > MAX_REQUEST_BYTES) {
        await reader.cancel();
        throw new RelayError("REQUEST_BODY_TOO_LARGE", 413);
      }
      chunks.push(value);
    }
  } finally {
    reader.releaseLock();
  }
  if (expectedLength !== null && total !== expectedLength) {
    throw new RelayError("CONTENT_LENGTH_MISMATCH", 400);
  }
  const body = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    body.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return body;
}

function validatePostHeaders(request) {
  const contentType = request.headers.get("Content-Type")?.split(";", 1)[0].trim().toLowerCase();
  if (contentType !== "application/json") {
    throw new RelayError("CONTENT_TYPE_MUST_BE_JSON", 415);
  }
  const idempotencyKey = request.headers.get("Idempotency-Key");
  if (!idempotencyKey || idempotencyKey.length > 256 || /[\r\n]/u.test(idempotencyKey)) {
    throw new RelayError("IDEMPOTENCY_KEY_REQUIRED", 400);
  }
  return idempotencyKey;
}

function jsonObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function canonicalJson(value) {
  if (value === null || typeof value === "string" || typeof value === "boolean") {
    return JSON.stringify(value);
  }
  if (typeof value === "number" && Number.isFinite(value)) return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  if (jsonObject(value)) {
    return `{${Object.keys(value)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${canonicalJson(value[key])}`)
      .join(",")}}`;
  }
  throw new RelayError("REQUEST_JSON_INVALID", 400);
}

function parseJsonObject(bytes, code, status) {
  let value;
  try {
    value = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes));
  } catch {
    throw new RelayError(code, status);
  }
  if (!jsonObject(value)) throw new RelayError(code, status);
  return value;
}

async function fetchBackend(env, pathname, init) {
  let upstream;
  try {
    upstream = await fetch(backendUrl(env, pathname), {
      ...init,
      cache: "no-store",
      redirect: "manual",
    });
  } catch {
    throw new RelayError("LIVE_BACKEND_UNAVAILABLE", 502);
  }
  if (upstream.status >= 300 && upstream.status < 400) {
    throw new RelayError("LIVE_BACKEND_REDIRECT_REFUSED", 502);
  }

  let body;
  try {
    body = new Uint8Array(await upstream.arrayBuffer());
  } catch {
    throw new RelayError("LIVE_BACKEND_RESPONSE_UNREADABLE", 502);
  }
  const bodyHash = upstream.headers.get(BODY_SHA256_HEADER);
  if (!bodyHash || !/^[0-9a-f]{64}$/u.test(bodyHash) || (await sha256(body)) !== bodyHash) {
    throw new RelayError("LIVE_BACKEND_INTEGRITY_FAILURE", 502);
  }
  return { upstream, body, bodyHash };
}

async function requireSealedDemoRequest(body, idempotencyKey, env, relayHeaders, signal) {
  const submitted = parseJsonObject(body, "REQUEST_JSON_INVALID", 400);
  if (
    typeof submitted.request_id !== "string" ||
    submitted.request_id.length === 0 ||
    submitted.request_id.length > 256 ||
    submitted.request_id !== idempotencyKey
  ) {
    throw new RelayError("IDEMPOTENCY_KEY_MISMATCH", 400);
  }

  const { upstream, body: templateBody } = await fetchBackend(env, "/api/demo-request", {
    method: "GET",
    headers: relayHeaders,
    signal,
  });
  if (!upstream.ok) throw new RelayError("DEMO_TEMPLATE_UNAVAILABLE", 502);
  const envelope = parseJsonObject(templateBody, "DEMO_TEMPLATE_INVALID", 502);
  if (!jsonObject(envelope.request)) throw new RelayError("DEMO_TEMPLATE_INVALID", 502);
  const template = envelope.request;
  if (typeof template.request_id !== "string" || typeof template.case_id !== "string") {
    throw new RelayError("DEMO_TEMPLATE_INVALID", 502);
  }
  if (submitted.schema_version !== template.schema_version || submitted.case_id !== template.case_id) {
    throw new RelayError("PUBLIC_DEMO_REQUEST_REQUIRED", 403);
  }

  const { request_id: _submittedId, ...submittedFixed } = submitted;
  const { request_id: _templateId, ...templateFixed } = template;
  if (canonicalJson(submittedFixed) !== canonicalJson(templateFixed)) {
    throw new RelayError("PUBLIC_DEMO_REQUEST_REQUIRED", 403);
  }
}

async function proxyApi(request, env, pathname, expectedMethod) {
  if (request.method !== expectedMethod) {
    return errorResponse(405, "METHOD_NOT_ALLOWED", { Allow: expectedMethod });
  }

  const headers = new Headers({ Accept: "application/json" });
  let body;
  let idempotencyKey;
  if (expectedMethod === "POST") {
    idempotencyKey = validatePostHeaders(request);
    body = await readBoundedBody(request);
    if (body.byteLength === 0) throw new RelayError("REQUEST_BODY_REQUIRED", 400);
    headers.set("Content-Type", "application/json");
    headers.set("Idempotency-Key", idempotencyKey);
  } else {
    const length = declaredLength(request);
    if ((length ?? 0) !== 0 || request.body) {
      throw new RelayError("GET_BODY_NOT_ALLOWED", 400);
    }
  }

  headers.set(RELAY_TOKEN_HEADER, requireSecret(env, "EBRT_RELAY_TOKEN"));
  headers.set(CLIENT_KEY_HEADER, await clientKey(request, env));

  if (expectedMethod === "POST") {
    await requireSealedDemoRequest(body, idempotencyKey, env, headers, request.signal);
  }
  const { upstream, body: upstreamBody, bodyHash } = await fetchBackend(env, pathname, {
    method: expectedMethod,
    headers,
    body,
    signal: request.signal,
  });

  const responseHeader = responseHeaders(bodyHash);
  responseHeader.set("Content-Length", String(upstreamBody.byteLength));
  const upstreamContentType = upstream.headers.get("Content-Type");
  if (upstreamContentType) responseHeader.set("Content-Type", upstreamContentType);
  const replay = upstream.headers.get(IDEMPOTENT_REPLAY_HEADER);
  if (replay !== null) responseHeader.set(IDEMPOTENT_REPLAY_HEADER, replay);
  return new Response(upstreamBody, { status: upstream.status, headers: responseHeader });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (!url.pathname.startsWith("/api/")) {
      if (env?.ASSETS && typeof env.ASSETS.fetch === "function") {
        return env.ASSETS.fetch(request);
      }
      return new Response("Static asset binding unavailable", {
        status: 503,
        headers: {
          "Cache-Control": "no-store",
          "Content-Type": "text/plain; charset=utf-8",
        },
      });
    }

    const expectedMethod = API_ROUTES.get(url.pathname);
    if (!expectedMethod || url.search) return errorResponse(404, "ROUTE_NOT_FOUND");
    try {
      return await proxyApi(request, env, url.pathname, expectedMethod);
    } catch (error) {
      if (error instanceof RelayError) return errorResponse(error.status, error.code);
      return errorResponse(500, "RELAY_INTERNAL_ERROR");
    }
  },
};
