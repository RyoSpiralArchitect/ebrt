# EBRT v0.6.3.1 live-r01

- Attempt block: `COMPLETE_EXACT_FOUR_TERMINALS`
- Assessment: `ASSESSED`
- Terminal decision: `PROMOTE_TO_FRESH_REPLICATION`
- Calls: `4/4`
- Gold loaded: `true`

## Public outputs

| Position | Arm | Status | Closure |
|---:|---|---|---|
| 1 | C | COMPLETED | K_5c1377f2fc |
| 2 | X | COMPLETED | K_ba42ee466f |
| 3 | D | COMPLETED | K_ba42ee466f |
| 4 | Z | COMPLETED | K_f41cb3914f |

## Boundary

- This is one sealed four-call actuator-uptake canary, not a population estimate or quality benchmark.
- The sole intentionally treatment-varying semantic payload field is evidence order.
- The provider never sees C/X/D/Z, treatment metadata, gradient values, controller internals, closure roles, gold, or grades.
- The local float64 backward pass ends before JSON; no gradient crosses GPT or the provider boundary.
- Known stale or mixed closures are valid semantic endpoints; only transport, parse, schema, and unknown-ID failures are structural invalidity.
- A positive canary opens only a separately sealed fresh replication; it never directly promotes v0.6.4.
- The fixed serial C-to-X-to-D-to-Z block cannot separate treatment order from temporal or provider drift.
- Provider receipts and execution provenance are operator-attested local records, not provider-signed proof.
- The authorization tag prevents accidental execution from an unreviewed checkout but does not provide global exactly-once semantics across clones.
- The semantic-gold barrier is a locked Path.read_bytes guard, not an operating-system sandbox.
- No result supports hidden-state editing, causal superiority, quality improvement, or general reasoning improvement.
