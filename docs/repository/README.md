# Repository and research history

This directory map and history were relocated from the former root README, retaining original artifact references and frozen-result caveats. Start with [EBRT](../../README.md) and the [documentation index](../README.md).

## Repository map

### Active path

| Path | Role |
| --- | --- |
| [`ebrt_core.py`](../../ebrt_core.py) | v0.7.1/v0.8 monolith and CLI |
| [`ebrt_engine.py`](../../ebrt_engine.py) | standard coverage-first single-lane engine over the verified historical optimizer |
| [`ebrt_reinspection.py`](../../ebrt_reinspection.py) | opt-in public reinspection planner, exact token allocation, and source-quotation validation |
| [`ebrt_reinspection_hosted.py`](../../ebrt_reinspection_hosted.py) | bounded extraction/final orchestration, explicit provider ledger, and offline verifier |
| [`ebrt_dependency_reinspection.py`](../../ebrt_dependency_reinspection.py) | dependency-ordered planning, source-bound parent context, and post-run source-span grades |
| [`ebrt_dependency_hosted.py`](../../ebrt_dependency_hosted.py) | opt-in dependency-aware audit execution and offline report reconstruction |
| [`ebrt_dependency_cases.py`](../../ebrt_dependency_cases.py) | long-record consignment/account/tariff lookup diagnostic |
| [`ebrt_dependency_canary.py`](../../ebrt_dependency_canary.py) | six-attempt comparison sharing a two-audit prefix |
| [`ebrt_coloring.py`](../../ebrt_coloring.py) | non-unique coloring task, independent feasibility predicates, and blind judging rubric |
| [`ebrt_coloring_hosted.py`](../../ebrt_coloring_hosted.py) | three audits, free JSON answer, four LLM judgments, and offline verification |
| [`ebrt_demo.py`](../../ebrt_demo.py) | network-zero comparison walkthrough with deterministic JSON output |
| [`ebrt_hosted.py`](../../ebrt_hosted.py) | two-call hosted comparison through the current core, with local-only provider receipts |
| [`ebrt_support_cases.py`](../../ebrt_support_cases.py) | three fresh, engineered required-support diagnostics |
| [`ebrt_support_eval.py`](../../ebrt_support_eval.py) | predeclared nine-call support-retention comparison and offline result verifier |
| [`ebrt_alignment_cases.py`](../../ebrt_alignment_cases.py) | two fresh entity-join tasks with active competing chains |
| [`ebrt_alignment_eval.py`](../../ebrt_alignment_eval.py) | predeclared eight-call numeric-alignment/placement diagnostic and offline verifier |
| [`local_output_diff_corpus_v0_8_2.py`](../../local_output_diff_corpus_v0_8_2.py) | matched local-model output corpus runner |
| [`role_stratified_uptake_canary_v0_8_3.py`](../../role_stratified_uptake_canary_v0_8_3.py) | fresh three-arm compiler-coverage/provider-uptake canary |
| [`policy_lock_role_stratified_uptake_v0_8_3.json`](../../policy_lock_role_stratified_uptake_v0_8_3.json) | pre-call v0.8.3 case, schedule, model, and source lock |
| [`typed_revision_channel_canary_v0_8_4.py`](../../typed_revision_channel_canary_v0_8_4.py) | sealed two-model, four-arm typed revision-channel canary |
| [`policy_lock_typed_revision_channel_v0_8_4.json`](../../policy_lock_typed_revision_channel_v0_8_4.json) | pre-call v0.8.4 cases, models, schedule, source, and invocation lock |
| [`interpret_typed_revision_channel_v0_8_4.py`](../../interpret_typed_revision_channel_v0_8_4.py) | deterministic post-review contrast and denominator interpreter |
| [`typed_public_state_regression_v0_8_5.py`](../../typed_public_state_regression_v0_8_5.py) | frozen typed-state runner and fail-closed portable verifier for the two-stage readiness artifact |
| [`policy_lock_typed_public_state_v0_8_5.json`](../../policy_lock_typed_public_state_v0_8_5.json) | pre-call v0.8.5 sources, exact models, readiness, cases, and invocation lock |
| [`public_role_transport_canary_v0_8_5_1.py`](../../public_role_transport_canary_v0_8_5_1.py) | caller-supplied public-role transport repair over the v0.8.5 task-shaped gate |
| [`policy_lock_public_role_transport_v0_8_5_1.json`](../../policy_lock_public_role_transport_v0_8_5_1.json) | pre-call v0.8.5.1 runner, role-record schema, exact models, readiness, cases, and invocations |
| [`interpret_public_role_transport_v0_8_5_1.py`](../../interpret_public_role_transport_v0_8_5_1.py) | deterministic prompt-delta and normalized public-state interpreter for sealed v0.8.5.1 |
| [`public_role_transport_isolation_v0_8_5_2.py`](../../public_role_transport_isolation_v0_8_5_2.py) | exact role-only prompt isolation and two-stage local adapter canary |
| [`policy_lock_public_role_transport_isolation_v0_8_5_2.json`](../../policy_lock_public_role_transport_isolation_v0_8_5_2.json) | pre-call runner, dependencies, nine prompt projections, exact models, schedule, and invocation lock |
| [`interpret_public_role_transport_isolation_v0_8_5_2.py`](../../interpret_public_role_transport_isolation_v0_8_5_2.py) | deterministic v0.8.5-to-v0.8.5.2 readiness, prompt, and normalized output interpreter |
| [`public_role_adapter_breadth_v0_8_5_3.py`](../../public_role_adapter_breadth_v0_8_5_3.py) | readiness-first Llama/Gemma adapter-breadth canary on the byte-exact v0.8.5.2 surface |
| [`policy_lock_public_role_adapter_breadth_v0_8_5_3.json`](../../policy_lock_public_role_adapter_breadth_v0_8_5_3.json) | pre-call source, prompt-surface, exact model, schedule, and no-retry lock |
| [`interpret_public_role_adapter_breadth_v0_8_5_3.py`](../../interpret_public_role_adapter_breadth_v0_8_5_3.py) | no-call static rendering-capability and sealed readiness interpreter |
| [`role_stratified_uptake_integrity_v0_8_3_1.py`](../../role_stratified_uptake_integrity_v0_8_3_1.py) | source- and model-bound integrity replication wrapper |
| [`policy_lock_role_stratified_uptake_v0_8_3_1_r02.json`](../../policy_lock_role_stratified_uptake_v0_8_3_1_r02.json) | pre-call hashes for the wrapper and every imported local execution file |
| [`role_stratified_uptake_integrity_v0_8_3_2.py`](../../role_stratified_uptake_integrity_v0_8_3_2.py) | exact expected model-snapshot manifest wrapper |
| [`policy_lock_role_stratified_uptake_v0_8_3_2_r03.json`](../../policy_lock_role_stratified_uptake_v0_8_3_2_r03.json) | pre-call relative path, byte-size, and blob-hash manifest |
| [`role_stratified_uptake_integrity_v0_8_3_3.py`](../../role_stratified_uptake_integrity_v0_8_3_3.py) | loader-bound private APFS staging wrapper |
| [`policy_lock_role_stratified_uptake_v0_8_3_3_r04.json`](../../policy_lock_role_stratified_uptake_v0_8_3_3_r04.json) | pre-call loader-path and staged-byte policy lock |
| [`role_stratified_uptake_integrity_v0_8_3_4.py`](../../role_stratified_uptake_integrity_v0_8_3_4.py) | exact Python/platform/distribution runtime wrapper |
| [`policy_lock_role_stratified_uptake_v0_8_3_4_r05.json`](../../policy_lock_role_stratified_uptake_v0_8_3_4_r05.json) | pre-call exact local runtime-version lock |
| [`role_stratified_uptake_integrity_v0_8_3_5.py`](../../role_stratified_uptake_integrity_v0_8_3_5.py) | unlinked read-only model image and imported-code wrapper |
| [`policy_lock_role_stratified_uptake_v0_8_3_5_r06.json`](../../policy_lock_role_stratified_uptake_v0_8_3_5_r06.json) | pre-call immutable-model/runtime-code lock |
| [`role_stratified_uptake_integrity_v0_8_3_6.py`](../../role_stratified_uptake_integrity_v0_8_3_6.py) | complete imported-dependency and exact locked-mount verifier |
| [`policy_lock_role_stratified_uptake_v0_8_3_6_r07.json`](../../policy_lock_role_stratified_uptake_v0_8_3_6_r07.json) | pre-call complete runtime-code and lock-derived mount receipt |
| [`role_stratified_uptake_integrity_v0_8_3_7.py`](../../role_stratified_uptake_integrity_v0_8_3_7.py) | verified-source child bootstrap and bytecode-cache divergence guard |
| [`policy_lock_role_stratified_uptake_v0_8_3_7_r08.json`](../../policy_lock_role_stratified_uptake_v0_8_3_7_r08.json) | pre-call source-execution policy and module receipt |
| [`requirements-core.txt`](../../requirements-core.txt) | network-zero core dependency |
| [`requirements-local-mlx.txt`](../../requirements-local-mlx.txt) | Apple-silicon local backend |
| [`docs/EBRT_CORE_THESIS.md`](../../docs/EBRT_CORE_THESIS.md) | mathematical and conceptual anchor |
| [`docs/MODEL_ADAPTER_PROTOCOL.md`](../../docs/MODEL_ADAPTER_PROTOCOL.md) | provider-neutral binding contract |
| [`docs/ROADMAP_MODEL_INTERFACE_CORE.md`](../../docs/ROADMAP_MODEL_INTERFACE_CORE.md) | evidence-labelled path beyond v0.8 |
| [`docs/RND_LOCAL_OUTPUT_DIFF_CORPUS_V0_8_2.md`](../../docs/RND_LOCAL_OUTPUT_DIFF_CORPUS_V0_8_2.md) | generated-output failure atlas and bounded next hypotheses |
| [`docs/RND_ROLE_STRATIFIED_UPTAKE_CANARY_V0_8_3.md`](../../docs/RND_ROLE_STRATIFIED_UPTAKE_CANARY_V0_8_3.md) | role-coverage repair result and remaining provider-uptake boundary |
| [`docs/RND_TYPED_REVISION_CHANNEL_V0_8_4.md`](../../docs/RND_TYPED_REVISION_CHANNEL_V0_8_4.md) | typed-channel result, readiness-gate defect, and next bounded adapter repair |
| [`artifacts/model_interface_core_v0_7_1/local_mistral_e2e_r01.json`](../../artifacts/model_interface_core_v0_7_1/local_mistral_e2e_r01.json) | sanitized real local E2E receipt |
| [`artifacts/local_output_diff_corpus_v0_8_2/r01/results.json`](../../artifacts/local_output_diff_corpus_v0_8_2/r01/results.json) | sealed four-model, 32-call development corpus |
| [`artifacts/role_stratified_uptake_v0_8_3/r01/results.json`](../../artifacts/role_stratified_uptake_v0_8_3/r01/results.json) | sealed one-model, nine-call uptake canary |
| [`artifacts/typed_revision_channel_v0_8_4/r01/results.json`](../../artifacts/typed_revision_channel_v0_8_4/r01/results.json) | sealed two-model, 34-call typed-channel canary |
| [`artifacts/role_stratified_uptake_v0_8_3/r02_integrity/results.json`](../../artifacts/role_stratified_uptake_v0_8_3/r02_integrity/results.json) | preserved source-bound repetition; not fresh evidence |
| [`artifacts/role_stratified_uptake_v0_8_3/r03_snapshot_bound/results.json`](../../artifacts/role_stratified_uptake_v0_8_3/r03_snapshot_bound/results.json) | preserved exact-snapshot-bound repetition; not fresh evidence |
| [`artifacts/role_stratified_uptake_v0_8_3/r04_loader_bound/results.json`](../../artifacts/role_stratified_uptake_v0_8_3/r04_loader_bound/results.json) | preserved loader-bound repetition; not fresh evidence |
| [`artifacts/role_stratified_uptake_v0_8_3/r05_runtime_bound/results.json`](../../artifacts/role_stratified_uptake_v0_8_3/r05_runtime_bound/results.json) | preserved runtime-version-bound repetition; not fresh evidence |
| [`artifacts/role_stratified_uptake_v0_8_3/r06_immutable_runtime_code/results.json`](../../artifacts/role_stratified_uptake_v0_8_3/r06_immutable_runtime_code/results.json) | preserved immutable-model/runtime-code repetition; not fresh evidence |
| [`artifacts/role_stratified_uptake_v0_8_3/r07_complete_integrity/results.json`](../../artifacts/role_stratified_uptake_v0_8_3/r07_complete_integrity/results.json) | preserved complete-integrity repetition; not fresh evidence |
| [`artifacts/role_stratified_uptake_v0_8_3/r08_verified_source/results.json`](../../artifacts/role_stratified_uptake_v0_8_3/r08_verified_source/results.json) | canonical verified-source repetition; not fresh evidence |

