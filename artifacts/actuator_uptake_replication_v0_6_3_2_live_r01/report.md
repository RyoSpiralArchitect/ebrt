# EBRT v0.6.3.2 live-r01

- Attempt block: `COMPLETE_EXACT_EIGHT_TERMINALS`
- Assessment: `ASSESSED`
- Terminal decision: `STOP_REPLICATION_CEILING_NOT_ASSESSED`
- Calls: `8/8`
- Gold loaded: `true`

## Public outputs

| Position | Block | Arm | Attempt | Status | Closure |
|---:|---|---|---|---|---|
| 1 | A | C | A_39276f79d4d0b99f | COMPLETED | K_8027291974 |
| 2 | A | Z | A_21009567d2b053a7 | COMPLETED | K_265e97f857 |
| 3 | A | D | A_2e4f7eee0d24f793 | COMPLETED | K_265e97f857 |
| 4 | A | X | A_a6b410a44c449443 | COMPLETED | K_265e97f857 |
| 5 | B | D | A_4c5f5a302b77395a | COMPLETED | K_265e97f857 |
| 6 | B | X | A_8c46e16cbc877b13 | COMPLETED | K_265e97f857 |
| 7 | B | C | A_256e156a33fa6895 | COMPLETED | K_8027291974 |
| 8 | B | Z | A_fbb3e5ecef6097ca | COMPLETED | K_265e97f857 |

## Boundary

- This is one sealed mirrored eight-call replication on a synthetic case fresh relative to the frozen v0.6.3.1 predecessor, not an independently sampled population case or quality benchmark.
- The sole intentionally treatment-varying semantic payload field is evidence order.
- The provider never sees C/X/D/Z, treatment metadata, gradient values, controller internals, closure roles, gold, or grades.
- The local float64 backward pass ends before JSON; no gradient crosses GPT or the provider boundary.
- Known stale or mixed closures are valid semantic endpoints; only transport, parse, schema, and unknown-ID failures are structural invalidity.
- Only two directional blocks may open a separately reviewed v0.6.4 network-zero preflight; no v0.6.4 live call is authorized.
- Pairwise position counterbalancing narrows but does not eliminate temporal or provider drift.
- Provider receipts and execution provenance are operator-attested local records, not provider-signed proof.
- The authorization tag prevents accidental execution from an unreviewed checkout but does not provide global exactly-once semantics across clones.
- The semantic-gold barrier is a locked Path.read_bytes guard, not an operating-system sandbox.
- No result supports hidden-state editing, causal superiority, quality improvement, or general reasoning improvement.
