# EBRT v0.4.3 — prospective provider-boundary protocol

Status: **FROZEN CONTRACT SMOKE; FULL BLOCK NOT LAUNCHED**

Promotion eligible: `false`

Reasoning-protocol change from v0.4.2: `false`

Observation change from v0.4.2: `SDK acquisition/parse boundary only`

The executable lock is
[`policy_lock_aperture_controls_v0_4_3.json`](../policy_lock_aperture_controls_v0_4_3.json).
No live execution may begin until the provider adapter, runner, lock, and this
protocol are sealed together in a pushed preregistration commit.

## Frozen execution outcome

The implementation and this protocol were preregistered and pushed before the
first live call:

```text
preregistration commit  3ff8ba9b1fd21bb39c230a5b65a7a232c1d67b6f
preregistration tree    42e0031e60cbcadaa4cd06333bfa7659c7c0b10d
smoke manifest          1aabd709e95f8f45c94a31dda6d443cdcd80ab4f03e93a03de3d6bac2cb36f3c
```

The locked two-case by one-trial smoke was then executed exactly once. Its
eight scheduled arm endpoints each stopped on the first attempted provider
call, so the run used 8 attempted calls against the preregistered 28-call
nominal ceiling. All eight receipts preserved an observed HTTP 429 with the
typed SDK error code `insufficient_quota`:

```text
attempted calls                         8
terminal receipts                       8
classified failed receipts              8
classified non-assessable endpoints     8
unclassified non-assessable endpoints   0
HTTP acquired / status retained         8 / 8
diagnostic_integrity_ready               true
locked_decision_ready                    false
full_launch_ready                        false
primary execution classification        smoke_gate_failed_full_not_launched
```

This is a successful diagnostic artifact and an unsuccessful launch gate. The
exact full block was not run, no reasoning contrast is assessed, and no token
or quality conclusion is emitted. The observed subtype is evidence about these
new attempts only; it does not retrospectively relabel the frozen r01 tail.

The smoke and full protocols are one-shot. Restoring quota does not authorize a
second v0.4.3 smoke or a fill/resume. Any future live attempt requires a new
preregistered protocol id.

## Post-freeze maintenance note (2026-07-19)

After the smoke and diagnostic comparison were frozen, the runner's offline
receipt audit was hardened in two bounded ways:

- a real-adapter `provider_contract/wrong_runtime` receipt may retain a safely
  shaped returned model or service tier that differs from the request without
  being converted into `receipt_audit/receipt_field_violation`; provider-contract
  reason priority remains owned by the adapter, while a completed receipt still
  requires exact `gpt-5.6-sol` and `default` values; and
- the locked Python version must equal the interpreter before any provider is
  constructed, and every receipt must carry that exact Python version.

Offline regressions cover wrong model, wrong tier, missing tier, higher-priority
refusal plus wrong model, unsafe field shape, completed-receipt mismatch,
policy-version tamper, and receipt-version tamper. This maintenance made **no
new live call**, does not change the policy lock, and does not alter or
reclassify the frozen provider observations or r01 artifacts. The
comparison verifier resolves the v0.4.3 runner from the smoke manifest's
preregistration commit, so post-freeze working-source maintenance cannot alter
which runner bytes are attributed to the live evidence.

The offline comparison verifier was also made clean-checkout reproducible.
Committed canonical bundles under `artifacts/` are the required evidence and
receive the full manifest, artifact-hash, trace/call, receipt, schedule, and
privacy audits. Ignored `benchmark_results/` working bundles are optional; when
one is present, every expected file must still be byte-identical to its
canonical counterpart. Offline tests exercise canonical-only validation plus
canonical tamper, working-copy tamper, and malformed working-path rejection.
This verifier maintenance made no live or network call. The later derived-field
correction below is its only explicit change to the smoke bundle bytes.

### Post-freeze smoke coverage derivation correction

The inherited v0.4.2 validator recognized only its historical
`openai_live_contract_smoke` mode and run-id prefix. The v0.4.3 compatibility
copy retained the v0.4.3 names, so the nested inherited field
`contract_smoke_exact_coverage` was `false` even though the authoritative
v0.4.3 policy/schedule audit was exactly covered. This was a namespace
projection defect, not a failed or missing provider observation.

