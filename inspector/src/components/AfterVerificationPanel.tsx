import type { ApplyRevisionView } from "../applyRevisionTypes";
import { Icon } from "./Icon";

function readableDecision(
  answer: string,
  targets: ApplyRevisionView["after"]["target_values"],
) {
  const naturalize = (value: string) => value
    .replaceAll("_", " ")
    .toLowerCase()
    .replace(/\bui\b/g, "UI")
    .replace(/\bend to end\b/g, "end-to-end");
  const facts = new Map(
    targets
      .filter((target) => target.target_type === "fact")
      .map((target) => [target.slot, naturalize(target.value)]),
  );
  const priority = facts.get("final_priority");
  const centerpiece = facts.get("demo_centerpiece");
  if (priority && centerpiece) {
    const centerpiecePhrase = centerpiece.endsWith("s") ? centerpiece : `a ${centerpiece}`;
    return `${answer} — Prioritize ${priority}; center the demo on ${centerpiecePhrase}.`;
  }
  return `${answer} — ${[...facts].map(([slot, value]) => `${slot.replaceAll("_", " ")}: ${value}`).join("; ")}.`;
}

export function AfterVerificationPanel({
  active,
  replayStep,
  snapshot,
}: {
  active: boolean;
  replayStep: number;
  snapshot: ApplyRevisionView;
}) {
  const accepted = snapshot.assessment.acceptance_status === "PASS";
  const assessed = snapshot.assessment.acceptance_status !== "NOT_ASSESSED";
  const answerChanged = snapshot.before.answer !== snapshot.after.answer;
  const recorded = snapshot.mode === "RECORDED_ARTIFACT_PLAYBACK";
  const recordedReference = snapshot.mode === "LIVE_RECORDED_REFERENCE";
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
      {recordedReference ? <p className="ar-reference-note">Live output is withheld until Apply Revision completes</p> : null}

      <div
        className={`ar-answer-diff ${recordedReference ? "pending" : answerChanged ? "changed" : "unchanged"}`}
        aria-label={
          recordedReference
            ? `${snapshot.before.answer} awaits a live regenerated answer`
            : answerChanged
            ? `${snapshot.before.answer} changed to ${snapshot.after.answer}`
            : `${snapshot.before.answer} remained unchanged`
        }
      >
        <strong>{snapshot.before.answer}</strong>
        <Icon name="arrow" size={36} />
        <b>{snapshot.after.answer}</b>
      </div>

      {!recordedReference ? (
        <div className="ar-language-diff">
          <span>Natural-language output diff · deterministic public-field projection</span>
          <p className="removed">− Bound prior output · R1–R5: {readableDecision(snapshot.before.answer, snapshot.before.target_values)}</p>
          <p className="added">+ Regenerated After · R1–R6 + public operation: {readableDecision(snapshot.after.answer, snapshot.after.target_values)}</p>
        </div>
      ) : null}

      {recordedReference ? (
        <div className="ar-live-output-pending" role="status">
          <Icon name="runs" size={26} />
          <strong>No live output yet</strong>
          <span>Apply Revision from the center panel to run one full-context regeneration.</span>
        </div>
      ) : (
        <>
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
              <span>{recorded ? "Actual recorded provider output · Call 2" : "Live regenerated public output"}</span>
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
        </>
      )}

      <div className="ar-verification-list" aria-label={recorded ? "Strict verification" : "Operational verification"}>
        <span className="ar-block-label">{recorded ? "Strict verification" : "Operational verification"}</span>
        {snapshot.verification.map((row) => (
          <div className={row.status === "NOT_ASSESSED" ? "not-assessed" : ""} key={row.label}>
            <span>{row.label}</span>
            <code>{row.detail}</code>
            <strong>
              <Icon name={row.status === "PASS" ? "check" : row.status === "FAIL" ? "close" : "minus"} size={16} />
              {row.status}
            </strong>
          </div>
        ))}
      </div>

      <strong className={!assessed ? "ar-terminal-not-assessed" : accepted ? "ar-accepted" : "ar-rejected"}>
        {snapshot.assessment.terminal_label}
      </strong>
    </section>
  );
}
