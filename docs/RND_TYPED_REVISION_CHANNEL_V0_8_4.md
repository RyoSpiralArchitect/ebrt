# EBRT v0.8.4 — typed revision-channel canary

Status: **COMPLETE DEVELOPMENT CANARY; NOT A BENCHMARK**

Canonical artifact:
[`artifacts/typed_revision_channel_v0_8_4/r01/results.json`](../artifacts/typed_revision_channel_v0_8_4/r01/results.json)

Portable verification:
[`artifacts/typed_revision_channel_v0_8_4/r01/verification.json`](../artifacts/typed_revision_channel_v0_8_4/r01/verification.json)

Post-review interpretation:
[`artifacts/typed_revision_channel_v0_8_4/r01/post_review_interpretation.json`](../artifacts/typed_revision_channel_v0_8_4/r01/post_review_interpretation.json)

Human-readable failure atlas:
[`artifacts/typed_revision_channel_v0_8_4/r01/report.md`](../artifacts/typed_revision_channel_v0_8_4/r01/report.md)

## Post-review correction

The original lock, runner, provider outputs, grades, and portable verification
remain byte-identical. Review found two interpretation defects:

1. the typed prompts uniquely said to exclude stable constraints from
   `SUPPORT`, while the same exclusion was a scored criterion in every arm;
   therefore flat versus typed is a **bundled output-interface and
   support-guidance contrast**, not a pure field-factorization contrast;
2. literal readiness alone admitted Qwen to the original aggregate even though
   none of its eight task-shaped typed outputs parsed. Qwen is now a partial
   adapter/interface diagnostic, not part of the algorithm-quality
   denominator.

The deterministic post-review receipt records two literal-ready models, one
full-factorial algorithm-diagnostic model (Mistral), and one partial
interface-diagnostic model (Qwen). Mechanically graded all-cell totals remain
available but are not interpreted as cross-model quality counts. The frozen
legacy field `results.json.summary.algorithm_diagnostic_models=2` is retained
for artifact identity but superseded for interpretation by the receipt's
corrected count of `1`.

## Why this canary exists

v0.8.3 repaired deterministic compiler coverage: the role-stratified
actuator retained the correction plus both required-support roles in every
case. Provider uptake remained incomplete, especially when the correction
event had to be cited in the same `SUPPORT` field as decision evidence.

v0.8.4 tests one small interface package suggested by that failure. It does
not change the public backward objective, control budget, role-stratified
selection, or number of generation calls. It asks whether correction
provenance becomes easier to retain when it receives a dedicated public output
channel plus the locked typed-only support-selection guidance. Those two
changes are not separately identified in this run.

## Locked 2x2 surface

| Arm | Public control | Output contract |
| --- | --- | --- |
| `direct_flat` | none; chronological full context | `ANSWER`, `SUPPORT` |
| `direct_typed` | none; chronological full context | `ANSWER`, `SUPPORT`, `REVISION_EVENT` |
| `role_flat` | role-stratified control bundle | `ANSWER`, `SUPPORT` |
| `role_typed` | same role-stratified control bundle | `ANSWER`, `SUPPORT`, `REVISION_EVENT` |

The four-arm order follows a four-sequence Williams design. Four fresh cases
were locked before calls. The two exact local snapshots were:

- `mlx-community/Mistral-7B-Instruct-v0.3-4bit@a4b8f...`
- `mlx-community/Qwen2.5-1.5B-Instruct-4bit@8b403...`

Both received one literal three-line readiness call. An admitted model then
received one deterministic call for each of the 16 case-arm cells, with
`temperature=0`, `seed=0`, a 64-token ceiling, and no retry. Semantic gold was
never included in a model prompt.

## Result

The block completed all 34 logical calls and portable verification replayed
all ten receipt classes. The compact aggregate is:

| Arm | Parsed, all cells | Strict pass, all cells | Strict pass, admitted surface |
| --- | ---: | ---: | ---: |
| `direct_flat` | 8/8 | 2/8 | 2/4 |
| `direct_typed` | 4/8 | 0/8 | 0/4 |
| `role_flat` | 8/8 | 0/8 | 0/4 |
| `role_typed` | 4/8 | 1/8 | 1/4 |

