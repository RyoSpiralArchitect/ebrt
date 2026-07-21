# EBRT

**Event-driven Backward Reasoning for Test-Time Inference**

## Current product — Apply Revision Runtime Preview 4

**Try the sealed public Live demo:**
[ebrt-apply-revision.ryospiralreality.chatgpt.site](https://ebrt-apply-revision.ryospiralreality.chatgpt.site/)

EBRT gives developers an external, inspectable revision layer for hosted
models whose internal reasoning state is not editable. It rolls a typed public
reasoning trajectory forward, computes one bounded local backward-credit step,
replays the revised public trajectory, compiles the result into an executable
`Reinspect / Suppress / Preserve` operation, regenerates once from full
context, and verifies the public output diff and evidence lineage.

```text
Before public state + late event
  -> chronological public trajectory
  -> public surrogate loss
  -> one local float64 backward()
  -> bounded controls + forward replay
  -> compiled Apply Revision actuator
  -> one full-context regeneration
  -> After diff + structural verification
```

### 30-second judge path (network-zero)

After installing the product dependencies, this scripted path exercises the
same request validation, trajectory controller, actuator, output projection,
and verification surfaces without an API key or network call:

```bash
python3 -m pip install -r requirements-product.txt
python3 ebrt_live.py self-test
python3 ebrt_live.py apply-demo --provider scripted
```

The built-in example is an explicitly contaminated product fixture. Its
`POLISH -> PROVE` diff demonstrates operational plumbing, not model quality or
causal control.

### Public interactive Reasoning IDE

The public Sites build exposes both **Live** and **Recorded** modes. Live keeps
the browser on a same-origin `/api/` surface: a small Sites Worker validates
that the POST matches the fresh, server-owned sealed demo request, derives an
opaque anonymous client key, and relays the bytes to the existing loopback
Python monolith through an authenticated HTTPS Quick Tunnel. The monolith then
executes the real `torch.float64` backward pass and exactly one no-retry
`gpt-5.6-sol` full-context regeneration. Provider credentials never enter the
browser, Worker response, or repository.

The public Apply POST accepts only the sealed demo case; the arbitrary-input
Protocol Editor remains local. Its configured provider-attempt budgets are 32
globally and 2 per anonymous client for the lifetime of the backend process.
Recorded mode remains a zero-call fallback over the committed acceptance
artifact. The Quick Tunnel is a temporary demo bridge with no uptime or
production-service guarantee.

### Full local Reasoning IDE

Terminal 1:

```bash
python3 ebrt_live.py serve --provider scripted --host 127.0.0.1 --port 8765
```

Terminal 2:

```bash
cd inspector
pnpm install --frozen-lockfile
pnpm dev
```

Open `http://127.0.0.1:5173`, switch to **Live**, then choose
**Apply Revision -> Regenerate**. To use the real provider boundary, set
`OPENAI_API_KEY` only in the backend environment and replace `scripted` with
`openai`; credentials never enter the browser or public response.

Choose **Editor** to paste or edit any complete `v0.6.2.5` public revision
request. The Editor starts empty, only loads the contaminated sample on an
explicit click, retains caller text in memory only, and submits through the
same fail-closed backend validator. Caller-supplied semantics and causal effect
remain `NOT_ASSESSED`.

Protocol `v0.6.2.5` makes zero temporal control a literal no-op over typed
event proposals: the uncontrolled path follows only the frozen forward
recurrence. Its reversed eligible-time sham now matches the signed control
multiset, L2 norm, control cost, and eligible-domain smoothness. That local
comparison is sealed as a `POSITIVE / NON_POSITIVE / UNAVAILABLE_DEGENERATE /
INVALID_GEOMETRY` research
diagnostic and never gates product execution. The backward pass allocates
where and how much to reinspect; typed-event compilation supplies the
allowlisted suppress/preserve semantics.

### Public Live bridge setup

Set these names only in the backend process environment:

- `OPENAI_API_KEY`
- `EBRT_RELAY_TOKEN`
- `EBRT_RELAY_MAX_PROVIDER_ATTEMPTS_TOTAL`
- `EBRT_RELAY_MAX_PROVIDER_ATTEMPTS_PER_CLIENT`

Start the loopback monolith and expose that loopback port through a temporary
HTTPS Quick Tunnel:

```bash
python3 ebrt_live.py serve --provider openai --host 127.0.0.1 --port 8765
cloudflared tunnel --url http://127.0.0.1:8765
```

Configure the Sites Worker with these environment names (the relay-token value
must match the backend):

- `EBRT_BACKEND_URL`
- `EBRT_CLIENT_KEY_SECRET`
- `EBRT_RELAY_TOKEN`

Then verify and stage the public build:

```bash
cd inspector
pnpm test:worker
pnpm build:public-live
```

`EBRT_BACKEND_URL` is the HTTPS Quick Tunnel origin. Do not commit any value.
The public deployment is deliberately a sealed-case, rate-bounded demo bridge,
not a general remote execution API.

### Runtime, model, and claim boundary

- **Supported local runtime:** CPython 3.11+, PyTorch 2.x, and a CPU. The
  committed runs were produced on macOS arm64; POSIX Linux is an intended
  local target but cross-platform byte identity is not claimed. The Inspector
  uses Node.js `^20.19.0` or `>=22.12.0` and pnpm. Windows and remote,
  multi-process hosting are not validated in this preview.
- **GPT-5.6 role:** `gpt-5.6-sol` performs the one structured, full-context
  After regeneration at a non-differentiable provider boundary. It is not
  trained, differentiated, or used as the local trajectory state.
- **Codex role:** Codex collaborated on implementation, adversarial tests,
  artifact validation, review repair, documentation, and the Reasoning IDE.
  Codex is not a runtime dependency and does not decide semantic correctness.
- **Exact claim:** EBRT implements an executable, observable, and verifiable
  external public revision operation. It does **not** edit GPT hidden states,
  attention, KV cache, or private chain-of-thought; send gradients through GPT
  or JSON; or establish provider uptake, causal superiority, semantic quality,
  or general reasoning improvement. Those effect and quality axes remain
  `NOT_ASSESSED`. The public web demo remotely invokes the same loopback
  monolith only through the sealed, authenticated, budgeted Quick Tunnel
  bridge; this establishes neither production readiness nor an uptime claim.

Submission copy and the final video checklist live in
[`SUBMISSION.md`](SUBMISSION.md). The complete, immutable research history
continues below.

EBRT v0.1 is an executable mechanism proof for a simple question: can a
reasoning process detect a structured change, route a bounded revision to an
earlier state, replay only the affected suffix, and leave an audit trail?

The repository deliberately starts small. The frozen monolith demonstrates the
mechanism over structured toy states, while a separate benchmark measures when
backward routing helps, when it does not, and what it costs.

EBRT v0.2 keeps that mechanism frozen and adds counterfactual instrumentation.
For each revision it separates the semantic reason to revisit an earlier state
from where one tested local control direction most changes the event-source
belief projection.
The purpose is to discover stronger routers, replay policies, and revision
objectives—not merely to attach an explanation after execution.

EBRT v0.3 prospectively implemented the resulting dual-route hypothesis under
a frozen five-arm, one-shot holdout protocol. Attempt 1 terminated on a
predeclared matched/native replay-invariance assertion, before a validated
result bundle was written. That terminal result reveals that the
trajectory-anchor loss horizon changed when one variable also set the physical
replay start; it does not rank the dual and control arms on quality.

EBRT v0.3.1 keeps that terminal evidence immutable and factorizes the coupled
variable. Physical suffix recomputation now uses `execution_replay_floor`,
while trajectory regularization uses `trajectory_anchor_floor`. A DEV-only
cost lane changes the former and requires exact outcomes; a separate causal
factorial changes the latter while keeping routing and generator work fixed.

EBRT v0.4 adds the first live Language Replay Bridge. GPT-5.6 produces compact
public Reasoning Cards, observes late evidence through a strict semantic
schema, freezes a pre-outcome replay plan, and regenerates only a selected
public suffix. A matched two-case DEV canary compares card-only continuation,
full restart, and selective replay with exact API usage and independent gold.
After closing observer and citation side channels, it exposes a concrete
interaction between invalidated-anchor routing and public-state sufficiency.

A subsequent 10-case × 3-trial calibration now tests that public-card scaffold
against one stateless call over all raw evidence after the same fixed revision
annotation. Direct passed 30/30 strict outputs; staged Full passed 4/30, with no
Full-only win. This freezes a useful negative result: repair or bypass lossy
public-state factorization before investing further in selective replay.

EBRT v0.4.1 adds the two missing same-block controls: a one-shot raw arm with
no revision envelope, and a staged arm that retains the cumulative raw prefix.
It also adds a provisional local, read-only Inspector over normalized recorded
artifacts. The Inspector is an observation-contract experiment, not a freeze of
the eventual frontend, navigation, brand, or hosting model.

The locked 30-run attempt produced a strong but non-decision-ready trend:
cumulative-raw staging passed 30/30 strict outputs versus 2/28 completed
card-only outputs. Two card-only runs stopped on a local contract error, so the
manifest is `INCOMPLETE` and the preregistered cause conclusion remains closed.

EBRT v0.4.2 prospectively added stable local-validator reason codes and treated
allowlisted post-response rejections as assessed strict failures. Its passing
contract smoke launched one fresh full block. That block again produced 30/30
cumulative-raw strict successes and 2/30 card-only successes, but one API
timeout and one SDK structured-output parse failure made two four-arm runs
non-assessable. The new instrumentation separately identified one
`invalidated_active_support` terminal rejection. The successor artifact is
therefore also preserved as `INCOMPLETE`, without rerun or partial fill.

EBRT v0.4.3 adds a prospective provider-boundary receipt around the unchanged
v0.4.2/r01 reasoning protocol. Its one-shot contract smoke recorded eight HTTP
429 `insufficient_quota` failures and classified all 8/8 at the native
phase/reason boundary. Diagnostic integrity passed, but the zero-provider-
failure launch gate correctly prevented the full block. No v0.4.3 reasoning
comparison exists. A post-freeze correction changes only an inherited derived
coverage field, with explicit lineage; calls, traces, receipts, failure labels,
and the closed launch/decision gates remain unchanged.

EBRT v0.4.4 turns the accumulated evidence into a provisional **Recorded
Revision Workbench**. A deterministic allowlist projection shows one complete
public episode from Evidence through Event, Revision, every Replay lane, and
the final public-card diff. A separate Provider Failure Atlas shows where the
v0.4.3 runtime episode stopped. The UI is still read-only and replaceable: its
playback control reveals recorded public cards and makes no model call.

EBRT v0.5.0 begins the algorithmic mainline rebuild. It freezes a typed,
one-hop public dependency graph, optimizes bounded scalar evidence gates with
real float64 autograd inside a local surrogate, and emits a deterministic
public control map. A built-in synthetic graph, isomorphic to the locked event
topology, verifies terminal credit, finite-difference agreement,
locked-topology locality, disconnected-padding invariance, and bounded control.
The external triggered fixture reproduces an accepted objective decrease and
canonical map; a separate no-event fixture is exact identity with zero backward
calls. This is a synthetic oracle mechanism result, not yet a GPT generation
or reasoning-quality result.

The experimental v0.5-T branch adds time-indexed public state transitions
without changing v0.5.0. Exact local adjoints allocate either evidence-leaf or
transition-basis controls through a smooth frozen recurrence. On one synthetic
oracle topology and its eight-cell parameter sweep, the transition arm reduced
aggregate terminal task loss by 44.61% versus the leaf arm and beat every
nonidentity floor permutation. The same evidence moved the top finite-leverage
transition from `decision_write` to `revision_mix` when correction order
changed. This is a supplied-actuator mechanism record: terminal Jacobian scales
are not matched, the cells are not independent replications, and no GPT output
is generated.

EBRT v0.5.1 builds the first horizontal bridge from that temporal control map
to one full-context regeneration. It freezes raw-only, textual-only,
gradient-controlled, and norm-matched permutation arms; provider-visible C/D
payloads differ only in control placement. The first preregistered four-call
block is preserved as `INCOMPLETE_CANARY`: all four attempts received HTTP 429
`insufficient_quota` before response parsing. The local surrogate decreased its
declared objective, but no public card, strict grade, output diff, or arm-quality
comparison exists. A separately named quota-recovery block then completed 4/4
calls and all four arms passed strictly, but their public cards were exactly
identical. The bridge therefore completed with a null observed output effect on
this saturated DEV case; no controlled advantage is established.

EBRT v0.5.2 adds a separate English, two-call product walkthrough rather than
retuning that null result. Under the R1-R5 horizon, GPT-5.6 emitted `POLISH`;
after R6 superseded R3, one controlled full-context regeneration emitted
`PROVE`, dropped and invalidated R3, added R4/R6 support, and preserved the
three-minute video fact. The block completed 2/2 calls with retry disabled, but
the locked walkthrough contract is a strict near-pass, not a pass: the final
card failed only `required_facts_exact` because R2/R4/R6 were present globally
but not repeated on both changed decision facts. The artifact is preserved
without rerun or post-hoc grading relaxation. The merged checkpoint is retained
as `v0.5.2-inspector-breakpoint`.

EBRT v0.5.3 now completes a network-zero factorized-lineage regression. Its
lossless migration reproduces the same two fact-local gaps while preserving the
frozen v0.5.2 `false` verdict. A separately hashed, explicitly contaminated
two-edge repair then closes exactly `final_priority:+R4` and
`demo_centerpiece:+R2`, with no other reachability or direct/inherited
classification change. The repaired local closure is `PASS`; this is a
public-representation engineering result, not a new hosted-model result.

EBRT v0.5.4 now compiles that sealed dependency program into a float64 public
temporal recurrence. Under one matched normalized-control budget, the exact
time-local adjoint arm is strictly below zero control, its node-tied projection,
and every locked within-node timing permutation for both mechanically derived
evidence schedules. Manual forward and reverse derivatives agree exactly with
autograd, finite differences agree within `1.24e-10`, all 17 hard gates pass,
and the sealed decision is `PROMOTE_V0_5_5_TEMPORAL_GATE`. This is a
contaminated network-zero mechanism result over one supplied public program,
not fresh benchmark or hosted-model evidence.

EBRT v0.5.5 now composes the three byte-sealed v0.5.4 lanes through one
mechanically generated typed incidence junction. A shared R1-R6 evidence
ledger is bound once by canonical payload hashes; the two Fact lanes retain
their local schedules and controls, while the stable Constraint lane remains
exactly disconnected. The one-lane bundle degenerates byte-exactly to the
source v0.5.4 C control map, all six three-lane input orders produce the same
full result bytes, and the explicit block adjoint agrees with full autograd to
`2.22e-16` and central finite differences to `1.24e-9`. All 10 top-level gates
and 10 required adversarial subchecks pass, yielding
`PROMOTE_V0_6_LANE_COMPOSITION_GATE`. This is still a contaminated,
network-zero public-substrate result: no model, agent, router, tool, generated
answer, or multi-agent quality comparison participated.

EBRT v0.6.1 now completes the first preregistered five-call hosted bundle in
the fixed order `P/A/B/D/C`. All five GPT-5.6 calls and the independent
artifact validator completed. D carried the exact v0.5.5 public control map
through full-context regeneration and passed the strict final answer,
invalidation, stable-fact, and fact-local lineage contract. The overall gate is
nevertheless `HOLD_V0_6_HOSTED_BUNDLE_GATE`: P returned the correct `POLISH`
answer but added an unexpected inherited R2 dependency, and the matched
placement comparison was null because B, D, and C returned byte-identical
passing public outputs. Raw arm A returned the correct `PROVE` answer but
omitted R4 from `final_priority`. This is a real bridge and a useful control-
channel null result, not evidence that gradient placement improves GPT.

### EBRT Runtime Preview 4 — zero-centered revisable public trajectory

The current live product monolith is [`ebrt_live.py`](ebrt_live.py). It accepts
a typed public invalidation-revision request containing the case and ordered
evidence, an already emitted Before state and its selected closure graph, a typed late event,
and at least two structurally distinct After closure candidates. It validates
that public surface as a single-late-event horizon (the declared correction
must be the final visible evidence), then rolls a three-axis public revision
trajectory forward over the ordered evidence. One projected float64
`backward()` step assigns credit to bounded time-local controls, after which
the declared transition is rolled forward again. Control magnitude is decoded
into a fixed abstract review budget and ordered
`Reinspect` steps, and typed-event `Suppress / Preserve` steps. A deterministic
state machine executes and seals the complete public revision program before
candidate IDs are remapped to server-generated opaque hashes and exactly one
After provider attempt is allowed for each new request identity.

This is a new operational runtime, not a mutable continuation of the sealed
acceptance runner. Root [`ebrt.py`](ebrt.py), its v0.6.2.1 policy surface, and
the canonical v0.6.2.1 artifact remain immutable. The live runtime does not
load a separate semantic-gold or grader artifact and does not grade general
answer quality. Reserved gold fields are rejected, while arbitrary caller text
remains semantically unverified. Its response
keeps mechanism, public output, and verification separate; semantic quality
and effect attribution remain `NOT_ASSESSED`.

Run the offline contract and contaminated demo adapter without a provider:

```bash
python3 -m pip install -r requirements-product.txt
python3 ebrt_live.py self-test
python3 ebrt_live.py demo-request
python3 ebrt_live.py apply-demo --provider scripted
```

With `OPENAI_API_KEY` supplied only through the server environment, exercise
the same public operation through the live provider boundary:

```bash
python3 ebrt_live.py apply-demo --provider openai
python3 ebrt_live.py serve --provider openai --host 127.0.0.1 --port 8765
```

The loopback server also supports a fully offline scripted mode:

```bash
python3 ebrt_live.py serve --provider scripted --host 127.0.0.1 --port 8765
```

Its bounded API surface is `GET /api/health`, `GET /api/capabilities`,
`GET /api/demo-request`, and `POST /api/apply-revision`. The demo request is a
server-owned adapter over the known v0.6.2.1 case; it is contaminated product
plumbing, not a benchmark, and that provenance is derived server-side from the
published manifest bytes and provider-input bytes, not merely from a
self-consistent embedded hash. Its envelope seals the exact request. Before the
Live UI renders a result, it recomputes that request fingerprint, binds response
provenance back to the envelope, verifies the API response-body SHA-256,
recomputes the live response self-seal without normalizing away numeric lexemes, and
enforces the pinned operational status graph plus two exact
`NOT_ASSESSED` rows. These hashes are integrity/correlation checks inside the
trusted loopback deployment, not signatures or remote-server authentication.
Request IDs terminally bind both successful and failed attempts; provider
retries are disabled. The session keeps 128 complete terminal responses in an
LRU cache plus compact fingerprints for up to 65,536 spent identities. An
identity whose full result has been evicted returns `410` and is never executed
again; the service safely rejects new identities if the compact ledger fills.
Provider credentials, raw receipts, reserved gold fields, and private reasoning
never enter the public response. Zero-control and revised public trajectories,
trajectory-wide objectives, time-local controls, central finite-difference
diagnostics, and continuous allocations are intentionally returned as Inspector
data. The nonterminal path term uses a role-blind, graph-incidence-derived
full-admission support envelope; it does not contain an answer, target value,
accepted closure ID, or semantic gold. Only the compiled public review
allocation—not states, gradients, losses, or source effects—enters provider
input. Inspection units are not provider tokens or attention weights, and
provider uptake remains `NOT_ASSESSED`.

The network-zero contract rederives the finite differences, projected update,
backtracking decision, zero-control/revised replay, matched temporal sham, and exact
trajectory-to-actuator binding from the public request. It also requires an
active nonterminal path loss, exact typed-event zero-control no-op, exact
no-event identity, and rejection of both
ordinary and coherently resealed scientific-receipt tampering before any
provider call. See
[`RND_TEMPORAL_PUBLIC_TRAJECTORY_V0_6_2_5.md`](docs/RND_TEMPORAL_PUBLIC_TRAJECTORY_V0_6_2_5.md).

Runtime Preview 4 has no new hosted-effect result. Its product gate is
independent of whether the local smoothness-matched sham diagnostic is
`POSITIVE`, `NON_POSITIVE`, or unavailable. The historical Preview 2
delivery canary exercised the v0.6.2.3 payload after its network-zero and
Inspector gates passed. It completed one explicit no-retry GPT-5.6 API attempt
in 6.32 seconds with 2,820 input and 150 output tokens, returned
`POLISH -> PROVE`, and passed actuator execution, provider delivery, public
structural dependency, and operational acceptance. That contaminated,
unmatched run remains contract-compatibility evidence only: provider uptake,
semantic quality, and effect attribution are `NOT_ASSESSED`.

### v0.6.2.1 immutable Apply Revision acceptance

EBRT now converges the product path into one executable,
[`ebrt.py`](ebrt.py). It takes an actual typed Before output, runs one local
float64 backward pass over an actual-Before-conditioned public surrogate,
compiles a bounded `Reinspect / Suppress / Preserve` operation, and performs
one dependent full-context regeneration. The hosted model is not
differentiated, and semantic gold is parsed only after two structurally valid
provider terminals exist.

The frozen acceptance case is intentionally contaminated and case-specific.
Its purpose is to test whether `Apply Revision -> Regenerate` is executable,
observable, and strictly verifiable—not whether the control caused an
improvement. Therefore every result keeps
`effect_attribution_status = NOT_ASSESSED`.

Run the network-zero contract checks:

```bash
python3 ebrt.py self-test
python3 ebrt.py preflight
```

The sealed contract, post-call-only gold, and UI concept are documented in
[`RND_APPLY_REVISION_ACCEPTANCE_V0_6_2_1.md`](docs/RND_APPLY_REVISION_ACCEPTANCE_V0_6_2_1.md).
The separately authorized live r01 then completed its exact two calls without
retry. The actual Before passed R1-R5, became stale under R1-R6, and the
compiled `R6 -> R4 -> R2 / suppress R3 / preserve R5` operation preceded one
full-context regeneration. The public answer changed `POLISH -> PROVE`; the
After answer, invalidation, stable fact, and every fact-local lineage check all
passed. The immutable result is `ACCEPT_APPLY_REVISION_PATH` with fingerprint
`1ba3cfe9565124d92fa8db8222c4d44bc62a81e1da7c6fad07e24e9a8e7ad245`.
See the
[`live r01 result note`](docs/RND_APPLY_REVISION_ACCEPTANCE_V0_6_2_1_LIVE_R01.md)
and
[`canonical artifact`](artifacts/apply_revision_acceptance_v0_6_2_1_live_r01/).
This is product acceptance only: `effect_attribution_status` remains
`NOT_ASSESSED`, and the run does not show that the control caused the changed
answer.

Revalidate the immutable publication without importing EBRT, Torch, Pydantic,
or the OpenAI SDK. Full provenance validation requires the published annotated
authorization tag; fetch it once if the checkout does not already have it:

```bash
git fetch origin tag v0.6.2.1-apply-revision-live-r01-authorized
```

Then run:

```bash
python3 -I -S verify_apply_revision_acceptance_v0_6_2_1_live_r01.py \
  artifacts/apply_revision_acceptance_v0_6_2_1_live_r01
python3 -I -S verify_apply_revision_acceptance_v0_6_2_1_live_r01.py \
  --self-test artifacts/apply_revision_acceptance_v0_6_2_1_live_r01
```

For a tag-free archive or foreign-root copy, pass `--no-git` to either command.
All locked source receipts remain mandatory, while annotated-tag authorization
is explicitly reported as not assessed:

```bash
python3 -I -S verify_apply_revision_acceptance_v0_6_2_1_live_r01.py \
  --no-git artifacts/apply_revision_acceptance_v0_6_2_1_live_r01
python3 -I -S verify_apply_revision_acceptance_v0_6_2_1_live_r01.py \
  --self-test --no-git artifacts/apply_revision_acceptance_v0_6_2_1_live_r01
```

The [`recorded Reasoning IDE`](inspector/README.md) consumes a separate,
allowlisted projection pinned to that exact publication. Its three panels keep
Before + late event, the local revision engine, and After + verification in one
view. `Replay recorded Apply Revision` animates stored public state only and
makes no new model call.

### v0.6.3 network-zero actuator preflight

EBRT v0.6.3 now freezes the next control question in one readable monolith,
[`actuator_calibration_v0_6_3.py`](actuator_calibration_v0_6_3.py). Its two
synthetic cases and separate post-call gold live in
[`fixtures/actuator_calibration_v0_6_3.json`](fixtures/actuator_calibration_v0_6_3.json)
and
[`fixtures/actuator_calibration_gold_v0_6_3.json`](fixtures/actuator_calibration_gold_v0_6_3.json).
The source, runtime, 16-call Williams geometry, no-live boundary, and exact hard
gates are sealed by
[`policy_lock_actuator_calibration_v0_6_3.json`](policy_lock_actuator_calibration_v0_6_3.json).

Run the network-zero adversarial checks and reproduce the canonical preflight
artifact:

```bash
python3 actuator_calibration_v0_6_3.py self-test
python3 actuator_calibration_v0_6_3.py build-artifact
python3 -I -S verify_actuator_calibration_v0_6_3_portable.py self-test
```

The committed
[`artifacts/actuator_calibration_v0_6_3_preflight/`](artifacts/actuator_calibration_v0_6_3_preflight/)
bundle records `PASS_NETWORK_ZERO`, 21/21 hard gates, 16 presealed provider
payloads, and zero network/provider calls; its manifest status is
`READY_ZERO_CALL_PREFLIGHT_ONLY`. Exact support is rederived from selected
candidate edges in the frozen public graph rather than accepted from a
model-written closure field. The conformance rows exercise both valid path
coordinates and alignment arithmetic only. They are not synthetic arm-effect
results, no synthetic X-minus-Z or D-minus-C delta is a gate, no hosted uptake
has been observed, and this preflight does not authorize a live call. See the
[`v0.6.3 R&D note`](docs/RND_ACTUATOR_CALIBRATION_V0_6_3.md).

The separately frozen hosted successor is
[`run_actuator_calibration_v0_6_3_live_r01.py`](run_actuator_calibration_v0_6_3_live_r01.py),
with its own
[`live r01 policy lock`](policy_lock_actuator_calibration_v0_6_3_live_r01.json)
and
[`execution note`](docs/RND_ACTUATOR_CALIBRATION_V0_6_3_LIVE_R01.md). It imports
the unchanged monolith, consumes only the 16 sealed payloads, durably journals
each attempt before crossing the provider boundary, and forbids retry, resume,
backfill, alternate output paths, or a partial block. Its network-zero component
self-test is separate from the irreversible `run-live` command. The live command
also requires an annotated authorization tag at its exact execution commit and
guards its semantic-gold loader until all 16 public outputs compile. No hosted r01
result is claimed until that one fixed command completes and its artifact
validates; local receipts are operator-auditable records, not provider-signed
cryptographic proof.

That r01 namespace has now executed once and is frozen. The first provider call
completed, but the unchanged public graph compiler rejected its output with
`EXACT_ONE_CLOSURE_FAILED`; the terminal result is
`STOP_OUTPUT_CONTRACT`, with 15 calls unattempted, semantic gold unloaded, and
secondary quality and all X/Z and D/C effects not assessed. This is not a
control-effect null and the block must not be rerun. See the
[`frozen live result`](docs/RND_ACTUATOR_CALIBRATION_V0_6_3_LIVE_R01_RESULT.md),
the
[`canonical artifact`](artifacts/actuator_calibration_v0_6_3_live_r01), and the
[`portable verifier`](verify_actuator_calibration_v0_6_3_live_r01.py).

### v0.6.3.1 zero-call actuator-uptake measurement repair

EBRT v0.6.3.1 leaves that r01 result immutable and starts a new, network-zero
namespace in
[`actuator_uptake_canary_v0_6_3_1.py`](actuator_uptake_canary_v0_6_3_1.py).
Its public fixture and separate provider-excluded grading gold are
[`fixtures/actuator_uptake_canary_v0_6_3_1.json`](fixtures/actuator_uptake_canary_v0_6_3_1.json)
and
[`fixtures/actuator_uptake_canary_gold_v0_6_3_1.json`](fixtures/actuator_uptake_canary_gold_v0_6_3_1.json).

The measurement repair keeps one actuator only: all four Z/C/D/X payloads
contain the same immutable evidence chunks and differ only in their order. D is
compiled from one real local float64 backward pass; C swaps the same path
blocks with matched permutation geometry; X is a frozen correction-first
positive control; and Z is neutral. The hosted model is not differentiated.

The provider chooses one known opaque `selected_closure_id`. The local harness
expands that coordinate into a public graph and grades it after parsing. A
known stale, mixed, or incomplete coordinate is therefore retained as a
semantic endpoint; malformed/schema-invalid output and unknown closure IDs
remain structural failures. This changes the successor measurement interface,
not the frozen v0.6.3-r01 contract or verdict.

Run the zero-call checks with:

```bash
python3 actuator_uptake_canary_v0_6_3_1.py self-test
python3 actuator_uptake_canary_v0_6_3_1.py validate-artifact
python3 -I -S verify_actuator_uptake_canary_v0_6_3_1_portable.py self-test
```

The monolith has no live command and authorizes zero provider calls. Its
separately authorized four-call successor could return at most
`PROMOTE_TO_FRESH_REPLICATION`; it could not directly open v0.6.4. That
historical successor later opened only the separately sealed v0.6.3.2
replication recorded below. See the
[`v0.6.3.1 R&D note`](docs/RND_ACTUATOR_UPTAKE_CANARY_V0_6_3_1.md).

The separately reviewed live successor is
[`run_actuator_uptake_canary_v0_6_3_1_live_r01.py`](run_actuator_uptake_canary_v0_6_3_1_live_r01.py),
with its own
[`live-r01 policy lock`](policy_lock_actuator_uptake_canary_v0_6_3_1_live_r01.json)
and
[`sealed execution protocol`](docs/RND_ACTUATOR_UPTAKE_CANARY_V0_6_3_1_LIVE_R01.md).
It was anchored to annotated preflight tag `v0.6.3.1-preflight` at commit
`c5e1244055e5d7f83493698119549c49df718ed7` and permitted exactly one call per
arm in `C -> X -> D -> Z` order, with no retry, reorder, resume, or backfill.
The separately merged authorization was annotated as
`v0.6.3.1-live-r01-authorized` (tag object
`621d6ce5aca04629eefd1f0189635ee84b62e8da`, peeled commit
`35b84895acb63298a8459dba1e9f3f2a47f4de0f`) and the block was consumed once.

All four calls completed. C, X, D, and Z selected `K_5c1377f2fc`,
`K_ba42ee466f`, `K_ba42ee466f`, and `K_f41cb3914f`, respectively. The locked
classifier returned `CHANNEL_OPEN_DIRECTIONAL`,
`GRADIENT_PLACEMENT_DIRECTIONAL`, and `PROMOTE_TO_FRESH_REPLICATION`; direct
v0.6.4 promotion remains false. This is one fixed serial block and cannot
separate evidence-order treatment from temporal or provider drift. Its frozen
next action was fresh preregistered replication rather than direct v0.6.4; that
replication has now been consumed as the v0.6.3.2 ceiling result below. See the
[`live-r01 result note`](docs/RND_ACTUATOR_UPTAKE_CANARY_V0_6_3_1_LIVE_R01_RESULT.md),
the
[`canonical artifact`](artifacts/actuator_uptake_canary_v0_6_3_1_live_r01),
and the
[`portable verifier`](verify_actuator_uptake_canary_v0_6_3_1_live_r01.py).

### v0.6.3.2 mirrored fresh-replication preflight

EBRT v0.6.3.2 now freezes the last actuator-replication question before
returning to product convergence. One synthetic case that is fresh relative to
the frozen v0.6.3.1 predecessor reuses exactly four sealed Z/C/D/X payload byte
strings across two mirrored blocks:

```text
Block A: C -> Z -> D -> X
Block B: D -> X -> C -> Z
```

C and D therefore exchange positions 1 and 3, while Z and X exchange positions
2 and 4. The primary public action remains only `selected_closure_id`;
`reviewed_evidence_ids` is an explicitly secondary inspection receipt and
cannot affect the replication decision. The strict aggregate succeeds only if
both blocks independently reproduce the preregistered X-versus-Z and
D-versus-C directional pattern. There is no pooling, majority vote, retry,
third block, or ninth call.

The committed preflight authorizes zero provider calls. Reproduce it with:

```bash
python3 actuator_uptake_replication_v0_6_3_2.py self-test
python3 actuator_uptake_replication_v0_6_3_2.py validate-artifact
python3 -I -S verify_actuator_uptake_replication_v0_6_3_2_portable.py self-test
```

The producer records `PASS_NETWORK_ZERO`; the independent verifier checks all
four payloads, eight scheduled attempts, 26 hard gates, exact artifact bytes,
and tamper probes under `python3 -I -S`. A live block still requires a separate
reviewed runner, merged authorization lock, and exact annotated tag. Even a
positive result would narrow only one serial-position explanation on one fresh
case; it would not establish causality, quality improvement, population
reliability, hidden-state editing, or permission for a v0.6.4 live run. See the
[`v0.6.3.2 protocol`](docs/RND_ACTUATOR_UPTAKE_REPLICATION_V0_6_3_2.md) and
[`network-zero artifact`](artifacts/actuator_uptake_replication_v0_6_3_2_preflight/).

The separately reviewed live-r01 authorization surface was frozen in the
[`eight-call live protocol`](docs/RND_ACTUATOR_UPTAKE_REPLICATION_V0_6_3_2_LIVE_R01.md),
[`runner`](run_actuator_uptake_replication_v0_6_3_2_live_r01.py), and
[`policy lock`](policy_lock_actuator_uptake_replication_v0_6_3_2_live_r01.json).
The exact annotated `v0.6.3.2-live-r01-authorized` tag was published and the
eight-call block was consumed once. Both mirrored blocks returned C as the
alternative event-consistent closure and D, X, and Z as the aligned closure.
The locked aggregate therefore records `REPLICATED_DIRECTIONAL` for D versus C
but `REPLICATED_CEILING` for X versus Z, with terminal
`STOP_REPLICATION_CEILING_NOT_ASSESSED`. The strict conjunction did not open
v0.6.4. No retry, third block, replacement case, or ninth call is permitted;
the project now returns to the Reasoning IDE. See the
[`live-r01 result note`](docs/RND_ACTUATOR_UPTAKE_REPLICATION_V0_6_3_2_LIVE_R01_RESULT.md),
[`canonical artifact`](artifacts/actuator_uptake_replication_v0_6_3_2_live_r01),
and
[`portable verifier`](verify_actuator_uptake_replication_v0_6_3_2_live_r01.py).

> [!IMPORTANT]
> v0.1-v0.3.1 are **not** a Transformer implementation, a GPT latent-state
> editor, or evidence of improved language-model accuracy. v0.4 meaningfully
> executes GPT-5.6 at the public adapter/replay boundary, but still does not
> access hidden states or private chain-of-thought, and its two-case DEV canary
> does not establish a general accuracy improvement. The repeated calibration
> is also contaminated DEV evidence; its Direct arm receives fixed revision
> metadata and is not an unqualified plain-API baseline. v0.4.3 improves
> failure classification coverage, not reasoning quality; v0.4.4 projects
> recorded public evidence and does not execute or edit a live agent. v0.5.0
> differentiates only through its frozen public surrogate: graph annotations
> are scripted, no gradient crosses an adapter/JSON/provider boundary, and no
> final answer is generated.
> v0.5-T likewise differentiates only through an oracle-specified public
> recurrence. Its leaf and transition lanes share standardized coordinate
> count and L2 bounds, not equal terminal actuator scale; the positive
> synthetic comparison therefore does not isolate temporal credit assignment
> from supplied control-basis geometry.
> v0.5.1 projects only allowlisted public controls and never differentiates the
> hosted model. Its first live block is provider-incomplete; the separately
> preserved recovery block completes but produces identical public outputs.
> Neither episode establishes a controlled advantage.
> v0.5.2 visibly changes one synthetic walkthrough output from `POLISH` to
> `PROVE`, but it changes evidence horizon, event envelope, and run position
> together. Its strict final endpoint fails on slot-level evidence attribution;
> it does not establish control-map causality, general quality, or reliability.
> The completed v0.5.3 migration and repair are explicitly contaminated by that
> known failure. Its passing local regression does not retroactively pass
> v0.5.2, discover semantics from language, or establish provider-output or
> general reasoning improvement. The four support-role bindings are supplied
> case annotations, and network/provider calls remain zero.
> v0.5.4 adds exact local temporal credit only inside the compiled public
> recurrence. Its positive comparison is implementation-gated rather than an
> independent held-out preregistration, uses two schedules over one contaminated
> synthetic program, and does not establish semantic discovery, GPT improvement,
> general causal superiority, or access to model hidden states.
> v0.5.5 adds deterministic composition of three sealed public trajectories,
> not execution or coordination of three agents. Its equality junction is a
> fixed signed incidence program with separate bounded slack, not voting,
> routing, debate, or learned arbitration. Its local objective decrease and
> exact block gradients do not establish a better hosted output or general
> multi-agent reasoning.
> v0.6.1 executes one contaminated, unbalanced five-call GPT-5.6 regression.
> Its supplied answer-adjacent oracle DAG is not autonomous semantic discovery;
> B/D/C identity means the tested signed-displacement placement had no observed
> effect. Exact-lineage failures in P and A are contract mismatches and do not
> by themselves prove their natural-language answers were semantically wrong.
> v0.6.3-live-r01 is a consumed one-call terminal artifact, not an actuator-null
> result: its compiler stopped before X/Z or D/C effects were assessed.
> v0.6.3.1's preflight is a zero-call measurement repair. Its separately
> authorized live-r01 block observed a directionally preregistered public
> endpoint difference, but the local backward pass still ends before JSON and
> the fixed serial one-case block cannot separate treatment from temporal or
> provider drift. It establishes no quality improvement, causal effect,
> population reliability, hidden-state editing, or general reasoning result.
> v0.6.3.2 consumed one fresh-case, pairwise-position-counterbalanced hosted
> block. D-versus-C closure selection was directionally repeated in both
> mirrored blocks, but X and Z both selected aligned in both blocks, producing
> the preregistered positive-control ceiling and stopping without opening
> v0.6.4. The two serial blocks cannot eliminate all time drift, and the result
> supports no quality, causal, population, attention, KV, or hidden-state claim.

## Why EBRT?

Most inference pipelines move only forward. If later evidence invalidates an
earlier assumption, the usual choices are to continue from a compromised state
or restart everything. EBRT explores a third option:

1. execute forward;
2. detect a revision event;
3. select a small set of eligible earlier states;
4. optimize bounded control variables for those states;
5. replay the affected suffix;
6. accept the revision or roll back to the best checkpoint.

This is a research harness for making that loop measurable and falsifiable. It
is not yet a production inference engine.

The [EBRT Core Thesis](docs/EBRT_CORE_THESIS.md) preserves the originating
latent-trajectory idea while defining the stricter reachable-control,
stop-gradient, and nonclaim boundaries used by the current public substrate.
The [v0.5.3-v0.5.5 roadmap](docs/ROADMAP_V0_5_3_TO_V0_5_5.md) separates the
vertical work into dependency space, time, and sealed-trajectory multiplicity
before any v0.6 execution or orchestration claim; all three network-zero
milestones are now complete. The evidence-led v0.6+ execution roadmap is
defined separately so that hosted outcomes cannot rewrite these substrate
artifacts: [v0.6+ execution roadmap](docs/ROADMAP_V0_6_PLUS.md).

## Repository map

```text
ebrt_monolith_v0_1.py         frozen mechanism implementation and demo
benchmark_ebrt_v0_1.py        independent matched-comparison benchmark
semantic_adapter_v0_2.py      versioned semantic-input boundary and provenance
instrumentation_ebrt_v0_2.py  event-local mirrors, geometry, and leverage probes
benchmark_instrumentation_v0_2.py v0.2 measurement and discovery benchmark
render_instrumentation_v0_2.py dependency-free mirror HTML/SVG renderer
dual_route_policy_v0_3.py     frozen five-arm dual-route policy candidate
benchmark_dual_route_v0_3.py preregistered matched/holdout runner
policy_lock_v0_3.json         frozen policy, endpoint, fixture, and runtime lock
fixtures/dual_route_v0_3_*.json DEV, holdout, and sequential case families
dual_route_policy_v0_3_1.py   factorized execution-replay and loss-horizon policy
benchmark_dual_route_v0_3_1.py DEV cost lane, trajectory factorial, runtime guards
policy_lock_v0_3_1.json       non-promotional DEV_DRAFT contract and future gates
fixtures/dual_route_v0_3_1_*.json fresh DEV and contaminated regression fixtures
language_replay_bridge_v0_4.py public cards, pre-outcome plan, three replay lanes
openai_reasoning_provider_v0_4.py strict GPT-5.6 Responses providers
benchmark_language_replay_v0_4.py deterministic/live gates, grading, bundles
policy_lock_v0_4.json        non-promotional Language Replay DEV contract
fixtures/language_replay_v0_4_*.json separated DEV inputs and machine gold
benchmark_direct_full_calibration_v0_4.py completion-ceiling Direct/Full runner
policy_lock_direct_full_calibration_v0_4.json frozen two-arm DEV contract
benchmark_aperture_controls_v0_4_1.py locked same-block four-arm control runner
policy_lock_aperture_controls_v0_4_1.json non-promotional aperture-control contract
benchmark_aperture_controls_v0_4_2.py prospective endpoint and diagnostic closure
policy_lock_aperture_controls_v0_4_2.json fixed reason-code and launch-gate contract
policy_lock_aperture_controls_v0_4_2_unchanged_replication_r01.json external one-shot replication meta-lock
openai_response_boundary_v0_4_3.py typed raw-response/provider failure boundary
benchmark_aperture_controls_v0_4_3.py frozen-protocol diagnostic smoke/full gate
policy_lock_aperture_controls_v0_4_3.json preregistered provider-boundary lock
compare_provider_boundary_v0_4_3.py offline frozen-block diagnostic comparison
build_inspector_snapshot_v0_4_1.py validated public-artifact normalizer
build_reasoning_workbench_snapshot_v0_4_4.py deterministic allowlist projection
projection_lock_reasoning_workbench_v0_4_4.json source/hash/privacy projection lock
inspector/                    provisional recorded Revision Workbench
differentiable_evidence_controller_v0_5.py typed graph, local autograd, control projection
policy_lock_differentiable_evidence_controller_v0_5.json frozen numeric/source/artifact contract
build_differentiable_evidence_control_artifact_v0_5.py deterministic mechanism artifact builder
fixtures/differentiable_evidence_controller_v0_5_*.json event and no-event public graphs
temporal_adjoint_state_controller_v0_5_t.py experimental temporal public-state core
benchmark_temporal_adjoint_state_control_v0_5_t.py matched A/B/C/D and exhaustive-sham sweep
policy_lock_temporal_adjoint_state_controller_v0_5_t.json locked v0.5-T mechanism contract
build_temporal_adjoint_state_control_artifact_v0_5_t.py deterministic v0.5-T artifact builder
fixtures/temporal_adjoint_state_controller_v0_5_t_*.json paired-order and no-event suites
controlled_raw_restart_v0_5_1.py case-bound control projection and full-context payloads
benchmark_controlled_raw_restart_v0_5_1.py four-arm one-shot live canary and artifact validator
verify_controlled_raw_restart_v0_5_1_portable.py host-independent verifier for both frozen live bundles
policy_lock_controlled_raw_restart_v0_5_1.json preregistered runtime/source/claim contract
fixtures/controlled_raw_restart_v0_5_1_canary.json explicit temporal-to-language binding
demo_hackathon_strategy_walkthrough_v0_5_2.py sealed two-call English output-diff runner
verify_hackathon_strategy_walkthrough_v0_5_2_portable.py host-independent canonical artifact verifier
policy_lock_hackathon_strategy_walkthrough_v0_5_2.json exact prompt/runtime/source contract
fixtures/hackathon_strategy_walkthrough_v0_5_2*.json separated public case and post-call gold
factorized_lineage_v0_5_3.py strict role-factorized DAG migration, closure, grading, and ablations
build_factorized_lineage_artifact_v0_5_3.py deterministic network-zero bundle builder and verifier
policy_lock_factorized_lineage_v0_5_3.json frozen predecessor/fixture/schema/artifact contract
fixtures/factorized_lineage_v0_5_3_*.json contaminated repair overlay and post-graph closure gold
temporal_adjoint_lineage_v0_5_4.py compiled recurrence, manual derivatives, normalized controls, and hard gates
benchmark_temporal_adjoint_lineage_v0_5_4.py deterministic A/B/C/D comparison and sealed-lane payloads
build_temporal_adjoint_lineage_artifact_v0_5_4.py portable network-zero bundle builder and verifier
policy_lock_temporal_adjoint_lineage_v0_5_4.json exact predecessor, source, schema, gate, and claim contract
fixtures/temporal_adjoint_lineage_v0_5_4_*.json symbolic event and no-event policies only
lane_composable_trajectory_v0_5_5.py typed direct-sum junction, block adjoint, isolation, and adversarial gates
benchmark_lane_composition_v0_5_5.py deterministic split-artifact composition benchmark and rederivation validator
build_lane_composition_artifact_v0_5_5.py atomic network-zero bundle builder, verifier, and rollback audit
policy_lock_lane_composition_v0_5_5.json exact v0.5.4 predecessor, source, fixture, artifact, and claim lock
fixtures/lane_composition_v0_5_5*.json canonical three-lane and exact one-lane-degeneration policies
hosted_bundle_projection_v0_6.py exact v0.5.5-to-provider projection and matched P/A/B/D/C bundle
hosted_bundle_lineage_v0_6.py strict public lineage compiler, closure, and post-call grader
openai_lineage_provider_v0_6.py one-attempt GPT-5.6 structured-output boundary
run_hosted_bundle_v0_6.py frozen five-call runner and exact producer-tree/runtime rederivation validator
verify_hosted_bundle_v0_6_1_portable.py host-independent canonical snapshot verifier
policy_lock_hosted_bundle_v0_6.json frozen source, runtime, order, endpoint, and claim contract
fixtures/hosted_bundle_projection_v0_6.json contaminated projection and matched-control fixture
fixtures/hosted_bundle_lineage_gold_v0_6.json post-call-only exact lineage gold
ebrt.py                       immutable v0.6.2.1 two-call acceptance runner and artifact validator
ebrt_live.py                  current Runtime Preview 4 zero-centered temporal public-trajectory monolith and loopback API
actuator_uptake_canary_v0_6_3_1.py discrete closure-choice uptake preflight monolith
verify_actuator_uptake_canary_v0_6_3_1_portable.py pure-stdlib exact-byte and tamper verifier
policy_lock_actuator_uptake_canary_v0_6_3_1.json zero-call source, runtime, order, and claim lock
run_actuator_uptake_canary_v0_6_3_1_live_r01.py separately authorized four-call one-shot runner
policy_lock_actuator_uptake_canary_v0_6_3_1_live_r01.json exact preflight, source, runtime, order, and live-authorization lock
fixtures/actuator_uptake_canary_v0_6_3_1.json one-case position-only actuator fixture
fixtures/actuator_uptake_canary_gold_v0_6_3_1.json provider-excluded closure roles and grading gold
artifacts/actuator_uptake_canary_v0_6_3_1_preflight/ canonical four-payload network-zero bundle
actuator_uptake_replication_v0_6_3_2.py fresh-case mirrored replication preflight monolith
verify_actuator_uptake_replication_v0_6_3_2_portable.py independent exact-byte and tamper verifier
policy_lock_actuator_uptake_replication_v0_6_3_2.json zero-call mirrored schedule and claim lock
run_actuator_uptake_replication_v0_6_3_2_live_r01.py authorized one-shot eight-attempt hosted runner
policy_lock_actuator_uptake_replication_v0_6_3_2_live_r01.json exact source, runtime, schedule, and authorization lock
verify_actuator_uptake_replication_v0_6_3_2_live_r01.py host-independent frozen-result and tamper verifier
fixtures/actuator_uptake_replication_v0_6_3_2.json fresh N1-N7 public actuator fixture
fixtures/actuator_uptake_replication_gold_v0_6_3_2.json delayed provider-excluded closure roles and gold
artifacts/actuator_uptake_replication_v0_6_3_2_preflight/ canonical four-payload/eight-attempt bundle
artifacts/actuator_uptake_replication_v0_6_3_2_live_r01/ canonical consumed eight-call result bundle
docs/RND_BENCHMARK_V0_1.md    protocol, results, limits, and claim ledger
docs/RND_INSTRUMENTATION_V0_2.md measurement contract and algorithm findings
docs/RND_DUAL_ROUTE_V0_3.md   terminal invariant result and v0.3.1 direction
docs/RND_DUAL_ROUTE_V0_3_1.md factorization design, DEV results, and next experiment
docs/RND_LANGUAGE_REPLAY_V0_4.md live protocol, result, failure, and v0.4.1 axis
docs/RND_DIRECT_FULL_CALIBRATION_V0_4.md repeated result and state-loss diagnosis
docs/RND_APERTURE_CONTROLS_V0_4_1.md control result and causal boundary
docs/RND_DIAGNOSTIC_CLOSURE_V0_4_2.md fresh successor result and failure taxonomy
docs/RND_APERTURE_CONTROLS_V0_4_2_UNCHANGED_REPLICATION_R01.md preregistered replication and frozen negative result
docs/RND_PROVIDER_BOUNDARY_V0_4_3.md protocol, smoke result, correction lineage
docs/RND_REASONING_WORKBENCH_V0_4_4.md workbench projection and claim gates
docs/RND_DIFFERENTIABLE_EVIDENCE_CONTROL_V0_5.md mechanism, gradient, and claim boundaries
docs/RND_TEMPORAL_ADJOINT_STATE_CONTROL_V0_5_T.md temporal mechanism, result, and actuator boundary
docs/RND_CONTROLLED_RAW_RESTART_V0_5_1.md bridge design, incomplete live result, and recovery boundary
docs/RND_HACKATHON_STRATEGY_WALKTHROUGH_V0_5_2.md preregistration, live diff, strict near-pass
docs/EBRT_CORE_THESIS.md       latent north star, corrected control math, and gradient boundaries
docs/RND_FACTORIZED_LINEAGE_V0_5_3.md network-zero lineage result and contaminated repair boundary
docs/RND_TEMPORAL_ADJOINT_LINEAGE_V0_5_4.md matched temporal result, derivative audits, and claim boundary
docs/RND_LANE_COMPOSABLE_TRAJECTORIES_V0_5_5.md completed composition mechanism, audits, and nonclaims
docs/RND_HOSTED_BUNDLE_V0_6_1.md completed hosted block, null placement effect, and next bottleneck
docs/RND_LIVE_APPLY_REVISION_RUNTIME_V0_6_2_2.md typed live invalidation operation, API, security, and claim boundary
docs/RND_TEMPORAL_PUBLIC_TRAJECTORY_V0_6_2_4.md chronological public recurrence, temporal backward, replay, receipts, and nonclaims
docs/RND_ACTUATOR_UPTAKE_CANARY_V0_6_3_1.md zero-call discrete uptake measurement repair
docs/RND_ACTUATOR_UPTAKE_CANARY_V0_6_3_1_LIVE_R01.md sealed four-call execution and authorization boundary
docs/RND_ACTUATOR_UPTAKE_REPLICATION_V0_6_3_2.md mirrored fresh-replication protocol and stop rule
docs/ROADMAP_V0_5_3_TO_V0_5_5.md Space/Time/Multiplicity gates through v0.6 execution design
docs/ROADMAP_V0_6_PLUS.md      sealed bundle-to-output, fresh utility, runtime lanes, and latent return
artifacts/benchmark_v0_1/     committed machine-readable benchmark evidence
artifacts/demo_v0_1/trace.json committed no-build mechanism trace
artifacts/benchmark_instrumentation_v0_2/ committed v0.2 measurement evidence
artifacts/instrumentation_v0_2/ committed trace and standalone mirror figure
artifacts/.dual_route_v0_3_holdout_ledger.json canonical terminal attempt record
artifacts/benchmark_dual_route_v0_3_1_dev/ committed non-promotional DEV evidence
artifacts/factorized_lineage_v0_5_3/ committed contaminated network-zero lineage regression
artifacts/temporal_adjoint_lineage_v0_5_4/ committed sealed temporal mechanism and three v0.5.5-compatible lanes
artifacts/lane_composition_v0_5_5/ committed shared ledger, junction, block audit, controls, and byte-copied lanes
artifacts/hosted_bundle_execution_v0_6_live_r01/ validated five-call hosted outputs, receipts, grades, and manifest
artifacts/benchmark_language_replay_v0_4_fake_dev/ scripted plumbing evidence only
artifacts/benchmark_language_replay_v0_4_live_smoke/ boundary-fixed GPT-5.6 DEV canary
artifacts/benchmark_direct_full_calibration_v0_4_dev/ non-promotional 10-case DEV evidence
artifacts/benchmark_aperture_controls_v0_4_1_dev/ incomplete locked four-arm attempt
artifacts/benchmark_aperture_controls_v0_4_2_contract_smoke/ passing launch evidence
artifacts/benchmark_aperture_controls_v0_4_2_dev/ fresh incomplete diagnostic block
artifacts/benchmark_aperture_controls_v0_4_2_unchanged_replication_r01_*/ unchanged-source smoke and full evidence
artifacts/benchmark_aperture_controls_v0_4_3_contract_smoke/ frozen diagnostic smoke
artifacts/compare_provider_boundary_v0_4_3/ offline non-causal comparison
artifacts/reasoning_workbench_v0_4_4/ canonical public projection and report
artifacts/differentiable_evidence_control_v0_5/ canonical control maps and mechanism report
artifacts/temporal_adjoint_state_control_v0_5_t/ temporal maps, audits, comparison, and manifest
artifacts/benchmark_controlled_raw_restart_v0_5_1_live_canary/ preserved four-receipt incomplete block
artifacts/benchmark_controlled_raw_restart_v0_5_1_quota_recovery_r01/ complete null-diff recovery block
artifacts/demo_hackathon_strategy_walkthrough_v0_5_2_live_r01/ complete two-call near-pass and output diff
requirements.txt              runtime dependency declaration
requirements-live.txt         sealed OpenAI/Pydantic dependency receipt
requirements-product.txt      complete current product runtime set
LICENSE                       Apache License 2.0
```

The benchmark imports the monolith but must not rewrite it. The frozen file is
guarded by this SHA-256 digest:

```text
b1702f2868839d989cc3a9321d227436a23c3dad6cc86483edee9d5dbab3a529
```

## Quick start

Requirements:

- CPython 3.11 or newer
- PyTorch 2.0 or newer
- a CPU execution environment

```bash
git clone https://github.com/RyoSpiralArchitect/ebrt.git
cd ebrt
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

Run the frozen mechanism self-test and both built-in scenarios:

```bash
python3 ebrt_monolith_v0_1.py --self-test
python3 ebrt_monolith_v0_1.py demo --scenario both
```

Validate the benchmark harness, then run the quick matched comparison:

```bash
python3 benchmark_ebrt_v0_1.py --self-test
python3 benchmark_ebrt_v0_1.py --quick \
  --output-dir benchmark_results/v0_1_quick
```

For the complete evidence run or a focused scaling profile:

```bash
python3 benchmark_ebrt_v0_1.py --full \
  --output-dir benchmark_results/v0_1_full
python3 benchmark_ebrt_v0_1.py --profile \
  --output-dir benchmark_results/v0_1_profile
```

The complete run is the reportable protocol. `--quick` is a smoke path and
must not be presented as the final benchmark.

Validate the v0.2 observer, generate a counterfactual trace, and render the
standalone research figure:

```bash
python3 semantic_adapter_v0_2.py
python3 instrumentation_ebrt_v0_2.py --self-test
python3 instrumentation_ebrt_v0_2.py demo --control-leverage \
  --output-json benchmark_results/v0_2_trace.json
python3 render_instrumentation_v0_2.py benchmark_results/v0_2_trace.json \
  --output-html benchmark_results/v0_2_mirror.html
```

Run the v0.2 discovery benchmark:

```bash
python3 benchmark_instrumentation_v0_2.py --self-test
python3 benchmark_instrumentation_v0_2.py --quick \
  --output-dir benchmark_results/v0_2_quick
python3 benchmark_instrumentation_v0_2.py --full \
  --output-dir benchmark_results/v0_2_full
```

Diagnostic generator calls are reported separately. Instrumentation timing is
excluded from deterministic v0.2 artifacts and does not replace the frozen v0.1
performance baseline.

Validate the frozen v0.3 policy and runner, or run the DEV-only smoke path from
a separate checkout of terminal evidence commit `6b3dec8`:

```bash
# Run these inside a detached clone/worktree at commit 6b3dec8.
python3 dual_route_policy_v0_3.py --self-test
python3 benchmark_dual_route_v0_3.py self-test
python3 benchmark_dual_route_v0_3.py quick \
  --output benchmark_results/v0_3_quick --no-progress
```

The terminal v0.3 runner applies its exact recorded runtime lock to `self-test`
and `quick` as well as `full`. Those two DEV commands therefore run only in the
environment recorded by `policy_lock_v0_3.json`; the repository-wide CPython
3.11+/PyTorch 2.x requirements do not imply cross-runtime v0.3 artifact
reproducibility. This over-strict DEV behavior is preserved because the runner
and terminal ledger are historical protocol evidence. v0.3.1 separates the
contract: `full` remains fail-closed on an exact runtime match, while DEV modes
record actual/expected runtime and mark nonmatching outputs non-promotional.

On the integrated post-v0.3 branch, the corrected v0.2 instrumentation SHA no
longer matches the historical v0.3 lock. The frozen guard is therefore expected
to reject v0.3 commands there. Do not update the old lock to silence that
mismatch; use the evidence commit above for inspection and a new v0.3.1 source
graph for new experiments.

Do **not** rerun `full` for v0.3. Its canonical one-shot ledger is terminal.
The next full experiment must use a new v0.3.1 policy version, ledger, and fresh
holdout.

Run the current v0.3.1 factorization checks and non-promotional DEV matrix:

```bash
python3 dual_route_policy_v0_3_1.py --self-test
python3 benchmark_dual_route_v0_3_1.py self-test
python3 benchmark_dual_route_v0_3_1.py quick \
  --output benchmark_results/v0_3_1_quick
python3 benchmark_dual_route_v0_3_1.py epsilon-audit \
  --output benchmark_results/v0_3_1_epsilon.json
```

The v0.3.1 lock is deliberately `DEV_DRAFT`. `full` fails before creating a
ledger or output directory until fresh primary, stable, and sequential
families and promotion rules are locked. DEV commands accept another supported
CPython 3.11+/PyTorch 2.x CPU runtime, record every expected/actual mismatch,
and remain non-promotional with no cross-runtime byte-reproducibility claim.

Validate the dependency-free v0.4 public-state bridge first:

```bash
python3 language_replay_bridge_v0_4.py
```

The frozen v0.4 benchmark `self-test` also validates the exact
OpenAI/Pydantic structured-output schemas. It makes no API call, but it requires
the separately pinned schema dependencies:

```bash
python3 -m pip install -r requirements-live.txt
python3 openai_reasoning_provider_v0_4.py
python3 benchmark_language_replay_v0_4.py self-test
python3 benchmark_language_replay_v0_4.py fake-dev \
  --output benchmark_results/v0_4_fake_dev
```

The local provider is explicitly gold-backed and proves plumbing only. To run
the locked two-case GPT-5.6 canary, additionally provide `OPENAI_API_KEY`
through the process environment:

```bash
python3 benchmark_language_replay_v0_4.py live-smoke \
  --output benchmark_results/v0_4_live_smoke
```

The live runner uses strict Responses structured outputs, disables SDK retry
and persisted response state, and never writes the key or raw response object.
Its output is still `DEV_DRAFT`, not a holdout or promotion result.

Validate the separate Direct-vs-Full calibration without making an API call:

```bash
python3 benchmark_direct_full_calibration_v0_4.py self-test
```

With the live dependencies and `OPENAI_API_KEY` available, the two-case smoke
and locked repeated DEV run are:

```bash
python3 benchmark_direct_full_calibration_v0_4.py live-smoke \
  --output benchmark_results/v0_4_direct_full_live_smoke
python3 benchmark_direct_full_calibration_v0_4.py live-dev \
  --output benchmark_results/v0_4_direct_full_dev
```

The comparison matches only the cumulative `max_output_tokens` ceiling. Direct
and Full use different call counts and realized token/latency budgets. The
committed bundle is development evidence, never a promotion or general model
benchmark.

Validate the v0.4.2 diagnostic successor, v0.4.3 provider-boundary evidence,
and both public exporters without making an API call:

```bash
python3 benchmark_aperture_controls_v0_4_2.py self-test
python3 benchmark_aperture_controls_v0_4_3.py self-test
python3 compare_provider_boundary_v0_4_3.py validate
python3 compare_provider_boundary_v0_4_3.py self-test
python3 build_inspector_snapshot_v0_4_1.py self-test
python3 build_reasoning_workbench_snapshot_v0_4_4.py self-test
python3 build_reasoning_workbench_snapshot_v0_4_4.py validate
```

The committed v0.4.2 full block is intentionally not a resume target. Its passing
contract-smoke launch evidence and incomplete full evidence are both preserved
under `artifacts/`. The v0.4.3 full block was never launched because its smoke
gate closed. To run the normalized v0.4.4 read-only workbench:

```bash
python3 build_reasoning_workbench_snapshot_v0_4_4.py validate
cd inspector
pnpm install
pnpm dev
```

This workbench is read-only and unhosted. `Play recorded revision` reveals
already recorded public cards, grades, and their output diff without a model
call. The Provider Failure Atlas is a separate runtime-health episode. Neither
surface exposes private chain-of-thought or model hidden state.

Validate the v0.5.0 mechanism core. On the runtime recorded in the artifact
manifest, also reproduce its committed zero-network bytes:

```bash
python3 differentiable_evidence_controller_v0_5.py self-test
python3 differentiable_evidence_controller_v0_5.py validate \
  --input-json fixtures/differentiable_evidence_controller_v0_5_dev.json
python3 differentiable_evidence_controller_v0_5.py validate \
  --input-json fixtures/differentiable_evidence_controller_v0_5_no_event.json
python3 build_differentiable_evidence_control_artifact_v0_5.py self-test
python3 build_differentiable_evidence_control_artifact_v0_5.py validate
```

The controller makes no provider call. Its adapter output is a frozen,
oracle-scripted public graph, and its JSON control map stops before full-context
regeneration. The committed artifact proves mechanism integrity and byte
identity only on its recorded Python/PyTorch/platform runtime; no cross-runtime
numerical identity is claimed.

Run the experimental v0.5-T temporal core, its 16-cell four-arm sweep, and the
same-runtime artifact validator:

```bash
python3 temporal_adjoint_state_controller_v0_5_t.py self-test
python3 temporal_adjoint_state_controller_v0_5_t.py validate \
  --input-json fixtures/temporal_adjoint_state_controller_v0_5_t_dev.json
python3 benchmark_temporal_adjoint_state_control_v0_5_t.py self-test
python3 build_temporal_adjoint_state_control_artifact_v0_5_t.py self-test
python3 build_temporal_adjoint_state_control_artifact_v0_5_t.py validate
```

The sweep is one synthetic topology under eight nearby parameter settings and
two evidence orders, not 16 independent benchmark tasks. Its execution map and
adjoint audit are separate artifacts, and both stop before provider execution.

Verify both preserved v0.5.1 live bundles without importing project/provider
dependencies, matching the capture host, or making a provider call:

```bash
python3 -I -S verify_controlled_raw_restart_v0_5_1_portable.py self-test
python3 -I -S verify_controlled_raw_restart_v0_5_1_portable.py verify \
  --artifact-dir artifacts/benchmark_controlled_raw_restart_v0_5_1_live_canary
python3 -I -S verify_controlled_raw_restart_v0_5_1_portable.py verify \
  --artifact-dir artifacts/benchmark_controlled_raw_restart_v0_5_1_quota_recovery_r01
```

The portable verifier uses reviewed canonical hashes as its external root of
trust. It checks frozen bytes, source/fixture lineage, recorded producer
runtime and receipts, result fingerprints, execution accounting, and the exact
calls ledger. It does not reproduce the local surrogate numerics or
cryptographically authenticate provider bodies. The frozen runner remains the
environment-coupled development and numerical-revalidation path:

```bash
python3 controlled_raw_restart_v0_5_1.py validate
python3 controlled_raw_restart_v0_5_1.py self-test
python3 benchmark_controlled_raw_restart_v0_5_1.py self-test
python3 benchmark_controlled_raw_restart_v0_5_1.py preflight
python3 benchmark_controlled_raw_restart_v0_5_1.py validate \
  --artifact-dir artifacts/benchmark_controlled_raw_restart_v0_5_1_live_canary
python3 benchmark_controlled_raw_restart_v0_5_1.py validate \
  --artifact-dir artifacts/benchmark_controlled_raw_restart_v0_5_1_quota_recovery_r01
```

`preflight` constructs no provider request. The committed live bundle contains
four typed HTTP 429 `insufficient_quota` receipts and no model output. It was
not overwritten or resumed. The separately preserved recovery bundle completes
all four calls and strict endpoints, with one identical public card across all
arms and therefore no observed output effect on this case. The portable
verifier is a post-run inspection layer and is not part of either
preregistered source snapshot.

Verify the separate v0.5.2 English walkthrough's preserved canonical artifact
without importing project or provider dependencies and without making a
provider call:

```bash
python3 -I -S verify_hackathon_strategy_walkthrough_v0_5_2_portable.py verify \
  --artifact-dir artifacts/demo_hackathon_strategy_walkthrough_v0_5_2_live_r01
```

This portable verifier uses reviewed external hashes as its root of trust. It
checks the canonical bytes, frozen source/fixture graph, recorded producer
runtime, two-call ledger, public diff, and strict grades on the validator's
current host. It does not require that host to match the recorded macOS/arm64
producer. For environment-coupled mechanism development and exact numerical
revalidation, use the frozen runner separately:

```bash
python3 demo_hackathon_strategy_walkthrough_v0_5_2.py self-test
python3 demo_hackathon_strategy_walkthrough_v0_5_2.py preflight
python3 demo_hackathon_strategy_walkthrough_v0_5_2.py validate \
  --artifact-dir artifacts/demo_hackathon_strategy_walkthrough_v0_5_2_live_r01
```

The committed artifact is `VALID` and both calls completed, but its
walkthrough contract is `false`. It records an observed `POLISH → PROVE` public
output diff with correct R3 invalidation and R5 preservation, while the final
card misses the frozen slot-level citation closure. The portable verifier is a
post-run inspection layer, not part of the preregistered source snapshot; it
does not reproduce local autograd or cryptographically attest the provider.
`preflight` constructs no provider request.

## Judge path: inspect first, rerun second

No training or model build is required to inspect the submitted evidence.
Start with:

1. [`docs/RND_BENCHMARK_V0_1.md`](docs/RND_BENCHMARK_V0_1.md) for the study
   design, result interpretation, and claim limits;
2. `artifacts/benchmark_v0_1/manifest.json` for the exact environment, seeds,
   fixture digest, and source digests;
3. `artifacts/benchmark_v0_1/benchmark_report.md` for the generated summary;
4. `artifacts/benchmark_v0_1/trials.csv` and `results.json` for auditable raw
   and aggregated evidence.

For the v0.2 counterfactual observer, inspect:

1. [`docs/RND_INSTRUMENTATION_V0_2.md`](docs/RND_INSTRUMENTATION_V0_2.md) for
   the mirror contract, geometry semantics, full results, and next algorithm;
2. `artifacts/instrumentation_v0_2/mirror.html` for the standalone generated
   figure and `trace.json` for its embedded source data;
3. `artifacts/benchmark_instrumentation_v0_2/manifest.json` and
   `benchmark_report.md` for the full 32-seed measurement run;
4. `events.csv` and `candidates.csv` for event-local effects and the separate
   semantic-attention/source-projection-leverage surface.

For the v0.3 prospective experiment, inspect:

1. [`docs/RND_DUAL_ROUTE_V0_3.md`](docs/RND_DUAL_ROUTE_V0_3.md) for the frozen
   comparison, terminal assertion, mechanism diagnosis, and clean next design;
2. `policy_lock_v0_3.json` for the preregistered arms, endpoints, margins,
   guardrails, fixture hashes, runtime, and one-shot rule;
3. `artifacts/.dual_route_v0_3_holdout_ledger.json` for the canonical attempt-1
   terminal record.

For the v0.3.1 DEV factorization, inspect:

1. [`docs/RND_DUAL_ROUTE_V0_3_1.md`](docs/RND_DUAL_ROUTE_V0_3_1.md) for the two
   independent floors, causal lanes, measured result, and promotion boundary;
2. `policy_lock_v0_3_1.json` for the runtime split, DEV protocol, pending fresh
   inputs, and old-evidence hashes;
3. `artifacts/benchmark_dual_route_v0_3_1_dev/` for deterministic lane rows,
   runtime metadata, source hashes, and the non-promotional manifest.

For the v0.4 Language Replay Bridge, inspect:

1. [`docs/RND_LANGUAGE_REPLAY_V0_4.md`](docs/RND_LANGUAGE_REPLAY_V0_4.md) for
   the public-card contract, matched lanes, live result, failed quality
   guardrail, and routing/sufficiency interaction;
2. `policy_lock_v0_4.json` for the pre-outcome route, live provider settings,
   accounting contract, and DEV claim boundary;
3. `artifacts/benchmark_language_replay_v0_4_live_smoke/` for the sanitized
   GPT-5.6 traces, exact usage, grades, and source hashes;
4. `artifacts/benchmark_language_replay_v0_4_fake_dev/` only for deterministic
   plumbing and failure-sentinel evidence, never model-performance evidence.

For the repeated Direct-vs-Full calibration, inspect:

1. [`docs/RND_DIRECT_FULL_CALIBRATION_V0_4.md`](docs/RND_DIRECT_FULL_CALIBRATION_V0_4.md)
   for the locked contrast, result, state-loss diagnosis, and next controls;
2. `policy_lock_direct_full_calibration_v0_4.json` for the fixed revision
   envelope, nominal completion ceiling, trial rotation, and claim boundary;
3. `artifacts/benchmark_direct_full_calibration_v0_4_dev/manifest.json` for all
   source and artifact hashes;
4. `benchmark_report.md` and `arm_rows.csv` for the compact result, then
   `results.json`, `traces.jsonl`, and `calls.jsonl` for the full audit surface.

For the v0.4.1 control block and provisional Inspector, inspect:

1. [`docs/RND_APERTURE_CONTROLS_V0_4_1.md`](docs/RND_APERTURE_CONTROLS_V0_4_1.md)
   for the paired questions, result, readiness status, and interpretation limit;
2. `policy_lock_aperture_controls_v0_4_1.json` for the four arms, post-event
   temporal semantics, output-ceiling scope, and cause-decision gate;
3. `artifacts/benchmark_aperture_controls_v0_4_1_dev/` for sanitized calls,
   traces, grades, exact receipts, and manifest hashes;
4. `inspector/` for the replaceable local viewer and
   `build_inspector_snapshot_v0_4_1.py` for its validated public data contract.

For the provider-boundary diagnostic and Recorded Revision Workbench, inspect:

1. [`docs/RND_PROVIDER_BOUNDARY_V0_4_3.md`](docs/RND_PROVIDER_BOUNDARY_V0_4_3.md)
   for the preregistered smoke, 8/8 typed failure coverage, closed launch gate,
   and post-freeze derived-field lineage;
2. `artifacts/benchmark_aperture_controls_v0_4_3_contract_smoke/` and
   `artifacts/compare_provider_boundary_v0_4_3/` for the frozen receipts and
   non-causal diagnostic comparison;
3. [`docs/RND_REASONING_WORKBENCH_V0_4_4.md`](docs/RND_REASONING_WORKBENCH_V0_4_4.md)
   for the deterministic episode-selection and public projection contract;
4. `artifacts/reasoning_workbench_v0_4_4/` for the canonical snapshot, manifest,
   and report, then `inspector/` for the replaceable product surface.

For the v0.5.0 differentiable controller core, inspect:

1. [`docs/RND_DIFFERENTIABLE_EVIDENCE_CONTROL_V0_5.md`](docs/RND_DIFFERENTIABLE_EVIDENCE_CONTROL_V0_5.md)
   for the graph, loss, gradient boundary, numerical policy, and claim limits;
2. `policy_lock_differentiable_evidence_controller_v0_5.json` for the exact
   source, fixture, optimizer, finite-difference, and projection contract;
3. `artifacts/differentiable_evidence_control_v0_5/mechanism_report.md` for the
   compact result and the two canonical control maps for triggered/no-event
   behavior;
4. `artifacts/differentiable_evidence_control_v0_5/self_test.json` for the
   per-term numerical checks and mechanism metrics.

For the experimental v0.5-T temporal state-control record, inspect:

1. [`docs/RND_TEMPORAL_ADJOINT_STATE_CONTROL_V0_5_T.md`](docs/RND_TEMPORAL_ADJOINT_STATE_CONTROL_V0_5_T.md)
   for the recurrence, exact adjoint, comparison design, actuator-scale caveat,
   result, and claim ledger;
2. `policy_lock_temporal_adjoint_state_controller_v0_5_t.json` for the exact
   sources, fixtures, numeric policy, post-pilot locked gates, and artifact set;
3. `artifacts/temporal_adjoint_state_control_v0_5_t/mechanism_report.md` and
   `arm_comparison.json` for the compact result, all five nonidentity shams, and
   terminal Jacobian norms;
4. the separate representative `execution_control_map` and
   `temporal_adjoint_audit` files for actionable controls versus diagnostics;
5. `self_test.json` and `manifest.json` for numerical, no-event, network-zero,
   source-integrity, and same-runtime byte evidence.

There is intentionally no normal v0.3 result directory: the runner stopped
before validated bundle publication, and the ledger stores no outcome rows.

After installing the single runtime dependency, the shortest executable check
is:

```bash
python3 ebrt_monolith_v0_1.py --self-test
python3 benchmark_ebrt_v0_1.py --self-test
python3 instrumentation_ebrt_v0_2.py --self-test
python3 benchmark_instrumentation_v0_2.py --self-test
python3 render_instrumentation_v0_2.py --self-test
python3 dual_route_policy_v0_3_1.py --self-test
python3 benchmark_dual_route_v0_3_1.py self-test
python3 language_replay_bridge_v0_4.py
python3 benchmark_language_replay_v0_4.py self-test
python3 benchmark_direct_full_calibration_v0_4.py self-test
python3 differentiable_evidence_controller_v0_5.py self-test
python3 build_differentiable_evidence_control_artifact_v0_5.py self-test
```

The v0.3 self-tests are historical checks and must be run from a separate
checkout of commit `6b3dec8`, as described above; they are intentionally not a
current-tree smoke command after the v0.2 feasibility correction.

The manifest is the source of truth for the exact platform used to produce the
committed results. The v0.1 CLI requires CPython 3.11+ and PyTorch 2.x on a
POSIX CPU environment; the committed run records the one macOS arm64 setup
actually validated. Linux is intended but not yet validated. Windows is not
supported by the v0.1 benchmark's process-memory probe. CUDA, MPS, distributed
execution, and numerical equivalence across hardware are not validated claims.

## What the benchmark compares

All arms run on matched synthetic cases and seeds:

| Arm | Purpose |
| --- | --- |
| A — forward-only | Zero-control, single-pass baseline |
| B — detect-only | Measures detector/scaffolding cost without revision |
| C — random-route revision | Controls for revision while removing informed routing |
| D — full EBRT | Event detection, routed revision, replay, and rollback |
| E — gold-route revision | Privileged annotated-target intervention; not assumed to be a performance ceiling |

The important contrasts are D−A (total mechanism value), D−C (routing value),
E−D (the effect of forcing the annotated causal target), and B−A
(detector/scaffold cost). The gold route is privileged information, but it is
not guaranteed to be the most effective control location in a recurrent toy
system. Primary quality measures use independent gold outcomes and targets;
the mechanism's internal energy is diagnostic, not a substitute for task
correctness.

See the [R&D benchmark note](docs/RND_BENCHMARK_V0_1.md) for fixtures, metrics,
statistics, failure analysis, and threats to validity.

## Measured v0.1 baseline

The reportable run executed 7,680 correctness trials and 630 controlled-profile
trials from source commit `37f81340`. Inspect the generated
[benchmark report](artifacts/benchmark_v0_1/benchmark_report.md) and
[manifest](artifacts/benchmark_v0_1/manifest.json) before interpreting the
summary.

| Arm | Target-topic success | Source-distance gain | Informative route recall | Median trial time |
| --- | ---: | ---: | ---: | ---: |
| A — forward-only | 55.56% | 0.000 | — | 0.516 ms |
| B — detect-only | 55.56% | 0.000 | — | 0.680 ms |
| C — random route | 95.49% | 0.217 | 50.14% | 11.611 ms |
| D — full EBRT | 97.66% | 0.266 | 50.00% | 11.419 ms |
| E — gold route | 91.15% | 0.149 | 100.00% | 12.202 ms |

Relative to A, D improved target-topic success by 42.10 percentage points with
a case-cluster 95% CI of `[+26.82, +57.90]`. Its stricter all-topic gain was
8.59 points with a CI of `[-0.78, +18.49]`, so whole-trajectory improvement is
not established. D improved source-distance gain over C by 0.0493
`[+0.0187, +0.0813]`, but its binary advantage was modest and its annotated
route recall was not better than random.

E corrected the annotated target most strongly, yet underperformed D at the
event/output state. That result is useful: the semantic causal anchor and the
most effective recurrent control location are not necessarily the same thing.
Stable cases produced no event or revision, and all pre-target state and
non-target control drift checks were exactly zero; unrelated suffix topics were
not invariant.

The top measured engineering bottlenecks are replay and scaffold cost. At
length 2,048, a no-event D run took 328.794 ms versus A's 68.604 ms; one far
event raised D to 4,908.228 ms and 75,776 generator steps. See the R&D note for
revision-step, replay-distance, failure-cluster, and claim-ledger details.

## Measured v0.2 instrumentation result

The v0.2 full run executed 1,536 instrumented sessions over the same 48 cases
and 32 model seeds. It recorded 1,312 revision events and 1,984 offline
candidate probes while preserving a 100% frozen-core, generator-accounting, and
finite-output pass rate.

Of the 1,984 probes, 72 (3.63%) reached the frozen control boundary and used the
projected-forward one-sided scheme. The largest evaluated control norm was
`1.750000119`, within the core's `1.75 + 1e-5` assertion tolerance. Regenerating
the feasible probes changed continuous leverage values and artifact hashes, but
the four displayed multi-candidate rank/alignment estimates below were unchanged
at their published precision.

The most useful result is an algorithm-design hypothesis. The 512
multi-candidate rows are repeated measurements of only 15 case clusters, 16
case-source fixtures, and two case families; their alignment values were
invariant across the 32 seeds within each fixture.

Here `control_leverage` has a narrow definition: a centered finite difference
of target-aligned event-source belief projection when both requested endpoints
are feasible, and a radially projected forward one-sided difference at the
control boundary. It tests one normalized topic-aligned requested actuation and
is not an objective gradient or a measure of full-state controllability.

| Measurement | Estimate | Case-cluster 95% CI |
| --- | ---: | ---: |
| Executed semantic route selected maximum source-projection leverage | 75.00% | [53.33%, 93.75%] |
| Annotated semantic-gold anchor had maximum source-projection leverage | 12.50% | [0.00%, 33.33%] |
| Executed route selected the semantic-gold anchor | 37.50% | [13.33%, 64.71%] |
| Attention/source-projection-leverage Spearman correlation | 0.5000 | [0.0667, 0.8824] |

The limited suite therefore nominates, but does not validate, a dual-route
policy: retain an auditable semantic anchor for what is being revised, while
testing whether a separately budgeted control anchor or window improves
downstream effect, leakage, and compute efficiency. Replacing the semantic
route with this one-direction leverage ranking is not promoted by the result.

Trajectory geometry also found a narrower useful role. Excess turn angle and
curvature tracked continuous source gain, but neither separated successful from
unsuccessful target-topic outcomes. v0.2 treats them as intervention and
propagation signals, not correctness rewards. Source gain per unit control norm
was negatively associated with unrelated-state leakage (`rho=-0.7380`,
case-cluster 95% CI `[-0.8615, -0.5444]`), motivating a leakage-aware efficiency
objective for the next matched experiment.

See the [v0.2 R&D note](docs/RND_INSTRUMENTATION_V0_2.md), generated
[benchmark report](artifacts/benchmark_instrumentation_v0_2/benchmark_report.md),
and standalone [Mirror figure](artifacts/instrumentation_v0_2/mirror.html).

## v0.3 terminal protocol result

v0.3 froze five capacity-matched policies, new DEV/holdout/sequential families,
two co-primary D2 contrasts, noninferiority/leakage/compute guardrails, exact
runtime hashes, and a one-shot ledger. Protocol commit `5b88faa` was pushed
before the holdout command ran.

Attempt 1 ended with:

```text
AssertionError: native selected-min replay changed matched outcome:
('holdout_dual_repeated_stream_00', 0, 'S2')
```

This is a terminal invariant rejection, not a policy-quality result. The
matched/native comparison kept the named objective and selected control sites
fixed, but one `replay_floor` variable controlled both physical recomputation
and the support of the trajectory-anchor loss. The latter changed the actual
optimization objective, so the native lane was not a cost-only change; exact
outcome preservation failed in the observed case.

No validated result bundle or outcome rows were written. D2-S2, D2-SR2,
confidence intervals, guardrails, stable cases, sequential cases, and promotion
status are all **not evaluated**. v0.3 is not rerun. The next version will
separate execution replay start from trajectory-anchor loss horizon, then study
semantic objective, control sites, and loss horizon as distinct policy
dimensions on an entirely fresh holdout.

See the [v0.3 R&D note](docs/RND_DUAL_ROUTE_V0_3.md), frozen
[`policy_lock_v0_3.json`](policy_lock_v0_3.json), and canonical
[`holdout ledger`](artifacts/.dual_route_v0_3_holdout_ledger.json).

## v0.3.1 DEV factorization result

v0.3.1 removes the ambiguous `replay_floor`. The cost lane keeps semantic
objective, control sites, probe work, optimizer, and trajectory loss support
fixed while moving only physical replay to the earliest selected control. The
trajectory factorial keeps physical replay and accounting fixed while moving
only the trajectory-anchor loss horizon.

The committed combined bundle contains 24 lane groups over two fresh DEV cases
plus four lane groups from the isolated, contaminated v0.3 terminal
counterexample. It uses four seeds and S2/L2/D2 where applicable.

- Exact cost-lane outcome equality passed for 28/28 groups.
- In fresh DEV only, 12/24 groups had a shorter execution floor, saved 320
  optimizer replay steps in total (26.67 per separated group), and changed
  under the trajectory-only factorial.
- In contaminated regression only, all 4/4 groups separated, saved 272 replay
  steps in total, and changed under the trajectory-only factorial.
- Combined, the same 16 groups both separated and changed; there were no
  one-sided mismatches between those sets.
- On the exact historical S2 counterexample, replay work fell from 374 to 306
  with exactly equal events, controls, final states, and decoded output. Moving
  only the loss horizon reproduced the old outcome divergence.
- The tested L2 leverage rank was stable at epsilon `1e-4`, `1e-3`, and `1e-2`.

This is stronger mechanism diagnosis and a cleaner reasoning-policy design, not
a held-out quality result. The old case is explicitly contaminated; the new
cases are DEV; no v0.3.1 holdout or ledger exists. The next experiment can now
learn or preregister trajectory horizon as a policy axis without confusing it
with replay cost.

## v0.4 Language Replay DEV result

v0.4 runs a GPT-5.6 semantic observer and public-card generator end to end.
The boundary-fixed canary contains one answer-flip case and one irrelevant
no-op, with one trial each. The observer matched both DEV event/floor
annotations. All 31 attempted calls completed under the locked model/tier with
exact provider usage; full restart was the only lane to answer both cases
exactly.

| Lane | Machine success | Answer exact | Regenerated cards | Branch input | Branch output | Branch reasoning |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Card-only forward | 1/2 | 1/2 | 2 | 1,580 | 431 | 136 |
| Full restart | 2/2 | 2/2 | 12 | 9,257 | 1,924 | 347 |
| Selective replay | 1/2 | 1/2 | 5 | 4,106 | 1,204 | 412 |

Selective replay used seven fewer public-card calls than full restart and
5,151 fewer input plus 720 fewer output tokens, but used 65 **more** reasoning
tokens and did **not** pass the quality guardrail. The fair counterfactual
totals charge the shared initial trace and observer to every lane: card-only,
full, and selective used 14, 24, and 17 calls respectively.

On the route-code revision, the invalidated-anchor rule correctly selected the
checkpoint after raw route table `R2`. That public card retained a bare `R2`
citation but not the concrete `B2 -> BLUE` lookup edge. Selective preserved the
late `B2` correction and stable seal but returned stale answer `AMBER` with
`bay=UNKNOWN`; full restart reread raw `R2` and passed. The no-op passed in all
lanes and selective replay correctly performed no backward replay.

This is a successful live bridge and a failed sufficiency result—not evidence
that selective replay already improves GPT reasoning. This canary initially
nominated dependency-complete public state plus pre-outcome floor expansion.
The subsequent calibration below pauses floor work and tests the representation
first. See the [v0.4 R&D note](docs/RND_LANGUAGE_REPLAY_V0_4.md).

## v0.4 Direct-vs-Full calibration result

The follow-up calibration holds revision detection fixed and compares two
generation paths over all 10 existing DEV cases, three trials each:

- one stateless `direct_raw_fixed_revision` call over all ordered raw evidence;
- six-step `full_restart` from an empty state using only the previous public
  card plus the current raw chunk.

Both arms use the same model, final schema, grader, reasoning setting, and
nominal cumulative output-token ceiling of 4,608 per case. Actual calls, input,
realized output/reasoning tokens, latency, price, and server compute are not
matched. Direct receives the same fixed revision metadata, so it is not an
unqualified plain-API control.

All 210 calls completed with exact sanitized usage and balanced 15/15 arm
order. The locked result was:

| Metric | Direct | Full |
| --- | ---: | ---: |
| Strict machine success | 30/30 | 4/30 |
| Answer exact | 30/30 | 15/30 |
| Evidence consistent | 30/30 | 4/30 |
| Stable case pass | 10/10 | 1/10 |
| API calls | 30 | 180 |
| Input tokens | 22,041 | 132,097 |
| Output tokens | 4,442 | 41,864 |
| Reasoning-token detail | 0 | 17,502 |

There were 26 Direct-only outcomes, four both-pass outcomes, and no Full-only
outcome. Full preserved stable facts and invalidation hygiene in all 30 runs,
but retained required evidence in only 4/30. Its only stable strict pass was the
irrelevant no-op.

The traces reveal an irreversible aperture loss. Evidence that cannot fill a
fixed decision slot when first seen—mapping tables, thresholds, conversion
rules, dependency edges, and precedence rules—often disappears from the next
public card. A later correction supplies the missing key, but the raw semantics
cannot re-enter. A citation ID is not a lossless memory.

This rejects the current staged public-card Full protocol as the primary
quality scaffold on this DEV suite. It does not reject external scaffolding in
general or formally rank selective replay. The next controls are a
no-revision-envelope one-shot raw control and a six-call cumulative-raw restart
that tests card-only information loss while holding staging fixed. See the
[calibration R&D note](docs/RND_DIRECT_FULL_CALIBRATION_V0_4.md).

## v0.4.1 Aperture-controls result

The follow-up ran the two planned controls in the same block as fresh Direct
and card-only anchors. The four arms were no-envelope one-shot raw,
fixed-envelope one-shot raw, fixed-envelope card-only staging, and
fixed-envelope cumulative-raw staging. All used the same exact model and
reasoning setting and a nominal 4,608-token output ceiling per case; input
tokens, call counts, realized output/reasoning tokens, latency, and compute were
not matched.

The 30 scheduled case-trials produced 28 complete four-arm runs. Both
incomplete arms were card-only staging and stopped after their third completed
provider call with a sanitized `local_contract_error`. The artifact preserves
414 validated receipts, carries an `INCOMPLETE` manifest, and does not open its
locked cause-decision gate.

| Metric | No-envelope Direct | Fixed Direct | Card-only staged | Cumulative raw |
| --- | ---: | ---: | ---: | ---: |
| Completed outputs | 30/30 | 30/30 | 28/30 | 30/30 |
| Strict machine success | 29/30 | 30/30 | 2/28 | 30/30 |
| Answer exact | 30/30 | 30/30 | 11/28 | 30/30 |
| Descriptive stable-pass cases | 10/10 | 10/10 | 1/10 | 10/10 |
| API calls | 30 | 30 | 174 | 180 |
| Input tokens | 22,041 | 22,911 | 131,308 | 148,222 |
| Output tokens | 4,523 | 4,563 | 41,299 | 35,046 |
| Reasoning-token detail | 87 | 0 | 17,861 | 9,232 |

Among completed staged pairs, cumulative raw had 26 exclusive strict
successes and shared two successes with card-only; card-only had no exclusive
success. This strongly nominates raw aperture as the next bottleneck to study,
but it is a descriptive result on contaminated DEV, not a completed causal
estimate or a general model-quality claim. The exact local validator sub-rule
for the two rejected cards was intentionally not retained, so stable
non-sensitive failure reason codes are the next instrumentation requirement.
Post-run review also found an unexercised harmful-envelope direction branch in
the frozen helper. It does not affect this not-ready artifact or the observed
10/10 one-shot stable parity, but a decision-ready successor must version the
runner, repair that branch, and add its missing self-test rather than rerun this
exact lock.

The provisional Inspector renders this incomplete artifact honestly: grade
unavailability is `NOT ASSESSED`, the header remains `Cause decision: NOT
READY`, and envelope delivery is visible per arm. See the
[v0.4.1 R&D note](docs/RND_APERTURE_CONTROLS_V0_4_1.md).

## v0.4.2 Diagnostic-closure result

The versioned successor preserved the v0.4.1 provider-facing protocol and
added a prospective endpoint policy: a completed provider call rejected by an
allowlisted local validator rule is an assessed strict failure, while provider,
SDK, receipt-audit, and internal failures remain non-assessable. A fixed
two-case contract smoke passed 28/28 calls before the exact 10-case x 3-trial
block was launched.

The full schedule ran once and produced 414 unique attempted receipts. It did
not become decision-ready: an `APITimeoutError` affected fixed Direct in one
`alias_rebind` trial, and an SDK structured-output `ValidationError` affected
card-only staging in another. Separately, one card-only run reached a completed
provider receipt and was rejected with `invalidated_active_support`; this is a
measured strict failure rather than missing data.

| Metric | No-envelope Direct | Fixed Direct | Card-only staged | Cumulative raw |
| --- | ---: | ---: | ---: | ---: |
| Accepted outputs | 30/30 | 29/30 | 28/30 | 30/30 |
| Strict machine success | 29/30 | 29/30 | 2/30 | 30/30 |
| Exact final answer | 30/30 | 29/30 | 11/30 | 30/30 |
| Assessed stable-pass cases | 9/9 | 9/9 | 1/9 | 9/9 |
| Attempted API calls | 30 | 30 | 174 | 180 |

Within the 28 assessed staged pairs, cumulative raw won exclusively 26 times
and shared two passes; card-only had no exclusive pass. This is consistent with
the prior raw-aperture mechanism candidate, but the two non-assessable pairs
keep both locked cause conclusions closed. Aggregate provider-token totals are
exact only for no-envelope Direct and cumulative raw, because the other two
arms include a receipt with unavailable usage. See the
[v0.4.2 R&D note](docs/RND_DIAGNOSTIC_CLOSURE_V0_4_2.md).

### v0.4.2 unchanged replication r01

An externally sealed meta-lock then repeated the byte-identical v0.4.2 lane.
The fresh two-case smoke again passed 28/28 calls and launched the full block.
The full block did not become decision-ready: it produced 22/30 assessed
four-arm runs, 20/30 all-output-completed runs, two assessed card-only
`invalidated_active_support` rejections, and 31 non-assessable provider-call
exceptions.

Those 31 exceptions form one contiguous tail from receipt 314 through 344.
Every frozen receipt records `failure_type=RateLimitError`, attempt 1, and retry
0. The first 313 receipts completed; there was no successful recovery after the
tail began. The v0.4.2 artifact does not retain an HTTP status or provider error
code, so it cannot distinguish ordinary rate limiting from quota exhaustion,
and the historical rows remain `provider_call_exception_unclassified`.

| Predeclared endpoint | Prior v0.4.2 | r01 |
| --- | ---: | ---: |
| Assessed four-arm runs | 28/30 | 22/30 |
| All-output-completed runs | 27/30 | 20/30 |
| Attempted calls | 414 | 344 |
| Non-assessable endpoints | 2 | 31 |
| Terminal local rejections | 1 | 2 |

The preregistered r01 classification is
`full_executed_incomplete_non_assessable`. This is a valid frozen runtime
negative result on a seen contaminated DEV suite, not an algorithm-quality
comparison. It motivates prospective provider-boundary instrumentation without
retrospectively relabeling failures. See the
[unchanged-replication note](docs/RND_APERTURE_CONTROLS_V0_4_2_UNCHANGED_REPLICATION_R01.md).

## Current scope and claim boundary

| Statement | Current status |
| --- | --- |
| A bounded event-triggered backward-revision loop executes end to end | Demonstrated by the structured harness and self-tests |
| The frozen core can be evaluated through an external matched benchmark | Covered by the benchmark and SHA guard |
| EBRT improves the labeled revision topic relative to forward-only on this suite | Supported by the committed full benchmark |
| EBRT improves every topic in the trajectory | Not established; the all-topic CI crosses zero |
| One revision's local and downstream effect can be isolated from earlier accepted revisions | Implemented by the v0.2 event-local mirror |
| Semantic-anchor and source-projection-leverage rankings are identical | Not supported on the informative fixed-suite fixtures; they are measured separately |
| Curvature measures reasoning correctness | Not established; currently an effect/geometry diagnostic |
| The five-arm dual-route candidate executes on DEV fixtures | Implemented with deterministic accounting and matched budgets in v0.3 |
| The dual-route policy improves or degrades held-out outcomes | Not evaluated; attempt 1 terminated before validated metrics were published |
| The coupled v0.3 minimum-selected lane preserves the matched outcome | Refuted as a universal exact invariant by the terminal v0.3 counterexample |
| A changed coupled `replay_floor` is a cost-only exact-invariance optimization | Refuted by v0.3; execution replay start and trajectory-anchor loss horizon must be separated |
| Factorized cost-lane outcomes remain exact when the loss horizon is fixed | Supported on all 24 fresh DEV groups plus four contaminated regression groups; actual floor shortening is exercised on 12 fresh and four contaminated groups, not yet as a universal or held-out claim |
| `trajectory_anchor_floor` is an independent causal policy axis in the toy mechanism | Supported mechanistically: changing it alone reproduced the historical divergence with matched accounting |
| v0.3.1 improves held-out reasoning quality | Not evaluated; the lock is DEV_DRAFT and no fresh holdout exists |
| A GPT observer can detect a late-evidence event and select a public replay floor | Executed correctly on 2/2 annotated DEV canary cases; generalization is not established |
| Selective public-card replay matches full-restart quality | Not established; it passed 1/2 full-success canary cases |
| Selective replay uses fewer provider tokens than full restart | It used fewer input/output tokens in this two-case DEV canary, but 65 more reasoning tokens; no general or monotonic-compute claim |
| The current staged Full protocol matches one-shot fixed-envelope Direct quality | Refuted on the locked contaminated DEV calibration: Full passed 4/30 versus Direct 30/30, with 0 Full-only outcomes |
| One-shot fixed-envelope Direct is stable on the existing 10-case DEV suite | Supported at 3/3 trials for all 10 cases; the suite is saturated and not a fresh holdout |
| The calibration proves an unassisted plain API is superior | Not supported; Direct receives fixed revision metadata and a strict output scaffold |
| Public-card compression alone caused the Full deficit | Not formally established: both v0.4.1 and v0.4.2 show 30/30 cumulative-raw strict outputs versus 2 card-only successes, but each block has non-assessable paired runs and the intervention changes more than compression alone |
| Retaining cumulative raw repairs this staged protocol | Strongly nominated on contaminated DEV and replicated descriptively at 30/30 strict outputs; the v0.4.2 locked cause gate remains closed because two paired runs were non-assessable |
| Stable local-validator reason codes make every live failure assessable | Refuted by the fresh v0.4.2 block: one local rejection became an assessed `invalidated_active_support` failure, while an API timeout and an SDK parse `ValidationError` remained non-assessable |
| Repeating unchanged v0.4.2 makes the locked cause estimate decision-ready | Refuted by r01: its smoke passed, but a contiguous 31-receipt `RateLimitError` tail left only 22/30 four-arm runs assessed and kept both cause conclusions closed |
| The r01 rate-limit tail proves quota exhaustion or an HTTP-layer cause | Not established: v0.4.2 retained the SDK exception class but not HTTP status or provider error code, so prospective v0.4.3 instrumentation is required |
| v0.4.3 improves native provider-failure classification coverage | Supported descriptively within its frozen two-case smoke: 8/8 non-assessable endpoints received a prospective phase/reason code, versus frozen r01 native 0/31; the blocks have different populations and the cross-block effect is `null` |
| The v0.4.3 HTTP 429 observations are reasoning failures or prove current provider health | Not supported; they are a recorded runtime-health episode, all reasoning endpoints were non-assessable, and the full block was not launched |
| The v0.4.3 derived coverage correction changed provider observations or the launch decision | No; explicit lineage retains the original hashes, while calls, traces, receipt projection, eight failure labels, closed gates, and absent full block remain unchanged |
| The fixed revision envelope improves the saturated one-shot raw scaffold | Not established; fixed passed 30/30 versus no-envelope 29/30 at output level and both were stable on 10/10 cases, with no decision-ready cause estimate |
| The Workbench can trace one recorded revision through final public output | Supported for its mechanically selected v0.4 episode; it preserves all three replay lanes and derives the diff from emitted public cards only |
| The Inspector or Workbench is the final EBRT frontend or a hosted debugger | No; it is a provisional local read-only view over recorded public artifacts and may be replaced entirely |
| EBRT v0.5.0 computes evidence controls with real gradients | Supported inside the frozen float64 public surrogate; per-term and total finite differences pass the locked tolerance |
| v0.5.0 discovers semantic dependencies from raw language | No; its one-hop graph, signed effects, affected claim, invalidation, and target are synthetic oracle annotations |
| v0.5.0 preserves a typed non-triggered episode | Supported by the separate locked control-flow sentinel: exact neutral gates, unchanged activations/objective, and zero backward calls; this does not calibrate an event detector |
| v0.5.0 is invariant to disconnected neutral graph padding | Supported numerically for eight added edge-less nodes on the built-in synthetic graph within the locked `1e-14` tolerance; not a generic total-objective locality theorem |
| The v0.5.0 control map improves a regenerated GPT answer | Not evaluated; no provider or final generation is part of this milestone |
| v0.5-T sends exact local adjoints through a supplied temporal public-state recurrence | Supported on one locked synthetic topology; manual recurrence and autograd differ by at most `2.220446049250313e-16`, and central finite differences remain within tolerance |
| v0.5-T adds a supplied transition-control direction absent from its supplied leaf-control class | Supported by an exact witness using the same `(M + cD)h + bxg` intervention equation; adding equivalent pseudo-leaves could still algebraically collapse the enlarged class |
| v0.5-T identifies a different useful control floor when evidence order changes | Supported in all eight cells of one local topology sweep: early correction selects floor 4 `decision_write`, late correction selects floor 5 `revision_mix` |
| v0.5-T proves temporal credit assignment alone beats evidence weighting | No; the arms share standardized coordinate bounds but not terminal Jacobian scale, so the positive C-vs-B result includes oracle actuator geometry |
| The 16 v0.5-T ordered cells are independent replications or a general reasoning benchmark | No; they are two orders over eight nearby parameter settings on one synthetic topology, with gates locked after pilot implementation rather than preregistered |
| A v0.5-T control map improves a regenerated GPT answer | Not evaluated; network/provider/generation calls are zero |
| v0.5.1 projects a case-bound temporal map into blinded full-context arms | Supported offline: A is raw-only, B is textual-only, C/D differ only at six control `delta`/`role` paths, and no-event is byte-identical across arms |
| The first v0.5.1 live block compares final GPT outputs | No; all four one-attempt calls stopped at HTTP 429 `insufficient_quota`, so no model response, public card, strict grade, or output diff exists |
| The v0.5.1 quota-recovery block completes the language bridge | Supported for one contaminated case: all four one-attempt calls completed, all strict endpoints passed, and receipts/output diffs validate |
| The v0.5.1 controlled arm changes or improves the recovery output | No observed effect on this case: all four public cards are canonically identical and the baseline-to-controlled diff is empty |
| The v0.5.1 surrogate decrease predicts an improved generated answer | Not supported here; the surrogate moved from `0.755433933319` to `0.294771509854`, actual output never participated in optimization, and the recovery outputs were identical |
| The v0.5.2 English walkthrough reaches a changed final output | Supported for one synthetic non-matched episode: 2/2 calls completed and the public answer changed `POLISH → PROVE`, with R3 dropped/invalidated, R4/R6 added, and R5 preserved |
| The v0.5.2 walkthrough passes its frozen strict contract | No; 6/7 walkthrough checks passed, but the controlled final card failed `required_facts_exact` because its two changed facts split R2 and R4 rather than each citing R2+R4+R6 |
| The v0.5.2 diff proves the gradient control caused the output change | No; evidence horizon, event envelope, and run position change together, and no matched no-control after-event call exists in this product walkthrough |
| v0.5.3 repairs or regrades the frozen v0.5.2 endpoint | No; the predecessor remains `false`. v0.5.3 is a separately named, contaminated local migration/regression result |
| The v0.5.3 typed DAG closes its local regression | Yes, narrowly: lossless migration remains `FAIL` with the exact two legacy gaps; the contaminated two-edge overlay adds only final/R4 and demo/R2, and the repaired exact closure is `PASS` under network-zero validation |
| v0.5.3 autonomously discovers support roles or improves a GPT output | No; the four role bindings are explicit case annotations, the predecessor output is not rerun or regraded, and provider calls are zero |
| The v0.5.4 exact temporal arm beats its matched controls | Supported only on the frozen contaminated public program: C is below A, node-tied B, and all three locked within-node timing shams for both schedules; 17/17 mechanism gates pass |
| v0.5.4 proves general temporal reasoning or improves a hosted answer | No; it is network-zero, uses two schedules over one supplied program, and its gradients stop at the local public recurrence |
| v0.5.5 composes the sealed public trajectories without losing local provenance or exact credit | Supported on one contaminated network-zero bundle: one-lane equivalence is exact, 6/6 lane orders are byte-identical, block/autograd error is `2.22e-16`, finite-difference error is `1.238e-9`, and 10/10 gates plus 10/10 adversarial subchecks pass |
| v0.5.5 executes or improves a multi-agent system | No; its lanes are deterministic public schedule views, its junction is fixed and unlearned, and provider/model/agent/generated-output calls are zero |
| v0.6.1 carries the sealed public substrate through a real hosted output | Supported for one contaminated block: 5/5 calls completed, D returned `PROVE`, and D passed exact answer, invalidation, stable-fact, and fact-local lineage endpoints |
| v0.6.1 shows gradient-derived placement beats a matched sham | No observed effect: B, D, and C returned byte-identical passing public outputs, so the primary `D_vs_C` contrast is `NULL` |
| The v0.6.1 overall gate promoted | No; P answered `POLISH` correctly but failed exact pre-event lineage because R2 was unexpectedly inherited into `demo_centerpiece`, so the preregistered gate is held |
| The v0.6.1 canonical artifact requires the current host or current v0.5.5 tree to validate | No; the post-run pure-stdlib verifier checks the pinned recorded snapshot without importing project/provider packages, reading current v0.5.5 sources, or gating on host runtime. It does not rederive the historical mechanism or authenticate the provider. |
| A raw full-context restart failed to revise the answer | No; A answered `PROVE`, invalidated R3, and preserved R5, but failed the stricter lineage endpoint because R4 was absent from `final_priority` |
| v0.6.2.1 makes `Apply Revision -> Regenerate` executable and verifiable | Yes, for one contaminated product-acceptance path: exactly two calls completed, the actual Before fed one local backward pass, the compiled public actuator preceded full-context regeneration, and the After answer, invalidation, stable fact, and fact-local lineage all passed |
| The v0.6.2.1 `POLISH -> PROVE` diff proves that EBRT control improved or caused the answer | No; this is not a matched effect experiment, the controller target is case-specific, and `effect_attribution_status` remains `NOT_ASSESSED` |
| The v0.6.2.1 Reasoning IDE performs a new model call when replayed | No; it verifies and animates an exact hash-pinned public projection of the recorded artifact, and the replay CTA issues zero provider requests |
| v0.6.2.2 exposes Apply Revision as a live reusable product operation | Yes, operationally within typed invalidation revisions: `ebrt_live.py` validates a strict public request, uses one local float64 backward pass to rank reinspection salience, compiles typed-event suppression/preservation, server-remaps closure IDs, and terminally binds at most one no-retry After attempt to each request identity |
| A v0.6.2.2 operational `PASS` establishes semantic correctness or control efficacy | No; live verification covers request, mechanism, lineage, provider, and accounting contracts only. Semantic quality and effect attribution are both `NOT_ASSESSED` |
| Runtime Preview 2 makes the public control continuous and executable | Yes, operationally: one projected allocation step changes provider-visible review shares and abstract budget units, then a validated state machine emits the exact one-call revision operation |
| Runtime Preview 2 proves provider uptake, attention control, token-budget control, or a counterfactual output effect | No; those axes remain `NOT_ASSESSED`. Its block/restore probe establishes only structural dependency inside the selected caller-supplied public graph |
| Runtime Preview 3 implements a revisable chronological public trajectory | Yes, operationally and network-zero: a three-axis public recurrence runs forward, one real local backward assigns time-local credit, a bounded update is replayed forward, and its magnitudes compile exactly into the existing executable actuator |
| Runtime Preview 3 is equivalent to hidden-state optimization or proves a hosted control effect | No; its trajectory is a hand-built public surrogate, the gradient stops before JSON/provider execution, and no new hosted contrast was run. Provider uptake, semantic quality, causal effect, and general reasoning improvement remain `NOT_ASSESSED` |
| Runtime Preview 4 makes zero control a true event-bearing no-op | Yes, network-zero: `u=0` follows only the frozen forward recurrence and admits none of the typed event proposals; independent replay and finite-difference checks pass |
| Runtime Preview 4 requires exact placement to beat its matched sham before executing | No; the eligible-time sham matches value geometry, L2, control cost, and smoothness, but its outcome is a sealed research diagnostic excluded from product acceptance |
| v0.6.3-live-r01 establishes a null provider actuator | No; it stopped after one completed call on `EXACT_ONE_CLOSURE_FAILED`, with 15 calls unattempted and all X/Z and D/C effects not assessed |
| v0.6.3.1-live-r01 observed a non-zero public endpoint difference | Yes, narrowly: one authorized `C -> X -> D -> Z` block completed 4/4 calls; X and D selected the aligned closure while C selected the alternative and Z the mixed closure, yielding `CHANNEL_OPEN_DIRECTIONAL` and `GRADIENT_PLACEMENT_DIRECTIONAL` |
| The v0.6.3.1-live-r01 result establishes evidence-order causality or quality improvement | No; evidence order was the sole intentionally varying semantic payload field, but the one fixed serial block cannot separate treatment from temporal/provider drift, and all arms returned the same public answer `VIOLET` |
| The favorable v0.6.3.1 four-call canary opens v0.6.4 | No; its terminal decision is only `PROMOTE_TO_FRESH_REPLICATION`. v0.6.4 remains blocked until a new sealed case replicates the directional result |
| v0.6.3.2 repeated the D-versus-C public closure contrast under mirrored positions | Yes, narrowly: both blocks selected aligned for D and alternative for C, yielding `REPLICATED_DIRECTIONAL`; one serial synthetic-case execution still cannot establish causality or population reliability |
| The v0.6.3.2 result opens v0.6.4 | No; X and Z both selected aligned in both blocks, so the required positive contrast was `REPLICATED_CEILING` and the locked terminal is `STOP_REPLICATION_CEILING_NOT_ASSESSED` |
| Selective replay should be optimized before state sufficiency | Not supported by current evidence; it is paused as a quality direction and remains an unranked future efficiency ablation |
| EBRT edits hidden states inside a trained Transformer or GPT model | Not implemented |
| EBRT improves real-world LLM reasoning accuracy | Not established |
| GPT-5.6 is meaningfully integrated | Yes at the public full-context regeneration boundary in the sealed v0.6.2.1 product-acceptance path; this is integration evidence, not causal or population-level quality evidence |

This project uses the term *reasoning state* only for the harness's explicit
structured state and v0.4's public Reasoning Cards. It does not claim access to
private chain-of-thought or model internals.

## OpenAI Build Week roadmap

The team currently intends to pursue the **Developer Tools** category. That is
our project-level interpretation of the current tool shape, not an official
category determination.

- **Milestone 0 — frozen mechanism:** preserve the v0.1 monolith and its audit
  trace.
- **Milestone 1 — measurable baseline (complete):** publish matched controls,
  raw evidence, bottleneck analysis, and this claim ledger.
- **Milestone 1.5 — counterfactual instrumentation (complete):** isolate each
  revision through an event-local mirror, separate semantic relevance from
  source-projection leverage, and measure propagation, geometry, leakage, and
  efficiency.
- **Milestone 1.75 — prospective dual-route test (terminal and documented):**
  freeze a five-arm matched protocol before opening a new holdout, preserve its
  one-shot terminal ledger, and publish the rejected replay-invariance premise
  without recovering partial outcome statistics.
- **Milestone 1.8 — replay-policy factorization (DEV complete):** v0.3.1 now
  separates execution replay start from trajectory-anchor loss horizon, repairs
  the historical exact-cost invariant, and exposes loss horizon as a causal
  quality/leakage axis. Fresh promotion fixtures and a LOCKED holdout remain
  pending.
- **Milestone 2 — meaningful GPT-5.6 Language Replay Bridge (DEV complete):**
  the live observer, strict public-card adapter, three matched textual controls,
  exact provider accounting, and two-case canary now execute end to end. The
  boundary-fixed canary rejects quality parity and nominates dependency-complete
  public state as the next representation question.
- **Milestone 2.1 — Direct-vs-Full calibration (DEV complete):** the repeated
  10-case run rejects current staged Full as a primary quality scaffold, freezes
  Direct at 30/30 versus Full at 4/30, and pauses selective replay optimization.
  A no-revision-envelope one-shot raw control, cumulative-raw staging control,
  and fresh harder DEV suite come first; if the compression ablation supports
  it, a generic evidence ledger follows. Promotion evidence is still pending.
- **Milestone 2.2 — aperture controls and diagnostic successor (executed,
  decision not ready):** v0.4.1 and a fresh v0.4.2 block are both preserved.
  The successor converted one local stop into an assessed
  `invalidated_active_support` strict failure and descriptively replicated
  cumulative raw at 30/30 versus card-only at 2/30. An API timeout and an SDK
  structured-output parse failure left two paired runs non-assessable, so no
  cause decision is promoted and no run is filled or reinterpreted. The
  byte-identical r01 replication also remains not ready: its smoke passed, but
  a late contiguous 31-receipt `RateLimitError` tail left only 22/30 four-arm
  runs assessed. r01 is frozen without retry or partial fill.
- **Milestone 2.3 — provider-boundary observability (diagnostic smoke
  complete):** the unchanged reasoning protocol now separates pre-HTTP
  acquisition, HTTP status, SDK structured parsing, provider contract, and
  local public-card validation. The smoke prospectively classified 8/8
  non-assessable endpoints as `http_status/insufficient_quota`; its zero-
  provider-failure gate prevented the full block, so no reasoning comparison
  or promotion claim is available.
- **Milestone 2.4 — external differentiable control (mechanism core
  complete):** v0.5.0 freezes a typed one-hop public graph, optimizes bounded
  evidence gates with local float64 autograd, and verifies numerical gradient
  agreement, revision-only terminal-credit locality on the locked topology,
  disconnected-padding invariance, no-event identity, bounded
  projection, deterministic bytes, and no separately supplied downstream
  grader-verdict/final-answer artifact leakage.
  Semantic extraction remains future integration work. v0.5.1 implements the
  controlled full-context bridge and its recovery block completed with a null
  output effect on one saturated case; v0.5.2 separately carries a synthetic
  English walkthrough to a changed generated output without turning it into a
  causal comparison.
- **Milestone 2.5 — temporal state-control vertical experiment (positive
  synthetic record):** v0.5-T leaves v0.5.0 frozen and adds exact local
  adjoints over a supplied smooth public-state recurrence. On one topology's
  eight-cell, two-order sweep, transition-basis controls beat leaf controls and
  all five nonidentity floor permutations under the same standardized
  coordinate budget, while the top finite-leverage floor changes with order.
  Terminal actuator scales are not matched, so the result includes oracle
  control-basis geometry and is not a GPT or reasoning-quality claim. v0.5.1
  implements the horizontal generation boundary, but its first live block did
  not reach a model response or actual output comparison.
- **Milestone 2.6 — controlled full-context bridge (implemented, recovery
  complete with null output effect):** v0.5.1 binds one public language case to the
  temporal program, blinds treatment labels at the provider boundary, and
  preregisters raw-only, textual-only, matched-permutation, and gradient arms.
  The first block emitted four exact receipts but every attempt stopped at HTTP
  429 `insufficient_quota`; no semantic or quality comparison was possible.
  That bundle remains unchanged. A separately named recovery block from the
  frozen source graph then completed 4/4 strict outputs. All four public cards
  were canonically identical, so the bridge is demonstrated but no controlled
  output effect or advantage is observed. The next eligible experiment is a
  separately frozen harder English suite, not tuning this contaminated case.
- **Milestone 2.7 — English final-output walkthrough (complete strict
  near-pass):** v0.5.2 freezes a product-readable question, R1-R5 Before
  horizon, R1-R6 controlled After horizon, separate post-call gold, exact
  receipts, and public output diff. Its one allowed run completed 2/2 calls and
  visibly moved `POLISH → PROVE`, invalidated R3, added R4/R6, and preserved
  R5. The frozen endpoint remains failed because the two changed facts split
  their required evidence rather than each closing R2+R4+R6. No rerun,
  endpoint relaxation, or causal claim is permitted from this artifact.
- **Milestone 2.8 — factorized lineage regression (network-zero complete):**
  v0.5.3 separates a lossless migration that reproduces the frozen two
  fact-local gaps from a separately hashed contaminated two-edge repair. The
  minimal public program admits only Evidence, Support, Fact, and Constraint
  nodes. Its exact grammar is Evidence-to-Support `supports`,
  Support-to-Fact/Constraint or Fact-to-Fact `depends_on`, and
  Evidence-to-Evidence `invalidates`; direct Evidence-to-Fact shortcuts are
  invalid. The canonical bundle passes deterministic witness, exact-set,
  edge-ablation, tamper, rollback, and socket-denied gates. Its only closure
  additions are final/R4 and demo/R2; the predecessor verdict remains false and
  provider calls are zero.
- **Milestone 2.9 — temporal adjoint over factorized lineage (network-zero
  complete):** v0.5.4 compiles the committed v0.5.3 program without accepting
  fixture matrices, Jacobians, terminal gold, or arbitrary operator order. Its
  manual forward/reverse derivatives, autograd, finite differences, normalized
  actuator geometry, severance, identity, commutation, no-event, adversarial
  sham, and deterministic artifact gates pass. C beats A, node-tied B, and all
  locked within-node timing shams in both schedules, promoting the exact local
  temporal-placement claim only.
- **Milestone 2.10 — sealed-trajectory multiplicity (network-zero complete):**
  v0.5.5 composes the two temporal Fact lanes and one disconnected stable
  Constraint lane under a single typed incidence program. Exact one-lane
  degeneration, shared-ledger identity, lane isolation, block/autograd/finite-
  difference agreement, 6/6 full-result order invariance, separate lane/merge
  bounds, source/artifact tamper rejection, and network-zero publication all
  pass. The result promotes a separately locked v0.6 execution question; it is
  not itself multi-agent or final-output evidence.
- **Milestone 2.11 — hosted execution over sealed public lanes (complete; gate
  held):** the preregistered `P/A/B/D/C` block completed 5/5 one-attempt
  GPT-5.6 calls with exact receipts and independent artifact validation. D
  passed the strict hosted path, while raw A missed one fact-local R4 edge and
  P added one unexpected inherited R2 edge. B/D/C were byte-identical strict
  passes, so the matched placement effect is `NULL`; P's exact-lineage failure
  keeps the overall gate at `HOLD_V0_6_HOSTED_BUNDLE_GATE`. See the
  [v0.6.1 R&D note](docs/RND_HOSTED_BUNDLE_V0_6_1.md) and
  [evidence-led v0.6+ roadmap](docs/ROADMAP_V0_6_PLUS.md).
- **Milestone 3 — coherent evaluator experience (provisional Reasoning IDE):**
  a deterministic allowlist projection connects Evidence, Event, the neutral
  and revised public trajectories, time-local credit, the compiled Apply
  Revision program, and Final Output Diff. Recorded v0.6.2.1 playback remains
  available, while Runtime Preview 4 adds the zero-centered generic loopback live operation.
  The first frontend remains replaceable; hosting and a general product claim
  remain pending.
- **Milestone 4 — submission evidence:** document the Codex development record,
  provide an English demo under the event rules, include the required Codex
  feedback session, and audit every public claim against committed artifacts.

The roadmap is a plan, not a list of completed capabilities.

## How Codex and humans collaborated

Codex was used as an implementation and research collaborator to turn the
initial reasoning sketch into an executable monolith, design falsifiable
comparison arms, construct validation checks, run repository diagnostics, and
draft the public evidence surface. The commit history and submission materials
are intended to preserve that development record.

Human decisions remain explicit. In particular, the project owner chose to:

- freeze the monolith before benchmarking;
- separate public R&D evidence from the temporary submission checklist;
- require matched controls and independent gold metrics;
- defer the final product UI until the benchmark reveals the most informative
  interaction, while using a provisional read-only viewer to test the public
  artifact and observation contract;
- use instrumentation to generate and falsify new routing/revision policies,
  not only to police public claims;
- keep semantic-cause routing separate from the narrower source-projection
  leverage diagnostic;
- preserve the terminal v0.3 attempt instead of recovering unpublished partial
  metrics, and turn its replay/loss coupling into the next causal experiment;
- keep mechanism, model-integration, and accuracy claims separate;
- require meaningful GPT-5.6 use before representing the project as
  hackathon-ready;
- preserve a failed selective-quality guardrail and turn the observed public
  routing/state-sufficiency interaction into the next algorithm experiment;
- insert a one-shot Direct control before tuning selective replay, freeze its
  negative result for staged Full, and prioritize causal compression controls
  over preserving the preferred roadmap.

Codex accelerated implementation and audit work; it did not decide whether the
evidence is sufficient for a scientific or product claim.

## Development status

This repository is an early public R&D release. The frozen mechanism baseline
and counterfactual instrumentation milestones are complete. The v0.3
dual-route policy is implemented, but its preregistered one-shot comparison is
terminal and inconclusive after rejecting a replay-invariance assumption. It
does not validate or quality-rank the dual route. The replay-factorized v0.3.1
DEV harness is implemented and repairs the observed cost invariant, but it is
not a fresh holdout or quality result. The live v0.4 GPT-5.6 Language Replay
Bridge and matched two-case canary are implemented; full restart passed 2/2,
while selective replay passed 1/2 and therefore did not clear its quality
guardrail. Selective used fewer input/output tokens but more reasoning tokens.
The subsequent locked 10-case × 3-trial calibration is also complete: one-shot
fixed-envelope Direct passed 30/30 while staged public-card Full passed 4/30.
This pauses both Full and selective as quality directions until a redesigned
public state meets the Direct non-degradation gate. The v0.4.1 control attempt
then found cumulative raw at 30/30 strict outputs versus card-only at 2/28
completed outputs, while no-envelope and fixed-envelope Direct reached 29/30
and 30/30. Two card-only arms failed a local contract after a completed third
provider call, leaving the manifest incomplete and the cause decision not
ready. The unchanged r01 replication also remained incomplete. v0.4.3 then
classified all eight endpoints in its contract smoke at the typed provider
boundary, but the resulting HTTP 429 failures correctly prevented a full run.
The repository now includes a deterministic v0.4.4 Recorded Revision Workbench
that reaches final public output and a separate Provider Failure Atlas. The
v0.5.0 mechanism core now adds a frozen typed graph, real local autograd,
bounded evidence gates, deterministic public projection, and a zero-network
reproduction artifact. Its graph is synthetic and oracle-scripted, and it does
not yet consume raw language or regenerate a model answer. The separate
v0.5-T experiment now adds a supplied temporal public-state recurrence, exact
manual/autograd adjoints, order-sensitive finite leverage, transition controls,
and exhaustive matched floor shams. Its positive 16-cell local-sweep record is
explicitly bounded by unequal terminal actuator geometry and does not change a
model answer. v0.5.1 now implements the controlled full-context boundary and
preserves its first four-receipt live block, but all attempts stopped on
`insufficient_quota` before a model response. Its separately preserved recovery
block then completed all four strict outputs with an empty public-card diff.
The separate v0.5.2 English walkthrough then completed two more calls and
recorded `POLISH → PROVE`, R3 invalidation, R4/R6 support, and R5 preservation.
Its final strict contract still failed on fact-level evidence closure, so it is
preserved as a judge-readable near-pass rather than presented as a successful
causal intervention. The network-zero v0.5.3 successor now reproduces that
exact defect without adding reachability, then passes a separately labeled
contaminated dependency regression whose only additions are final/R4 and
demo/R2. The network-zero v0.5.4 successor then compiles that exact repaired
program into a temporal recurrence: manual/autograd/finite-difference checks
pass, C beats its matched node-tied and timing-placement controls in both
schedules, and the sealed 17-gate decision promotes v0.5.5. The completed
v0.5.5 successor then composes its three sealed lanes with exact block credit,
one-lane equivalence, disconnected Constraint isolation, and byte invariance
across all six input orders. The later product line now adds the loopback
`Apply Revision` API, Runtime Preview 4's zero-centered revisable public trajectory, and a
Reasoning IDE with local and sealed public Live modes. One sealed GPT-5.6
acceptance artifact and one later manual runtime smoke establish that the
full-context provider boundary can complete, while effect attribution remains
`NOT_ASSESSED`. A matched hard-suite
promotion result remains pending. The public judge demo reaches that loopback
runtime through a budgeted Sites Worker and temporary Quick Tunnel; it is not a
production service and carries no uptime guarantee.

Issues and pull requests that add reproducible tests, adversarial fixtures, or
better controls are especially welcome. Please avoid expanding claims without
corresponding evidence.

## License

Copyright 2026 Ryo SpiralArchitect.

Licensed under the [Apache License 2.0](LICENSE).
