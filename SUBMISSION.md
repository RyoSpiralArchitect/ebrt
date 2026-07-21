# EBRT — Build Week submission

## Title

**EBRT — Apply Revision for Hosted Reasoning**

## Tagline

**An external differentiable revision layer developers can inspect, apply, and
verify.**

## Track

**Developer Tools**

## Devpost description (140 words)

Hosted language models do not expose editable reasoning states, so EBRT adds
an external differentiable revision layer that developers can inspect and
verify. A typed late event is applied to an already-emitted public state. EBRT
rolls a three-axis public trajectory forward, computes one real local float64
backward pass, projects bounded time-local controls, replays the trajectory,
and compiles an executable Reinspect / Suppress / Preserve operation. GPT-5.6
then performs one structured full-context regeneration, while the Reasoning IDE
displays the Before/After diff, evidence lineage, stable facts, operational
checks, and gradient boundary. The scripted mode runs without network access;
the public sealed-case demo relays to OpenAI mode while keeping credentials
server-side. EBRT does not edit model hidden
states, attention, KV cache, or private chain-of-thought, and it does not claim
causal superiority or general reasoning improvement. It makes revision
operations executable, observable, and auditable.

## Judge links

- Public repository: `https://github.com/RyoSpiralArchitect/ebrt`
- Public runnable demo: `TODO_PUBLIC_DEMO_URL`
- Public YouTube video: `TODO_PUBLIC_YOUTUBE_URL`
- Codex feedback/session ID: `019f70e8-b94c-7002-bc14-512338e2c5fd`
- Devpost project: `TODO_DEVPOST_PROJECT_URL`

These placeholders must be replaced before submission. Do not replace the
local runtime wording with a hosted-service claim unless a public deployment
has actually been validated.

## Features

- A chronological, three-axis public reasoning trajectory over typed evidence.
- One real local `torch.float64` reverse-mode pass with finite-difference,
  projection, locality, replay, and tamper-rejection checks.
- Bounded time-local controls compiled into an executable
  `Reinspect / Suppress / Preserve` revision program.
- At most one no-retry GPT-5.6 full-context After attempt per fresh request
  identity in OpenAI mode.
- A Reasoning IDE showing Before, late event, temporal credit, compiled
  actuator, After diff, evidence lineage, preserved facts, and verification.
- A network-zero scripted path for judges and a loopback API that keeps
  provider credentials server-side.
- A local Protocol Editor for arbitrary complete public-state requests, with no
  hidden semantic adapter and the same fail-closed runtime validator.
- A public Live/Recorded IDE whose same-origin Worker accepts only the sealed
  demo request and relays it through an authenticated HTTPS Quick Tunnel.
- Process-lifetime public budgets of 32 provider attempts globally and 2 per
  anonymous client, plus idempotency and no automatic retry.
- A recorded zero-call replay fallback that remains usable without the Live
  bridge.
- Recorded artifacts, fingerprints, matched temporal sham diagnostics, and an
  explicit `NOT_ASSESSED` boundary for semantic quality and causal effect.

## Supported platforms

- Backend: CPython 3.11+, PyTorch 2.x, CPU execution.
- Recorded and final development environment: macOS arm64.
- Intended local deployment: POSIX macOS and Linux; cross-platform byte
  identity is not claimed.
- Inspector: Node.js `^20.19.0` or `>=22.12.0`, pnpm, and a modern browser.
- Responsive Inspector layouts are provided for desktop, tablet, and mobile.
- Windows, multi-process idempotency, production hosting, and uptime are not
  validated in Runtime Preview 3. The public Quick Tunnel is a temporary demo
  bridge to the loopback monolith.

## GPT-5.6 and Codex usage

### GPT-5.6

The runtime pins `gpt-5.6-sol` at one non-differentiable structured-generation
boundary. After EBRT has computed and compiled the public revision operation,
GPT-5.6 receives the full raw context plus that public operation and selects
one opaque candidate closure while generating the After public state. The API
key remains in the backend environment. GPT-5.6 is not trained,
differentiated, treated as the public trajectory, or given semantic gold.

### Codex

Codex collaborated on architecture translation, implementation, matched
controls, adversarial contract tests, artifact validation, pull-request review
repairs, documentation, and the Reasoning IDE. Human decisions fixed the
research questions, acceptance boundaries, live-call authorization, and public
claims. Codex is not a runtime dependency, semantic grader, or source of the
sealed provider result.