### Frozen research history

Root-level v0.1-v0.6.3.2 modules, `policy_lock_*.json`, reports, and artifacts
are retained as immutable research history. They include negative results that
shaped the current abstraction: a mathematically valid control surface can be
ignored by a generator, public lineage is not the same as control uptake, and
integrity closure is not method superiority.

The most useful historical entrypoints are:

- [`ebrt_monolith_v0_1.py`](../../ebrt_monolith_v0_1.py): original differentiable toy
  mechanism;
- [`ebrt.py`](../../ebrt.py): sealed Apply Revision acceptance engine;
- [`ebrt_live.py`](../../ebrt_live.py): frozen v0.6 live runtime;
- [`docs/ROADMAP_V0_6_PLUS.md`](../../docs/ROADMAP_V0_6_PLUS.md): pre-core roadmap and
  decision record;
- [`SUBMISSION.md`](../../SUBMISSION.md): historical Build Week presentation, no
  longer the project definition.

## Roadmap

The active roadmap is
[`docs/ROADMAP_MODEL_INTERFACE_CORE.md`](../../docs/ROADMAP_MODEL_INTERFACE_CORE.md).
The next scientific gates are:

1. two distinct real local model IDs behind the same protocol;
2. a hosted adapter E2E when credentials and policy are available;
3. external public control versus an admitted model-native latent actuator;
4. fresh matched evaluation of actuator uptake and output quality.

## Origin

EBRT began as a sketch in which a latent reasoning trajectory receives a
trajectory-level loss and backward revision before decoding. The Build Week
deadline compressed that sketch into a hosted-model runtime, an Inspector, and
strict public artifacts. Those components remain valuable, but the current
definition is broader: **the missing primitive is backward revision at
inference time**, independent of any particular provider.

## License

Apache License 2.0. See [`LICENSE`](../../LICENSE).
