# EBRT v0.4.4 Recorded Reasoning Workbench

## Status

v0.4.4 is a deterministic, read-only product projection over committed public
artifacts. It gives the provisional Inspector one complete visible path:

```text
Evidence -> GPT event observer -> pre-outcome revision plan
         -> three recorded replay lanes -> public output diff
```

The projection makes zero network calls. It neither executes a model nor
applies a live revision. Its primary action is therefore **Play recorded
revision**, not Run, Apply, or Regenerate.

This version is deliberately non-promotional. It does not establish improved
reasoning accuracy, private-state access, or a production-ready scaffold.

## Locked sources

`projection_lock_reasoning_workbench_v0_4_4.json` pins every input byte used by
the projection:

- the v0.4 GPT-5.6 live-smoke manifest, results, and trace rows;
- the v0.4.1 aperture manifest and results;
- the v0.4.2 unchanged-replication r01 manifest and results;
- the v0.4.3 contract-smoke manifest, results, and diagnostic comparison.

For each bundle, the builder also verifies the bundle manifest's full artifact
hash map. Input paths are repository-relative and cannot escape the repository
root. A present canonical v0.4.3 full-block artifact is a hard validation
failure because the frozen smoke gate records that the full block was not
launched.

The builder projects named fields only. It does not copy source records
wholesale. The allowlist covers:

- public fixture evidence;
- emitted public Reasoning Cards;
- public observer output and sanitized receipt accounting;
- the pre-outcome replay plan and fingerprints;
- machine grades and public-card-derived diffs;
- bounded aggregate aperture and provider-boundary context.

Raw provider bodies, headers, exceptions, credentials, private reasoning text,
and hidden states are outside the projection contract.

The observer receipt has an exact two-level allowlist. Its top level is limited
to provider/model identity, completion status, service tier, attempt outcome,
retry/refusal counts, and `usage`. The nested usage object is limited to the
same ten sanitized accounting fields used elsewhere by the projection. The
builder rejects an added key at either level, even when the value is harmless.

## Mechanical episode selection

The demo episode is selected by rule, not by runtime outcome:

```text
case_id = episode_manifest.case_ids[0]
trial_index = 0
```

The lock asserts that this resolves uniquely to
`route_code_supersession / trial 0`. Both results and trace rows must contain
exactly one matching run. The trace and replay-plan fingerprints are recomputed
from their source material before any public snapshot is built.

The selected recorded sequence is:

1. R1-R5 produce a pre-event public answer of `AMBER`.
2. The GPT observer reads R6 and emits a public correction summary.
3. R6 invalidates R3; the plan anchors at R3 with execution replay floor 2.
4. All lanes execute under the same plan fingerprint.
5. Their final public Reasoning Cards and strict machine grades differ.

## Initial-state semantics

The R1-R5 card is labeled:

```text
phase: pre_event
status: initial_answer_match
post_event_machine_success: null
```

It is not labeled post-event PASS or FAIL. Its `AMBER` answer is the expected
answer before R6 arrives. Only the three post-event replay lanes receive the
strict post-event machine grade.

## Recorded replay lanes

| Lane | Replay calls | Regenerated public cards | Final answer | Grade |
| --- | ---: | ---: | --- | --- |
| Card-only forward | 1 | 1 | `AMBER` | FAIL |
| Selective replay | 4 | 4 | `AMBER` | FAIL |
| Full restart | 6 | 6 | `BLUE` | PASS |

The two negative lanes are retained intentionally. v0.4.4 does not turn the
recorded full-restart success into a general claim or silently promote
selective replay.

The visible output diff is computed only from public cards. It reports answer,
support, invalidation, and decision-fact changes. It is not a latent-state diff
or a chain-of-thought trace.

## Aperture context is separate

The v0.4.1 and v0.4.2 aperture summaries appear as a separate context panel.
They do not supply or explain the selected v0.4 episode.

The frozen v0.4.1 incomplete DEV block descriptively recorded:

- staged cumulative raw: 30 machine successes in 30 completed outputs;
- staged card-only: 2 machine successes in 28 completed outputs, with two
  incomplete outputs.

The locked cause gate was false. The v0.4.2 unchanged replication was also
incomplete, attempted 344 of 420 nominal calls, and retained 31 non-assessable
endpoints. It produced no locked aperture or reasoning decision.

These aggregates are useful debugging context, not a same-episode causal
decomposition.

## Provider Failure Atlas

The v0.4.3 panel is a separate boundary diagnostic:

```text
8 client attempts
  -> 8 HTTP observations (429)
  -> 0 structured parses
  -> 0 accepted outputs
  -> 0 reasoning assessments
```

The HTTP status is not a UI constant. The lock separately pins the frozen
`calls.jsonl`; the builder requires every calls row to match the corresponding
receipt in corrected `results.json`, then derives the HTTP status, phase, reason,
and counts from those eight receipts. For this artifact the derived distribution
is `429: 8`. A calls-only edit fails cross-file identity, while a matched edit to
both receipt sources still fails the locked status distribution.

