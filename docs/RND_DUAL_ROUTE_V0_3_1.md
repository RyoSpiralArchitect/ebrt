# EBRT v0.3.1: replay/loss factorization

## Status

EBRT v0.3.1 is a **non-promotional DEV_DRAFT**. It repairs and measures the
mechanism exposed by the terminal v0.3 attempt. It does not rerun the consumed
holdout as a promotion split: one exact case is rerun only as contaminated
regression. It is not a dual-route quality ranking or evidence about natural-
language or LLM reasoning.

The frozen v0.3 policy, runner, lock, fixtures, and terminal ledger remain
unchanged. The exact failing case is copied into a separately labeled
`contaminated_historical_regression` fixture and can never enter promotion
statistics.

## The algorithmic correction

v0.3 used one `replay_floor` for two distinct operations:

1. where recurrent suffix recomputation physically starts; and
2. where the trajectory-anchor loss begins averaging state deviation.

v0.3.1 makes both decisions explicit in every route plan:

```text
semantic objective
      x
control sites
      x
trajectory_anchor_floor    reasoning-policy / loss axis
      x
execution_replay_floor     exact-preserving compute axis
```

`probe_mode` now controls only whether an arm pays the online leverage probe.
It cannot select either floor. The ambiguous `replay_floor` field does not
exist in the v0.3.1 plan or revision trace.

The online source-projection probe also adopts the corrected v0.2 feasibility
contract. It uses a centered finite difference when both requested endpoints
are inside the frozen control ball and a projected-forward one-sided derivative
at the boundary. Both projected endpoints are still executed so matched probe
accounting remains constant across arms.

## Two independent lanes

### Exact cost lane

The cost lane fixes:

- event and candidate set;
- semantic objective anchor;
- selected control sites;
- matched online probe and epsilon;
- trajectory-anchor floor;
- optimizer, steps, and norm caps.

It changes only `execution_replay_floor` from the minimum eligible candidate to
the minimum selected control. The run fails closed unless committed events,
controls, final states, decoded output, and their outcome fingerprint are exact.
Generator accounting must decrease or remain equal.

### Trajectory-horizon factorial

The factorial fixes the same route and physical replay, then changes only
`trajectory_anchor_floor` from the minimum eligible candidate to the minimum
selected control. Generator and backward accounting must be exact across the
pair. Outcome changes are allowed and measured, because the loss horizon is now
named as an end-to-end reasoning policy rather than disguised as a cost option.

This lane is the bridge from observability to algorithm design. Future horizon
policies can use preregistered pre-outcome signals—such as event-local
propagation, leakage, or curvature regimes—without changing physical replay or
silently redefining the objective.

## Fixtures and contamination boundary

The combined DEV/regression bundle uses:

- two DEV cases with new IDs, families, topics, text, stance values, and
  confidence values, checked automatically against the consumed v0.3 holdout;
- four model seeds (`0..3`);
- S2, L2, and D2 where applicable;
- the exact v0.3 terminal case for S2 only, isolated as contaminated regression.

The historical regression retains source step 10, candidates `(0, 2, 4, 6,
8)`, and semantic controls `(2, 4)`. With 32 optimizer steps, the common floor
requires 374 optimizer replay steps and the selected-control floor requires
306. These values are locked as regression expectations, not rediscovered
promotion endpoints.

No v0.3 holdout, stable, or sequential case is eligible for v0.3.1 promotion.
A future full run requires entirely fresh families, case IDs, topics, text, and
numeric values for all three roles.

## Initial DEV and regression measurement

The deterministic quick bundle contains 24 fresh DEV lane groups plus four
contaminated historical-regression lane groups. The split is reported before
the combined view so historical contamination cannot inflate the DEV result.

| Split | Exact cost equality | Shorter floor | Replay saved | Mean per separated group | Factorial changed |
| --- | ---: | ---: | ---: | ---: | ---: |
| Fresh DEV | 24/24 | 12/24 | 320 | 26.67 | 12/24 |
| Contaminated regression | 4/4 | 4/4 | 272 | 68 | 4/4 |
| Combined diagnostic bundle | 28/28 | 16/28 | 592 | 37 | 16/28 |

All 16 groups with a changed floor preserved exact cost-lane outcomes and
changed under the trajectory-only factorial. This pattern supports the narrow
mechanism diagnosis: physical replay shortening is exact on these cases when
the mathematical objective is held fixed, while loss-horizon selection is a
real policy intervention.

On the terminal historical case at seed 0:

- `execution_replay_floor: 0 -> 2` reduced replay work `374 -> 306`;
- events, controls, final states, decoded output, and outcome fingerprint were
  exact;
- `trajectory_anchor_floor: 0 -> 2` with execution fixed changed controls by a
  maximum absolute `0.0040507913`, final state by `0.0027348399`, and changed
  decoded output.

The DEV epsilon audit retained the same L2 leverage rank at `1e-4`, `1e-3`, and
`1e-2`. This is one case and does not establish global rank stability.

## Runtime contract correction

v0.3 required its exact recorded environment for every command. v0.3.1 splits
the contract:

- `full`: exact Python, PyTorch, OS, machine, device, and dtype match; any drift
  fails before ledger or output creation;
- `self-test`, `quick`, `epsilon-audit`: supported CPython 3.11+, PyTorch 2.x,
  CPU/float32 may run;
- every DEV output records expected environment, actual environment, matched
  status, and each mismatch;
- nonmatching DEV output is non-promotional and has no cross-runtime byte-
  reproducibility claim.

Self-tests inject a supported runtime-drift sentinel and an unsupported Python
sentinel. They call the ledger and full-bundle writers with both a non-exact
full contract and the exact current runtime under `DEV_DRAFT`, verifying that
neither can create a path. DEV commands also reject the canonical full paths
and all descendants.

## What this changes in the research roadmap

v0.3.1 does more than repair a claim boundary. It creates a controllable
experimental axis:

1. use execution floor only for compute optimization under exact invariance;
2. treat trajectory horizon as a potentially adaptive reasoning policy;
3. measure horizon effects on target gain, propagation, unrelated-state
   leakage, and control magnitude;
4. preregister a selector before opening entirely fresh promotion fixtures;
5. only then return to the capacity-matched dual-route quality comparison.

The next lock should not simply pick the horizon that looks best on these DEV
rows. It should define a small causal factorial or a pre-outcome selection rule,
then test it on fresh data.

## Claim ledger

Supported now:

- execution and trajectory floors are separate code paths and trace fields;
- the v0.3 terminal counterexample passes the factorized exact-cost invariant;
- the same case's divergence is reproduced by changing loss horizon alone;
- DEV quick, epsilon, source/evidence SHA, accounting, and runtime sentinels
  pass;
- old v0.3 evidence remains byte-identical.

Not supported:

- v0.3.1 improves held-out quality;
- one trajectory horizon is generally best;
- D2 beats S2 or SR2;
- results generalize beyond the fixed structured mechanism;
- a pretrained model, GPT-5.6, or natural-language reasoning is improved.

## Reproduce the DEV surface

```bash
python3 dual_route_policy_v0_3_1.py --self-test
python3 benchmark_dual_route_v0_3_1.py self-test
python3 benchmark_dual_route_v0_3_1.py quick \
  --output benchmark_results/v0_3_1_quick
python3 benchmark_dual_route_v0_3_1.py epsilon-audit \
  --output benchmark_results/v0_3_1_epsilon.json
```

`python3 benchmark_dual_route_v0_3_1.py full` must fail while
`policy_lock_v0_3_1.json` remains `DEV_DRAFT`. There is intentionally no
v0.3.1 holdout ledger.
