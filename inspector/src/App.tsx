import { useEffect, useMemo, useState } from "react";
import { GateStrip } from "./components/GateStrip";
import { Header } from "./components/Header";
import { Icon } from "./components/Icon";
import { ProviderBoundaryAtlas } from "./components/ProviderBoundaryAtlas";
import { PublicOutputDiff } from "./components/PublicOutputDiff";
import {
  ReasoningFlow,
  StageNav,
  type WorkbenchStage,
} from "./components/ReasoningFlow";
import { WorkbenchRail } from "./components/WorkbenchRail";
import type { WorkbenchSnapshot } from "./types";

const SNAPSHOT_URL = "/data/ebrt-reasoning-workbench-v0.4.4.json";

export default function App() {
  const [snapshot, setSnapshot] = useState<WorkbenchSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedLaneId, setSelectedLaneId] = useState("full_restart");
  const [activeStage, setActiveStage] = useState<WorkbenchStage>("replay");
  const [playing, setPlaying] = useState(false);
  const [playbackStep, setPlaybackStep] = useState(0);

  useEffect(() => {
    fetch(SNAPSHOT_URL)
      .then((response) => {
        if (!response.ok) throw new Error(`Recorded artifact load failed (${response.status})`);
        return response.json() as Promise<WorkbenchSnapshot>;
      })
      .then((value) => {
        setSnapshot(value);
        const selected = value.recorded_episode.public_output_comparison.selected_recorded_lane;
        setSelectedLaneId(typeof selected === "string" ? selected : "full_restart");
      })
      .catch((cause: unknown) => {
        setError(cause instanceof Error ? cause.message : "Recorded artifact load failed");
      });
  }, []);

  const selectedLane = useMemo(
    () => snapshot?.recorded_episode.replay_lanes.find((lane) => lane.lane_id === selectedLaneId),
    [selectedLaneId, snapshot],
  );
  const playbackTotal = selectedLane?.public_cards.length ?? 0;

  useEffect(() => {
    if (!playing || playbackTotal === 0) return undefined;
    if (playbackStep >= playbackTotal) {
      setPlaying(false);
      return undefined;
    }
    const timer = window.setTimeout(() => {
      setPlaybackStep((current) => Math.min(current + 1, playbackTotal));
    }, 360);
    return () => window.clearTimeout(timer);
  }, [playing, playbackStep, playbackTotal]);

  function selectLane(laneId: string) {
    setSelectedLaneId(laneId);
    setPlaying(false);
    setPlaybackStep(0);
  }

  function playRecordedRevision() {
    if (playing) {
      setPlaying(false);
      return;
    }
    if (!selectedLane) setSelectedLaneId("full_restart");
    setActiveStage("replay");
    setPlaybackStep(0);
    setPlaying(true);
  }

  if (error) {
    return (
      <main className="rw-load-state error">
        <h1>EBRT Reasoning Workbench</h1>
        <p>{error}</p>
        <code>{SNAPSHOT_URL}</code>
      </main>
    );
  }

  if (!snapshot) {
    return <main className="rw-load-state">Loading immutable recorded projection…</main>;
  }

  const episode = snapshot.recorded_episode;

  return (
    <div className="rw-shell">
      <Header snapshot={snapshot} />
      <GateStrip snapshot={snapshot} />
      <div className="rw-mobile-run">
        <span><strong>{snapshot.selection.case_id}</strong> · Trial {snapshot.selection.trial_index}</span>
        <Icon name="chevron" size={15} />
      </div>
      <StageNav activeStage={activeStage} onSelect={setActiveStage} />
      <WorkbenchRail snapshot={snapshot} />

      <main className="rw-main">
        <div className="rw-workbench-grid">
          <ReasoningFlow
            evidence={episode.evidence}
            initial={episode.initial}
            observer={episode.observer}
            revisionPlan={episode.revision_plan}
            lanes={episode.replay_lanes}
            selectedLaneId={selectedLaneId}
            onSelectLane={selectLane}
            onPlay={playRecordedRevision}
            playing={playing}
            playbackStep={playbackStep}
            activeStage={activeStage}
          />
          <PublicOutputDiff
            initialCard={episode.initial.public_card}
            lane={selectedLane}
            activeStage={activeStage}
          />
        </div>
        <ProviderBoundaryAtlas atlas={snapshot.provider_failure_atlas} aperture={snapshot.aperture_context} />
        <footer className="rw-audit-line">
          <div><Icon name="document" size={18} /><strong>Audit line · read-only</strong><span>Immutable public projection</span></div>
          <div><span>Episode</span><strong>{snapshot.selection.case_id}:{snapshot.selection.trial_index}</strong></div>
          <div><span>Protocol</span><strong>Recorded revision replay</strong></div>
          <div><span>Model</span><strong>{episode.observer.provenance.model}</strong></div>
          <div><span>Physical calls</span><strong>{episode.recorded_physical_experiment_accounting.api_calls}</strong></div>
          <div><span>Boundary</span><strong>Public state only</strong></div>
        </footer>
      </main>
    </div>
  );
}
