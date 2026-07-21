#!/usr/bin/env python3
"""Build the deterministic public projection for the v0.6.2.1 Reasoning IDE.

The builder reads the seven sealed result files, verifies every manifest-bound
source byte, and projects an explicit public allowlist. It performs no network
request and does not expose provider bodies, request identifiers, credentials,
or private reasoning text.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import socket
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


INSPECTOR_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = INSPECTOR_ROOT.parent
SOURCE_ROOT = (
    REPOSITORY_ROOT
    / "artifacts"
    / "apply_revision_acceptance_v0_6_2_1_live_r01"
)
PUBLIC_PATH = (
    INSPECTOR_ROOT
    / "public"
    / "data"
    / "ebrt-apply-revision-acceptance-v0.6.2.1.json"
)
SCHEMA_VERSION = "ebrt-apply-revision-ide-projection-v0.6.2.1"
EXPECTED_MANIFEST_SHA256 = (
    "532dd593ef4464d87dd02fd2eeaa712855f47e5de799c669889c0302ee2fe3a4"
)
EXPECTED_MANIFEST_FINGERPRINT = (
    "7f2b64794add0fa3bc9b8a0a4b3bd617cd8a1ac8cd862844899374886e0aa357"
)
EXPECTED_RESULT_FINGERPRINT = (
    "1ba3cfe9565124d92fa8db8222c4d44bc62a81e1da7c6fad07e24e9a8e7ad245"
)
EXPECTED_TRACE_FINGERPRINT = (
    "9ecad537a43a51f44e672c9ffb8c1544ff2fe430c2302f43f108c30e76094d14"
)
EXPECTED_PROJECTION_SHA256 = (
    "d2d9a1531bd384bfb7b7b2875e830289092d9b49d01198d3c6e7c5bddac497f2"
)


def _reject_constant(value: str) -> Any:
    raise ValueError(f"nonfinite JSON constant: {value}")


def _reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, child in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON key: {key}")
        value[key] = child
    return value


def _reject_nonfinite(value: Any) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("nonfinite JSON number")
    if isinstance(value, dict):
        for child in value.values():
            _reject_nonfinite(child)
    elif isinstance(value, list):
        for child in value:
            _reject_nonfinite(child)


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(
        path.read_bytes().decode("utf-8"),
        object_pairs_hook=_reject_duplicates,
        parse_constant=_reject_constant,
    )
    _reject_nonfinite(value)
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _pretty_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _fingerprint(value: dict[str, Any]) -> str:
    material = dict(value)
    material.pop("fingerprint_sha256", None)
    raw = json.dumps(
        material,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _seal(value: dict[str, Any]) -> dict[str, Any]:
    sealed = dict(value)
    sealed.pop("fingerprint_sha256", None)
    sealed["fingerprint_sha256"] = _fingerprint(sealed)
    return sealed


def _validate_seal(value: dict[str, Any], label: str) -> None:
    if value.get("fingerprint_sha256") != _fingerprint(value):
        raise ValueError(f"{label} fingerprint mismatch")


@contextmanager
def _deny_network() -> Iterator[None]:
    original_socket = socket.socket
    original_create_connection = socket.create_connection

    def denied(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("network access is forbidden while building the IDE projection")

    socket.socket = denied  # type: ignore[assignment]
    socket.create_connection = denied  # type: ignore[assignment]
    try:
        yield
    finally:
        socket.socket = original_socket  # type: ignore[assignment]
        socket.create_connection = original_create_connection  # type: ignore[assignment]


def _verify_sources(
    manifest: dict[str, Any],
    *,
    source_root: Path,
) -> dict[str, str]:
    manifest_path = source_root / "manifest.json"
    if _sha256(manifest_path) != EXPECTED_MANIFEST_SHA256:
        raise ValueError("publication manifest is not the pinned live r01 bytes")
    _validate_seal(manifest, "manifest")
    if manifest.get("schema_version") != "ebrt-apply-revision-manifest-v0.6.2.1-r01":
        raise ValueError("unexpected result manifest schema")
    if manifest.get("status") != "SEALED_APPLY_REVISION_RESULT":
        raise ValueError("result manifest is not sealed")
    if manifest.get("fingerprint_sha256") != EXPECTED_MANIFEST_FINGERPRINT:
        raise ValueError("publication manifest fingerprint changed")
    if manifest.get("result_fingerprint_sha256") != EXPECTED_RESULT_FINGERPRINT:
        raise ValueError("publication result fingerprint changed")

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict) or set(artifacts) != {
        "apply_revision_trace.json",
        "attempt_journal.jsonl",
        "calls.jsonl",
        "provider_inputs.json",
        "report.md",
        "result.json",
    }:
        raise ValueError("sealed artifact inventory changed")

    verified: dict[str, str] = {}
    for filename, metadata in artifacts.items():
        if not isinstance(metadata, dict):
            raise ValueError(f"invalid manifest entry: {filename}")
        path = source_root / filename
        if not path.is_file():
            raise ValueError(f"missing sealed source: {filename}")
        observed_sha = _sha256(path)
        observed_bytes = path.stat().st_size
        if observed_sha != metadata.get("sha256") or observed_bytes != metadata.get("bytes"):
            raise ValueError(f"sealed source drifted: {filename}")
        verified[filename] = observed_sha
    return verified


def build_projection(*, source_root: Path = SOURCE_ROOT) -> dict[str, Any]:
    manifest = _load_json(source_root / "manifest.json")
    source_sha256 = _verify_sources(manifest, source_root=source_root)
    result = _load_json(source_root / "result.json")
    inputs = _load_json(source_root / "provider_inputs.json")
    trace = _load_json(source_root / "apply_revision_trace.json")

    _validate_seal(result, "result")
    _validate_seal(trace, "trace")
    if result.get("fingerprint_sha256") != manifest.get("result_fingerprint_sha256"):
        raise ValueError("result fingerprint is not manifest-bound")
    if result.get("fingerprint_sha256") != EXPECTED_RESULT_FINGERPRINT:
        raise ValueError("result is not the pinned live r01 publication")
    if trace.get("fingerprint_sha256") != EXPECTED_TRACE_FINGERPRINT:
        raise ValueError("trace is not the pinned live r01 publication")
    if result.get("status") != "COMPLETE_EXACT_TWO_TERMINALS":
        raise ValueError("result is not a complete exact two-terminal run")
    if trace.get("effect_attribution_status") != "NOT_ASSESSED":
        raise ValueError("effect attribution boundary changed")
    expected_decision = {
        "run_status": "COMPLETE_EXACT_TWO_TERMINALS",
        "mechanism_status": "PASS",
        "before_status": "PASS_THEN_STALE",
        "after_status": "PASS_STRICT_POST_EVENT",
        "diff_status": "OBSERVED_EXPECTED_PUBLIC_DIFF",
        "product_acceptance_status": "PASS",
        "effect_attribution_status": "NOT_ASSESSED",
        "terminal_decision": "ACCEPT_APPLY_REVISION_PATH",
    }
    if result.get("decision") != expected_decision:
        raise ValueError("live r01 product decision changed")

    payloads = inputs.get("payloads")
    if not isinstance(payloads, list) or len(payloads) != 2:
        raise ValueError("expected exactly two provider inputs")
    before_payload = payloads[0]["payload"]
    after_payload = payloads[1]["payload"]
    evidence = after_payload["all_raw_evidence"]
    if [row["evidence_id"] for row in evidence] != ["R1", "R2", "R3", "R4", "R5", "R6"]:
        raise ValueError("evidence order changed")

    before = result["executions"]["before_event"]
    after = result["executions"]["after_event"]
    control = trace["control_map"]
    actuator = trace["compiled_actuator"]
    grades = result["grades"]
    output_diff = result["output_diff"]
    answer_diff = output_diff["answer"]
    if answer_diff != {
        "before": before["public_output"]["current_answer"],
        "after": after["public_output"]["current_answer"],
    }:
        raise ValueError("answer diff is not bound to the provider outputs")
    if result["checks"]["product"]["expected_public_diff_exact"] is not True:
        raise ValueError("recorded answer diff did not pass its exact contract")

    invalidation_edges = after["compiled_output"]["invalidation_edges"]
    if len(invalidation_edges) != 1:
        raise ValueError("expected one recorded invalidation edge")
    invalidation_edge = invalidation_edges[0]
    stable_target_ids = output_diff["stable_target_ids"]
    if len(stable_target_ids) != 1:
        raise ValueError("expected one recorded stable target")
    stable_target = next(
        row
        for row in output_diff["target_values"]
        if row["target_id"] == stable_target_ids[0]
    )
    if stable_target["changed"] is not False:
        raise ValueError("recorded stable target changed")
    fact_support = sorted(
        {
            evidence_id
            for target in after["compiled_output"]["targets"]
            if target["target_type"] == "fact"
            for evidence_id in target["all_active_evidence_ids"]
        }
    )

    projection = {
        "schema_version": SCHEMA_VERSION,
        "mode": "RECORDED_ARTIFACT_PLAYBACK",
        "case": {
            "case_id": result["case_id"],
            "version": "v0.6.2.1",
            "question": before_payload["question"],
            "model": before["receipt"]["returned_model"],
        },
        "source": {
            "manifest_fingerprint_sha256": manifest["fingerprint_sha256"],
            "manifest_sha256": _sha256(source_root / "manifest.json"),
            "result_fingerprint_sha256": result["fingerprint_sha256"],
            "trace_fingerprint_sha256": trace["fingerprint_sha256"],
            "artifact_sha256": source_sha256,
        },
        "evidence": [
            {
                "evidence_id": row["evidence_id"],
                "text": row["text"],
                "role": (
                    "late_event"
                    if row["evidence_id"] == "R6"
                    else "invalidated"
                    if row["evidence_id"] == "R3"
                    else "stable_constraint"
                    if row["evidence_id"] == "R5"
                    else "public_evidence"
                ),
            }
            for row in evidence
        ],
        "before": {
            "horizon_evidence_ids": before["compiled_output"]["source_horizon_evidence_ids"],
            "answer": before["public_output"]["current_answer"],
            "selected_closure_id": before["public_output"]["selected_closure_id"],
            "target_values": before["public_output"]["target_values"],
            "active_support_evidence_ids": before["compiled_output"]["active_support_evidence_ids"],
            "provider_output_fingerprint_sha256": before["compiled_output"]["normalized_output_fingerprint_sha256"],
            "own_horizon_status": grades["before"]["status"],
            "post_event_status": grades["before_post_event_stale"]["post_grade"]["status"],
            "post_event_failed_axes": grades["before_post_event_stale"]["failed_axes"],
        },
        "late_event": {
            "evidence_id": "R6",
            "event_id": actuator["event_id"],
            "text": next(row["text"] for row in evidence if row["evidence_id"] == "R6"),
            "invalidated_evidence_ids": ["R3"],
            "stable_evidence_ids": ["R5"],
        },
        "revision_engine": {
            "actual_before_state": control["actual_before_state"],
            "surrogate": {
                "objective_before": control["objective_before"],
                "objective_after": control["objective_after"],
                "terminal_target": control["terminal_target"],
                "dtype": control["dtype"],
                "backward_calls": control["backward_calls"],
                "maximum_finite_difference_error": control["maximum_finite_difference_error"],
            },
            "public_control_map": {
                "fingerprint_sha256": control["fingerprint_sha256"],
                "control_l2": control["control_l2"],
                "max_control_l2": control["max_control_l2"],
                "credit_rows": control["credit_rows"],
                "checks": control["checks"],
            },
            "compiled_actuator": {
                "fingerprint_sha256": actuator["fingerprint_sha256"],
                "reinspect_evidence_ids": actuator["reinspect_evidence_ids"],
                "suppress_evidence_ids": actuator["suppress_evidence_ids"],
                "preserve_evidence_ids": actuator["preserve_evidence_ids"],
                "correction_evidence_id": actuator["correction_evidence_id"],
                "gradient_stops_here": actuator["gradient_stops_here"],
            },
            "boundary": "Gradient stops at the public control map. GPT-5.6 is not backpropagated through.",
        },
        "after": {
            "answer": after["public_output"]["current_answer"],
            "selected_closure_id": after["public_output"]["selected_closure_id"],
            "target_values": after["public_output"]["target_values"],
            "active_support_evidence_ids": after["compiled_output"]["active_support_evidence_ids"],
            "invalidated_evidence_ids": after["compiled_output"]["invalidated_evidence_ids"],
            "invalidation_edges": after["compiled_output"]["invalidation_edges"],
            "provider_output_fingerprint_sha256": after["compiled_output"]["normalized_output_fingerprint_sha256"],
            "strict_status": grades["after"]["status"],
            "fact_local_lineage_status": grades["after"]["fact_local_lineage_status"],
        },
        "output_diff": output_diff,
        "verification": [
            {
                "label": "Answer diff",
                "detail": f"{answer_diff['before']} → {answer_diff['after']}",
                "status": "PASS",
            },
            {
                "label": "Invalidated evidence",
                "detail": (
                    f"{invalidation_edge['target_evidence_id']} invalidated by "
                    f"{invalidation_edge['source_evidence_id']}"
                ),
                "status": grades["after"]["invalidation_status"],
            },
            {
                "label": "Stable fact preserved",
                "detail": (
                    f"{' + '.join(actuator['preserve_evidence_ids'])} · "
                    f"{stable_target['after']}"
                ),
                "status": grades["after"]["stable_fact_status"],
            },
            {
                "label": "Fact-local lineage",
                "detail": f"{' + '.join(fact_support)} closed",
                "status": grades["after"]["fact_local_lineage_status"],
            },
        ],
        "decision": result["decision"],
        "accounting": result["accounting"],
        "claim_boundary": result["claim_boundary"],
    }
    return projection


def validate_projection() -> dict[str, Any]:
    projection = build_projection()
    observed = PUBLIC_PATH.read_bytes()
    expected = _pretty_bytes(projection)
    if observed != expected:
        raise ValueError("committed public projection is not the exact deterministic derivation")
    observed_sha256 = hashlib.sha256(observed).hexdigest()
    if observed_sha256 != EXPECTED_PROJECTION_SHA256:
        raise ValueError("committed public projection is not the reviewed live r01 bytes")
    return {
        "status": "PASS",
        "projection_sha256": observed_sha256,
        "source_manifest_sha256": _sha256(SOURCE_ROOT / "manifest.json"),
        "network_calls": 0,
    }


def self_test() -> dict[str, Any]:
    with _deny_network():
        first_projection = build_projection()
        first = _pretty_bytes(first_projection)
        second = _pretty_bytes(build_projection())
        if first != second:
            raise AssertionError("projection is not byte deterministic")
        validated = validate_projection()
        answer_row = first_projection["verification"][0]
        displayed_values_derived = (
            answer_row["detail"]
            == (
                f"{first_projection['before']['answer']} → "
                f"{first_projection['after']['answer']}"
            )
            and answer_row["status"] == "PASS"
            and first_projection["decision"]["product_acceptance_status"] == "PASS"
        )

        with tempfile.TemporaryDirectory(prefix="ebrt-ide-projection-tamper-") as raw_tmp:
            tampered_root = Path(raw_tmp) / "artifact"
            shutil.copytree(SOURCE_ROOT, tampered_root)
            tampered_result = _load_json(tampered_root / "result.json")
            tampered_result["executions"]["after_event"]["public_output"][
                "current_answer"
            ] = "POLISH"
            tampered_result["decision"]["product_acceptance_status"] = "FAIL"
            tampered_result = _seal(tampered_result)
            result_bytes = _pretty_bytes(tampered_result)
            (tampered_root / "result.json").write_bytes(result_bytes)

            tampered_manifest = _load_json(tampered_root / "manifest.json")
            tampered_manifest["artifacts"]["result.json"] = {
                "bytes": len(result_bytes),
                "sha256": hashlib.sha256(result_bytes).hexdigest(),
            }
            tampered_manifest["result_fingerprint_sha256"] = tampered_result[
                "fingerprint_sha256"
            ]
            tampered_manifest = _seal(tampered_manifest)
            (tampered_root / "manifest.json").write_bytes(
                _pretty_bytes(tampered_manifest)
            )
            try:
                build_projection(source_root=tampered_root)
                coherent_publication_tamper_rejected = False
            except ValueError as error:
                coherent_publication_tamper_rejected = (
                    "pinned live r01 bytes" in str(error)
                )
        if not coherent_publication_tamper_rejected:
            raise AssertionError("coherently resealed publication tamper was accepted")
        if not displayed_values_derived:
            raise AssertionError("displayed acceptance values are not source-derived")
    return {
        **validated,
        "coherently_resealed_publication_tamper_rejected": True,
        "deterministic_rebuild": True,
        "displayed_values_derived": True,
        "exact_publication_pinned": True,
        "sealed_sources_verified": True,
        "provider_secrets_projected": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("print", "validate", "self-test"))
    args = parser.parse_args()
    if args.command == "print":
        print(_pretty_bytes(build_projection()).decode("utf-8"), end="")
        return
    payload = validate_projection() if args.command == "validate" else self_test()
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
