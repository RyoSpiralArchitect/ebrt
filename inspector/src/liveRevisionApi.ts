import type {
  ActuatorExecutionTraceStep,
  AssessmentStatus,
  CreditRow,
  EvidenceRecord,
  InspectionPlanStep,
  LiveApplyRevisionResponse,
  LiveDemoRequestEnvelope,
  ProviderPublicOutput,
  PublicDependencyAudit,
  PublicRevisionTrajectory,
  PublicTrajectoryAxis,
  PublicTrajectoryPoint,
  RevisionProgramStep,
  TargetValue,
} from "./applyRevisionTypes";

const DEMO_REQUEST_SCHEMA = "ebrt-live-demo-request-v0.6.2.4";
const LIVE_REQUEST_SCHEMA = "ebrt-live-apply-revision-request-v0.6.2.4";
const LIVE_RESPONSE_SCHEMA = "ebrt-live-apply-revision-response-v0.6.2.4";
const PUBLIC_TRAJECTORY_SCHEMA = "ebrt-live-public-revision-trajectory-v0.6.2.4";
const INSPECTION_PLAN_SCHEMA = "ebrt-live-continuous-inspection-plan-v0.6.2.4";
const REVISION_PROGRAM_SCHEMA = "ebrt-live-public-revision-program-v0.6.2.4";
const DEPENDENCY_AUDIT_SCHEMA = "ebrt-live-public-dependency-audit-v0.6.2.4";
const TRAJECTORY_AXES = [
  "event_consistent_support",
  "invalidated_support_clearance",
  "stable_support_retention",
] as const satisfies readonly PublicTrajectoryAxis[];
const SHA256 = /^[0-9a-f]{64}$/;
const BODY_SHA256_HEADER = "X-EBRT-Body-SHA256";
const OPERATIONAL_ROW_LABELS: Record<string, string> = {
  provider_output_schema_valid: "Provider output schema",
  selected_closure_lineage_bound: "Selected closure lineage",
  correction_evidence_active: "Correction evidence active",
  all_invalidated_evidence_absent: "All invalidated support removed",
  invalidation_transition_exact: "Exact invalidation transition",
  prior_invalidations_preserved: "Prior invalidations preserved",
  no_previously_invalidated_evidence_resurrected: "No invalidated evidence resurrected",
  changed_fact_targets_exist: "Changed fact target",
  changed_fact_targets_bind_correction: "Fact-local correction lineage",
  stable_bound_targets_exist: "Stable target binding",
  stable_bound_targets_preserved: "Stable target preserved",
  public_diff_observable: "Public output diff",
  public_structural_dependency_block_restore: "Public structural dependency",
};
const SEMANTIC_ROW_DETAIL = "Reserved gold fields are rejected; caller semantic content is unverified";
const EFFECT_ROW_DETAIL = "One regeneration is not a causal contrast";
const CONTROL_CHECK_KEYS = [
  "actual_before_state_bound_to_controller",
  "local_backward_executed",
  "finite_continuous_allocation",
  "surrogate_objective_decreased",
  "non_neutral_control_map",
  "control_budget_respected",
  "allocation_simplex_respected",
  "ineligible_allocation_zero",
  "surrogate_terminal_state_increased",
  "public_trajectory_bound",
  "pre_event_temporal_credit_nonzero",
  "trajectory_path_loss_decreased",
  "stable_axis_exact_identity",
  "exact_temporal_placement_beats_matched_sham",
  "finite_difference_agreement",
  "gradient_stops_before_provider",
  "reserved_gold_fields_absent",
] as const;
const ACTUATOR_CHECK_KEYS = [
  "source_control_map_bound",
  "source_public_trajectory_bound",
  "selected_count_exact",
  "continuous_allocation_finite",
  "selected_allocation_simplex_respected",
  "abstract_inspection_budget_exact",
  "deterministic_priority_order",
  "operation_sets_disjoint",
  "program_steps_bounded",
  "gradient_stops_at_public_program",
] as const;
const EXECUTION_CHECK_KEYS = [
  "source_actuator_bound",
  "source_control_map_bound",
  "source_public_trajectory_bound",
  "program_state_machine_complete",
  "execution_trace_exact",
  "program_summaries_exact",
  "emitted_operation_sealed",
  "abstract_inspection_budget_exact",
  "provider_operation_gold_free",
] as const;
const TRAJECTORY_CHECK_KEYS = [
  "source_actual_before_state_bound",
  "chronological_forward_exact",
  "single_backward_executed",
  "pre_event_temporal_credit_nonzero",
  "correction_site_credit_nonzero",
  "trajectory_objective_decreased",
  "trajectory_path_loss_decreased",
  "revised_forward_replay_exact",
  "stable_axis_exact_identity",
  "bounded_time_local_control",
  "matched_sham_control_geometry",
  "exact_temporal_placement_beats_matched_sham",
  "gradient_stops_before_json",
] as const;
const DEPENDENCY_CHECK_KEYS = [
  "changed_fact_targets_exist",
  "correction_bound_before_block",
  "correction_absent_when_blocked",
  "changed_fact_lineage_changes_when_blocked",
  "event_consistency_breaks_when_blocked",
  "stable_evidence_binding_preserved",
  "unblocked_recomputation_exact",
] as const;
const ALLOCATION_TOLERANCE = 1e-9;

export class LiveRevisionApiError extends Error {
  readonly code: string;
  readonly status?: number;

  constructor(message: string, code: string, status?: number) {
    super(message);
    this.name = "LiveRevisionApiError";
    this.code = code;
    this.status = status;
  }
}

function fail(label: string): never {
  throw new LiveRevisionApiError(`Live response failed validation: ${label}`, "INVALID_LIVE_RESPONSE");
}

function record(value: unknown, label: string): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) return fail(label);
  return value as Record<string, unknown>;
}

function string(value: unknown, label: string): string {
  if (typeof value !== "string" || value.length === 0) return fail(label);
  return value;
}

function sha256(value: unknown, label: string): string {
  const observed = string(value, label);
  if (!SHA256.test(observed)) return fail(label);
  return observed;
}

