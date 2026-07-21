# EBRT Core Thesis

Status: **DESIGN ANCHOR — NOT A NEW EMPIRICAL RESULT**

This note fixes the conceptual north star of EBRT while separating it from the
smaller public-state mechanisms that this repository can currently observe and
test.

> **EBRT treats reasoning as an explicit, revisable computation rather than
> only an irreversible token prefix.** When later evidence changes the validity
> of an earlier premise, a bounded backward signal should assign credit to the
> relevant earlier operations, update an admitted control, and execute the
> affected computation forward again before final generation.

This thesis is broader than any completed experiment in the repository. It is
an architectural constraint on future versions, not evidence that a hosted
model exposes its private reasoning or hidden states.

## The originating sketch

The original intuition represented a reasoning episode as a continuous
trajectory

\[
\mathcal H = (H_1, H_2, \ldots, H_T),
\qquad
H_t = f_{\theta,t}(H_{t-1}, H_0, E_t),
\]

evaluated that trajectory with a differentiable objective such as

\[
\mathcal L_{sketch}
=g_{\phi}(H_{1:T},E_{1:T},C)
=\mathcal L_{consistency}
-\lambda\mathcal L_{novelty},
\]

propagated terminal error backward through time, and decoded only after
revision. This objective was illustrative, not a calibrated loss implemented
by the current repository. The important idea was not silent chain-of-thought
or a particular Transformer implementation. It was that intermediate reasoning
should be treated as a testable computation with an explicit revision path.

Three parts of the sketch remain the EBRT anchor:

1. **Forward execution:** later states depend on earlier states and on evidence
   arriving at particular positions.
2. **Trajectory-level evaluation:** the endpoint is not the only inspectable
   object; preservation, invalidation, drift, and dependency consistency can be
   evaluated over the public trajectory.
3. **Backward credit followed by forward re-execution:** a late error is routed
   to admitted earlier controls, after which the affected computation is run
   forward again.

## Corrected control formulation

Directly updating every state vector independently,

\[
H_t \leftarrow H_t - \eta\nabla_{H_t}\mathcal L,
\]

can move the trajectory outside the states reachable by its declared forward
program. EBRT therefore treats the states as consequences of the program and
optimizes bounded controls instead.

For an episode observed through horizon \(\tau\), let

\[
h_0 = \operatorname{Enc}_{\theta}(x),
\qquad
h_t = F_{\theta,t}(h_{t-1}, e_t, u_t),
\quad t=1,\ldots,\tau,
\]

where \(e_t\) is the evidence admitted at position \(t\), and \(u_t\) is a
bounded intervention exposed by the implementation. A trajectory objective is

\[
J_{\tau}(u) =
\Phi_{\tau}(h_{\tau};c_{\tau})
+ \sum_{t=1}^{\tau}\ell_t(h_t,u_t;c_{\tau}),
\]

where \(c_{\tau}\) is the public terminal contract at that horizon. The adjoint
recurrence is

\[
\lambda_{\tau}
= \nabla_{h_{\tau}}\Phi_{\tau}
+ \nabla_{h_{\tau}}\ell_{\tau},
\]

\[
\lambda_t
= \nabla_{h_t}\ell_t
+ \left(\frac{\partial F_{\theta,t+1}}{\partial h_t}\right)^{\!\top}
  \lambda_{t+1},
\quad t=\tau-1,\ldots,1.
\]

For a control applied while producing \(h_t\),

\[
\nabla_{u_t}J_{\tau}
= \nabla_{u_t}\ell_t
+ \left(\frac{\partial F_{\theta,t}}{\partial u_t}\right)^{\!\top}
  \lambda_t.
\]

The revision step is projected back into the declared control set:

\[
u^{(k+1)} =
\Pi_{\mathcal U(c_{\tau})}
\left(u^{(k)}-\eta\nabla_u J_{\tau}\right).
\]

The program is then rolled forward with the revised controls. Projection,
control regularization, rollback, and exact no-event identity are part of the
mechanism contract; an unconstrained change to an arbitrary intermediate state
is not.

In the latent north-star formulation, a language head could decode an admitted
revised state only after this process:

\[
p(y_j\mid y_{<j},h^{(K)}_{1:\tau})
= \operatorname{Softmax}(W_v d_j(h^{(K)}_{1:\tau},y_{<j})).
\]

That equation is a research target. It does not describe the hosted-model
integration currently implemented in this repository.

## The observable implementation ladder

The project translates the latent thesis into progressively more observable
contracts:

