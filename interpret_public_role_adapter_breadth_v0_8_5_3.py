#!/usr/bin/env python3
"""Interpret sealed v0.8.5.3 breadth results without another model call."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from ebrt_core import EBRTError, SharedMLXRuntime, _seal
import public_role_adapter_breadth_v0_8_5_3 as current


SCHEMA_VERSION = "ebrt-public-role-adapter-breadth-interpretation-v0.8.5.3"

CLAIM_BOUNDARY = (
    "This is a post-run interpretation of a contaminated adapter-breadth canary, not a fresh benchmark.",
    "No model call is made by this interpreter; tokenizer configuration is inspected locally and hashed.",
    "Absence of a chat template under a locked chat-template rendering mode is a static adapter mismatch, not evidence of weak model reasoning.",
    "The public MLX_GENERATION_FAILED code intentionally does not expose its underlying exception, so runtime-failure causal attribution remains not assessed.",
    "Models with no admitted cells contribute no direct/control or algorithm-quality denominator.",
    "No gradient crosses a model adapter, and no causal, model-ranking, general-quality, or cross-model claim is admitted.",
)

JsonObject = dict[str, Any]


def _load(path: Path, code: str) -> JsonObject:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise EBRTError(code) from error
    if not isinstance(value, dict):
        raise EBRTError(code)
    return value


def _chat_template_present(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return bool(value)
    return False


def _static_adapter_preflight(
    model_path: str,
    *,
    locked_prompt_mode: str,
) -> JsonObject:
    """Inspect local tokenizer metadata without loading or running the model."""

    runtime = SharedMLXRuntime(
        model_path,
        max_tokens=current.DEFAULT_MAX_TOKENS,
        seed=0,
        prompt_rendering_mode=locked_prompt_mode,  # type: ignore[arg-type]
    )
    config_path = runtime.model_path / "tokenizer_config.json"
    try:
        raw = config_path.read_bytes()
        value = json.loads(raw)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise EBRTError("V0853_INTERPRET_TOKENIZER_CONFIG_INVALID") from error
    if not isinstance(value, dict):
        raise EBRTError("V0853_INTERPRET_TOKENIZER_CONFIG_INVALID")
    present = _chat_template_present(value.get("chat_template"))
    mismatch = locked_prompt_mode == "chat_template" and not present
    return _seal(
        {
            "model_id": runtime.model_id,
            "tokenizer_config_sha256": hashlib.sha256(raw).hexdigest(),
            "chat_template_present": present,
            "locked_prompt_rendering_mode": locked_prompt_mode,
            "static_adapter_mismatch": mismatch,
            "static_compatibility_status": (
                "CHAT_TEMPLATE_ABSENT_UNDER_LOCKED_CHAT_TEMPLATE_MODE"
                if mismatch
                else "NO_STATIC_CHAT_TEMPLATE_MISMATCH_OBSERVED"
            ),
        }
    )


def _semantic_effect_status(rows: Sequence[Mapping[str, Any]]) -> str:
    admitted = [row for row in rows if row["admitted_to_regression"]]
    if not admitted:
        return "NOT_ASSESSED_NO_ADMITTED_CELLS"
    if any(row["raw_output_diff_cells"] > 0 for row in admitted):
        return "RAW_DIFFERENCE_OBSERVED_REQUIRES_CELL_INTERPRETATION"
    return "NULL_RAW_DIFFERENCE_ON_ADMITTED_MODELS"


def interpret(
    result: Mapping[str, Any],
    lock: Mapping[str, Any],
    model_paths: Sequence[str],
) -> JsonObject:
    locked = current.validate_lock(lock)
    verification = current.verify_run(result, locked)
    locked_mode = locked["execution_policy"]["prompt_rendering_mode"]
    if type(locked_mode) is not str:
        raise EBRTError("V0853_INTERPRET_PROMPT_MODE_INVALID")

    preflights = [
        _static_adapter_preflight(path, locked_prompt_mode=locked_mode)
        for path in model_paths
    ]
    preflight_by_model = {row["model_id"]: row for row in preflights}
    if len(preflight_by_model) != len(preflights):
        raise EBRTError("V0853_INTERPRET_MODEL_DUPLICATE")
    if set(preflight_by_model) != set(locked["model_ids"]):
        raise EBRTError("V0853_INTERPRET_MODEL_SET_MISMATCH")

    rows: list[JsonObject] = []
    observed_model_ids: set[str] = set()
    for run in result["runs"]:
        model_id = run["model_adapter"]["model_id"]
        if model_id in observed_model_ids or model_id not in preflight_by_model:
            raise EBRTError("V0853_INTERPRET_RESULT_MODEL_INVALID")
        observed_model_ids.add(model_id)
        readiness = run["readiness"]
        format_ready = readiness["format_ready"]
        task_ready = readiness["task_channel_ready"]
        cases = run["cases"]
        rows.append(
            _seal(
                {
                    "model_id": model_id,
                    "format_status": format_ready["status"],
                    "format_error_code": format_ready["error_code"],
                    "task_status": task_ready["status"],
                    "task_result_status": task_ready["result"]["status"],
                    "task_error_code": task_ready["result"]["error_code"],
                    "admitted_to_regression": run["summary"][
                        "admitted_to_regression"
                    ],
                    "case_count": len(cases),
                    "raw_output_diff_cells": run["summary"][
                        "raw_output_diff_cells"
                    ],
                    "static_adapter_preflight": preflight_by_model[model_id],
                }
            )
        )
    if observed_model_ids != set(locked["model_ids"]):
        raise EBRTError("V0853_INTERPRET_RESULT_MODEL_SET_MISMATCH")

    admitted_models = sum(row["admitted_to_regression"] for row in rows)
    both_static_mismatch = bool(rows) and all(
        row["static_adapter_preflight"]["static_adapter_mismatch"]
        for row in rows
    )
    all_public_errors = bool(rows) and all(
        row["format_error_code"] == "MLX_GENERATION_FAILED"
        and row["task_error_code"] == "MLX_GENERATION_FAILED"
        for row in rows
    )
    return _seal(
        {
            "schema_version": SCHEMA_VERSION,
            "status": "PASS",
            "run_fingerprint_sha256": result["fingerprint_sha256"],
            "verification_fingerprint_sha256": verification[
                "fingerprint_sha256"
            ],
            "lock_fingerprint_sha256": locked["fingerprint_sha256"],
            "model_rows": rows,
            "summary": {
                "model_count": len(rows),
                "format_ready_models": sum(
                    row["format_status"] == "PASS" for row in rows
                ),
                "task_ready_models": sum(
                    row["task_status"] == "PASS" for row in rows
                ),
                "admitted_regression_models": admitted_models,
                "admitted_regression_cells": sum(row["case_count"] for row in rows),
                "public_generation_error_at_both_probes": sum(
                    row["format_error_code"] == "MLX_GENERATION_FAILED"
                    and row["task_error_code"] == "MLX_GENERATION_FAILED"
                    for row in rows
                ),
                "static_chat_template_mismatch_models": sum(
                    row["static_adapter_preflight"]["static_adapter_mismatch"]
                    for row in rows
                ),
            },
            "adapter_breadth_status": (
                "ZERO_OF_TWO_ADMITTED"
                if admitted_models == 0 and len(rows) == 2
                else "PARTIAL_OR_COMPLETE_ADMISSION"
            ),
            "static_adapter_mismatch_status": (
                "IDENTIFIED_ON_BOTH_SNAPSHOTS"
                if both_static_mismatch
                else "NOT_IDENTIFIED_ON_ALL_SNAPSHOTS"
            ),
            "public_error_pattern_status": (
                "BOTH_PROBES_MLX_GENERATION_FAILED_ON_BOTH_SNAPSHOTS"
                if all_public_errors
                else "MIXED_PUBLIC_ERROR_PATTERN"
            ),
            "runtime_failure_causal_attribution_status": "NOT_ASSESSED",
            "algorithm_effect_status": _semantic_effect_status(rows),
            "next_gate": "PROMPT_RENDERING_COMPATIBILITY_MUST_CLOSE_BEFORE_ALGORITHM_EVALUATION",
            "claim_boundary": list(CLAIM_BOUNDARY),
        }
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("--model", action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        receipt = interpret(
            _load(args.result, "V0853_INTERPRET_RESULT_INVALID"),
            _load(args.lock, "V0853_INTERPRET_LOCK_INVALID"),
            args.model,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except EBRTError as error:
        print(json.dumps({"status": "FAIL", "error_code": str(error)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
