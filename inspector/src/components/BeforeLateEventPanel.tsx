import type { ApplyRevisionSnapshot, EvidenceRecord } from "../applyRevisionTypes";

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
  snapshot: ApplyRevisionSnapshot;
}) {
  const r3 = snapshot.evidence.find((row) => row.evidence_id === "R3")!;
  const r5 = snapshot.evidence.find((row) => row.evidence_id === "R5")!;

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

      <div className="ar-before-answer">
        <strong>{snapshot.before.answer}</strong>
        <span><b>PASS</b> · {snapshot.before.horizon_evidence_ids[0]}–{snapshot.before.horizon_evidence_ids.at(-1)} OWN HORIZON</span>
      </div>

      <div className="ar-provider-output ar-provider-before">
        <div>
          <span>Actual provider output · Call 1</span>
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
        <strong>STALE POST-EVENT</strong>
        <span>{snapshot.before.post_event_failed_axes.length} strict axes fail</span>
      </div>
      <ul className="ar-evidence-audit">
        <EvidenceRow evidence={r3} annotation="invalidated · conflicts with R6" />
        <EvidenceRow evidence={r5} annotation="stable · unchanged" />
      </ul>
    </section>
  );
}
