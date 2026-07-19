# EBRT Reasoning Workbench (provisional)

This local, read-only workbench projects one immutable recorded revision
episode and one separate provider-boundary diagnostic. It is a replaceable
product experiment, not a commitment to the final frontend architecture,
navigation, brand, or hosting model.

The default episode is selected mechanically from the frozen v0.4 live-smoke
artifact: `manifest.case_ids[0]`, trial `0`, uniquely matching
`route_code_supersession`. The page shows the complete public flow:

```text
Evidence -> GPT public observer -> declared revision plan
         -> every recorded replay lane -> final public-card diff
```

All three replay attempts remain visible. Card-only and Selective both retain
their recorded strict failures; Full restart retains its recorded strict pass.
The Initial row is labelled `PRE-EVENT`, not retroactively graded as a
post-event pass or failure. `Play recorded revision` only reveals already
stored public cards. It never invokes a model, edits an artifact, regenerates
an answer, or applies a live revision.

The Provider Failure Atlas is a different recorded runtime-health episode. It
shows eight client attempts reaching HTTP 429 and zero structured parses,
accepted outputs, or reasoning assessments. Its `8/8` native classification is
diagnostic coverage, not a reasoning result. The frozen r01 comparison remains
`0/31`, the cross-block effect remains `null`, the v0.4.3 full block was not
launched, and the reasoning-decision gate remains closed.

## Build and verify the public projection

From the repository root:

```bash
python3 build_reasoning_workbench_snapshot_v0_4_4.py self-test
python3 build_reasoning_workbench_snapshot_v0_4_4.py validate
```

The builder verifies pinned source manifests and hashes, unique fixture
selection, observer/event/plan fingerprints, all replay cards and grades,
public-card-derived diffs, v0.4.3 coverage lineage, privacy allowlists,
deterministic regeneration, and canonical/public byte identity. Its self-test
makes no network call.

The normalized public artifact is committed at:

```text
public/data/ebrt-reasoning-workbench-v0.4.4.json
```

## Run locally

```bash
cd inspector
pnpm install
pnpm dev
```

Production build:

```bash
pnpm build
```

## Interpretation boundary

The workbench exposes fixed fixture evidence, emitted public Reasoning Cards,
a typed public observer event, declared revision metadata, machine grades, and
sanitized usage/diagnostic aggregates. It does not expose private
chain-of-thought, attention, hidden state, raw provider bodies, credentials, or
model-weight changes. `reasoning_tokens` is a provider usage count, not
reasoning text or reasoning quality.

The displayed episode proves that the recorded public pipeline can be audited
through final output. It does not establish general reasoning improvement,
Selective replay parity, a causal aperture effect, current provider health, or
promotion readiness. See
[`docs/RND_REASONING_WORKBENCH_V0_4_4.md`](../docs/RND_REASONING_WORKBENCH_V0_4_4.md)
for the projection protocol and full claim boundary.