All eight endpoints received the allowlisted typed classification
`http_status/insufficient_quota`. Native phase/reason coverage is shown as:

```text
r01 frozen native       0/31
v0.4.3 contract smoke   8/8
cross-block effect      null
```

The 8/8 coverage field uses the corrected authoritative projection
`v0.4.3_policy_exact_schedule_projection`. The correction was applied after
the frozen live run because an inherited v0.4.2 smoke namespace had projected
the v0.4.3 run IDs incorrectly. Its lineage explicitly records:

- no additional live call;
- unchanged provider observations;
- the original and corrected manifest/results hashes;
- an unchanged receipt projection hash;
- unchanged `arm_rows.csv`, `benchmark_report.md`, `calls.jsonl`, and
  `traces.jsonl` hashes.

The v0.4.4 builder verifies this complete lineage against both the corrected
manifest and the independent v0.4.3 comparison before publishing the Atlas.
The correction changes derived coverage metadata, not the eight observed HTTP
429 outcomes.

The blocks have different populations. This comparison supports diagnostic
observability only. The failed smoke gate closed the v0.4.3 full launch and all
reasoning conclusions.

## Gates

The public snapshot locks the following state:

```text
recorded_episode_integrity_ready      true
projection_integrity_ready            true
provider_diagnostic_integrity_ready   true
recorded_demo_ready                   true

live_execution_ready                  false
locked_reasoning_decision_ready       false
reasoning_improvement_claim_ready     false
promotion_eligible                    false
```

`recorded_demo_ready` means the saved episode can be rendered and audited. It
does not mean a new provider call can be made or a revision can be applied.

## Deterministic build and validation

Build the canonical artifact, the public Inspector copy, and the report:

```bash
python3 build_reasoning_workbench_snapshot_v0_4_4.py build
```

Validate the checked-in outputs against all pinned sources:

```bash
python3 build_reasoning_workbench_snapshot_v0_4_4.py validate
```

Run the no-network, two-build determinism test:

```bash
python3 build_reasoning_workbench_snapshot_v0_4_4.py self-test
```

The combined default command performs all three:

```bash
python3 build_reasoning_workbench_snapshot_v0_4_4.py
```

Validation fails unless:

- every pinned source byte and bundle artifact hash matches;
- the mechanical selection is unique;
- source trace, observer-input, event-projection, and plan fingerprints hold;
- the plan is pre-outcome and shared by all lanes;
- call, card, usage, and grade cardinalities match;
- the sanitized observer receipt and nested usage objects match their exact
  allowlists;
- the public output diff recomputes from public cards;
- both recorded negative lanes remain present;
- v0.4.3 and r01 native diagnostic coverage remains 8/8 and 0/31;
- the authoritative coverage-correction lineage remains complete and the
  provider-observation artifact hashes remain unchanged;
- Atlas HTTP status, phase, reason, and counts rederive from the pinned receipt
  rows and match the locked distribution;
- the v0.4.3 full artifact remains absent;
- forbidden keys and credential-like values do not enter the snapshot;
- two independent in-memory builds are byte-identical;
- the canonical and public snapshot files are byte-identical;
- the builder opens no network socket.

Timestamps are intentionally absent from the snapshot, report, and manifest.

## Provisional visual concept and fidelity ledger

The first product surface is guided by two committed, replaceable visual
concepts:

- `docs/design/ebrt_reasoning_workbench_concept_v0_4_4.png`;
- `docs/design/ebrt_reasoning_workbench_narrow_concept_v0_4_4.png`.

The implementation retains their true-white audit surface, near-black type,
cobalt/amber/vermilion state language, one-pixel rules, five-stage flow,
all-lane Replay view, git-style public output diff, gate strip, and separate
Failure Atlas. Desktop and narrow browser renders were compared directly with
both concepts after the production build.

Three deviations are intentional evidence corrections rather than visual
drift:

1. Initial is `PRE-EVENT / answer match`, not a fabricated post-event FAIL.
2. The Atlas shows the exact saved pipeline: 8 client attempts, 8 HTTP
   observations, then zero parses, accepted outputs, and assessments.
3. The rail contains only the one mechanically projected episode, and no
   timestamp is invented for a timestamp-free deterministic artifact.

Browser screenshots used for layout QA are temporary and are not evidence
artifacts. The concepts are design inputs; the snapshot remains the sole data
source for rendered claims.

## Claim boundary

v0.4.4 is evidence-preserving product compression. It shows how a developer
can inspect a recorded event, a public revision plan, replay alternatives, and
their resulting public output diff in one artifact-backed surface.

It does not claim:

- general LLM reasoning improvement;
- a causal advantage for selective replay or full restart;
- cross-block failure-rate improvement;
- access to private chain-of-thought;
- hidden-state editing or model-weight change;
- matched compute across replay lanes;
- live execution readiness or production safety.
