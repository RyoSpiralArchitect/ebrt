# EBRT

**Event-driven Backward Reasoning for Test-Time Inference**

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

> [!IMPORTANT]
> v0.1-v0.3.1 are **not** a Transformer implementation, a GPT latent-state editor, or
> evidence of improved language-model accuracy. Topic, stance, and revision
> targets remain structured inputs in the committed harness. v0.2 exposes an
> adapter boundary, but meaningful GPT-5.6 integration is a later milestone,
> not a capability claimed by this release.

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
docs/RND_BENCHMARK_V0_1.md    protocol, results, limits, and claim ledger
docs/RND_INSTRUMENTATION_V0_2.md measurement contract and algorithm findings
docs/RND_DUAL_ROUTE_V0_3.md   terminal invariant result and v0.3.1 direction
docs/RND_DUAL_ROUTE_V0_3_1.md factorization design, DEV results, and next experiment
artifacts/benchmark_v0_1/     committed machine-readable benchmark evidence
artifacts/demo_v0_1/trace.json committed no-build mechanism trace
artifacts/benchmark_instrumentation_v0_2/ committed v0.2 measurement evidence
artifacts/instrumentation_v0_2/ committed trace and standalone mirror figure
artifacts/.dual_route_v0_3_holdout_ledger.json canonical terminal attempt record
artifacts/benchmark_dual_route_v0_3_1_dev/ committed non-promotional DEV evidence
requirements.txt              runtime dependency declaration
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
| Events are detected autonomously from natural language | Not implemented |
| EBRT edits hidden states inside a trained Transformer or GPT model | Not implemented |
| EBRT improves real-world LLM reasoning accuracy | Not established |
| GPT-5.6 is meaningfully integrated | Not yet; explicit hackathon gate |

This project uses the term *reasoning state* only for the harness's explicit
structured state. It does not claim access to private chain-of-thought or model
internals.

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
- **Milestone 2 — meaningful GPT-5.6 adapter:** the versioned provider-neutral
  interface exists; a live GPT-5.6 implementation and matched textual controls
  remain pending.
- **Milestone 3 — coherent evaluator experience:** the deterministic standalone
  Mirror figure exists; a minimal editable or hosted judge sandbox remains
  pending. A broad product UI is still intentionally deferred.
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
- defer UI work until the benchmark reveals the most informative interaction;
- use instrumentation to generate and falsify new routing/revision policies,
  not only to police public claims;
- keep semantic-cause routing separate from the narrower source-projection
  leverage diagnostic;
- preserve the terminal v0.3 attempt instead of recovering unpublished partial
  metrics, and turn its replay/loss coupling into the next causal experiment;
- keep mechanism, model-integration, and accuracy claims separate;
- require meaningful GPT-5.6 use before representing the project as
  hackathon-ready.

Codex accelerated implementation and audit work; it did not decide whether the
evidence is sufficient for a scientific or product claim.

## Development status

This repository is an early public R&D release. The frozen mechanism baseline
and counterfactual instrumentation milestones are complete. The v0.3
dual-route policy is implemented, but its preregistered one-shot comparison is
terminal and inconclusive after rejecting a replay-invariance assumption. It
does not validate or quality-rank the dual route. The replay-factorized v0.3.1
DEV harness is implemented and repairs the observed cost invariant, but it is
not a fresh holdout or quality result. A LOCKED v0.3.1 promotion experiment,
live GPT-5.6 adapter, matched language benchmark, and hosted judge sandbox are
still pending; there is no hosted service in this release.

Issues and pull requests that add reproducible tests, adversarial fixtures, or
better controls are especially welcome. Please avoid expanding claims without
corresponding evidence.

## License

Copyright 2026 Ryo SpiralArchitect.

Licensed under the [Apache License 2.0](LICENSE).