function canonicalJson(value: unknown): string {
  if (value === null) return "null";
  if (typeof value === "string" || typeof value === "boolean") return JSON.stringify(value);
  if (typeof value === "number") {
    if (!Number.isFinite(value)) return fail("canonical JSON contains a non-finite number");
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  if (typeof value === "object") {
    const candidate = value as Record<string, unknown>;
    return `{${Object.keys(candidate)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${canonicalJson(candidate[key])}`)
      .join(",")}}`;
  }
  return fail("canonical JSON contains an unsupported value");
}

async function digestSha256(value: string): Promise<string> {
  if (!globalThis.crypto?.subtle) {
    throw new LiveRevisionApiError(
      "Browser SHA-256 support is required for Live response binding",
      "INTEGRITY_CHECK_UNAVAILABLE",
    );
  }
  const digest = await globalThis.crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

function compactJsonPreservingNumberLexemes(raw: string): string {
  let compact = "";
  let inString = false;
  let escaped = false;
  for (const character of raw) {
    if (inString) {
      compact += character;
      if (escaped) escaped = false;
      else if (character === "\\") escaped = true;
      else if (character === '"') inString = false;
    } else if (character === '"') {
      inString = true;
      compact += character;
    } else if (!/\s/u.test(character)) {
      compact += character;
    }
  }
  if (inString || escaped) return fail("response canonical JSON string termination");
  return compact;
}

function canonicalResponseWithoutSelfSeal(raw: string): string {
  const compact = compactJsonPreservingNumberLexemes(raw);
  if (!compact.startsWith("{") || !compact.endsWith("}")) {
    return fail("response canonical JSON object");
  }
  const body = compact.slice(1, -1);
  const members: string[] = [];
  let start = 0;
  let depth = 0;
  let inString = false;
  let escaped = false;
  for (let index = 0; index < body.length; index += 1) {
    const character = body[index];
    if (inString) {
      if (escaped) escaped = false;
      else if (character === "\\") escaped = true;
      else if (character === '"') inString = false;
      continue;
    }
    if (character === '"') inString = true;
    else if (character === "{" || character === "[") depth += 1;
    else if (character === "}" || character === "]") {
      depth -= 1;
      if (depth < 0) return fail("response canonical JSON nesting");
    } else if (character === "," && depth === 0) {
      members.push(body.slice(start, index));
      start = index + 1;
    }
  }
  if (inString || escaped || depth !== 0) return fail("response canonical JSON structure");
  members.push(body.slice(start));
  const sealPrefix = '"fingerprint_sha256":';
  const sealMembers = members.filter((member) => member.startsWith(sealPrefix));
  if (sealMembers.length !== 1) return fail("response fingerprint_sha256 cardinality");
  if (!/^"fingerprint_sha256":"[0-9a-f]{64}"$/u.test(sealMembers[0])) {
    return fail("response fingerprint_sha256 canonical member");
  }
  return `{${members.filter((member) => !member.startsWith(sealPrefix)).join(",")}}`;
}

function sameCanonical(left: unknown, right: unknown): boolean {
  return canonicalJson(left) === canonicalJson(right);
}

function approximatelyEqual(left: number, right: number, tolerance = ALLOCATION_TOLERANCE): boolean {
  return Math.abs(left - right) <= tolerance;
}

function finiteNumber(value: unknown, label: string, nonnegative = false): number {
  if (typeof value !== "number" || !Number.isFinite(value) || (nonnegative && value < 0)) return fail(label);
  return value;
}

function finiteNumbers(value: unknown, label: string, expectedLength?: number): number[] {
  const observed = array(value, label).map((item, index) =>
    finiteNumber(item, `${label}[${index}]`),
  );
  if (expectedLength !== undefined && observed.length !== expectedLength) return fail(`${label} length`);
  return observed;
}

function integer(value: unknown, label: string, minimum = 0): number {
  const observed = finiteNumber(value, label, true);
  if (!Number.isInteger(observed) || observed < minimum) return fail(label);
  return observed;
}

function boolean(value: unknown, label: string): boolean {
  if (typeof value !== "boolean") return fail(label);
  return value;
}

function array(value: unknown, label: string): unknown[] {
  if (!Array.isArray(value)) return fail(label);
  return value;
}

function strings(value: unknown, label: string): string[] {
  const observed = array(value, label).map((item, index) => string(item, `${label}[${index}]`));
  if (new Set(observed).size !== observed.length) return fail(`${label} contains duplicates`);
  return observed;
}

function status(value: unknown, label: string): AssessmentStatus {
  if (value !== "PASS" && value !== "FAIL" && value !== "NOT_ASSESSED") return fail(label);
  return value;
}

function binaryStatus(value: unknown, label: string): "PASS" | "FAIL" {
  const observed = status(value, label);
  if (observed === "NOT_ASSESSED") return fail(label);
  return observed;
}

function targetValue(value: unknown, label: string): TargetValue {
  const candidate = record(value, label);
  const targetType = string(candidate.target_type, `${label}.target_type`);
  if (targetType !== "fact" && targetType !== "constraint") return fail(`${label}.target_type`);
  return {
    slot: string(candidate.slot, `${label}.slot`),
    target_id: string(candidate.target_id, `${label}.target_id`),
    target_type: targetType,
    value: string(candidate.value, `${label}.value`),
  };
}

function publicOutput(value: unknown, label: string): ProviderPublicOutput {
  const candidate = record(value, label);
  return {
    schema_version: string(candidate.schema_version, `${label}.schema_version`),
    checkpoint_id: string(candidate.checkpoint_id, `${label}.checkpoint_id`),
    current_answer: string(candidate.current_answer, `${label}.current_answer`),
    selected_closure_id: string(candidate.selected_closure_id, `${label}.selected_closure_id`),
    target_values: array(candidate.target_values, `${label}.target_values`).map((row, index) =>
      targetValue(row, `${label}.target_values[${index}]`),
    ),
  };
}

function evidence(value: unknown, label: string): EvidenceRecord {
  const candidate = record(value, label);
  const role = string(candidate.role, `${label}.role`);
  if (!["public_evidence", "invalidated", "stable_constraint", "late_event"].includes(role)) {
    return fail(`${label}.role`);
  }
  return {
    evidence_id: string(candidate.evidence_id, `${label}.evidence_id`),
    text: string(candidate.text, `${label}.text`),
    role: role as EvidenceRecord["role"],
  };
}

type LiveCreditRow = CreditRow & Required<
  Pick<
    CreditRow,
    | "reinspection_salience"
    | "control_value"
    | "eligible_for_reinspection"
    | "baseline_allocation_fraction"
    | "optimized_allocation_fraction"
    | "allocation_delta"
    | "surrogate_contribution_before"
    | "surrogate_contribution_after"
    | "temporal_step_index"
    | "state_before"
    | "state_after"
  >
>;

function creditRow(value: unknown, label: string): LiveCreditRow {
  const candidate = record(value, label);
  return {
    active_before: boolean(candidate.active_before, `${label}.active_before`),
    evidence_id: string(candidate.evidence_id, `${label}.evidence_id`),
    gradient: finiteNumber(candidate.gradient, `${label}.gradient`),
    finite_difference_gradient: finiteNumber(candidate.finite_difference_gradient, `${label}.finite_difference_gradient`),
    reinspection_salience: finiteNumber(candidate.reinspection_salience, `${label}.reinspection_salience`, true),
    control_value: finiteNumber(candidate.control_value, `${label}.control_value`),
    eligible_for_reinspection: boolean(candidate.eligible_for_reinspection, `${label}.eligible_for_reinspection`),
    baseline_allocation_fraction: finiteNumber(
      candidate.baseline_allocation_fraction,
      `${label}.baseline_allocation_fraction`,
      true,
    ),
    optimized_allocation_fraction: finiteNumber(
      candidate.optimized_allocation_fraction,
      `${label}.optimized_allocation_fraction`,
      true,
    ),
    allocation_delta: finiteNumber(candidate.allocation_delta, `${label}.allocation_delta`),
    surrogate_contribution_before: finiteNumber(
      candidate.surrogate_contribution_before,
      `${label}.surrogate_contribution_before`,
    ),
    surrogate_contribution_after: finiteNumber(
      candidate.surrogate_contribution_after,
      `${label}.surrogate_contribution_after`,
    ),
    temporal_step_index: integer(candidate.temporal_step_index, `${label}.temporal_step_index`),
    state_before: finiteNumbers(candidate.state_before, `${label}.state_before`, TRAJECTORY_AXES.length),
    state_after: finiteNumbers(candidate.state_after, `${label}.state_after`, TRAJECTORY_AXES.length),
    source_effect: finiteNumber(candidate.source_effect, `${label}.source_effect`),
  };
}

function trajectoryPoint(value: unknown, label: string): PublicTrajectoryPoint {
  const candidate = record(value, label);
  return {
    fingerprint_sha256: sha256(candidate.fingerprint_sha256, `${label}.fingerprint_sha256`),
    step_index: integer(candidate.step_index, `${label}.step_index`),
    evidence_id: string(candidate.evidence_id, `${label}.evidence_id`),
    is_correction_event: boolean(candidate.is_correction_event, `${label}.is_correction_event`),
    eligible_for_temporal_control: boolean(
      candidate.eligible_for_temporal_control,
      `${label}.eligible_for_temporal_control`,
    ),
    state: finiteNumbers(candidate.state, `${label}.state`, TRAJECTORY_AXES.length),
    full_admission_support_reference: finiteNumber(
      candidate.full_admission_support_reference,
      `${label}.full_admission_support_reference`,
      true,
    ),
    control_value: finiteNumber(candidate.control_value, `${label}.control_value`),
    temporal_gradient: finiteNumber(candidate.temporal_gradient, `${label}.temporal_gradient`),
  };
}

function booleanRecord(value: unknown, label: string): Record<string, boolean> {
  const candidate = record(value, label);
  return Object.fromEntries(
    Object.entries(candidate).map(([key, child]) => [key, boolean(child, `${label}.${key}`)]),
  );
}

function exactTrueChecks<const T extends readonly string[]>(
  value: unknown,
  expected: T,
  label: string,
): Record<T[number], boolean> {
  const checks = booleanRecord(value, label);
  const keys = Object.keys(checks);
  if (
    keys.length !== expected.length ||
    expected.some((key) => checks[key] !== true) ||
    keys.some((key) => !expected.includes(key as T[number]))
  ) {
    return fail(`${label} hard gate`);
  }
  return checks as Record<T[number], boolean>;
}

function reviewDepth(value: unknown, label: string): InspectionPlanStep["review_depth"] {
  if (value !== "LIGHT" && value !== "STANDARD" && value !== "DEEP") return fail(label);
  return value;
}

function inspectionPlanStep(value: unknown, label: string): InspectionPlanStep {
  const candidate = record(value, label);
  return {
    evidence_id: string(candidate.evidence_id, `${label}.evidence_id`),
    priority_rank: integer(candidate.priority_rank, `${label}.priority_rank`, 1),
    controller_allocation_fraction: finiteNumber(
      candidate.controller_allocation_fraction,
      `${label}.controller_allocation_fraction`,
      true,
    ),
    inspection_share: finiteNumber(candidate.inspection_share, `${label}.inspection_share`, true),
    allocation_delta: finiteNumber(candidate.allocation_delta, `${label}.allocation_delta`),
    relative_emphasis: finiteNumber(candidate.relative_emphasis, `${label}.relative_emphasis`, true),
    review_depth: reviewDepth(candidate.review_depth, `${label}.review_depth`),
    inspection_budget_units: integer(candidate.inspection_budget_units, `${label}.inspection_budget_units`, 1),
  };
}

function programOperation(value: unknown, label: string): RevisionProgramStep["operation"] {
  if (
    value !== "LOAD_EVENT" &&
    value !== "SUPPRESS" &&
    value !== "REINSPECT" &&
    value !== "PRESERVE" &&
    value !== "PREPARE_FULL_CONTEXT_REGENERATION"
  ) {
    return fail(label);
  }
  return value;
}

function revisionProgramStep(value: unknown, label: string): RevisionProgramStep {
  const candidate = record(value, label);
  const operation = programOperation(candidate.operation, `${label}.operation`);
  const step: RevisionProgramStep = {
    step_index: integer(candidate.step_index, `${label}.step_index`),
    operation,
  };
  if (operation !== "PREPARE_FULL_CONTEXT_REGENERATION") {
    step.evidence_id = string(candidate.evidence_id, `${label}.evidence_id`);
  }
  if (operation === "REINSPECT") {
    const plan = inspectionPlanStep(candidate, label);
    Object.assign(step, plan);
  }
  return step;
}

function executionTraceStep(value: unknown, label: string): ActuatorExecutionTraceStep {
  const candidate = record(value, label);
  const evidenceId = candidate.evidence_id;
  if (evidenceId !== null && typeof evidenceId !== "string") return fail(`${label}.evidence_id`);
  return {
    step_index: integer(candidate.step_index, `${label}.step_index`),
    operation: programOperation(candidate.operation, `${label}.operation`),
    state_before: string(candidate.state_before, `${label}.state_before`),
    state_after: string(candidate.state_after, `${label}.state_after`),
    evidence_id: evidenceId,
  };
}

function parseDemoRequest(value: unknown): LiveDemoRequestEnvelope {
  const candidate = record(value, "demo request");
  if (candidate.schema_version !== DEMO_REQUEST_SCHEMA) return fail("demo request schema_version");
  const request = record(candidate.request, "demo request.request");
  if (request.schema_version !== LIVE_REQUEST_SCHEMA) return fail("demo request.request.schema_version");
  string(request.request_id, "demo request.request.request_id");
  if (candidate.provenance !== "CONTAMINATED_REGRESSION_FIXTURE") return fail("demo request provenance");
  return {
    schema_version: DEMO_REQUEST_SCHEMA,
    provenance: "CONTAMINATED_REGRESSION_FIXTURE",
    source_artifact_fingerprint_sha256: sha256(
      candidate.source_artifact_fingerprint_sha256,
      "demo request.source_artifact_fingerprint_sha256",
    ),
    request_fingerprint_sha256: sha256(
      candidate.request_fingerprint_sha256,
      "demo request.request_fingerprint_sha256",
    ),
    fingerprint_sha256: sha256(candidate.fingerprint_sha256, "demo request.fingerprint_sha256"),
    request: request as LiveDemoRequestEnvelope["request"],
  };
}

function invalidationEdge(value: unknown, label: string) {
  const edge = record(value, label);
  return {
    source_evidence_id: string(edge.source_evidence_id, `${label}.source_evidence_id`),
    target_evidence_id: string(edge.target_evidence_id, `${label}.target_evidence_id`),
  };
}

function trajectoryRun(value: unknown, label: string) {
  const candidate = record(value, label);
  const loss = record(candidate.loss_components, `${label}.loss_components`);
  const lossKeys = ["terminal", "path", "control", "smoothness"];
  if (!sameCanonical(Object.keys(loss).sort(), [...lossKeys].sort())) return fail(`${label}.loss_components keys`);
  const points = array(candidate.points, `${label}.points`).map((row, index) =>
    trajectoryPoint(row, `${label}.points[${index}]`),
  );
  if (points.length === 0) return fail(`${label}.points empty`);
  return {
    fingerprint_sha256: sha256(candidate.fingerprint_sha256, `${label}.fingerprint_sha256`),
    objective: finiteNumber(candidate.objective, `${label}.objective`, true),
    loss_components: {
      terminal: finiteNumber(loss.terminal, `${label}.loss_components.terminal`, true),
      path: finiteNumber(loss.path, `${label}.loss_components.path`, true),
      control: finiteNumber(loss.control, `${label}.loss_components.control`, true),
      smoothness: finiteNumber(loss.smoothness, `${label}.loss_components.smoothness`, true),
    },
    terminal_state: finiteNumbers(candidate.terminal_state, `${label}.terminal_state`, TRAJECTORY_AXES.length),
    points,
  };
}

function publicTrajectory(value: unknown): PublicRevisionTrajectory {
  const label = "response.mechanism.public_trajectory";
  const candidate = record(value, label);
  if (
    candidate.schema_version !== PUBLIC_TRAJECTORY_SCHEMA ||
    candidate.state_kind !== "PUBLIC_HAND_BUILT_REVISION_SURROGATE"
  ) {
    return fail(`${label} schema`);
  }
  const axes = strings(candidate.axis_order, `${label}.axis_order`);
  if (!sameCanonical(axes, TRAJECTORY_AXES)) return fail(`${label}.axis_order`);
  const semantics = record(candidate.axis_semantics, `${label}.axis_semantics`);
  if (!sameCanonical(Object.keys(semantics).sort(), [...TRAJECTORY_AXES].sort())) {
    return fail(`${label}.axis_semantics keys`);
  }
  const neutral = trajectoryRun(candidate.neutral, `${label}.neutral`);
  const revised = trajectoryRun(candidate.revised, `${label}.revised`);
  const sham = record(candidate.matched_temporal_sham, `${label}.matched_temporal_sham`);
  const boundary = record(candidate.gradient_boundary, `${label}.gradient_boundary`);
  if (
    sham.construction !== "REVERSE_ACCEPTED_CONTROL_VALUES_OVER_ELIGIBLE_TIME_SITES" ||
    sham.claim_scope !== "PUBLIC_RECURRENCE_TEMPORAL_PLACEMENT_ONLY" ||
    sham.provider_calls !== 0 ||
    boundary.hosted_model_differentiated !== false ||
    boundary.private_reasoning_observed !== false
  ) {
    return fail(`${label} boundary`);
  }
  const parsed: PublicRevisionTrajectory = {
    fingerprint_sha256: sha256(candidate.fingerprint_sha256, `${label}.fingerprint_sha256`),
    state_kind: "PUBLIC_HAND_BUILT_REVISION_SURROGATE",
    axis_order: axes as PublicTrajectoryAxis[],
    axis_semantics: Object.fromEntries(
      TRAJECTORY_AXES.map((axis) => [axis, string(semantics[axis], `${label}.axis_semantics.${axis}`)]),
    ) as Record<PublicTrajectoryAxis, string>,
    terminal_target: finiteNumbers(candidate.terminal_target, `${label}.terminal_target`, TRAJECTORY_AXES.length),
    source_actual_before_state_fingerprint_sha256: sha256(
      candidate.source_actual_before_state_fingerprint_sha256,
      `${label}.source_actual_before_state_fingerprint_sha256`,
    ),
    source_credit_basis_fingerprint_sha256: sha256(
      candidate.source_credit_basis_fingerprint_sha256,
      `${label}.source_credit_basis_fingerprint_sha256`,
    ),
    correction_step_index: integer(candidate.correction_step_index, `${label}.correction_step_index`),
    neutral,
    revised,
    matched_temporal_sham: {
      construction: "REVERSE_ACCEPTED_CONTROL_VALUES_OVER_ELIGIBLE_TIME_SITES",
      objective: finiteNumber(sham.objective, `${label}.matched_temporal_sham.objective`, true),
      terminal_state: finiteNumbers(
        sham.terminal_state,
        `${label}.matched_temporal_sham.terminal_state`,
        TRAJECTORY_AXES.length,
      ),
      control_l2: finiteNumber(sham.control_l2, `${label}.matched_temporal_sham.control_l2`, true),
      provider_calls: 0,
      claim_scope: "PUBLIC_RECURRENCE_TEMPORAL_PLACEMENT_ONLY",
    },
    gradient_boundary: {
      starts_at: string(boundary.starts_at, `${label}.gradient_boundary.starts_at`),
      ends_at: string(boundary.ends_at, `${label}.gradient_boundary.ends_at`),
      hosted_model_differentiated: false,
      private_reasoning_observed: false,
    },
    checks: exactTrueChecks(candidate.checks, TRAJECTORY_CHECK_KEYS, `${label}.checks`),
  };
  return parsed;
}

function parseResponse(
  value: unknown,
  expectedEnvelope: LiveDemoRequestEnvelope,
  expectedInputFingerprint: string,
  transportBodySha256: string,
): LiveApplyRevisionResponse {
  const expectedRequest = record(expectedEnvelope.request, "expected request");
  const expectedRequestId = string(expectedRequest.request_id, "expected request.request_id");
  const candidate = record(value, "response");
  if (candidate.schema_version !== LIVE_RESPONSE_SCHEMA) return fail("response.schema_version");
  if (candidate.status !== "COMPLETE") return fail("response.status");
  if (candidate.mode !== "LIVE_AFTER_REGENERATION") return fail("response.mode");
  const requestId = string(candidate.request_id, "response.request_id");
  if (requestId !== expectedRequestId) return fail("response.request_id correlation");
  if (candidate.input_fingerprint_sha256 !== expectedInputFingerprint) {
    return fail("response.input_fingerprint_sha256 correlation");
  }
  if (candidate.case_id !== expectedRequest.case_id) return fail("response.case_id correlation");

  const context = record(candidate.context, "response.context");
  const contextEvidence = array(context.evidence, "response.context.evidence").map((row, index) =>
    evidence(row, `response.context.evidence[${index}]`),
  );
  const evidenceIds = contextEvidence.map((row) => row.evidence_id);
  if (new Set(evidenceIds).size !== evidenceIds.length) return fail("response.context.evidence duplicate IDs");
  const lateEvent = record(context.late_event, "response.context.late_event");
  const inputProvenance = string(context.input_provenance, "response.context.input_provenance");
  if (!["CALLER_SUPPLIED_UNVERIFIED", "CONTAMINATED_REGRESSION_FIXTURE"].includes(inputProvenance)) {
    return fail("response.context.input_provenance");
  }
  if (inputProvenance !== expectedEnvelope.provenance) {
    return fail("response.context.input_provenance correlation");
  }
  if (
    context.source_artifact_fingerprint_sha256 !==
    expectedEnvelope.source_artifact_fingerprint_sha256
  ) {
    return fail("response.context.source_artifact_fingerprint_sha256 correlation");
  }
  if (context.question !== expectedRequest.question) return fail("response.context.question correlation");
  if (!sameCanonical(context.before_horizon_evidence_ids, expectedRequest.before_horizon_evidence_ids)) {
    return fail("response.context.before_horizon_evidence_ids correlation");
  }
  const expectedEvidence = array(expectedRequest.all_raw_evidence, "expected request.all_raw_evidence").map(
    (row, index) => {
      const item = record(row, `expected request.all_raw_evidence[${index}]`);
      return {
        evidence_id: string(item.evidence_id, `expected request.all_raw_evidence[${index}].evidence_id`),
        text: string(item.text, `expected request.all_raw_evidence[${index}].text`),
      };
    },
  );
  if (
    !sameCanonical(
      contextEvidence.map(({ evidence_id, text }) => ({ evidence_id, text })),
      expectedEvidence,
    )
  ) {
    return fail("response.context.evidence correlation");
  }
  const expectedEvent = record(expectedRequest.event, "expected request.event");
  if (
    lateEvent.event_id !== expectedEvent.event_id ||
    lateEvent.evidence_id !== expectedEvent.correction_evidence_id ||
    !sameCanonical(lateEvent.invalidated_evidence_ids, expectedEvent.invalidated_evidence_ids) ||
    !sameCanonical(lateEvent.stable_evidence_ids, expectedEvent.stable_evidence_ids)
  ) {
    return fail("response.context.late_event correlation");
  }

  const mechanism = record(candidate.mechanism, "response.mechanism");
  const actualBefore = record(mechanism.actual_before_state, "response.mechanism.actual_before_state");
  const surrogate = record(mechanism.surrogate, "response.mechanism.surrogate");
  const trajectory = publicTrajectory(mechanism.public_trajectory);
  const control = record(mechanism.public_control_map, "response.mechanism.public_control_map");
  const actuator = record(mechanism.compiled_actuator, "response.mechanism.compiled_actuator");
  const actuatorExecution = record(mechanism.actuator_execution, "response.mechanism.actuator_execution");
  const inspectionPlan = record(actuator.inspection_plan, "response.mechanism.compiled_actuator.inspection_plan");
  const revisionProgram = record(actuator.program, "response.mechanism.compiled_actuator.program");
  const dependency = record(candidate.public_dependency_audit, "response.public_dependency_audit");

  const output = record(candidate.output, "response.output");
  const before = record(output.before, "response.output.before");
  const after = record(output.after, "response.output.after");
  const diff = record(output.diff, "response.output.diff");
  const diffAnswer = record(diff.answer, "response.output.diff.answer");
  const diffClosure = record(diff.selected_closure_id, "response.output.diff.selected_closure_id");
  if (!sameCanonical(before.public_output, expectedRequest.prior_public_state)) {
    return fail("response.output.before.public_output correlation");
  }

  const verification = record(candidate.verification, "response.verification");
  const providerAttempts = finiteNumber(verification.provider_attempts, "response.verification.provider_attempts", true);
  if (providerAttempts !== 1) return fail("response.verification.provider_attempts");
  if (verification.semantic_correctness_status !== "NOT_ASSESSED") {
    return fail("response.verification.semantic_correctness_status");
  }
  if (verification.effect_attribution_status !== "NOT_ASSESSED") {
    return fail("response.verification.effect_attribution_status");
  }

  const mechanismStatus = binaryStatus(mechanism.status, "response.mechanism.status");
  const controlChecks = exactTrueChecks(
    control.checks,
    CONTROL_CHECK_KEYS,
    "response.mechanism.public_control_map.checks",
  );
  const actuatorChecks = exactTrueChecks(
    actuator.checks,
    ACTUATOR_CHECK_KEYS,
    "response.mechanism.compiled_actuator.checks",
  );
  const executionChecks = exactTrueChecks(
    actuatorExecution.checks,
    EXECUTION_CHECK_KEYS,
    "response.mechanism.actuator_execution.checks",
  );
  const dependencyChecks = exactTrueChecks(
    dependency.checks,
    DEPENDENCY_CHECK_KEYS,
    "response.public_dependency_audit.checks",
  );
  if (mechanismStatus !== "PASS") return fail("response.mechanism.status hard gate");

  const actualBeforeFingerprint = sha256(
    actualBefore.fingerprint_sha256,
    "response.mechanism.actual_before_state.fingerprint_sha256",
  );
  const actualBeforeAxisOrder = strings(
    actualBefore.axis_order,
    "response.mechanism.actual_before_state.axis_order",
  );
  const actualBeforeInitialVector = finiteNumbers(
    actualBefore.initial_vector,
    "response.mechanism.actual_before_state.initial_vector",
    TRAJECTORY_AXES.length,
  );
  if (
    !sameCanonical(actualBeforeAxisOrder, TRAJECTORY_AXES) ||
    trajectory.source_actual_before_state_fingerprint_sha256 !== actualBeforeFingerprint ||
    !sameCanonical(trajectory.axis_order, actualBeforeAxisOrder) ||
    !approximatelyEqual(trajectory.terminal_target[2], actualBeforeInitialVector[2])
  ) {
    return fail("response.mechanism public trajectory initial-state binding");
  }

  const verificationRows = array(verification.rows, "response.verification.rows").map((row, index) => {
    const item = record(row, `response.verification.rows[${index}]`);
    return {
      label: string(item.label, `response.verification.rows[${index}].label`),
      detail: string(item.detail, `response.verification.rows[${index}].detail`),
      status: status(item.status, `response.verification.rows[${index}].status`),
    };
  });
  const rowLabels = verificationRows.map((row) => row.label);
  if (new Set(rowLabels).size !== rowLabels.length) return fail("response.verification.rows duplicate labels");
  const semanticRows = verificationRows.filter((row) => row.label === "Semantic correctness");
  const effectRows = verificationRows.filter((row) => row.label === "Effect attribution");
  if (
    semanticRows.length !== 1 ||
    semanticRows[0].status !== "NOT_ASSESSED" ||
    semanticRows[0].detail !== SEMANTIC_ROW_DETAIL
  ) {
    return fail("response.verification.rows semantic correctness boundary");
  }
  if (
    effectRows.length !== 1 ||
    effectRows[0].status !== "NOT_ASSESSED" ||
    effectRows[0].detail !== EFFECT_ROW_DETAIL
  ) {
    return fail("response.verification.rows effect attribution boundary");
  }
  const operationalRows = verificationRows.filter(
    (row) => row.label !== "Semantic correctness" && row.label !== "Effect attribution",
  );
  const operationalKeys = Object.keys(OPERATIONAL_ROW_LABELS);
  if (
    operationalRows.length !== operationalKeys.length ||
    operationalRows.some(
      (row) =>
        row.status === "NOT_ASSESSED" ||
        OPERATIONAL_ROW_LABELS[row.detail] !== row.label,
    ) ||
    new Set(operationalRows.map((row) => row.detail)).size !== operationalKeys.length ||
    operationalKeys.some((key) => !operationalRows.some((row) => row.detail === key))
  ) {
    return fail("response.verification.rows operational coverage");
  }
  const auditPassed = operationalRows.every((row) => row.status === "PASS");
  const operationalStatus = binaryStatus(
    verification.operational_acceptance_status,
    "response.verification.operational_acceptance_status",
  );
  const providerSchemaStatus = binaryStatus(
    verification.provider_output_schema_status,
    "response.verification.provider_output_schema_status",
  );
  const lineageStatus = binaryStatus(
    verification.lineage_binding_status,
    "response.verification.lineage_binding_status",
  );
  const actuatorExecutionStatus = binaryStatus(
    verification.public_actuator_execution_status,
    "response.verification.public_actuator_execution_status",
  );
  const providerDeliveryStatus = binaryStatus(
    verification.provider_delivery_status,
    "response.verification.provider_delivery_status",
  );
  if (verification.provider_uptake_status !== "NOT_ASSESSED") {
    return fail("response.verification.provider_uptake_status");
  }
  const structuralDependencyStatus = binaryStatus(
    verification.structural_dependency_status,
    "response.verification.structural_dependency_status",
  );
  if (verification.counterfactual_output_effect_status !== "NOT_ASSESSED") {
    return fail("response.verification.counterfactual_output_effect_status");
  }
  if (providerSchemaStatus !== "PASS") return fail("response.verification.provider_output_schema_status hard gate");
  if (
    operationalRows.find((row) => row.detail === "provider_output_schema_valid")?.status !==
    providerSchemaStatus
  ) {
    return fail("response.verification.provider_output_schema_status consistency");
  }
  if (lineageStatus !== (auditPassed ? "PASS" : "FAIL")) {
    return fail("response.verification.lineage_binding_status consistency");
  }
  const expectedOperationalStatus =
    mechanismStatus === "PASS" && providerSchemaStatus === "PASS" && lineageStatus === "PASS"
      ? "PASS"
      : "FAIL";
  if (operationalStatus !== expectedOperationalStatus) {
    return fail("response.verification.operational_acceptance_status consistency");
  }

  const surrogateObjectiveBefore = finiteNumber(
    surrogate.objective_before,
    "response.mechanism.surrogate.objective_before",
    true,
  );
  const surrogateObjectiveAfter = finiteNumber(
    surrogate.objective_after,
    "response.mechanism.surrogate.objective_after",
    true,
  );
  const surrogateTerminalBefore = finiteNumber(
    surrogate.surrogate_terminal_state_before,
    "response.mechanism.surrogate.surrogate_terminal_state_before",
  );
  const surrogateTerminalAfter = finiteNumber(
    surrogate.surrogate_terminal_state_after,
    "response.mechanism.surrogate.surrogate_terminal_state_after",
  );
  const correctionEvidenceId = string(lateEvent.evidence_id, "response.context.late_event.evidence_id");
  const correctionStepIndex = evidenceIds.indexOf(correctionEvidenceId);
  const neutralPoints = trajectory.neutral.points;
  const revisedPoints = trajectory.revised.points;
  const revisedControlL2 = Math.hypot(...revisedPoints.map((row) => row.control_value));
  const decisionMean = (values: number[]) => (values[0] + values[1]) / 2;
  if (
    correctionStepIndex < 0 ||
    trajectory.correction_step_index !== correctionStepIndex ||
    neutralPoints.length !== evidenceIds.length ||
    revisedPoints.length !== evidenceIds.length ||
    trajectory.revised.objective >= trajectory.neutral.objective ||
    trajectory.revised.objective >= trajectory.matched_temporal_sham.objective ||
    !approximatelyEqual(trajectory.neutral.objective, surrogateObjectiveBefore) ||
    !approximatelyEqual(trajectory.revised.objective, surrogateObjectiveAfter) ||
    !approximatelyEqual(decisionMean(trajectory.neutral.terminal_state), surrogateTerminalBefore) ||
    !approximatelyEqual(decisionMean(trajectory.revised.terminal_state), surrogateTerminalAfter) ||
    !approximatelyEqual(revisedControlL2, trajectory.matched_temporal_sham.control_l2) ||
    !sameCanonical(trajectory.neutral.terminal_state, neutralPoints.at(-1)?.state) ||
    !sameCanonical(trajectory.revised.terminal_state, revisedPoints.at(-1)?.state) ||
    neutralPoints.some((row, index) => {
      const revised = revisedPoints[index];
      return (
        row.step_index !== index ||
        revised.step_index !== index ||
        row.evidence_id !== evidenceIds[index] ||
        revised.evidence_id !== evidenceIds[index] ||
        row.is_correction_event !== (index === correctionStepIndex) ||
        revised.is_correction_event !== row.is_correction_event ||
        revised.eligible_for_temporal_control !== row.eligible_for_temporal_control ||
        row.full_admission_support_reference > 1 + ALLOCATION_TOLERANCE ||
        !approximatelyEqual(
          revised.full_admission_support_reference,
          row.full_admission_support_reference,
        ) ||
        !approximatelyEqual(row.control_value, 0) ||
        (!revised.eligible_for_temporal_control && !approximatelyEqual(revised.control_value, 0)) ||
        !approximatelyEqual(row.temporal_gradient, revised.temporal_gradient) ||
        !approximatelyEqual(row.state[2], actualBeforeInitialVector[2]) ||
        !approximatelyEqual(revised.state[2], actualBeforeInitialVector[2])
      );
    })
  ) {
    return fail("response.mechanism.public_trajectory cross-binding");
  }

  const creditRows = array(control.credit_rows, "response.mechanism.public_control_map.credit_rows").map(
    (row, index) => creditRow(row, `response.mechanism.public_control_map.credit_rows[${index}]`),
  );
  if (!sameCanonical(creditRows.map((row) => row.evidence_id), evidenceIds)) {
    return fail("response.mechanism.public_control_map.credit_rows evidence order");
  }
  const controlL2 = finiteNumber(control.control_l2, "response.mechanism.public_control_map.control_l2", true);
  const maxControlL2 = finiteNumber(
    control.max_control_l2,
    "response.mechanism.public_control_map.max_control_l2",
    true,
  );
  if (
    !approximatelyEqual(controlL2, revisedControlL2) ||
    controlL2 > maxControlL2 + ALLOCATION_TOLERANCE ||
    !approximatelyEqual(
      creditRows.reduce((sum, row) => sum + row.optimized_allocation_fraction, 0),
      1,
    ) ||
    creditRows.some(
      (row) =>
        row.temporal_step_index !== evidenceIds.indexOf(row.evidence_id) ||
        !sameCanonical(row.state_before, neutralPoints[row.temporal_step_index]?.state) ||
        !sameCanonical(row.state_after, revisedPoints[row.temporal_step_index]?.state) ||
        !approximatelyEqual(row.control_value, revisedPoints[row.temporal_step_index]?.control_value ?? Number.NaN) ||
        !approximatelyEqual(row.gradient, revisedPoints[row.temporal_step_index]?.temporal_gradient ?? Number.NaN) ||
        row.eligible_for_reinspection !== revisedPoints[row.temporal_step_index]?.eligible_for_temporal_control ||
        !approximatelyEqual(
          row.optimized_allocation_fraction - row.baseline_allocation_fraction,
          row.allocation_delta,
        ) ||
        (!row.eligible_for_reinspection && !approximatelyEqual(row.optimized_allocation_fraction, 0)),
    )
  ) {
    return fail("response.mechanism.public_control_map continuous allocation");
  }
  const allocationDomainEvidenceIds = strings(
    control.allocation_domain_evidence_ids,
    "response.mechanism.public_control_map.allocation_domain_evidence_ids",
  );
  if (
    !sameCanonical(
      allocationDomainEvidenceIds,
      creditRows.filter((row) => row.eligible_for_reinspection).map((row) => row.evidence_id),
    )
  ) {
    return fail("response.mechanism.public_control_map allocation domain");
  }

  if (inspectionPlan.schema_version !== INSPECTION_PLAN_SCHEMA) {
    return fail("response.mechanism.compiled_actuator.inspection_plan.schema_version");
  }
  if (inspectionPlan.allocation_scope !== "SELECTED_PUBLIC_REINSPECTION_STEPS") {
    return fail("response.mechanism.compiled_actuator.inspection_plan.allocation_scope");
  }
  if (inspectionPlan.budget_unit_semantics !== "ABSTRACT_PUBLIC_REVIEW_ALLOCATION_NOT_PROVIDER_TOKENS") {
    return fail("response.mechanism.compiled_actuator.inspection_plan.budget_unit_semantics");
  }
  const inspectionPlanFingerprint = sha256(
    inspectionPlan.fingerprint_sha256,
    "response.mechanism.compiled_actuator.inspection_plan.fingerprint_sha256",
  );
  const inspectionPlanSourceTrajectoryFingerprint = sha256(
    inspectionPlan.source_public_trajectory_fingerprint_sha256,
    "response.mechanism.compiled_actuator.inspection_plan.source_public_trajectory_fingerprint_sha256",
  );
  const totalBudgetUnits = integer(
    inspectionPlan.total_budget_units,
    "response.mechanism.compiled_actuator.inspection_plan.total_budget_units",
    1,
  );
  const inspectionSteps = array(
    inspectionPlan.steps,
    "response.mechanism.compiled_actuator.inspection_plan.steps",
  ).map((row, index) =>
    inspectionPlanStep(row, `response.mechanism.compiled_actuator.inspection_plan.steps[${index}]`),
  );
  const expectedReinspectionCount = integer(expectedRequest.reinspection_count, "expected request.reinspection_count", 1);
  const reinspectEvidenceIds = strings(
    actuator.reinspect_evidence_ids,
    "response.mechanism.compiled_actuator.reinspect_evidence_ids",
  );
  const suppressEvidenceIds = strings(
    actuator.suppress_evidence_ids,
    "response.mechanism.compiled_actuator.suppress_evidence_ids",
  );
  const preserveEvidenceIds = strings(
    actuator.preserve_evidence_ids,
    "response.mechanism.compiled_actuator.preserve_evidence_ids",
  );
  const creditById = new Map(creditRows.map((row) => [row.evidence_id, row]));
  const selectedControllerTotal = inspectionSteps.reduce(
    (sum, row) => sum + row.controller_allocation_fraction,
    0,
  );
  if (
    inspectionSteps.length !== expectedReinspectionCount ||
    new Set(inspectionSteps.map((row) => row.evidence_id)).size !== inspectionSteps.length ||
    !sameCanonical(inspectionSteps.map((row) => row.evidence_id), reinspectEvidenceIds) ||
    !approximatelyEqual(inspectionSteps.reduce((sum, row) => sum + row.inspection_share, 0), 1) ||
    inspectionSteps.reduce((sum, row) => sum + row.inspection_budget_units, 0) !== totalBudgetUnits ||
    inspectionSteps.some((row, index) => {
      const credit = creditById.get(row.evidence_id);
      const expectedDepth =
        row.relative_emphasis >= 1.25 ? "DEEP" : row.relative_emphasis >= 0.75 ? "STANDARD" : "LIGHT";
      return (
        row.priority_rank !== index + 1 ||
        !credit?.eligible_for_reinspection ||
        !approximatelyEqual(row.controller_allocation_fraction, credit.optimized_allocation_fraction) ||
        !approximatelyEqual(row.allocation_delta, credit.allocation_delta) ||
        !approximatelyEqual(row.inspection_share, row.controller_allocation_fraction / selectedControllerTotal) ||
        !approximatelyEqual(row.relative_emphasis, row.inspection_share * inspectionSteps.length) ||
        row.review_depth !== expectedDepth
      );
    })
  ) {
    return fail("response.mechanism.compiled_actuator.inspection_plan cross-binding");
  }

  if (revisionProgram.schema_version !== REVISION_PROGRAM_SCHEMA || revisionProgram.state !== "COMPILED") {
    return fail("response.mechanism.compiled_actuator.program contract");
  }
  const controlFingerprint = sha256(control.fingerprint_sha256, "response.mechanism.public_control_map.fingerprint_sha256");
  const actuatorFingerprint = sha256(
    actuator.fingerprint_sha256,
    "response.mechanism.compiled_actuator.fingerprint_sha256",
  );
  const programFingerprint = sha256(
    revisionProgram.fingerprint_sha256,
    "response.mechanism.compiled_actuator.program.fingerprint_sha256",
  );
  const actuatorSourceControlFingerprint = sha256(
    actuator.source_control_map_fingerprint_sha256,
    "response.mechanism.compiled_actuator.source_control_map_fingerprint_sha256",
  );
  const programSourceControlFingerprint = sha256(
    revisionProgram.source_control_map_fingerprint_sha256,
    "response.mechanism.compiled_actuator.program.source_control_map_fingerprint_sha256",
  );
  const actuatorSourceTrajectoryFingerprint = sha256(
    actuator.source_public_trajectory_fingerprint_sha256,
    "response.mechanism.compiled_actuator.source_public_trajectory_fingerprint_sha256",
  );
  const programSourceTrajectoryFingerprint = sha256(
    revisionProgram.source_public_trajectory_fingerprint_sha256,
    "response.mechanism.compiled_actuator.program.source_public_trajectory_fingerprint_sha256",
  );
  if (
    actuatorSourceControlFingerprint !== controlFingerprint ||
    programSourceControlFingerprint !== controlFingerprint ||
    actuatorSourceTrajectoryFingerprint !== trajectory.fingerprint_sha256 ||
    programSourceTrajectoryFingerprint !== trajectory.fingerprint_sha256 ||
    inspectionPlanSourceTrajectoryFingerprint !== trajectory.fingerprint_sha256
  ) {
    return fail("response.mechanism.compiled_actuator source control binding");
  }
  const programSteps = array(
    revisionProgram.steps,
    "response.mechanism.compiled_actuator.program.steps",
  ).map((row, index) =>
    revisionProgramStep(row, `response.mechanism.compiled_actuator.program.steps[${index}]`),
  );
  const expectedOperations: RevisionProgramStep["operation"][] = [
    "LOAD_EVENT",
    ...suppressEvidenceIds.map(() => "SUPPRESS" as const),
    ...inspectionSteps.map(() => "REINSPECT" as const),
    ...preserveEvidenceIds.map(() => "PRESERVE" as const),
    "PREPARE_FULL_CONTEXT_REGENERATION",
  ];
  if (
    programSteps.length !== expectedOperations.length ||
    programSteps.some((row, index) => row.step_index !== index || row.operation !== expectedOperations[index]) ||
    programSteps[0]?.evidence_id !== lateEvent.evidence_id ||
    !sameCanonical(
      programSteps.filter((row) => row.operation === "SUPPRESS").map((row) => row.evidence_id),
      suppressEvidenceIds,
    ) ||
    !sameCanonical(
      programSteps.filter((row) => row.operation === "PRESERVE").map((row) => row.evidence_id),
      preserveEvidenceIds,
    ) ||
    !sameCanonical(
      programSteps
        .filter((row) => row.operation === "REINSPECT")
        .map(({ step_index: _stepIndex, operation: _operation, ...row }) => row),
      inspectionSteps,
    )
  ) {
    return fail("response.mechanism.compiled_actuator.program materialization");
  }

  if (
    actuatorExecution.status !== "COMPLETED" ||
    actuatorExecution.final_state !== "READY_FOR_PROVIDER" ||
    actuatorExecution.provider_payload_receipt_binding_status !== "PASS"
  ) {
    return fail("response.mechanism.actuator_execution terminal state");
  }
  const executionFingerprint = sha256(
    actuatorExecution.fingerprint_sha256,
    "response.mechanism.actuator_execution.fingerprint_sha256",
  );
  const executionSourceActuatorFingerprint = sha256(
    actuatorExecution.source_actuator_fingerprint_sha256,
    "response.mechanism.actuator_execution.source_actuator_fingerprint_sha256",
  );
  const executionSourceProgramFingerprint = sha256(
    actuatorExecution.source_program_fingerprint_sha256,
    "response.mechanism.actuator_execution.source_program_fingerprint_sha256",
  );
  const executionSourceTrajectoryFingerprint = sha256(
    actuatorExecution.source_public_trajectory_fingerprint_sha256,
    "response.mechanism.actuator_execution.source_public_trajectory_fingerprint_sha256",
  );
  if (
    executionSourceActuatorFingerprint !== actuatorFingerprint ||
    executionSourceProgramFingerprint !== programFingerprint ||
    executionSourceTrajectoryFingerprint !== trajectory.fingerprint_sha256
  ) {
    return fail("response.mechanism.actuator_execution source binding");
  }
  const executionTrace = array(
    actuatorExecution.trace,
    "response.mechanism.actuator_execution.trace",
  ).map((row, index) => executionTraceStep(row, `response.mechanism.actuator_execution.trace[${index}]`));
  if (
    executionTrace.length !== programSteps.length ||
    executionTrace.some((row, index) => {
      const source = programSteps[index];
      return (
        row.step_index !== index ||
        row.operation !== source.operation ||
        row.evidence_id !== (source.evidence_id ?? null) ||
        (index > 0 && row.state_before !== executionTrace[index - 1].state_after)
      );
    }) ||
    executionTrace[0]?.state_before !== "INITIALIZED" ||
    executionTrace.at(-1)?.state_after !== "READY_FOR_PROVIDER"
  ) {
    return fail("response.mechanism.actuator_execution trace binding");
  }
  const emittedProviderOperationFingerprint = sha256(
    actuatorExecution.emitted_provider_operation_fingerprint_sha256,
    "response.mechanism.actuator_execution.emitted_provider_operation_fingerprint_sha256",
  );
  const providerPayloadFingerprint = sha256(
    actuatorExecution.provider_payload_fingerprint_sha256,
    "response.mechanism.actuator_execution.provider_payload_fingerprint_sha256",
  );
  if (actuatorExecutionStatus !== "PASS" || providerDeliveryStatus !== "PASS") {
    return fail("response.verification actuator delivery hard gate");
  }

  if (
    dependency.schema_version !== DEPENDENCY_AUDIT_SCHEMA ||
    dependency.mode !== "PUBLIC_GRAPH_BLOCK_RESTORE" ||
    dependency.scope !== "SELECTED_CALLER_SUPPLIED_PUBLIC_GRAPH_ONLY" ||
    dependency.blocked_evidence_id !== lateEvent.evidence_id ||
    dependency.provider_calls !== 0 ||
    dependency.hosted_output_regenerated !== false ||
    dependency.hosted_causality_status !== "NOT_ASSESSED" ||
    dependency.counterfactual_output_effect_status !== "NOT_ASSESSED"
  ) {
    return fail("response.public_dependency_audit boundary");
  }
  const dependencyStatus = binaryStatus(
    dependency.structural_dependency_status,
    "response.public_dependency_audit.structural_dependency_status",
  );
  const dependencyFingerprint = sha256(dependency.fingerprint_sha256, "response.public_dependency_audit.fingerprint_sha256");
  const baselineClosureFingerprint = sha256(
    dependency.baseline_closure_fingerprint_sha256,
    "response.public_dependency_audit.baseline_closure_fingerprint_sha256",
  );
  const blockedClosureFingerprint = sha256(
    dependency.blocked_closure_fingerprint_sha256,
    "response.public_dependency_audit.blocked_closure_fingerprint_sha256",
  );
  const unblockedClosureFingerprint = sha256(
    dependency.unblocked_closure_fingerprint_sha256,
    "response.public_dependency_audit.unblocked_closure_fingerprint_sha256",
  );
  const dependencyMaskTrace = array(
    dependency.mask_trace,
    "response.public_dependency_audit.mask_trace",
  ).map((row, index) => {
    const item = record(row, `response.public_dependency_audit.mask_trace[${index}]`);
    const phase = item.phase;
    if (phase !== "BLOCK" && phase !== "UNBLOCK_AND_RECOMPUTE") {
      return fail(`response.public_dependency_audit.mask_trace[${index}].phase`);
    }
    return {
      phase: phase as "BLOCK" | "UNBLOCK_AND_RECOMPUTE",
      blocked_evidence_ids: strings(
        item.blocked_evidence_ids,
        `response.public_dependency_audit.mask_trace[${index}].blocked_evidence_ids`,
      ),
      closure_fingerprint_sha256: sha256(
        item.closure_fingerprint_sha256,
        `response.public_dependency_audit.mask_trace[${index}].closure_fingerprint_sha256`,
      ),
    };
  });
  const afterPublicOutput = publicOutput(after.public_output, "response.output.after.public_output");
  const afterTypeByTarget = new Map(afterPublicOutput.target_values.map((row) => [row.target_id, row.target_type]));
  const changedFactTargetIds = array(diff.target_values, "response.output.diff.target_values")
    .map((row, index) => {
      const item = record(row, `response.output.diff.target_values[${index}]`);
      return boolean(item.changed, `response.output.diff.target_values[${index}].changed`)
        ? string(item.target_id, `response.output.diff.target_values[${index}].target_id`)
        : null;
    })
    .filter((targetId): targetId is string => targetId !== null && afterTypeByTarget.get(targetId) === "fact");
  const dependencyTargetRows = array(
    dependency.changed_fact_targets,
    "response.public_dependency_audit.changed_fact_targets",
  ).map((row, index) => {
    const item = record(row, `response.public_dependency_audit.changed_fact_targets[${index}]`);
    return {
      target_id: string(item.target_id, `response.public_dependency_audit.changed_fact_targets[${index}].target_id`),
      baseline_contains_correction: boolean(
        item.baseline_contains_correction,
        `response.public_dependency_audit.changed_fact_targets[${index}].baseline_contains_correction`,
      ),
      blocked_contains_correction: boolean(
        item.blocked_contains_correction,
        `response.public_dependency_audit.changed_fact_targets[${index}].blocked_contains_correction`,
      ),
      blocked_lineage_changed: boolean(
        item.blocked_lineage_changed,
        `response.public_dependency_audit.changed_fact_targets[${index}].blocked_lineage_changed`,
      ),
      blocked_lineage_evidence_ids: strings(
        item.blocked_lineage_evidence_ids,
        `response.public_dependency_audit.changed_fact_targets[${index}].blocked_lineage_evidence_ids`,
      ),
      unblocked_lineage_exact: boolean(
        item.unblocked_lineage_exact,
        `response.public_dependency_audit.changed_fact_targets[${index}].unblocked_lineage_exact`,
      ),
    };
  });
  const dependencyStableTargetIds = strings(
    dependency.stable_target_ids,
    "response.public_dependency_audit.stable_target_ids",
  );
  const diffStableTargetIds = strings(diff.stable_target_ids, "response.output.diff.stable_target_ids");
  if (
    dependencyStatus !== "PASS" ||
    structuralDependencyStatus !== dependencyStatus ||
    baselineClosureFingerprint !== unblockedClosureFingerprint ||
    baselineClosureFingerprint === blockedClosureFingerprint ||
    dependencyMaskTrace.length !== 2 ||
    dependencyMaskTrace[0].phase !== "BLOCK" ||
    !sameCanonical(
      dependencyMaskTrace[0].blocked_evidence_ids,
      [string(lateEvent.evidence_id, "response.context.late_event.evidence_id")],
    ) ||
    dependencyMaskTrace[0].closure_fingerprint_sha256 !== blockedClosureFingerprint ||
    dependencyMaskTrace[1].phase !== "UNBLOCK_AND_RECOMPUTE" ||
    dependencyMaskTrace[1].blocked_evidence_ids.length !== 0 ||
    dependencyMaskTrace[1].closure_fingerprint_sha256 !== unblockedClosureFingerprint ||
    !sameCanonical(dependencyTargetRows.map((row) => row.target_id), changedFactTargetIds) ||
    dependencyTargetRows.some(
      (row) =>
        !row.baseline_contains_correction ||
        row.blocked_contains_correction ||
        !row.blocked_lineage_changed ||
        !row.unblocked_lineage_exact ||
        row.blocked_lineage_evidence_ids.includes(
          string(lateEvent.evidence_id, "response.context.late_event.evidence_id"),
        ) ||
        row.blocked_lineage_evidence_ids.some((id) => !evidenceIds.includes(id)),
    ) ||
    dependencyStableTargetIds.some((targetId) => !diffStableTargetIds.includes(targetId))
  ) {
    return fail("response.public_dependency_audit structural binding");
  }

  const accounting = record(candidate.accounting, "response.accounting");

  return {
    schema_version: LIVE_RESPONSE_SCHEMA,
    transport_body_sha256: transportBodySha256,
    request_id: requestId,
    status: "COMPLETE",
    mode: "LIVE_AFTER_REGENERATION",
    case_id: string(candidate.case_id, "response.case_id"),
    input_fingerprint_sha256: sha256(candidate.input_fingerprint_sha256, "response.input_fingerprint_sha256"),
    context: {
      question: string(context.question, "response.context.question"),
      model: string(context.model, "response.context.model"),
      input_provenance: inputProvenance as LiveApplyRevisionResponse["context"]["input_provenance"],
      source_artifact_fingerprint_sha256:
        context.source_artifact_fingerprint_sha256 === null
          ? null
          : sha256(
              context.source_artifact_fingerprint_sha256,
              "response.context.source_artifact_fingerprint_sha256",
            ),
      evidence: contextEvidence,
      before_horizon_evidence_ids: strings(
        context.before_horizon_evidence_ids,
        "response.context.before_horizon_evidence_ids",
      ),
      late_event: {
        evidence_id: string(lateEvent.evidence_id, "response.context.late_event.evidence_id"),
        event_id: string(lateEvent.event_id, "response.context.late_event.event_id"),
        text: string(lateEvent.text, "response.context.late_event.text"),
        invalidated_evidence_ids: strings(
          lateEvent.invalidated_evidence_ids,
          "response.context.late_event.invalidated_evidence_ids",
        ),
        stable_evidence_ids: strings(
          lateEvent.stable_evidence_ids,
          "response.context.late_event.stable_evidence_ids",
        ),
      },
    },
    mechanism: {
      status: mechanismStatus,
      actual_before_state: {
        fingerprint_sha256: actualBeforeFingerprint,
        source_selected_closure_id: string(
          actualBefore.source_selected_closure_id,
          "response.mechanism.actual_before_state.source_selected_closure_id",
        ),
        initial_scalar: finiteNumber(actualBefore.initial_scalar, "response.mechanism.actual_before_state.initial_scalar"),
        initial_vector: actualBeforeInitialVector,
        axis_order: actualBeforeAxisOrder as PublicTrajectoryAxis[],
        active_support_evidence_ids: strings(
          actualBefore.active_support_evidence_ids,
          "response.mechanism.actual_before_state.active_support_evidence_ids",
        ),
      },
      surrogate: {
        objective_before: surrogateObjectiveBefore,
        objective_after: surrogateObjectiveAfter,
        terminal_target: finiteNumber(surrogate.terminal_target, "response.mechanism.surrogate.terminal_target"),
        dtype: string(surrogate.dtype, "response.mechanism.surrogate.dtype"),
        backward_calls: finiteNumber(surrogate.backward_calls, "response.mechanism.surrogate.backward_calls", true),
        maximum_finite_difference_error: finiteNumber(
          surrogate.maximum_finite_difference_error,
          "response.mechanism.surrogate.maximum_finite_difference_error",
          true,
        ),
        inspection_temperature: finiteNumber(
          surrogate.inspection_temperature,
          "response.mechanism.surrogate.inspection_temperature",
          true,
        ),
        surrogate_terminal_state_before: surrogateTerminalBefore,
        surrogate_terminal_state_after: surrogateTerminalAfter,
      },
      public_trajectory: trajectory,
      public_control_map: {
        fingerprint_sha256: controlFingerprint,
        control_l2: controlL2,
        max_control_l2: maxControlL2,
        credit_rows: creditRows,
        allocation_domain_evidence_ids: allocationDomainEvidenceIds,
        checks: controlChecks,
      },
      compiled_actuator: {
        fingerprint_sha256: actuatorFingerprint,
        reinspect_evidence_ids: reinspectEvidenceIds,
        reinspect_source: string(
          actuator.reinspect_source,
          "response.mechanism.compiled_actuator.reinspect_source",
        ),
        suppress_evidence_ids: suppressEvidenceIds,
        suppress_source: string(
          actuator.suppress_source,
          "response.mechanism.compiled_actuator.suppress_source",
        ),
        preserve_evidence_ids: preserveEvidenceIds,
        preserve_source: string(
          actuator.preserve_source,
          "response.mechanism.compiled_actuator.preserve_source",
        ),
        correction_evidence_id: string(
          actuator.correction_evidence_id,
          "response.mechanism.compiled_actuator.correction_evidence_id",
        ),
        source_control_map_fingerprint_sha256: actuatorSourceControlFingerprint,
        source_public_trajectory_fingerprint_sha256: actuatorSourceTrajectoryFingerprint,
        inspection_plan: {
          fingerprint_sha256: inspectionPlanFingerprint,
          allocation_scope: "SELECTED_PUBLIC_REINSPECTION_STEPS",
          total_budget_units: totalBudgetUnits,
          budget_unit_semantics: "ABSTRACT_PUBLIC_REVIEW_ALLOCATION_NOT_PROVIDER_TOKENS",
          source_public_trajectory_fingerprint_sha256: inspectionPlanSourceTrajectoryFingerprint,
          steps: inspectionSteps,
        },
        program: {
          fingerprint_sha256: programFingerprint,
          state: "COMPILED",
          source_control_map_fingerprint_sha256: programSourceControlFingerprint,
          source_public_trajectory_fingerprint_sha256: programSourceTrajectoryFingerprint,
          steps: programSteps,
        },
        checks: actuatorChecks,
        gradient_stops_here: boolean(
          actuator.gradient_stops_here,
          "response.mechanism.compiled_actuator.gradient_stops_here",
        ),
      },
      actuator_execution: {
        fingerprint_sha256: executionFingerprint,
        status: "COMPLETED",
        source_actuator_fingerprint_sha256: executionSourceActuatorFingerprint,
        source_program_fingerprint_sha256: executionSourceProgramFingerprint,
        source_public_trajectory_fingerprint_sha256: executionSourceTrajectoryFingerprint,
        final_state: "READY_FOR_PROVIDER",
        trace: executionTrace,
        emitted_provider_operation_fingerprint_sha256: emittedProviderOperationFingerprint,
        provider_payload_fingerprint_sha256: providerPayloadFingerprint,
        provider_payload_receipt_binding_status: "PASS",
        checks: executionChecks,
      },
      boundary: string(mechanism.boundary, "response.mechanism.boundary"),
    },
    output: {
      before: {
        public_output: publicOutput(before.public_output, "response.output.before.public_output"),
        compiled_output_fingerprint_sha256: sha256(
          before.compiled_output_fingerprint_sha256,
          "response.output.before.compiled_output_fingerprint_sha256",
        ),
        active_support_evidence_ids: strings(
          before.active_support_evidence_ids,
          "response.output.before.active_support_evidence_ids",
        ),
        invalidated_evidence_ids: strings(
          before.invalidated_evidence_ids,
          "response.output.before.invalidated_evidence_ids",
        ),
        invalidation_edges: array(
          before.invalidation_edges,
          "response.output.before.invalidation_edges",
        ).map((row, index) =>
          invalidationEdge(row, `response.output.before.invalidation_edges[${index}]`),
        ),
      },
      after: {
        public_output: publicOutput(after.public_output, "response.output.after.public_output"),
        compiled_output_fingerprint_sha256: sha256(
          after.compiled_output_fingerprint_sha256,
          "response.output.after.compiled_output_fingerprint_sha256",
        ),
        active_support_evidence_ids: strings(
          after.active_support_evidence_ids,
          "response.output.after.active_support_evidence_ids",
        ),
        invalidated_evidence_ids: strings(
          after.invalidated_evidence_ids,
          "response.output.after.invalidated_evidence_ids",
        ),
        invalidation_edges: array(after.invalidation_edges, "response.output.after.invalidation_edges").map(
          (row, index) => invalidationEdge(row, `response.output.after.invalidation_edges[${index}]`),
        ),
      },
      diff: {
        answer: {
          before: string(diffAnswer.before, "response.output.diff.answer.before"),
          after: string(diffAnswer.after, "response.output.diff.answer.after"),
        },
        selected_closure_id: {
          before: string(diffClosure.before, "response.output.diff.selected_closure_id.before"),
          after: string(diffClosure.after, "response.output.diff.selected_closure_id.after"),
        },
        support_added_evidence_ids: strings(
          diff.support_added_evidence_ids,
          "response.output.diff.support_added_evidence_ids",
        ),
        support_dropped_evidence_ids: strings(
          diff.support_dropped_evidence_ids,
          "response.output.diff.support_dropped_evidence_ids",
        ),
        stable_target_ids: strings(diff.stable_target_ids, "response.output.diff.stable_target_ids"),
        target_values: array(diff.target_values, "response.output.diff.target_values").map((row, index) => {
          const item = record(row, `response.output.diff.target_values[${index}]`);
          return {
            slot: string(item.slot, `response.output.diff.target_values[${index}].slot`),
            target_id: string(item.target_id, `response.output.diff.target_values[${index}].target_id`),
            before: string(item.before, `response.output.diff.target_values[${index}].before`),
            after: string(item.after, `response.output.diff.target_values[${index}].after`),
            changed: boolean(item.changed, `response.output.diff.target_values[${index}].changed`),
          };
        }),
      },
    },
    verification: {
      rows: verificationRows,
      operational_acceptance_status: operationalStatus,
      provider_output_schema_status: providerSchemaStatus,
      lineage_binding_status: lineageStatus,
      public_actuator_execution_status: actuatorExecutionStatus,
      provider_delivery_status: providerDeliveryStatus,
      provider_uptake_status: "NOT_ASSESSED",
      structural_dependency_status: structuralDependencyStatus,
      counterfactual_output_effect_status: "NOT_ASSESSED",
      semantic_correctness_status: "NOT_ASSESSED",
      effect_attribution_status: "NOT_ASSESSED",
      provider_attempts: 1,
    },
    public_dependency_audit: {
      fingerprint_sha256: dependencyFingerprint,
      mode: "PUBLIC_GRAPH_BLOCK_RESTORE",
      scope: "SELECTED_CALLER_SUPPLIED_PUBLIC_GRAPH_ONLY",
      blocked_evidence_id: string(
        dependency.blocked_evidence_id,
        "response.public_dependency_audit.blocked_evidence_id",
      ),
      provider_calls: 0,
      hosted_output_regenerated: false,
      structural_dependency_status: dependencyStatus,
      hosted_causality_status: "NOT_ASSESSED",
      counterfactual_output_effect_status: "NOT_ASSESSED",
      baseline_closure_fingerprint_sha256: baselineClosureFingerprint,
      blocked_closure_fingerprint_sha256: blockedClosureFingerprint,
      unblocked_closure_fingerprint_sha256: unblockedClosureFingerprint,
      mask_trace: dependencyMaskTrace,
      changed_fact_targets: dependencyTargetRows,
      stable_target_ids: dependencyStableTargetIds,
      checks: dependencyChecks,
    },
    accounting: {
      api_calls: finiteNumber(accounting.api_calls, "response.accounting.api_calls", true),
      logical_calls: finiteNumber(accounting.logical_calls, "response.accounting.logical_calls", true),
      input_tokens: finiteNumber(accounting.input_tokens, "response.accounting.input_tokens", true),
      output_tokens: finiteNumber(accounting.output_tokens, "response.accounting.output_tokens", true),
      reasoning_tokens: finiteNumber(accounting.reasoning_tokens, "response.accounting.reasoning_tokens", true),
      total_tokens: finiteNumber(accounting.total_tokens, "response.accounting.total_tokens", true),
      latency_ms: finiteNumber(accounting.latency_ms, "response.accounting.latency_ms", true),
    },
    claim_boundary: strings(candidate.claim_boundary, "response.claim_boundary"),
    fingerprint_sha256: sha256(candidate.fingerprint_sha256, "response.fingerprint_sha256"),
  };
}

function endpoint(path: string): string {
  const configured =
    (import.meta as ImportMeta & { env?: { VITE_EBRT_API_BASE_URL?: string } }).env?.VITE_EBRT_API_BASE_URL?.trim() ||
    "/api/";
  const base = new URL(configured, window.location.origin);
  if (base.protocol !== "http:" && base.protocol !== "https:") {
    throw new LiveRevisionApiError("Live API URL must use HTTP or HTTPS", "INVALID_API_BASE");
  }
  if (base.username || base.password || base.search || base.hash) {
    throw new LiveRevisionApiError("Live API URL must not contain credentials, query, or fragment", "INVALID_API_BASE");
  }
  if (!base.pathname.endsWith("/")) base.pathname += "/";
  return new URL(path, base).toString();
}

async function verifiedJson(
  response: Response,
  label: string,
): Promise<{ value: unknown; bodySha256: string; raw: string }> {
  const expectedBodySha256 = response.headers.get(BODY_SHA256_HEADER);
  if (!expectedBodySha256 || !SHA256.test(expectedBodySha256)) {
    throw new LiveRevisionApiError(
      `${label} omitted its response-body integrity header`,
      "MISSING_BODY_INTEGRITY_HEADER",
      response.status,
    );
  }
  const raw = await response.text();
  const bodySha256 = await digestSha256(raw);
  if (bodySha256 !== expectedBodySha256) {
    throw new LiveRevisionApiError(
      `${label} failed its response-body integrity check`,
      "BODY_INTEGRITY_MISMATCH",
      response.status,
    );
  }
  try {
    return { value: JSON.parse(raw) as unknown, bodySha256, raw };
  } catch {
    throw new LiveRevisionApiError(`${label} did not return JSON`, "INVALID_JSON", response.status);
  }
}

async function responseError(response: Response, label: string): Promise<LiveRevisionApiError> {
  let code = "HTTP_ERROR";
  try {
    const { value } = await verifiedJson(response, `${label} error`);
    const payload = record(value, `${label} error`);
    const error = payload.error && typeof payload.error === "object" ? record(payload.error, `${label} error.error`) : payload;
    if (typeof error.code === "string" && error.code) code = error.code;
  } catch {
    // A sanitized status and code are enough; never reflect an arbitrary response body.
  }
  return new LiveRevisionApiError(`${label} failed (${response.status}, ${code})`, code, response.status);
}

export async function loadLiveDemoRequest(signal: AbortSignal): Promise<LiveDemoRequestEnvelope> {
  const response = await fetch(endpoint("demo-request"), {
    method: "GET",
    headers: { Accept: "application/json" },
    cache: "no-store",
    credentials: "omit",
    redirect: "error",
    signal,
  });
  if (!response.ok) throw await responseError(response, "Live request template");
  const { value } = await verifiedJson(response, "Live request template");
  const envelope = parseDemoRequest(value);
  const requestFingerprint = await digestSha256(canonicalJson(envelope.request));
  if (requestFingerprint !== envelope.request_fingerprint_sha256) {
    return fail("demo request.request_fingerprint_sha256 integrity");
  }
  const { fingerprint_sha256: _fingerprint, ...unsealedEnvelope } = envelope;
  const envelopeFingerprint = await digestSha256(canonicalJson(unsealedEnvelope));
  if (envelopeFingerprint !== envelope.fingerprint_sha256) {
    return fail("demo request.fingerprint_sha256 integrity");
  }
  return envelope;
}

export async function applyLiveRevision(
  envelope: LiveDemoRequestEnvelope,
  signal: AbortSignal,
): Promise<LiveApplyRevisionResponse> {
  const request = envelope.request;
  const requestId = string(request.request_id, "live request.request_id");
  const expectedInputFingerprint = await digestSha256(canonicalJson(request));
  if (expectedInputFingerprint !== envelope.request_fingerprint_sha256) {
    return fail("live request.request_fingerprint_sha256 integrity");
  }
  const response = await fetch(endpoint("apply-revision"), {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "Idempotency-Key": requestId,
    },
    body: JSON.stringify(request),
    cache: "no-store",
    credentials: "omit",
    redirect: "error",
    signal,
  });
  if (!response.ok) throw await responseError(response, "Live Apply Revision");
  const { value, bodySha256, raw } = await verifiedJson(response, "Live Apply Revision");
  const responseRecord = record(value, "response");
  const observedFingerprint = sha256(
    responseRecord.fingerprint_sha256,
    "response.fingerprint_sha256",
  );
  const recomputedFingerprint = await digestSha256(canonicalResponseWithoutSelfSeal(raw));
  if (recomputedFingerprint !== observedFingerprint) {
    return fail("response.fingerprint_sha256 integrity");
  }
  return parseResponse(value, envelope, expectedInputFingerprint, bodySha256);
}
