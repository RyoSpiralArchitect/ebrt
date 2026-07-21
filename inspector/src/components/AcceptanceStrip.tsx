import type { ApplyRevisionSnapshot } from "../applyRevisionTypes";

function seconds(milliseconds: number) {
  return `${(milliseconds / 1000).toFixed(2)} s`;
}

export function AcceptanceStrip({ snapshot }: { snapshot: ApplyRevisionSnapshot }) {
  const shortFingerprint = snapshot.source.result_fingerprint_sha256.slice(0, 16);
  return (
    <footer className="ar-acceptance-strip" aria-label="Recorded acceptance status">
      <div className="ar-run-cell">
        <span>Run</span>
        <strong>COMPLETE · {snapshot.accounting.api_calls} calls</strong>
        <code title={snapshot.source.result_fingerprint_sha256}>{shortFingerprint}…</code>
      </div>
      <div>
        <span>Mechanism</span>
        <strong className={snapshot.decision.mechanism_status === "PASS" ? "ar-pass" : "ar-fail"}>
          {snapshot.decision.mechanism_status}
        </strong>
      </div>
      <div>
        <span>Product acceptance</span>
        <strong className={snapshot.decision.product_acceptance_status === "PASS" ? "ar-pass" : "ar-fail"}>
          {snapshot.decision.product_acceptance_status}
        </strong>
      </div>
      <div>
        <span>Effect attribution</span>
        <strong className="ar-not-assessed">NOT ASSESSED</strong>
      </div>
      <div className="ar-cost-cell">
        <span>Recorded cost</span>
        <strong>{snapshot.accounting.input_tokens.toLocaleString()} in · {snapshot.accounting.output_tokens.toLocaleString()} out</strong>
        <code>{snapshot.accounting.reasoning_tokens} reasoning · {seconds(snapshot.accounting.latency_ms)}</code>
      </div>
    </footer>
  );
}
