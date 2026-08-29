# EBRT v0.8.3 Role-Stratified Provider-Uptake Canary

Status: **COMPLETE DEVELOPMENT CANARY; MIXED RESULT; NOT A BENCHMARK**

Canonical integrity-bound artifact:
[`artifacts/role_stratified_uptake_v0_8_3/r03_snapshot_bound/results.json`](../artifacts/role_stratified_uptake_v0_8_3/r03_snapshot_bound/results.json)

Preserved source-bound artifact:
[`artifacts/role_stratified_uptake_v0_8_3/r02_integrity/results.json`](../artifacts/role_stratified_uptake_v0_8_3/r02_integrity/results.json)

Preserved original artifact:
[`artifacts/role_stratified_uptake_v0_8_3/r01/results.json`](../artifacts/role_stratified_uptake_v0_8_3/r01/results.json)

Pre-call lock:
[`policy_lock_role_stratified_uptake_v0_8_3.json`](../policy_lock_role_stratified_uptake_v0_8_3.json)

Integrity-replication lock:
[`policy_lock_role_stratified_uptake_v0_8_3_1_r02.json`](../policy_lock_role_stratified_uptake_v0_8_3_1_r02.json)

Exact-snapshot lock:
[`policy_lock_role_stratified_uptake_v0_8_3_2_r03.json`](../policy_lock_role_stratified_uptake_v0_8_3_2_r03.json)

## Question

The v0.8.2 corpus exposed two different failures:

```text
backward credit
  -> scalar top-k compiler       # may drop a required public role
  -> model-visible request
  -> generated support lineage  # may omit a compiled obligation
```

This canary asks whether a minimal public-role coverage floor repairs the first
boundary, and whether that repair reaches the second boundary in one real local
generator.

It does not ask whether role-stratified EBRT is generally better. The arms have
different provider-visible requests, the public roles are caller-supplied, and
there are only three development cases over one model snapshot.

## Locked geometry

- Source main commit: `2961feb6aaa2222bb56a62cb04274587487f4a17`.
- Original lock commit before r01 calls: `8a04d04`.
- Strengthened lock commit before r02 calls: `c6e6ee7`.
- Exact snapshot-manifest lock commit before r03 calls: `34f7807`.
- Model: `mlx-community/Mistral-7B-Instruct-v0.3-4bit@a4b8f...`.
- Three fresh synthetic late-event cases.
- Three arms and one generation per arm:
  - `direct_full_context`;
  - `ebrt_top_k`;
  - `ebrt_role_stratified`.
- Each arm occupies each serial position exactly once.
- `temperature=0`, `seed=0`, 48 generated-token ceiling.
- No automatic retry and no native-state capture.
- Semantic contracts remain post-call-only.

Codex review found two attribution gaps after r01: an arbitrary external model
directory could carry the explicit locked ID, and the pre-call lock hashed the
canary runner without hashing the imported core/corpus implementation. The r01
artifact remains immutable. r02 requires the exact content-address-verified
Hugging Face cache snapshot and binds SHA-256 hashes for the wrapper plus every
repository-local implementation file on the execution path.

r02 repeats already observed cases and therefore is not fresh replication
evidence. Its nine public outputs are byte-identical to r01 (`9/9`); it only
strengthens execution attribution.

A second review found that a cache directory could retain the expected path
and revision name while pointing at a different internally consistent blob
set. r03 therefore locks all seven expected snapshot-relative files by path,
byte size, and blob address. Git-blob SHA-1 and SHA-256 addresses are each
verified against file content immediately before and after the calls. r03 is
also a contaminated integrity repetition, not new evidence. All public outputs
remain byte-identical across r01/r02/r03 (`9/9`).

The candidate reserves capacity for the correction plus every public evidence
node whose caller-supplied role is `required_support`, then fills remaining
capacity by absolute backward-credit magnitude. The total allocation remains
100 units and uses the same signed controls, suppression, preservation, and one
full-context regeneration boundary as scalar top-k.

## Result

| Measurement | Scalar top-k | Role-stratified |
| :--- | ---: | ---: |
| Compiler coverage | 1/3 | 3/3 |
| Provider uptake | 2/3 | 2/3 |
| Strict semantic pass | 2/3 | 2/3 |

The direct arm also passed `2/3` strict semantic contracts.

Across top-k versus role-stratified outputs:

- raw output changed in `2/3` cases;
- support lineage changed in `2/3` cases; and
- the final answer changed in `1/3` cases.

The deterministic compiler repair succeeded exactly where intended. It did not
produce an aggregate provider-uptake or strict-semantic gain.

## Case atlas

### Parcel dock policy

The scalar compiler selected `R6,R4,R1`, dropping required identity evidence
`R2`. The role compiler selected `R6,R4,R2`.

```diff
 ANSWER=DOCK_A
-SUPPORT=R6,R4,R1,R2,R5
+SUPPORT=R6,R4,R2
```

Both controlled outputs passed. Even though scalar top-k did not compile `R2`,
the generator recovered it from full raw context. The role candidate removed
the irrelevant context citation and preserve-only leakage in this one case.

### Scaled reading schema

The scalar compiler selected `R6,R1,R2`, dropping required rule evidence `R4`.
The role compiler selected `R6,R2,R4`.

```diff
-ANSWER=60_UNITS
-SUPPORT=R1,R2,R4,R5
+ANSWER=6_UNITS
+SUPPORT=R2,R4,R5
```

This is the only answer-level difference. Direct and scalar top-k emitted the
old value `60_UNITS`; the candidate emitted the expected `6_UNITS`. However,
both controlled outputs omitted compiled correction evidence `R6`. The
candidate therefore failed provider uptake and the strict semantic contract.
This is an observed fresh-case difference, not evidence that role placement
caused the improvement.

### Grant eligibility policy

Both compilers selected `R6,R4,R2`. Their provider-visible prompts were
byte-identical and Mistral emitted the same output in both serial positions:

```text
ANSWER=ELIGIBLE
SUPPORT=R6,R4,R2
```

This is the canary's no-op/invariance control.

## Interpretation

The result localizes the remaining bottleneck.

1. **Coverage loss is repaired at compile time.** The role floor prevents a
   high-credit context node from displacing a required public role.
2. **Full raw context can compensate for compiler omissions.** In the parcel
   case, top-k omitted `R2` but the generator cited it anyway.
3. **Complete compilation does not guarantee uptake.** In the numeric case,
   both controlled arms omitted `R6` despite explicit compilation and prompt
   language requiring the late correction.
4. **Answer and lineage remain different axes.** The role candidate produced
   the expected numeric answer while still failing correction provenance.

The next bounded iteration should not increase gradient magnitude. It should
test a smaller typed output channel that separates decision support from
revision provenance, for example:

```text
ANSWER=6_UNITS
SUPPORT=R2,R4
REVISION_EVENT=R6
```

That would test whether the provider can retain compiled obligations when the
schema gives correction provenance its own slot. It remains a provider-channel
experiment, not a hidden-state or general reasoning claim.

## Claim boundary

- Public `required_support` roles are supplied by the synthetic task author.
- The local backward pass is real, but the generator lies beyond a
  stop-gradient boundary.
- Arms differ in evidence order, actuator payload, and prompt text.
- One fresh answer difference does not establish a causal effect.
- `PASS` for compiler coverage, provider uptake, or semantic correctness does
  not imply either of the other two.
- No cross-model conclusion is admitted.
