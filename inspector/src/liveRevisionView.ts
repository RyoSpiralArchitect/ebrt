import type {
  ApplyRevisionSnapshot,
  ApplyRevisionView,
  LiveApplyRevisionResponse,
} from "./applyRevisionTypes";

function sameValues(left: string[], right: string[]) {
  return left.length === right.length && [...left].sort().every((value, index) => value === [...right].sort()[index]);
}

function edgeKey(edge: { source_evidence_id: string; target_evidence_id: string }) {
  return `${edge.source_evidence_id}\u0000${edge.target_evidence_id}`;
}

function requireView(condition: boolean, message: string): asserts condition {
  if (!condition) throw new Error(`Live response binding failed: ${message}`);
}

export function recordedApplyRevisionView(snapshot: ApplyRevisionSnapshot): ApplyRevisionView {
  const { decision, mode: _mode, source, verification, ...shared } = snapshot;
  return {
    ...shared,
    mode: "RECORDED_ARTIFACT_PLAYBACK",
    source: {
      kind: "recorded",
      display_fingerprint_sha256: source.result_fingerprint_sha256,
      manifest_fingerprint_sha256: source.manifest_fingerprint_sha256,
      manifest_sha256: source.manifest_sha256,
      trace_fingerprint_sha256: source.trace_fingerprint_sha256,
      artifact_sha256: source.artifact_sha256,
    },
    verification,
    assessment: {
      run_label: "Recorded run",
      run_status: decision.run_status,
      mechanism_status: decision.mechanism_status,
      acceptance_label: "Product acceptance",
      acceptance_status: decision.product_acceptance_status,
      semantic_correctness_status: decision.product_acceptance_status,
      effect_attribution_status: "NOT_ASSESSED",
      provider_attempts: snapshot.accounting.api_calls,
      terminal_label:
        decision.product_acceptance_status === "PASS"
          ? "APPLY REVISION ACCEPTED"
          : "APPLY REVISION NOT ACCEPTED",
      cost_label: "Recorded cost",
    },
  };
}

export function liveRecordedReferenceView(snapshot: ApplyRevisionSnapshot): ApplyRevisionView {
  const recorded = recordedApplyRevisionView(snapshot);
  return {
    ...recorded,
    mode: "LIVE_RECORDED_REFERENCE",
    before: {
      ...recorded.before,
      own_horizon_status: "NOT_ASSESSED",
      post_event_status: "NOT_ASSESSED",
      post_event_failed_axes: [],
    },
    after: {
      ...recorded.after,
      strict_status: "NOT_ASSESSED",
      fact_local_lineage_status: "NOT_ASSESSED",
    },
    verification: [
      {
        label: "Live result",
        detail: "Recorded output is displayed only as a reference",
        status: "NOT_ASSESSED",
      },
      {
        label: "Semantic correctness",
        detail: "No validated live result is available",
        status: "NOT_ASSESSED",
      },
      {
        label: "Effect attribution",
        detail: "No live causal contrast is available",
        status: "NOT_ASSESSED",
      },
    ],
    assessment: {
      run_label: "Live run",
      run_status: "NOT_ASSESSED",
      mechanism_status: "NOT_ASSESSED",
      acceptance_label: "Operational path",
      acceptance_status: "NOT_ASSESSED",
      semantic_correctness_status: "NOT_ASSESSED",
      effect_attribution_status: "NOT_ASSESSED",
      provider_attempts: 0,
      terminal_label: "NO LIVE RESULT · RECORDED REFERENCE",
      cost_label: "Live cost",
    },
  };
}

