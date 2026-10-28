# Counterbalanced replication on harder minimum-repair cases

Status: **COLLECTED; MINIMAL OUTPUTS 1/6 VS 2/6, NINE PROVIDER TIMEOUTS**

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

## Executed results

The run used source `01089c5116c2ad72fdcb2676bb07475bdbceddae`, fixed before
the plan and provider requests. It completed on 2026-10-26 (Asia/Tokyo); offline
verification and result review completed on 2026-10-27. The saved collection
was inspected and verified without starting another run.

| Problem | Trial | Full repair | Gradient feedback | Exact minimum |
| --- | --- | --- | --- | ---: |
| 24 vertices | 1 | Feasible, minimal: 12 edits | Provider timeout | 12 |
| 24 vertices | 2 | Provider timeout | Feasible, minimal: 12 edits | 12 |
| 36 vertices | 1 | Provider timeout | Provider timeout | 18 |
| 36 vertices | 2 | Provider timeout | Provider timeout | 18 |
| 48 vertices | 1 | Provider timeout | Feasible, minimal: 21 edits | 21 |
| 48 vertices | 2 | Provider timeout | Provider timeout | 21 |

| Condition | Planned / attempted | Completed | Feasible | Exactly minimal |
| --- | ---: | ---: | ---: | ---: |
| Full repair | 6 / 6 | 1 / 6 | 1 / 6 | 1 / 6 |
| Gradient feedback | 6 / 6 | 2 / 6 | 2 / 6 | 2 / 6 |

All three completed candidates passed format and every graph constraint.
All three judges returned PASS and agreed on every individual criterion.
Separate direct checks of the raw colors confirmed palette, coverage, A=RED,
edge inequalities, changed-vertex sets, and the exact edit counts. Minimality
comes from the independently verified oracles, not the judges.

Every missing solver output had error `HOSTED_PROVIDER_TIMEOUT`, with a
configured 60-second request timeout. These are not token-exhaustion records
or mathematically incorrect colorings. Their actual logged latencies range
from about 60.07 to 67.49 seconds; the transport timeout is not an exact global
wall-clock deadline. Provider usage fields are null for all nine timeouts,
so total token consumption/cost and the unfinished answers' quality are unknown.
No zero usage is imputed and no full efficiency comparison is justified.

The observed difference is one extra usable minimal answer under these request
settings. It is not a demonstrated reasoning-quality advantage. On 24 vertices,
the successful arm swapped between trials. The feedback-only 48-vertex success
in trial 1 did not recur in trial 2. All completed answers were optimal, while
timeouts leave nine mathematical outcomes unassessed. With only three selected
problems and two trials, latency, provider conditions, sampling variability,
and mechanism effects cannot be separated.

Known solver usage and latency for the three completed outputs:

| Case / trial / condition | Input tokens | Output tokens | Reasoning tokens | Latency (seconds) |
| --- | ---: | ---: | ---: | ---: |
| 24 / 1 / Full repair | 774 | 3036 | 2894 | 58.59 |
| 48 / 1 / Gradient feedback | 2854 | 3297 | 3035 | 50.37 |
| 24 / 2 / Gradient feedback | 1456 | 3014 | 2872 | 50.92 |

All twelve planned solver requests were attempted once. Three judges ran and
nine were explicitly skipped because no completed raw answer existed. Thus
the block made fifteen actual requests, not twenty-four. Collection is COMPLETE,
execution is FAIL because of provider errors, and offline integrity verification
is PASS for all fifteen attempts and skipped slots. No retries, extra cases,
sampling, or timeout/budget adjustment followed.

```text
plan:   cb31d6f3bc0e49f94a979c1167861a39a4b2df7763fa2fc7e262952cf2c6b6f3
report: e24bdda2227d4a9aa1f05f36c00dad3820f424227054a8ce6b3353558924935b
verify: 2c39be6ffe84f9058a88e2125d95e57269936cfe0830e8dc15bd7a51dba9b401
```

Plan, full raw report, and verification receipt remain in private 0600 files
outside the checkout. The natural follow-up is a separately declared comparison
with a matched, longer timeout while retaining the output budget and all cases,
to separate answer quality from missing observations. That follow-up was not
executed in this block.