The compatibility copy now maps only the mode and run-id namespace before the
frozen v0.4.2 validator consumes it, then cross-checks that answer against the
unchanged v0.4.3 policy schedule. A run-id or schedule tamper fails closed. The
canonical and working smoke `results.json` and `manifest.json` correct that
derived coverage field to `true`, name
`v0.4.3_policy_exact_schedule_projection` as its authority, and carry an
explicit `ebrt-post-freeze-derived-correction-v0.4.3` lineage.

```text
original manifest  1aabd709e95f8f45c94a31dda6d443cdcd80ab4f03e93a03de3d6bac2cb36f3c
corrected manifest 42172d684de6541fc6b26e23cf7e9ae7fde92395dd81db8fbeb53ed8a32021ec
original results   f519d253228d037092037b1592c46ac0443d1684ad223b0701420225223b544e
corrected results  fb9a863b82d4caaf6afc60446c852d6e1c2de09c463239508b02a28a39316819
calls.jsonl        68989d17874f2da14964733f003aedcd6f4e8e99e35284f2def19f2873575d5e
traces.jsonl       1cfd67fe6f8894a2c82f023a1624c223df76656e3a056ae632bc5228714ba0a5
receipt projection ba735cd7ec08a9644636ac665bf3514d8d1fd460a103214e40da0afeeba658e9
```

No live call, retry, provider receipt, trace, call row, score, failure label, or
reasoning conclusion changed. All eight endpoints remain non-assessable
`http_status/insufficient_quota`; `full_run_launch_ready` and
`locked_decision_ready` remain `false`, and the full block remains unexecuted.

## Why v0.4.3 exists

The unchanged v0.4.2 replication r01 passed its fixed two-case contract smoke,
then ended its exact ten-case by three-trial block with a contiguous tail of 31
non-assessable provider attempts. The frozen receipts identify the SDK exception
type as `RateLimitError`, but retain neither an HTTP status nor a typed provider
error code. They therefore cannot distinguish ordinary rate limiting from quota
exhaustion. Those rows correctly remain `provider_call_exception_unclassified`.

v0.4.3 instruments the boundary prospectively. It asks whether a provider
response was acquired, whether the SDK's structured parser ran, and where an
attempt failed. Its objective is diagnostic closure, not a favorable reasoning
result.

Pinned predecessor evidence:

```text
frozen commit       56225784d51b97243b2fdd0a615379418444631d
frozen tree         2faa99c945e2fcd13fe3bb98f5be7f52ac7b7128
r01 policy          2fdecd663df2efd713a242268108e7f7ee131e074191c72bc650c5ab48886584
r01 smoke manifest  fb623a28eb61d7c9dea971ff8018645890b141f79b048e38e109fb32765d15a5
r01 full manifest   dde2d872ead686fa5d4b8074536e0d44acc1678036937f834fbe6389a3971671
r01 full status     INCOMPLETE
```

The two manifest hashes point to the canonical r01 bundles under `artifacts/`.
They are evidence inputs only. v0.4.3 does not mutate, regrade, relabel, repair,
or fill them.

## Exactly what remains unchanged

The four arms, prompts, response schema, fixtures, gold, model, reasoning
effort, service tier, storage setting, truncation setting, per-call output-token
budgets, Williams schedule, case/trial order, validators, endpoint definitions,
and local terminal-rejection policy remain inherited from v0.4.2.

The runtime request remains:

```text
model                 gpt-5.6-sol
reasoning effort      low
service tier          default
SDK retries           0
timeout               60 seconds
store                 false
previous_response_id  false
truncation            disabled
provider seed         unset
```

No instrumentation-only provider request is added. Each semantic request body
and structured-output schema is the same as v0.4.2. The sole intended change is
how the same SDK call is observed before and during local structured parsing.

## Prospective acquisition and parse boundary

The adapter divides one attempted provider call into observable phases:

```text
request_call
  -> http_status
  -> sdk_response_parse
  -> provider_contract
  -> local_public_card_validation
  -> receipt_audit
```

An internal invariant stop has the separate phase `internal`.

The call path is fixed:

1. Call `client.responses.with_raw_response.parse(...)` once.
2. If it returns, record that an HTTP wrapper was acquired, its numeric status,
   and only the sanitized metadata allowed below.
3. Invoke `raw_response.parse()` exactly once to perform the same SDK
   structured-output parse.
4. Validate provider status, refusal, model/runtime, structured output, and
   exact usage.
5. Pass a successful public card through the unchanged local validator.

A failed attempt terminates that arm. There is no retry or repair. Remaining
preassigned arms and scheduled runs continue so that a one-shot block preserves
its diagnostic geometry.

