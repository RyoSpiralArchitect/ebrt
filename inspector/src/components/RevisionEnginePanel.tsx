import type { ApplyRevisionView, CreditRow } from "../applyRevisionTypes";
import { Icon } from "./Icon";

export type LiveRevisionPhase = "idle" | "loading-template" | "regenerating" | "complete" | "error" | "aborted";

function formatObjective(value: number) {
  return value.toFixed(4);
}

function formatTrajectoryState(values: number[]) {
  return `[${values.map((value) => value.toFixed(3)).join(" / ")}]`;
}

type DisplayCredit = {
  row: CreditRow;
  value: number;
};

function CreditMap({
  credits,
  label,
  suppressEvidenceIds,
  trajectory,
}: {
  credits: DisplayCredit[];
  label: string;
  suppressEvidenceIds: string[];
  trajectory: boolean;
}) {
  const maxCredit = Math.max(0, ...credits.map(({ value }) => Math.abs(value)));
  return (
    <div className="ar-credit-map" aria-label={label}>
      {credits.map(({ row, value }) => (
        <div className={suppressEvidenceIds.includes(row.evidence_id) ? "suppressed" : ""} key={row.evidence_id}>
          <strong>{row.evidence_id}</strong>
          <span>
            <i
              style={{
                width: maxCredit === 0 ? "0%" : `${Math.max(2, Math.abs(value) / maxCredit * 100)}%`,
              }}
            />
          </span>
          <code>
            {value.toFixed(4)}
            {trajectory && row.control_value !== undefined ? ` · u ${row.control_value.toFixed(4)}` : ""}
          </code>
        </div>
      ))}
    </div>
  );
}

