# EBRT Inspector (provisional)

This is a local, read-only viewer for recorded public benchmark artifacts. It
is intentionally a temporary research surface: it does not define the final
frontend architecture, edit model state, expose private chain-of-thought, or
provide a hosted evaluation service.

The viewer compares execution protocols over one recorded model. It renders
the raw evidence recorded in the artifact, emitted public-card support,
declared invalidations, final-card grading, and provider-reported usage.
Declared support is not proof that uncited evidence had no semantic influence.
An unavailable grade is rendered as `NOT ASSESSED`, never as `FAIL`, and the
header keeps cause-decision readiness separate from execution progress.

The revision envelope shown above the evidence order is a fixture annotation.
Its actual provider delivery is shown separately for each arm; the no-envelope
control remains `null`. These are post-event reconstruction records, not an
online event-detection trace.

## Build the normalized snapshot

From the repository root:

```bash
python3 build_inspector_snapshot_v0_4_1.py build \
  --bundle artifacts/benchmark_aperture_controls_v0_4_1_dev \
  --output inspector/public/data/ebrt-public-inspector-v0.1.json
```

The exporter can also read the locked two-arm PR #6 artifact while the new
four-arm control bundle is not yet present:

```bash
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
