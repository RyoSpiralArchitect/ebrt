# EBRT v0.5-T — Temporal Adjoint State Control over a Public Reasoning Program

Status: **experimental positive synthetic mechanism record**

Runtime calls to hosted models: **0**

Relationship to v0.5.0: **new branch and schemas; all v0.5.0 files and artifacts remain frozen**

## Result in one sentence

On one synthetic oracle-specified topology and its local parameter sweep,
exact local adjoints optimized bounded transition-basis controls that
outperformed evidence-leaf controls and every matched nonidentity floor
permutation; the result includes the supplied actuator geometry and does not
isolate temporal credit assignment by itself.

## Why this branch exists

v0.5.0 established that real float64 autograd can optimize bounded evidence
gates over a frozen one-hop public graph. That result was intentionally narrow,
but it left an important ambiguity: a multi-hop graph whose only trainable
variables remain evidence leaves can still be locally collapsed into an
effective evidence-weighting Jacobian.

v0.5-T therefore asks a different, falsifiable question:

> Does a supplied temporal public-state program expose useful bounded
> intervention directions at state transitions that are absent from its
> supplied evidence-leaf control class, and does the locally most useful
> transition move when the same evidence arrives in a different order?

This is an intervention-class question, not a language-model benchmark.

## Frozen temporal program

For floor `t`, the public recurrence is

\[
h_t = \phi_t\!\left((M_t+c_tD_t)h_{t-1}
       + b_tx_t(1+e_t)\right).
\]

- \(h_t\) is an explicit three-axis public state: `premise`, `decision`, and
  `stable`.
- \(M_t\), \(D_t\), \(b_t\), \(x_t\), floor order, and activation are frozen
  synthetic fixture inputs.
- \(e_t\) is an evidence-leaf control when that floor reads evidence.
- \(c_t\) is a transition-basis control when that floor exposes a public
  transition actuator.
- `tanh` is the only activation in the locked DEV fixture. The core also
  supports exact `identity` floors for mechanism invariance checks.

Each nonzero evidence direction has L2 norm 1. Each nonzero transition basis
has Frobenius norm 1. This normalizes the local bases, but does **not** make
their terminal Jacobian norms equal after they pass through a trace. Those
observed terminal norms are published explicitly.

## Exact adjoint boundary

Let

\[
z_t=(M_t+c_tD_t)h_{t-1}+b_tx_t(1+e_t),
\qquad h_t=\phi_t(z_t).
\]

At neutral controls, the terminal adjoint and recurrence are

\[
\lambda_T=\nabla_{h_T}\mathcal L,
\]

