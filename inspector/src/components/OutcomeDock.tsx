import type { InspectorArm } from "../types";
import { armLabel } from "../armLabels";

type Props = {
  arms: InspectorArm[];
  selectedArm: string;
};

function formatTokens(value?: number | null) {
  return value == null ? "—" : new Intl.NumberFormat("en-US").format(value);
}

export function OutcomeDock({ arms, selectedArm }: Props) {
  const active = arms.find((arm) => arm.arm === selectedArm) ?? arms[0];
  const facts = active?.outcome.available
    ? active.timeline.at(-1)?.public_card.decision_facts ?? []
    : [];
  return (
    <section className="outcome-dock">
      <div className="facts-panel">
        <h2>Final public decision facts</h2>
        <div className="fact-list">
          {facts.length ? facts.map((fact) => (
            <div className="fact-row" key={fact.slot}>
              <span>{fact.slot}</span>
              <strong>{fact.value}</strong>
            </div>
          )) : <p className="empty-copy">Final decision facts unavailable.</p>}
        </div>
      </div>
      <div className="measurement-panel">
        <div className="dock-title">
          <h2>Final outcome &amp; recorded usage</h2>
          <span>Reasoning-token detail is usage metadata, not chain-of-thought or total compute.</span>
        </div>
        <div className="measurement-table-wrap">
          <table className="measurement-table">
            <thead>
              <tr>
                <th>Execution protocol</th>
                <th>Final strict grader outcome</th>
                <th>Required evidence</th>
                <th>API calls</th>
                <th>Input tokens</th>
                <th>Output tokens</th>
                <th>Reasoning-token detail</th>
              </tr>
            </thead>
            <tbody>
              {arms.map((arm) => {
                const available = arm.outcome.available;
                const success = available && arm.outcome.machine_success === true;
                return (
                  <tr key={arm.arm} className={arm.arm === selectedArm ? "selected" : ""}>
                    <th>{armLabel(arm.arm)}</th>
                    <td className={available ? (success ? "pass" : "fail") : "not-assessed"}>
                      {available ? (success ? "PASS" : "FAIL") : "NOT ASSESSED"}
                    </td>
                    <td>{available ? (arm.outcome.missing_required_evidence_ids.length === 0 ? "met" : `missing ${arm.outcome.missing_required_evidence_ids.join(", ")}`) : "not assessed"}</td>
                    <td>{arm.cost.api_calls}</td>
                    <td>{formatTokens(arm.cost.input_tokens)}</td>
                    <td>{formatTokens(arm.cost.output_tokens)}</td>
                    <td>{formatTokens(arm.cost.reasoning_tokens)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}
