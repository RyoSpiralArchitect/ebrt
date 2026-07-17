# EBRT v0.1 Benchmark: Protocol, Evidence, and Claim Boundary

**Status:** Protocol frozen; results pending the reportable full run

**Scope:** Structured mechanism benchmark, not an LLM accuracy evaluation

**Frozen monolith SHA-256:**
`b1702f2868839d989cc3a9321d227436a23c3dad6cc86483edee9d5dbab3a529`

This note is the public R&D record for the EBRT v0.1 benchmark. It is separate
from the team's temporary hackathon submission checklist. The benchmark may
inform that submission, but this document exists to make the mechanism's
evidence, limitations, and next experiments independently inspectable.

> [!NOTE]
> Sections marked **Pending full run** are intentionally empty. Do not replace
> them with quick-run measurements. The generated report and manifest should be
> committed alongside the filled sections.

## 1. Research question

Can a bounded, event-triggered backward revision improve an independently
scored structured toy task relative to matched forward-only and random-routing
controls, without revising stable cases unnecessarily?

The question is deliberately narrower than “does EBRT improve language-model
reasoning?” The current system receives structured topic, stance, and revision
information. It does not infer semantic events from natural language or edit a
trained model's hidden states.

## 2. Hypotheses

The full benchmark tests the following preregistered directional hypotheses:

- **H1 — total mechanism value:** full EBRT (D) outperforms forward-only (A) on
  cases that require revision, while preserving stable cases.
- **H2 — routing value:** full EBRT (D) outperforms random-route revision (C) on
  routing-informative cases.
- **H3 — annotated-target intervention:** gold-route revision (E) increases
  correction at the annotated causal target relative to full EBRT (D). It is
  not assumed to upper-bound final task performance because control location
  and semantic causality can diverge in a recurrent system.
- **H4 — scaffold cost:** detect-only (B) matches forward-only (A) on final
  outputs but incurs measurable detector/scaffolding latency.
- **H5 — locality:** accepted revisions do not materially alter states before
  the selected target or unrelated topics.
- **H6 — bounded execution:** control norms, event budgets, and rollback checks
  remain within configured limits for every trial.

These hypotheses are about this fixed synthetic suite. A positive result is not
evidence of natural-language generalization.

## 3. Comparison arms

| ID | Arm | Intervention | Diagnostic role |
| --- | --- | --- | --- |
| A | `forward_only_1pass` | True one-pass generation with zero controls | Baseline task outcome and cost |
| B | `detect_only_budget0` | Run event detection with revision budget set to zero | Detector/scaffold overhead and false-event audit |
| C | `random_route_revision` | Keep event, update, and replay logic; choose a seeded random eligible same-topic target | Revision control without informed routing |
| D | `ebrt_full` | Use the frozen v0.1 event, routing, optimization, replay, and rollback loop | Mechanism under test |
| E | `oracle_route_revision` | Route to the independently specified gold causal target | Privileged intervention, not a deployable baseline or assumed performance ceiling |

Trials are paired by case and model seed. Variant execution order is
deterministically shuffled to reveal order-dependent contamination. The random
route seed is separate from the model seed.

## 4. Fixture suite

The fixed suite contains 48 synthetic cases:

| Family | Count | What it probes |
| --- | ---: | --- |
| Stable / no shift | 6 | Unnecessary-event and unnecessary-revision behavior |
| Below / zero threshold | 6 | Detector specificity near the no-event boundary |
| Exact / above threshold | 6 | Threshold-edge determinism |
| Single-anchor shift | 6 | Basic event, routing, and correction behavior |
| Multi-anchor routing | 12 | Aligned, recency, stale-anchor, and contradiction traps |
| Interleaved multi-topic | 6 | Topic locality and interference |
| Sequential / budget | 4 | Multiple events, suppression, and event-budget behavior |
| Long-horizon correctness | 2 | Replay distance and accumulated suffix effects |

