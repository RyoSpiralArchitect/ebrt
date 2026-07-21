# EBRT v0.6.2.2 — Live Apply Revision Runtime

Status: **CURRENT LIVE PRODUCT MONOLITH — OPERATIONAL PASS ONLY; SEMANTIC QUALITY AND EFFECT NOT ASSESSED**

`ebrt_live.py` is the current Apply Revision product surface. It is a new
runtime namespace: root `ebrt.py`, the sealed v0.6.2.1 two-call acceptance
contract, and `artifacts/apply_revision_acceptance_v0_6_2_1_live_r01/` remain
immutable.

## Contract

```text
typed public invalidation-revision request
  -> validate case, evidence, Before state, closure graphs, and event
  -> compile the selected Before closure
  -> one local float64 backward() ranks reinspection salience
  -> typed event compiles Suppress / Preserve
  -> server remaps candidate IDs to opaque graph hashes
  -> exactly one no-retry After provider attempt per new request identity
  -> typed public output, lineage, and accounting checks
```

`POST /api/apply-revision` accepts a complete
`ebrt-live-apply-revision-request-v0.6.2.2` request with these exact root fields:

```text
schema_version                   request_id
case_id                          checkpoint_id
question                         answer_choices
decision_slots                   all_raw_evidence
before_horizon_evidence_ids      prior_public_state
prior_closure                    candidate_closures
event                            reinspection_count
```

The caller supplies an already emitted Before state and its selected closure
graph, a typed invalidation event, and at least two structurally distinct After
closure candidates.
Validation rejects extra fields, duplicate keys, nonfinite values, dangling or
cyclic graph references, a non-prefix Before horizon, duplicate graph aliases,
undeclared invalidation transitions, missing prior invalidations, missing
fact-local correction lineage, evidence outside its horizon, and values outside
the public domains. Reserved gold/expected-answer fields are rejected. Free-form
caller text is not certified as gold-free. The runtime does not call the
fixture-bound v0.6.2.1 validators or runners.

The hosted model is not differentiated. Gradients stop at the public control
map and actuator compiler. The backward pass ranks evidence for `Reinspect`;
the signs and roles of `Suppress` and `Preserve` come from the typed event, not
from the backward pass. Provider input excludes credentials, gradients, losses,
salience values, private controller material, expected answers, caller closure
labels, grades, reserved gold fields, previous response IDs, and private
reasoning. The provider sees only server-generated opaque closure IDs.

## Result and claim boundary

A complete response uses
`ebrt-live-apply-revision-response-v0.6.2.2` and keeps `context`, `mechanism`,
`output`, `verification`, and `accounting` separate. Operational `PASS` means
the request, local mechanism, one-attempt provider boundary, typed output, and
public lineage contracts completed. Every response still records:

```text
semantic_correctness_status = NOT_ASSESSED
effect_attribution_status   = NOT_ASSESSED
provider_attempts           = 1
```

No response exposes raw provider input, receipts, provider HTTP headers, exception text,
credentials, reserved gold fields, provider-private gradients/losses, or
post-hoc grades. The response intentionally exposes the local public-surrogate
objective, gradient, finite-difference check, and reinspection salience as
auditable mechanism diagnostics; none of those fields enter provider input.
The server marks the built-in demo as `CONTAMINATED_REGRESSION_FIXTURE` only
after exact normalized-template matching and byte pins for the published
v0.6.2.1 manifest and `provider_inputs.json`; all other requests are
`CALLER_SUPPLIED_UNVERIFIED`. The demo envelope seals both the request and the
envelope. The Inspector recomputes those seals, correlates provenance and source
identity through the submitted request, verifies `X-EBRT-Body-SHA256` over the
received API bytes, recomputes the live response self-seal without losing JSON
number lexemes, and rejects any inconsistent operational/reserved status graph
before rendering. These SHA-256 values are deterministic integrity and
correlation checks within the trusted loopback deployment, not authentication
of an untrusted remote server. v0.6.2.2 therefore establishes
an executable and auditable product operation, not semantic correctness,
causal necessity, quality improvement, or general reasoning improvement.