\[
\lambda_{t-1}=M_t^\top
\left(\lambda_t\odot\phi_t'(z_t)\right).
\]

The standardized control sensitivities are

\[
\frac{\partial\mathcal L}{\partial e_t}
=
\left(\lambda_t\odot\phi_t'(z_t)\right)^\top b_tx_t,
\]

\[
\frac{\partial\mathcal L}{\partial c_t}
=
\left(\lambda_t\odot\phi_t'(z_t)\right)^\top D_th_{t-1}.
\]

The implementation computes these values twice: once with PyTorch autograd
and once with an explicit reverse recurrence. The maximum observed difference
on the locked representative traces is
`2.220446049250313e-16`. Central finite differences agree with autograd within
`7.759481945868174e-11`, below the locked `3e-8` tolerance.

No gradient crosses the following boundary:

```text
synthetic public suite / future semantic adapter output
  STOP-GRADIENT
frozen temporal public-state program
  exact local autograd and adjoint recurrence
bounded public control projection
  NON-DIFFERENTIABLE JSON
future full-context generation backend
  NOT IMPLEMENTED IN v0.5-T
```

The code does not differentiate GPT, private chain-of-thought, provider usage,
JSON serialization, or a final generated answer.

## Objective and bounded controls

The terminal-only objective is

\[
\mathcal L =
\lambda_r(h_T^{decision}-y)^2
+\lambda_s(h_T^{stable}-h_{T,0}^{stable})^2
+\lambda_c\|u\|_2^2.
\]

There is no direct “boost required support” or “suppress invalidated evidence”
loss in this experiment. The stable axis is a terminal preservation target.
`stable_read` and the later controlled `stable_carry` are separate floors, so
the stable actuator has a nonzero local Jacobian rather than being a dead sham
slot.

A, B, and C optimize three standardized control coordinates with

```text
coordinate parameterization  delta = 0.75 * tanh(logit)
maximum coordinate L2 norm   0.55
optimizer                     deterministic Adam
steps                         300
learning rate                 0.06
control L2 weight             0.01
randomness                    none
```

D performs no optimization or backward call. It inherits C's exact optimized
values and applies only a locked floor permutation.

“Same budget” here means the same coordinate count, coordinate cap, and L2
radius. It does not mean equal terminal controllability. For representative
cell P03:

| Order | Leaf terminal Jacobian norm | Transition terminal Jacobian norm | Ratio |
| --- | ---: | ---: | ---: |
| early correction | 0.303349 | 0.264342 | 0.871411 |
| late correction | 0.155681 | 0.750937 | 4.823561 |

The large late-order ratio is part of the supplied actuator geometry. It is
why the comparison cannot attribute C's advantage to “better adjoint credit”
alone.

## Four arms

All arms are evaluated by rolling their final controls through the same actual
temporal recurrence.

### A — `static_collapsed_leaf`

The terminal state is linearized at neutral leaf controls:

\[
\hat h_T(e)=h_T(0)+J_e e.
\]

A optimizes that static collapse, then applies its selected leaf controls back
to the nonlinear temporal program. It is a v0.5.0-style scalar evidence-gate
baseline, not an invocation of the frozen v0.5.0 executable.

### B — `temporal_leaf_only`

B optimizes the same three evidence-leaf controls through the full nonlinear
recurrence. At neutral, A's collapsed gradient and B's true temporal gradient
agree within `8.326672684688674e-17`. This expected equality records that
adding temporal notation to leaf-only controls does not itself create a new
local control class.

### C — `temporal_state_transition`

C keeps all evidence leaves neutral and optimizes the three supplied
transition bases: `decision_write`, `revision_mix`, and `stable_carry`.

### D — `matched_floor_shuffle_sham`

D applies C's exact final values to a locked nonidentity permutation of target
floors. It preserves the exact value multiset, sign multiset, sparsity, and L2
norm. The L2 mismatch is at most `1.1102230246251565e-16`.

The audit also evaluates all five possible nonidentity permutations, so the
result does not depend on selecting one weak sham after inspection.

## Paired order sweep

The DEV fixture contains eight nearby parameter cells on **one topology**.
They are not eight independent tasks or replications. Each cell is evaluated
under two orders with the same evidence values:

```text
early correction
stable_read -> legacy -> correction -> decision -> revision -> stable_carry

late correction
stable_read -> legacy -> decision -> correction -> revision -> stable_carry
```

This yields 16 ordered cells. The gate thresholds were frozen with the
mechanism artifact after pilot implementation; this is not a preregistered
study and the 16/16 counts must not be interpreted as binomial generalization
evidence.

## Locked result

| Arm | Aggregate actual terminal task loss | Mean over 16 ordered cells |
| --- | ---: | ---: |
| A static collapsed leaf | 6.134341859646 | 0.383396366228 |
| B temporal leaf only | 6.056278736103 | 0.378517421006 |
| C temporal state transition | **3.354650695400** | **0.209665668463** |
| D locked matched shuffle | 9.219280479837 | 0.576205029990 |

Within this local sweep:

- C beat B in 16/16 ordered cells;
- C beat locked D in 16/16 ordered cells;
- C reduced aggregate task loss by 44.6087% relative to B;
- C beat every one of the five nonidentity floor permutations in 16/16 cells;
- the strongest nonidentity sham had aggregate loss 4.393432925291;
- all eight cells moved the top finite-leverage target from
  `decision_write` at floor 4 under early correction to `revision_mix` at
  floor 5 under late correction;
- every order-specific top target exceeded the second-ranked finite leverage
  by at least the locked 0.01 margin.

The lock records a positive synthetic mechanism result, not an empirical model
promotion.

## Sensitivity and finite leverage are separate

The diagnostic sidecar calls the signed local derivative
`signed_adjoint_sensitivity`. It deliberately does not call it “attention.”
Gradient magnitude changes with coordinate choice, saturation, and supplied
operator scale.

For each control, the audit also applies one fixed `0.10` step in the locally
improving sign and records

\[
\text{finite leverage}_i
=\mathcal L_{task}(0)-\mathcal L_{task}(\delta_i).
\]

Three floor concepts remain distinct:

- structural earliest floor: a nonzero supplied graph path exists;
- active earliest floor: finite leverage is at least 25% of the maximum for
  that trace;
- top finite-leverage floor: the largest measured fixed-step task gain.

None is called a GPT replay start. v0.5-T has no GPT execution backend.

## Reachable-subspace witness

A separate exact two-axis linear witness uses the same intervention equation
as the main core:

\[
h_t=(M_t+c_tD_t)h_{t-1}+b_tx_t(1+e_t).
\]

When evidence enters before a transition, the supplied leaf control has zero
terminal-decision Jacobian while the supplied transition basis has Jacobian 1.
Reversing those two floors makes the transition Jacobian zero because no state
has yet reached its basis. This proves only that the **admitted** transition
class adds a reachable direction to the **admitted** leaf class and that its
leverage depends on order. Adding equivalent state-control pseudo-leaves could
algebraically collapse the enlarged linear system, so universal
non-collapsibility is not claimed.

## Mechanism integrity checks

The committed self-tests require:

1. exact schema, ID, shape, normalized-basis, permutation, and semantic-hash
   validation;
2. manual adjoint recurrence agreement with autograd;
3. central finite-difference agreement;
4. A/B collapsed neutral-gradient equivalence;
5. premise-to-decision edge severing removes upstream leaf credit;
6. an inserted exact identity floor preserves terminal state and gradients;
7. order-dependent top-control ID, ordinal, and finite-leverage margin;
8. exhaustive nonidentity sham evaluation;
9. bounded controls and rollback behavior;
10. exact no-event identity with zero backward calls;
11. observer construction leaves execution-control-map bytes unchanged;
12. recursive forbidden-key and semantic-hash tamper rejection;
13. same-runtime byte determinism; and
14. successful local execution while socket creation is denied.

## Artifact split

v0.5-T does not extend the frozen `ebrt-evidence-control-map-v0.5.0` schema.
It emits two new surfaces:

- `ebrt-execution-control-map-v1.0.0`: actionable evidence or transition
  controls only;
- `ebrt-temporal-adjoint-audit-v0.5-t.0`: sensitivities, finite leverage,
  structural/active/top floor diagnostics, and the neutral public trajectory.

The audit is a detachable observer. Building it cannot change execution-map
bytes. Curvature, SOL lanes, semantic extraction, controlled full-context
generation, final output diff, and UI integration remain outside this branch.

## Reproduce

```bash
python3 temporal_adjoint_state_controller_v0_5_t.py self-test
python3 temporal_adjoint_state_controller_v0_5_t.py validate \
  --input-json fixtures/temporal_adjoint_state_controller_v0_5_t_dev.json
python3 temporal_adjoint_state_controller_v0_5_t.py validate \
  --input-json fixtures/temporal_adjoint_state_controller_v0_5_t_no_event.json
python3 benchmark_temporal_adjoint_state_control_v0_5_t.py self-test
python3 build_temporal_adjoint_state_control_artifact_v0_5_t.py self-test
python3 build_temporal_adjoint_state_control_artifact_v0_5_t.py validate
```

Committed evidence lives in
`artifacts/temporal_adjoint_state_control_v0_5_t/`. Canonical byte identity is
asserted only for the Python/PyTorch/platform runtime recorded in its manifest.

## Claim ledger

| Claim | Status |
| --- | --- |
| Exact local adjoints traverse the supplied temporal public recurrence | Supported on the locked synthetic topology; manual recurrence and autograd agree within tolerance |
| Transition controls add an admitted terminal direction absent from admitted leaf controls | Supported by the exact same-equation reachable-subspace witness |
| The useful transition target changes with evidence order | Supported in all eight cells of this one-topology sweep, with locked ID, ordinal, and margin checks |
| C beats B because temporal credit assignment is intrinsically better | Not isolated; terminal actuator Jacobian scales differ and are oracle-supplied |
| Eight cells are independent replications | No; they are nearby parameters on one topology |
| The controller discovers dependencies or causal structure | No; topology, matrices, controls, event, and target are fixture inputs |
| Adjoint sensitivity is model attention or causal importance | No |
| v0.5-T changes a GPT output | Not evaluated; provider and generation calls are zero |
| v0.5-T improves LLM reasoning | Not established |

The next horizontal experiment may project this control map into one
full-context regeneration call. That experiment must preserve this actuator
geometry caveat and compare actual generated outputs under a separately locked
protocol.
