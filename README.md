# EBRT

**Event-driven Backward Reasoning for Test-Time Inference**

EBRT v0.1 is an executable mechanism proof for a simple question: can a
reasoning process detect a structured change, route a bounded revision to an
earlier state, replay only the affected suffix, and leave an audit trail?

The repository deliberately starts small. The frozen monolith demonstrates the
mechanism over structured toy states, while a separate benchmark measures when
backward routing helps, when it does not, and what it costs.

> [!IMPORTANT]
> v0.1 is **not** a Transformer implementation, a GPT latent-state editor, or
> evidence of improved language-model accuracy. Topic, stance, and revision
> targets are structured inputs in the current harness. Meaningful GPT-5.6
> integration is a later milestone, not a capability claimed by this release.

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
docs/RND_BENCHMARK_V0_1.md    protocol, results, limits, and claim ledger
artifacts/benchmark_v0_1/     committed machine-readable benchmark evidence
artifacts/demo_v0_1/trace.json committed no-build mechanism trace
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

After installing the single runtime dependency, the shortest executable check
is:

```bash
python3 ebrt_monolith_v0_1.py --self-test
python3 benchmark_ebrt_v0_1.py --self-test
```

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

## Current scope and claim boundary

| Statement | v0.1 status |
| --- | --- |
| A bounded event-triggered backward-revision loop executes end to end | Demonstrated by the structured harness and self-tests |
| The frozen core can be evaluated through an external matched benchmark | Covered by the benchmark and SHA guard |
| EBRT improves the labeled revision topic relative to forward-only on this suite | Supported by the committed full benchmark |
| EBRT improves every topic in the trajectory | Not established; the all-topic CI crosses zero |
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
- **Milestone 2 — meaningful GPT-5.6 adapter:** replace structured-oracle
  assumptions at a clearly defined boundary, benchmark it against matched
  textual controls, and retain observable rollback behavior.
- **Milestone 3 — coherent evaluator experience:** add the smallest useful
  interface or sandbox after the benchmark defines what must be shown. UI work
  is intentionally deferred during Milestone 1.
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
- keep mechanism, model-integration, and accuracy claims separate;
- require meaningful GPT-5.6 use before representing the project as
  hackathon-ready.

Codex accelerated implementation and audit work; it did not decide whether the
evidence is sufficient for a scientific or product claim.

## Development status

This repository is an early public R&D release. The benchmark and committed
artifacts complete the first milestone. A product interface and meaningful
GPT-5.6 adapter are still pending, and there is no hosted service in v0.1.

Issues and pull requests that add reproducible tests, adversarial fixtures, or
better controls are especially welcome. Please avoid expanding claims without
corresponding evidence.

## License

Copyright 2026 Ryo SpiralArchitect.

Licensed under the [Apache License 2.0](LICENSE).
