import type { ApplyRevisionView } from "../applyRevisionTypes";
import { Icon } from "./Icon";

export type LiveRevisionPhase = "idle" | "loading-template" | "regenerating" | "complete" | "error" | "aborted";

function formatObjective(value: number) {
  return value.toFixed(4);
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
  const { compiled_actuator: actuator, public_control_map: control, surrogate } = snapshot.revision_engine;
  const actuatorEvidence = new Set([
    ...actuator.reinspect_evidence_ids,
    ...actuator.suppress_evidence_ids,
    ...actuator.preserve_evidence_ids,
    snapshot.late_event.evidence_id,
  ]);
  const liveSalience = snapshot.mode === "LIVE_AFTER_REGENERATION";
  const controlMetric = (row: (typeof control.credit_rows)[number]) =>
    liveSalience ? (row.reinspection_salience ?? 0) : (row.signed_public_credit ?? 0);
  const selectedCredits = control.credit_rows.filter(
    (row) => row.active_before || Math.abs(controlMetric(row)) > Number.EPSILON || actuatorEvidence.has(row.evidence_id),
  );
  const visibleCredits = selectedCredits.length ? selectedCredits : control.credit_rows;
  const maxCredit = Math.max(0, ...visibleCredits.map((row) => Math.abs(controlMetric(row))));
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
          <span>Revision objective</span>
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
            {liveSalience ? "Reinspection salience" : "Signed public credit"}
          </span>
          <code>L2 {control.control_l2.toFixed(4)} / {control.max_control_l2.toFixed(2)}</code>
        </div>
        <div
          className="ar-credit-map"
          aria-label={liveSalience ? "Backward reinspection salience by evidence" : "Signed public credit by evidence"}
        >
          {visibleCredits.map((row) => (
            <div className={actuator.suppress_evidence_ids.includes(row.evidence_id) ? "suppressed" : ""} key={row.evidence_id}>
              <strong>{row.evidence_id}</strong>
              <span>
                <i
                  style={{
                    width: maxCredit === 0 ? "0%" : `${Math.max(2, Math.abs(controlMetric(row)) / maxCredit * 100)}%`,
                  }}
                />
              </span>
              <code>{controlMetric(row).toFixed(4)}</code>
            </div>
          ))}
        </div>
      </div>

      <div className={`ar-engine-step ar-actuator-block ${replayStep >= 2 ? "is-replaying" : ""}`}>
        <span className="ar-block-label">Compiled actuator · provider-visible</span>
        <dl>
          <div><dt>{actuator.reinspect_source ? "Reinspect · backward-ranked" : "Reinspect"}</dt><dd className="ar-blue">{actuator.reinspect_evidence_ids.join(" → ")}</dd></div>
          <div><dt>{actuator.suppress_source ? "Suppress · typed event" : "Suppress"}</dt><dd className="ar-red">{actuator.suppress_evidence_ids.join(", ")}</dd></div>
          <div><dt>{actuator.preserve_source ? "Preserve · typed event" : "Preserve"}</dt><dd>{actuator.preserve_evidence_ids.join(", ")}</dd></div>
        </dl>
      </div>

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