Every fixture declares, independently of the mechanism:

- expected event steps;
- gold target steps for each event;
- expected final label by topic;
- expected revision target;
- whether routing is informative;
- expected suppressed events; and
- fixture family.

Routing-informative fixtures contain multiple eligible past positions for the
same topic; otherwise the random and informed routing arms would be identical.
Fixture contents and their digest are recorded in `manifest.json`.

## 5. Execution protocol

### 5.1 Correctness run

- Model seeds: `0..31`
- Random-routing seed: `10000 + model_seed`
- Bootstrap seed: `20260718`
- Device and dtype: CPU, float32
- PyTorch intra-op and inter-op threads: 1
- Pairing unit: case × model seed
- Reportable mode: `--full`

The exact CLI, Python and PyTorch versions, platform, processor, thread counts,
source digests, fixture digest, and seed lists are recorded in the committed
manifest. `--quick` is for smoke testing only.

### 5.2 Latency and scaling run

Correctness timing is reported separately from controlled scaling profiles.
The profile varies:

- sequence length: 4 through 2048;
- revision steps: 1, 4, 8, 16, 32, and 64;
- event count: 0, 1, 2, and 4;
- replay distance: near, middle, and far;
- routing width (`top_k`): 1, 2, and 4.

Warm-up policy, repetition count, and trial ordering must be copied from the
generated manifest into the completed report. Latency summaries use median,
p95, and median absolute deviation rather than only a mean.

### 5.3 Integrity checks

The benchmark self-test must verify at least:

- the monolith digest before and after execution;
- deterministic fixture and route fingerprints;
- zero-control behavior in A;
- output equivalence of A and B, apart from detector metadata and cost;
- matched event metadata for C and D;
- eligibility and same-topic locality for random targets;
- correct gold targets in E;
- execution-order independence;
- frozen core parameters, bounded controls, and finite values;
- expected generator/replay accounting;
- deterministic statistics/schema helper checks; and
- absence of writes to the frozen monolith.

## 6. Metrics and statistics

### 6.1 Primary quality metrics

- **Target-topic success:** the expected final label is satisfied for topics
  that actually contain a labeled revision event.
- **All-topic conjunction:** every topic label is satisfied. This stricter
  secondary metric can expose unrelated-topic interference, but is not used as
  the sole revision-quality measure.
- **Gold target distance gain:** reduction in absolute distance from the gold
  revision target.
- **Routing recall@k:** the gold causal target is contained in routed targets.
- **Unnecessary revision rate:** stable cases revised despite no required
  correction.
- **Latency:** wall-clock cost under the controlled CPU protocol.

The mechanism's internal energy is recorded only as a diagnostic. It is not a
primary correctness metric and must not be described as “reasoning quality.”

### 6.2 Diagnostic metrics

- event precision, recall, and F1 at exact labeled source steps;
- attention mass on gold targets;
- accepted revision, rollback, and suppression counts;
- control saturation;
- pre-target drift and non-target leakage;
- generator, backward, and replay step counts;
- gain per unit compute;
- frozen-core hash, decode count, and non-finite-value checks; and
- serialized artifact size.

### 6.3 Statistical treatment

- Binary paired outcomes: paired success delta with case-cluster bootstrap
  uncertainty. Exact McNemar values over case×seed pairs are retained only as
  unadjusted descriptive diagnostics because repeated seeds within a case are
  correlated.
- Continuous outcomes: paired difference summaries.
- Uncertainty: fixed-seed case-level bootstrap confidence intervals.
- Runtime: median, p95, and median absolute deviation.
- Routing analysis: report both all cases and the routing-informative subset.

The synthetic fixture collection is the inference population for this study.
Confidence intervals measure sensitivity within this suite; they do not confer
external validity.

## 7. Results

**Pending full run.** Populate this section only from the committed full-run
artifacts, and include the artifact manifest digest.

### 7.1 Run identity

