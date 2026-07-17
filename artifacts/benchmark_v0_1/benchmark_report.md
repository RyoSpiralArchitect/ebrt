# EBRT v0.1 generated benchmark report

- Run ID: `ebrt-v0.1-full-20260717T193915Z-3a12be03`
- Mode: `full`
- Correctness trials: 7680
- Profile trials: 630
- Scope: fixed structured synthetic mechanism suite

> This report does not establish natural-language event detection, GPT or
> Transformer hidden-state repair, or improved LLM reasoning accuracy.

## Correctness summary

Target-topic success is primary on event-bearing cases. The all-topic
conjunction is secondary because unrelated-topic memory can dominate it.

| Arm | Target-topic success | All-topic success | Source gain | Target gain | Router recall | Informative recall | Median ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A_forward_only_1pass | 0.556 | 0.396 | 0.000 | 0.000 | n/a | n/a | 0.516 |
| B_detect_only_budget0 | 0.556 | 0.396 | 0.000 | 0.000 | n/a | n/a | 0.680 |
| C_random_route_revision | 0.955 | 0.493 | 0.217 | 0.699 | 0.739 | 0.501 | 11.611 |
| D_ebrt_full | 0.977 | 0.482 | 0.266 | 0.726 | 0.738 | 0.500 | 11.419 |
| E_oracle_route_revision | 0.911 | 0.505 | 0.149 | 0.948 | 1.000 | 1.000 | 12.202 |

`router recall` includes proposals for budget-suppressed events; the
machine-readable results also report executed-routing recall separately.
Internal energy is retained as a diagnostic and is not a quality metric.

## Paired contrasts

| Contrast | Metric | Mean delta | Case-cluster 95% CI | Unadjusted McNemar p |
| --- | --- | ---: | --- | ---: |
| full_minus_forward | target_topic_success | 0.421 | [0.268, 0.579] | 2.00e-146 |
| full_minus_random_route | source_distance_gain | 0.049 | [0.019, 0.081] | n/a |
| oracle_minus_full | target_distance_gain | 0.223 | [0.110, 0.342] | n/a |
| detect_minus_forward | external_wall_ms | 0.217 | [0.151, 0.316] | n/a |

McNemar values treat repeated case×seed pairs descriptively and do not
adjust for within-case correlation. Case-cluster bootstrap intervals are
the primary uncertainty summary.

## Evidence-led bottleneck read

- Full versus random routing must be judged on paired distance and route
  metrics as well as the binary endpoint. In this run their target-topic
  success rates are 0.977
  and 0.955.
- The gold-route arm is a privileged annotated-target intervention, not a
  presumed performance ceiling. Its target-distance gain is
  0.948, while full
  EBRT's is
  0.726. Compare this
  with source-distance gain and final target-topic success before inferring
  that the semantic anchor is the best recurrent control location.
- Stable-case attempted and accepted revision rates are reported separately
  in `results.json`; zero accepted revisions alone would not rule out wasted
  detector or optimizer work.

## Scaling profile

The exponent below is a two-point engineering diagnostic from T=256 to
T=2048, not a formal complexity proof.

- Forward-only no-event wall-time exponent: 0.94
- Full-scaffold no-event wall-time exponent: 1.36

| Length | A median ms | B median ms | D median ms |
| ---: | ---: | ---: | ---: |
| 4 | 0.393 | 0.498 | 0.484 |
| 16 | 0.802 | 1.239 | 1.229 |
| 64 | 2.391 | 4.193 | 4.267 |
| 256 | 9.715 | 19.512 | 19.498 |
| 512 | 17.269 | 43.019 | 43.183 |
| 1024 | 34.374 | 112.486 | 112.841 |
| 2048 | 68.604 | 332.898 | 328.794 |

The implementation inspection predicts repeated prefix materialization and
all-prior eligibility scans on long scaffolded runs, dense control tensors
for sparse updates, and suffix replay multiplied by revision-step count.
Treat the profile as confirmation or rejection of that ranking, not as an
LLM-serving latency estimate.

## Claim boundary

- This is a fixed synthetic mechanism benchmark, not a language-model reasoning benchmark.
- Event inputs and revision targets are derived from oracle-structured topic, stance, confidence, and cue fields.
- The frozen generator is a tiny continuous-state toy model, not a pretrained Transformer hidden manifold.
- Energy reduction is an optimized in-system objective and is not treated as independent quality evidence.
- Runtime and memory measurements apply only to the recorded software, hardware, dtype, and benchmark protocol.
- No result establishes natural-language semantic detection, pretrained-model repair, or production generalization.

Raw paired trials, summaries, failures, source digests, fixture digest,
environment, and protocol are recorded beside this report.
