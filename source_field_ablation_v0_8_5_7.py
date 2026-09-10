#!/usr/bin/env python3
"""Replay one recorded calculation, varying only its supplementary source ID.

Two STATE_JSON readiness calls, then with/without and without/with pairs.
At most six fresh local generations, no retries, and no new calculation.
Old sources, raw evidence, strict grading, and the core remain unchanged.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

import public_calculation_bridge_v0_8_5_6 as bridge
from ebrt_core import (
    EBRTError,
    RevisionTask,
    SharedMLXRuntime,
    _canonical_bytes,
    _fingerprint,
    _seal,
    _sealed_snapshot,
)


ROOT = Path(__file__).resolve().parent
VERSION = "v0.8.5.7"
BASE_COMMIT = "c888d1073414a2fc870e9ef77b578f88233d656f"
transport = bridge.transport
diagnostic = bridge.diagnostic
prior = bridge.prior
MODEL_ID = bridge.MODEL_ID
MAX_TOKENS = bridge.MAX_TOKENS
DEPENDENCIES = (Path(__file__).name, *bridge.DEPENDENCIES)
PRIOR_ROOT = "artifacts/public_calculation_bridge_v0_8_5_6/r01/"
PRIOR_LOCK = "policy_lock_public_calculation_bridge_v0_8_5_6.json"
SOURCE_FILES = {
    PRIOR_LOCK: "14cde9dabd3682701704e13112628912da8975168e87330235ae8d4a611b05ae",
    PRIOR_ROOT
    + "results.json": "11fa4a68de7a736b6a40625a2b33ba89d635827d355b68ff634a69727ed5ae38",
    PRIOR_ROOT
    + "journal.jsonl": "abba15844416226bc9f1ed3f9675b23b0611cf9291a6ca3e0b3153ef33e29f7f",
    PRIOR_ROOT
    + "verification.json": "525b5909a0a623b451a3f02f4201d31c7a2b5052abf4a611faf99e335196069b",
}
READY_KEYS = ("state_format", "state_task")
ARMS = ("with_source", "without_source")
SCHEDULE = (
    ("pair1_with_source", "with_source"),
    ("pair1_without_source", "without_source"),
    ("pair2_without_source", "without_source"),
    ("pair2_with_source", "with_source"),
)
CALL_ORDER = (*READY_KEYS, *(key for key, _ in SCHEDULE))
BOUNDARY = {
    "scope": "ONE_KNOWN_CASE_CONTAMINATED_RECORDED_CALCULATION_REPLAY",
    "calculation": "PREVIOUS_ACTUAL_TERMINAL_NOT_REGENERATED",
    "changed_surface": "ONLY_SUPPLEMENTARY_RULE_EVIDENCE_ID_PRESENCE",
    "raw_evidence": "COMPLETE_CHRONOLOGICAL_BYTES_UNCHANGED",
    "answer_label_forwarded": False,
    "product_recomputed_or_corrected": False,
    "gold_support_inserted": False,
    "parser_or_grader_relaxed": False,
    "gradient_utility": "NOT_ASSESSED_NO_GRADIENT_INTERVENTION",
    "causal_superiority": "NOT_ESTABLISHED_ONE_CASE_AB_BA_DESCRIPTIVE_REPEATS",
    "private_reasoning": "NOT_OBSERVED_PUBLIC_OUTPUT_ONLY",
    "stable_values": "NOT_OBSERVABLE_IN_LEGACY_FINAL_STATE",
    "compute_matching": "SHARED_CEILING_NOT_EQUAL_INPUT_TOKENS_OR_TOTAL_COMPUTE",
}
Json = dict[str, Any]


def require(condition: bool, code: str) -> None:
    if not condition:
        raise EBRTError("V0857_" + code)


def read_journal(path: Path) -> list[Json]:
    with path.open(encoding="utf-8") as stream:
        return [
            json.loads(line, object_pairs_hook=prior._pairs_without_duplicates)
            for line in stream
        ]


def recorded_source() -> Json:
    """Read exactly the sealed prior calculation, never a selected new answer."""
    for name, digest in SOURCE_FILES.items():
        require(transport.file_sha(ROOT / name) == digest, "PRIOR_FILE_CHANGED")
    old = transport.load_json(ROOT / PRIOR_ROOT / "results.json")
    old_lock = transport.load_json(ROOT / PRIOR_LOCK)
    journal = read_journal(ROOT / PRIOR_ROOT / "journal.jsonl")
    verified = bridge.verify_run(old, old_lock, journal)
    require(
        verified == transport.load_json(ROOT / PRIOR_ROOT / "verification.json"),
        "PRIOR_VERIFICATION_CHANGED",
    )
    rows = [row for row in old["results"] if row["key"] == "calculation"]
    require(len(rows) == 1, "PRIOR_CALCULATION_NOT_UNIQUE")
    terminal = rows[0]["terminal"]
    require(terminal["status"] == "COMPLETE", "PRIOR_CALCULATION_INCOMPLETE")
    raw = terminal["raw_text"]
    parsed = bridge.parse_calculation(raw, diagnostic.numeric_case().task)
    require(parsed is not None, "PRIOR_CALCULATION_UNPARSED")
    return _seal(
        {
            "source_file_sha256": SOURCE_FILES,
            "source_run_fingerprint_sha256": old["fingerprint_sha256"],
            "source_calculation_raw_sha256": transport.sha(raw),
            "raw_text": raw,
            "parsed_values": parsed,
            "disposition": "RECORDED_CONTAMINATED_NOT_A_FRESH_CALCULATION",
            "prior_calculation_cost_not_reexecuted": {
                name: terminal[name] for name in ("input_tokens", "output_tokens")
            },
        }
    )


def compile_final(task: RevisionTask, arm: str, raw: str) -> Json:
    require(arm in ARMS, "ARM_INVALID")
    original = bridge.final_invocation(task, "product_bridge", raw)
    projection = dict(original["projected_record"])
    if arm == "without_source":
        del projection["rule_evidence_id"]
    old_line = "PUBLIC_CALCULATION_JSON " + transport.json_line(
        original["projected_record"]
    )
    new_line = "PUBLIC_CALCULATION_JSON " + transport.json_line(projection)
    require(original["prompt"].splitlines().count(old_line) == 1, "RECORD_NOT_UNIQUE")
    prompt = "\n".join(
        new_line if line == old_line else line
        for line in original["prompt"].split("\n")
    )
    return _seal(
        {
            "arm": arm,
            "prompt": prompt,
            "prompt_sha256": transport.sha(prompt),
            "projected_record": projection,
            "source_calculation_raw_sha256": original["source_calculation_raw_sha256"],
        }
    )


def invocations(source: Mapping[str, Any]) -> Json:
    values = {}
    for key in READY_KEYS:
        prompt = bridge.static_prompts()[key]
        values[key] = _seal(
            {
                "key": key,
                "arm": None,
                "prompt": prompt,
                "prompt_sha256": transport.sha(prompt),
                "projected_record": None,
                "source_calculation_raw_sha256": None,
            }
        )
    for key, arm in SCHEDULE:
        compiled = compile_final(
            diagnostic.numeric_case().task, arm, source["raw_text"]
        )
        values[key] = _seal(
            {
                "key": key,
                **{
                    k: value
                    for k, value in compiled.items()
                    if k != "fingerprint_sha256"
                },
            }
        )
    return values


def lock_spec() -> Json:
    source = recorded_source()
    return _seal(
        {
            "schema_version": "ebrt-source-field-lock-" + VERSION,
            "base_commit": BASE_COMMIT,
            "source_sha256": {
                name: transport.file_sha(ROOT / name) for name in DEPENDENCIES
            },
            "model_id": MODEL_ID,
            "recorded_source": source,
            "invocations": invocations(source),
            "post_call_contract": diagnostic.numeric_case().contract.to_dict(),
            "execution_policy": {
                "call_order": list(CALL_ORDER),
                "maximum_calls": 6,
                "readiness_calls": 2,
                "final_calls": 4,
                "pair_orders": [
                    ["with_source", "without_source"],
                    ["without_source", "with_source"],
                ],
                "max_tokens": MAX_TOKENS,
                "max_input_tokens": bridge.MAX_INPUT_TOKENS,
                "temperature": 0.0,
                "seed": 0,
                "cross_call_kv_cache": "NONE",
                "automatic_retry": False,
                "calculation_calls": 0,
                "readiness_gate": "BOTH_STATE_CHECKS_PASS",
                "required_before_execution": "SOURCES_REPLAY_INPUTS_LOCK_PREFLIGHT_COMMITTED_AND_PUSHED",
            },
            "claim_boundary": BOUNDARY,
        }
    )


def validate_lock(value: Mapping[str, Any]) -> Json:
    locked = _sealed_snapshot(value, "V0857_LOCK")
    require(_canonical_bytes(locked) == _canonical_bytes(lock_spec()), "LOCK_MISMATCH")
    return locked


def preflight(model_path: str, lock: Mapping[str, Any]) -> Json:
    locked = validate_lock(lock)
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    runtime = SharedMLXRuntime(model_path, max_tokens=MAX_TOKENS)
    require(runtime.model_id == MODEL_ID, "MODEL_ID_MISMATCH")
    from mlx_lm.utils import load_tokenizer

    config = transport.load_json(runtime.model_path / "config.json")
    tokenizer = load_tokenizer(
        runtime.model_path,
        {"local_files_only": True},
        eos_token_ids=config.get("eos_token_id"),
    )
    return _seal(
        {
            "schema_version": "ebrt-source-field-preflight-" + VERSION,
            "status": "PASS_ZERO_GENERATION",
            "logical_calls": 0,
            "policy_lock_fingerprint_sha256": locked["fingerprint_sha256"],
            "model_id": MODEL_ID,
            "snapshot_files": transport.snapshot_files(runtime.model_path),
            "runtime": transport.runtime_identity(),
            "rendered": {
                key: bridge.validate_render(
                    transport.render(tokenizer, row["prompt"]), row["prompt"]
                )
                for key, row in locked["invocations"].items()
            },
        }
    )


def validate_preflight(value: Mapping[str, Any], lock: Mapping[str, Any]) -> Json:
    result = _sealed_snapshot(value, "V0857_PREFLIGHT")
    require(
        set(result)
        == {
            "schema_version",
            "status",
            "logical_calls",
            "policy_lock_fingerprint_sha256",
            "model_id",
            "snapshot_files",
            "runtime",
            "rendered",
            "fingerprint_sha256",
        },
        "PREFLIGHT_SHAPE",
    )
    require(
        result["schema_version"] == "ebrt-source-field-preflight-" + VERSION
        and result["status"] == "PASS_ZERO_GENERATION"
        and type(result["logical_calls"]) is int
        and result["logical_calls"] == 0
        and result["policy_lock_fingerprint_sha256"] == lock["fingerprint_sha256"]
        and result["model_id"] == MODEL_ID,
        "PREFLIGHT_BINDING",
    )
    files = result["snapshot_files"]
    require(type(files) is dict and bool(files), "SNAPSHOT_INVALID")
    for name, row in files.items():
        require(
            type(name) is str
            and name == Path(name).name
            and type(row) is dict
            and set(row) == {"size", "sha256"}
            and type(row["size"]) is int
            and row["size"] >= 0
            and type(row["sha256"]) is str
            and re.fullmatch(r"[0-9a-f]{64}", row["sha256"]) is not None,
            "SNAPSHOT_INVALID",
        )
    identity = result["runtime"]
    require(
        type(identity) is dict
        and set(identity) == {"python", "machine", "packages"}
        and all(
            type(identity[key]) is str and bool(identity[key])
            for key in ("python", "machine")
        )
        and type(identity["packages"]) is dict
        and set(identity["packages"])
        == {"torch", "mlx", "mlx-lm", "transformers", "tokenizers"}
        and all(
            type(version) is str and bool(version)
            for version in identity["packages"].values()
        ),
        "RUNTIME_IDENTITY_INVALID",
    )
    require(set(result["rendered"]) == set(lock["invocations"]), "PREFLIGHT_KEYS")
    for key, invocation in lock["invocations"].items():
        bridge.validate_render(result["rendered"][key], invocation["prompt"])
    return result


def readiness(results: Sequence[Mapping[str, Any]]) -> Json:
    require(
        len(results) >= 2 and [row["key"] for row in results[:2]] == list(READY_KEYS),
        "READINESS_TERMINALS",
    )
    literal, task = (row["terminal"] for row in results[:2])
    quality = transport.quality(task["raw_text"], prior.build_readiness_case())
    checks = {
        "state_format": literal["status"] == "COMPLETE"
        and literal["raw_text"] == prior.FORMAT_EXPECTED,
        "state_task": task["status"] == "COMPLETE"
        and quality["strict_grade"]["status"] == "PASS",
    }
    return {
        "checks": checks,
        "all_passed": all(checks.values()),
        "state_task_quality": quality,
    }


def assess(
    lock: Mapping[str, Any],
    checked: Mapping[str, Any],
    results: Sequence[Mapping[str, Any]],
) -> Json:
    require(len(results) in (2, 6), "CALL_COUNT_INVALID")
    admitted = readiness(results)
    expected_keys = CALL_ORDER if admitted["all_passed"] else READY_KEYS
    require(
        [row["key"] for row in results] == list(expected_keys), "CALL_SCHEDULE_MISMATCH"
    )
    for row in results:
        require(set(row) == {"key", "invocation", "rendered", "terminal"}, "CALL_SHAPE")
        key = row["key"]
        require(row["invocation"] == lock["invocations"][key], "INVOCATION_CHANGED")
        require(row["rendered"] == checked["rendered"][key], "RENDER_CHANGED")
        transport.validate_result(row["terminal"], key, row["rendered"])
    finals = {}
    for row in results[2:]:
        terminal = row["terminal"]
        quality = transport.quality(terminal["raw_text"], diagnostic.numeric_case())
        state = quality["public_state"]
        finals[row["key"]] = {
            "arm": row["invocation"]["arm"],
            "execution_status": terminal["status"],
            "raw_text": terminal["raw_text"],
            "quality": quality,
            "r2_present": None
            if state is None
            else "R2" in state["decision_support_ids"],
            "edit_diagnostics": diagnostic.state_edit_diagnostics(
                diagnostic.numeric_case(), state
            ),
        }
    pairs, repeats = [], {}
    if finals:
        for index in (1, 2):
            left, right = f"pair{index}_with_source", f"pair{index}_without_source"
            comparison = transport.compare(finals[left], finals[right], left, right)
            complete = all(
                finals[key]["execution_status"] == "COMPLETE" for key in (left, right)
            )
            comparison["both_generations_complete"] = complete
            comparison["execution_order"] = [
                key for key, _ in SCHEDULE if key in (left, right)
            ]
            comparison["r2_presence_transition"] = [
                finals[key]["r2_present"] for key in (left, right)
            ]
            if not complete:
                comparison["strict_repair"] = comparison["strict_regression"] = None
            pairs.append(comparison)
        for arm in ARMS:
            rows = [row for row in finals.values() if row["arm"] == arm]
            complete = all(row["execution_status"] == "COMPLETE" for row in rows)
            parsed = all(row["quality"]["public_state"] is not None for row in rows)
            repeats[arm] = {
                "planned": 2,
                "generated": sum(row["execution_status"] == "COMPLETE" for row in rows),
                "parsed": sum(
                    row["quality"]["public_state"] is not None for row in rows
                ),
                "strict_passes": sum(
                    row["quality"]["strict_grade"]["status"] == "PASS" for row in rows
                ),
                "raw_outputs_identical": rows[0]["raw_text"] == rows[1]["raw_text"]
                if complete
                else None,
                "normalized_states_identical": transport.semantic_state(
                    rows[0]["quality"]["public_state"]
                )
                == transport.semantic_state(rows[1]["quality"]["public_state"])
                if complete and parsed
                else None,
            }
    return {
        "run_status": "READINESS_STOP_NO_FINAL_CALLS"
        if not admitted["all_passed"]
        else (
            "COMPLETE_SIX_CALL_BLOCK"
            if all(row["terminal"]["status"] == "COMPLETE" for row in results)
            else "INCOMPLETE_GENERATION_ERRORS_RETAINED"
        ),
        "readiness": admitted,
        "logical_calls": len(results),
        "new_calculation_calls": 0,
        "recorded_source_fingerprint_sha256": lock["recorded_source"][
            "fingerprint_sha256"
        ],
        "final_probe_denominator": len(finals),
        "strict_final_passes": sum(
            row["quality"]["strict_grade"]["status"] == "PASS"
            for row in finals.values()
        ),
        "finals": finals,
        "pairs_with_to_without_source": pairs,
        "within_arm_repeats": repeats,
        "total_input_tokens": sum(row["terminal"]["input_tokens"] for row in results),
        "total_output_tokens_including_terminal": sum(
            row["terminal"]["output_tokens"] for row in results
        ),
        "diagnostic_cause": "NOT_IDENTIFIED_ONE_KNOWN_CASE_DESCRIPTIVE_REPEATS",
    }


def verify_run(
    value: Mapping[str, Any],
    lock: Mapping[str, Any],
    journal: Sequence[Mapping[str, Any]],
) -> Json:
    locked = validate_lock(lock)
    artifact = _sealed_snapshot(value, "V0857_RUN")
    require(
        set(artifact)
        == {
            "schema_version",
            "lock_commit",
            "policy_lock_fingerprint_sha256",
            "preflight",
            "results",
            "assessment",
            "claim_boundary",
            "fingerprint_sha256",
        },
        "RUN_SHAPE",
    )
    require(
        artifact["schema_version"] == "ebrt-source-field-run-" + VERSION
        and artifact["policy_lock_fingerprint_sha256"] == locked["fingerprint_sha256"]
        and artifact["claim_boundary"] == BOUNDARY
        and type(artifact["lock_commit"]) is str
        and re.fullmatch(r"[0-9a-f]{40}", artifact["lock_commit"]) is not None,
        "RUN_BINDING",
    )
    checked = validate_preflight(artifact["preflight"], locked)
    require(
        _canonical_bytes(artifact["assessment"])
        == _canonical_bytes(assess(locked, checked, artifact["results"])),
        "ASSESSMENT_REPLAY_MISMATCH",
    )
    require(
        _canonical_bytes(list(journal))
        == _canonical_bytes(bridge.journal_rows(artifact)),
        "JOURNAL_REPLAY_MISMATCH",
    )
    return _seal(
        {
            "status": "PASS",
            "logical_calls": 0,
            "artifact_fingerprint_sha256": artifact["fingerprint_sha256"],
            "model_execution": "NOT_REEXECUTED",
            "tokenization": "RECORDED_NOT_REEXECUTED",
            "replayed": "PINNED_SOURCE_FIELD_ONLY_PROMPTS_READINESS_AB_BA_GRADES_JOURNAL",
        }
    )


def run_once(
    model_path: str, lock_path: Path, preflight_path: Path, output: Path, commit: str
) -> Json:
    locked = validate_lock(transport.load_json(lock_path))
    checked = validate_preflight(transport.load_json(preflight_path), locked)
    transport.published_inputs(lock_path, preflight_path, commit)
    for name in (*DEPENDENCIES, *SOURCE_FILES):
        require(
            subprocess.check_output(["git", "show", commit + ":" + name], cwd=ROOT)
            == (ROOT / name).read_bytes(),
            "COMMITTED_INPUT_CHANGED",
        )
    require(
        _canonical_bytes(preflight(model_path, locked)) == _canonical_bytes(checked),
        "PREFLIGHT_CHANGED",
    )
    require(not output.exists(), "OUTPUT_ALREADY_EXISTS")
    transport.write_new(
        lock_path.with_suffix(".execution-claim.json"),
        {
            "lock_fingerprint_sha256": locked["fingerprint_sha256"],
            "lock_commit": commit,
            "status": "EXECUTION_CLAIMED_NO_RETRY",
        },
    )
    output.mkdir(parents=True, exist_ok=False)
    runtime = transport.LocalRuntime(model_path)
    results: list[Json] = []
    journal: list[Json] = []
    with (output / "journal.jsonl").open("x", encoding="utf-8") as stream:

        def record(kind: str, payload: Any) -> None:
            row = _seal(
                {
                    "kind": kind,
                    "payload": payload,
                    "previous_sha256": journal[-1]["fingerprint_sha256"]
                    if journal
                    else None,
                }
            )
            stream.write(transport.json_line(row) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
            journal.append(row)

        record(
            "START",
            {
                "lock_commit": commit,
                "lock_sha256": locked["fingerprint_sha256"],
                "preflight_sha256": checked["fingerprint_sha256"],
            },
        )
        for key in CALL_ORDER:
            if len(results) == 2 and not readiness(results)["all_passed"]:
                break
            invocation, rendered = locked["invocations"][key], checked["rendered"][key]
            dispatch = {"key": key, "invocation": invocation, "rendered": rendered}
            record("DISPATCH", dispatch)
            try:
                terminal = runtime.invoke(key, invocation["prompt"], rendered)
            except BaseException as error:
                record(
                    "INTERRUPTED", {"key": key, "exception_type": type(error).__name__}
                )
                raise
            record("TERMINAL", terminal)
            results.append({**dispatch, "terminal": terminal})
            print(
                transport.json_line(
                    {
                        "progress": key,
                        "calls": len(results),
                        "status": terminal["status"],
                    }
                ),
                flush=True,
            )
        artifact = _seal(
            {
                "schema_version": "ebrt-source-field-run-" + VERSION,
                "lock_commit": commit,
                "policy_lock_fingerprint_sha256": locked["fingerprint_sha256"],
                "preflight": checked,
                "results": results,
                "assessment": assess(locked, checked, results),
                "claim_boundary": BOUNDARY,
            }
        )
        record(
            "FINISH", {"artifact_fingerprint_sha256": artifact["fingerprint_sha256"]}
        )
    transport.write_new(output / "results.json", artifact)
    transport.write_new(
        output / "verification.json", verify_run(artifact, locked, journal)
    )
    with (output / "report.md").open("x", encoding="utf-8") as stream:
        stream.write(report(artifact))
    return artifact


def report(artifact: Mapping[str, Any]) -> str:
    result = artifact["assessment"]
    lines = [
        "# Source-field ablation " + VERSION,
        "",
        "Recorded calculation replay on one known case; no fresh calculation or gradient-utility claim.",
        "",
        f"Run: `{result['run_status']}`; calls: {result['logical_calls']}; strict final: {result['strict_final_passes']}/{result['final_probe_denominator']}",
        "",
        "| Call | Execution | Input tokens | Output tokens | Finish |",
        "| --- | --- | ---: | ---: | --- |",
    ]
    for row in artifact["results"]:
        t = row["terminal"]
        lines.append(
            f"| {row['key']} | {t['status']} | {t['input_tokens']} | {t['output_tokens']} | {t['finish_reason']} |"
        )
    for row in artifact["results"]:
        lines.extend(
            [
                "",
                "## " + row["key"],
                "",
                "```text",
                row["terminal"]["raw_text"] or "<NO COMPLETED OUTPUT>",
                "```",
            ]
        )
    lines.extend(
        [
            "",
            "## Assessment",
            "",
            "```json",
            json.dumps(result, indent=2),
            "```",
            "",
            "## Boundary",
            "",
            "```json",
            json.dumps(BOUNDARY, indent=2),
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def self_test() -> Json:
    import contextlib
    import io
    import tempfile
    from unittest.mock import patch

    checks = {}
    source = recorded_source()
    task = diagnostic.numeric_case().task
    raw = source["raw_text"]
    with_id = compile_final(task, "with_source", raw)
    without_id = compile_final(task, "without_source", raw)

    def reseal(value: Mapping[str, Any]) -> Json:
        return _seal(
            {key: item for key, item in value.items() if key != "fingerprint_sha256"}
        )

    def rejected(callback: Any) -> bool:
        try:
            callback()
        except EBRTError:
            return True
        return False

    def calculation(**updates: Any) -> str:
        return "CALC_JSON=" + transport.json_line(
            {**source["parsed_values"], **updates}
        )

    def emit(answer: str = "15_CREDITS", support: Sequence[str] = ("R2", "R4")) -> str:
        return "STATE_JSON=" + transport.json_line(
            {
                "answer": answer,
                "decision_support_ids": list(support),
                "revision_event_id": "R6",
                "preserved_constraint_ids": ["R5"],
            }
        )

    checks["prior_source_reverified_without_generation"] = (
        source["source_run_fingerprint_sha256"]
        == "c541b13a4541d0c0a3ff6db380f2d0d7cca93379fd491b3c55e208b8376acc5b"
    )
    checks["source_hash_bound"] = (
        with_id["source_calculation_raw_sha256"]
        == source["source_calculation_raw_sha256"]
    )
    checks["with_source_bytes_equal_prior_product_bridge"] = (
        with_id["prompt"]
        == bridge.final_invocation(task, "product_bridge", raw)["prompt"]
    )
    old_product = next(
        row
        for row in transport.load_json(ROOT / PRIOR_ROOT / "results.json")["results"]
        if row["key"] == "product_bridge"
    )
    checks["with_source_bytes_equal_actual_prior_dispatch"] = (
        with_id["prompt"] == old_product["invocation"]["prompt"]
        and with_id["projected_record"] == old_product["invocation"]["projected_record"]
    )
    stripped = {
        key: value
        for key, value in with_id["projected_record"].items()
        if key != "rule_evidence_id"
    }
    checks["only_source_field_removed"] = stripped == without_id["projected_record"]
    replaced = with_id["prompt"].replace(
        "PUBLIC_CALCULATION_JSON " + transport.json_line(with_id["projected_record"]),
        "PUBLIC_CALCULATION_JSON " + transport.json_line(stripped),
    )
    checks["complete_prompt_difference_is_one_field"] = replaced == without_id["prompt"]

    def evidence(prompt: str) -> list[str]:
        return [
            line for line in prompt.splitlines() if line.startswith("EVIDENCE_JSON ")
        ]

    checks["full_chronological_raw_unchanged"] = (
        evidence(with_id["prompt"])
        == evidence(without_id["prompt"])
        == evidence(bridge.final_invocation(task, "raw_only")["prompt"])
    )
    checks["answer_not_forwarded"] = all(
        "answer" not in row["projected_record"] for row in (with_id, without_id)
    )
    checks["no_gold_support_added"] = set(without_id["projected_record"]) == {
        "base_count",
        "multiplier",
        "product",
    }
    checks["wrong_product_copied_not_corrected"] = (
        compile_final(task, "without_source", calculation(product=45))[
            "projected_record"
        ]["product"]
        == 45
    )
    checks["wrong_known_source_not_corrected"] = (
        compile_final(task, "with_source", calculation(rule_evidence_id="R6"))[
            "projected_record"
        ]["rule_evidence_id"]
        == "R6"
    )
    checks["source_answer_does_not_change_prompt"] = (
        compile_final(task, "with_source", calculation(answer="45_CREDITS"))["prompt"]
        == with_id["prompt"]
    )
    checks["source_field_only_affects_with_source_prompt"] = (
        compile_final(task, "without_source", calculation(rule_evidence_id="R6"))[
            "prompt"
        ]
        == without_id["prompt"]
    )
    checks["unknown_arm_rejected"] = rejected(lambda: compile_final(task, "raw", raw))
    for name, invalid in {
        "missing_prefix": raw.removeprefix("CALC_JSON="),
        "multiline": json.dumps(source["parsed_values"], indent=2),
        "duplicate": raw.replace('"product":15', '"product":15,"product":15'),
        "boolean": calculation(product=True),
        "float": calculation(product=15.0),
        "negative": calculation(product=-1),
        "oversized": calculation(product=1_000_001),
        "unknown_source": calculation(rule_evidence_id="R99"),
        "extra_key": calculation(expected_support=["R2", "R4"]),
    }.items():
        checks["rejects_" + name] = rejected(
            lambda invalid=invalid: compile_final(task, "without_source", invalid)
        )
    with patch.object(transport, "file_sha", return_value="0" * 64):
        checks["altered_prior_file_rejected"] = rejected(recorded_source)

    locked = lock_spec()
    checks["no_new_calculator_calls"] = (
        locked["execution_policy"]["calculation_calls"] == 0
        and len(locked["invocations"]) == 6
    )
    checks["same_arm_prompts_equal_across_order"] = all(
        locked["invocations"][f"pair1_{arm}"]["prompt"]
        == locked["invocations"][f"pair2_{arm}"]["prompt"]
        for arm in ARMS
    )
    checks["ab_ba_order_fixed"] = [arm for _, arm in SCHEDULE] == [
        "with_source",
        "without_source",
        "without_source",
        "with_source",
    ]

    def fake_render(prompt: str) -> Json:
        return _seal(
            {
                "prompt_sha256": transport.sha(prompt),
                "rendered_prompt": prompt,
                "rendered_sha256": transport.sha(prompt),
                "token_ids": [1],
                "token_ids_sha256": _fingerprint([1]),
                "input_tokens": 1,
            }
        )

    checked = _seal(
        {
            "schema_version": "ebrt-source-field-preflight-" + VERSION,
            "status": "PASS_ZERO_GENERATION",
            "logical_calls": 0,
            "policy_lock_fingerprint_sha256": locked["fingerprint_sha256"],
            "model_id": MODEL_ID,
            "snapshot_files": {"SYNTHETIC": {"size": 0, "sha256": "0" * 64}},
            "runtime": {
                "python": "SYNTHETIC",
                "machine": "SYNTHETIC",
                "packages": {
                    name: "SYNTHETIC"
                    for name in ("torch", "mlx", "mlx-lm", "transformers", "tokenizers")
                },
            },
            "rendered": {
                key: fake_render(row["prompt"])
                for key, row in locked["invocations"].items()
            },
        }
    )

    def make_rows(overrides: Mapping[str, str] | None = None) -> list[Json]:
        texts = {
            "state_format": prior.FORMAT_EXPECTED,
            "state_task": emit(prior.build_readiness_case().contract.expected_answer),
        }
        texts.update(
            {
                key: emit(support=("R4",) if arm == "with_source" else ("R2", "R4"))
                for key, arm in SCHEDULE
            }
        )
        texts.update(overrides or {})
        rows = []
        for key in CALL_ORDER:
            if len(rows) == 2 and not readiness(rows)["all_passed"]:
                break
            rendered = checked["rendered"][key]
            terminal = _seal(
                {
                    "key": key,
                    "render_fingerprint_sha256": rendered["fingerprint_sha256"],
                    "status": "COMPLETE",
                    "raw_text": texts[key],
                    "partial_text": None,
                    "error_code": None,
                    "input_tokens": 1,
                    "output_tokens": 1,
                    "output_token_ids": [2],
                    "finish_reason": "stop",
                    "latency_ms": 0.0,
                }
            )
            rows.append(
                {
                    "key": key,
                    "invocation": locked["invocations"][key],
                    "rendered": rendered,
                    "terminal": terminal,
                }
            )
        return rows

    def artifact_for(rows: Sequence[Mapping[str, Any]]) -> Json:
        return _seal(
            {
                "schema_version": "ebrt-source-field-run-" + VERSION,
                "lock_commit": BASE_COMMIT,
                "policy_lock_fingerprint_sha256": locked["fingerprint_sha256"],
                "preflight": checked,
                "results": list(rows),
                "assessment": assess(locked, checked, rows),
                "claim_boundary": BOUNDARY,
            }
        )

    rows = make_rows()
    artifact = artifact_for(rows)
    checks["six_call_artifact_replays"] = (
        verify_run(artifact, locked, bridge.journal_rows(artifact))["status"] == "PASS"
    )
    checks["four_finals_not_six_quality_cells"] = (
        artifact["assessment"]["final_probe_denominator"] == 4
    )
    checks["pair_direction_normalized_with_to_without"] = all(
        row["strict_repair"]
        for row in artifact["assessment"]["pairs_with_to_without_source"]
    )
    checks["pair2_reverse_execution_retained"] = artifact["assessment"][
        "pairs_with_to_without_source"
    ][1]["execution_order"] == ["pair2_without_source", "pair2_with_source"]
    checks["within_arm_repeat_consistency_recorded"] = all(
        row["normalized_states_identical"]
        for row in artifact["assessment"]["within_arm_repeats"].values()
    )
    checks["r2_loss_is_over_edit"] = artifact["assessment"]["finals"][
        "pair1_with_source"
    ]["edit_diagnostics"]["errors"]["over_edit"] == ["/decision_support_ids/R2"]
    for key in READY_KEYS:
        stopped = artifact_for(make_rows({key: "bad"}))
        checks[key + "_failure_stops_all_finals"] = (
            stopped["assessment"]["logical_calls"] == 2
            and stopped["assessment"]["final_probe_denominator"] == 0
        )
        checks[key + "_stop_journal_replays"] = (
            verify_run(stopped, locked, bridge.journal_rows(stopped))["status"]
            == "PASS"
        )
    for name, altered in {
        "extra_call": [*rows, rows[-1]],
        "missing_call": rows[:-1],
        "duplicate_call": [*rows[:-1], rows[-2]],
        "wrong_pair_order": [*rows[:2], rows[3], rows[2], *rows[4:]],
    }.items():
        checks["rejects_" + name] = rejected(
            lambda altered=altered: artifact_for(altered)
        )
    tampered = json.loads(json.dumps(rows))
    tampered[2]["invocation"] = reseal(
        {
            **tampered[2]["invocation"],
            "projected_record": without_id["projected_record"],
        }
    )
    checks["mislabeled_source_payload_rejected"] = rejected(
        lambda: artifact_for(tampered)
    )
    malformed = artifact_for(make_rows({"pair1_without_source": "bare JSON"}))
    checks["malformed_state_stays_unparsed"] = (
        malformed["assessment"]["finals"]["pair1_without_source"]["r2_present"] is None
    )
    error_rows = json.loads(json.dumps(rows))
    error_rows[2]["terminal"] = reseal(
        {
            **error_rows[2]["terminal"],
            "status": "GENERATION_ERROR",
            "raw_text": None,
            "partial_text": "",
            "error_code": "MLX_GENERATION_FAILED",
            "finish_reason": None,
            "output_tokens": 0,
            "output_token_ids": [],
        }
    )
    failed = artifact_for(error_rows)
    checks["generation_error_not_counted_as_repair"] = (
        failed["assessment"]["pairs_with_to_without_source"][0]["strict_repair"] is None
    )
    checks["generation_errors_retained"] = (
        failed["assessment"]["run_status"] == "INCOMPLETE_GENERATION_ERRORS_RETAINED"
    )
    checks["generation_error_journal_replays"] = (
        verify_run(failed, locked, bridge.journal_rows(failed))["status"] == "PASS"
    )
    changed = reseal(
        {**artifact, "assessment": {**artifact["assessment"], "strict_final_passes": 4}}
    )
    checks["invented_grades_rejected"] = rejected(
        lambda: verify_run(changed, locked, bridge.journal_rows(changed))
    )
    checks["journal_required"] = rejected(
        lambda: verify_run(artifact, locked, bridge.journal_rows(artifact)[1:])
    )
    checks["changed_lock_rejected"] = rejected(
        lambda: validate_lock(reseal({**locked, "model_id": "other"}))
    )
    checks["lock_roundtrip"] = (
        validate_lock(json.loads(json.dumps(locked, sort_keys=True))) == locked
    )
    checks["boolean_preflight_calls_rejected"] = rejected(
        lambda: validate_preflight(reseal({**checked, "logical_calls": False}), locked)
    )
    checks["snapshot_path_escape_rejected"] = rejected(
        lambda: validate_preflight(
            reseal(
                {
                    **checked,
                    "snapshot_files": {
                        "../outside": checked["snapshot_files"]["SYNTHETIC"]
                    },
                }
            ),
            locked,
        )
    )

    # Synthetic outputs exercise real orchestration and fsynced dispatch; no MLX generation.
    with tempfile.TemporaryDirectory(prefix="ebrt-v0857-test-") as temporary:
        directory = Path(temporary)
        lock_path, checked_path, output = (
            directory / "lock.json",
            directory / "preflight.json",
            directory / "run",
        )
        transport.write_new(lock_path, locked)
        transport.write_new(checked_path, checked)
        dispatched = []
        terminals = {row["key"]: row["terminal"] for row in rows}

        class FakeRuntime:
            def __init__(self, model_path: str):
                pass

            def invoke(
                self, key: str, prompt: str, rendering: Mapping[str, Any]
            ) -> Json:
                last = read_journal(output / "journal.jsonl")[-1]
                require(
                    last["kind"] == "DISPATCH" and last["payload"]["key"] == key,
                    "MOCK_DISPATCH_MISSING",
                )
                require(
                    last["payload"]["invocation"]["prompt"] == prompt
                    and last["payload"]["rendered"] == rendering,
                    "MOCK_DISPATCH_BYTES",
                )
                dispatched.append(key)
                return terminals[key]

        def committed_bytes(command: Sequence[str], cwd: Path) -> bytes:
            require(command[:2] == ["git", "show"], "MOCK_UNEXPECTED_PROCESS")
            return (ROOT / command[2].split(":", 1)[1]).read_bytes()

        with (
            patch.object(transport, "published_inputs"),
            patch.object(sys.modules[__name__], "preflight", return_value=checked),
            patch.object(subprocess, "check_output", side_effect=committed_bytes),
            patch.object(transport, "LocalRuntime", FakeRuntime),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            actual = run_once(
                "SYNTHETIC_NO_MODEL", lock_path, checked_path, output, BASE_COMMIT
            )
            checks["mock_dispatch_durable_before_generation"] = dispatched == list(
                CALL_ORDER
            )
            checks["mock_saved_artifact_replays"] = (
                verify_run(actual, locked, read_journal(output / "journal.jsonl"))[
                    "status"
                ]
                == "PASS"
            )
            checks["mock_report_exact"] = (output / "report.md").read_text() == report(
                actual
            )
            try:
                run_once(
                    "SYNTHETIC_NO_MODEL",
                    lock_path,
                    checked_path,
                    directory / "another",
                    BASE_COMMIT,
                )
                denied = False
            except FileExistsError:
                denied = True
            checks["execution_identity_cannot_rerun"] = denied and len(dispatched) == 6

            # A simulated interruption consumes a separate synthetic execution identity.
            interrupted_lock = directory / "interrupted-lock.json"
            transport.write_new(interrupted_lock, locked)
            output = directory / "interrupted-run"
            dispatched.clear()

            class InterruptedRuntime(FakeRuntime):
                def invoke(
                    self, key: str, prompt: str, rendering: Mapping[str, Any]
                ) -> Json:
                    super().invoke(key, prompt, rendering)
                    raise KeyboardInterrupt

            with patch.object(transport, "LocalRuntime", InterruptedRuntime):
                try:
                    run_once(
                        "SYNTHETIC_NO_MODEL",
                        interrupted_lock,
                        checked_path,
                        output,
                        BASE_COMMIT,
                    )
                    interrupted = False
                except KeyboardInterrupt:
                    interrupted = True
                events = read_journal(output / "journal.jsonl")
                checks["interrupted_dispatch_retained_without_terminal"] = (
                    interrupted
                    and [row["kind"] for row in events]
                    == ["START", "DISPATCH", "INTERRUPTED"]
                    and not (output / "results.json").exists()
                )
                try:
                    run_once(
                        "SYNTHETIC_NO_MODEL",
                        interrupted_lock,
                        checked_path,
                        directory / "interrupted-retry",
                        BASE_COMMIT,
                    )
                    denied = False
                except FileExistsError:
                    denied = True
                checks["interruption_does_not_authorize_retry"] = (
                    denied and dispatched == [READY_KEYS[0]]
                )
    require(
        all(checks.values()),
        "SELF_TEST_FAILED:"
        + ",".join(key for key, passed in checks.items() if not passed),
    )
    return _seal(
        {
            "schema_version": "ebrt-source-field-self-test-" + VERSION,
            "status": "PASS",
            "logical_model_calls": 0,
            "synthetic_outputs_only": True,
            "checks": checks,
        }
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("self-test")
    spec = sub.add_parser("lock-spec")
    spec.add_argument("--output", type=Path, required=True)
    prep = sub.add_parser("preflight")
    prep.add_argument("--model", required=True)
    prep.add_argument("--lock", type=Path, required=True)
    prep.add_argument("--output", type=Path, required=True)
    run = sub.add_parser("run")
    run.add_argument("--model", required=True)
    run.add_argument("--lock", type=Path, required=True)
    run.add_argument("--preflight", type=Path, required=True)
    run.add_argument("--lock-commit", required=True)
    run.add_argument("--output", type=Path, required=True)
    run.add_argument("--execute-local-once", action="store_true", required=True)
    verify = sub.add_parser("verify")
    verify.add_argument("artifact", type=Path)
    verify.add_argument("--lock", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "self-test":
            result = self_test()
        elif args.command == "lock-spec":
            result = lock_spec()
            transport.write_new(args.output, result)
        elif args.command == "preflight":
            result = preflight(args.model, transport.load_json(args.lock))
            validate_preflight(result, transport.load_json(args.lock))
            transport.write_new(args.output, result)
        elif args.command == "run":
            artifact = run_once(
                args.model, args.lock, args.preflight, args.output, args.lock_commit
            )
            result = {
                "artifact_fingerprint_sha256": artifact["fingerprint_sha256"],
                "assessment": artifact["assessment"],
            }
        else:
            result = verify_run(
                transport.load_json(args.artifact),
                transport.load_json(args.lock),
                read_journal(args.artifact.parent / "journal.jsonl"),
            )
        print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
        return 0
    except (EBRTError, OSError, ValueError, subprocess.CalledProcessError) as error:
        print(
            json.dumps(
                {
                    "status": "ERROR",
                    "error_code": str(error)
                    if isinstance(error, EBRTError)
                    else type(error).__name__,
                }
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
