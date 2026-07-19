# EBRT v0.5.3-v0.5.5 Research Roadmap

Status: **v0.5.3 COMPLETE; v0.5.4-v0.5.5 PROSPECTIVE — EACH MILESTONE HAS ITS OWN LOCK**

This roadmap translates the [Core Thesis](EBRT_CORE_THESIS.md) through three
orthogonal axes before any multi-agent execution claim:

```text
v0.5.3  Space         factorized dependency program
v0.5.4  Time          temporal adjoint over that program
v0.5.5  Multiplicity  composition of sealed trajectories
v0.6+   Execution     external models or agents populate those trajectories
```

The versions are promotion gates, not calendar labels. A negative or
incomplete result is frozen at the version where it occurs. Later work must not
relax, refill, or retrospectively regrade that artifact.

## Immutable starting point

The source state tagged `v0.5.2-inspector-breakpoint` is the predecessor
checkpoint at commit `6cd42f2528cab6df2c943e1e080d14c7904fb0e5`. Its
canonical hosted artifact remains a strict near-pass with
`walkthrough_contract_passed=false`.

The roadmap never changes that endpoint. v0.5.3 uses a new namespace for a
known, contaminated engineering regression motivated by the observed
fact-local lineage defect; that network-zero milestone is now complete.

## Shared rules

Every milestone must declare before its reportable run:

1. exact source, fixture, policy, schema, and artifact hashes;
2. the controller inputs and forbidden downstream inputs;
3. positive endpoint, negative controls, stop rule, and incomplete-run policy;
4. deterministic projection and receipt surfaces;
5. separate mechanism, provider, generated-output, and grader fields; and
6. claim language that remains valid if the primary gate fails.

An implementation-discovered change may be bold, but it must be prospective:
amend the still-unrun lock or create a successor namespace. It must not rewrite
a completed predecessor artifact.

Run health and semantic acceptance remain separate:

```text
run_status         COMPLETE | DEGRADED | INCOMPLETE
regression_status  PASS | FAIL | NOT_ASSESSED
```

`ALL_GREEN` is reserved for a complete block in which every declared strict
pair passes. Provider failure may make a block incomplete; it does not become a
semantic success or failure by imputation.

## v0.5.3 — Space: Factorized Lineage Regression

### Question

Can a minimal typed public dependency program distinguish aggregate evidence
availability from fact-local direct and inherited support, while preserving the
v0.5.2 failure as immutable evidence?

### Minimal representation

Node types are limited to:

- `evidence` — an admitted public observation or update;
- `support` — an interpreted intermediate reason;
- `fact` — a decision fact evaluated by the endpoint; and
- `constraint` — a public invariant that must be preserved.

Edge relations are limited to:

- `supports` — only `Evidence -> Support`;
- `depends_on` — only `Support -> Fact|Constraint` or `Fact -> Fact`; and
- `invalidates` — only `Evidence -> Evidence`.

Direct `Evidence -> Fact|Constraint`, `Support -> Support`, every outgoing
`Constraint` edge, and all other type pairs are invalid. This grammar forces
evidence interpretation through an explicit Support node without growing into
a general knowledge graph.

`supports` and `depends_on` form the positive lineage DAG. `invalidates` is a
separate temporal revocation relation and never counts as positive support.
Every edge is labeled exactly `observed`, `migration_inferred`, or
`repair_overlay`; only the final class may add reachability informed by the
known v0.5.2 defect.

### Two migrations, never one reinterpretation

1. **Lossless migration:** translate only the relationships explicitly present
   in the frozen v0.5.2 public card. It must reproduce the same fact-level
   missing-support diagnosis. A translation that silently passes is a migration
   bug.
2. **Contaminated repair overlay:** add exactly the separately declared
   dependency edges motivated by the known defect. It has its own provenance,
   hash, grade, and report. A pass is an engineering-regression result, not a
   fresh reasoning result.

Closure output must distinguish direct evidence from inherited evidence. For a
graded Fact or Constraint, an evidence ID is direct iff a positive path reaches
the terminal without an intermediate Fact. Support normalization nodes do not
make a path inherited. An ID is inherited iff a positive path contains at least
one intermediate Fact and no direct path exists for that same ID. The canonical
witness minimizes `repair_overlay` use first, then path length, then full
node-ID and edge-ID paths lexicographically within the applicable class. Grades
compare exact direct, inherited, and total sets, not subsets.

### Completed result

The lossless migration remained `FAIL` with exactly missing final/R4 and
demo/R2. The separately pinned repair added exactly those two reachability
pairs, changed no existing direct/inherited classification, and passed exact
closure grading. Removing either repair edge reopened only its corresponding
gap. The canonical builder and reload validator passed under socket denial with
zero provider calls. This closes the v0.5.3 representation gate only; the four
support roles remain explicit case annotations rather than discovered
semantics.

### Network-zero gates

Before any hosted call, require:

- exact schema, vocabulary, unique-ID, reference, ordinal, and acyclicity
  validation;
- exact legal edge-type grammar and rejection of every forbidden type pair;
- positive closure that excludes invalidated evidence;
- stable direct/inherited partitions and witness paths;
- lossless migration reproduction of the two v0.5.2 lineage gaps;
- a separately identified overlay whose mutation or removal reopens the
  expected gaps;
- exact preservation of the predecessor's `false` endpoint;
- deterministic canonical bytes across identical builds;
- recursive forbidden-key and downstream-grade leakage rejection;
- malformed-reference, cycle, type, provenance, and invalidation mutation
  tests; and
- successful build and validation while network access is denied.

