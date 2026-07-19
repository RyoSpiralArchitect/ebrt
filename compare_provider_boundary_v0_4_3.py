#!/usr/bin/env python3
"""Deterministic diagnostic comparison of frozen r01 and v0.4.3 artifacts.

This is an offline artifact audit. It never imports a provider SDK, calls a
network endpoint, mutates either input bundle, or reclassifies an r01 row.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "artifacts" / "compare_provider_boundary_v0_4_3"

R01_SMOKE_CANONICAL = (
    ROOT
    / "artifacts"
    / "benchmark_aperture_controls_v0_4_2_unchanged_replication_r01_contract_smoke"
)
R01_SMOKE_WORKING = (
    ROOT
    / "benchmark_results"
    / "v0_4_2_unchanged_replication_r01_contract_smoke"
)
R01_FULL_CANONICAL = (
    ROOT
    / "artifacts"
    / "benchmark_aperture_controls_v0_4_2_unchanged_replication_r01_dev"
)
R01_FULL_WORKING = (
    ROOT / "benchmark_results" / "v0_4_2_unchanged_replication_r01_dev"
)
V043_SMOKE_CANONICAL = (
    ROOT / "artifacts" / "benchmark_aperture_controls_v0_4_3_contract_smoke"
)
V043_SMOKE_WORKING = (
    ROOT / "benchmark_results" / "v0_4_3_provider_boundary_contract_smoke"
)
V043_FULL_CANONICAL = ROOT / "artifacts" / "benchmark_aperture_controls_v0_4_3_dev"
V043_FULL_WORKING = ROOT / "benchmark_results" / "v0_4_3_provider_boundary_dev"

R01_POLICY = ROOT / "policy_lock_aperture_controls_v0_4_2_unchanged_replication_r01.json"
V043_POLICY = ROOT / "policy_lock_aperture_controls_v0_4_3.json"

ARTIFACT_NAMES = (
    "arm_rows.csv",
    "benchmark_report.md",
    "calls.jsonl",
    "manifest.json",
    "results.json",
    "traces.jsonl",
)
HASHED_ARTIFACT_NAMES = tuple(name for name in ARTIFACT_NAMES if name != "manifest.json")
ARMS = (
    "direct_raw_no_revision",
    "direct_raw_fixed_revision_rerun",
    "staged_card_only_rerun",
    "staged_cumulative_raw",
)
WILLIAMS_ROWS = (
    (ARMS[0], ARMS[1], ARMS[3], ARMS[2]),
    (ARMS[1], ARMS[2], ARMS[0], ARMS[3]),
    (ARMS[2], ARMS[3], ARMS[1], ARMS[0]),
    (ARMS[3], ARMS[0], ARMS[2], ARMS[1]),
)

PINS = {
    "r01_policy": "2fdecd663df2efd713a242268108e7f7ee131e074191c72bc650c5ab48886584",
    "r01_smoke_manifest": "fb623a28eb61d7c9dea971ff8018645890b141f79b048e38e109fb32765d15a5",
    "r01_full_manifest": "dde2d872ead686fa5d4b8074536e0d44acc1678036937f834fbe6389a3971671",
    "v043_policy": "ed69464c5065ec081a9ca117a08e3e53eac2a4e235968e7392f514fbd23ffa65",
    "v043_runner": "e8d065eebbbc8289c4afac91a4d40649bd7ff6305a54e888a6cf30ebe6fd09e9",
    "v043_adapter": "7f78fce94cb141a4355d3c040010e11e049ff67a3a8c603099d0548a47b7cf03",
    "v043_smoke_manifest": "42172d684de6541fc6b26e23cf7e9ae7fde92395dd81db8fbeb53ed8a32021ec",
}

V043_PRE_CORRECTION_SMOKE_MANIFEST_SHA256 = (
    "1aabd709e95f8f45c94a31dda6d443cdcd80ab4f03e93a03de3d6bac2cb36f3c"
)
V043_PRE_CORRECTION_RESULTS_SHA256 = (
    "f519d253228d037092037b1592c46ac0443d1684ad223b0701420225223b544e"
)
V043_PROVIDER_RECEIPT_PROJECTION_SHA256 = (
    "ba735cd7ec08a9644636ac665bf3514d8d1fd460a103214e40da0afeeba658e9"
)

FORBIDDEN_KEYS = frozenset(
    {
        "api_key",
        "authorization",
        "bearer_token",
        "credentials",
        "exception_args",
        "exception_message",
        "exception_traceback",
        "headers",
        "provider_raw_response_body",
        "raw_headers",
        "raw_response",
        "rejected_card",
        "rejected_public_reasoning_card",
        "response_body",
    }
)
SECRET_PATTERNS = (
    re.compile(rb"\bsk-[A-Za-z0-9_-]{16,}\b"),
    re.compile(rb"(?i)\bBearer\s+[A-Za-z0-9._~+/-]{12,}"),
    re.compile(rb"OPENAI_API_KEY"),
)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_blob(commit: str, path: str) -> bytes:
    return subprocess.run(
        ["git", "show", f"{commit}:{path}"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(value, dict), f"expected JSON object: {path}")
    return value


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    _require(all(isinstance(row, dict) for row in rows), f"invalid JSONL: {path}")
    return rows


def _relative(path: Path) -> str:
    return str(path.relative_to(ROOT))


def _walk_keys(value: Any) -> list[str]:
    keys: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            keys.append(str(key))
            keys.extend(_walk_keys(child))
    elif isinstance(value, list):
        for child in value:
            keys.extend(_walk_keys(child))
    return keys


def _audit_privacy(directory: Path) -> None:
    for name in ARTIFACT_NAMES:
        raw = (directory / name).read_bytes()
        for pattern in SECRET_PATTERNS:
            _require(pattern.search(raw) is None, f"secret-like payload found in {directory / name}")
        if name.endswith((".json", ".jsonl")):
            values: list[Any]
            if name.endswith(".jsonl"):
                values = _load_jsonl(directory / name)
            else:
                values = [_load_json(directory / name)]
            keys = {key.lower() for value in values for key in _walk_keys(value)}
            _require(not (keys & FORBIDDEN_KEYS), f"forbidden persisted key in {directory / name}")


def _validate_bundle(
    *, canonical: Path, working: Path, manifest_sha256: str
) -> dict[str, Any]:
    _require(canonical.is_dir(), f"missing canonical bundle: {canonical}")
    canonical_names = tuple(sorted(path.name for path in canonical.iterdir() if path.is_file()))
    _require(canonical_names == tuple(sorted(ARTIFACT_NAMES)), "canonical bundle file set drifted")
    working_present = working.exists()
    byte_identity: dict[str, bool] | None = None
    if working_present:
        _require(working.is_dir(), f"working bundle is not a directory: {working}")
        working_names = tuple(
            sorted(path.name for path in working.iterdir() if path.is_file())
        )
        _require(working_names == canonical_names, "working bundle file set drifted")
        byte_identity = {
            name: (canonical / name).read_bytes() == (working / name).read_bytes()
            for name in ARTIFACT_NAMES
        }
        _require(
            all(byte_identity.values()),
            f"working/canonical mismatch: {canonical.name}",
        )

    manifest_path = canonical / "manifest.json"
    _require(_sha256(manifest_path) == manifest_sha256, f"manifest pin drifted: {manifest_path}")
    manifest = _load_json(manifest_path)
    artifact_hashes = manifest.get("artifact_sha256")
    _require(isinstance(artifact_hashes, dict), "manifest artifact hash map missing")
    _require(set(artifact_hashes) == set(HASHED_ARTIFACT_NAMES), "artifact hash key set drifted")
    for name, expected in artifact_hashes.items():
        _require(_sha256(canonical / name) == expected, f"artifact hash drifted: {canonical / name}")

    results = _load_json(canonical / "results.json")
    calls = _load_jsonl(canonical / "calls.jsonl")
    traces = _load_jsonl(canonical / "traces.jsonl")
    _require(traces == results["runs"], f"trace/result run mismatch: {canonical.name}")
    _require(len(calls) == manifest["attempted_api_calls"], "call/attempt cardinality drifted")

    flattened: list[dict[str, Any]] = []
    for run in results["runs"]:
        _require(set(run["arms"]) == set(ARMS), "arm set drifted")
        for arm in run["arm_order"]:
            for arm_call_index, receipt in enumerate(run["arms"][arm]["receipts"]):
                flattened.append(
                    {
                        "arm": arm,
                        "arm_call_index": arm_call_index,
                        "case_id": run["case_id"],
                        "family": run["family"],
                        "receipt": receipt,
                        "run_id": run["run_id"],
                        "trial_index": run["trial_index"],
                    }
                )
    _require(flattened == calls, f"result/call receipt projection drifted: {canonical.name}")
    for row in calls:
        metadata = row["receipt"]["metadata"]
        _require(metadata.get("attempt") == 1, "attempt is not exactly one")
        _require(metadata.get("retry_count") == 0, "retry count is not zero")

    _audit_privacy(canonical)
    return {
        "artifact_sha256": dict(sorted(artifact_hashes.items())),
        "byte_identical_files": byte_identity,
        "calls": calls,
        "manifest": manifest,
        "manifest_sha256": manifest_sha256,
        "results": results,
        "working_bundle_present": working_present,
        "working_identity_checked": working_present,
    }


def _receipt_projection_sha256(results: Mapping[str, Any]) -> str:
    receipts = [
        receipt
        for run in results["runs"]
        for arm in run["arm_order"]
        for receipt in run["arms"][arm]["receipts"]
    ]
    return hashlib.sha256(_canonical_json(receipts).encode("utf-8")).hexdigest()


def _validate_v043_derived_coverage(bundle: Mapping[str, Any]) -> dict[str, Any]:
    manifest = bundle["manifest"]
    results = bundle["results"]
    authority = "v0.4.3_policy_exact_schedule_projection"
    coverage_records = (
        manifest,
        manifest["execution_record"],
        manifest["comparison_record"],
        results["summary"]["live_receipt_validation"],
    )
    for record in coverage_records:
        _require(
            record.get("contract_smoke_exact_coverage") is True,
            "authoritative v0.4.3 smoke coverage is not exact",
        )
        _require(
            record.get("contract_smoke_coverage_authority") == authority,
            "v0.4.3 smoke coverage authority drifted",
        )
        _require(
            record.get(
                "inherited_v0_4_2_smoke_namespace_projection_validated"
            )
            is True,
            "v0.4.2 smoke namespace projection was not validated",
        )

    result_lineage = results.get("derived_artifact_lineage", {})
    manifest_lineage = manifest.get("derived_artifact_lineage", {})
    _require(
        result_lineage.get("corrected_fields")
        == [
            "derived_artifact_lineage",
            "summary.live_receipt_validation.contract_smoke_exact_coverage",
            "summary.live_receipt_validation.contract_smoke_coverage_authority",
            "summary.live_receipt_validation.inherited_v0_4_2_smoke_namespace_projection_validated",
        ],
        "v0.4.3 corrected results field lineage drifted",
    )
    _require(
        manifest_lineage.get("corrected_fields")
        == [
            "artifact_sha256.results.json",
            "claim_boundary.post_freeze_derived_coverage_correction_only",
            "comparison_record.coverage_projection_fields",
            "contract_smoke_coverage_authority",
            "contract_smoke_exact_coverage",
            "derived_artifact_lineage",
            "execution_record.coverage_projection_fields",
            "inherited_v0_4_2_smoke_namespace_projection_validated",
            "results.json.derived_artifact_lineage",
            "results.json.summary.live_receipt_validation.coverage_projection_fields",
        ],
        "v0.4.3 corrected manifest field lineage drifted",
    )
    for lineage in (result_lineage, manifest_lineage):
        _require(
            lineage.get("schema_version")
            == "ebrt-post-freeze-derived-correction-v0.4.3"
            and lineage.get("correction_id")
            == "post_freeze_inherited_v0_4_2_smoke_namespace_projection"
            and lineage.get("authority") == authority
            and lineage.get("no_live_call") is True
            and lineage.get("artifact_bytes_postdate_preregistration") is True
            and lineage.get("provider_observations_unchanged") is True,
            "v0.4.3 post-freeze derivation lineage drifted",
        )
        _require(
            lineage.get("original_manifest_sha256")
            == V043_PRE_CORRECTION_SMOKE_MANIFEST_SHA256
            and lineage.get("original_results_sha256")
            == V043_PRE_CORRECTION_RESULTS_SHA256
            and lineage.get("provider_receipt_projection_sha256")
            == V043_PROVIDER_RECEIPT_PROJECTION_SHA256,
            "v0.4.3 pre-correction evidence lineage drifted",
        )
        _require(
            lineage.get("observation_artifacts_unchanged")
            == {
                name: bundle["artifact_sha256"][name]
                for name in (
                    "arm_rows.csv",
                    "benchmark_report.md",
                    "calls.jsonl",
                    "traces.jsonl",
                )
            },
            "v0.4.3 observation-artifact lineage drifted",
        )
    _require(
        manifest_lineage.get("corrected_results_sha256")
        == bundle["artifact_sha256"]["results.json"],
        "corrected v0.4.3 results hash is absent from its lineage",
    )
    _require(
        _receipt_projection_sha256(results)
        == V043_PROVIDER_RECEIPT_PROJECTION_SHA256,
        "frozen v0.4.3 provider receipts changed during derived correction",
    )
    _require(
        manifest["full_run_launch_ready"] is False
        and manifest["full_launch_ready"] is False
        and manifest["provider_boundary_failures"] == 8
        and manifest["primary_execution_classification"]
        == "smoke_gate_failed_full_not_launched",
        "derived coverage correction changed the frozen launch decision",
    )
    return {
        "authority": authority,
        "corrected_results_sha256": bundle["artifact_sha256"]["results.json"],
        "no_live_call": True,
        "original_manifest_sha256": V043_PRE_CORRECTION_SMOKE_MANIFEST_SHA256,
        "provider_receipt_projection_sha256": (
            V043_PROVIDER_RECEIPT_PROJECTION_SHA256
        ),
    }


def _schedule_projection(results: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "arm_order": list(run["arm_order"]),
            "case_id": run["case_id"],
            "original_case_index": int(run["original_case_index"]),
            "run_id": run["run_id"],
            "run_position": int(run["run_position"]),
            "trial_index": int(run["trial_index"]),
        }
        for run in results["runs"]
    ]


def _validate_schedule(results: Mapping[str, Any]) -> str:
    cases = list(results["case_ids"])
    expected: list[dict[str, Any]] = []
    for trial_index in range(int(results["trials"])):
        indexed = list(enumerate(cases))
        shift = trial_index % len(indexed)
        for run_position, (original_case_index, case_id) in enumerate(
            [*indexed[shift:], *indexed[:shift]]
        ):
            expected.append(
                {
                    "arm_order": list(
                        WILLIAMS_ROWS[(trial_index + original_case_index) % 4]
                    ),
                    "case_id": case_id,
                    "original_case_index": original_case_index,
                    "run_id": f"{results['mode']}:{trial_index}:{case_id}",
                    "run_position": run_position,
                    "trial_index": trial_index,
                }
            )
    actual = _schedule_projection(results)
    _require(actual == expected, f"deterministic schedule drifted: {results['mode']}")
    return hashlib.sha256(_canonical_json(actual).encode("utf-8")).hexdigest()


def _validate_hash_pins(
    r01_policy: Mapping[str, Any], v043_policy: Mapping[str, Any], v043: Mapping[str, Any]
) -> dict[str, Any]:
    prereg_commit = str(v043["manifest"]["preregistration_commit"])
    paths = {
        "r01_policy": R01_POLICY,
        "r01_smoke_manifest": R01_SMOKE_CANONICAL / "manifest.json",
        "r01_full_manifest": R01_FULL_CANONICAL / "manifest.json",
        "v043_policy": V043_POLICY,
        "v043_adapter": ROOT / "openai_response_boundary_v0_4_3.py",
        "v043_smoke_manifest": V043_SMOKE_CANONICAL / "manifest.json",
    }
    observed = {name: _sha256(path) for name, path in paths.items()}
    observed["v043_runner"] = hashlib.sha256(
        _git_blob(prereg_commit, "benchmark_aperture_controls_v0_4_3.py")
    ).hexdigest()
    _require(observed == PINS, "top-level comparison pin drifted")

    predecessor = v043_policy["predecessor"]
    _require(predecessor["r01_preregistration_policy_sha256"] == PINS["r01_policy"], "r01 policy link drifted")
    _require(predecessor["r01_contract_smoke_manifest_sha256"] == PINS["r01_smoke_manifest"], "r01 smoke link drifted")
    _require(predecessor["r01_full_manifest_sha256"] == PINS["r01_full_manifest"], "r01 full link drifted")
    _require(v043["manifest"]["policy_sha256"] == PINS["v043_policy"], "v0.4.3 policy link drifted")
    _require(v043["manifest"]["provider_adapter_sha256"] == PINS["v043_adapter"], "adapter link drifted")

    for path, expected in r01_policy["expected_execution_source_sha256"].items():
        _require(_sha256(ROOT / path) == expected, f"r01 execution source pin drifted: {path}")
    reference_paths = {
        "prior_v0_4_2_contract_smoke_manifest_sha256": "artifacts/benchmark_aperture_controls_v0_4_2_contract_smoke/manifest.json",
        "prior_v0_4_2_incomplete_dev_manifest_sha256": "artifacts/benchmark_aperture_controls_v0_4_2_dev/manifest.json",
        "v0_4_1_dev_manifest_sha256": "artifacts/benchmark_aperture_controls_v0_4_1_dev/manifest.json",
        "direct_full_parent_manifest_sha256": "artifacts/benchmark_direct_full_calibration_v0_4_dev/manifest.json",
    }
    for key, path in reference_paths.items():
        _require(_sha256(ROOT / path) == r01_policy["frozen_reference"][key], f"r01 frozen reference drifted: {key}")

    boot_map = v043["manifest"]["boot_source_sha256_map"]
    _require(
        set(boot_map) == set(v043_policy["source_seal"]["boot_source_paths"]),
        "v0.4.3 boot path set drifted",
    )
    for path, expected in boot_map.items():
        if path == "benchmark_aperture_controls_v0_4_3.py":
            # The live smoke is permanently tied to the preregistered runner
            # blob. Post-freeze audit maintenance may change the working runner
            # without changing the bytes that actually generated the artifact.
            observed_source = hashlib.sha256(_git_blob(prereg_commit, path)).hexdigest()
        else:
            observed_source = _sha256(ROOT / path)
        _require(observed_source == expected, f"v0.4.3 boot source drifted: {path}")

    prereg_tree = subprocess.run(
        ["git", "rev-parse", f"{prereg_commit}^{{tree}}"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    _require(prereg_tree == v043["manifest"]["preregistration_tree"], "preregistration tree drifted")
    for path, expected in boot_map.items():
        committed = _git_blob(prereg_commit, path)
        _require(hashlib.sha256(committed).hexdigest() == expected, f"preregistration source mismatch: {path}")
    return observed


def _ratio(numerator: int, denominator: int) -> dict[str, Any]:
    _require(numerator >= 0 and denominator >= 0, "ratio counts must be non-negative")
    _require(numerator <= denominator, "ratio numerator exceeds denominator")
    return {
        "defined": denominator > 0,
        "denominator": denominator,
        "fraction": f"{numerator}/{denominator}",
        "numerator": numerator,
        "ratio": None if denominator == 0 else numerator / denominator,
    }


def _endpoint_counts(
    results: Mapping[str, Any], allowlist: Mapping[str, Sequence[str]] | None
) -> tuple[int, int, Counter[tuple[str, str]]]:
    nonassessable = [
        payload
        for run in results["runs"]
        for payload in run["arms"].values()
        if not bool(payload["primary_endpoint_assessed"])
    ]
    classified = 0
    phase_reason: Counter[tuple[str, str]] = Counter()
    for payload in nonassessable:
        phase = payload.get("failure_phase")
        reason = payload.get("failure_reason_code")
        native_pair_present = allowlist is None and phase is not None and reason is not None
        allowlisted_pair = (
            allowlist is not None
            and phase in allowlist
            and reason in allowlist[str(phase)]
        )
        if native_pair_present or allowlisted_pair:
            classified += 1
            phase_reason[(str(phase), str(reason))] += 1
    return classified, len(nonassessable), phase_reason


def build_comparison() -> dict[str, Any]:
    r01_policy = _load_json(R01_POLICY)
    v043_policy = _load_json(V043_POLICY)
    r01_smoke = _validate_bundle(
        canonical=R01_SMOKE_CANONICAL,
        working=R01_SMOKE_WORKING,
        manifest_sha256=PINS["r01_smoke_manifest"],
    )
    r01 = _validate_bundle(
        canonical=R01_FULL_CANONICAL,
        working=R01_FULL_WORKING,
        manifest_sha256=PINS["r01_full_manifest"],
    )
    v043 = _validate_bundle(
        canonical=V043_SMOKE_CANONICAL,
        working=V043_SMOKE_WORKING,
        manifest_sha256=PINS["v043_smoke_manifest"],
    )
    pins = _validate_hash_pins(r01_policy, v043_policy, v043)
    coverage_lineage = _validate_v043_derived_coverage(v043)

    _require(not V043_FULL_WORKING.exists(), "unexpected v0.4.3 working full block")
    _require(not V043_FULL_CANONICAL.exists(), "unexpected v0.4.3 canonical full block")
    _require(r01["manifest"]["status"] == "INCOMPLETE", "r01 status drifted")
    _require(r01["manifest"]["locked_decision_ready"] is False, "r01 decision gate drifted")
    _require(v043["manifest"]["status"] == "COMPLETE_DIAGNOSTIC_NON_DECISION", "v0.4.3 smoke status drifted")
    _require(v043["manifest"]["diagnostic_integrity_ready"] is True, "v0.4.3 diagnostic gate drifted")
    _require(v043["manifest"]["full_launch_ready"] is False, "v0.4.3 full-launch gate drifted")
    _require(v043["manifest"]["locked_decision_ready"] is False, "v0.4.3 decision gate drifted")
    _require(v043["manifest"]["reasoning_comparison_available"] is False, "reasoning gate drifted")
    _require(v043["manifest"]["primary_execution_classification"] == "smoke_gate_failed_full_not_launched", "execution classification drifted")

    r01_schedule = _validate_schedule(r01["results"])
    v043_schedule = _validate_schedule(v043["results"])
    _require(len(r01["results"]["runs"]) == 30, "r01 run coverage drifted")
    _require(len(v043["results"]["runs"]) == 2, "v0.4.3 smoke run coverage drifted")
    _require(v043_schedule == v043["manifest"]["run_and_arm_order_sha256"], "v0.4.3 manifest schedule drifted")
    _require(v043_schedule == v043_policy["execution_sequence"]["contract_smoke"]["run_and_arm_order_sha256"], "v0.4.3 policy schedule drifted")

    r01_classified, r01_nonassessable, _ = _endpoint_counts(r01["results"], None)
    allowlist = v043_policy["failure_code_allowlist"]["non_assessable_by_phase"]
    v043_classified, v043_nonassessable, phase_reason = _endpoint_counts(
        v043["results"], allowlist
    )
    _require((r01_classified, r01_nonassessable) == (0, 31), "r01 native metric drifted")
    _require((v043_classified, v043_nonassessable) == (8, 8), "v0.4.3 smoke metric drifted")
    _require(r01["manifest"]["non_assessable_failures"] == r01_nonassessable, "r01 denominator mismatch")
    _require(v043["manifest"]["classified_nonassessable_endpoint_count"] == v043_classified, "v0.4.3 numerator mismatch")
    _require(v043["manifest"]["non_assessable_failures"] == v043_nonassessable, "v0.4.3 denominator mismatch")

    r01_failed = [row for row in r01["calls"] if row["receipt"]["metadata"]["attempt_outcome"] != "completed"]
    _require(len(r01_failed) == 31, "r01 failed receipt count drifted")
    _require(all("failure_phase" not in row["receipt"]["metadata"] for row in r01_failed), "r01 phase was retrospectively added")
    _require(all("failure_reason_code" not in row["receipt"]["metadata"] for row in r01_failed), "r01 reason was retrospectively added")
    _require(len(v043["calls"]) == 8, "v0.4.3 receipt cardinality drifted")
    for row in v043["calls"]:
        metadata = row["receipt"]["metadata"]
        phase = metadata.get("failure_phase")
        reason = metadata.get("failure_reason_code")
        _require(
            phase in allowlist and reason in allowlist[str(phase)],
            "v0.4.3 receipt phase/reason pair is not allowlisted",
        )

    checks = {
        "artifact_hash_maps_valid": True,
        "canonical_bundles_required": True,
        "deterministic_schedule_valid": True,
        "full_v0_4_3_block_absent": True,
        "pinned_hashes_valid": True,
        "post_freeze_runner_verified_from_preregistration_blob": True,
        "privacy_audit_valid": True,
        "r01_native_rows_not_reclassified": True,
        "receipt_cardinality_valid": True,
        "v0_4_3_phase_reason_allowlist_valid": True,
        "v0_4_3_post_freeze_coverage_lineage_valid": True,
        "v0_4_3_provider_receipts_unchanged_by_coverage_correction": True,
        "working_bundles_optional_for_clean_checkout": True,
        "working_canonical_byte_identity_valid_when_available": True,
        "zero_retry_valid": True,
    }
    return {
        "schema_version": "ebrt-provider-boundary-diagnostic-comparison-v0.4.3",
        "status": "COMPLETE_DIAGNOSTIC_NON_CAUSAL",
        "promotion_eligible": False,
        "generation": {
            "deterministic": True,
            "timestamp_recorded": False,
            "markdown_source": "comparison.json_only",
            "network_calls": 0,
        },
        "primary_metric": {
            "name": "classified_nonassessable_endpoints/all_nonassessable_endpoints",
            "definition": "Prospective native phase/reason coverage among each block's non-assessable arm endpoints.",
            "r01_frozen_native": _ratio(r01_classified, r01_nonassessable),
            "v0_4_3_contract_smoke": _ratio(v043_classified, v043_nonassessable),
        },
        "diagnostic_comparison": {
            "available": True,
            "cross_block_effect_estimate": None,
            "scope": "native_phase_reason_coverage_within_each_frozen_block",
        },
        "reasoning": {
            "comparison_available": False,
            "cross_block_effect_estimate": None,
            "raw_aperture_conclusion": "not_assessed_incomplete_or_subset_run",
            "revision_envelope_conclusion": "not_assessed_incomplete_or_subset_run",
        },
        "decision": {
            "bounded_smoke_level_decision": "The v0.4.3 boundary classified all eight non-assessable smoke endpoints with diagnostic integrity, but the failed smoke launch gate closed the full block and every reasoning conclusion.",
            "diagnostic_integrity_ready": True,
            "locked_reasoning_ready": False,
            "primary_execution_classification": "smoke_gate_failed_full_not_launched",
        },
        "inputs": {
            "r01_contract_smoke": {
                "canonical_path": _relative(R01_SMOKE_CANONICAL),
                "manifest_sha256": r01_smoke["manifest_sha256"],
                "status": r01_smoke["manifest"]["status"],
            },
            "r01_full": {
                "attempted_api_calls": r01["manifest"]["attempted_api_calls"],
                "canonical_path": _relative(R01_FULL_CANONICAL),
                "manifest_sha256": r01["manifest_sha256"],
                "non_assessable_endpoints": r01_nonassessable,
                "receipt_count": len(r01["calls"]),
                "schedule_sha256": r01_schedule,
                "status": r01["manifest"]["status"],
            },
            "v0_4_3_contract_smoke": {
                "attempted_api_calls": v043["manifest"]["attempted_api_calls"],
                "canonical_path": _relative(V043_SMOKE_CANONICAL),
                "diagnostic_integrity_ready": v043["manifest"]["diagnostic_integrity_ready"],
                "failure_counts_by_phase_and_reason": {
                    f"{phase}/{reason}": count
                    for (phase, reason), count in sorted(phase_reason.items())
                },
                "full_launch_ready": v043["manifest"]["full_launch_ready"],
                "manifest_sha256": v043["manifest_sha256"],
                "non_assessable_endpoints": v043_nonassessable,
                "receipt_count": len(v043["calls"]),
                "schedule_sha256": v043_schedule,
                "status": v043["manifest"]["status"],
            },
            "v0_4_3_full": {
                "executed": False,
                "reason": "contract_smoke_full_launch_ready_false",
            },
        },
        "verification": {
            "all_passed": all(checks.values()),
            "checks": checks,
            "input_artifact_sha256": {
                "r01_contract_smoke": r01_smoke["artifact_sha256"],
                "r01_full": r01["artifact_sha256"],
                "v0_4_3_contract_smoke": v043["artifact_sha256"],
            },
            "pinned_sha256": pins,
            "bundle_path_policy": {
                "canonical_bundles": "required_and_fully_validated",
                "working_bundles": "optional_but_byte_identical_when_present",
            },
            "source_pin_scope": {
                "v0_4_3_runner": "preregistration_commit_blob",
                "other_v0_4_3_boot_sources": "working_tree_and_preregistration_commit_blob",
            },
            "v0_4_3_derived_coverage_lineage": coverage_lineage,
        },
        "interpretation": [
            "The frozen r01 block natively classified 0 of 31 non-assessable endpoints at the prospective phase/reason boundary.",
            "The v0.4.3 smoke natively classified 8 of 8 non-assessable endpoints and retained diagnostic integrity.",
            "The v0.4.3 smoke failed its full-launch gate, so no v0.4.3 full block exists and no reasoning endpoint comparison is available.",
        ],
        "claim_boundary": [
            "The r01 rows remain frozen and are not retrospectively relabeled.",
            "r01 and v0.4.3 are independent stochastic blocks; the two proportions are descriptive and are not a causal instrumentation effect.",
            "The blocks have different declared populations: r01 is a 10-case by 3-trial full block, while v0.4.3 is a 2-case by 1-trial contract smoke.",
            "No quality, token, latency, failure-rate, or reasoning conclusion is assessed by this diagnostic comparison.",
            "This does not establish general reasoning improvement, provider-side root cause beyond typed observations, private chain-of-thought access, hidden-state editing, or model-weight change.",
        ],
    }


def render_markdown(comparison: Mapping[str, Any]) -> str:
    metric = comparison["primary_metric"]
    r01 = metric["r01_frozen_native"]
    v043 = metric["v0_4_3_contract_smoke"]
    smoke = comparison["inputs"]["v0_4_3_contract_smoke"]
    lines = [
        "# EBRT v0.4.2 r01 vs v0.4.3 provider-boundary diagnostic",
        "",
        f"Status: `{comparison['status']}`",
        "Scope: offline, deterministic, diagnostic-only artifact comparison.",
        f"Promotion eligible: `{str(comparison['promotion_eligible']).lower()}`",
        "",
        "## Primary metric",
        "",
        f"`{metric['name']}`",
        "",
        "| Frozen block | Native classified | Ratio |",
        "| --- | ---: | ---: |",
        f"| v0.4.2 r01 full | {r01['fraction']} | {r01['ratio']:.1f} |",
        f"| v0.4.3 contract smoke | {v043['fraction']} | {v043['ratio']:.1f} |",
        "",
        "The r01 numerator remains zero because its frozen rows do not contain",
        "the prospective v0.4.3 phase/reason fields. They were not relabeled.",
        "",
        "## v0.4.3 observed boundary",
        "",
    ]
    for phase_reason, count in smoke["failure_counts_by_phase_and_reason"].items():
        lines.append(f"- `{phase_reason}`: {count}")
    lines.extend(
        [
            "",
            f"- Diagnostic integrity ready: `{str(smoke['diagnostic_integrity_ready']).lower()}`",
            f"- Full launch ready: `{str(smoke['full_launch_ready']).lower()}`",
            "- Full block executed: `false`",
            "",
            "## Decision",
            "",
            comparison["decision"]["bounded_smoke_level_decision"],
            "",
            f"- Primary execution classification: `{comparison['decision']['primary_execution_classification']}`",
            f"- Locked reasoning ready: `{str(comparison['decision']['locked_reasoning_ready']).lower()}`",
            "- Cross-block diagnostic effect estimate: `null`",
            "- Cross-block reasoning effect estimate: `null`",
            f"- Raw-aperture conclusion: `{comparison['reasoning']['raw_aperture_conclusion']}`",
            f"- Revision-envelope conclusion: `{comparison['reasoning']['revision_envelope_conclusion']}`",
            "",
            "## Verification",
            "",
        ]
    )
    for name, passed in comparison["verification"]["checks"].items():
        lines.append(f"- `{name}`: `{str(bool(passed)).lower()}`")
    lines.extend(["", "## Interpretation", ""])
    for item in comparison["interpretation"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Claim boundary", ""])
    for item in comparison["claim_boundary"]:
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def _write() -> dict[str, Any]:
    comparison = build_comparison()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "comparison.json").write_bytes(_json_bytes(comparison))
    loaded = _load_json(OUTPUT / "comparison.json")
    (OUTPUT / "comparison_report.md").write_text(
        render_markdown(loaded), encoding="utf-8"
    )
    return comparison


def _validate_existing() -> dict[str, Any]:
    expected = build_comparison()
    actual = _load_json(OUTPUT / "comparison.json")
    _require(actual == expected, "canonical comparison JSON is stale")
    _require(
        (OUTPUT / "comparison.json").read_bytes() == _json_bytes(actual),
        "canonical comparison JSON encoding drifted",
    )
    _require(
        (OUTPUT / "comparison_report.md").read_text(encoding="utf-8")
        == render_markdown(actual),
        "comparison Markdown is not generated from canonical JSON",
    )
    return actual


def _self_test_optional_working_bundle(
    expected_comparison: Mapping[str, Any],
) -> dict[str, bool]:
    """Simulate clean checkout and reject canonical/optional-working tamper."""

    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        working_path_names = (
            "R01_SMOKE_WORKING",
            "R01_FULL_WORKING",
            "V043_SMOKE_WORKING",
            "V043_FULL_WORKING",
        )
        original_working_paths = {
            name: globals()[name] for name in working_path_names
        }
        try:
            for name in working_path_names:
                globals()[name] = root / "clean-checkout-absent" / name
            clean_checkout_comparison = build_comparison()
        finally:
            globals().update(original_working_paths)
        _require(
            clean_checkout_comparison == expected_comparison,
            "clean-checkout comparison differs without ignored working bundles",
        )

        canonical = root / "canonical"
        absent_working = root / "absent-working"
        shutil.copytree(V043_SMOKE_CANONICAL, canonical)

        canonical_only = _validate_bundle(
            canonical=canonical,
            working=absent_working,
            manifest_sha256=PINS["v043_smoke_manifest"],
        )
        _require(
            canonical_only["working_bundle_present"] is False
            and canonical_only["working_identity_checked"] is False
            and canonical_only["byte_identical_files"] is None,
            "absent optional working bundle was not treated as clean checkout",
        )

        working = root / "working"
        shutil.copytree(canonical, working)
        paired = _validate_bundle(
            canonical=canonical,
            working=working,
            manifest_sha256=PINS["v043_smoke_manifest"],
        )
        _require(
            paired["working_bundle_present"] is True
            and paired["working_identity_checked"] is True
            and all(paired["byte_identical_files"].values()),
            "available working bundle did not receive a strict identity audit",
        )

        (working / "benchmark_report.md").write_text(
            "working tamper\n", encoding="utf-8"
        )
        try:
            _validate_bundle(
                canonical=canonical,
                working=working,
                manifest_sha256=PINS["v043_smoke_manifest"],
            )
        except RuntimeError:
            pass
        else:
            raise AssertionError("available working-bundle tamper passed validation")

        shutil.rmtree(working)
        working.write_text("not a directory\n", encoding="utf-8")
        try:
            _validate_bundle(
                canonical=canonical,
                working=working,
                manifest_sha256=PINS["v043_smoke_manifest"],
            )
        except RuntimeError:
            pass
        else:
            raise AssertionError("malformed available working path was ignored")
        working.unlink()

        (canonical / "benchmark_report.md").write_text(
            "canonical tamper\n", encoding="utf-8"
        )
        try:
            _validate_bundle(
                canonical=canonical,
                working=absent_working,
                manifest_sha256=PINS["v043_smoke_manifest"],
            )
        except RuntimeError:
            pass
        else:
            raise AssertionError("canonical tamper passed clean-checkout validation")
    return {
        "available_working_identity_checked": True,
        "available_working_tamper_rejected": True,
        "canonical_only_clean_checkout_passed": True,
        "clean_checkout_comparison_is_deterministic": True,
        "canonical_tamper_rejected_without_working_bundle": True,
        "malformed_available_working_path_rejected": True,
    }


def _self_test_v043_coverage_tamper() -> dict[str, int | bool]:
    bundle = _validate_bundle(
        canonical=V043_SMOKE_CANONICAL,
        working=V043_SMOKE_WORKING,
        manifest_sha256=PINS["v043_smoke_manifest"],
    )
    _validate_v043_derived_coverage(bundle)
    tampers: list[dict[str, Any]] = []

    result_tamper = copy.deepcopy(bundle)
    result_tamper["results"]["summary"]["live_receipt_validation"][
        "contract_smoke_exact_coverage"
    ] = False
    tampers.append(result_tamper)

    manifest_tamper = copy.deepcopy(bundle)
    manifest_tamper["manifest"]["contract_smoke_exact_coverage"] = False
    tampers.append(manifest_tamper)

    lineage_tamper = copy.deepcopy(bundle)
    lineage_tamper["manifest"]["derived_artifact_lineage"]["no_live_call"] = False
    tampers.append(lineage_tamper)

    for tampered in tampers:
        try:
            _validate_v043_derived_coverage(tampered)
        except RuntimeError:
            pass
        else:
            raise AssertionError("v0.4.3 derived coverage tamper passed validation")
    return {
        "authoritative_exact_coverage_passed": True,
        "tamper_cases_rejected": len(tampers),
    }


def _self_test() -> dict[str, Any]:
    first = build_comparison()
    second = build_comparison()
    _require(first == second, "comparison projection is not deterministic")
    _require(_json_bytes(first) == _json_bytes(second), "JSON bytes are not deterministic")
    _require(_ratio(0, 0)["ratio"] is None, "zero-denominator ratio must be null")
    _require(_ratio(0, 0)["defined"] is False, "zero denominator must be undefined")
    _require(_ratio(1, 4)["ratio"] == 0.25, "ratio arithmetic drifted")
    _require(_ratio(1, 4)["defined"] is True, "nonzero denominator must be defined")
    _require(first["promotion_eligible"] is False, "comparison cannot promote")
    _require(
        first["diagnostic_comparison"]["cross_block_effect_estimate"] is None,
        "diagnostic cross-block effect must remain null",
    )
    _require(
        first["reasoning"]["cross_block_effect_estimate"] is None
        and first["reasoning"]["comparison_available"] is False,
        "reasoning comparison gate drifted",
    )
    _require(
        first["reasoning"]["raw_aperture_conclusion"]
        == "not_assessed_incomplete_or_subset_run"
        and first["reasoning"]["revision_envelope_conclusion"]
        == "not_assessed_incomplete_or_subset_run",
        "within-block reasoning conclusions drifted",
    )
    _require(
        first["decision"]["primary_execution_classification"]
        == "smoke_gate_failed_full_not_launched"
        and first["decision"]["locked_reasoning_ready"] is False
        and first["decision"]["diagnostic_integrity_ready"] is True,
        "bounded decision fields drifted",
    )
    optional_working = _self_test_optional_working_bundle(first)
    coverage_tamper = _self_test_v043_coverage_tamper()
    if OUTPUT.exists():
        _validate_existing()
    return {
        "status": "PASS",
        "network_calls": 0,
        "primary_metric": first["primary_metric"],
        "optional_working_bundle": optional_working,
        "v0_4_3_coverage_tamper": coverage_tamper,
        "verification_checks": len(first["verification"]["checks"]),
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build", "self-test", "validate"))
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.command == "build":
        result = _write()
    elif args.command == "validate":
        result = _validate_existing()
    else:
        result = _self_test()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
