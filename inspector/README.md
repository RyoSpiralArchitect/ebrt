# EBRT Apply Revision · recorded and live Reasoning IDE

This interface runs the sealed public Live demo and replays the sealed
`v0.6.2.1` Apply Revision acceptance artifact. Both present one product path:

```text
Before + late event
  -> neutral public trajectory
  -> one time-local public surrogate backward()
  -> revised public trajectory
  -> public control map
  -> compiled provider-visible actuator
  -> GPT-5.6 full-context output
  -> strict verification
```

`Replay recorded Apply Revision` only animates already-recorded public states.
It makes no provider request, does not regenerate output, and does not edit the
sealed artifact. The UI keeps the local surrogate, control map, compiled
actuator, actual provider output, semantic grade, product acceptance, and
effect-attribution boundary visibly separate.

Live mode performs one explicit `Apply Revision → Regenerate`
operation. Each button press first fetches a fresh, server-owned complete
request from `GET /api/demo-request`, then posts that request unchanged to
`POST /api/apply-revision`. The browser does not construct or edit evidence,
prior public state, closure graphs, fingerprints, or provider configuration.
There is no automatic retry. Stopping the browser wait aborts only the browser
request; the server operation may still complete.

The adjacent **Editor** opens a complete Protocol `v0.6.2.4` request document.
It starts blank and loads the known sample only after an explicit user action.
Developers can edit ordered evidence, the emitted Before state, the typed late
event, and supplied closure candidates without a hidden natural-language-to-
graph adapter. The exact document is submitted to the same strict backend
validator; no raw evidence is written to browser storage, and caller semantics
remain `CALLER_SUPPLIED_UNVERIFIED` / `NOT_ASSESSED`.

Before that operation completes, Live mode deliberately withholds the sealed
recorded After output and displays `POLISH → PENDING`. The live After card,
public diff, and verification rows are revealed only from the returned live
response. The center panel keeps the late event, objective change, local
`backward()`, top three public credits, compiled actuator, and gradient
boundary on the primary demo surface; full trajectories, matched controls,
allocation rows, and execution receipts remain available under
**Inspect trajectory receipts**.

Live protocol `v0.6.2.4` exposes Runtime Preview 3's public temporal revision
path. The backend starts from the compiled public Before vector, executes a
chronological neutral trajectory, performs one real local `float64` backward
over eligible time sites, and replays the same public recurrence with bounded
time-local controls. The Inspector shows both neutral and revised trajectories,
the matched temporal sham objective, temporal credit, optimized public
inspection shares, the full-admission support reference used by the
preterminal path objective, deterministic abstract budget units, compiled
program, and executed state trace. The three trajectory coordinates are a
hand-built public surrogate; they are not private model states or a transcript
of private model reasoning. Inspection fields are external review directives—not provider
attention probabilities or token budgets. Provider uptake remains
`NOT_ASSESSED`.

The live parser requires the public trajectory to bind to the actual Before
state, and requires its fingerprint to propagate exactly through the compiled
actuator, inspection plan, revision program, and execution receipt. Neutral,
revised, matched-sham, chronology, locality, stable-axis identity, path-loss,
and gradient-boundary checks are exact hard gates. The recorded `v0.6.2.1`
artifact has no temporal trajectory and remains a supported fallback; its
existing signed-credit view is rendered unchanged and makes no live request.

The Live display retains the whole demo envelope, recomputes its request and
envelope fingerprints, and requires the response input fingerprint, provenance,
source fingerprint, Before state, event, and evidence to bind back to that
envelope. Every JSON response carries `X-EBRT-Body-SHA256`; the browser hashes
the received bytes before parsing, recomputes the live response self-seal from
the number-lexeme-preserving canonical body, and displays the independently
verified transport digest. The parser also requires the exact operational
rows, two exact `NOT_ASSESSED` rows, the trajectory/controller/actuator/execution
hard gates, and their aggregate status
relationships before the UI can render a terminal. These unkeyed hashes are
transport-consistency checks, not signatures. Public worker-to-backend access
is separately authenticated with `EBRT_RELAY_TOKEN`.

The API defaults to same-origin `/api/`. Dev and preview are deliberately fixed
to loopback ports `5173` and `4173`; startup fails instead of silently moving to
an Origin the backend has not allowlisted. A direct loopback API base may be
selected for those exact dev Origins without exposing provider credentials:

```bash
VITE_EBRT_API_BASE_URL=http://127.0.0.1:8765/api/ pnpm dev
```

Provider credentials remain server-side. Live results report operational path
status only. Semantic correctness, provider uptake, hosted counterfactual
effect, and effect attribution remain `NOT_ASSESSED`. The public
block/unblock audit is limited to the selected caller-supplied graph. The
temporal placement comparison is local to the declared public recurrence and
does not establish hosted-model causality, hidden-state editing, attention
control, KV-cache control, quality improvement, or general reasoning
improvement.

## Public Live demo bridge

The public build uses the same-origin `/api/` surface. On POST, a Sites Worker
accepts only the fresh sealed demo request, strips browser credentials, derives
an opaque HMAC client key, and proxies the exact request and response bytes over
HTTPS to the existing loopback Python monolith through a Quick Tunnel. The
monolith performs one real `torch.float64` backward pass and one no-retry
`gpt-5.6-sol` full-context regeneration. The public UI does not expose the
arbitrary-input Editor.

The deployed backend is configured for at most 32 provider attempts globally
and 2 per anonymous client for the lifetime of that process. Request identity
is also idempotent, concurrent provider execution is serialized, and terminal
errors consume the attempt. Recorded mode remains available as a zero-call
fallback. A Quick Tunnel is an ephemeral demo bridge; availability and
production uptime are not promised.

Backend environment names (values stay server-side):

- `OPENAI_API_KEY`
- `EBRT_RELAY_TOKEN`
- `EBRT_RELAY_MAX_PROVIDER_ATTEMPTS_TOTAL`
- `EBRT_RELAY_MAX_PROVIDER_ATTEMPTS_PER_CLIENT`

Sites Worker environment names:

- `EBRT_BACKEND_URL`
- `EBRT_CLIENT_KEY_SECRET`
- `EBRT_RELAY_TOKEN`

Run the bridge and verify the public Worker/build with:

```bash
python3 ebrt_live.py serve --provider openai --host 127.0.0.1 --port 8765
cloudflared tunnel --url http://127.0.0.1:8765

cd inspector
pnpm test:worker
pnpm build:public-live
```

Set `EBRT_BACKEND_URL` to the generated HTTPS tunnel origin. Do not commit any
environment value. `pnpm build:recorded` remains the static, no-API fallback
build.

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
preview mode. `pnpm build:recorded` produces the public zero-call build: it
removes Live and Editor controls, stages only the current sealed projection,
and exposes no provider endpoint. `pnpm build:public-live` stages the public
Live/Recorded UI and the fail-closed same-origin relay Worker; it still omits
the local arbitrary-input Editor.

The desktop layout shows three simultaneous lanes. The public Live build opens
in Live mode but makes no request until Apply is pressed; Recorded mode never
calls `/api/**`. The local build starts in Recorded mode and also exposes the
Editor. Tablet and mobile layouts use an accessible three-step tab surface
with ArrowLeft/ArrowRight navigation. Motion respects
`prefers-reduced-motion`.

## Interpretation boundary

The recorded acceptance and public sealed Live path establish only that Apply
Revision is executable, observable, and structurally verifiable in one known,
contaminated synthetic product case. They do not establish causal control,
provider uptake, hidden-state editing, semantic correctness, quality
improvement, or general reasoning improvement. Effect attribution remains
`NOT_ASSESSED`.
