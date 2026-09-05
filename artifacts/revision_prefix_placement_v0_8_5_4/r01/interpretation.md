# v0.8.5.4 r01 — post-run interpretation

Date: 2026-09-06. This document is commentary added after the sealed execution.
It does not replace, modify, regrade, or retry the emitted result artifact.

## Outcome

**No repair benefit was observed.** The full-context baseline passed 3/4 strict
cases, the appended program 2/4, and the prepended program 0/4. Four known cases,
one Mistral snapshot, and one deterministic sample per arm are an engineering
screen, not a general estimate of prefix-conditioning or gradient utility.

| Case | Baseline | Append | Prepend |
| --- | --- | --- | --- |
| Freight lane | PASS | PASS | FAIL: R6 in two disjoint channels |
| Credit scale | FAIL: 45 instead of 15 | Same failure | Same failure |
| Archive tier | PASS | PASS | FAIL: missing R2 |
| Permit state | PASS | FAIL: missing R2 | FAIL: missing R2 |

The generated outputs make the changes concrete. For archive, the answer stays
`COLD_TIER` while decision support changes from `["R2","R4"]` to `["R4"]`.
For freight, prepend adds R6 to decision support while also returning R6 as the
revision event. The unchanged parser rejects that overlap. It is not a
token-limit failure: every generation ended with `stop` below the ceiling.

Thus append/prepend yields one normalized-state difference among three
jointly parsed pairs, and zero answer differences among those three. The
unparsed fourth pair is retained separately, not counted as an answer change
or silently normalized into validity. Against baseline, append has one strict
regression and prepend three, with no strict repairs.

## What remains unresolved

- Correct support references do not ensure the final value is computed from
  those references. All three credit outputs cite R2/R4 and R6 correctly but
  still return the retired-rule result `45_CREDITS`; the current scale is
  five multiplied by three, requiring `15_CREDITS`.
- This does not identify whether the numeric failure originates in arithmetic,
  stale-rule adoption, answer-choice mapping, or another model behavior.
- The prefix contains an existing public instruction/allocation program,
  not the model-generated reasoning traces studied by Trace as State.
- The three reinspection targets are already mandatory in this corpus. This
  run does not identify gradient-based target-selection or allocation value.
- Stable evidence IDs are emitted; stable fact values are not. Preservation
  of those values remains unobserved.

Keep baseline as the engineering reference and do not enable prepend by
default. A next small diagnostic can separate numeric computation from final
label mapping without relaxing the existing contracts. No such follow-up was
executed here.

## Execution and verification

- Lock commit, pushed before execution:
  `c104a9c1296047e4ea48f3d048090f38117eafba`.
- 14 unique logical dispatches, 14 complete generations, 0 automatic retries.
- Literal and task readiness both PASS; four cases admitted per arm.
- All 14 finish reasons are `stop`; none are `length`.
- Native activations and remote provider APIs were not accessed by this run.
- Portable verification: PASS; no model rerun.
- Read-only journal audit: 30 entries; valid hash chain, exact alternating
  dispatch/terminal matches, correct lock/preflight start anchors and final
  artifact fingerprint. Saved terminal payloads equal all 14 result records.
- Regression-only input tokens: baseline 2626, append 3346, prepend 3346.
  Output tokens including terminal tokens: baseline 208, append 205, prepend
  205. Equal totals do not demonstrate equal FLOPs or latency.

Artifact fingerprint:
`fbe70eb242717d29d210e13b5971278cf38000e22916a9d3e70033f2eaf28396`.

File SHA-256 values (before this interpretation was added):

| File | SHA-256 |
| --- | --- |
| results.json | `1ad4b0b367a801fa7f1804683f8f9ec9d37d2070f4634e80b8072e0fe0c08336` |
| journal.jsonl | `79d40a0136a5e2914f41efb4d5ef29a563d45f5894b249cc9a1eda9edee52fae` |
| verification.json | `ea192f6e4f660892cd1c31572dce1a8c30c98951f37eb60c80d9881a66bb0905` |
| report.md | `6480a81c205219e1548a9a5b9cab7ce2315ad439af1780a1a3d3988d3c5e9d19` |

`effect_attribution = NOT_ASSESSED` and
`gradient_allocation_superiority = NOT_ASSESSED` remain unchanged.