`wrong_runtime` is resolved at this boundary, before a completed receipt. A
returned model unequal to the requested model, or a returned service tier
unequal to the locked `default` (including unavailable), emits exactly one
`provider_contract/wrong_runtime` receipt and terminates that arm. It may not be
deferred to the later receipt audit.

## Stable failure taxonomy

Every failed attempt gets one phase and one allowlisted reason. Unknown,
missing, or phase-incompatible codes are themselves an audit failure.

| Phase | Allowlisted non-assessable codes |
| --- | --- |
| `request_call` | `timeout`, `connection`, `request_unclassified` |
| `http_status` | `authentication`, `permission_denied`, `not_found`, `bad_request`, `conflict`, `unprocessable_entity`, `insufficient_quota`, `rate_limit`, `unknown429`, `server_error`, `http_other` |
| `sdk_response_parse` | `sdk_http_envelope_validation`, `sdk_structured_parse_validation`, `sdk_response_decode`, `sdk_parse_unclassified` |
| `provider_contract` | `provider_refusal`, `provider_status_non_completed`, `provider_error`, `provider_incomplete`, `missing_structured_output`, `missing_exact_usage`, `wrong_runtime` |
| `receipt_audit` | `receipt_request_fingerprint_mismatch`, `receipt_missing`, `receipt_duplicate`, `receipt_field_violation`, `boot_source_snapshot_mismatch`, `artifact_hash_mismatch` |
| `internal` | `internal_invariant_failure` |

All of these remain non-assessable reasoning endpoints. Better classification
does not convert a provider or SDK failure into a model failure.

The unchanged 13 local public-card codes remain a separate assessed surface:

```text
answer_choice_violation
checkpoint_id_mismatch
claim_character_bound_exceeded
disallowed_decision_slot_value
duplicate_decision_slot
invalidated_active_support
invented_invalidation
missing_required_decision_slot
multiple_raw_chunks_copied
topic_character_bound_exceeded
unavailable_evidence_citation
unknown_decision_slot
unseen_active_support
```

An allowlisted local rejection after a completed provider call is an assessed
strict failure. It is not missing data and does not create a second provider
receipt. Its remaining staged calls are not made.

### Prospective HTTP 429 split

`RateLimitError` is split only for new v0.4.3 attempts:

- typed SDK error code exactly `insufficient_quota` -> `insufficient_quota`;
- typed SDK error code `rate_limit` or `rate_limit_exceeded` -> `rate_limit`;
- absent or any other typed code with HTTP 429 -> `unknown429`.

Only the stable reason and numeric status are saved. The error body, exception
message, args, traceback, and arbitrary headers are not saved. These operational
labels report what the typed SDK surface exposed; they do not prove a deeper
provider-side cause.

The r01 failure tail is not processed through this mapping. Its historical
`provider_call_exception_unclassified` and `transport_error` labels remain
byte-identical.

## One receipt per attempted call

Each attempted client call emits exactly one terminal receipt. `attempt=1` and
`retry_count=0` are invariant. A success cannot also emit a failure receipt,
and a later local validator rejection does not emit another provider receipt.

Required fields include:

- provider, requested model, runtime versions, and request settings;
- request, prompt, response-schema, and semantic-protocol fingerprints;
- attempt, retry count, outcome, phase, reason, and parse boundary;
- whether HTTP was observed, numeric status when known, and latency; and
- fixed privacy and audit schema versions.

Conditional fields remain null unless safely observed:

- returned model and service tier after successful parsing;
- exact usage after validated extraction;
- hashed response/request identifiers; and
- provider-body SHA-256 and byte count computed in memory.

The provider body bytes themselves are never persisted. The following are also
forbidden from every artifact, trace, log, and report:

- exception messages, args, and tracebacks;
- arbitrary response headers;
- credentials and bearer tokens;
- rejected public cards and their slot/evidence values; and
- any inferred or reconstructed usage for a failed call.

## Two different readiness gates

v0.4.3 deliberately separates artifact trustworthiness from reasoning-decision
readiness.

### `diagnostic_integrity_ready`

This gate says the run is trustworthy as a provider-boundary diagnostic. It
requires:

- a pushed preregistration commit and clean preflight;
- the exact boot-source snapshot sealed below;
- complete scheduled case/trial and arm-order records;
- one valid allowlisted receipt per attempted call;
- equal attempted-call and receipt counts;
- no retry, repair, resume, fill, replacement, or prior-receipt reuse;
- no forbidden payload persistence; and
- a validating final artifact hash map.