### Stop rule

Do not make a provider call if lossless migration does not reproduce the frozen
defect, if the repair depends on a hidden expected-evidence list, or if the
network-zero artifact is not deterministic and independently reloadable.

A later hosted regression is eligible only under a new live lock. It must not
replace the local migration artifact.

## v0.5.4 — Time: Temporal Adjoint over the Dependency Program

### Question

Once the spatial dependency program is explicit, does an exact temporal
adjoint place bounded intervention on useful earlier operations under matched
actuator geometry, rather than merely reflecting a stronger supplied control
basis?

### Planned mechanism

Compile a frozen v0.5.3 program and evidence order into a smooth public
recurrence

\[
s_t = F_{o_t}(s_{t-1}, e_t, u_t;G),
\]

then compute terminal credit through that recurrence. The compiler, operator
bases, neutral controls, normalization, terminal contract, and event order are
fixture inputs fixed before comparison.

The minimum matched comparison is:

- A — zero control;
- B — static terminal-closure control;
- C — exact temporal-adjoint placement; and
- D — type-, sign-, sparsity-, norm-, and finite-leverage-matched placement
  sham.

Where possible, intervention coordinates are normalized by a preregistered
neutral terminal-Jacobian or fixed-step leverage scale. If equalization is not
achieved, actuator geometry remains an explicit confound and no isolated
temporal-credit claim is permitted.

### Hard gates

- manual adjoint, autograd, and central finite difference agree;
- severing a dependency path gives that upstream path exact zero terminal
  credit;
- an inserted identity operation preserves state and credit;
- independent operations commute under the declared ordering rule;
- no-event input is exact identity with zero backward calls;
- moving a late invalidation changes the preregistered top eligible control
  site on the paired fixture;
- projected controls remain bounded and byte deterministic; and
- C clears a preregistered margin against B and every eligible matched sham.

### Stop rule

If numerical checks fail, repair the mechanism before comparison. If C does not
clear the matched controls, freeze the negative result, do not promote temporal
superiority, and do not open v0.5.5 under this version line. A separately locked
successor may revise the admitted control geometry, but it cannot tune or relabel
the completed v0.5.4 block.

No hosted model is required for the v0.5.4 mechanism result.

## v0.5.5 — Multiplicity: Lane-Composable Public Trajectories

### Question

Can several sealed reasoning trajectories share an evidence ledger and one
terminal contract while preserving lane-local provenance, isolation, and exact
backward credit?

### Minimal scope

Limit the first substrate to at most three prebuilt lanes:

```text
sealed lane A --\
sealed lane B ----> one frozen acyclic merge junction -> terminal contract
sealed lane C --/
```

Each lane is an immutable v0.5.4-compatible artifact with a namespaced node
space. The bundle has one shared evidence ledger, one fixed merge operator, one
terminal contract, a block adjoint, and a per-lane public control map.

The milestone explicitly excludes live provider calls, agent spawning, debate,
dynamic routing, learned arbitration, tool execution, and final answer
generation.

### Hard gates

- a one-lane bundle degenerates exactly to the corresponding v0.5.4 result;
- lane identifier collisions and undeclared cross-lane edges are rejected;
- perturbing one disconnected lane cannot alter another lane's local state or
  control map;
- block-adjoint credit agrees with full autograd and finite differences;
- permuting lanes under a declared commutative merge leaves terminal output and
  lane-keyed credit unchanged;
- source and artifact mutations are detected after reload;
- merge controls and lane controls are separately bounded and receipted; and
- all mechanism artifacts build with network access denied.

### Stop rule

Do not introduce orchestration while single-lane equivalence, lane isolation,
or block-gradient agreement is open. A failed lane-composition gate is a v0.5.5
mechanism result, not justification for a learned arbiter.

## v0.6+ — Execution over the substrate

v0.6 begins only after the v0.5.5 completion audit. Its first design task is to
decide how external models or agents may populate sealed lanes without changing
the substrate's semantics after observing outcomes.

Potential execution questions include:

- adapter contracts for heterogeneous providers;
- pre-outcome lane selection versus post-outcome arbitration;
- blinded lane identities and matched execution budgets;
- one controlled full-context regeneration from the merged public program;
- provider availability, retries, usage, and latency as separate runtime axes;
- final-output and lineage grading that remains independent of local surrogate
  loss; and
- a Reasoning IDE surface for clean passes and hidden-defect detection.

These are design candidates, not v0.5.5 capabilities. The concrete v0.6
protocol is intentionally assembled from the evidence observed after v0.5.3,
v0.5.4, and v0.5.5 complete.

## Deferred axis: novelty

Novelty is not an implicit reward in this roadmap. It requires its own frozen
reference distribution, semantic metric, validity guardrail, reward-hacking
tests, and matched control. It may be studied after dependency, time, and
multiplicity are separable; it must not be used to rescue a failed gate in
v0.5.3-v0.5.5.

## Promotion ledger

| Version | Promotion evidence | What a pass would not prove |
| --- | --- | --- |
| v0.5.3 | deterministic network-zero migration, closure, witness paths, and contaminated repair regression | semantic discovery, provider-output improvement, or general reasoning quality |
| v0.5.4 | exact temporal derivatives plus matched-control result on a frozen public recurrence | hidden-state access, universal controllability, or GPT improvement |
| v0.5.5 | single-lane equivalence, lane isolation, block credit, and deterministic merge | effective multi-agent orchestration or better final answers |
| v0.6+ | separately preregistered hosted execution evidence | claims outside its provider, fixture, and endpoint population |
