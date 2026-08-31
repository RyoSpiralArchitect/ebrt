#!/usr/bin/env python3
"""Derive the post-review interpretation receipt for the frozen v0.8.4 run.

The original runner, policy lock, provider outputs, grades, and portable
verification remain immutable.  This script narrows only the interpretation:

* the flat/typed contrast bundled a field-layout change with typed-only
  support-selection guidance, so it does not identify field factorization;
* a model enters the algorithm-quality denominator only when every task arm
  parses for every case.  Partial surfaces remain interface diagnostics.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from ebrt_core import (
    EBRTError,
    _canonical_bytes,
    _seal,
    _sealed_snapshot,
)
from typed_revision_channel_canary_v0_8_4 import (
    ARM_IDS,
    ARM_ROLE_TYPED,
    RUN_SCHEMA_VERSION,
    build_cases,
    build_invocations,
    compile_case,
    verify_run,
)


INTERPRETATION_SCHEMA_VERSION = (
    "ebrt-typed-revision-channel-post-review-interpretation-v0.8.4"
)
SOURCE_RUN_FINGERPRINT = (
    "2a4dfc288e85c9fd26f73eac37f37e4e8068194067b267709cd2b1ec4ff94d95"
)
SOURCE_RESULTS_SHA256 = (
    "55a1fb8b11c49cfa69b074916ec2bee18e52bd7e18a2635070f8e510651f4fc6"
)
TYPED_ONLY_SCORED_GUIDANCE = (
    "Keep stable constraints out of SUPPORT unless they directly determine ANSWER."
)

JsonObject = dict[str, Any]


def _load_json(path: Path, code: str) -> JsonObject:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise EBRTError(code) from error
    if not isinstance(value, dict):
        raise EBRTError(code)
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _source_sha256(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as error:
        raise EBRTError("V084_INTERPRETATION_SOURCE_READ_FAILED") from error


def _prompt_contrast_audit() -> JsonObject:
    audited_cases = 0
    for case in build_cases():
        program, _receipt = compile_case(case)
        invocations = build_invocations(case, program)
        for arm_id in ("direct_flat", "role_flat"):
            if TYPED_ONLY_SCORED_GUIDANCE in invocations[arm_id]["prompt"]:
                raise EBRTError("V084_INTERPRETATION_FLAT_GUIDANCE_UNEXPECTED")
        for arm_id in ("direct_typed", ARM_ROLE_TYPED):
            if TYPED_ONLY_SCORED_GUIDANCE not in invocations[arm_id]["prompt"]:
                raise EBRTError("V084_INTERPRETATION_TYPED_GUIDANCE_MISSING")
        audited_cases += 1
    return {
        "audited_case_count": audited_cases,
        "scored_guidance_symmetric": False,
        "typed_only_scored_guidance": [TYPED_ONLY_SCORED_GUIDANCE],
        "contrast_scope": "BUNDLED_OUTPUT_INTERFACE_AND_SUPPORT_GUIDANCE",
        "pure_field_factorization_effect_status": "NOT_IDENTIFIED",
    }


def _counts_for_runs(runs: Sequence[Mapping[str, Any]]) -> JsonObject:
    strict = {arm_id: 0 for arm_id in ARM_IDS}
    parsed = {arm_id: 0 for arm_id in ARM_IDS}
    cells = 0
    for run in runs:
        for cell in run["cases"]:
            cells += 1
            for arm_id in ARM_IDS:
                arm = cell["arms"][arm_id]
                parsed[arm_id] += arm["result"]["status"] == "PARSED"
                strict[arm_id] += arm["semantic_grade"]["status"] == "PASS"
    return {
        "model_count": len(runs),
        "case_count": cells,
        "parsed_outputs": parsed,
        "strict_passes": strict,
        "denominator_cells_per_arm": cells,
    }


def build_interpretation(
    source: Mapping[str, Any],
    lock: Mapping[str, Any],
    *,
    source_results_sha256: str,
) -> JsonObject:
    snapshot = _sealed_snapshot(source, "V084_INTERPRETATION_SOURCE")
    if (
        snapshot.get("schema_version") != RUN_SCHEMA_VERSION
        or snapshot.get("fingerprint_sha256") != SOURCE_RUN_FINGERPRINT
        or source_results_sha256 != SOURCE_RESULTS_SHA256
    ):
        raise EBRTError("V084_INTERPRETATION_SOURCE_IDENTITY_MISMATCH")

    source_verification = verify_run(snapshot, lock)
    case_count = len(build_cases())
    model_scopes: list[JsonObject] = []
    admitted_runs: list[Mapping[str, Any]] = []
    interface_runs: list[Mapping[str, Any]] = []
    for run in snapshot["runs"]:
        model_id = run["model_adapter"]["model_id"]
        parsed = {
            arm_id: sum(
                cell["arms"][arm_id]["result"]["status"] == "PARSED"
                for cell in run["cases"]
            )
            for arm_id in ARM_IDS
        }
        literal_ready = run["readiness"]["status"] == "PASS"
        full_factorial_ready = (
            literal_ready
            and len(run["cases"]) == case_count
            and all(parsed[arm_id] == case_count for arm_id in ARM_IDS)
        )
        typed_task_ready = all(
            parsed[arm_id] == case_count
            for arm_id in ("direct_typed", ARM_ROLE_TYPED)
        )
        if full_factorial_ready:
            scope = "FULL_FACTORIAL_ALGORITHM_DIAGNOSTIC"
            admitted_runs.append(run)
        else:
            scope = "PARTIAL_INTERFACE_DIAGNOSTIC"
            interface_runs.append(run)
        model_scopes.append(
            {
                "model_id": model_id,
                "literal_readiness_status": run["readiness"]["status"],
                "parsed_outputs": parsed,
                "task_shaped_typed_channel_ready": typed_task_ready,
                "interpretation_scope": scope,
            }
        )

    mechanically_graded = _counts_for_runs(snapshot["runs"])
    algorithm_diagnostic = _counts_for_runs(admitted_runs)
    return _seal(
        {
            "schema_version": INTERPRETATION_SCHEMA_VERSION,
            "status": "PASS_WITH_NARROWED_INTERPRETATION",
            "source": {
                "run_fingerprint_sha256": snapshot["fingerprint_sha256"],
                "results_file_sha256": source_results_sha256,
                "policy_lock_fingerprint_sha256": snapshot[
                    "policy_lock_fingerprint_sha256"
                ],
                "portable_verification_fingerprint_sha256": source_verification[
                    "fingerprint_sha256"
                ],
                "original_artifact_mutated": False,
            },
            "review_findings": {
                "schema_contrast_prompt_symmetry": "ORIGINAL_LOCKED_DESIGN_ASYMMETRIC",
                "algorithm_diagnostic_admission": "CORRECTED_POST_REVIEW",
            },
            "prompt_contrast_audit": _prompt_contrast_audit(),
            "model_scopes": model_scopes,
            "mechanically_graded_all_cells": mechanically_graded,
            "algorithm_diagnostic_surface": algorithm_diagnostic,
            "interface_diagnostic_surface": _counts_for_runs(interface_runs),
            "corrected_counts": {
                "literal_ready_models": sum(
                    row["literal_readiness_status"] == "PASS"
                    for row in model_scopes
                ),
                "full_factorial_algorithm_diagnostic_models": len(admitted_runs),
                "partial_interface_diagnostic_models": len(interface_runs),
            },
            "interpretation": [
                "All-cell counts are mechanical grades, not a cross-model algorithm-quality denominator.",
                "Only full-factorial task-shaped parse surfaces enter the algorithm diagnostic; Qwen typed failures remain adapter/interface evidence.",
                "The positive controlled repair is one Mistral cell within a bundled output-interface and support-guidance contrast.",
                "Field factorization alone, causal superiority, and general reasoning improvement remain not identified.",
            ],
        }
    )


def verify_interpretation(
    receipt: Mapping[str, Any],
    source: Mapping[str, Any],
    lock: Mapping[str, Any],
    *,
    source_results_sha256: str,
) -> JsonObject:
    observed = _sealed_snapshot(receipt, "V084_INTERPRETATION_RECEIPT")
    expected = build_interpretation(
        source, lock, source_results_sha256=source_results_sha256
    )
    if _canonical_bytes(observed) != _canonical_bytes(expected):
        raise EBRTError("V084_INTERPRETATION_RECEIPT_MISMATCH")
    return _seal(
        {
            "schema_version": "ebrt-v0.8.4-post-review-verification-v1",
            "status": "PASS",
            "receipt_fingerprint_sha256": observed["fingerprint_sha256"],
            "source_run_fingerprint_sha256": SOURCE_RUN_FINGERPRINT,
        }
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("build", "verify"):
        command = commands.add_parser(name)
        command.add_argument("--source", type=Path, required=True)
        command.add_argument("--lock", type=Path, required=True)
        if name == "build":
            command.add_argument("--output", type=Path, required=True)
        else:
            command.add_argument("--receipt", type=Path, required=True)
    commands.add_parser("self-test")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    default_source = Path("artifacts/typed_revision_channel_v0_8_4/r01/results.json")
    default_lock = Path("policy_lock_typed_revision_channel_v0_8_4.json")
    try:
        source_path = default_source if args.command == "self-test" else args.source
        lock_path = default_lock if args.command == "self-test" else args.lock
        source = _load_json(source_path, "V084_INTERPRETATION_SOURCE_READ_FAILED")
        lock = _load_json(lock_path, "V084_INTERPRETATION_LOCK_READ_FAILED")
        source_sha256 = _source_sha256(source_path)
        if args.command == "verify":
            receipt = _load_json(
                args.receipt, "V084_INTERPRETATION_RECEIPT_READ_FAILED"
            )
            result = verify_interpretation(
                receipt, source, lock, source_results_sha256=source_sha256
            )
        else:
            result = build_interpretation(
                source, lock, source_results_sha256=source_sha256
            )
            if args.command == "build":
                _write_json(args.output, result)
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except EBRTError as error:
        print(json.dumps({"status": "ERROR", "error_code": str(error)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
