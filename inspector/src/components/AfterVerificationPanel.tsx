import type { ApplyRevisionSnapshot } from "../applyRevisionTypes";
import { Icon } from "./Icon";

export function AfterVerificationPanel({
  active,
  replayStep,
  snapshot,
}: {
  active: boolean;
  replayStep: number;
  snapshot: ApplyRevisionSnapshot;
}) {
  const accepted = snapshot.decision.product_acceptance_status === "PASS";
  return (
    <section
      aria-labelledby="after-title"
      className={`ar-panel ar-after-panel ${active ? "mobile-active" : ""} ${replayStep >= 3 ? "is-replaying" : ""}`}
      id="stage-panel-after"
      role="tabpanel"
    >
      <header className="ar-panel-title">
        <span>03</span>
        <h1 id="after-title">After + Verification</h1>
      </header>

      <div className="ar-answer-diff" aria-label={`${snapshot.before.answer} changed to ${snapshot.after.answer}`}>
        <strong>{snapshot.before.answer}</strong>
        <Icon name="arrow" size={36} />
        <b>{snapshot.after.answer}</b>
      </div>

      <div className="ar-public-diff">
        <span className="ar-block-label">Public decision-fact diff</span>
        {snapshot.output_diff.target_values.map((target) => (
          <div className={target.changed ? "changed" : "stable"} key={target.target_id}>
            <span>{target.changed ? "−" : "="}</span>
            <code>{target.before.replaceAll("_", " ")}</code>
            {target.changed ? (
              <>
                <span>+</span>
                <code>{target.after.replaceAll("_", " ")}</code>
              </>
            ) : <small>preserved</small>}
          </div>
        ))}
      </div>

      <div className="ar-provider-output ar-provider-after">
        <div>
          <span>Actual provider output · Call 2</span>
          <code>{snapshot.after.selected_closure_id}</code>
        </div>
        <div className="ar-output-answer">
          <span>answer</span>
          <strong>{snapshot.after.answer}</strong>
        </div>
        <dl>
          {snapshot.after.target_values.map((target) => (
            <div key={target.target_id}>
              <dt>{target.slot.replaceAll("_", " ")}</dt>
              <dd>{target.value.replaceAll("_", " ")}</dd>
            </div>
          ))}
        </dl>
      </div>

      <div className="ar-verification-list" aria-label="Strict verification">
        <span className="ar-block-label">Strict verification</span>
        {snapshot.verification.map((row) => (
          <div key={row.label}>
            <span>{row.label}</span>
            <code>{row.detail}</code>
            <strong>
              <Icon name={row.status === "PASS" ? "check" : "close"} size={16} />
              {row.status}
            </strong>
          </div>
        ))}
      </div>

      <strong className={accepted ? "ar-accepted" : "ar-rejected"}>
        {accepted ? "APPLY REVISION ACCEPTED" : "APPLY REVISION NOT ACCEPTED"}
      </strong>
    </section>
  );
}
