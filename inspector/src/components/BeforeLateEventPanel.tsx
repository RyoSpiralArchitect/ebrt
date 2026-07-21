import type { ApplyRevisionView, EvidenceRecord } from "../applyRevisionTypes";

function EvidenceRow({ evidence, annotation }: { evidence: EvidenceRecord; annotation: string }) {
  return (
    <li className={`ar-evidence-row ${evidence.role}`}>
      <strong>{evidence.evidence_id}</strong>
      <div>
        <span>{annotation}</span>
        <p>{evidence.text}</p>
      </div>
    </li>
  );
}

export function BeforeLateEventPanel({
  active,
  snapshot,
}: {
  active: boolean;
  snapshot: ApplyRevisionView;
}) {
  const invalidated = snapshot.late_event.invalidated_evidence_ids
    .map((evidenceId) => snapshot.evidence.find((row) => row.evidence_id === evidenceId))
    .filter((row): row is EvidenceRecord => Boolean(row));
  const stable = snapshot.late_event.stable_evidence_ids
    .map((evidenceId) => snapshot.evidence.find((row) => row.evidence_id === evidenceId))
    .filter((row): row is EvidenceRecord => Boolean(row));
  const recorded = snapshot.mode === "RECORDED_ARTIFACT_PLAYBACK";
  const recordedReference = snapshot.mode === "LIVE_RECORDED_REFERENCE";

  return (
    <section
      aria-labelledby="before-title"
      className={`ar-panel ar-before-panel ${active ? "mobile-active" : ""}`}
      id="stage-panel-before"
      role="tabpanel"
    >
      <header className="ar-panel-title">
        <span>01</span>
        <h1 id="before-title">Before + Late Event</h1>
      </header>
      {recordedReference ? <p className="ar-reference-note">Recorded reference · no live result</p> : null}
      {snapshot.source.input_provenance === "CONTAMINATED_REGRESSION_FIXTURE" ? (
        <p className="ar-reference-note">Contaminated regression fixture · operational demo only</p>
      ) : null}

      <div className="ar-before-answer">
        <strong>{snapshot.before.answer}</strong>
        <span>
          <b>{snapshot.before.own_horizon_status.replaceAll("_", " ")}</b> · {snapshot.before.horizon_evidence_ids.join(" · ")} {recorded ? "OWN HORIZON" : recordedReference ? "RECORDED REFERENCE HORIZON" : "SOURCE HORIZON"}
        </span>
      </div>

      <div className="ar-provider-output ar-provider-before">
        <div>
          <span>
            {recorded
              ? "Actual recorded provider output · Call 1"
              : recordedReference
                ? "Recorded reference provider output · no live result"
                : "Bound source public output"}
          </span>
          <code>{snapshot.before.selected_closure_id}</code>
        </div>
        <dl>
          {snapshot.before.target_values.map((target) => (
            <div key={target.target_id}>
              <dt>{target.slot.replaceAll("_", " ")}</dt>
              <dd>{target.value.replaceAll("_", " ")}</dd>
            </div>
          ))}
        </dl>
      </div>

      <article className="ar-late-event">
        <div className="ar-event-label">
          <strong>{snapshot.late_event.evidence_id}</strong>
          <span>LATE EVIDENCE RECEIVED</span>
        </div>
        <p>{snapshot.late_event.text}</p>
      </article>

      <div className="ar-stale-heading">
        <strong>
          {recorded
            ? "STALE POST-EVENT"
            : recordedReference
              ? "RECORDED REFERENCE · LIVE NOT ASSESSED"
              : "SEMANTIC STATUS NOT ASSESSED"}
        </strong>
        <span>
          {recorded
            ? `${snapshot.before.post_event_failed_axes.length} strict axes fail`
            : "reserved gold fields blocked · semantics unverified"}
        </span>
      </div>
      <ul className="ar-evidence-audit">
        {invalidated.map((row) => (
          <EvidenceRow
            annotation={`invalidated · conflicts with ${snapshot.late_event.evidence_id}`}
            evidence={row}
            key={row.evidence_id}
          />
        ))}
        {stable.map((row) => (
          <EvidenceRow annotation="stable · unchanged" evidence={row} key={row.evidence_id} />
        ))}
      </ul>
    </section>
  );
}
