#!/usr/bin/env python3
"""Build and validate the EBRT v0.5.4 temporal-lineage benchmark payloads."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

import temporal_adjoint_lineage_v0_5_4 as core


PAYLOAD_KEYS = {
    "actuator_geometry",
    "arm_comparison",
    "compiled_programs",
    "correction_early_sealed_lane",
    "correction_late_sealed_lane",
    "no_event_audit",
    "self_test",
    "stable_constraint_sealed_lane",
}


def _seal(value: dict[str, Any]) -> dict[str, Any]:
    value["fingerprint_sha256"] = core.fingerprint(value)
    return value


def build_artifact_payloads(
    event_fixture_path: Path = core.DEFAULT_EVENT_FIXTURE,
    no_event_fixture_path: Path = core.DEFAULT_NO_EVENT_FIXTURE,
) -> dict[str, Any]:
    event_fixture = core.load_fixture(event_fixture_path)
    no_event_fixture = core.load_fixture(no_event_fixture_path, no_event=True)
    event_program = core.compile_program(event_fixture)
    no_event_program = core.compile_program(no_event_fixture, no_event=True)
    early = core.evaluate_lane(event_program, "correction_early")
    late = core.evaluate_lane(event_program, "correction_late")
    no_event_audit, stable_lane = core.run_no_event_audit(no_event_fixture)
    test = core.self_test(
        event_fixture_path=event_fixture_path,
        no_event_fixture_path=no_event_fixture_path,
        event_program=event_program,
        evaluations={"correction_early": early, "correction_late": late},
        no_event_result=(no_event_audit, stable_lane),
    )
    compiled_programs = _seal(
        {
            "closure_fingerprint_sha256": event_program.closure[
                "fingerprint_sha256"
            ],
            "event_program": core.program_receipt(event_program),
            "graph_fingerprint_sha256": event_program.graph[
                "fingerprint_sha256"
            ],
            "network_calls": 0,
            "no_event_program": core.program_receipt(no_event_program),
            "provider_calls": 0,
            "schema_version": "ebrt-temporal-lineage-suite-v0.5.4",
            "source_regression_fingerprint_sha256": (
                event_program.regression_fingerprint_sha256
            ),
            "state_axis_order": ["channel", "evidence", "node"],
        }
    )
    actuator_geometry = _seal(
        {
            "lanes": {
                "correction_early": early.geometry,
                "correction_late": late.geometry,
            },
            "network_calls": 0,
            "provider_calls": 0,
            "schema_version": core.GEOMETRY_SCHEMA_VERSION,
        }
    )
    lane_comparisons = {
        "correction_early": early.comparison,
        "correction_late": late.comparison,
    }
    promoted = bool(test["promotion_ready"])
    decision_status = core.PROMOTION_STATUS if promoted else core.STOP_STATUS
    arm_comparison = _seal(
        {
            "decision_status": decision_status,
            "hard_gates": dict(test["hard_gates"]),
            "lanes": lane_comparisons,
            "network_calls": 0,
            "promotion": {
                "eligible_for_v0_5_5": promoted,
                "stop_rule": None if promoted else core.STOP_STATUS,
            },
            "promotion_ready": promoted,
            "provider_calls": 0,
            "schema_version": core.COMPARISON_SCHEMA_VERSION,
            "status": "PASS" if promoted else "FAIL",
        }
    )
    payloads = {
        "actuator_geometry": actuator_geometry,
        "arm_comparison": arm_comparison,
        "compiled_programs": compiled_programs,
        "correction_early_sealed_lane": early.sealed_lane,
        "correction_late_sealed_lane": late.sealed_lane,
        "no_event_audit": no_event_audit,
        "self_test": test,
        "stable_constraint_sealed_lane": stable_lane,
    }
    validate_artifact_payloads(payloads)
    return payloads


def _ensure_finite(value: Any, path: str = "$") -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise core.TemporalAdjointValidationError(f"non-finite payload value at {path}")
    if isinstance(value, Mapping):
        for key, child in value.items():
            if not isinstance(key, str):
                raise core.TemporalAdjointValidationError(f"non-string key at {path}")
            _ensure_finite(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _ensure_finite(child, f"{path}[{index}]")


def validate_artifact_payloads(payloads: Mapping[str, Any]) -> None:
    if not isinstance(payloads, Mapping) or set(payloads) != PAYLOAD_KEYS:
        raise core.TemporalAdjointValidationError("artifact payload key set mismatch")
    _ensure_finite(payloads)
    if payloads["self_test"].get("status") != "PASS":
        raise core.TemporalAdjointValidationError("self-test payload is not PASS")
    for key in (
        "correction_early_sealed_lane",
        "correction_late_sealed_lane",
        "stable_constraint_sealed_lane",
    ):
        if payloads[key].get("schema_version") != core.LANE_SCHEMA_VERSION:
            raise core.TemporalAdjointValidationError(f"sealed lane schema mismatch: {key}")
        if payloads[key].get("status") != "PASS":
            raise core.TemporalAdjointValidationError(f"sealed lane failed: {key}")
    if payloads["no_event_audit"].get("status") != "PASS":
        raise core.TemporalAdjointValidationError("no-event audit failed")
    comparison = payloads["arm_comparison"]
    if comparison.get("schema_version") != core.COMPARISON_SCHEMA_VERSION:
        raise core.TemporalAdjointValidationError("comparison schema mismatch")
    if comparison.get("status") != "PASS":
        raise core.TemporalAdjointValidationError("temporal promotion gate failed")
    if set(comparison.get("hard_gates", {})) != set(core.HARD_GATE_IDS):
        raise core.TemporalAdjointValidationError("hard-gate identifier set drift")
    if not all(comparison["hard_gates"].values()):
        raise core.TemporalAdjointValidationError("one or more temporal hard gates failed")
    if comparison.get("promotion_ready") is not True:
        raise core.TemporalAdjointValidationError("promotion_ready must be true")
    if comparison.get("decision_status") != core.PROMOTION_STATUS:
        raise core.TemporalAdjointValidationError("promotion decision status drift")
    for lane_id, lane_comparison in comparison.get("lanes", {}).items():
        sham_audit = lane_comparison.get("sham_geometry_audit", {})
        if sham_audit.get("status") != "PASS":
            raise core.TemporalAdjointValidationError(
                f"sham geometry audit failed: {lane_id}"
            )
        if not all(sham_audit.get("family_gates", {}).values()):
            raise core.TemporalAdjointValidationError(
                f"sham family invariant failed: {lane_id}"
            )
        if not sham_audit.get("per_sham") or not all(
            row.get("status") == "PASS"
            for row in sham_audit["per_sham"].values()
        ):
            raise core.TemporalAdjointValidationError(
                f"per-sham invariant failed: {lane_id}"
            )
    if comparison.get("promotion") != {
        "eligible_for_v0_5_5": True,
        "stop_rule": None,
    }:
        raise core.TemporalAdjointValidationError("promotion/stop rule drift")
    self_test = payloads["self_test"]
    if self_test.get("hard_gates") != comparison["hard_gates"]:
        raise core.TemporalAdjointValidationError("self-test hard gates drift")
    if self_test.get("promotion_ready") is not comparison["promotion_ready"]:
        raise core.TemporalAdjointValidationError("self-test promotion state drift")
    if payloads["no_event_audit"].get("exact_identity") is not True:
        raise core.TemporalAdjointValidationError("no-event exact identity missing")
    if (
        payloads["no_event_audit"].get("recurrence_zero_delta_exact_zero")
        is not True
    ):
        raise core.TemporalAdjointValidationError(
            "no-event recurrence identity missing"
        )
    for name, value in payloads.items():
        if value.get("network_calls") != 0 or value.get("provider_calls") != 0:
            raise core.TemporalAdjointValidationError(
                f"payload boundary counters drift: {name}"
            )


def _pretty(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=("benchmark", "self-test", "validate"), nargs="?", default="benchmark"
    )
    parser.add_argument("--event-fixture", type=Path, default=core.DEFAULT_EVENT_FIXTURE)
    parser.add_argument("--no-event-fixture", type=Path, default=core.DEFAULT_NO_EVENT_FIXTURE)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "self-test":
        result = core.self_test(
            event_fixture_path=args.event_fixture,
            no_event_fixture_path=args.no_event_fixture,
        )
        print(_pretty(result), end="")
        return 0 if result["status"] == "PASS" else 1
    payloads = build_artifact_payloads(args.event_fixture, args.no_event_fixture)
    if args.command == "validate":
        validate_artifact_payloads(payloads)
        print(_pretty({"payload_keys": sorted(payloads), "status": "PASS"}), end="")
    else:
        print(_pretty(payloads), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
