# v0.9.1: Delayed terminal credit versus immediate local feedback

Status: **NETWORK-ZERO PRECHECK PASS; FIRST HOSTED BLOCK CLOSED — [RESULTS](RND_DELAYED_TERMINAL_CREDIT_V0_9_1_RUN.md)**

This is a separately scoped, non-production research canary following the model-agnostic EBRT core and the PUCT/multistart comparison. It does **not** edit the frozen v0.1–v0.8 artifacts or claim improvement in the current mainline EBRT engine.

## Question

Can a later change in the terminal contract identify upstream sites that are invisible to an immediate local consistency loss? Can the resulting externally allocated reinspection weights change an API generator's *observable answer and source-lineage behavior*, compared with the same weight multiset assigned to permuted sites?

These are **two different gates**:

1. **Mechanism gate (network zero):** demonstrate a mathematically exact nonlocal credit gradient over explicit public dynamics, with finite differences and an independent integer oracle.
2. **Hosted uptake gate (up to nine API calls):** measure whether the placement of these weights affects exact answer and required-support reporting. This is descriptive and cannot isolate a general gradient-specific quality effect.

## Fixed public dynamics

Each synthetic case supplies three initial public register receipts $x\in\mathbb Z^3$, two visible integer transition matrices $A,B$, a prior output selector $c_{\mathrm{old}}$, and a late selector replacement $c_{\mathrm{new}}$ with offset $b$.

For time-local upstream controls $u$,

$$
h_1=A(x+u),\qquad h_2=Bh_1,\qquad
y_{\mathrm{new}}(u)=c_{\mathrm{new}}^\top h_2+b.
$$

The already-emitted public value is $y_{\mathrm{old}}=c_{\mathrm{old}}^\top BAx$. Define the pre-event local consistency objective and the revised terminal objective separately:

$$
L_{\mathrm{local}}(u)=\tfrac12\|A(x+u)-Ax\|_2^2,\qquad
J_{\mathrm{late}}(u)=\tfrac12(y_{\mathrm{new}}(u)-y_{\mathrm{old}})^2.
$$

At $u=0$,

$$
\nabla_u L_{\mathrm{local}}(0)=0,\qquad
\nabla_u J_{\mathrm{late}}(0)
=(y_{\mathrm{new}}(0)-y_{\mathrm{old}})
A^\top B^\top c_{\mathrm{new}}.
$$

The terminal adjoint can be nonzero at an upstream control despite a zero immediate local gradient. This is a property of the fully specified **external linear surrogate**, not an empirical model-internal finding. The controller computes the terminal gradient with one actual `torch.float64` backward call and independently checks central finite differences. A second backward call evaluates the separate local diagnostic.

The local objective is stationary at the reference point **by construction**. This is not a comparison against all possible local algorithms, finite-difference methods, or symbolic analysis. The late objective measures sensitivity relative to the old value; the runner does not minimize it to restore the obsolete answer. It uses only absolute gradient magnitudes as review weights. For these linear cases, normalizing those magnitudes cancels the common terminal residual, making the allocation proportional to the absolute terminal coefficients. This is a credit-transport canary, not evidence that autograd provides information unavailable to an exact algebraic method.

### Locked development fixtures

| Case | Immediate gradient | Terminal gradient | Adjoint weights (E_A,E_B,E_C) | Cyclic scrambled weights |
| --- | --- | --- | --- | --- |
| shifted_readout | (0,0,0) | (0,-4,4) | (0,50,50) | (50,0,50) |
| merged_register | (0,0,0) | (38,19,19) | (50,25,25) | (25,50,25) |
| cancelled_branch | (0,0,0) | (-40,0,40) | (50,0,50) | (50,50,0) |

A separate integer matrix computation grades the numeric answer and support lineage after generation. In particular, algebraic cancellation can make an input receipt irrelevant even when it appears in a transition matrix.

## Hosted protocol

Three conditions run once on each of three engineered cases, **nine maximum attempts**, in a Latin-rotated serial schedule:

| Case | First | Second | Third |
| --- | --- | --- | --- |
| shifted_readout | direct | scrambled | adjoint |
| merged_register | scrambled | adjoint | direct |
| cancelled_branch | adjoint | direct | scrambled |

All arms receive identical chronological evidence and one output contract: an integer `answer` string and chronologically ordered `support_ids`. Each controlled pair receives exactly the same review-weight multiset and instruction text. Only the assignment of weights to the three input evidence IDs changes. Direct receives no review weights and is contextual, not the matched primary control.

- **Adjoint:** largest-remainder integer weights from the absolute terminal gradient.
- **Scrambled:** cyclic reassignment of those exact weights to different input sites, without changing their multiset.
- **Direct:** full raw evidence, no externally allocated review weights.

The default requested output ceiling is 384 tokens. The model is bound when creating the plan via `--model`; it is not intrinsically GPT-5.6 or tied to any single provider family. This runner's first transport adapter is OpenAI **Responses API**. It passes `store=False` and uses `max_retries=0`. Choose an exact model identity that the provider will return: alias-to-snapshot resolution is not silently accepted. Unsupported provider features, incomplete provider responses, returned-model drift, or other call failures consume an attempt and stop the block; they do not trigger fallback.