| Field | Value |
| --- | --- |
| Run timestamp | `[PENDING FULL RUN]` |
| Git commit | `[PENDING FULL RUN]` |
| Manifest SHA-256 | `[PENDING FULL RUN]` |
| Trial count | `[PENDING FULL RUN]` |
| Platform | `[PENDING FULL RUN]` |
| Python / PyTorch | `[PENDING FULL RUN]` |

### 7.2 Primary contrasts

| Contrast | Estimand | Point estimate | 95% CI / exact test | Interpretation |
| --- | --- | ---: | --- | --- |
| D−A | Total mechanism value | `[PENDING]` | `[PENDING]` | `[PENDING]` |
| D−C | Informed-routing value | `[PENDING]` | `[PENDING]` | `[PENDING]` |
| E−D | Annotated-target intervention | `[PENDING]` | `[PENDING]` | `[PENDING]` |
| B−A | Detector/scaffold cost | `[PENDING]` | `[PENDING]` | `[PENDING]` |

### 7.3 Stable-case safety

| Metric | Result |
| --- | ---: |
| Unnecessary event rate | `[PENDING]` |
| Unnecessary revision rate | `[PENDING]` |
| Pre-target drift | `[PENDING]` |
| Non-target leakage | `[PENDING]` |
| Rollback rate | `[PENDING]` |

### 7.4 Runtime and scaling

| Profile | Median | p95 | MAD | Step-accounting note |
| --- | ---: | ---: | ---: | --- |
| Forward-only | `[PENDING]` | `[PENDING]` | `[PENDING]` | `[PENDING]` |
| Detect-only | `[PENDING]` | `[PENDING]` | `[PENDING]` | `[PENDING]` |
| Full EBRT | `[PENDING]` | `[PENDING]` | `[PENDING]` | `[PENDING]` |
| Scaling sweep | `[PENDING]` | `[PENDING]` | `[PENDING]` | `[PENDING]` |

### 7.5 Result narrative

`[PENDING FULL RUN: summarize what the preregistered contrasts establish, what
they fail to establish, and whether any hypothesis must be rejected. Separate
statistical uncertainty from engineering significance.]`

## 8. Failure clusters

**Pending full run.** Classify every failed or rolled-back trial by the earliest
observable failure boundary, preserving representative case IDs and trace
links.

| Cluster | Count | Observable signature | Likely layer | Next discriminating test |
| --- | ---: | --- | --- | --- |
| Event miss / false event | `[PENDING]` | `[PENDING]` | Detector | `[PENDING]` |
| Wrong routed target | `[PENDING]` | `[PENDING]` | Router | `[PENDING]` |
| Correct target, ineffective update | `[PENDING]` | `[PENDING]` | Optimizer/control | `[PENDING]` |
| Correct local update, replay failure | `[PENDING]` | `[PENDING]` | Generator/replay | `[PENDING]` |
| Constraint rejection / rollback | `[PENDING]` | `[PENDING]` | Acceptance policy | `[PENDING]` |
| Budget suppression | `[PENDING]` | `[PENDING]` | Resource policy | `[PENDING]` |

Do not label every wrong target as one isolated distractor. Where the trace
supports it, preserve broader wrong-anchor families such as recency bias,
connection underspecification, or stale-anchor attraction.

## 9. Bottleneck inventory

The following are **inspection-derived candidates**, not measured conclusions.
The full profile must confirm, reject, or reorder them:

1. prefix states are repeatedly materialized and all prior positions are
   scanned, which may dominate long no-event sequences;
2. the optimizer maintains a dense sequence-length × control-dimension tensor
   even when revision targets are sparse;
3. each optimizer step replays the affected suffix, multiplying cost by replay
   distance and revision-step count;
4. per-event pre/post traces improve auditability but may dominate serialized
   artifact size;
5. routing evidence can be uninformative when only one eligible prior anchor is
   present; and