## 2:45 video script

| Time | Shot | English voiceover |
| --- | --- | --- |
| 0:00–0:20 | Title, then the stale Before card (`POLISH`). | “Hosted models can regenerate text, but they do not expose an editable reasoning state. When late evidence invalidates an earlier premise, developers need a revision operation they can inspect—not another invisible retry.” |
| 0:20–0:42 | Show R1–R5, then introduce late event R6 superseding R3. | “This answer was valid under its original evidence horizon. R6 changes the judging rule and invalidates R3, so the emitted public state is now stale.” |
| 0:42–1:08 | Center the neutral trajectory, loss, and `backward()` animation. | “EBRT rolls a typed public trajectory forward, evaluates a public surrogate loss, and executes one real local float64 backward pass. Credit is assigned only to eligible public time sites.” |
| 1:08–1:30 | Show bounded controls and compiled `Reinspect / Suppress / Preserve`. Keep the gradient-boundary notice visible. | “The update is projected, replayed through the same recurrence, and compiled into a bounded revision program: reinspect R6, suppress invalidated R3, and preserve stable R5. The gradient stops at this public control map; GPT-5.6 is not backpropagated through.” |
| 1:30–1:58 | Click **Apply Revision → Regenerate** in Live mode; show the one provider attempt. | “Now I apply that revision. GPT-5.6 receives the full context and the compiled public operation, then performs one structured regeneration. Provider credentials remain server-side, and the runtime does not retry.” |
| 1:58–2:20 | Reveal `POLISH → PROVE`, lineage checks, invalidation, and stable-fact preservation. | “The public output changes from POLISH to PROVE. The IDE separately verifies the diff, removes R3 from active support, binds the late correction into the selected lineage, and confirms that the three-minute constraint stayed unchanged.” |
| 2:20–2:35 | Briefly show self-tests, receipts, and repository history. | “Codex helped turn the initial research sketch into this monolith, build adversarial tests, validate artifacts, repair review findings, and create the Reasoning IDE. The repository keeps each negative and null result instead of rewriting the evidence.” |
| 2:35–2:45 | Closing product diagram and repository/demo links. | “EBRT does not claim to read hidden thoughts. It gives developers an external revision layer they can execute, observe, and verify.” |

## Exact claim boundary

Supported claim:

> EBRT computes backward credit over an external public reasoning trajectory,
> compiles a bounded revision operation, carries it through one full-context
> hosted regeneration, and verifies the resulting public output and lineage.

Not claimed:

- editing of GPT hidden states, attention, KV cache, or private chain-of-thought;
- gradients through GPT-5.6, the provider, JSON, output parsing, or grading;
- that inspection units are provider tokens or attention probabilities;
- autonomous discovery of semantic truth or a correct dependency graph;
- provider uptake, counterfactual necessity, causal superiority, semantic
  correctness, accuracy improvement, or general reasoning improvement;
- a fresh benchmark, population estimate, production-service readiness, or
  uptime guarantee.

The built-in scripted and live demo case is a known, contaminated product
fixture. Operational `PASS` means that the declared public revision operation
completed and satisfied its structural contract. Both
`semantic_correctness_status` and `effect_attribution_status` remain
`NOT_ASSESSED`.

## Final submission checklist

- [x] Developer Tools track selected.
- [x] Apache License 2.0 included.
- [x] Current product and 30-second network-zero path placed at the top of the
  README.
- [x] Local scripted backend and Reasoning IDE paths documented.
- [x] Public Live/Recorded bridge, sealed-request restriction, provider
  budgets, and Quick Tunnel limitation documented.
- [x] GPT-5.6 and Codex roles documented without crossing the claim boundary.
- [ ] Replace every `TODO_...` judge-link placeholder above.
- [ ] Confirm the GitHub repository is public and the default branch contains
  the final submission commit.
- [ ] Run the scripted judge path from a fresh clone.
- [ ] Run the full Inspector path and verify the final UI at desktop and mobile
  widths.
- [ ] Record an English narrated video no longer than three minutes.
- [ ] Confirm the YouTube video and runnable demo are public without sign-in.
- [ ] Add the required Codex feedback/session ID to Devpost.
- [ ] Paste the description, track, links, and supported-platform statement
  into Devpost.
- [ ] Audit the final video, Devpost copy, README, and UI against the exact
  claim boundary above.
- [ ] Submit once with time remaining, then verify every public link from a
  signed-out browser session.
