#!/usr/bin/env python3
"""Split-artifact benchmark surface for EBRT v0.5.5 lane composition."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

import lane_composable_trajectory_v0_5_5 as core


ROOT = Path(__file__).resolve().parent
ARTIFACT_KEYS = (
    "shared_evidence_ledger",
    "sealed_bundle",
    "merge_contract",
    "bundle_control_map",
    "block_adjoint_audit",
    "hard_gate_audit",
    "self_test",
)
REQUIRED_ALIAS_SUBCHECKS = (
    "all_six_lane_permutations_invariant",
    "artifact_tamper_rejected",
    "conflicting_axis_target_rejected",
    "conflicting_evidence_hash_rejected",
    "duplicate_lane_alias_rejected",
    "forbidden_schema_surface_rejected",
    "provider_calls_zero",
    "socket_denied",
    "source_tamper_rejected",
    "two_build_byte_identical",
)


def _clone(value: Any) -> Any:
    return json.loads(core.canonical_json_bytes(value))


def _seal(value: Mapping[str, Any]) -> dict[str, Any]:
    payload = _clone(value)
    payload["fingerprint_sha256"] = core.fingerprint(payload)
    return payload


def _require_canonical_fixture(path: Path, expected: Path) -> dict[str, Any]:
    observed = core.load_fixture(path)
    canonical = core.load_fixture(expected)
    if core.canonical_json_bytes(observed) != core.canonical_json_bytes(canonical):
        raise core.LaneCompositionValidationError(
            f"benchmark fixture differs from pinned canonical bytes: {path}"
        )
    return observed


def build_artifact_payloads(
    composition_fixture_path: Path = core.DEFAULT_FIXTURE,
    one_lane_fixture_path: Path = core.DEFAULT_ONE_LANE_FIXTURE,
    *,
    _validate: bool = True,
) -> dict[str, dict[str, Any]]:
    composition_fixture_path = Path(composition_fixture_path)
    one_lane_fixture_path = Path(one_lane_fixture_path)
    _require_canonical_fixture(composition_fixture_path, core.DEFAULT_FIXTURE)
    _require_canonical_fixture(one_lane_fixture_path, core.DEFAULT_ONE_LANE_FIXTURE)
    bundle = core.build_bundle(composition_fixture_path)
    self_test = core.self_test()
    aliases = dict(self_test["subchecks"])
    if set(aliases) != set(REQUIRED_ALIAS_SUBCHECKS):
        raise core.LaneCompositionValidationError("benchmark alias subcheck IDs drift")
    sealed_lane_receipts = {
        row["lane_id"]: {
            "bytes": len(core.LANE_PATHS[row["lane_id"]].read_bytes()),
            "sealed_lane_fingerprint_sha256": row[
                "sealed_lane_fingerprint_sha256"
            ],
            "sha256": row["immutable_source_bytes_sha256"],
            "source_path": row["source_path"],
        }
        for row in bundle["lanes"]
    }

    payloads: dict[str, dict[str, Any]] = {
        "shared_evidence_ledger": _seal(
            {
                "ledger": bundle["shared_evidence_ledger"],
                "network_calls": 0,
                "provider_calls": 0,
                "schema_version": "ebrt-shared-evidence-ledger-artifact-v0.5.5",
            }
        ),
        "sealed_bundle": _seal(
            {
                "decision_status": bundle["decision_status"],
                "fixture_id": bundle["fixture_id"],
                "junction_count": bundle["junction"]["junction_count"],
                "lane_ids": [row["lane_id"] for row in bundle["lanes"]],
                "network_calls": 0,
                "one_lane_equivalence": bundle["one_lane_equivalence"],
                "promotion_ready": bundle["promotion_ready"],
                "provider_calls": 0,
                "schema_version": "ebrt-sealed-lane-composition-bundle-v0.5.5",
                "sealed_lane_receipts": sealed_lane_receipts,
                "source_bundle_fingerprint_sha256": bundle["fingerprint_sha256"],
                "source_gate": bundle["source_gate"],
            }
        ),
        "merge_contract": _seal(
            {
                "contract": bundle["junction"],
                "controlled_evaluation": bundle["controlled_evaluation"],
                "network_calls": 0,
                "neutral_evaluation": bundle["neutral_evaluation"],
                "provider_calls": 0,
                "schema_version": "ebrt-lane-merge-contract-artifact-v0.5.5",
            }
        ),
        "bundle_control_map": _seal(
            {
                "control_bundle": bundle["control_bundle"],
                "network_calls": 0,
                "provider_calls": 0,
                "schema_version": "ebrt-lane-control-bundle-artifact-v0.5.5",
            }
        ),
        "block_adjoint_audit": _seal(
            {
                "audit": bundle["block_adjoint_audit"],
                "disconnected_audit": bundle["disconnected_audit"],
                "network_calls": 0,
                "permutation_audit": bundle["permutation_audit"],
                "provider_calls": 0,
                "schema_version": "ebrt-block-adjoint-audit-artifact-v0.5.5",
            }
        ),
        "hard_gate_audit": _seal(
            {
                "core_gate_audit_fingerprint_sha256": bundle["gates"][
                    "fingerprint_sha256"
                ],
                "decision_status": bundle["decision_status"],
                "network_calls": 0,
                "promotion_ready": bundle["promotion_ready"]
                and self_test["promotion_ready"],
                "provider_calls": 0,
                "schema_version": "ebrt-lane-composition-hard-gate-audit-v0.5.5",
                "status": (
                    "PASS"
                    if bundle["gates"]["status"] == "PASS"
                    and self_test["status"] == "PASS"
                    and all(aliases.values())
                    else "FAIL"
                ),
                "subchecks": aliases,
                "top_level_gates": bundle["gates"]["top_level_gates"],
            }
        ),
        "self_test": _clone(self_test),
    }
    if _validate:
        validate_artifact_payloads(
            payloads,
            composition_fixture_path=composition_fixture_path,
            one_lane_fixture_path=one_lane_fixture_path,
            exact_rederive=False,
        )
    return payloads


def validate_artifact_payloads(
    payloads: Mapping[str, Any],
    *,
    composition_fixture_path: Path = core.DEFAULT_FIXTURE,
    one_lane_fixture_path: Path = core.DEFAULT_ONE_LANE_FIXTURE,
    exact_rederive: bool = True,
) -> None:
    if set(payloads) != set(ARTIFACT_KEYS):
        raise core.LaneCompositionValidationError(
            f"split artifact keys differ: {sorted(payloads)}"
        )
    for key in ARTIFACT_KEYS:
        payload = payloads[key]
        if not isinstance(payload, Mapping):
            raise core.LaneCompositionValidationError(f"split artifact {key} must be object")
        if payload.get("network_calls") != 0 or payload.get("provider_calls") != 0:
            raise core.LaneCompositionValidationError(
                f"split artifact {key} is not network/provider zero"
            )
        if payload.get("fingerprint_sha256") != core.fingerprint(
            {name: _clone(value) for name, value in payload.items() if name != "fingerprint_sha256"}
        ):
            raise core.LaneCompositionValidationError(
                f"split artifact {key} fingerprint mismatch"
            )
    ledger = payloads["shared_evidence_ledger"]["ledger"]
    core.validate_evidence_ledger(ledger)
    control = payloads["bundle_control_map"]["control_bundle"]
    core.validate_control_bundle(control)
    hard = payloads["hard_gate_audit"]
    if set(hard["top_level_gates"]) != set(core.HARD_GATE_IDS) or not all(
        hard["top_level_gates"].values()
    ):
        raise core.LaneCompositionValidationError("split hard gate top-level mismatch")
    if set(hard["subchecks"]) != set(REQUIRED_ALIAS_SUBCHECKS) or not all(
        hard["subchecks"].values()
    ):
        raise core.LaneCompositionValidationError("split hard gate aliases mismatch")
    if (
        hard["status"] != "PASS"
        or hard["promotion_ready"] is not True
        or hard["decision_status"] != core.PROMOTE_STATUS
    ):
        raise core.LaneCompositionValidationError("split hard gate did not promote")
    if exact_rederive:
        expected = build_artifact_payloads(
            composition_fixture_path,
            one_lane_fixture_path,
            _validate=False,
        )
        if core.canonical_json_bytes(payloads) != core.canonical_json_bytes(expected):
            raise core.LaneCompositionValidationError(
                "split artifacts differ from independent pinned rederivation"
            )


def benchmark() -> dict[str, Any]:
    payloads = build_artifact_payloads()
    return {
        "artifact_fingerprints": {
            key: payloads[key]["fingerprint_sha256"] for key in ARTIFACT_KEYS
        },
        "decision_status": payloads["hard_gate_audit"]["decision_status"],
        "network_calls": 0,
        "promotion_ready": payloads["hard_gate_audit"]["promotion_ready"],
        "provider_calls": 0,
        "status": payloads["hard_gate_audit"]["status"],
    }


def _pretty(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("run")
    subparsers.add_parser("self-test")
    args = parser.parse_args(argv)
    if args.command == "run":
        result = benchmark()
    else:
        result = core.self_test()
    print(_pretty(result), end="")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
