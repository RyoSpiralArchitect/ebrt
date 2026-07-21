import type { ApplyRevisionSnapshot } from "./applyRevisionTypes";

const SNAPSHOT_URL = "/data/ebrt-apply-revision-acceptance-v0.6.2.1.json";
const EXPECTED_PROJECTION_SHA256 = "d2d9a1531bd384bfb7b7b2875e830289092d9b49d01198d3c6e7c5bddac497f2";
const EXPECTED_MANIFEST_SHA256 = "532dd593ef4464d87dd02fd2eeaa712855f47e5de799c669889c0302ee2fe3a4";
const EXPECTED_RESULT_FINGERPRINT = "1ba3cfe9565124d92fa8db8222c4d44bc62a81e1da7c6fad07e24e9a8e7ad245";

function hex(bytes: ArrayBuffer) {
  return Array.from(new Uint8Array(bytes), (value) => value.toString(16).padStart(2, "0")).join("");
}

function assertSnapshot(value: unknown): asserts value is ApplyRevisionSnapshot {
  if (!value || typeof value !== "object") throw new Error("Recorded projection is not an object");
  const candidate = value as Partial<ApplyRevisionSnapshot>;
  if (candidate.schema_version !== "ebrt-apply-revision-ide-projection-v0.6.2.1") {
    throw new Error("Recorded projection schema does not match v0.6.2.1");
  }
  if (candidate.mode !== "RECORDED_ARTIFACT_PLAYBACK") {
    throw new Error("Inspector accepts recorded-artifact playback only");
  }
  if (candidate.decision?.effect_attribution_status !== "NOT_ASSESSED") {
    throw new Error("Effect-attribution boundary is missing");
  }
  if (
    candidate.source?.manifest_sha256 !== EXPECTED_MANIFEST_SHA256 ||
    candidate.source?.result_fingerprint_sha256 !== EXPECTED_RESULT_FINGERPRINT
  ) {
    throw new Error("Recorded projection is not bound to the exact live r01 publication");
  }
  if (
    candidate.decision?.run_status !== "COMPLETE_EXACT_TWO_TERMINALS" ||
    candidate.decision?.mechanism_status !== "PASS" ||
    candidate.decision?.product_acceptance_status !== "PASS" ||
    candidate.decision?.terminal_decision !== "ACCEPT_APPLY_REVISION_PATH"
  ) {
    throw new Error("Recorded projection does not carry the accepted live r01 decision");
  }
  if (
    candidate.output_diff?.answer?.before !== candidate.before?.answer ||
    candidate.output_diff?.answer?.after !== candidate.after?.answer
  ) {
    throw new Error("Recorded projection answer diff is not bound to its provider outputs");
  }
}

export async function loadApplyRevisionSnapshot(): Promise<ApplyRevisionSnapshot> {
  const response = await fetch(SNAPSHOT_URL, { cache: "no-store" });
  if (!response.ok) throw new Error(`Recorded projection load failed (${response.status})`);
  const raw = await response.arrayBuffer();
  const observedSha256 = hex(await crypto.subtle.digest("SHA-256", raw));
  if (observedSha256 !== EXPECTED_PROJECTION_SHA256) {
    throw new Error("Recorded projection bytes do not match the reviewed live r01 snapshot");
  }
  const value: unknown = JSON.parse(new TextDecoder().decode(raw));
  assertSnapshot(value);
  return value;
}
