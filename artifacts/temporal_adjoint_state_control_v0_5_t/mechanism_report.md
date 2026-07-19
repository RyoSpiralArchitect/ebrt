# EBRT v0.5-T temporal adjoint state-control mechanism report

Status: **RECORD_POSITIVE_TEMPORAL_STATE_CONTROL_MECHANISM**

## Locked question

Can controls over supplied public state transitions add a useful intervention class beyond evidence-leaf gates under the same standardized coordinate count and L2 cap, while exact local adjoints move the nominated intervention point when evidence order changes?

## Four-arm result

| Arm | Sum of actual terminal task loss (16 cases) |
| --- | ---: |
| `A_static_collapsed_leaf` | 6.134341859646 |
| `B_temporal_leaf_only` | 6.056278736103 |
| `C_temporal_state_transition` | 3.354650695400 |
| `D_matched_floor_shuffle_sham` | 9.219280479837 |

Across the 16 ordered cells of one local parameter sweep, the temporal state-transition arm beat the temporal leaf arm in **16/16** cells and the locked shuffled-floor sham in **16/16**. Its aggregate loss reduction versus temporal leaf control was **44.61%**.
It also beat all five nonidentity control-floor permutations in all 16 cells; the best such sham had aggregate loss `4.393432925291`.

## Order-sensitive intervention

For all eight parameter cells, the largest fixed-step finite control leverage moved with order:

- early correction: `decision_write` at `F04:decision`
- late correction: `revision_mix` at `F05:revision`

The representative execution maps remained inside the shared L2 budget:

- early: `0.55`
- late: `0.55`

## Numerical and anti-decoration checks

- collapsed A/B neutral-gradient max error: `8.326672684688674e-17`
- matched-sham L2 max error: `1.1102230246251565e-16`
- all control bases are normalized locally, but terminal Jacobian norms are not matched; actuator-scale rows are published in `arm_comparison.json`
- manual temporal adjoints and central finite differences are checked by the core self-test
- the audit is a detached sidecar; observing it does not alter execution-map bytes
- no-event is exact identity with zero backward calls
- network calls: `0`

## Claim boundary

- All public transitions, control bases, evidence values, ordering, event flags, and terminal targets are synthetic oracle inputs.
- A and B have the same neutral local gradient by construction; finite controls can diverge because A is a linearization.
- The eight parameter cells are a local sweep of one topology, not eight independent replications.
- Leaf and transition arms share standardized coordinate count and L2 bounds, not matched terminal Jacobian scale; C versus B therefore includes oracle actuator-geometry leverage and does not isolate temporal credit assignment alone.
- C winning under that shared coordinate budget supports a supplied-intervention-class result, not dependency discovery or universal non-collapsibility.
- Adjoint sensitivity and finite leverage are local surrogate diagnostics, not causal importance or model attention.
- No provider, hidden state, final natural-language output, downstream grader, latency, or token count participates.
- No hosted-model reasoning-quality, efficiency, production-readiness, or real-world causal claim is supported.

The recorded mechanism claim is therefore limited to:

> On one synthetic oracle-specified topology and its parameter sweep, exact local adjoints optimized bounded transition-basis controls that outperformed leaf controls and every matched floor permutation. The result includes the supplied actuator geometry.
