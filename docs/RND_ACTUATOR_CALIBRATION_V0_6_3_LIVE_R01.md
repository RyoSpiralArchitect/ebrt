# EBRT v0.6.3-live-r01 — Sealed actuator execution

Status: **PREREGISTERED; NETWORK-ZERO SELF-TEST ONLY; LIVE BLOCK NOT YET RUN**

This namespace executes the 16 provider payloads already sealed by the
v0.6.3 network-zero monolith. It does not modify or replace that monolith, its
zero-call policy, or its canonical preflight artifact.

## Fixed surface

```text
actuator_calibration_v0_6_3.py                 unchanged mechanism
run_actuator_calibration_v0_6_3_live_r01.py    one live runner and validator
policy_lock_actuator_calibration_v0_6_3_live_r01.json
artifacts/actuator_calibration_v0_6_3_live_r01/  created only by run-live
```

The separate live lock anchors tag object
`d569bf5960fea7c72f572a7b204288837a499756`, commit
`97b8d63b32e07664e3f16b5f13df91309fbb40ee`, the exact committed preflight
manifest bytes, all imported source bytes, runtime versions, prompt/schema
fingerprints, payload hashes, call order, thresholds, and terminal states.

## Execution contract

All 16 payloads are rederived and checked against the committed projection
before provider construction. The fixed Williams order is:

```text
relay / trial 1:   Z C X D
coolant / trial 1: C D Z X
relay / trial 2:   D X C Z
coolant / trial 2: X Z D C
```

The irreversible command additionally requires the annotated tag
`v0.6.3-live-r01-authorized` to point at its exact checked-out commit, requires
that commit to be reachable from local `origin/main`, and rejects dirty or
untracked locked execution sources. Each
attempt then uses a fresh `gpt-5.6-sol` Responses client with low reasoning,
2048 maximum output tokens, a 60 second timeout, no stored conversation, and
SDK retries set to zero. The provider receives only its sealed payload. It
never receives the treatment ID, blinded request ID, `q^D`, `q^X`, path label,
gold, or grade.

Before every irreversible call, the runner appends and `fsync`s an
`ATTEMPT_STARTED` journal row. The staging directory, plan, empty journal,
journal rows, and directory entries are synchronized before the first call. It
appends a terminal row after the receipt and local contract boundary. A process
or filesystem crash after the synchronized namespace is created leaves the
`.inflight` namespace as the burn marker; the runner refuses resume, retry,
backfill, or reuse of that output path.

The structured provider output is parsed as
`ActuatorCalibrationOutput`, then the unchanged monolith:

1. validates the checkpoint, answer vocabulary, slot set, inspection receipt,
   and candidate-edge IDs;
2. derives the selected graph locally;
3. requires one exact valid closure, one exact invalidation, stable-support
   preservation, acyclicity, minimality, and no irrelevant edge; and
4. computes alignment from the graph-derived closure without reading the
   inspection receipt.

The locked runner guards its semantic-gold `Path.read_bytes` loader during
projection, preflight, provider execution, and partial failure handling. Its
locked bytes are first verified and parsed only after all 16 outputs have passed
the public compiler. This is a locked-code regression guard, not an
operating-system sandbox against arbitrary processes. Its
answer/lineage grades remain secondary and do not gate actuator promotion.
The preflight records the gold receipt as expected, not observed; a separate
observed receipt is emitted by post-compilation grading. Each grading or
independent validation pass reads and parses the same locked bytes once, and no
such pass occurs before complete public compilation.

## Frozen endpoints

With `epsilon = 1e-12`, each complete four-arm block records:

```text
delta_XZ = alignment(X, q^X) - alignment(Z, q^X)
delta_DC = alignment(D, q^D) - alignment(C, q^D)
```

- X/Z channel adherence requires all four X and all four Z receipts to match
  their schedules.
- X propagation requires positive aggregate `delta_XZ` and at least three of
  four positive blocks.
- D/C adherence requires all four D and all four C receipts to match their
  schedules.
- Gradient placement requires D/C adherence, positive aggregate `delta_DC`,
  and at least three of four positive blocks.

The public inspection receipt and raw byte inequality never count as
downstream propagation.

## Terminal states

```text
INCOMPLETE_NOT_ASSESSED
STOP_OUTPUT_CONTRACT
STOP_CHANNEL_ADHERENCE_NULL
STOP_ACTUATOR_ECHO_ONLY
STOP_GRADIENT_PLACEMENT_NULL
PROMOTE_V0_6_4_ACTUATOR_GATE
```

A provider, receipt, or structured-parser failure stops the sequence and makes
effects not assessed. A schema-valid provider output rejected by the local
graph compiler stops as `STOP_OUTPUT_CONTRACT`. D/C nonadherence and a null
D/C directional result share the frozen terminal status but retain different
reason codes.

Preflight failure raises before the live namespace is created and therefore is
not represented as a post-call terminal result.

## Commands

Network-zero checks:

```bash
python3 run_actuator_calibration_v0_6_3_live_r01.py component-self-test
python3 run_actuator_calibration_v0_6_3_live_r01.py emit-lock
```

Zero-call launch check; this requires the API key only to prove the exact live
provider can be constructed. Before the authorization tag exists it returns a
contract-only pending status; at the tagged execution commit it must return
`READY_EXACT_16_CALL_LIVE_BLOCK`:

```bash
python3 run_actuator_calibration_v0_6_3_live_r01.py preflight
```

The following command is irreversible and consumes up to 16 provider calls:

```bash
python3 run_actuator_calibration_v0_6_3_live_r01.py run-live
```

After execution, validate the canonical artifact without another provider call:

```bash
python3 run_actuator_calibration_v0_6_3_live_r01.py validate
```

## Claim boundary

This is one sealed two-case, two-trial feasibility calibration. D is generated
and evaluated in the same `q^D` coordinate system. A positive result supports
only the claim that this bounded public actuator was observably consumed and
that its gradient placement differed directionally from the matched
anti-placement in this block. It does not establish hidden-state editing,
causal superiority, quality improvement, population reliability, or general
reasoning improvement. The authorization tag, attempt journal, response/body
hashes, and—once published—the separate post-run artifact commit form an
operator-auditable provenance chain. The runner itself records the tagged
execution commit; it does not create the later artifact commit. The provider
does not sign these receipts, so the artifact alone is neither
cryptographically authenticated nor proof that hosted execution occurred. The
tag also does not authenticate operator identity or guarantee global
exactly-once execution across separate clones.
