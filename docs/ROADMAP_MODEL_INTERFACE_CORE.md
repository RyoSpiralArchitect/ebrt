# EBRT Model-Interface Core Roadmap

Status: **ACTIVE ENGINEERING AND RESEARCH PLAN**
Current implementation: **v0.7.1 core + v0.8.5 typed-state admission diagnostic**

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
  are byte-identical. A fourth review found that the permissive `mlx-lm`
  requirement still left execution semantics unbound. r05 fixes and checks
  the exact Python/platform and local-model distribution versions before and
  after calls. A fifth review found that r04's owner-mode bits were reversible
  and r05's version strings did not bind imported code. r06 loads the exact
  model from an unlinked read-only APFS image and binds installed distribution
  content plus actual imported-module origins and hashes. A sixth review found
  that r06's selected distribution set omitted indirectly imported dependency
  owners and that its portable mount check did not compare against the exact
  lock-derived snapshot fingerprints. r07 binds 3,039 imported file-backed
  non-standard-library modules to 42 full owning-distribution receipts and 10
  repository modules to source receipts, then requires both staged-manifest
  and clone fingerprints to equal the lock. All r01-r07 public outputs are
  byte-identical. A seventh review found that a timestamp-valid generated
  `.pyc` could diverge from its locked source while still being executed. r08
  launches the admitted run before non-standard-library imports with a fresh
  empty `pycache_prefix` and bytecode writes disabled, forcing 2,861 Python
  modules through verified source while retaining content receipts for 189
  native extensions. An eighth review found that automatic outer-interpreter
  site initialization could still run before that bootstrap. r09 requires
  `-E -S` for both outer and child interpreters, manually admits only the two
  locked package roots, and bypasses `.pth`, `sitecustomize`, and
  `usercustomize`. A ninth review found that CPython and stdlib code remained
  outside the receipt. r10 then failed before calls at a historical module-set
  gate; r11 completed nine calls but failed after a legitimate 392-to-397
  stdlib lazy-import expansion. Both failures are preserved. r12 locks the
  complete 1,839-file stdlib Python/native code tree plus the interpreter, then
  verifies the varying imported sets against that stable universe. Its
  portable verifier passes 16/16 checks. All complete r01-r09/r12 public
  outputs are byte-identical. A tenth review distinguished the small CPython
  launcher from the macOS framework implementation. r13 additionally locks the
  13.55MB `Python.framework/Versions/3.13/Python` binary and passes 16/16
  portable checks. All complete r01-r09/r12/r13 public outputs are
  byte-identical; no integrity repetition is counted as fresh evidence.
- Final review localized the remaining integrity boundary to hostile-host
  attestation: dyld loaded-image overrides and concurrent same-user source
  replacement are not excluded by configured-file and pre/post source hashes.
  They are recorded as `NOT_ASSESSED`; this lane stops at a quiescent, trusted
  local host instead of expanding into OS-level isolation.
- No gradient-specific, causal-superiority, general-reasoning, or cross-model
  claim is admitted from this canary.

### v0.8.4 — Typed revision-channel canary

Status: **IMPLEMENTED + VERIFIED; POST-REVIEW INTERPRETATION NARROWED**

- Lock four fresh cases, two exact local instruction-model snapshots, a
  four-arm Williams schedule, and 34 logical calls before execution.
- Cross chronological versus role-stratified control with flat versus typed
  revision-provenance interface packages while keeping the public backward
  objective and controlled program unchanged.
- Preserve a post-review finding that typed-only support-selection guidance
  also changed a scored criterion; field factorization alone is therefore not
  identified by this lock.
- Observe one Mistral strict repair: the typed package restores required `R2`
  and moves correction `R6` from decision support into `REVISION_EVENT`.
- Record `1/4` strict repairs on the sole full-factorial
  algorithm-diagnostic model and `1/8` mechanically across all cells; the
  latter is not a cross-model quality denominator.
- Preserve continued stable-evidence leakage and one Mistral numeric answer
  that stays on the retired rule in all arms.
- Preserve Qwen's `0/8` task-shaped typed parse result as a partial
  adapter/interface diagnostic after its weaker literal-copy readiness probe
  passed; exclude it from algorithm-quality denominators.
- Observe opposite-direction Qwen answer flips under the public control bundle;
  the actuator is non-neutral on this surface but not quality-monotonic.
- Admit no gradient-specific, causal, general-quality, or cross-model claim.

### v0.8.5 — Typed public-state adapter regression

Status: **COMPLETE ADAPTER DIAGNOSTIC; ALGORITHM NOT ASSESSED**

- Separate literal `FORMAT_READY` from a held-out task-shaped
  `TASK_CHANNEL_READY`; only adapters passing both enter regression cells.
- Give decision support, revision provenance, and preserved constraints
  distinct pairwise-disjoint slots in one compact typed public state.
- Keep the core objective, role-stratified program, one-call geometry, and
  portable receipts fixed.
- Give direct and role-controlled arms the exact same output guidance, closing
  the prompt-asymmetry defect found in post-review of v0.8.4.
- Treat v0.8.4 cases as contaminated engineering regression material; this
  iteration cannot provide fresh quality evidence.
- Record `FORMAT_READY=2/2`, `TASK_CHANNEL_READY=0/2`, and zero admitted
  regression cells. Preserve this as a readiness-gate success and complementary
  Mistral/Qwen interface failure atlas, not an algorithm loss.
- Test caller-supplied public evidence-role rendering only in a successor
  namespace with a new lock; do not relax or rerun v0.8.5 r01.
- Do not add stronger gradients, additional lanes, or more model breadth until
  the model-interface boundary closes.

### v0.8.6 — Hosted-provider adapters

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
