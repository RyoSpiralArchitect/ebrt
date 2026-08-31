# EBRT v0.8.5.2 — exact public-role isolation

Status: `COMPLETE_WITH_BOUNDED_ADAPTER_ADMISSION`.

## Question

Does transporting the caller-supplied public `Evidence.role` field across the
model-adapter boundary remain associated with the known task-channel repair
when the unintended v0.8.5.1 adapter-label wording change is removed?

This is a contaminated engineering regression over one known readiness failure
and four published cases. It is not a fresh benchmark.

## Single model-visible delta

The v0.8.5.2 prompt restores the exact v0.8.5 adapter label:

```text
You are a full-context generator behind the EBRT typed-state adapter.
```

Each model-visible evidence record additionally carries the already-public
caller-supplied role:

```json
{"evidence_id":"R2","role":"required_support","text":"..."}
```

The pre-call hard gate removes only `role` from each `EVIDENCE_JSON` record and
then compares complete prompt bytes with v0.8.5. It must pass for task-channel
readiness and both arms of all four cases: 9/9 exact comparisons.

## Frozen geometry

- Models: the same exact Mistral-7B-Instruct-v0.3-4bit and
  Qwen2.5-1.5B-Instruct-4bit snapshots as v0.8.5 and v0.8.5.1.
- Readiness: literal format call, then one task-shaped call per model.
- Admission: only a model passing both readiness gates enters regression cells.
- Regression: four known cases, direct and role-controlled arms, one sample per
  cell, alternating arm order.
- Sampling: temperature `0.0`, seed `0`, maximum `96` generated tokens.
- Automatic retry: disabled.
- Native-state capture: disabled.

The policy lock contains the exact runner and dependency hashes, the nine
prompt-projection receipts, model identities, schedule, and contract
fingerprints. The lock is committed and pushed before any model call.

## Interpretation boundary

- Roles are caller-supplied scaffold metadata, not dependencies discovered by
  EBRT or by a model.
- Removing the role field reproduces the v0.8.5 model-visible prompt exactly;
  this isolates the interface field within this frozen implementation.
- Semantic gold remains post-call grading material and is absent from prompts.
- Direct versus controlled still bundles evidence ordering and explicit public
  revision instructions.
- No gradient crosses a model adapter.
- One deterministic sample over contaminated cases cannot establish causal
  superiority, general reasoning improvement, or cross-model regularity.

## Commands

```bash
python3 -m ruff check public_role_transport_isolation_v0_8_5_2.py
python3 public_role_transport_isolation_v0_8_5_2.py self-test
python3 public_role_transport_isolation_v0_8_5_2.py lock-spec \
  --output policy_lock_public_role_transport_isolation_v0_8_5_2.json
```

The live one-shot command is authorized only after the generated lock and
runner are present in a pushed commit. A failed or null result is preserved as
first-class evidence and is not retried under this namespace.

## r01 result

The lock was pushed in commit `11ff6f5` before execution. The single run used
12 logical calls with no retry.

- Full prompt projection: `9 / 9` exact after deleting only `role`.
- Mistral task readiness: v0.8.5 `FAIL` to v0.8.5.2 `PASS`.
- Qwen task readiness: v0.8.5 `FAIL` to v0.8.5.2 `FAIL` (required support
  `R2` remained absent).
- Mistral strict regression: `3 / 4` direct and `3 / 4` controlled.
- Strict repairs / regressions: `0 / 0`.
- Direct/control raw differences: `3 / 4`.
- Direct/control normalized public-state differences: `0 / 4`.
- Direct/control answer differences: `0 / 4`.

The isolated role field is associated with one contaminated model's known
readiness repair, while causal attribution remains `NOT_ASSESSED`. The
direct/control semantic effect is `NULL_ON_ADMITTED_CELLS`.

See
[`artifacts/public_role_transport_isolation_v0_8_5_2/r01/report.md`](../artifacts/public_role_transport_isolation_v0_8_5_2/r01/report.md)
for exact outputs, hashes, and claim boundaries.
