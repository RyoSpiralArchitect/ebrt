# EBRT v0.2 instrumentation benchmark

## Outcome

- Mode: `full`
- Trials: 1536 across 48 cases and 32 paired seeds
- Instrumented events: 1312
- Multi-candidate events: 512
- Multi-candidate support: 15 case clusters, 16 case-source fixtures, 2 families
- Offline candidate probes: 1984

The event-local mirror is the attribution baseline. Curvature and semantic/source-projection-leverage
alignment are exploratory diagnostics and are not standalone quality measures.

## Core measurements

| Metric | Mean | Median | 5th–95th percentile |
| --- | ---: | ---: | ---: |
| `separation_auc` | 2.1805 | 2.1721 | 1.4509–3.1802 |
| `separation_auc_per_step` | 0.6222 | 0.6098 | 0.3982–0.8996 |
| `post_source_auc` | 0.1101 | 0.0000 | 0.0000–0.7867 |
| `post_source_mean` | 0.4930 | 0.5035 | 0.1838–0.8082 |
| `post_source_retention_ratio` | 0.9210 | 1.0000 | 0.4140–1.0000 |
| `source_projection_gain` | 0.3068 | 0.2857 | 0.1278–0.5599 |
| `target_projection_gain` | 0.9934 | 1.0056 | 0.7996–1.1461 |
| `terminal_projection_gain` | 0.2869 | 0.2606 | 0.1278–0.5599 |
| `unrelated_state_leakage` | 0.5446 | 0.7514 | 0.0000–0.9066 |
| `control_efficiency` | 0.1841 | 0.1770 | 0.0731–0.3199 |
| `excess_turn_angle_mean` | 0.2014 | 0.2207 | -0.0035–0.4616 |
| `excess_curvature_mean` | 0.4267 | 0.4668 | -0.0632–0.9825 |

## Candidate routing alignment

Single-candidate events make selection agreement mechanical, so the
multi-candidate column is the informative routing comparison.
Here `control_leverage` is only the target-aligned event-source belief
projection finite difference along one predefined topic-aligned control
direction; it is not an objective gradient or full controllability.

| Metric | All events (mean; n) | Multi-candidate only (mean; n) | Case-cluster 95% CI |
| --- | ---: | ---: | ---: |
| `attention_leverage_spearman` | 0.5000; 512 | 0.5000; 512 | [0.0667, 0.8824] |
| `selected_is_max_leverage` | 0.9024; 1312 | 0.7500; 512 | [0.5333, 0.9375] |
| `selected_leverage_regret` | 0.0155; 1312 | 0.0397; 512 | [0.0078, 0.0815] |
| `semantic_gold_is_max_leverage` | 0.6585; 1312 | 0.1250; 512 | [0.0000, 0.3333] |
| `selected_hits_semantic_gold` | 0.7561; 1312 | 0.3750; 512 | [0.1333, 0.6471] |

All five multi-candidate alignment metrics were seed-invariant within each case-source fixture. The 512 event rows therefore do not represent 512 independent routing situations.

## Session outcomes

| Metric | Mean |
| --- | ---: |
| `target_topic_success` | 0.9766 |
| `source_distance_gain` | 0.2660 |
| `target_distance_gain` | 0.7255 |
| `unrelated_topic_state_drift_max` | 0.4652 |

## Outcome and leakage associations

| Kind | Geometry/control metric | Outcome metric | Estimate | Case-cluster 95% CI |
| --- | --- | --- | ---: | ---: |
| spearman_association | `separation_auc` | `source_projection_gain` | -0.7962 | [-0.8789, -0.6631] |
| spearman_association | `separation_auc_per_step` | `source_projection_gain` | -0.2228 | [-0.5353, 0.1575] |
| spearman_association | `separation_mean` | `source_projection_gain` | -0.2348 | [-0.5352, 0.1563] |
| spearman_association | `post_source_auc` | `source_projection_gain` | 0.0604 | [-0.1422, 0.2324] |
| spearman_association | `post_source_mean` | `source_projection_gain` | 0.8120 | [0.6520, 0.8940] |
| spearman_association | `post_source_retention_ratio` | `source_projection_gain` | -0.0590 | [-0.2231, 0.1544] |
| spearman_association | `separation_terminal` | `source_projection_gain` | 0.7762 | [0.6060, 0.8703] |
| spearman_association | `excess_turn_angle_mean` | `source_projection_gain` | 0.5215 | [0.1371, 0.7303] |
| spearman_association | `excess_curvature_mean` | `source_projection_gain` | 0.4263 | [0.1001, 0.6537] |
| spearman_association | `control_delta_norm` | `source_projection_gain` | 0.2971 | [0.0903, 0.4384] |
| spearman_association | `control_efficiency` | `unrelated_state_leakage` | -0.7380 | [-0.8615, -0.5444] |
| spearman_association | `attention_leverage_spearman` | `source_projection_gain` | 0.7500 | [0.4193, 0.8641] |
| spearman_association | `selected_is_max_leverage` | `source_projection_gain` | 0.7500 | [0.4193, 0.8641] |
| successful_minus_unsuccessful_mean | `separation_auc` | `outcome_success` | 0.6743 | [0.4881, 0.9152] |
| successful_minus_unsuccessful_mean | `separation_terminal` | `outcome_success` | -0.2676 | [-0.3896, -0.0298] |
| successful_minus_unsuccessful_mean | `excess_turn_angle_mean` | `outcome_success` | -0.0090 | [-0.0638, 0.0431] |
| successful_minus_unsuccessful_mean | `excess_curvature_mean` | `outcome_success` | -0.0538 | [-0.1997, 0.0991] |
| successful_minus_unsuccessful_mean | `control_efficiency` | `outcome_success` | -0.0850 | [-0.1171, -0.0561] |
| successful_minus_unsuccessful_mean | `selected_is_max_leverage` | `outcome_success` | -0.2607 | [-0.4848, -0.0654] |

These associations are discovery signals. A non-zero association does not show
that curvature or leverage causes a better revision; obvious magnitude, distance,
sequence-length, and representation confounds remain.

## Claim boundary

- This benchmark measures a structured synthetic mechanism, not natural-language reasoning quality.
- Event-local mirrors are matched counterfactual execution traces, not private chain-of-thought or model introspection.
- Turn angle and curvature are coordinate-sensitive geometric proxies; lower or higher values are not inherently better.
- Semantic attention and offline target-aligned source-projection leverage answer different questions: why a premise is implicated versus how one predefined local control direction changes the event-source belief projection.
- Candidate control_leverage is a centered finite difference along one topic-aligned control direction; it is not full-state controllability, an objective gradient, or proof of causal optimality.
- Outcome and leakage associations are descriptive on the fixed 48-case suite and do not establish external validity or causality.
- Paired seeds control the toy generator initialization but do not close case-selection, representation, or future hosted-model nondeterminism.