The source file SHA-256, model ID, output ceiling, actual nine prompts, prompt fingerprints, instructions hash, output schema hash, and execution schedule are sealed before dispatch. A START record is saved before every call. Reports are local mode-0600 files, never automatically overwritten or resumed, and are verified offline against the exact source-bound plan. Checksums establish consistency, **not provider-signed authenticity or global exactly-once guarantees**. Output-path refusal is local: using another path or clone is not prevented by a global consumption ledger and is prohibited by this protocol after a consumed attempt.

### Receipt and failure boundary

Every returned response's available public text, response ID, returned model, status, incomplete reason, provider error code, and token usage are persisted **before** terminal-status/model validation. Missing usage remains `null`, never zero-imputed. Local failures retain the distinct `PROVIDER_INCOMPLETE` or `RETURNED_MODEL_DRIFT` reason; other exceptions retain a sanitized exception class under `PROVIDER_EXCEPTION`, not arbitrary exception text.

Offline verification checks recorded model identities and provider statuses, typed usage, exact grades, the scheduled prefix, and terminal-state consistency. It rejects unknown statuses, a completed label on a truncated ledger, a stop label without a terminal error, and attempts after a recorded failure. A crash-recovered `RUNNING` prefix is incomplete, never promoted. The `run` and `verify` CLIs return a nonzero exit status on stopped/incomplete collections.

Completed responses containing malformed JSON, duplicate keys, invalid values, or wrong answers are **graded failures**, not provider failures. They stay in the planned denominator and collection continues. Provider failures stop the block and leave the remaining mathematical outcomes unassessed. These two paths must not be conflated.

### Endpoints and interpretation

- **Primary descriptive outcome:** per-arm exact `answer`, exact required `support_ids`, and strict conjunction, out of three planned cases.
- **Protocol outcomes:** all nine provider calls completed with the locked model identity, correct prompt hashes, exact attempt accounting, and no retries or rescue. Output-schema compliance is graded separately.
- **No-claim outcome:** if direct is already correct or adjoint matches scrambled, report the ceiling or null contrast as observed.

The controller has full *public mathematical dynamics*, so it can already derive exact sensitivity. The trial tests whether transferring that localization to the generator changes its behavior. It does **not** show that a black-box model recovered hidden credit, that the controller discovered unknown dynamics, or that backpropagation is better than symbolic algebra. With only three synthetic cases and one serial block, any observed effect is descriptive, not a population estimate or a demonstrated general reasoning gain.

## Commands

The first hosted block is now closed: nine completed calls, with all arms at
0/3 exact answer, 1/3 exact support, and 0/3 strict. See the
[execution note](RND_DELAYED_TERMINAL_CREDIT_V0_9_1_RUN.md) for model/configuration,
retained failures, and offline replay. The commands below describe the original
protocol; they do not authorize repeating that consumed block under a new path.

```bash
python3 -m pip install -r requirements-core.txt
python3 delayed_terminal_credit_v0_9_1.py self-test
python3 -m unittest -v test_delayed_terminal_credit_v0_9_1

# Freeze on the exact checked-out source before provider execution.
python3 delayed_terminal_credit_v0_9_1.py plan \
  --model YOUR_EXACT_RESPONSES_MODEL_ID \
  --max-output-tokens 384 \
  --output /tmp/ebrt-delayed-plan.json

# Requires OPENAI_API_KEY. Exactly nine intended calls, no retries.
python3 delayed_terminal_credit_v0_9_1.py run \
  --plan /tmp/ebrt-delayed-plan.json \
  --output /tmp/ebrt-delayed-report.json

python3 delayed_terminal_credit_v0_9_1.py verify \
  --plan /tmp/ebrt-delayed-plan.json \
  --report /tmp/ebrt-delayed-report.json
```

Install the OpenAI Python SDK in the runner environment for the hosted command. No hosted result may be described as `PASS` until that exact source-bound report exists and passes offline verification. The local mock API test cannot establish hosted accuracy.

The pre-merge lightweight review passed **16 network-zero tests**, including incomplete-response retention, returned-model drift, coherently resealed model/status/grade tampering, malformed-output denominator preservation, duplicate/nonfinite JSON rejection, and CLI failure exits. The three fixtures, mathematical objectives, allocation rules, public prompts, and nine-call schedule were not changed by that hardening. API collection was unexecuted at merge; the subsequent first block is recorded separately in the [execution note](RND_DELAYED_TERMINAL_CREDIT_V0_9_1_RUN.md).

## Next decision

Only after reading the completed artifact should EBRT decide whether to design a larger, fresh and better balanced evaluation, or whether the public-dynamics controller primarily provides a useful **source reinspection primitive** without a measurable hosted quality effect. Do not tune the current three fixtures against API outputs, replace failures, or relabel local proof as hosted superiority.
