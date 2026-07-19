import type { WorkbenchSnapshot } from "../types";
import { Icon } from "./Icon";

type Props = {
  snapshot: WorkbenchSnapshot;
};

export function GateStrip({ snapshot }: Props) {
  const recorded = snapshot.gates.recorded_demo_ready === true;
  const fullLaunch = snapshot.provider_failure_atlas.gates.full_launch_ready === true;
  const reasoningReady = snapshot.gates.locked_reasoning_decision_ready === true;

  return (
    <section className="rw-gates" aria-label="Evidence and decision gates">
      <div className={recorded ? "gate complete" : "gate incomplete"}>
        <span className="gate-icon"><Icon name={recorded ? "check" : "minus"} size={15} /></span>
        <strong>Recorded episode {recorded ? "complete" : "not ready"}</strong>
      </div>
      <div className={fullLaunch ? "gate complete" : "gate neutral"}>
        <span className="gate-icon"><Icon name={fullLaunch ? "check" : "minus"} size={15} /></span>
        <strong>v0.4.3 full {fullLaunch ? "launched" : "not launched"}</strong>
      </div>
      <div className={reasoningReady ? "gate complete" : "gate blocked"}>
        <span className="gate-icon"><Icon name={reasoningReady ? "check" : "close"} size={15} /></span>
        <strong>Reasoning decision {reasoningReady ? "ready" : "not ready"}</strong>
      </div>
    </section>
  );
}
