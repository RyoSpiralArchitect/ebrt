# EBRT Inspector (provisional)

This is a local, read-only viewer for recorded public benchmark artifacts. It
is intentionally a temporary research surface: it does not define the final
frontend architecture, edit model state, expose private chain-of-thought, or
provide a hosted evaluation service.

The viewer compares execution protocols over one recorded model. It renders
the raw evidence recorded in the artifact, emitted public-card support,
declared invalidations, final-card grading, and provider-reported usage.
Declared support is not proof that uncited evidence had no semantic influence.
Detailed-grade availability is separate from endpoint adjudication. An
unassessed endpoint is rendered as `NOT ASSESSED`; a v0.4.2 terminal local
contract rejection is rendered as endpoint `FAIL` even though no accepted final
card exists. The header keeps accepted-output completion, endpoint assessment,
manifest execution status, and cause-decision readiness separate. For failed
v0.4.2 endpoints it also projects the recorded failure position and the safe
provider/SDK exception class when available; it never exposes an exception
message or rejected card.

`Overview` provides a recorded Replay-to-Output comparison using the final
public Reasoning Cards already stored in the artifact. Its playback control
only reveals recorded reference/candidate outputs and their public diff: it
does not invoke a model, regenerate an answer, mutate the source bundle, or
turn the Inspector into an editor. `Inspect` retains the detailed timeline,
lineage, and usage view.

The revision envelope shown above the evidence order is a fixture annotation.
Its actual provider delivery is shown separately for each arm; the no-envelope
control remains `null`. These are post-event reconstruction records, not an
online event-detection trace.

## Build the normalized snapshot

From the repository root:

```bash
python3 build_inspector_snapshot_v0_4_1.py build \
  --bundle artifacts/benchmark_aperture_controls_v0_4_2_dev \
  --output inspector/public/data/ebrt-public-inspector-v0.1.json
```

The exporter remains backward-compatible with the frozen v0.4.1 four-arm
artifact and the locked two-arm calibration artifact:

```bash
python3 build_inspector_snapshot_v0_4_1.py build \
  --bundle artifacts/benchmark_aperture_controls_v0_4_1_dev \
  --output inspector/public/data/ebrt-public-inspector-v0.1.json
python3 build_inspector_snapshot_v0_4_1.py build \
  --bundle artifacts/benchmark_direct_full_calibration_v0_4_dev \
  --output inspector/public/data/ebrt-public-inspector-v0.1.json
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

The committed snapshot is recorded contaminated DEV evidence. Do not use this
surface to claim general reasoning improvement, Selective replay parity,
multi-model portability, or a causal aperture diagnosis unless the matching
control artifact supports that narrower statement.
