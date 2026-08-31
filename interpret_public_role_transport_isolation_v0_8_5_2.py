#!/usr/bin/env python3
"""Deterministically interpret the sealed v0.8.5 -> v0.8.5.2 transition."""

from __future__ import annotations

import argparse
import difflib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from ebrt_core import EBRTError, _seal
import public_role_transport_isolation_v0_8_5_2 as current
import typed_public_state_regression_v0_8_5 as prior


SCHEMA_VERSION = "ebrt-public-role-isolation-interpretation-v0.8.5.2"

CLAIM_BOUNDARY = (
    "The known readiness task and all regression cases are contaminated engineering material.",
    "After removing only the public role field, all nine v0.8.5.2 prompts match v0.8.5 byte for byte.",
    "The exact model-visible interface delta is isolated, but a one-sample readiness transition is association evidence, not causal attribution.",
    "List ordering and JSON field ordering are normalized before public-state differences are counted.",
    "The direct/control contrast still bundles evidence order and explicit public revision instructions.",
    "No gradient crosses a model adapter, and no causal, general-quality, or cross-model claim is admitted.",
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


def _normalized_state(value: Mapping[str, Any] | None) -> JsonObject | None:
    if value is None:
        return None
    return {
        "answer": value["answer"],
        "decision_support_ids": sorted(value["decision_support_ids"]),
        "revision_event_id": value["revision_event_id"],
        "preserved_constraint_ids": sorted(value["preserved_constraint_ids"]),
    }


def _model_runs(value: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {row["model_adapter"]["model_id"]: row for row in value["runs"]}


def _serialization_or_order_only(
    raw_text_changed: bool,
    direct_state: Mapping[str, Any] | None,
    controlled_state: Mapping[str, Any] | None,
) -> bool:
    return bool(
        raw_text_changed
        and direct_state is not None
        and controlled_state is not None
        and direct_state == controlled_state
    )


def _semantic_effect_status(rows: Sequence[Mapping[str, Any]]) -> str:
    if not rows:
        return "NOT_ASSESSED_NO_ADMITTED_CELLS"
    if any(
        row["normalized_public_state_changed"] or row["answer_changed"]
        for row in rows
    ):
        return "OBSERVED_NON_NULL_ON_ADMITTED_CELLS"
    return "NULL_ON_ADMITTED_CELLS"


def _prompt_audit() -> JsonObject:
    pairs: list[tuple[str, str, str]] = []
    old_readiness = prior.build_task_readiness_invocation()
    new_readiness = current.build_task_readiness_invocation()
    pairs.append(
        (
            "task_channel_readiness",
            old_readiness["prompt"],
            new_readiness["prompt"],
        )
    )
    for old_case, new_case in zip(
        prior.build_cases(), current.build_cases(), strict=True
    ):
        old_program, _old_receipt = prior.compile_case(old_case)
        new_program, _new_receipt = current.compile_case(new_case)
        old_invocations = prior.build_case_invocations(old_case, old_program)
        new_invocations = current.build_case_invocations(new_case, new_program)
        pairs.extend(
            (
                f"{old_case.task.task_id}:{old_arm}",
                old_invocations[old_arm]["prompt"],
                new_invocations[new_arm]["prompt"],
            )
            for old_arm, new_arm in (
                (prior.ARM_DIRECT, current.ARM_DIRECT),
                (prior.ARM_ROLE, current.ARM_ROLE),
            )
        )
    rows: list[JsonObject] = []
    for label, old_prompt, new_prompt in pairs:
        projected = current._strip_public_roles_from_prompt(new_prompt)
        diff = list(
            difflib.unified_diff(
                old_prompt.splitlines(),
                projected.splitlines(),
                fromfile="v0.8.5",
                tofile="v0.8.5.2-minus-role",
                lineterm="",
            )
        )
        rows.append(
            {
                "invocation": label,
                "text_only_projection_exact": projected == old_prompt,
                "non_role_unified_diff": diff,
            }
        )
    exact_count = sum(row["text_only_projection_exact"] for row in rows)
    return _seal(
        {
            "invocation_count": len(rows),
            "text_only_projection_exact_count": exact_count,
            "all_text_only_projections_exact": exact_count == len(rows),
            "non_role_difference": "NONE",
            "model_visible_delta_status": "EXACT_PUBLIC_ROLE_FIELD_ONLY",
            "rows": rows,
        }
    )


def interpret(
    prior_result: Mapping[str, Any],
    prior_lock: Mapping[str, Any],
    current_result: Mapping[str, Any],
    current_lock: Mapping[str, Any],
) -> JsonObject:
    prior_verification = prior.verify_run(prior_result, prior_lock)
    current_verification = current.verify_run(current_result, current_lock)
    prompt_audit = _prompt_audit()
    if (
        prompt_audit["invocation_count"] != 9
        or not prompt_audit["all_text_only_projections_exact"]
    ):
        raise EBRTError("V0852_INTERPRET_PROMPT_ISOLATION_FAILED")
    old_runs = _model_runs(prior_result)
    new_runs = _model_runs(current_result)
    if set(old_runs) != set(new_runs):
        raise EBRTError("V0852_INTERPRET_MODEL_SET_MISMATCH")

    readiness_rows: list[JsonObject] = []
    for model_id in current.MODEL_IDS:
        old_ready = old_runs[model_id]["readiness"]["task_channel_ready"]
        new_ready = new_runs[model_id]["readiness"]["task_channel_ready"]
        readiness_rows.append(
            {
                "model_id": model_id,
                "v0_8_5_status": old_ready["status"],
                "v0_8_5_2_status": new_ready["status"],
                "transition": f"{old_ready['status']}_TO_{new_ready['status']}",
                "v0_8_5_output": old_ready["result"]["raw_text"],
                "v0_8_5_2_output": new_ready["result"]["raw_text"],
            }
        )

    cell_rows: list[JsonObject] = []
    for model_id in current.MODEL_IDS:
        for cell in new_runs[model_id]["cases"]:
            direct = cell["arms"][current.ARM_DIRECT]
            controlled = cell["arms"][current.ARM_ROLE]
            direct_state = _normalized_state(direct["result"]["public_state"])
            controlled_state = _normalized_state(
                controlled["result"]["public_state"]
            )
            cell_rows.append(
                {
                    "model_id": model_id,
                    "case_id": cell["case_id"],
                    "direct_grade": direct["semantic_grade"]["status"],
                    "controlled_grade": controlled["semantic_grade"]["status"],
                    "raw_text_changed": cell["diff"]["raw_text_changed"],
                    "parsed_sequence_changed": cell["diff"][
                        "parsed_state_changed"
                    ],
                    "normalized_public_state_changed": direct_state
                    != controlled_state,
                    "answer_changed": (
                        direct_state is not None
                        and controlled_state is not None
                        and direct_state["answer"] != controlled_state["answer"]
                    ),
                    "serialization_or_order_only": _serialization_or_order_only(
                        cell["diff"]["raw_text_changed"],
                        direct_state,
                        controlled_state,
                    ),
                }
            )

    semantic_diff_cells = sum(
        row["normalized_public_state_changed"] for row in cell_rows
    )
    answer_diff_cells = sum(row["answer_changed"] for row in cell_rows)
    semantic_effect_status = _semantic_effect_status(cell_rows)

    return _seal(
        {
            "schema_version": SCHEMA_VERSION,
            "status": "PASS",
            "prior_run_fingerprint_sha256": prior_result["fingerprint_sha256"],
            "current_run_fingerprint_sha256": current_result[
                "fingerprint_sha256"
            ],
            "prior_verification_fingerprint_sha256": prior_verification[
                "fingerprint_sha256"
            ],
            "current_verification_fingerprint_sha256": current_verification[
                "fingerprint_sha256"
            ],
            "prompt_audit": prompt_audit,
            "readiness_transitions": readiness_rows,
            "regression_cells": cell_rows,
            "summary": {
                "readiness_fail_to_pass": sum(
                    row["transition"] == "FAIL_TO_PASS" for row in readiness_rows
                ),
                "readiness_fail_to_fail": sum(
                    row["transition"] == "FAIL_TO_FAIL" for row in readiness_rows
                ),
                "admitted_regression_cells": len(cell_rows),
                "raw_text_diff_cells": sum(
                    row["raw_text_changed"] for row in cell_rows
                ),
                "parsed_sequence_diff_cells": sum(
                    row["parsed_sequence_changed"] for row in cell_rows
                ),
                "normalized_public_state_diff_cells": semantic_diff_cells,
                "answer_diff_cells": answer_diff_cells,
                "serialization_or_order_only_cells": sum(
                    row["serialization_or_order_only"] for row in cell_rows
                ),
                "strict_direct_passes": sum(
                    row["direct_grade"] == "PASS" for row in cell_rows
                ),
                "strict_controlled_passes": sum(
                    row["controlled_grade"] == "PASS" for row in cell_rows
                ),
                "strict_repairs": sum(
                    row["direct_grade"] == "FAIL"
                    and row["controlled_grade"] == "PASS"
                    for row in cell_rows
                ),
                "strict_regressions": sum(
                    row["direct_grade"] == "PASS"
                    and row["controlled_grade"] == "FAIL"
                    for row in cell_rows
                ),
            },
            "contrast_label": "EXACT_CALLER_SUPPLIED_PUBLIC_ROLE_FIELD",
            "model_visible_delta_status": "EXACT_PUBLIC_ROLE_FIELD_ONLY",
            "role_field_readiness_association": (
                "OBSERVED_FAIL_TO_PASS_ON_ONE_CONTAMINATED_MODEL"
                if any(
                    row["transition"] == "FAIL_TO_PASS"
                    for row in readiness_rows
                )
                else "NO_FAIL_TO_PASS_OBSERVED"
            ),
            "role_only_effect_attribution_status": "NOT_ASSESSED",
            "direct_control_semantic_effect_status": semantic_effect_status,
            "claim_boundary": list(CLAIM_BOUNDARY),
        }
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prior-result", type=Path, required=True)
    parser.add_argument("--prior-lock", type=Path, required=True)
    parser.add_argument("--current-result", type=Path, required=True)
    parser.add_argument("--current-lock", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        receipt = interpret(
            _load(args.prior_result, "V0852_INTERPRET_PRIOR_RESULT_INVALID"),
            _load(args.prior_lock, "V0852_INTERPRET_PRIOR_LOCK_INVALID"),
            _load(args.current_result, "V0852_INTERPRET_CURRENT_RESULT_INVALID"),
            _load(args.current_lock, "V0852_INTERPRET_CURRENT_LOCK_INVALID"),
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
