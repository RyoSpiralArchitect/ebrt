# EBRT v0.8.5 typed public-state adapter regression

Status: **COMPLETE ADAPTER-ADMISSION BLOCK; PORTABLE VERIFICATION PASS**

Algorithm status: **NOT ASSESSED — ZERO REGRESSION CELLS ADMITTED**

The locked block executed four logical local-model calls: one literal format
probe and one held-out task-shaped channel probe for each of two exact local
snapshots. Both models passed literal formatting and failed task-shaped
composition, so the fail-closed runner made no contaminated regression call.

## Aggregate

| Measurement | Result |
| --- | ---: |
| Exact model snapshots | 2 |
| Logical calls | 4 |
| `FORMAT_READY` | 2/2 |
| `TASK_CHANNEL_READY` | 0/2 |
| Models admitted to regression | 0/2 |
| Regression calls | 0 |
| Algorithm-quality denominator | 0 |

This is a successful readiness-gate diagnostic, not a failed algorithm run.

## Mistral diagnostic

Observed public output:

```text
STATE_JSON={"answer":"GATE_RED","decision_support_ids":["R2","R4"],"revision_event_id":"R6","preserved_constraint_ids":["R1","R5"]}
```

Passed:

- strict parsing;
- exact decision support `R2,R4`;
- exact revision event `R6`;
- forbidden-evidence exclusion and channel disjointness.

Failed:

- retained the retired answer `GATE_RED` instead of `GATE_BLUE`;
- over-assigned context `R1` to preserved constraints, whose exact target was
  stable evidence `R5` only.

## Qwen diagnostic

Observed public output:

```text
STATE_JSON={"answer":"GATE_BLUE","decision_support_ids":["R4"],"preserved_constraint_ids":["R5"],"revision_event_id":"R6"}
```

Passed:

- strict parsing;
- corrected answer `GATE_BLUE`;
- exact revision event `R6`;
- exact preserved constraint `R5`;
- forbidden-evidence exclusion and channel disjointness.

Failed:

- omitted identity evidence `R2` from decision support.

## Interpretation

The two failures are complementary. Mistral formed the required support set
but did not bind it to the corrected answer. Qwen selected the corrected answer
but under-factorized its decision lineage. A literal output probe would have
admitted both, reproducing v0.8.4's gate defect. The held-out task-shaped gate
correctly stopped both before algorithm-quality cells.

The current readiness prompt exposes evidence text but not the caller-supplied
public evidence roles already present in `RevisionTask`. The next bounded
adapter iteration should test whether rendering those typed roles closes the
composition boundary. It must use a successor namespace and new pre-call lock;
this r01 artifact remains unchanged.

## Receipts

- Pre-call lock commit: `81fd786`
- Policy-lock fingerprint:
  `47e2e05077bb115bb58d7e4e5f72fd2d74b42bf3fce5550be9a0d21cfbd8f991`
- Results fingerprint:
  `6c7ced068b2d1ae6e764ecc06e8c658df4af582eb940d624894781d532546cab`
- Results file SHA-256:
  `3372933e91c6ef061eaf65e7115ffd2e82a689d6ada75395c9f410ad86afaea6`
- Portable verification fingerprint:
  `83759763795294197aaf726ac038f7c14c270e4bee369ccd312eee531132170b`

## Claim boundary

- The four published v0.8.4 cases received zero calls in this block.
- No algorithm-quality result, provider-uptake result, or direct/control
  comparison is available.
- The readiness outputs are public adapter artifacts, not private reasoning
  states.
- No gradient crossed either model.
- No causal, general-quality, or cross-model claim is admitted.
