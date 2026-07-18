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

> [!IMPORTANT]
> v0.1-v0.3.1 are **not** a Transformer implementation, a GPT latent-state
> editor, or evidence of improved language-model accuracy. v0.4 meaningfully
> executes GPT-5.6 at the public adapter/replay boundary, but still does not
> access hidden states or private chain-of-thought, and its two-case DEV canary
> does not establish a general accuracy improvement. The repeated calibration
> is also contaminated DEV evidence; its Direct arm receives fixed revision
> metadata and is not an unqualified plain-API baseline.

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
language_replay_bridge_v0_4.py public cards, pre-outcome plan, three replay lanes
openai_reasoning_provider_v0_4.py strict GPT-5.6 Responses providers
benchmark_language_replay_v0_4.py offline gates, live canary, grading, bundles
policy_lock_v0_4.json        non-promotional Language Replay DEV contract
fixtures/language_replay_v0_4_*.json separated DEV inputs and machine gold
benchmark_direct_full_calibration_v0_4.py completion-ceiling Direct/Full runner
policy_lock_direct_full_calibration_v0_4.json frozen two-arm DEV contract
docs/RND_BENCHMARK_V0_1.md    protocol, results, limits, and claim ledger
docs/RND_INSTRUMENTATION_V0_2.md measurement contract and algorithm findings
docs/RND_DUAL_ROUTE_V0_3.md   terminal invariant result and v0.3.1 direction
docs/RND_DUAL_ROUTE_V0_3_1.md factorization design, DEV results, and next experiment
docs/RND_LANGUAGE_REPLAY_V0_4.md live protocol, result, failure, and v0.4.1 axis
docs/RND_DIRECT_FULL_CALIBRATION_V0_4.md repeated result and state-loss diagnosis
artifacts/benchmark_v0_1/     committed machine-readable benchmark evidence
artifacts/demo_v0_1/trace.json committed no-build mechanism trace
artifacts/benchmark_instrumentation_v0_2/ committed v0.2 measurement evidence
artifacts/instrumentation_v0_2/ committed trace and standalone mirror figure
artifacts/.dual_route_v0_3_holdout_ledger.json canonical terminal attempt record
artifacts/benchmark_dual_route_v0_3_1_dev/ committed non-promotional DEV evidence
artifacts/benchmark_language_replay_v0_4_fake_dev/ scripted plumbing evidence only
artifacts/benchmark_language_replay_v0_4_live_smoke/ boundary-fixed GPT-5.6 DEV canary
artifacts/benchmark_direct_full_calibration_v0_4_dev/ non-promotional 10-case DEV evidence
requirements.txt              runtime dependency declaration
requirements-live.txt         separately pinned OpenAI/Pydantic live dependencies
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

Validate the v0.4 public-state bridge and deterministic plumbing bundle:

```bash
python3 language_replay_bridge_v0_4.py
python3 benchmark_language_replay_v0_4.py self-test
python3 benchmark_language_replay_v0_4.py fake-dev \
  --output benchmark_results/v0_4_fake_dev
```

The local provider is explicitly gold-backed and proves plumbing only. To run
the locked two-case GPT-5.6 canary, install the separate live dependencies and
provide `OPENAI_API_KEY` through the process environment:

```bash
python3 -m pip install -r requirements-live.txt
python3 openai_reasoning_provider_v0_4.py
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
| Public-card compression alone caused the Full deficit | Not yet isolated; a cumulative-raw staged control is required to separate compression from repeated-call/prompt effects |
| Selective replay should be optimized before state sufficiency | Not supported by current evidence; it is paused as a quality direction and remains an unranked future efficiency ablation |
| EBRT edits hidden states inside a trained Transformer or GPT model | Not implemented |
| EBRT improves real-world LLM reasoning accuracy | Not established |
| GPT-5.6 is meaningfully integrated | Yes at the public observer/replay boundary in a complete DEV canary; not yet promotion evidence |

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
public state meets the Direct non-degradation gate. A no-revision-envelope
one-shot raw control, cumulative-raw staged control, generic evidence ledger,
fresh harder DEV and promotion suites, and a hosted judge sandbox remain
pending; there is no hosted service in this release.

Issues and pull requests that add reproducible tests, adversarial fixtures, or
better controls are especially welcome. Please avoid expanding claims without
corresponding evidence.

## License

Copyright 2026 Ryo SpiralArchitect.

Licensed under the [Apache License 2.0](LICENSE).
