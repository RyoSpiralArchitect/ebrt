# Counterbalanced replication on harder minimum-repair cases

Status: **PREFLIGHT; ONE FIXED 24-ATTEMPT BLOCK**

PR #54 was reviewed and merged at
`6402312c1fe28ade7bc14e57da8d2cded04952fb`. Review found no required fixes;
all 221 tests and three closed report replays passed. No GitHub CI checks
were configured. This new study starts from that merged main revision.

## Fixed problems, independent optima

| Case | Vertices | Current edges | Added conflicts | Minimum edits | Exact-search states | Selection seed |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| hard-24 | 24 | 46 | 15 | 12 | 204 | 262442 |
| hard-36 | 36 | 75 | 24 | 18 | 922 | 263617 |
| hard-48 | 48 | 92 | 39 | 21 | 1537 | 264802 |

Each problem uses RED/GREEN/BLUE, fixes A=RED, and starts from an assignment
valid on the old edges. Other vertices use fixed-length labels N01 onward,
so concatenated edge criterion names remain unambiguous. Every case has at
least two distinct optimal repairs. All three are infeasible if changes are
restricted to vertices on the initially conflicting edges. The unchanged
solver prompt allows changes outside those suggested vertices.

`generate_hard_repair_cases.py` constructs cases offline, with no hosted
calls. For each size n=24,36,48, try seeds 260000+n*100+i for i=1..200. Draw
prior and planted feasible colors with A=RED; sample current edges between
unequal planted colors with probability 6.5/(n-1). Require at least three
conflicts, at least one inactive vertex, minimum edits >= floor(n/3), two
optimal witnesses, and no optimum confined to initially conflicting vertices.
Select the first qualifying case also visiting at least 200/500/1000 states
in the deterministic minimum-edit search. This adds an offline structural
search-load criterion rather than relying on vertex count alone. It does not
guarantee any particular LLM difficulty or constitute a random benchmark.
Earlier denser candidates were rejected before any model calls because their
optima were too easy for the exact search. No case was selected from LLM
success/failure or observed arm differences.

Optima and restricted infeasibility were checked independently using SciPy
1.17.0's MILP solver (successful exact optimization with zero MIP gap) and a
separate branch-and-bound coloring search in `ebrt_hard_oracle.py`. The latter
is also cross-checked against brute force on twelve small random graphs,
including restricted and unrestricted variants. Runtime planning revalidates
all fixture optima, two feasible minimum witnesses, and prior/correction
consistency. Witnesses and optimum metadata never enter solver/judge prompts.
The planted assignment is not supplied to the models.

SciPy is optional, for reproducing fixtures only:

```bash
python -m pip install -r requirements-hard-oracle.txt
python generate_hard_repair_cases.py --output /tmp/hard-repair-cases.json
```

## Unchanged repair and fixed collection

The study directly reuses `backward_feedback`, `solver_invocation`, and the
existing per-graph assessment/judge routines. No earlier execution source is
edited. Model gpt-5.6-sol, low reasoning effort, solver output ceiling 4096,
60-second timeout, and no-retry policy are retained. The judge output ceiling
is 4096 here, for up to 95 criterion booleans; it is equal across both arms.
Judges assess feasibility only, with fresh contexts and hidden arm/trial/
prior/gradient/oracle information. They share the solver backend.

There are exactly two trials per case and condition. Trial 1 runs cases
24,36,48, with full repair before gradient feedback. Trial 2 runs cases
48,36,24, with gradient feedback first. Each pair's two raw outputs are then
judged in the corresponding order. Both trials use identical prompts for a
given case and arm. No seeds or hidden model state are controlled; these are
repeated requests, not six independent problems per arm.

Maximum attempts: 12 solver + 12 judge = 24. Maximum requested output ceiling:
98304 tokens (24*4096), not actual consumption. Completed malformed/infeasible
answers and well-formed disagreements are retained. A solver provider failure
skips only its judge; the independent remaining conditions continue. Judge
protocol/provider errors are recorded. Model drift or a pre-dispatch error
stops collection. No repeated sampling, case replacement, prompt adjustment,
or budget increase is selected from outcomes.

Primary endpoints are completed outputs, feasible repairs, and exactly minimal
repairs out of all six planned trials per arm. Missing/invalid outputs never
vanish from denominators. Per-case paired outcomes and excess changes among
feasible answers are retained; the best of two trials is not the endpoint.
Judge agreement is a separate diagnostic. Collection completion does not imply
execution success or mathematical correctness. Three selected problems and two
trials per condition support descriptive findings, not a general superiority
claim. Feedback bundles explicit conflict information with gradients; any
observed difference cannot isolate a gradient-specific mechanism.

Plans pin cases, trial schedule, source hashes, settings, and Torch version.
Private receipts remain outside the checkout, with no overwrite or automatic
retry. Offline verification reconstructs all attempted/skipped slots, grades,
and denominators from raw records. It checks consistency, not authenticity.

```bash
python ebrt_hard_repair.py plan --output /tmp/hard-repair-plan.json
python ebrt_hard_repair.py run --plan /tmp/hard-repair-plan.json --output /tmp/hard-repair-report.json
python ebrt_hard_repair.py verify --plan /tmp/hard-repair-plan.json --report /tmp/hard-repair-report.json --output /tmp/hard-repair-verification.json
```

Preflight passed all 228 network-zero tests. Seven new tests cover independent
brute-force oracle checks, exact prompt reuse across trials, counterbalanced
ordering, the 24-attempt ledger, six planned trials per arm, skipped judges,
invalid outputs, judge disagreement, model drift, hidden retries, tampering,
and truncated collections. The optional SciPy generator reproduced the fixture
byte-for-byte before any hosted requests. Existing execution sources have no
diff against merged main.