export function liveApplyRevisionView(response: LiveApplyRevisionResponse): ApplyRevisionView {
  const { context, mechanism, output, verification } = response;
  const before = output.before.public_output;
  const after = output.after.public_output;
  const evidenceById = new Map(context.evidence.map((row) => [row.evidence_id, row]));
  const referencedEvidenceIds = new Set([
    ...context.before_horizon_evidence_ids,
    context.late_event.evidence_id,
    ...context.late_event.invalidated_evidence_ids,
    ...context.late_event.stable_evidence_ids,
    ...mechanism.actual_before_state.active_support_evidence_ids,
    ...mechanism.compiled_actuator.reinspect_evidence_ids,
    ...mechanism.compiled_actuator.suppress_evidence_ids,
    ...mechanism.compiled_actuator.preserve_evidence_ids,
    ...output.before.active_support_evidence_ids,
    ...output.after.active_support_evidence_ids,
    ...output.after.invalidated_evidence_ids,
  ]);

  requireView([...referencedEvidenceIds].every((id) => evidenceById.has(id)), "unknown evidence ID");
  requireView(
    evidenceById.get(context.late_event.evidence_id)?.text === context.late_event.text,
    "late-event text is not evidence-bound",
  );
  requireView(
    evidenceById.get(context.late_event.evidence_id)?.role === "late_event",
    "late-event role is not explicit",
  );
  requireView(
    context.late_event.invalidated_evidence_ids.every((id) => evidenceById.get(id)?.role === "invalidated"),
    "invalidated evidence roles drifted",
  );
  requireView(
    context.late_event.stable_evidence_ids.every((id) => evidenceById.get(id)?.role === "stable_constraint"),
    "stable evidence roles drifted",
  );
  requireView(
    mechanism.actual_before_state.source_selected_closure_id === before.selected_closure_id,
    "actual Before closure drifted",
  );
  requireView(
    mechanism.compiled_actuator.correction_evidence_id === context.late_event.evidence_id,
    "compiled correction is not late-event-bound",
  );
  requireView(
    sameValues(mechanism.compiled_actuator.suppress_evidence_ids, context.late_event.invalidated_evidence_ids),
    "suppression and invalidation sets differ",
  );
  requireView(
    sameValues(mechanism.compiled_actuator.preserve_evidence_ids, context.late_event.stable_evidence_ids),
    "preservation and stable-evidence sets differ",
  );
  const expectedAfterInvalidated = [
    ...new Set([
      ...output.before.invalidated_evidence_ids,
      ...context.late_event.invalidated_evidence_ids,
    ]),
  ];
  const expectedAfterEdges = new Set([
    ...output.before.invalidation_edges.map(edgeKey),
    ...context.late_event.invalidated_evidence_ids.map((target_evidence_id) =>
      edgeKey({
        source_evidence_id: context.late_event.evidence_id,
        target_evidence_id,
      }),
    ),
  ]);
  if (verification.operational_acceptance_status === "PASS") {
    requireView(
      sameValues(output.after.invalidated_evidence_ids, expectedAfterInvalidated),
      "After invalidation transition drifted on PASS",
    );
    requireView(
      sameValues(output.after.invalidation_edges.map(edgeKey), [...expectedAfterEdges]),
      "After invalidation edges are not an exact typed transition on PASS",
    );
    requireView(
      !output.after.active_support_evidence_ids.some((id) => output.after.invalidated_evidence_ids.includes(id)),
      "invalidated evidence remained active on PASS",
    );
  } else {
    requireView(
      verification.rows.some((row) => row.status === "FAIL"),
      "operational FAIL has no failed verification row",
    );
  }
  requireView(output.diff.answer.before === before.current_answer, "Before answer diff drifted");
  requireView(output.diff.answer.after === after.current_answer, "After answer diff drifted");
  requireView(
    output.diff.selected_closure_id.before === before.selected_closure_id,
    "Before closure diff drifted",
  );
  requireView(
    output.diff.selected_closure_id.after === after.selected_closure_id,
    "After closure diff drifted",
  );
  const beforeTargets = new Map(before.target_values.map((row) => [row.target_id, row.value]));
  const afterTargets = new Map(after.target_values.map((row) => [row.target_id, row.value]));
  requireView(
    output.diff.target_values.every(
      (row) => beforeTargets.get(row.target_id) === row.before && afterTargets.get(row.target_id) === row.after,
    ),
    "target diff is not public-output-bound",
  );
  requireView(mechanism.compiled_actuator.gradient_stops_here, "gradient boundary is open");
  requireView(
    Object.keys(mechanism.public_control_map.checks).length > 0 &&
      Object.values(mechanism.public_control_map.checks).every(Boolean),
    "public control hard gate failed",
  );
  requireView(response.accounting.api_calls === 1, "live path must account for one API call");
  requireView(
    verification.provider_output_schema_status === "PASS",
    "completed response has a failed provider schema",
  );
  requireView(
    verification.operational_acceptance_status !== "PASS" || mechanism.status === "PASS",
    "operational acceptance passed a failed mechanism",
  );

  const verificationRows = [
    ...verification.rows.filter(
      (row) => row.label !== "Semantic correctness" && row.label !== "Effect attribution",
    ),
    {
      label: "Semantic correctness",
      detail: "Reserved gold fields are rejected; caller semantic content is unverified",
      status: "NOT_ASSESSED" as const,
    },
    {
      label: "Effect attribution",
      detail: "A single regeneration is not a causal contrast",
      status: "NOT_ASSESSED" as const,
    },
  ];

  return {
    schema_version: response.schema_version,
    mode: "LIVE_AFTER_REGENERATION",
    case: {
      case_id: response.case_id,
      version: "v0.6.2.2",
      question: context.question,
      model: context.model,
    },
    source: {
      kind: "live",
      display_fingerprint_sha256: response.transport_body_sha256,
      input_fingerprint_sha256: response.input_fingerprint_sha256,
      input_provenance: context.input_provenance,
      source_artifact_fingerprint_sha256:
        context.source_artifact_fingerprint_sha256 ?? undefined,
      transport_body_sha256: response.transport_body_sha256,
      server_response_fingerprint_sha256: response.fingerprint_sha256,
    },
    evidence: context.evidence,
    before: {
      horizon_evidence_ids: context.before_horizon_evidence_ids,
      answer: before.current_answer,
      selected_closure_id: before.selected_closure_id,
      target_values: before.target_values,
      active_support_evidence_ids: output.before.active_support_evidence_ids,
      provider_output_fingerprint_sha256: output.before.compiled_output_fingerprint_sha256,
      own_horizon_status: "NOT_ASSESSED",
      post_event_status: "NOT_ASSESSED",
      post_event_failed_axes: [],
    },
    late_event: context.late_event,
    revision_engine: {
      actual_before_state: mechanism.actual_before_state,
      surrogate: mechanism.surrogate,
      public_control_map: mechanism.public_control_map,
      compiled_actuator: mechanism.compiled_actuator,
      boundary: mechanism.boundary,
    },
    after: {
      answer: after.current_answer,
      selected_closure_id: after.selected_closure_id,
      target_values: after.target_values,
      active_support_evidence_ids: output.after.active_support_evidence_ids,
      invalidated_evidence_ids: output.after.invalidated_evidence_ids,
      invalidation_edges: output.after.invalidation_edges,
      provider_output_fingerprint_sha256: output.after.compiled_output_fingerprint_sha256,
      strict_status: verification.semantic_correctness_status,
      fact_local_lineage_status: verification.lineage_binding_status,
    },
    output_diff: output.diff,
    verification: verificationRows,
    assessment: {
      run_label: "Live run",
      run_status: response.status,
      mechanism_status: mechanism.status,
      acceptance_label: "Operational path",
      acceptance_status: verification.operational_acceptance_status,
      semantic_correctness_status: verification.semantic_correctness_status,
      effect_attribution_status: verification.effect_attribution_status,
      provider_attempts: verification.provider_attempts,
      terminal_label:
        verification.operational_acceptance_status === "PASS"
          ? "LIVE REGENERATION COMPLETE"
          : "LIVE REGENERATION FAILED",
      cost_label: "Live cost",
    },
    accounting: response.accounting,
    claim_boundary: response.claim_boundary,
  };
}
