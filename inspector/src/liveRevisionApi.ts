import type {
  AssessmentStatus,
  CreditRow,
  EvidenceRecord,
  LiveApplyRevisionResponse,
  LiveDemoRequestEnvelope,
  ProviderPublicOutput,
  TargetValue,
} from "./applyRevisionTypes";

const DEMO_REQUEST_SCHEMA = "ebrt-live-demo-request-v0.6.2.2";
const LIVE_RESPONSE_SCHEMA = "ebrt-live-apply-revision-response-v0.6.2.2";
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
};
const SEMANTIC_ROW_DETAIL = "Reserved gold fields are rejected; caller semantic content is unverified";
const EFFECT_ROW_DETAIL = "One regeneration is not a causal contrast";
const CONTROL_CHECK_KEYS = [
  "actual_before_state_bound_to_controller",
  "local_backward_executed",
  "finite_reinspection_salience",
  "surrogate_objective_decreased",
  "non_neutral_control_map",
  "control_budget_respected",
  "finite_difference_agreement",
  "gradient_stops_before_provider",
  "reserved_gold_fields_absent",
] as const;

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

function finiteNumber(value: unknown, label: string, nonnegative = false): number {
  if (typeof value !== "number" || !Number.isFinite(value) || (nonnegative && value < 0)) return fail(label);
  return value;
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

function creditRow(value: unknown, label: string): CreditRow {
  const candidate = record(value, label);
  return {
    active_before: boolean(candidate.active_before, `${label}.active_before`),
    evidence_id: string(candidate.evidence_id, `${label}.evidence_id`),
    gradient: finiteNumber(candidate.gradient, `${label}.gradient`),
    finite_difference_gradient: finiteNumber(candidate.finite_difference_gradient, `${label}.finite_difference_gradient`),
    reinspection_salience: finiteNumber(candidate.reinspection_salience, `${label}.reinspection_salience`, true),
    source_effect: finiteNumber(candidate.source_effect, `${label}.source_effect`),
  };
}

function booleanRecord(value: unknown, label: string): Record<string, boolean> {
  const candidate = record(value, label);
  return Object.fromEntries(
    Object.entries(candidate).map(([key, child]) => [key, boolean(child, `${label}.${key}`)]),
  );
}

function parseDemoRequest(value: unknown): LiveDemoRequestEnvelope {
  const candidate = record(value, "demo request");
  if (candidate.schema_version !== DEMO_REQUEST_SCHEMA) return fail("demo request schema_version");
  const request = record(candidate.request, "demo request.request");
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
  const control = record(mechanism.public_control_map, "response.mechanism.public_control_map");
  const actuator = record(mechanism.compiled_actuator, "response.mechanism.compiled_actuator");

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
  const controlChecks = booleanRecord(control.checks, "response.mechanism.public_control_map.checks");
  const controlCheckKeys = Object.keys(controlChecks);
  if (
    controlCheckKeys.length !== CONTROL_CHECK_KEYS.length ||
    CONTROL_CHECK_KEYS.some((key) => controlChecks[key] !== true) ||
    controlCheckKeys.some((key) => !CONTROL_CHECK_KEYS.includes(key as (typeof CONTROL_CHECK_KEYS)[number]))
  ) {
    return fail("response.mechanism.public_control_map.checks hard gate");
  }
  if (mechanismStatus !== "PASS") return fail("response.mechanism.status hard gate");

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
        fingerprint_sha256: sha256(actualBefore.fingerprint_sha256, "response.mechanism.actual_before_state.fingerprint_sha256"),
        source_selected_closure_id: string(
          actualBefore.source_selected_closure_id,
          "response.mechanism.actual_before_state.source_selected_closure_id",
        ),
        initial_scalar: finiteNumber(actualBefore.initial_scalar, "response.mechanism.actual_before_state.initial_scalar"),
        active_support_evidence_ids: strings(
          actualBefore.active_support_evidence_ids,
          "response.mechanism.actual_before_state.active_support_evidence_ids",
        ),
      },
      surrogate: {
        objective_before: finiteNumber(surrogate.objective_before, "response.mechanism.surrogate.objective_before"),
        objective_after: finiteNumber(surrogate.objective_after, "response.mechanism.surrogate.objective_after"),
        terminal_target: finiteNumber(surrogate.terminal_target, "response.mechanism.surrogate.terminal_target"),
        dtype: string(surrogate.dtype, "response.mechanism.surrogate.dtype"),
        backward_calls: finiteNumber(surrogate.backward_calls, "response.mechanism.surrogate.backward_calls", true),
        maximum_finite_difference_error: finiteNumber(
          surrogate.maximum_finite_difference_error,
          "response.mechanism.surrogate.maximum_finite_difference_error",
          true,
        ),
      },
      public_control_map: {
        fingerprint_sha256: sha256(control.fingerprint_sha256, "response.mechanism.public_control_map.fingerprint_sha256"),
        control_l2: finiteNumber(control.control_l2, "response.mechanism.public_control_map.control_l2", true),
        max_control_l2: finiteNumber(control.max_control_l2, "response.mechanism.public_control_map.max_control_l2", true),
        credit_rows: array(control.credit_rows, "response.mechanism.public_control_map.credit_rows").map((row, index) =>
          creditRow(row, `response.mechanism.public_control_map.credit_rows[${index}]`),
        ),
        checks: controlChecks,
      },
      compiled_actuator: {
        fingerprint_sha256: sha256(actuator.fingerprint_sha256, "response.mechanism.compiled_actuator.fingerprint_sha256"),
        reinspect_evidence_ids: strings(
          actuator.reinspect_evidence_ids,
          "response.mechanism.compiled_actuator.reinspect_evidence_ids",
        ),
        reinspect_source: string(
          actuator.reinspect_source,
          "response.mechanism.compiled_actuator.reinspect_source",
        ),
        suppress_evidence_ids: strings(
          actuator.suppress_evidence_ids,
          "response.mechanism.compiled_actuator.suppress_evidence_ids",
        ),
        suppress_source: string(
          actuator.suppress_source,
          "response.mechanism.compiled_actuator.suppress_source",
        ),
        preserve_evidence_ids: strings(
          actuator.preserve_evidence_ids,
          "response.mechanism.compiled_actuator.preserve_evidence_ids",
        ),
        preserve_source: string(
          actuator.preserve_source,
          "response.mechanism.compiled_actuator.preserve_source",
        ),
        correction_evidence_id: string(
          actuator.correction_evidence_id,
          "response.mechanism.compiled_actuator.correction_evidence_id",
        ),
        gradient_stops_here: boolean(
          actuator.gradient_stops_here,
          "response.mechanism.compiled_actuator.gradient_stops_here",
        ),
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
      semantic_correctness_status: "NOT_ASSESSED",
      effect_attribution_status: "NOT_ASSESSED",
      provider_attempts: 1,
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
  const configured = import.meta.env.VITE_EBRT_API_BASE_URL?.trim() || "/api/";
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