6. the structured oracle boundary limits how much detector or semantic
   bottleneck evidence v0.1 can provide.

### Measured bottleneck ranking

**Pending full run.** For each bottleneck, report the profile slice, observed
scaling, confidence or variability summary, and proposed mitigation. Preserve
negative results.

| Rank | Bottleneck | Evidence | Impact | Candidate mitigation |
| ---: | --- | --- | --- | --- |
| 1 | `[PENDING]` | `[PENDING]` | `[PENDING]` | `[PENDING]` |
| 2 | `[PENDING]` | `[PENDING]` | `[PENDING]` | `[PENDING]` |
| 3 | `[PENDING]` | `[PENDING]` | `[PENDING]` | `[PENDING]` |

## 10. Threats to validity

- **Synthetic-task validity:** structured fixtures may reward assumptions baked
  into the mechanism and do not represent open-ended language reasoning.
- **Oracle boundary:** topic, stance, event expectations, and gold targets are
  available as structured data; a real system must infer or obtain them.
- **Implementation coupling:** benchmark arms share implementation components,
  so a common defect can survive every contrast.
- **Privileged intervention:** E uses annotated gold information and cannot be
  compared as a deployable system. The annotated causal target may also differ
  from the control location that best changes the final recurrent output.
- **Finite fixture diversity:** 48 designed cases cover named mechanisms, not
  the space of possible sequences.
- **Hardware specificity:** CPU wall-clock measurements need not extrapolate to
  accelerators or hosted model latency.
- **Seed sensitivity:** fixed seeds improve reproducibility but do not eliminate
  sensitivity to initialization or random routing.
- **Metric multiplicity:** secondary metrics are exploratory; primary contrasts
  must remain visually and narratively distinct.
- **Artifact observer effect:** full audit traces add runtime and storage cost.

## 11. Claim ledger

| Claim | Evidence required | Current disposition |
| --- | --- | --- |
| The structured EBRT loop executes end to end | Monolith self-tests and traces | Supported at mechanism level |
| The public benchmark leaves the frozen monolith unchanged | Before/after SHA guard and manifest | Must be reverified for every run |
| Full EBRT beats forward-only on this suite | Full paired D−A results | Pending full run |
| Informed routing adds value over revision alone | Routing-informative paired D−C results | Pending full run |
| Stable sequences are preserved | Stable-family false-event, revision, and leakage metrics | Pending full run |
| EBRT detects semantic changes in natural language | Natural-language detector benchmark | Not implemented / not claimed |
| EBRT edits a Transformer or GPT hidden state | Trained-model integration and intervention evidence | Not implemented / not claimed |
| EBRT improves LLM reasoning accuracy | External task benchmarks with adequate controls | Not established / not claimed |
| GPT-5.6 is meaningfully integrated | Reproducible adapter, matched textual controls, and traces | Future hackathon gate |

## 12. Next experiments

Proceed in evidence order:

1. run and freeze the full structured benchmark;
2. optimize only the measured top bottleneck, then rerun the same protocol;
3. add adversarial routing fixtures without changing the frozen baseline suite;
4. introduce a GPT-5.6 semantic adapter at one explicit boundary;
5. compare that adapter with a matched textual self-revision control and an
   unchanged forward-only control;
6. test whether structured event and routing decisions remain auditable under
   model-generated inputs;
7. build the minimum evaluator interface around the most discriminating trace,
   after the evidence identifies it.

Promotion beyond mechanism proof requires success on the benchmark that
corresponds to the new claim. Plumbing alone is not promotion evidence.

## 13. Artifact checklist

The reportable bundle should contain:

```text
artifacts/benchmark_v0_1/
  manifest.json
  trials.csv
  summary.csv
  results.json
  benchmark_report.md
  failures.jsonl
```

Before publication, verify that the bundle contains no credentials, private
paths, clipboard transcripts, hidden prompts, or local-only submission notes.
