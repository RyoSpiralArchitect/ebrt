# EBRT Apply Revision · recorded Reasoning IDE

This interface replays the sealed `v0.6.2.1` Apply Revision acceptance
artifact. It presents one public product path:

```text
Before + late event
  -> local public surrogate backward()
  -> public control map
  -> compiled provider-visible actuator
  -> recorded GPT-5.6 full-context output
  -> strict verification
```

`Replay recorded Apply Revision` only animates already-recorded public states.
It makes no provider request, does not regenerate output, and does not edit the
sealed artifact. The UI keeps the local surrogate, control map, compiled
actuator, actual provider output, semantic grade, product acceptance, and
effect-attribution boundary visibly separate.

## Deterministic public projection

The allowlist projector verifies all six manifest-bound result files plus the
manifest itself, pins the exact live-r01 manifest/result/trace publication,
validates their seals, and reproduces the committed browser snapshot
byte-for-byte. Its self-test rejects a coherently resealed replacement result
and manifest. The browser independently hashes the raw snapshot before
rendering. The projection excludes provider bodies, request identifiers,
credentials, and private reasoning text.

From the repository root:

```bash
python3 inspector/build_apply_revision_snapshot_v0_6_2_1.py validate
python3 inspector/build_apply_revision_snapshot_v0_6_2_1.py self-test
```

The browser reads:

```text
inspector/public/data/ebrt-apply-revision-acceptance-v0.6.2.1.json
```

## Run locally

```bash
cd inspector
pnpm install
pnpm build
pnpm dev
```

The desktop layout shows three simultaneous lanes. Tablet and mobile layouts
use an accessible three-step tab surface with ArrowLeft/ArrowRight navigation.
Motion respects `prefers-reduced-motion`.

## Interpretation boundary

The recorded path establishes that Apply Revision was executable, observable,
and strictly verifiable in one contaminated synthetic product-acceptance case.
It does not establish causal control, hidden-state editing, quality
improvement, or general reasoning improvement. Effect attribution remains
`NOT_ASSESSED`.
