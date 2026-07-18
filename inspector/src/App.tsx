import { useEffect, useMemo, useState } from "react";
import { EvidenceLineage } from "./components/EvidenceLineage";
import { EvidenceTimeline } from "./components/EvidenceTimeline";
import { Header } from "./components/Header";
import { OutcomeDock } from "./components/OutcomeDock";
import { ReplayOverview } from "./components/ReplayOverview";
import { RunRail } from "./components/RunRail";
import type {
  ContrastDefinition,
  InspectorArm,
  InspectorSnapshot,
  InspectorViewMode,
} from "./types";

const SNAPSHOT_URL = "/data/ebrt-public-inspector-v0.1.json";

function fallbackContrasts(snapshot: InspectorSnapshot): ContrastDefinition[] {
  const arms = snapshot.runs[0]?.arms.map((arm) => arm.arm) ?? [];
  if (arms.length < 2) return [];
  return [{
    contrast_id: "recorded_protocol_comparison",
    label: "Recorded Direct / Full calibration",
    reference_arm: arms[0],
    candidate_arm: arms[1],
  }];
}

export default function App() {
  const [snapshot, setSnapshot] = useState<InspectorSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedRunId, setSelectedRunId] = useState("");
  const [selectedContrastId, setSelectedContrastId] = useState("");
  const [selectedArm, setSelectedArm] = useState("");
  const [selectedStep, setSelectedStep] = useState(0);
  const [viewMode, setViewMode] = useState<InspectorViewMode>("overview");

  useEffect(() => {
    fetch(SNAPSHOT_URL)
      .then((response) => {
        if (!response.ok) throw new Error(`Artifact load failed (${response.status})`);
        return response.json() as Promise<InspectorSnapshot>;
      })
      .then((value) => {
        setSnapshot(value);
        setSelectedRunId(value.runs[0]?.run_id ?? "");
        const available = value.contrast_definitions.filter((item) => item.available !== false);
        const contrasts = available.length ? available : fallbackContrasts(value);
        const preferred = contrasts.find((item) => item.contrast_id === "raw_aperture_ablation") ?? contrasts[0];
        setSelectedContrastId(preferred?.contrast_id ?? "");
        setSelectedArm(preferred?.reference_arm ?? value.runs[0]?.arms[0]?.arm ?? "");
      })
      .catch((cause: unknown) => setError(cause instanceof Error ? cause.message : "Artifact load failed"));
  }, []);

  const contrasts = useMemo(
    () => {
      if (!snapshot) return [];
      const available = snapshot.contrast_definitions.filter((item) => item.available !== false);
      return available.length ? available : fallbackContrasts(snapshot);
    },
    [snapshot],
  );
  const selectedRun = snapshot?.runs.find((run) => run.run_id === selectedRunId) ?? snapshot?.runs[0];
  const contrast = contrasts.find((item) => item.contrast_id === selectedContrastId) ?? contrasts[0];
  const visibleArms = useMemo(() => {
    if (!selectedRun) return [];
    const wanted = contrast ? [contrast.reference_arm, contrast.candidate_arm] : selectedRun.arm_order.slice(0, 2);
    return wanted
      .map((armName) => selectedRun.arms.find((arm) => arm.arm === armName))
      .filter((arm): arm is InspectorArm => Boolean(arm));
  }, [contrast, selectedRun]);

  useEffect(() => {
    if (!visibleArms.length) return;
    if (!visibleArms.some((arm) => arm.arm === selectedArm)) setSelectedArm(visibleArms[0].arm);
    setSelectedStep(Math.max((selectedRun?.case.evidence.length ?? 1) - 1, 0));
  }, [selectedRunId, selectedContrastId]); // eslint-disable-line react-hooks/exhaustive-deps

  if (error) {
    return (
      <main className="load-state error-state">
        <h1>EBRT Inspector</h1>
        <p>{error}</p>
        <code>{SNAPSHOT_URL}</code>
      </main>
    );
  }
  if (!snapshot || !selectedRun) {
    return <main className="load-state">Loading recorded public artifact…</main>;
  }

  return (
    <div className={`app-shell ${viewMode === "overview" ? "overview-mode" : "inspect-mode"}`}>
      <Header
        snapshot={snapshot}
        contrasts={contrasts}
        selectedContrastId={selectedContrastId}
        onContrastChange={setSelectedContrastId}
        viewMode={viewMode}
        onViewModeChange={setViewMode}
      />
      <RunRail runs={snapshot.runs} selectedRunId={selectedRun.run_id} onSelect={setSelectedRunId} />
      {viewMode === "overview" ? (
        <ReplayOverview run={selectedRun} contrast={contrast} arms={visibleArms} />
      ) : (
        <>
          <EvidenceTimeline
            evidence={selectedRun.case.evidence}
            arms={visibleArms}
            selectedArm={selectedArm}
            selectedStep={selectedStep}
            onSelectArm={setSelectedArm}
            onSelectStep={setSelectedStep}
            revisionEnvelope={selectedRun.case.revision_envelope}
          />
          <EvidenceLineage evidence={selectedRun.case.evidence} arms={visibleArms} selectedStep={selectedStep} />
          <OutcomeDock arms={visibleArms} selectedArm={selectedArm} />
        </>
      )}
    </div>
  );
}