`request_id` is the idempotency key. Repeating the same identity and canonical
request returns the same terminal success or sanitized terminal error; a
different canonical request conflicts, and an in-flight duplicate never starts
another attempt. The session keeps complete terminal results in a 128-entry LRU
cache and separately retains compact request fingerprints for up to 65,536
spent identities. A repeated identity whose complete result was evicted returns
`410 IDEMPOTENCY_RESULT_EVICTED` without provider execution, while new identities
continue normally. Once the compact ledger fills, the service safely rejects
new identities rather than risking an old call being repeated. SDK and
application retries are zero, and new provider execution is serialized. This
ledger is process-local in v0.6.2.2; durable multi-process idempotency is outside
the loopback runtime's declared surface.

## CLI and loopback API

Run the offline contract and contaminated demo adapter:

```bash
python3 -m pip install -r requirements-product.txt
python3 ebrt_live.py self-test
python3 ebrt_live.py demo-request
python3 ebrt_live.py apply-demo --provider scripted
python3 ebrt_live.py serve --provider scripted --host 127.0.0.1 --port 8765
```

With `OPENAI_API_KEY` supplied only through the process environment or an
equivalent server-side secret store:

```bash
python3 ebrt_live.py apply-demo --provider openai
python3 ebrt_live.py serve --provider openai --host 127.0.0.1 --port 8765
```

The bounded server surface is:

```text
GET  /api/health         liveness; zero provider calls
GET  /api/capabilities   public contract and limits
GET  /api/demo-request   contaminated public example; zero provider calls
POST /api/apply-revision one idempotent live operation
```

Health and capability responses use `ebrt-live-health-v0.6.2.2` and
`ebrt-live-capabilities-v0.6.2.2`; the demo envelope uses
`ebrt-live-demo-request-v0.6.2.2`.

The server binds loopback by default and does not serve repository files. API
keys remain server-side and are never accepted in request JSON, health,
capabilities, errors, or logs. Remote binding, wildcard CORS, and client-supplied
provider credentials are outside this version's product surface.

## Scripted and demo boundary

The scripted provider exercises request validation, local control, response
projection, API, and idempotency without network access. It is test plumbing,
not a hosted result.

`demo-request` adapts the known hackathon-strategy case for CLI and UI use. That
case inherits the v0.5.2-v0.6.2.1 design, repair, controller, and result history.
It is intentionally contaminated—not a fresh benchmark, holdout, causal
comparison, accuracy result, or population estimate.

## Adversarial contract checks

The network-zero self-test covers enum-order invariance of the salience map,
exact single-late-event horizon binding, order-normalized duplicate candidate
rejection, exact invalidation transitions, inherited invalidation preservation, fact-local
correction binding, server-opaque provider IDs, one-call failure tombstones,
terminal-result LRU eviction without identity reexecution,
concurrent same-ID suppression, the publication-pinned demo source, sealed demo
envelope, and API response-body digest. The historical `ebrt.py` byte lock and
the recorded Inspector projection are checked independently. A headless-browser
negative test intercepted an otherwise valid scripted response, changed the
`Semantic correctness` row to `PASS`, recomputed the body SHA-256, and confirmed
that the Inspector rejected the coherent mutation before rendering a terminal.
A second interception changed only the top-level response self-seal, recomputed
the transport-body header, and was rejected specifically at
`response.fingerprint_sha256 integrity`.

## Manual real-provider smoke

On 2026-07-21 JST, after the offline and browser-scripted gates passed, the
loopback API was switched once to `openai` mode and the Inspector issued one
explicit `Apply Revision → Regenerate` operation. There was no retry. The one
GPT-5.6 provider attempt completed in 6.41 seconds with 1,948 input tokens and
152 output tokens. The public answer changed `POLISH → PROVE`; provider schema,
opaque closure binding, exact invalidation transition, prior-invalidation
preservation, fact-local correction lineage, stable-target preservation, and
public diff all returned operational `PASS`.

This was an interactive product smoke, not a newly sealed benchmark artifact
or causal contrast. The built-in case is the explicitly contaminated regression
fixture, and both semantic correctness and effect attribution remained
`NOT_ASSESSED`. The OpenAI-mode backend was stopped after that terminal.