The mechanically evaluated controlled flat-to-typed-package output changed in
8/8 cells, but only one cell moved from strict FAIL to strict PASS. The typed
control contrast changed raw output in 7/8 cells. These are public-output
observations, not causal or quality claims. Only Mistral's four fully parsed
cells per arm enter the narrowed algorithm-diagnostic surface.

## What the one strict repair means

For Mistral's archive-tier case, the flat controlled output was:

```text
ANSWER=COLD_TIER
SUPPORT=R6,R4
```

It selected the correct answer but omitted identity evidence `R2`. With the
same role-stratified program and the typed output contract, the model emitted:

```text
ANSWER=COLD_TIER
SUPPORT=R4,R2
REVISION_EVENT=R6
```

That output passed answer, decision-support, invalidation, stable-evidence,
and channel-separation checks. It is a concrete instance where the bundled
typed interface package coincided with repaired provider uptake. The run does
not isolate field factorization from typed-only support guidance. It is one
contaminated development example and must not be generalized.

## What did not improve

### Stable evidence still lacks a public destination

Mistral placed stable evidence `R5` in active decision support in three of four
controlled typed cases. Qwen placed `R5` in all four controlled flat outputs.
The prompt says to preserve `R5` but the output schema offers no preservation
slot. The model is therefore asked to retain information that has nowhere
valid to go.

### Output factorization does not solve answer selection

Mistral returned the retired `45_CREDITS` answer in every numeric-case arm,
including typed control. The output interface cannot substitute for a
fact-local operation that binds the base value, current rule, and correction
event.

### Literal readiness was under-specified

Qwen copied the literal readiness fixture exactly, yet produced zero parseable
task-shaped typed outputs. It often emitted only `ANSWER` and
`REVISION_EVENT`, or repeated fields until the token ceiling. Therefore:

```text
literal schema copy
    !=
task-shaped channel composition
```

This is a readiness-gate defect. Those eight typed format failures are
interface evidence and do not update the EBRT algorithm-quality count.

### The actuator is non-null but not monotonic

On Qwen's raw first-line answers, the control bundle changed freight from the
retired to the corrected answer, while changing permit from the corrected to
the retired answer. This is useful evidence that the provider-visible channel
can alter actual final generation. It is equally clear evidence that the
current actuator does not yet control the direction reliably.

## Engineering decision

The next iteration should stay on the center line:

```text
public backward credit
  -> role-aware bounded actuator
  -> one typed public state contract
  -> one full-context generation
  -> strict output and lineage receipts
```

The smallest successor is a **typed-state adapter regression**, not a new
controller architecture:

1. gate models with a held-out task-shaped composition probe;
2. expose distinct slots for decision support, revision event, and preserved
   constraints;
3. keep one call, the same local backward pass, and the same role-stratified
   selection;
4. preserve Qwen's task-shaped failures as adapter diagnostics;
5. postpone stronger gradients, more lanes, and more model breadth until this
   interface closes.

## Reproduction

Network-zero checks:

```bash
python3 typed_revision_channel_canary_v0_8_4.py self-test
python3 ebrt_core.py self-test
```

Portable artifact verification:

```bash
python3 typed_revision_channel_canary_v0_8_4.py verify \
  artifacts/typed_revision_channel_v0_8_4/r01/results.json \
  --lock policy_lock_typed_revision_channel_v0_8_4.json

python3 interpret_typed_revision_channel_v0_8_4.py verify \
  --source artifacts/typed_revision_channel_v0_8_4/r01/results.json \
  --lock policy_lock_typed_revision_channel_v0_8_4.json \
  --receipt artifacts/typed_revision_channel_v0_8_4/r01/post_review_interpretation.json
```

The run artifact is immutable evidence for this development block. It must not
be overwritten by a repaired adapter or regraded under a relaxed parser.

## Claim boundary

- No gradient crosses either local model.
- The control factor bundles evidence order and explicit revision
  instructions.
- The typed package changes both output shape and typed-only support-selection
  guidance; a pure field-factorization effect is not identified.
- Qwen's typed task-shape failures remain adapter/interface diagnostics and are
  excluded from the narrowed algorithm-quality denominator.
- The cases are synthetic and the run has one deterministic sample per cell.
- No general reasoning improvement, causal superiority, or cross-model
  regularity is claimed.
