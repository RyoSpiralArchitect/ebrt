# EBRT Model-Interface Core Roadmap

Status: **ACTIVE ENGINEERING AND RESEARCH PLAN**
Current implementation: **v0.7.1 core + v0.8.2 local output corpus**

This roadmap starts where the sealed v0.6 line ends. It does not rewrite those
artifacts or reinterpret their results. The new line separates the backward
revision mechanism from any particular generator.

## North star

EBRT treats test-time reasoning as a revisable trajectory:

```text
forward trajectory
  -> late event
  -> backward credit assignment
  -> bounded intervention
  -> replay or regeneration
```

The core contract is model-interface-agnostic. A state adapter exposes an
explicit trajectory, the core differentiates only through that trajectory, an
actuator adapter compiles bounded credit into a backend-visible operation, and
a model adapter performs generation beyond a stop-gradient boundary.

## Evidence labels

| Label | Meaning |
| --- | --- |
| **IMPLEMENTED + VERIFIED** | Code exists and the named local or network-zero check passed. |
| **CONFORMANCE ONLY** | Interface shape and invariants pass with deterministic doubles; no real backend claim. |
| **DEFERRED** | Designed but not executed because a required backend, credential, or locked evaluation is absent. |
| **RESEARCH TARGET** | A hypothesis requiring a separate protocol and evidence. |

## v0.7 — Model-interface-agnostic backward revision

### v0.7.0 — Protocol extraction

Status: **IMPLEMENTED + VERIFIED** as part of `ebrt_core.py`

- Separate `StateAdapter`, `ActuatorAdapter`, and `ModelAdapter` contracts.
- Bind task-owned trajectory parameters and detach adapter-owned tensor history
  before the EBRT core creates its differentiable control graph.
- Keep model generation outside the autograd graph.
- Keep post-run semantic contracts outside model-visible requests.
- Emit canonical fingerprints and independent mechanism, structural, and
  semantic receipts.

### v0.7.1 — Real local open-weight execution

Status: **IMPLEMENTED + VERIFIED**

- One chronological public trajectory with a literal zero-control identity.
- One real `torch.float64` backward pass and central finite-difference check.
- Bounded L2 control projection with backtracking descent.
- Typed `REINSPECT / SUPPRESS / PRESERVE / REGENERATE` compilation.
- One full-context generation through `MLXLocalAdapter`.
- Verified reference run with
  `mlx-community/Mistral-7B-Instruct-v0.3-4bit`:
  `ANSWER=PROVE`, `SUPPORT=R6,R4,R2`, strict contract `PASS`.

This is a contaminated integration fixture, not evidence of general reasoning
improvement or causal superiority over an uncontrolled regeneration.

### v0.7.2 — External versus native latent actuator

Status: **RESEARCH TARGET**

- Add an open-weight activation/logit adapter with an explicitly admitted
  intervention surface.
- Compare the existing external public actuator with a model-native latent
  actuator under matched tasks, budgets, and decoding.
- Measure whether surrogate credit predicts public output change.
- Do not infer a latent causal effect from projection geometry alone.

## v0.8 — Joint trajectories

### v0.8.0 — Joint public backward block

Status: **IMPLEMENTED + VERIFIED**

- Namespace two or more trajectory lanes.
- Execute one backward pass over the concatenated control block.
- Enforce per-lane and global control budgets.
- Add a fixed shared-axis consensus term.
- Compile one actuator per lane.
- Merge public outputs through deterministic weighted-answer consensus and the
  winning-answer lanes' support union minus invalidated evidence.
- Verify lane-order permutation invariance.
- Execute two real local generations through one shared Mistral runtime.

The verified v0.8.0 run demonstrates multi-lane composition around one local
model. It does **not** establish a heterogeneous multi-model effect.

### v0.8.1 — Selective state oscilloscope

Status: **IMPLEMENTED + VERIFIED**

- Observe selected event-centered public-trajectory windows after optimization.
- Capture bounded scalar and sampled-channel residual summaries at selected MLX
  layers without changing model outputs or feeding observations back into the
  controller.
