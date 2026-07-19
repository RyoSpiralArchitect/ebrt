import type { ProviderFailureAtlas, WorkbenchSnapshot } from "../types";
import { Icon } from "./Icon";

type Props = {
  atlas: ProviderFailureAtlas;
  aperture: WorkbenchSnapshot["aperture_context"];
};

type ContextArm = {
  completed_outputs?: number;
  machine_successes?: number;
  reasoning_tokens?: number | null;
};

function contextArm(block: Record<string, unknown>, arm: string): ContextArm | undefined {
  const arms = block.arms;
  if (!arms || typeof arms !== "object") return undefined;
  const value = (arms as Record<string, unknown>)[arm];
  return value && typeof value === "object" ? value as ContextArm : undefined;
}

export function ProviderBoundaryAtlas({ atlas, aperture }: Props) {
  const v043 = atlas.native_diagnostic_coverage.v0_4_3_contract_smoke;
  const r01 = atlas.native_diagnostic_coverage.r01_frozen_native;
  const cardOnly = contextArm(aperture.v0_4_1, "staged_card_only_rerun");
  const cumulative = contextArm(aperture.v0_4_1, "staged_cumulative_raw");

  return (
    <section className="rw-atlas" aria-labelledby="provider-atlas-title">
      <header>
        <div>
          <h2 id="provider-atlas-title">Provider Failure Atlas <span>· recorded v0.4.3 smoke</span></h2>
          <p>Runtime-health episode. Separate from the reasoning episode above.</p>
        </div>
        <details className="rw-atlas-details">
          <summary>Inspect context</summary>
          <div>
            <h3>Aperture evidence · separate frozen DEV</h3>
            <p>{aperture.relationship_to_recorded_episode.replaceAll("_", " ")}</p>
            <dl>
              <div>
                <dt>Card-only</dt>
                <dd>{cardOnly?.machine_successes ?? "—"}/{cardOnly?.completed_outputs ?? "—"} completed successes</dd>
              </div>
              <div>
                <dt>Cumulative raw</dt>
                <dd>{cumulative?.machine_successes ?? "—"}/{cumulative?.completed_outputs ?? "—"} completed successes</dd>
              </div>
              <div>
                <dt>Cause gate</dt>
                <dd>not ready</dd>
              </div>
            </dl>
            <p className="rw-context-boundary">{aperture.claim_boundary}</p>
          </div>
        </details>
      </header>

      <div className="rw-atlas-body">
        <div className="rw-pipeline" aria-label="Recorded provider boundary pipeline">
          {atlas.pipeline.map((stage, index) => (
            <div className="rw-pipeline-pair" key={stage.stage_id}>
              <div className={`rw-pipeline-stage ${stage.stage_id === "http_observation" ? "failure" : ""}`}>
                <span>{index + 1}</span>
                <strong>{stage.label}</strong>
                <b>{stage.count}</b>
                <small>{stage.status_code ? `HTTP ${stage.status_code}` : stage.stage_id.replaceAll("_", " ")}</small>
              </div>
              {index < atlas.pipeline.length - 1 ? <Icon name="arrow" size={20} /> : null}
            </div>
          ))}
        </div>
        <dl className="rw-atlas-facts">
          <div><dt>Error code</dt><dd>{atlas.classified_failure.allowlisted_reason_code}</dd></div>
          <div><dt>Classification</dt><dd>{v043.fraction} classified</dd></div>
          <div><dt>Frozen r01</dt><dd>{r01.fraction} native</dd></div>
          <div><dt>Cross-block effect</dt><dd>{String(atlas.native_diagnostic_coverage.cross_block_effect_estimate)}</dd></div>
          <div><dt>Full launch</dt><dd>{atlas.gates.full_launch_ready ? "ready" : "not launched"}</dd></div>
        </dl>
      </div>

      <footer>
        <strong>{atlas.status}</strong>
        <span>{atlas.claim_boundary}</span>
      </footer>
    </section>
  );
}
