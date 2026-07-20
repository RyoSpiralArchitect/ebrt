# EBRT v0.6.3-live-r01 — Frozen terminal result

Status: **EXECUTED ONCE; VALID TERMINAL ARTIFACT; STOP_OUTPUT_CONTRACT; NO RERUN**

The preregistered namespace ran once on 2026-07-20 after PR #22 was merged.
The annotated authorization tag `v0.6.3-live-r01-authorized` records tag object
`eb76d2573073f34b020de8b37d877cf6670f917b` over execution commit
`012791fc942107bf442e5db91be197a803ced599`.

## Terminal decision

| Field | Observed |
| --- | --- |
| Run status | `INCOMPLETE` |
| Terminal status | `STOP_OUTPUT_CONTRACT` |
| Decision reason | `PUBLIC_OUTPUT_COMPILER_REJECTED` |
| Local compiler reason | `EXACT_ONE_CLOSURE_FAILED` |
| Provider calls | 1 of the authorized maximum 16 |
| Unattempted calls | 15 |
| Gold loaded | false |
| Effect endpoints | not assessed |
| Secondary quality | not assessed |

The provider call itself completed successfully. Its exact usage was 1,621
input tokens, 230 output tokens, 103 reasoning tokens, 1,851 total tokens, and
8,848.18 ms at the recorded boundary. The runner did not retry or continue.

## What the Inspector caught

The first fixed arm was the `Z` baseline for `relay_bay_revision_a`. The public
output emitted:

```text
current_answer: BLUE
primary_decision: BLUE_BAY
stable_constraint: SIGNED_JSON
reviewed evidence: E1, E2, E3
selected edges: C01, C02, C03, C09, C10, C11
```

The output included one base support route, stable-support edges, and the
required invalidation edge. It did not select `C07` and `C08`, the public
correction-support route from `E6` into the primary fact. Consequently the
locally derived active support did not equal exactly one allowed closure and
the unchanged compiler rejected it with `EXACT_ONE_CLOSURE_FAILED`.

This is an output-contract stop, not a negative actuator-effect result. X/Z
propagation and D/C gradient placement were never evaluated. The emitted answer
and slots are visible public outputs, but semantic correctness was not graded
because the fixed block did not complete and gold remained unloaded.

## Frozen artifacts

- Result fingerprint:
  `52b3878b877d7c006d7521d98de4ee3ce398cd5b279e577fe1bd9eebbd168a29`
- Manifest bytes SHA-256:
  `4bf105c325a800f9108262caaf6133f2d15be1c0353b61f8c0eaba37ed1309aa`
- Canonical directory:
  [`artifacts/actuator_calibration_v0_6_3_live_r01`](../artifacts/actuator_calibration_v0_6_3_live_r01)
- Portable verifier:
  [`verify_actuator_calibration_v0_6_3_live_r01.py`](../verify_actuator_calibration_v0_6_3_live_r01.py)

Network-zero validation:

```bash
python3 run_actuator_calibration_v0_6_3_live_r01.py validate
python3 verify_actuator_calibration_v0_6_3_live_r01.py
```

The first command independently rederives the frozen runner contract with its
pinned dependencies. The second is a pure-standard-library byte and terminal
receipt verifier suitable for a copied artifact. Both reject artifact drift;
neither contacts the provider.

The generated `report.md` is preserved byte-for-byte and therefore shows only
the frozen public decision reason. The exact compiler reason, attempt count,
unattempted count, gold status, and no-rerun interpretation are carried by
`result.json`, the ledgers, and this post-run note; the generated report was not
edited after execution.

## Decision boundary

The r01 namespace is consumed. Do not retry, resume, backfill, loosen the
closure contract, or reinterpret this as a control-effect null. v0.6.4 remains
blocked because its promotion gate was not reached. Any future attempt to study
provider uptake must use a new version, a newly preregistered namespace, and an
explicit hypothesis about public closure construction rather than modifying
this result.

The receipts remain operator-attested local records. They are not
cryptographically authenticated provider proof, do not authenticate operator
identity, and do not establish hidden-state editing, causal superiority,
quality improvement, population reliability, or general reasoning improvement.