- Require exact probe-OFF/probe-ON equality and restore original layer objects.
- Treat native measurements as run-local development instruments, not
  cross-model scientific evidence.

### v0.8.2 — Heterogeneous local output-diff corpus

Status: **IMPLEMENTED + VERIFIED; DEVELOPMENT ONLY**

- Execute direct full-context and EBRT credit-first arms across four local model
  snapshots, four cases, and 32 terminal calls.
- Store raw generated text, parsed answer, support lineage, public controller
  receipts, and common post-call grades.
- Require explicit chat-template or plain-text rendering in the model
  descriptor rather than silently guessing.
- Admit only Mistral's four paired cells to algorithm diagnosis; retain the
  other 12 format-failed cells as adapter/capability diagnostics.
- Observe zero answer changes and four support-lineage changes. Do not infer a
  gradient-specific or general reasoning effect from the bundled arm contrast.

### v0.8.3 — Role-stratified provider-uptake canary

Status: **IMPLEMENTED + VERIFIED; MIXED DEVELOPMENT RESULT**

- A pre-call lock fixes three fresh cases, one Mistral snapshot, a 48-token
  ceiling, and a cyclic three-arm schedule with nine terminal calls.
- The public-role coverage floor closes deterministic compiler coverage from
  `1/3` for scalar top-k to `3/3` for the candidate.
- Provider uptake remains `2/3` for both controlled arms, demonstrating that
  complete compilation does not guarantee generated support retention.
- Strict semantic passes remain `2/3` for direct, top-k, and role-stratified
  arms. One candidate output changes `60_UNITS` to the expected `6_UNITS`, but
  omits correction provenance and therefore remains a strict failure.
- The already-covered control case has byte-identical provider prompts and
  outputs across top-k and role-stratified arms.
- Review found that r01 did not bind imported implementation files or require
  a derivable cache identity for the locked model. A pre-call-locked r02
  integrity repetition closes both gaps and reproduces all nine public outputs
  byte-identically. A second review found that revision/path identity did not
  bind the expected blob set. r03 locks all seven snapshot-relative paths,
  sizes, and content-addressed blob hashes and checks them before and after the
  calls. A third review found that this still left a cache-symlink TOCTOU window
  while MLX loaded the model. r04 passes MLX only a private APFS copy-on-write
  tree of the exact locked regular files, requires source-distinct inodes, and
  rehashes the staged tree after all calls. All r01/r02/r03/r04 public outputs
  are byte-identical; none of the integrity repetitions is counted as fresh
  evidence.
- No gradient-specific, causal-superiority, general-reasoning, or cross-model
  claim is admitted from this canary.

### v0.8.4 — Hosted-provider adapters

Status: **CONFORMANCE ONLY; LIVE E2E DEFERRED**

- Bind provider SDKs at the existing `ModelAdapter.generate` edge.
- Keep API credentials and provider receipts outside public artifacts.
- Run fresh sealed E2E blocks only when credentials and provider policy are
  available.
- Never describe a hosted API boundary as differentiable.

## v0.9 — Evaluation and actuator fidelity

Status: **RESEARCH TARGET**

- Construct fresh revision suites with required support, invalidated support,
  distractors, stable facts, and typed terminal contracts.
- Compare no intervention, matched textual revision, matched sham placement,
  external EBRT control, and admitted latent control.
- Measure actuator uptake, strict output quality, lineage integrity, cost, and
  failure modes separately.
- Calibrate whether local surrogate descent transfers to generator behavior.

## v1.0 gate

EBRT reaches a v1.0 research release only after all of the following exist:

1. a stable provider-neutral core protocol;
2. at least two real model backends;
3. matched, fresh evaluation rather than a single contaminated fixture;
4. an explicit actuator-fidelity result, including null outcomes;
5. reproducible receipts and portable verification; and
6. claim language that distinguishes mechanism execution, control uptake, and
   reasoning quality.

## Frozen history

The repository's v0.1-v0.6.3.2 modules, policy locks, reports, and artifacts
remain immutable evidence of the path that produced the current abstraction.
They include both positive and negative results. The active core builds on that
history; it does not silently regrade it.