The coverage check includes the exact case/trial population, original case
index, run position, run id, and Williams arm order. A matching set of cases is
not sufficient if any scheduled position or order differs.

The preregistered canonical schedule hashes are
`05b586414582e799dc827e76a7389375f49e0c0f721b234f783f3a9373fd460d`
for smoke and
`d586e073f31aedf46bafcf391a42330abc508db3610d3bd75adb6d660f66e957`
for the full block.

The bundle is first written and audited in a uniquely owned sibling staging
directory. Only a complete bundle is atomically published to the locked output
path. A write or audit failure cannot leave a partial success bundle at that
path; any terminal failure record is sanitized and explicitly unavailable for
comparison.

An arm may terminate early, so this does not require all nominal calls. A
classified provider failure is permitted: preserving that failure accurately is
the purpose of this gate.

### `locked_decision_ready`

This gate controls whether the unchanged reasoning contrasts may receive a
locked cause conclusion. It requires:

- `diagnostic_integrity_ready=true`;
- the exact ten-case by three-trial schedule;
- every one of 120 arm endpoints assessed as either an accepted output or an
  allowlisted terminal local rejection;
- zero provider, SDK, receipt-audit, or internal non-assessable failures; and
- validated receipts for every attempted call.

Assessed local strict failures are allowed. Any non-assessable endpoint keeps
this gate false. When false, both cause conclusions remain
`not_assessed_incomplete_or_subset_run`, even when the failure taxonomy is
perfectly diagnostic.

Thus these states are valid and intentionally different:

```text
diagnostic_integrity_ready=true
locked_decision_ready=false
```

## Source and preregistration seal

The lock does not embed the hashes of the new runner or provider adapter. Doing
so would create a brittle self-reference during implementation. Instead, the
first live call is gated on one pushed preregistration commit containing:

- `benchmark_aperture_controls_v0_4_3.py`;
- `openai_response_boundary_v0_4_3.py`;
- `policy_lock_aperture_controls_v0_4_3.json`;
- this protocol; and
- all inherited sources named in the lock's `boot_source_paths`.

At preflight the runner computes the SHA-256 map for every named boot source
and records it with the exact git commit and tree. The smoke manifest owns this
map. Full launch requires byte equality with the smoke snapshot, and final
freeze revalidates it. The lock names the new files but contains no expected
hash for itself, the new runner, or the new provider.

Before any live call:

- the preregistration commit is pushed;
- the worktree is clean;
- Python/OpenAI/Pydantic versions match the lock;
- the API credential is present without being printed;
- the offline matrix passes;
- the two r01 predecessor manifests match their pinned hashes; and
- both v0.4.3 working and canonical output paths are absent.

Any failed preflight ends the protocol with no live call.

## Offline fault matrix

The self-test must use fakes only and make no network call. It covers:

1. successful acquisition, parse, provider contract, exact usage, and one
   receipt;
2. timeout and connection exceptions;
3. authentication, permission, not-found, bad-request, conflict,
   unprocessable, server, and other HTTP errors;
4. three distinct `RateLimitError` branches: `insufficient_quota`, ordinary
   `rate_limit`, and `unknown429`;
5. SDK HTTP-envelope validation failure;
6. Pydantic structured-output validation after HTTP acquisition;
7. response decode and unclassified parse failures;
8. refusal, non-completed status, provider error/incomplete, missing output,
   missing exact usage, and wrong runtime, including wrong/missing returned
   model or service tier;
9. all 13 local validator codes remaining assessed strict failures;
10. provider/SDK failures remaining non-assessable;
11. exactly one receipt per attempt and zero retry;
12. continuation of remaining preassigned arms after a failed arm;
13. leakage sentinels for body, exception, headers, credentials, and rejected
    card values;
14. request/prompt/schema/semantic fingerprint tamper detection;
15. missing, duplicate, unknown, and phase-incompatible receipt rejection;
16. boot-source and artifact-hash tamper detection;
17. the zero-provider-failure smoke launch gate;
18. `diagnostic_integrity_ready=true` with a classified provider failure while
    `locked_decision_ready=false`;
19. the exact ten-case by three-trial decision gate;
20. tamper rejection for original case index, run position, run id, and
    Williams arm order;
