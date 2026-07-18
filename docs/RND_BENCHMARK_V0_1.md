# EBRT v0.1 Benchmark: Protocol, Evidence, and Claim Boundary

**Status:** Reportable v0.1 baseline complete

**Scope:** Structured mechanism benchmark, not an LLM accuracy evaluation

**Frozen monolith SHA-256:**
`b1702f2868839d989cc3a9321d227436a23c3dad6cc86483edee9d5dbab3a529`

This note is the public R&D record for the EBRT v0.1 benchmark. It is separate
from the team's temporary hackathon submission checklist. The benchmark may
inform that submission, but this document exists to make the mechanism's
evidence, limitations, and next experiments independently inspectable.

> [!NOTE]
> Every number below comes from the committed full-run bundle. Quick and profile
> smoke runs were used only to validate the harness and are not evidence cited
> in this note.

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

The full run completed without a source-integrity, numerical, accounting,
control-bound, or locality assertion failure. The raw bundle is committed at
`artifacts/benchmark_v0_1/`.

### 7.1 Run identity

| Field | Value |
| --- | --- |
| Run timestamp | `2026-07-17T19:39:15Z` (`2026-07-18 04:39:15 JST`) |
| Source commit | `37f81340f534b5ce0259b6e1f34ebe16f1cbc71b` |
| Manifest SHA-256 | `fe7050e5eb4e41358be032643b3e6eb7847df266cd684944d7943ebd75d37d4d` |
| Trials | 7,680 correctness + 630 profile = 8,310 |
| Elapsed time | 177.804 seconds |
| Platform | macOS 26.2, arm64, CPU, float32, one PyTorch thread |
| Python / PyTorch | CPython 3.13.13 / PyTorch 2.11.0 |

### 7.2 Primary contrasts

| Contrast | Estimand | Point estimate | 95% CI / exact test | Interpretation |
| --- | --- | ---: | --- | --- |
| D−A | Target-topic success | +0.4210 | case-cluster 95% CI `[+0.2682, +0.5790]` | Full EBRT improves the labeled revision topic on this suite |
| D−C | Source-distance gain | +0.0493 | case-cluster 95% CI `[+0.0187, +0.0813]` | Informed routing adds continuous source alignment; its binary endpoint gain is smaller |
| E−D | Gold-target distance gain | +0.2228 | case-cluster 95% CI `[+0.1096, +0.3419]` | Forcing the annotated target improves that local target, not final performance |
| B−A | External wall time | +0.2166 ms | case-cluster 95% CI `[+0.1512, +0.3162]` | Detection/scaffolding preserves output but adds cost |

Arm-level target-topic success was 0.5556 for A and B, 0.9549 for C, 0.9766
for D, and 0.9115 for E. D−C target-topic success was +0.0217 with a
case-cluster 95% CI of `[0.0000, +0.0495]`. D's all-topic conjunction gain over
A was +0.0859, but its 95% CI `[-0.0078, +0.1849]` crossed zero. The evidence
therefore supports correction of the labeled revision topic, not a claim that
the whole multi-topic trajectory improves uniformly.