| Level | Representation | Current meaning |
| --- | --- | --- |
| Latent north star | model-native hidden trajectory and admitted latent controls | Research hypothesis; not implemented for GPT or another hosted model |
| Public differentiable substrate | typed semantic states, dependencies, local recurrence, and bounded external controls | Mechanism studied by v0.5.0 and the experimental v0.5-T branch |
| Full-context execution backend | public control map projected into one full-context regeneration | Implemented as a non-differentiable bridge in v0.5.1 and exercised in v0.5.2 |
| Revisable public trajectory runtime | chronological three-axis public recurrence, trajectory-wide loss, time-local controls, replay, and compiled actuator | Implemented network-zero in Runtime Preview 3 (`v0.6.2.4`); no new hosted-effect result |
| Reasoning IDE | recorded or live evidence, event, neutral/revised trajectories, controls, output diff, and strict diagnostics | Provisional Inspector/Workbench surface; not a final product claim |

The public representation is neither a transcript of private chain-of-thought
nor a claim that it is isomorphic to model internals. It is an intentionally
small, typed program through which revision hypotheses can be audited and
falsified.

## Gradient and information boundaries

The current architecture has explicit discontinuities:

```text
raw public evidence
  -> semantic annotation or adapter
       STOP-GRADIENT: adapter output becomes a frozen public artifact
  -> typed public dependency / temporal program
  -> differentiable local surrogate and bounded controls
       backward() EXISTS ONLY INSIDE THIS LOCAL PROGRAM
  -> deterministic public control-map projection
       NON-DIFFERENTIABLE JSON BOUNDARY
  -> full-context hosted regeneration
       PROVIDER IS NOT PART OF THE AUTOGRAD GRAPH
  -> independently computed output and lineage grades
       GRADER VERDICTS DO NOT FLOW BACK INTO A FROZEN RUN
```

Consequently:

- no gradient crosses semantic extraction, JSON serialization, a provider API,
  sampling, or final natural-language output;
- provider reasoning tokens, latency, and usage are measurements or budget
  constraints, not differentiable semantic loss terms;
- a typed grader failure may motivate a separately locked successor, but cannot
  rewrite the contract or controls of the artifact that revealed it; and
- public evidence and support lineage may be inspected without requesting or
  storing private chain-of-thought.

## What "backward" means at each layer

The word has deliberately different, bounded meanings:

- in v0.1, it means a controlled revision routed to an earlier explicit toy
  state followed by suffix replay;
- in v0.5.0, it means autograd through a frozen public semantic surrogate into
  external evidence gates;
- in v0.5-T, it means an exact local adjoint through an oracle-specified public
  temporal recurrence;
- in v0.5.3, it means deterministic dependency traversal and fact-level
  direct/inherited closure over a role-factorized public program;
- in v0.5.4, it means exact normalized temporal credit over the compiled
  factorized program, checked against autograd, finite differences, and matched
  within-node timing shams;
  and
- in v0.5.5, it means exact block credit over three byte-sealed public
  trajectories joined by one fixed typed incidence program, with a disconnected
  stable Constraint lane and separately bounded merge slack; and
- in Runtime Preview 3 (`v0.6.2.4`), it means one real reverse-mode pass over
  bounded scalar controls inside a chronological three-axis public recurrence,
  followed by deterministic projected replay and exact compilation into the
  existing public actuator.

None of these definitions licenses the phrase "backpropagation through GPT."

The completed v0.5.5 gate establishes that this public trajectory substrate is
composable under its frozen contaminated program. It does not establish that
the three lanes are agents, that their composition improves an answer, or that
the fixed junction is an effective orchestration policy. Those become new,
separately locked execution questions in v0.6 and later.

## Deferred novelty objective

The originating sketch included a novelty reward intended to resist generic or
centroid-seeking continuations. That remains an interesting research direction,
but it is deliberately excluded from v0.5.3-v0.5.5.

A novelty term is unsafe to interpret before the project has fixed:

- the comparison corpus or reference distribution;
- the semantic representation and distance metric;
- a task-validity and factuality guardrail;
- a matched control that distinguishes useful novelty from arbitrary drift; and
- resistance to reward hacking through rare wording or unsupported claims.

Dependency, time, and multi-trajectory composition are therefore isolated
first. Novelty may later enter as a preregistered objective under its own
controls; it is not silently folded into lineage or temporal loss.

## Standing nonclaims

The Core Thesis does **not** establish that:

- a hosted model exposes editable hidden states;
- the public semantic program faithfully recovers private model computation;
- local surrogate improvement predicts generated-output improvement;
- differentiable control outperforms a matched textual instruction;
- EBRT improves general reasoning accuracy, creativity, or reliability;
- temporal credit alone explains the v0.5-T synthetic result; or
- a successful contaminated regression is fresh benchmark evidence.

These boundaries are part of the thesis: EBRT should make revision claims more
testable, not make them larger than the evidence.