21. exact comparison-field names, zero-filled reason maps, and endpoint/call
    accounting identities;
22. dropped, duplicated, reordered, or altered `calls.jsonl` rows;
23. write, audit, and pre-publish failures leaving no partial success bundle;
    and
24. an explicit guard that historical r01 rows are never reclassified.

The report and manifest must also regenerate deterministically from the same
fake run records.

## One-shot execution sequence

Run the offline gate first:

```bash
python3 benchmark_aperture_controls_v0_4_3.py self-test
```

Then run the same fixed contract smoke used by v0.4.2/r01 exactly once:

```bash
python3 benchmark_aperture_controls_v0_4_3.py live-contract-smoke \
  --output benchmark_results/v0_4_3_provider_boundary_contract_smoke
```

It is fixed to `unit_reinterpretation` and
`invalidated_sensor_fallback`, one trial, four arms, and 28 nominal calls. Full
launch requires:

- exact two-case/one-trial coverage;
- `diagnostic_integrity_ready=true`;
- all eight arm endpoints assessed;
- zero provider, SDK, receipt-audit, or internal failure; and
- a source snapshot equal to the preregistration seal.

An allowlisted terminal local rejection is assessed and may reduce attempted
calls below 28 without failing this launch gate. Any provider-boundary failure,
even if classified perfectly, freezes the smoke and prevents full launch.

Only when `full_launch_ready=true`, execute the exact full block once:

```bash
python3 benchmark_aperture_controls_v0_4_3.py live-dev \
  --contract-smoke-manifest \
    benchmark_results/v0_4_3_provider_boundary_contract_smoke/manifest.json \
  --output benchmark_results/v0_4_3_provider_boundary_dev
```

The full command has no case/trial override. It runs all ten locked cases,
three trials, the fixed Williams order, 120 endpoints, and a 420-call nominal
ceiling. It is never launched from an old smoke or the v0.4.2/r01 smoke.

There is no SDK or manual retry, repair, resume, partial fill, output
replacement, prior-receipt reuse, or subset substitution. An adverse run is
frozen as observed. Any later attempt requires a new preregistered protocol ID
and does not complete v0.4.3.

## Required execution record

The eventual smoke/full manifests and reports record, at minimum:

- preregistration commit/tree, policy hash, complete boot-source hash map,
  predecessor manifest hashes, and runtime versions;
- mode, case count/IDs, trials/IDs, exact run/arm order and hash, scheduled arm
  endpoints, nominal calls, attempted calls, and receipt count;
- zero-filled counts by every failure phase and allowlisted reason;
- failed/classified receipt counts and classified/unclassified non-assessable
  endpoint counts;
- HTTP-observation-recorded, HTTP-acquired/status, parse-attempted/succeeded,
  and exact-usage-available counts;
- accepted/assessed/non-assessable endpoints and zero-filled terminal local
  reasons;
- per-arm accepted/assessed/strict outcomes, assessed four-arm runs,
  all-output-completed runs, stable counts, and both locked contrasts;
- exact total tokens only when available for the complete declared population;
- receipt, source, privacy, calls-row, atomic-publication, and artifact-hash
  audit results; and
- `diagnostic_integrity_ready`, `locked_decision_ready`,
  `full_launch_ready`, primary execution classification, and either the locked
  cause conclusion or `not_assessed`.

The primary execution classification is exactly one of:

```text
offline_gate_failed_no_live_call
smoke_gate_failed_full_not_launched
full_executed_diagnostic_integrity_failed
full_executed_diagnostic_integrity_ready_decision_not_ready
full_executed_decision_ready
```

## Claim boundary

This remains a contaminated ten-case DEV suite. It is neither a holdout nor a
promotion/generalization experiment.

v0.4.2 and v0.4.3 are independent stochastic blocks. A difference in quality,
token use, latency, failure frequency, stable counts, or contrast counts is
descriptive only; it is not an instrumentation effect. No favorable subset may
be introduced after execution.

The prospective taxonomy can show where the typed SDK surface failed. It cannot
turn a provider failure into an assessed model answer, prove the provider's
internal cause, establish general reasoning improvement, isolate a
compression-only mechanism, access private chain-of-thought, edit hidden state,
or change model weights.

Exact token claims require exact provider usage across the complete declared
population. A partial sum or accepted-output subset is not a full-block
efficiency result.

## Execution record

Intentionally empty until the sealed protocol terminates.

Execution status: **PENDING**