Gold-route E had perfect annotated routing recall and the strongest local
target-distance gain (0.9483), but lower source-distance gain (0.1494 versus
D's 0.2660) and lower final target-topic success (0.9115 versus 0.9766). This
rejects the assumption that an annotated semantic cause is automatically the
best recurrent control location.

### 7.3 Stable-case safety

| Metric | Result |
| --- | ---: |
| Unnecessary event rate | 0/192 stable trials for each detector-bearing arm |
| Unnecessary revision rate | 0/192 stable trials for C, D, and E |
| Pre-target state drift | 0.0 maximum across all arms and trials |
| Non-target control leakage | 0.0 maximum across all arms and trials |
| D unrelated-topic state drift | 0.4652 mean maximum norm; suffix propagation is not topic-local |
| D rollback-to-best rate | 478/1,312 revision events (36.4%); all 1,312 were still accepted |

“Rollback” here means choosing the best optimizer checkpoint instead of its
last iterate, not rejecting the revision back to the zero-control baseline.

### 7.4 Runtime and scaling

| Profile | Median | p95 | MAD | Step-accounting note |
| --- | ---: | ---: | ---: | --- |
| Forward-only correctness trials | 0.516 ms | 1.024 ms | 0.094 ms | median 4 generator steps |
| Detect-only correctness trials | 0.680 ms | 1.234 ms | 0.125 ms | median 8 generator steps |
| Full EBRT correctness trials | 11.419 ms | 22.001 ms | 5.595 ms | median 111; p95 222 generator steps |

| Scaling slice | Result | Accounting / interpretation |
| --- | --- | --- |
| No-event T=2048 | A 68.604 ms; B 332.898 ms; D 328.794 ms | T=256→2048 wall-time exponent: A 0.94, D 1.36 |
| One far event at T=2048, D | 4,908.228 ms | 75,776 generator steps |
| Revision steps 1→64, D | 7.045→143.195 ms | 192→2,208 generator steps on the fixed fixture |
| Replay distance far/middle/near, D | 68.828 / 38.699 / 12.297 ms | Same revision-step count; suffix length changes |

Revision-step scaling was approximately monotone: D rose from 7.045 ms at one
optimizer step to 143.195 ms at 64. Replay distance also mattered: far, middle,
and near targets took 68.828, 38.699, and 12.297 ms respectively. Changing
`top_k` from 1 to 4 on its small fixture left runtime near 17.2 ms and did not
change generator-step count, so the current dense update path does not realize
a compute benefit from narrower routing.

### 7.5 Result narrative

H1 is supported for the labeled target topic and stable-case preservation, but
not for the stricter all-topic conjunction. H2 receives partial support: D
improves source-distance gain over random routing, while its binary success
gain is modest and its routing-informative gold recall (0.5000) is essentially
the same as C's (0.5014). H3 is supported only as a local target intervention;
the idea that E is a task-performance ceiling is rejected. H4 is supported: B
reproduces A exactly and costs more. H5 holds for controls and states before the
selected target, but unrelated-topic suffix states still move. H6 passed every
trial-level assertion.

The detector-bearing arms show event precision and recall of 1.0 only because
the benchmark labeler and detector share the same explicit structured event
contract. This result says nothing about natural-language semantic detection.

## 8. Failure clusters

Failure records are diagnostic flags and can overlap; they are not 3,702
independent task failures. Counts below are trial-level flags from
`failures.jsonl`.

| Cluster | Count | Observable signature | Likely layer | Next discriminating test |
| --- | ---: | --- | --- | --- |
| Event miss / false event | 0 | Exact source-step labels matched | Structured detector contract | Replace oracle fields with a model-produced semantic adapter |
| Wrong annotated route | 695 | C: 343, D: 352; 537 were multi-anchor cases | Router / target definition | Split recency, contradiction, and stale-anchor families and score control leverage separately |
| Gold route, failed endpoint | 102 | E route recall 1.0 but target-topic output wrong; 96 were multi-anchor trials | Objective / propagation | Decompose local target gain, source gain, and final decode per event |
| Local update versus replay failure | Not uniquely identifiable | The same 102 E candidates can fail after a strong local target update | Generator/replay | Add per-suffix survival curves before assigning a layer |
| Rollback to best checkpoint | 1,540 | C: 521, D: 477, E: 542 trial flags; revisions remained accepted | Optimizer/checkpoint policy | Early-stop on best energy and measure saved replay work |
| Budget suppression | 1,248 | B: 1,152 by design; C/D/E: 32 each | Resource policy | Separate detector audit from executable-budget outcome in reports |

Target-topic failures were A: 512, B: 512, C: 52, D: 27, and E: 102. The D
route misses concentrate in the multi-anchor and sequential families. Because
many route misses still end in the correct binary label, routing recall and
continuous distance must remain visible instead of relying on success alone.

Do not label every wrong target as one isolated distractor. Where the trace
supports it, preserve broader wrong-anchor families such as recency bias,
connection underspecification, or stale-anchor attraction.

## 9. Bottleneck inventory

The following inspection-derived candidates were tested by the full profile:

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

| Rank | Bottleneck | Evidence | Impact | Candidate mitigation |
| ---: | --- | --- | --- | --- |
| 1 | Repeated suffix replay | One-event D at T=2048 took 4,908.228 ms and 75,776 generator steps; 1→64 optimizer steps increased latency 7.045→143.195 ms; far replay was 5.6× near | Dominant event-path cost | Add adaptive early stopping, cache unchanged prefixes, and benchmark bounded replay windows |
| 2 | Superlinear no-event scaffold | At T=2048, D took 328.794 ms versus A's 68.604 ms; T=256→2048 exponent was 1.36 for D versus 0.94 for A; B matched D | Wasted cost even when no revision occurs | Keep incremental state buffers and per-topic indices; avoid repeated `torch.stack(prefix)` and all-prior scans |
| 3 | Semantic-route / control-location mismatch | D informative gold recall 0.5000; E improved local target gain by 0.2228 over D but reduced source gain by 0.1166 and target success by 0.0651 | Limits routing interpretation and whole-trajectory reliability | Separate semantic causal anchors from control-leverage candidates; penalize unrelated-topic propagation and score both layers |

The dense full-sequence control tensor remains an implementation concern, but
this run did not isolate its cost. The near-identical `top_k=1/2/4` timings are
consistent with the current dense path, not proof that sparse controls cannot
help. Full audit artifacts total roughly 5.7 MB, dominated by raw trials and
diagnostic failure records; trace verbosity is a storage concern but not the
leading measured runtime bottleneck.

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
| The public benchmark leaves the frozen monolith unchanged | Before/after SHA guard and manifest | Supported for this run; both digests equal `b1702f…a529` |
| Full EBRT beats forward-only on this suite | Full paired D−A results | Supported for target-topic success; not established for the all-topic conjunction |
| Informed routing adds value over revision alone | Routing-informative paired D−C results | Partially supported by source-distance gain; binary gain is modest and gold recall is not better than random |
| Stable sequences are preserved | Stable-family false-event, revision, and leakage metrics | Supported for stable fixtures and pre-target/control locality; unrelated suffix topics are not invariant |
| EBRT detects semantic changes in natural language | Natural-language detector benchmark | Not implemented / not claimed |
| EBRT edits a Transformer or GPT hidden state | Trained-model integration and intervention evidence | Not implemented / not claimed |
| EBRT improves LLM reasoning accuracy | External task benchmarks with adequate controls | Not established / not claimed |
| GPT-5.6 is meaningfully integrated | Reproducible adapter, matched textual controls, and traces | Future hackathon gate |

## 12. Next experiments

Proceed in evidence order:

1. preserve this full structured run as the immutable v0.1 baseline;
2. add an incremental no-event scaffold and rerun the same length profile;
3. add adaptive replay stopping/windowing and rerun the revision-step and
   replay-distance profiles;
4. split semantic-anchor routing from control-leverage routing, add propagation
   survival metrics, and extend the adversarial routing fixtures without
   changing the frozen baseline suite;
5. introduce a GPT-5.6 semantic adapter at one explicit boundary;
6. compare that adapter with a matched textual self-revision control and an
   unchanged forward-only control;
7. test whether structured event and routing decisions remain auditable under
   model-generated inputs;
8. build the minimum evaluator interface around the most discriminating trace,
   after the evidence identifies it.

Promotion beyond mechanism proof requires success on the benchmark that
corresponds to the new claim. Plumbing alone is not promotion evidence.

## 13. Artifact checklist

The committed reportable bundle contains:

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
