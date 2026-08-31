# EBRT v0.8.5 — typed public-state adapter regression

Status: **COMPLETE ADAPTER DIAGNOSTIC; ZERO REGRESSION CELLS; PORTABLE VERIFY PASS**

Runner:
[`typed_public_state_regression_v0_8_5.py`](../typed_public_state_regression_v0_8_5.py)

Pre-call policy lock:
[`policy_lock_typed_public_state_v0_8_5.json`](../policy_lock_typed_public_state_v0_8_5.json)

Canonical result:
[`artifacts/typed_public_state_v0_8_5/r01/results.json`](../artifacts/typed_public_state_v0_8_5/r01/results.json)

Portable verification:
[`artifacts/typed_public_state_v0_8_5/r01/verification.json`](../artifacts/typed_public_state_v0_8_5/r01/verification.json)

Failure atlas:
[`artifacts/typed_public_state_v0_8_5/r01/report.md`](../artifacts/typed_public_state_v0_8_5/r01/report.md)

Lock fingerprint:
`47e2e05077bb115bb58d7e4e5f72fd2d74b42bf3fce5550be9a0d21cfbd8f991`

## Why this regression exists

v0.8.4 exposed two model-interface defects before it exposed a stable
algorithm effect:

1. literal schema copying admitted a Qwen snapshot that parsed none of the
   eight task-shaped typed outputs;
2. stable evidence was required to remain available but had no valid public
   destination outside active decision support.

Post-review also found that v0.8.4's flat and typed prompts differed in scored
support-selection guidance. v0.8.5 therefore does not repeat that schema
contrast. It fixes one typed output contract for every regression arm.

## Single typed public state

Each admitted output must be exactly one `STATE_JSON=<object>` line with four
pairwise-disjoint fields:

```json
{
  "answer": "<one answer choice>",
  "decision_support_ids": ["<evidence that determines answer>"],
  "revision_event_id": "<late correction>",
  "preserved_constraint_ids": ["<stable non-decision constraint>"]
}
```

Duplicate keys, unknown evidence IDs, extra fields, overlapping destinations,
markdown wrappers, and free text fail closed. The direct and role-controlled
arms share one exact output-contract fingerprint:

`5863e855ea986e0e6ba05b54361cdfc366d392e13daa733332709042bab9eb73`

## Two-stage adapter admission

Every exact model snapshot receives two calls before regression cells:

1. `FORMAT_READY`: copy one literal typed-state line exactly;
2. `TASK_CHANNEL_READY`: solve a held-out six-evidence revision task and place
   decision support, correction provenance, and a stable constraint into the
   correct destinations.

Only a model passing both stages executes the contaminated regression cases.
A literal pass followed by a task-channel failure remains an adapter/capability
diagnostic and contributes no algorithm-quality denominator.

## Locked execution geometry

- Models: the same exact Mistral 7B and Qwen 1.5B MLX snapshots as v0.8.4.
- Regression material: the four published v0.8.4 cases.
- Arms: chronological direct typed state and role-controlled typed state.
- Calls: two readiness calls per model, then two calls per contaminated case
  only for admitted models.
- Order: alternating two-arm schedule across the four cases.
- Sampling: temperature `0`, seed `0`, 96-token ceiling.
- Retry: none.
- Native-state capture: disabled.

The role-controlled arm retains the existing public backward output and
role-stratified actuator. It still bundles evidence order and explicit public
revision instructions. This regression does not identify a gradient-only
effect.

## Result

The block completed exactly four readiness calls and stopped before every
contaminated regression cell:

| Model | `FORMAT_READY` | `TASK_CHANNEL_READY` | Regression cells |
| --- | ---: | ---: | ---: |
| Mistral 7B | PASS | FAIL | 0 |
| Qwen 1.5B | PASS | FAIL | 0 |

Mistral emitted an exactly parseable state with correct `R2,R4` decision
support and `R6` revision provenance, but kept the retired `GATE_RED` answer
and added context `R1` beside stable `R5`. Qwen emitted the corrected
`GATE_BLUE` answer with exact `R6` and `R5`, but omitted identity evidence
`R2` from decision support.

Therefore:

```text
literal format readiness:       2/2
task-shaped channel readiness:  0/2
algorithm-quality denominator:  0
```

The gate worked as intended. This block says nothing about direct versus EBRT
quality because neither model was admitted to those cells.

The next bounded question is whether the adapter should render the
caller-supplied public evidence roles already present in `RevisionTask` rather
than asking the generator to reconstruct those roles from raw text inside an
adapter-readiness test. That requires a successor namespace and fresh lock;
r01 is not rerun or relaxed.

## Network-zero checks

```bash
python3 typed_public_state_regression_v0_8_5.py self-test
python3 typed_public_state_regression_v0_8_5.py lock-spec
python3 ebrt_core.py self-test

python3 typed_public_state_regression_v0_8_5.py verify \
  artifacts/typed_public_state_v0_8_5/r01/results.json \
  --lock policy_lock_typed_public_state_v0_8_5.json
```

The runner self-test includes one admitted scripted adapter, one task-channel
diagnostic adapter with zero regression cells, exact arm-shared output
guidance, strict state-parser rejection cases, grade replay, and portable
artifact verification.

## Claim boundary

- This is contaminated engineering regression, not fresh quality evidence.
- No semantic gold appears in a model prompt.
- Public state fields are adapter outputs, not private reasoning states.
- No gradient crosses either local model.
- Strict output quality, provider uptake, and raw output differences remain
  separate receipts.
- Because no model passed admission, algorithm quality and provider uptake are
  `NOT_ASSESSED`, not zero-performance results.
- No causal superiority, general reasoning improvement, or cross-model
  regularity is claimed.
