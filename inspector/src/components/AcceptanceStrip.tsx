import type { ApplyRevisionView, AssessmentStatus } from "../applyRevisionTypes";

function seconds(milliseconds: number) {
  return `${(milliseconds / 1000).toFixed(2)} s`;
}

function statusClass(value: AssessmentStatus) {
  return value === "PASS" ? "ar-pass" : value === "FAIL" ? "ar-fail" : "ar-not-assessed";
}

export function AcceptanceStrip({ snapshot }: { snapshot: ApplyRevisionView }) {
  const shortFingerprint = snapshot.source.display_fingerprint_sha256.slice(0, 16);
  const recordedReference = snapshot.mode === "LIVE_RECORDED_REFERENCE";
  return (
    <footer className="ar-acceptance-strip" aria-label={`${snapshot.assessment.run_label} status`}>
      <div className="ar-run-cell">
        <span>{snapshot.assessment.run_label}</span>
        <strong>{snapshot.assessment.run_status.replaceAll("_", " ")} · {snapshot.assessment.provider_attempts} {snapshot.assessment.provider_attempts === 1 ? "attempt" : "attempts"}</strong>
        <code title={snapshot.source.display_fingerprint_sha256}>
          {recordedReference ? "reference " : snapshot.mode === "LIVE_AFTER_REGENERATION" ? "verified body " : ""}{shortFingerprint}…
        </code>
      </div>
      <div>
        <span>Mechanism</span>
        <strong className={statusClass(snapshot.assessment.mechanism_status)}>
          {snapshot.assessment.mechanism_status.replaceAll("_", " ")}
        </strong>
      </div>
      <div>
        <span>{snapshot.assessment.acceptance_label}</span>
        <strong className={statusClass(snapshot.assessment.acceptance_status)}>
          {snapshot.assessment.acceptance_status.replaceAll("_", " ")}
        </strong>
      </div>
      <div>
        <span>Effect attribution</span>
        <strong className="ar-not-assessed">NOT ASSESSED</strong>
      </div>
      <div className="ar-cost-cell">
        <span>{snapshot.assessment.cost_label}</span>
        {recordedReference ? (
          <>
            <strong>No live result</strong>
            <code>No provider attempt</code>
          </>
        ) : (
          <>
            <strong>{snapshot.accounting.input_tokens.toLocaleString()} in · {snapshot.accounting.output_tokens.toLocaleString()} out</strong>
            <code>{snapshot.accounting.reasoning_tokens} reasoning · {seconds(snapshot.accounting.latency_ms)}</code>
          </>
        )}
      </div>
    </footer>
  );
}