export function RevisionEnginePanel({
  active,
  liveError,
  livePhase,
  mode,
  onAbort,
  onLiveApply,
  onReplay,
  playing,
  replayStep,
  snapshot,
}: {
  active: boolean;
  liveError: string | null;
  livePhase: LiveRevisionPhase;
  mode: "recorded" | "live";
  onAbort: () => void;
  onLiveApply: () => void;
  onReplay: () => void;
  playing: boolean;
  replayStep: number;
  snapshot: ApplyRevisionView;
}) {
  const { compiled_actuator: actuator, public_control_map: control, public_trajectory: trajectory, surrogate } = snapshot.revision_engine;
  const inspectionPlan = actuator.inspection_plan;
  const execution = snapshot.revision_engine.actuator_execution;
  const actuatorEvidence = new Set([
    ...actuator.reinspect_evidence_ids,
    ...actuator.suppress_evidence_ids,
    ...actuator.preserve_evidence_ids,
    snapshot.late_event.evidence_id,
  ]);
  const liveAllocation = snapshot.mode === "LIVE_AFTER_REGENERATION" && Boolean(inspectionPlan);
  const controlMetric = (row: (typeof control.credit_rows)[number]) =>
    trajectory
      ? Math.abs(row.gradient)
      : liveAllocation
      ? (row.optimized_allocation_fraction ?? 0)
      : snapshot.mode === "LIVE_AFTER_REGENERATION"
        ? (row.reinspection_salience ?? 0)
        : (row.signed_public_credit ?? 0);
  const selectedCredits = control.credit_rows.filter(
    (row) => row.active_before || Math.abs(controlMetric(row)) > Number.EPSILON || actuatorEvidence.has(row.evidence_id),
  );
  const visibleCredits = selectedCredits.length ? selectedCredits : control.credit_rows;
  const displayCredits = visibleCredits.map((row) => ({ row, value: controlMetric(row) }));
  const focusCredits = [...displayCredits]
    .sort((left, right) => Math.abs(right.value) - Math.abs(left.value))
    .slice(0, 3);
  const liveBusy = livePhase === "loading-template" || livePhase === "regenerating";
  const actionBusy = mode === "recorded" ? playing : liveBusy;

  const liveStatus =
    livePhase === "loading-template"
      ? "Loading a fresh server-owned request…"
      : livePhase === "regenerating"
        ? "One live provider regeneration is in progress…"
        : livePhase === "complete"
          ? "Live regeneration complete · semantic correctness not assessed"
          : livePhase === "aborted"
            ? "Stopped waiting · the server run may still complete"
            : livePhase === "error"
              ? "Live regeneration did not produce a displayable result"
              : "Fresh request fetched only when Apply is pressed";

  return (
    <section
      aria-labelledby="engine-title"
      className={`ar-panel ar-engine-panel ${active ? "mobile-active" : ""}`}
      id="stage-panel-engine"
      role="tabpanel"
    >
      <header className="ar-panel-title">
        <span>02</span>
        <h1 id="engine-title">EBRT Revision Engine</h1>
      </header>
      {snapshot.mode === "LIVE_RECORDED_REFERENCE" ? (
        <p className="ar-reference-note">Recorded engine reference · live mechanism not assessed</p>
      ) : null}

      <div className={`ar-engine-step ar-surrogate-block ${replayStep >= 1 ? "is-replaying" : ""}`}>
        <span className="ar-block-label">Local surrogate</span>
        <div className="ar-event-node">Late evidence {snapshot.late_event.evidence_id}</div>
        <Icon name="arrow" size={18} />
        <div className="ar-objective-row">
          <span>{trajectory ? "Trajectory loss" : "Revision objective"}</span>
          <strong>{formatObjective(surrogate.objective_before)}</strong>
          <Icon name="arrow" size={16} />
          <strong>{formatObjective(surrogate.objective_after)}</strong>
        </div>
        <div className="ar-backward-row">
          <span>backward()</span>
          <strong>EXECUTED LOCALLY · {surrogate.dtype}</strong>
        </div>
      </div>

      <div className={`ar-engine-step ar-control-block ${replayStep >= 1 ? "is-replaying" : ""}`}>
        <div className="ar-block-heading">
          <span className="ar-block-label">
            {trajectory ? "Top temporal credit · |∂L/∂uₜ|" : liveAllocation ? "Top inspection allocation" : "Top signed public credit"}
          </span>
          <code>L2 {control.control_l2.toFixed(4)} / {control.max_control_l2.toFixed(2)}</code>
        </div>
        <CreditMap
          credits={focusCredits}
          label={trajectory ? "Top temporal credit by public trajectory step" : liveAllocation ? "Top optimized public inspection allocation by evidence" : "Top signed public credit by evidence"}
          suppressEvidenceIds={actuator.suppress_evidence_ids}
          trajectory={Boolean(trajectory)}
        />
      </div>

      <div className={`ar-engine-step ar-actuator-block ${replayStep >= 2 ? "is-replaying" : ""}`}>
        <span className="ar-block-label">Compiled actuator · provider-visible</span>
        <dl>
          <div><dt>{inspectionPlan ? "Reinspect · |uₜ| allocation" : actuator.reinspect_source ? "Reinspect · backward-ranked" : "Reinspect"}</dt><dd className="ar-blue">{actuator.reinspect_evidence_ids.join(" → ")}</dd></div>
          <div><dt>{actuator.suppress_source ? "Suppress · typed event" : "Suppress"}</dt><dd className="ar-red">{actuator.suppress_evidence_ids.join(", ")}</dd></div>
          <div><dt>{actuator.preserve_source ? "Preserve · typed event" : "Preserve"}</dt><dd>{actuator.preserve_evidence_ids.join(", ")}</dd></div>
        </dl>
        {trajectory ? (
          <p className="ar-reference-note">
            Control magnitude allocates reinspection; the typed event defines suppress and preserve.
          </p>
        ) : null}
      </div>

      <details className="ar-receipt-details">
        <summary>
          <Icon name="document" size={16} />
          <span>Inspect trajectory receipts</span>
          <Icon name="chevron" size={15} />
        </summary>
        <div className="ar-receipt-content">
          {trajectory ? (
            <>
              <div className="ar-objective-row">
                <span>Matched temporal sham · {trajectory.research_diagnostics.temporal_sham.status.replaceAll("_", " ")}</span>
                <strong>{formatObjective(trajectory.matched_temporal_sham.objective)}</strong>
                <span>diagnostic only · 0 calls</span>
              </div>
              <dl aria-label="Neutral and revised public trajectories">
                <div>
                  <dt>Zero-control trajectory · no event proposal admitted</dt>
                  <dd>
                    {trajectory.neutral.points.map((point) =>
                      `${point.evidence_id}${formatTrajectoryState(point.state)}`,
                    ).join(" → ")}
                  </dd>
                </div>
                <div>
                  <dt>Revised trajectory</dt>
                  <dd className="ar-blue">
                    {trajectory.revised.points.map((point) =>
                      `${point.evidence_id}${formatTrajectoryState(point.state)}`,
                    ).join(" → ")}
                  </dd>
                </div>
                <div>
                  <dt>Full-admission support reference</dt>
                  <dd>
                    {trajectory.neutral.points.map((point) =>
                      `${point.evidence_id}[${point.full_admission_support_reference.toFixed(3)}]`,
                    ).join(" → ")}
                  </dd>
                </div>
              </dl>
              <p className="ar-reference-note">
                Axis order · {trajectory.axis_order.join(" / ")} · public surrogate only
              </p>
            </>
          ) : null}
          {surrogate.surrogate_terminal_state_before !== undefined &&
          surrogate.surrogate_terminal_state_after !== undefined ? (
            <div className="ar-objective-row">
              <span>Surrogate terminal state</span>
              <strong>{formatObjective(surrogate.surrogate_terminal_state_before)}</strong>
              <Icon name="arrow" size={16} />
              <strong>{formatObjective(surrogate.surrogate_terminal_state_after)}</strong>
            </div>
          ) : null}
          {displayCredits.length > focusCredits.length ? (
            <>
              <span className="ar-block-label">Complete public credit receipt</span>
              <CreditMap
                credits={displayCredits}
                label="Complete public credit receipt by evidence"
                suppressEvidenceIds={actuator.suppress_evidence_ids}
                trajectory={Boolean(trajectory)}
              />
            </>
          ) : null}
          {inspectionPlan ? (
            <>
              <span className="ar-block-label">
                Continuous inspection plan · {inspectionPlan.total_budget_units} abstract units
              </span>
              <div className="ar-credit-map" aria-label="Provider-visible continuous inspection allocation">
                {inspectionPlan.steps.map((step) => (
                  <div key={step.evidence_id}>
                    <strong>#{step.priority_rank} {step.evidence_id}</strong>
                    <span>
                      <i style={{ width: `${Math.max(2, step.inspection_share * 100)}%` }} />
                    </span>
                    <code>
                      {(step.inspection_share * 100).toFixed(2)}% · {step.inspection_budget_units}u · {step.review_depth}
                    </code>
                  </div>
                ))}
              </div>
              <p className="ar-reference-note">
                Allocation and units are public review directives, not attention probabilities or provider token budgets.
              </p>
            </>
          ) : null}
          {execution ? (
            <>
              <span className="ar-block-label">Actuator execution trace · {execution.final_state}</span>
              <dl aria-label="Public actuator state-machine execution trace">
                {execution.trace.map((step) => (
                  <div key={step.step_index}>
                    <dt>{String(step.step_index).padStart(2, "0")} · {step.operation}</dt>
                    <dd>
                      {step.evidence_id ?? "full context"} · {step.state_before} → {step.state_after}
                    </dd>
                  </div>
                ))}
              </dl>
            </>
          ) : null}
          {snapshot.public_dependency_audit ? (
            <p className="ar-reference-note">
              Public graph block/unblock · {snapshot.public_dependency_audit.blocked_evidence_id} ·{" "}
              {snapshot.public_dependency_audit.structural_dependency_status}. Hosted causality{" "}
              {snapshot.public_dependency_audit.hosted_causality_status.toLowerCase().replaceAll("_", " ")}.
            </p>
          ) : null}
        </div>
      </details>

      <div className="ar-boundary">
        <span>GRADIENT STOPS HERE</span>
        <p>{snapshot.revision_engine.boundary}</p>
      </div>

      <div className="ar-regeneration-node">{snapshot.case.model} · full-context regeneration</div>
      <button
        aria-describedby="replay-status"
        aria-pressed={mode === "recorded" ? replayStep === 3 : undefined}
        className="ar-replay-button"
        disabled={actionBusy}
        onClick={mode === "recorded" ? onReplay : onLiveApply}
        type="button"
      >
        <Icon name={mode === "recorded" ? "play" : "runs"} size={18} />
        {mode === "recorded"
          ? "Replay recorded Apply Revision"
          : livePhase === "loading-template"
            ? "Loading fresh request…"
            : livePhase === "regenerating"
              ? "Regenerating…"
              : "Apply Revision → Regenerate"}
      </button>
      {liveBusy ? (
        <button className="ar-abort-button" onClick={onAbort} type="button">
          Stop waiting
        </button>
      ) : null}
      <span className="ar-replay-status" id="replay-status">
        {mode === "recorded"
          ? playing
            ? "Replaying sealed public states…"
            : replayStep === 3
              ? "Replay complete · no model call"
              : "Local playback · no model call"
          : liveStatus}
      </span>
      {mode === "live" && liveError ? <p className="ar-live-error" role="alert">{liveError}</p> : null}
    </section>
  );
}
