# EBRT Apply Revision · recorded and live Reasoning IDE

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

The optional Live mode performs one explicit `Apply Revision → Regenerate`
operation. Each button press first fetches a fresh, server-owned complete
request from `GET /api/demo-request`, then posts that request unchanged to
`POST /api/apply-revision`. The browser does not construct or edit evidence,
prior public state, closure graphs, fingerprints, or provider configuration.
There is no automatic retry. Stopping the browser wait aborts only the browser
request; the server operation may still complete.

The Live display retains the whole demo envelope, recomputes its request and
envelope fingerprints, and requires the response input fingerprint, provenance,
source fingerprint, Before state, event, and evidence to bind back to that
envelope. Every JSON response carries `X-EBRT-Body-SHA256`; the browser hashes
the received bytes before parsing and displays that verified body digest rather
than presenting an unchecked server seal. The parser also requires the exact 12
operational rows, two exact `NOT_ASSESSED` rows, and their aggregate status
relationships before the UI can render a terminal. These unkeyed hashes are
loopback integrity checks, not signatures or remote-backend authentication.

The API defaults to same-origin `/api/`. Dev and preview are deliberately fixed
to loopback ports `5173` and `4173`; startup fails instead of silently moving to
an Origin the backend has not allowlisted. A direct loopback API base may be
selected for those exact dev Origins without exposing provider credentials:

```bash
VITE_EBRT_API_BASE_URL=http://127.0.0.1:8765/api/ pnpm dev
```

Provider credentials remain server-side. Live results report operational path
status only. Semantic correctness and effect attribution remain
`NOT_ASSESSED`.

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

Start the loopback backend from the repository root (use `openai` for the real
provider or `scripted` for network-zero UI work):

```bash
python3 -m pip install -r requirements-product.txt
python3 ebrt_live.py serve --provider scripted --host 127.0.0.1 --port 8765
```

Then start the Inspector in a second terminal:

```bash
cd inspector
pnpm install
pnpm build
pnpm dev
```

Vite proxies same-origin `/api/**` requests to `127.0.0.1:8765` in both dev and
preview mode. A deployed build should provide the same reverse-proxy contract;
arbitrary cross-origin deployment is outside the loopback server contract.

The desktop layout shows three simultaneous lanes. Recorded is always the
initial mode and performs no `/api/**` request. Tablet and mobile layouts
use an accessible three-step tab surface with ArrowLeft/ArrowRight navigation.
Motion respects `prefers-reduced-motion`.

## Interpretation boundary

The recorded path establishes that Apply Revision was executable, observable,
and strictly verifiable in one contaminated synthetic product-acceptance case.
It does not establish causal control, hidden-state editing, quality
improvement, or general reasoning improvement. Effect attribution remains
`NOT_ASSESSED`.
