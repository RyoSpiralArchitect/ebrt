#!/usr/bin/env python3
"""Sealed 16-call hosted execution for EBRT v0.6.3 actuator calibration.

The existing v0.6.3 monolith remains the network-zero mechanism owner.  This
successor imports its exact projection, strict provider-output schema, graph
compiler, and frozen endpoint arithmetic.  It adds only an irreversible hosted
runner, a separately frozen live policy, durable public receipts, and a local
artifact validator.

No command retries, resumes, backfills, or runs a subset of the block.  Semantic
gold is first parsed only after all sixteen fixed attempts have returned one
schema-valid, compiler-valid public output.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import shutil
import socket
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterator, Mapping, Sequence
from unittest import mock

from openai import OpenAI

import actuator_calibration_v0_6_3 as core
from language_replay_bridge_v0_4 import ProviderReceipt, canonical_json, fingerprint
from openai_response_boundary_v0_4_3 import (
    BOUNDARY_REASON_CODES_BY_PHASE,
    EXPECTED_OPENAI_SDK_VERSION,
    EXPECTED_PYDANTIC_VERSION,
    RECEIPT_SCHEMA_VERSION,
    InstrumentedResponsesClientBase,
    OpenAIProviderBoundaryError,
)


ROOT = Path(__file__).resolve().parent
LOCK_PATH = ROOT / "policy_lock_actuator_calibration_v0_6_3_live_r01.json"
PREFLIGHT_DIR = ROOT / "artifacts" / "actuator_calibration_v0_6_3_preflight"
COMMITTED_PROJECTION_PATH = PREFLIGHT_DIR / "projection_bundle.json"
COMMITTED_PREFLIGHT_MANIFEST_PATH = PREFLIGHT_DIR / "manifest.json"
DEFAULT_OUTPUT = ROOT / "artifacts" / "actuator_calibration_v0_6_3_live_r01"
EXECUTION_AUTHORIZATION_TAG = "v0.6.3-live-r01-authorized"

PRELIGHT_ANCHOR_TAG_OBJECT = "d569bf5960fea7c72f572a7b204288837a499756"
PRELIGHT_ANCHOR_COMMIT = "97b8d63b32e07664e3f16b5f13df91309fbb40ee"
PRELIGHT_MANIFEST_BYTES_SHA256 = (
    "f5de1d69e50ce3da34532e04d2b2a1f27125fa933c5338864f172145f32a3853"
)
EFFECT_EPSILON = 1.0e-12

LOCK_SCHEMA = "ebrt-actuator-calibration-live-policy-v0.6.3-r01"
RESULT_SCHEMA = "ebrt-actuator-calibration-live-result-v0.6.3-r01"
CALL_SCHEMA = "ebrt-actuator-calibration-live-call-v0.6.3-r01"
JOURNAL_SCHEMA = "ebrt-actuator-calibration-live-journal-v0.6.3-r01"
PROVIDER_INPUTS_SCHEMA = "ebrt-actuator-calibration-live-inputs-v0.6.3-r01"
MANIFEST_SCHEMA = "ebrt-actuator-calibration-live-manifest-v0.6.3-r01"

ARTIFACT_FILES = (
    "result.json",
    "calls.jsonl",
    "attempt_journal.jsonl",
    "provider_inputs.json",
    "projection_bundle.json",
    "report.md",
    "manifest.json",
)

TERMINAL_STATUSES = (
    "INCOMPLETE_NOT_ASSESSED",
    "STOP_OUTPUT_CONTRACT",
    "STOP_CHANNEL_ADHERENCE_NULL",
    "STOP_ACTUATOR_ECHO_ONLY",
    "STOP_GRADIENT_PLACEMENT_NULL",
    "PROMOTE_V0_6_4_ACTUATOR_GATE",
)

SOURCE_PATHS = {
    "runner": "run_actuator_calibration_v0_6_3_live_r01.py",
    "core": "actuator_calibration_v0_6_3.py",
    "fixture": "fixtures/actuator_calibration_v0_6_3.json",
    "post_call_gold": "fixtures/actuator_calibration_gold_v0_6_3.json",
    "zero_call_policy": "policy_lock_actuator_calibration_v0_6_3.json",
    "zero_call_manifest": "artifacts/actuator_calibration_v0_6_3_preflight/manifest.json",
    "zero_call_projection": "artifacts/actuator_calibration_v0_6_3_preflight/projection_bundle.json",
    "response_boundary": "openai_response_boundary_v0_4_3.py",
    "provider_base": "openai_reasoning_provider_v0_4.py",
    "receipt_contract": "language_replay_bridge_v0_4.py",
    "requirements": "requirements.txt",
    "requirements_live": "requirements-live.txt",
    "protocol_note": "docs/RND_ACTUATOR_CALIBRATION_V0_6_3_LIVE_R01.md",
}

CLAIM_BOUNDARY = (
    "This is one sealed two-case, two-trial actuator calibration block, not a population estimate or quality benchmark.",
    "The provider sees raw evidence, a neutral candidate scaffold, and one bounded public reinspection schedule; it never sees arm labels, q vectors, accepted paths, gold, or grades.",
    "The local float64 backward pass ends before JSON; no gradient crosses GPT or the provider boundary.",
    "Schedule adherence is a public receipt and is never counted as downstream propagation.",
    "D is constructed and evaluated in the same q^D coordinate system, so a positive result is construct-aligned calibration rather than independent validation.",
    "Answer and lineage quality are secondary diagnostics and do not gate actuator promotion.",
    "Provider receipts and execution provenance are operator-attested local records, not cryptographically authenticated or provider-signed proof of hosted execution.",
    "The authorization tag does not authenticate operator identity or guarantee global exactly-once execution across clones.",
    "The semantic-gold barrier is a locked-code Path.read_bytes guard, not an operating-system sandbox against arbitrary processes.",
    "No result supports hidden-state editing, causal superiority, general quality improvement, or general reasoning improvement.",
)

ACTUATOR_INSTRUCTIONS = (
    "Return only the strict public actuator-calibration output. Treat the ordered "
    "raw evidence as the sole semantic authority. The candidate scaffold is the "
    "complete allowed edge universe; select only supplied candidate edge IDs and "
    "select one minimal, acyclic support graph that supports the primary and stable "
    "decision slots while honoring explicit invalidation. The revision_actuator is "
    "bounded operation-level guidance, not evidence, truth, probability, an answer, "
    "or permission to override raw evidence. If no_reordering is true, inspect raw "
    "evidence in its supplied order. Otherwise inspect the three evidence rows with "
    "positive priority tiers from highest to lowest tier, retaining supplied order "
    "for ties. Return exactly those three inspected evidence IDs in inspection_plan. "
    "Derive current_answer and every decision-slot value only from raw evidence. "
    "Return every supplied slot ID exactly once and choose only an allowed value. "
    "Do not return private chain-of-thought, hidden reasoning, free-form rationale, "
    "a model-written closure, or any field outside the strict structured schema."
)
INSTRUCTIONS_FINGERPRINT = fingerprint(ACTUATOR_INSTRUCTIONS)
RESPONSE_SCHEMA_FINGERPRINT = fingerprint(
    core.ActuatorCalibrationOutput.model_json_schema()
)


class ActuatorLiveExecutionError(RuntimeError):
    """A live policy, execution, receipt, artifact, or validation gate failed."""


def _staging_directory(output: Path) -> Path:
    return output.with_name(f".{output.name}.inflight")


def _canonical_bytes(value: Any, *, trailing_newline: bool = False) -> bytes:
    text = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    if trailing_newline:
        text += "\n"
    return text.encode("utf-8")


def _pretty_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        + "\n"
    ).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_path(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _clone(value: Any) -> Any:
    return json.loads(_canonical_bytes(value))


def _seal(value: Mapping[str, Any]) -> dict[str, Any]:
    output = _clone(dict(value))
    output["fingerprint_sha256"] = fingerprint(output)
    return output


def _is_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _is_git_oid(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 40
        and all(character in "0123456789abcdef" for character in value)
    )


def _reject_constant(value: str) -> Any:
    raise ActuatorLiveExecutionError(f"nonfinite JSON constant rejected: {value}")


def _reject_duplicates(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise ActuatorLiveExecutionError(f"duplicate JSON key rejected: {key}")
        output[key] = value
    return output


def _strict_load(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    try:
        value = json.loads(
            raw.decode("utf-8"),
            parse_constant=_reject_constant,
            object_pairs_hook=_reject_duplicates,
        )
    except ActuatorLiveExecutionError:
        raise
    except Exception as error:
        raise ActuatorLiveExecutionError(f"invalid JSON: {path}") from error
    if not isinstance(value, dict):
        raise ActuatorLiveExecutionError(f"JSON root is not an object: {path}")
    return value


def _file_receipt(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    return {
        "path": str(path.relative_to(ROOT)),
        "bytes": len(raw),
        "sha256": _sha256_bytes(raw),
    }


def _file_receipts(
    paths: Mapping[str, str],
    *,
    frozen_post_call_gold_receipt: Mapping[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    receipts: dict[str, dict[str, Any]] = {}
    for label, path in paths.items():
        if label == "post_call_gold" and frozen_post_call_gold_receipt is not None:
            receipt = _clone(frozen_post_call_gold_receipt)
            if (
                set(receipt) != {"path", "bytes", "sha256"}
                or receipt["path"] != path
                or type(receipt["bytes"]) is not int
                or receipt["bytes"] <= 0
                or not _is_sha256(receipt["sha256"])
            ):
                raise ActuatorLiveExecutionError(
                    "frozen post-call gold receipt invalid"
                )
            receipts[label] = receipt
        else:
            receipts[label] = _file_receipt(ROOT / path)
    return receipts


def _anchored_post_call_gold_receipt() -> dict[str, Any]:
    if (
        _sha256_path(COMMITTED_PREFLIGHT_MANIFEST_PATH)
        != PRELIGHT_MANIFEST_BYTES_SHA256
    ):
        raise ActuatorLiveExecutionError("committed preflight manifest bytes drifted")
    manifest = _strict_load(COMMITTED_PREFLIGHT_MANIFEST_PATH)
    source_receipts = manifest.get("source_receipts")
    if not isinstance(source_receipts, Mapping):
        raise ActuatorLiveExecutionError("committed source receipts missing")
    receipt = source_receipts.get("post_call_gold")
    expected_path = SOURCE_PATHS["post_call_gold"]
    if (
        not isinstance(receipt, Mapping)
        or set(receipt) != {"path", "bytes", "sha256"}
        or receipt.get("path") != expected_path
        or type(receipt.get("bytes")) is not int
        or receipt["bytes"] <= 0
        or not _is_sha256(receipt.get("sha256"))
    ):
        raise ActuatorLiveExecutionError("committed post-call gold receipt invalid")
    return _clone(receipt)


def _source_snapshot(lock: Mapping[str, Any]) -> dict[str, str]:
    snapshot: dict[str, str] = {}
    for label, receipt in lock["sources"].items():
        if label == "post_call_gold":
            continue
        snapshot[label] = _sha256_path(ROOT / receipt["path"])
    return snapshot


def _runtime_contract() -> dict[str, Any]:
    return {
        "provider": "openai_responses",
        "api": "responses.with_raw_response.parse+raw.parse",
        "model": core.MODEL,
        "reasoning_effort": core.REASONING_EFFORT,
        "max_output_tokens": core.MAX_OUTPUT_TOKENS,
        "timeout_seconds": core.TIMEOUT_SECONDS,
        "sdk_retries": 0,
        "store": False,
        "previous_response_id": False,
        "service_tier": "default",
        "truncation": "disabled",
        "openai_sdk": importlib.metadata.version("openai"),
        "pydantic": importlib.metadata.version("pydantic"),
        "torch": core.torch.__version__,
        "python": platform.python_version(),
        "machine": platform.machine(),
    }


def _projection_schedule(projection: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = projection.get("public_treatment_key")
    if not isinstance(rows, list) or len(rows) != 16:
        raise ActuatorLiveExecutionError("projection treatment schedule is not 16 rows")
    ordered = sorted((_clone(row) for row in rows), key=lambda row: row["run_position"])
    expected_positions = list(range(1, 17))
    if [row.get("run_position") for row in ordered] != expected_positions:
        raise ActuatorLiveExecutionError("projection run positions drifted")
    return ordered


def policy_lock_material() -> dict[str, Any]:
    """Build the live authorization lock without parsing semantic gold bytes."""

    committed_projection = _strict_load(COMMITTED_PROJECTION_PATH)
    committed_manifest = _strict_load(COMMITTED_PREFLIGHT_MANIFEST_PATH)
    schedule = _projection_schedule(committed_projection)
    return _seal(
        {
            "schema_version": LOCK_SCHEMA,
            "status": "PREREGISTERED_EXACT_16_CALL_LIVE_BLOCK",
            "preflight_anchor_tag_object": PRELIGHT_ANCHOR_TAG_OBJECT,
            "preflight_anchor_commit": PRELIGHT_ANCHOR_COMMIT,
            "preflight_manifest_bytes_sha256": PRELIGHT_MANIFEST_BYTES_SHA256,
            "preflight_projection_fingerprint_sha256": committed_projection[
                "fingerprint_sha256"
            ],
            "preflight_manifest_fingerprint_sha256": committed_manifest[
                "fingerprint_sha256"
            ],
            "sources": _file_receipts(
                SOURCE_PATHS,
                frozen_post_call_gold_receipt=_anchored_post_call_gold_receipt(),
            ),
            "runtime": _runtime_contract(),
            "instructions_fingerprint_sha256": INSTRUCTIONS_FINGERPRINT,
            "response_schema_fingerprint_sha256": RESPONSE_SCHEMA_FINGERPRINT,
            "execution": {
                "provider_calls_authorized": 16,
                "exact_attempt_count": 16,
                "call_schedule": schedule,
                "no_retry": True,
                "no_resume": True,
                "no_backfill": True,
                "authorization_tag": EXECUTION_AUTHORIZATION_TAG,
                "authorization_requires_origin_main_ancestry": True,
                "authorization_requires_preflight_anchor_ancestry": True,
                "provenance_scope": "OPERATOR_ATTESTED_NOT_CRYPTOGRAPHICALLY_AUTHENTICATED",
                "gold_loaded_after_complete_compilation_only": True,
            },
            "endpoints": {
                "effect_epsilon": EFFECT_EPSILON,
                "x_z_adherence": "all four X and all four Z receipts exactly match their frozen schedules",
                "x_propagation": "X/Z adherence passes, sum(delta_XZ)>epsilon, and at least 3 of 4 delta_XZ>epsilon",
                "d_c_adherence": "all four D and all four C receipts exactly match their frozen schedules",
                "d_placement": "all D/C receipts adhere, sum(delta_DC)>epsilon, and at least 3 of 4 delta_DC>epsilon",
                "quality_status": "secondary_only_not_a_promotion_gate",
                "schedule_receipt_scored_as_downstream": False,
            },
            "terminal_statuses": list(TERMINAL_STATUSES),
            "artifact": {
                "directory": str(DEFAULT_OUTPUT.relative_to(ROOT)),
                "files": list(ARTIFACT_FILES),
            },
            "claim_boundary": list(CLAIM_BOUNDARY),
        }
    )


def _load_lock() -> dict[str, Any]:
    lock = _strict_load(LOCK_PATH)
    expected = policy_lock_material()
    if lock != expected:
        raise ActuatorLiveExecutionError(
            "live policy lock or locked source bytes drifted"
        )
    if lock.get("fingerprint_sha256") != fingerprint(
        {
            key: _clone(value)
            for key, value in lock.items()
            if key != "fingerprint_sha256"
        }
    ):
        raise ActuatorLiveExecutionError("live policy fingerprint drifted")
    return lock


@contextmanager
def _semantic_gold_denied() -> Iterator[dict[str, int]]:
    """Fail before semantic gold bytes can be accessed in a blinded phase."""

    counts = {"attempted_gold_accesses": 0}
    original = Path.read_bytes
    gold_path = core.GOLD_PATH.resolve()

    def guarded(path: Path) -> bytes:
        if path.resolve() == gold_path:
            counts["attempted_gold_accesses"] += 1
            raise ActuatorLiveExecutionError(
                "semantic gold access attempted before complete compilation"
            )
        return original(path)

    with mock.patch.object(Path, "read_bytes", guarded):
        yield counts


def _git_text(*args: str) -> str:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise ActuatorLiveExecutionError(
            "git authorization boundary unavailable"
        ) from error
    return completed.stdout.strip()


def _tag_ref_exists(tag_name: str) -> bool:
    try:
        completed = subprocess.run(
            ["git", "show-ref", "--verify", "--quiet", f"refs/tags/{tag_name}"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise ActuatorLiveExecutionError(
            "git authorization boundary unavailable"
        ) from error
    if completed.returncode == 0:
        return True
    if completed.returncode == 1:
        return False
    raise ActuatorLiveExecutionError("git authorization ref probe failed")


def _observe_execution_authorization(*, allow_pending: bool) -> dict[str, Any]:
    repository_root = Path(_git_text("rev-parse", "--show-toplevel")).resolve()
    if repository_root != ROOT:
        raise ActuatorLiveExecutionError("execution repository root drifted")
    if not _tag_ref_exists(EXECUTION_AUTHORIZATION_TAG):
        if allow_pending:
            return {
                "status": "PENDING_ANNOTATED_TAG",
                "tag_name": EXECUTION_AUTHORIZATION_TAG,
            }
        raise ActuatorLiveExecutionError("execution authorization tag is unavailable")
    tag_object = _git_text(
        "rev-parse", "--verify", f"refs/tags/{EXECUTION_AUTHORIZATION_TAG}"
    )
    if not _is_git_oid(tag_object) or _git_text("cat-file", "-t", tag_object) != "tag":
        raise ActuatorLiveExecutionError("execution authorization tag is not annotated")
    commit = _git_text(
        "rev-parse", f"refs/tags/{EXECUTION_AUTHORIZATION_TAG}^{{commit}}"
    )
    head = _git_text("rev-parse", "HEAD")
    if not _is_git_oid(commit) or not _is_git_oid(head):
        raise ActuatorLiveExecutionError("execution authorization commit is malformed")
    try:
        _git_text("merge-base", "--is-ancestor", commit, "refs/remotes/origin/main")
    except ActuatorLiveExecutionError as error:
        raise ActuatorLiveExecutionError(
            "authorized execution commit is not reachable from local origin/main"
        ) from error
    try:
        _git_text("merge-base", "--is-ancestor", PRELIGHT_ANCHOR_COMMIT, commit)
    except ActuatorLiveExecutionError as error:
        raise ActuatorLiveExecutionError(
            "authorized execution commit does not descend from the preflight anchor"
        ) from error
    if head == commit:
        locked_paths = [
            receipt_path
            for label, receipt_path in SOURCE_PATHS.items()
            if label != "post_call_gold"
        ] + [str(LOCK_PATH.relative_to(ROOT))]
        try:
            _git_text("ls-files", "--error-unmatch", "--", *locked_paths)
            _git_text("diff", "--quiet", commit, "--", *locked_paths)
        except ActuatorLiveExecutionError as error:
            raise ActuatorLiveExecutionError(
                "authorized execution sources are untracked or dirty"
            ) from error
    return {
        "status": "AUTHORIZED_ANNOTATED_TAG",
        "tag_name": EXECUTION_AUTHORIZATION_TAG,
        "tag_object": tag_object,
        "authorized_commit": commit,
        "execution_head_commit": head,
        "head_matches_authorized_commit": head == commit,
        "provenance_scope": "OPERATOR_ATTESTED_NOT_CRYPTOGRAPHICALLY_AUTHENTICATED",
    }


def _validate_recorded_execution_authorization(
    authorization: Mapping[str, Any],
) -> None:
    expected_keys = {
        "status",
        "tag_name",
        "tag_object",
        "authorized_commit",
        "execution_head_commit",
        "head_matches_authorized_commit",
        "provenance_scope",
    }
    if (
        set(authorization) != expected_keys
        or authorization.get("status") != "AUTHORIZED_ANNOTATED_TAG"
        or authorization.get("tag_name") != EXECUTION_AUTHORIZATION_TAG
        or authorization.get("head_matches_authorized_commit") is not True
        or authorization.get("authorized_commit")
        != authorization.get("execution_head_commit")
        or authorization.get("provenance_scope")
        != "OPERATOR_ATTESTED_NOT_CRYPTOGRAPHICALLY_AUTHENTICATED"
    ):
        raise ActuatorLiveExecutionError("recorded execution authorization invalid")
    observed = _observe_execution_authorization(allow_pending=False)
    if (
        observed["tag_object"] != authorization["tag_object"]
        or observed["authorized_commit"] != authorization["authorized_commit"]
    ):
        raise ActuatorLiveExecutionError("execution authorization tag drifted")


class OpenAIActuatorProviderLiveR01(InstrumentedResponsesClientBase):
    """One-attempt provider for the frozen v0.6.3 public output schema."""

    def __init__(self, *, client: OpenAI | Any | None = None) -> None:
        super().__init__(
            model=core.MODEL,
            reasoning_effort=core.REASONING_EFFORT,
            timeout_seconds=float(core.TIMEOUT_SECONDS),
            client=client,
        )

    @property
    def provenance(self) -> dict[str, Any]:
        return {
            **_runtime_contract(),
            "instructions_fingerprint_sha256": INSTRUCTIONS_FINGERPRINT,
            "response_schema_fingerprint_sha256": RESPONSE_SCHEMA_FINGERPRINT,
            "receipt_schema_version": RECEIPT_SCHEMA_VERSION,
        }

    def generate(
        self, input_payload: Mapping[str, Any]
    ) -> tuple[dict[str, Any], ProviderReceipt]:
        core.validate_provider_payload(input_payload)
        public_input = json.loads(canonical_json(dict(input_payload)))
        parsed, receipt = self._parse(
            input_payload=public_input,
            instructions=ACTUATOR_INSTRUCTIONS,
            text_format=core.ActuatorCalibrationOutput,
            max_output_tokens=core.MAX_OUTPUT_TOKENS,
        )
        if not isinstance(parsed, core.ActuatorCalibrationOutput):
            raise AssertionError("provider returned the wrong structured-output type")
        public_output = parsed.model_dump(mode="json")
        reparsed = core.ActuatorCalibrationOutput.model_validate(public_output)
        if canonical_json(reparsed.model_dump(mode="json")) != canonical_json(
            public_output
        ):
            raise AssertionError("public actuator output did not round-trip exactly")
        return public_output, receipt


class _FakeRawResponse:
    def __init__(self, parsed: core.ActuatorCalibrationOutput) -> None:
        self.status_code = 200
        self.headers = {"x-request-id": "v063-live-offline-server-request"}
        self.content = b'{"offline":"v063-live-provider-self-test"}'
        self._parsed = parsed

    def parse(self) -> Any:
        usage = SimpleNamespace(
            input_tokens=41,
            output_tokens=23,
            total_tokens=64,
            input_tokens_details=SimpleNamespace(
                cached_tokens=0,
                cache_write_tokens=0,
            ),
            output_tokens_details=SimpleNamespace(reasoning_tokens=5),
        )
        return SimpleNamespace(
            id="resp-v063-live-offline",
            model=core.MODEL,
            service_tier="default",
            status="completed",
            error=None,
            incomplete_details=None,
            output=[],
            output_parsed=self._parsed,
            usage=usage,
        )


class _FakeRawParseEndpoint:
    def __init__(self, parsed: core.ActuatorCalibrationOutput) -> None:
        self._parsed = parsed
        self.calls: list[dict[str, Any]] = []

    def parse(self, **kwargs: Any) -> _FakeRawResponse:
        self.calls.append(dict(kwargs))
        return _FakeRawResponse(self._parsed)


class _FakeOpenAIClient:
    def __init__(self, parsed: core.ActuatorCalibrationOutput) -> None:
        self.max_retries = 0
        self.endpoint = _FakeRawParseEndpoint(parsed)
        self.responses = SimpleNamespace(
            with_raw_response=SimpleNamespace(parse=self.endpoint.parse)
        )


@contextmanager
def _network_denied() -> Iterator[dict[str, int]]:
    counts = {"network_calls": 0}

    def denied(*_args: Any, **_kwargs: Any) -> None:
        counts["network_calls"] += 1
        raise AssertionError("network forbidden during v0.6.3 live preflight")

    with (
        mock.patch.object(socket, "create_connection", side_effect=denied),
        mock.patch.object(socket.socket, "connect", side_effect=denied),
        mock.patch.object(socket.socket, "connect_ex", side_effect=denied),
    ):
        yield counts


def _materialize_projection() -> dict[str, Any]:
    fixture = core._strict_load(core.FIXTURE_PATH)
    core.validate_fixture(fixture)
    cases = core._case_map(fixture)
    with _network_denied() as counts:
        rebuilt = core.build_projection(fixture)
    if counts["network_calls"] != 0:
        raise ActuatorLiveExecutionError("projection attempted network access")
    committed = _strict_load(COMMITTED_PROJECTION_PATH)
    if _canonical_bytes(rebuilt) != _canonical_bytes(committed):
        raise ActuatorLiveExecutionError(
            "rebuilt projection differs from committed bytes"
        )

    schedule = _projection_schedule(committed)
    payload_rows = committed.get("provider_payloads")
    if not isinstance(payload_rows, list) or len(payload_rows) != 16:
        raise ActuatorLiveExecutionError("projection payload table is not 16 rows")
    payload_by_blind = {
        row["blinded_request_id"]: row for row in payload_rows if isinstance(row, dict)
    }
    if len(payload_by_blind) != 16:
        raise ActuatorLiveExecutionError("projection blinded payload set drifted")

    attempts: list[dict[str, Any]] = []
    for row in schedule:
        blind_id = row["blinded_request_id"]
        wrapper = payload_by_blind.get(blind_id)
        if wrapper is None:
            raise ActuatorLiveExecutionError("scheduled payload is missing")
        payload = _clone(wrapper["payload"])
        if wrapper.get("provider_payload_sha256") != fingerprint(payload) or row.get(
            "provider_payload_sha256"
        ) != fingerprint(payload):
            raise ActuatorLiveExecutionError("scheduled payload fingerprint drifted")
        case = cases.get(row["case_id"])
        if case is None:
            raise ActuatorLiveExecutionError("scheduled case is unknown")
        core.validate_provider_payload(payload, case=case)
        attempts.append({**_clone(row), "payload": payload})
    return {
        "projection": committed,
        "fixture": fixture,
        "cases": cases,
        "attempts": attempts,
    }


def _valid_conformance_output(material: Mapping[str, Any]) -> dict[str, Any]:
    attempt = material["attempts"][0]
    case = material["cases"][attempt["case_id"]]
    return core._conformance_output(
        path_id="P0",
        case=case,
        payload=attempt["payload"],
    )


def _provider_transport_self_test(material: Mapping[str, Any]) -> dict[str, Any]:
    output = _valid_conformance_output(material)
    parsed = core.ActuatorCalibrationOutput.model_validate(output)
    fake = _FakeOpenAIClient(parsed)
    payload = material["attempts"][0]["payload"]
    with _network_denied() as counts:
        provider = OpenAIActuatorProviderLiveR01(client=fake)  # type: ignore[arg-type]
        public_output, receipt = provider.generate(payload)
    receipt_value = receipt.to_dict()
    call = fake.endpoint.calls[0] if len(fake.endpoint.calls) == 1 else {}
    other_status_receipt = _clone(receipt_value)
    other_status_receipt["metadata"].update(
        {
            "status": "other",
            "attempt_outcome": "contract_error",
            "failure_phase": "provider_contract",
            "failure_reason_code": "provider_status_non_completed",
            "failure_type": "provider_status_non_completed",
        }
    )
    other_status_failure = {
        "category": "provider_boundary_error",
        "exception_class": "OpenAIProviderBoundaryError",
        "phase": "provider_contract",
        "reason_code": "provider_status_non_completed",
    }
    _validate_receipt(
        other_status_receipt,
        payload,
        provider_completed=False,
        failure=other_status_failure,
    )
    checks = {
        "one_fake_transport_call": len(fake.endpoint.calls) == 1,
        "exact_public_output_roundtrip": public_output == output,
        "one_sanitized_receipt": provider.audit_receipts == [receipt_value],
        "request_payload_bound": receipt_value["request_fingerprint"]
        == fingerprint(payload),
        "instructions_bound": receipt_value["prompt_fingerprint"]
        == INSTRUCTIONS_FINGERPRINT,
        "sanitized_other_status_accepted": True,
        "runtime_arguments_pinned": (
            call.get("model") == core.MODEL
            and call.get("instructions") == ACTUATOR_INSTRUCTIONS
            and call.get("input") == canonical_json(payload)
            and call.get("reasoning") == {"effort": core.REASONING_EFFORT}
            and call.get("max_output_tokens") == core.MAX_OUTPUT_TOKENS
            and call.get("store") is False
            and call.get("service_tier") == "default"
            and call.get("truncation") == "disabled"
            and call.get("timeout") == float(core.TIMEOUT_SECONDS)
            and call.get("text_format") is core.ActuatorCalibrationOutput
            and set(call.get("extra_headers", {})) == {"X-Client-Request-Id"}
        ),
        "network_calls_zero": counts["network_calls"] == 0,
    }
    if not all(checks.values()):
        raise ActuatorLiveExecutionError("offline provider transport self-test failed")
    return _seal(
        {
            "schema_version": "ebrt-actuator-provider-self-test-v0.6.3-r01",
            "status": "PASS",
            "checks": checks,
            "provider_calls": 0,
            "simulated_api_calls": 1,
            "network_calls": 0,
        }
    )


def _offline_full_block_self_test(material: Mapping[str, Any]) -> dict[str, Any]:
    """Exercise all journal/compiler/effect plumbing with fake transport only."""

    controllers = {
        row["case_id"]: row for row in material["projection"]["controller_audits"]
    }
    outputs: dict[str, dict[str, Any]] = {}
    compiled_outputs: dict[str, dict[str, Any]] = {}
    attempts: list[dict[str, Any]] = []
    for row in material["attempts"]:
        arm = row["treatment_id"]
        controller = controllers[row["case_id"]]
        if arm == "X":
            path_id = controller["q_x_selected_path"]
        elif arm == "Z":
            path_id = "P1" if controller["q_x_selected_path"] == "P0" else "P0"
        elif arm == "D":
            path_id = controller["q_d_preferred_path"]
        else:
            path_id = "P1" if controller["q_d_preferred_path"] == "P0" else "P0"
        output = core._conformance_output(
            path_id=path_id,
            case=material["cases"][row["case_id"]],
            payload=row["payload"],
        )
        fake = _FakeOpenAIClient(core.ActuatorCalibrationOutput.model_validate(output))
        provider = OpenAIActuatorProviderLiveR01(client=fake)  # type: ignore[arg-type]
        public_output, receipt = provider.generate(row["payload"])
        receipt_value = receipt.to_dict()
        _validate_live_receipt(
            provider,
            receipt_value,
            row["payload"],
            provider_completed=True,
            failure=None,
        )
        compiled = core.compile_output(
            public_output,
            payload=row["payload"],
            case=material["cases"][row["case_id"]],
        )
        blind_id = row["blinded_request_id"]
        outputs[blind_id] = public_output
        compiled_outputs[blind_id] = compiled
        attempts.append(
            {
                **{key: _clone(row[key]) for key in row if key != "payload"},
                "provider_input_fingerprint_sha256": fingerprint(row["payload"]),
                "provider_output_fingerprint_sha256": fingerprint(public_output),
                "compiled_output_fingerprint_sha256": compiled["fingerprint_sha256"],
                "receipt": receipt_value,
                "failure": None,
                "status": "COMPLETED",
            }
        )
    execution = {
        "attempts": attempts,
        "provider_outputs": outputs,
        "compiled_outputs": compiled_outputs,
        "run_status": "COMPLETE",
        "unattempted_blinded_request_ids": [],
    }
    _validate_execution(execution, material)
    expected_journal = _journal_bytes(execution)
    with tempfile.TemporaryDirectory(
        prefix="ebrt-v063-live-journal-test-"
    ) as directory:
        journal_path = Path(directory) / "attempt_journal.jsonl"
        journal_path.touch(mode=0o600)
        for attempt in attempts:
            _append_journal(journal_path, _started_journal_row(attempt))
            _append_journal(
                journal_path,
                _terminal_journal_row(
                    attempt,
                    provider_output=outputs[attempt["blinded_request_id"]],
                    compiled_output=compiled_outputs[attempt["blinded_request_id"]],
                ),
            )
        observed_journal = journal_path.read_bytes()
    endpoints = _effect_endpoints(execution, material)
    checks = {
        "sixteen_fake_transport_calls": len(attempts) == 16,
        "all_fake_outputs_compile": len(compiled_outputs) == 16,
        "journal_exact_reconstruction": observed_journal == expected_journal,
        "sixteen_started_markers": expected_journal.count(b"ATTEMPT_STARTED") == 16,
        "sixteen_terminal_markers": expected_journal.count(b"ATTEMPT_TERMINAL") == 16,
        "x_endpoint_plumbing_positive": endpoints["positive_control"]["status"]
        == "POSITIVE",
        "d_c_endpoint_plumbing_positive": endpoints["gradient_placement"]["status"]
        == "POSITIVE",
        "all_schedule_receipts_adherent": endpoints["channel_adherence"]["status"]
        == "PASS"
        and endpoints["d_c_adherence"]["status"] == "PASS",
    }
    if not all(checks.values()):
        raise ActuatorLiveExecutionError("offline full-block self-test failed")
    return _seal(
        {
            "schema_version": "ebrt-actuator-live-offline-block-test-v0.6.3-r01",
            "status": "PASS",
            "checks": checks,
            "provider_calls": 0,
            "simulated_api_calls": 16,
            "network_calls": 0,
            "claim_boundary": [
                "The conformance outputs exercise journal and endpoint plumbing only.",
                "No fake arm delta is a hosted result or evidence of provider uptake.",
            ],
        }
    )


def component_self_test() -> dict[str, Any]:
    with _network_denied() as counts, _semantic_gold_denied() as gold_counts:
        material = _materialize_projection()
        committed_manifest = _strict_load(COMMITTED_PREFLIGHT_MANIFEST_PATH)
        transport = _provider_transport_self_test(material)
        offline_block = _offline_full_block_self_test(material)
    committed_hard_gates = committed_manifest.get("hard_gates", {})
    checks = {
        "committed_core_manifest_exact": (
            _sha256_path(COMMITTED_PREFLIGHT_MANIFEST_PATH)
            == PRELIGHT_MANIFEST_BYTES_SHA256
            and committed_manifest.get("status") == "READY_ZERO_CALL_PREFLIGHT_ONLY"
            and committed_manifest.get("live_execution_authorized") is False
            and committed_manifest.get("provider_calls") == 0
            and committed_manifest.get("network_calls") == 0
        ),
        "committed_core_hard_gates_pass": (
            set(committed_hard_gates) == set(core.HARD_GATE_IDS)
            and all(committed_hard_gates.values())
        ),
        "projection_exact": material["projection"]["fingerprint_sha256"]
        == "c817e45c27f6b4a94696a8519fe6b0130c5f66e97966413914fda42d57eb1588",
        "sixteen_attempts_presealed": len(material["attempts"]) == 16,
        "provider_transport_pass": transport["status"] == "PASS",
        "offline_full_block_pass": offline_block["status"] == "PASS",
        "network_calls_zero": counts["network_calls"] == 0,
        "semantic_gold_path_read_attempts_zero": gold_counts["attempted_gold_accesses"]
        == 0,
        "sdk_versions_pinned": (
            importlib.metadata.version("openai") == EXPECTED_OPENAI_SDK_VERSION
            and importlib.metadata.version("pydantic") == EXPECTED_PYDANTIC_VERSION
        ),
    }
    if not all(checks.values()):
        raise ActuatorLiveExecutionError("component self-test failed")
    return _seal(
        {
            "schema_version": "ebrt-actuator-live-component-self-test-v0.6.3-r01",
            "status": "PASS_NETWORK_ZERO",
            "checks": checks,
            "provider_calls": 0,
            "network_calls": 0,
            "simulated_api_calls": 17,
        }
    )


def _expected_provider_provenance() -> dict[str, Any]:
    return {
        **_runtime_contract(),
        "instructions_fingerprint_sha256": INSTRUCTIONS_FINGERPRINT,
        "response_schema_fingerprint_sha256": RESPONSE_SCHEMA_FINGERPRINT,
        "receipt_schema_version": RECEIPT_SCHEMA_VERSION,
    }


def _build_preflight_record(
    *,
    lock: Mapping[str, Any],
    material: Mapping[str, Any],
    source_snapshot: Mapping[str, str],
    require_api_key: bool,
    execution_authorization: Mapping[str, Any],
) -> dict[str, Any]:
    component = component_self_test()
    if component.get("status") != "PASS_NETWORK_ZERO":
        raise ActuatorLiveExecutionError("component self-test did not pass")

    manifest = _strict_load(COMMITTED_PREFLIGHT_MANIFEST_PATH)
    projection = material["projection"]
    if (
        _sha256_path(COMMITTED_PREFLIGHT_MANIFEST_PATH)
        != PRELIGHT_MANIFEST_BYTES_SHA256
        or manifest.get("fingerprint_sha256")
        != lock["preflight_manifest_fingerprint_sha256"]
        or manifest.get("projection_fingerprint_sha256")
        != projection["fingerprint_sha256"]
        or manifest.get("status") != "READY_ZERO_CALL_PREFLIGHT_ONLY"
        or manifest.get("live_execution_authorized") is not False
        or manifest.get("provider_calls") != 0
        or manifest.get("network_calls") != 0
        or set(manifest.get("hard_gates", {})) != set(core.HARD_GATE_IDS)
        or not all(manifest.get("hard_gates", {}).values())
    ):
        raise ActuatorLiveExecutionError("committed zero-call manifest drifted")

    expected_provenance = _expected_provider_provenance()
    if require_api_key and not os.environ.get("OPENAI_API_KEY"):
        raise ActuatorLiveExecutionError("OPENAI_API_KEY is unavailable")
    if require_api_key:
        # Every sealed payload exists before any provider object is constructed.
        providers = [OpenAIActuatorProviderLiveR01() for _ in material["attempts"]]
        provenances = [provider.provenance for provider in providers]
        if (
            len(provenances) != 16
            or len({_canonical_bytes(value) for value in provenances}) != 1
            or provenances[0] != expected_provenance
            or any(provider.audit_receipts for provider in providers)
        ):
            raise ActuatorLiveExecutionError("provider runtime differs across attempts")

    if (
        lock["runtime"] != _runtime_contract()
        or lock["instructions_fingerprint_sha256"] != INSTRUCTIONS_FINGERPRINT
        or lock["response_schema_fingerprint_sha256"] != RESPONSE_SCHEMA_FINGERPRINT
        or lock["execution"]["provider_calls_authorized"] != 16
    ):
        raise ActuatorLiveExecutionError("live runtime differs from policy lock")

    return _seal(
        {
            "schema_version": "ebrt-actuator-live-preflight-v0.6.3-r01",
            "status": (
                "READY_EXACT_16_CALL_LIVE_BLOCK"
                if execution_authorization.get("status") == "AUTHORIZED_ANNOTATED_TAG"
                and execution_authorization.get("head_matches_authorized_commit")
                is True
                else "READY_CONTRACT_ONLY_AWAITING_EXECUTION_TAG"
            ),
            "expected_api_attempts": 16,
            "call_order_blinded_request_ids": [
                row["blinded_request_id"] for row in material["attempts"]
            ],
            "payload_fingerprints": {
                row["blinded_request_id"]: fingerprint(row["payload"])
                for row in material["attempts"]
            },
            "projection_fingerprint_sha256": material["projection"][
                "fingerprint_sha256"
            ],
            "policy_lock_fingerprint_sha256": lock["fingerprint_sha256"],
            "preflight_anchor_tag_object": PRELIGHT_ANCHOR_TAG_OBJECT,
            "preflight_anchor_commit": PRELIGHT_ANCHOR_COMMIT,
            "preflight_manifest_bytes_sha256": PRELIGHT_MANIFEST_BYTES_SHA256,
            "provider": expected_provenance,
            "component_self_test": component,
            "execution_authorization": _clone(execution_authorization),
            "source_snapshot_sha256": dict(source_snapshot),
            "post_call_gold_expected_receipt": _clone(
                lock["sources"]["post_call_gold"]
            ),
            "gold_loaded": False,
            "guarded_gold_path_read_attempts": 0,
            "gold_guard_scope": "LOCKED_PATH_READ_BYTES_NOT_OS_SANDBOX",
            "provider_calls": 0,
            "network_calls": 0,
        }
    )


def _preflight_materialize(
    *, require_api_key: bool = True, require_authorization: bool = False
) -> dict[str, Any]:
    output = DEFAULT_OUTPUT
    if output.is_symlink() or output.parent.is_symlink():
        raise ActuatorLiveExecutionError("live namespace contains a symlink")
    if output.exists():
        raise ActuatorLiveExecutionError(f"output already exists: {output}")
    if _staging_directory(output).exists():
        raise ActuatorLiveExecutionError(
            f"unresolved prior attempt journal exists: {_staging_directory(output)}"
        )
    with _semantic_gold_denied() as gold_counts:
        lock = _load_lock()
        source_before = _source_snapshot(lock)
        material = _materialize_projection()
        authorization = _observe_execution_authorization(
            allow_pending=not require_authorization
        )
        if require_authorization and (
            authorization.get("status") != "AUTHORIZED_ANNOTATED_TAG"
            or authorization.get("head_matches_authorized_commit") is not True
        ):
            raise ActuatorLiveExecutionError(
                "live execution HEAD is not the authorized tagged commit"
            )
        preflight_value = _build_preflight_record(
            lock=lock,
            material=material,
            source_snapshot=source_before,
            require_api_key=require_api_key,
            execution_authorization=authorization,
        )
        source_after = _source_snapshot(lock)
    if gold_counts["attempted_gold_accesses"] != 0:
        raise ActuatorLiveExecutionError("semantic gold access occurred in preflight")
    if source_after != source_before:
        raise ActuatorLiveExecutionError("locked sources changed during preflight")
    return {
        **material,
        "lock": lock,
        "preflight": preflight_value,
        "source_snapshot": source_before,
    }


def preflight() -> dict[str, Any]:
    return _clone(_preflight_materialize()["preflight"])


def _failure_record(error: Exception) -> dict[str, Any]:
    if isinstance(error, OpenAIProviderBoundaryError):
        return {
            "category": error.category,
            "exception_class": type(error).__name__,
            "phase": error.phase,
            "reason_code": error.reason_code,
        }
    reason_code = getattr(error, "reason_code", None)
    return {
        "category": "local_output_contract_error",
        "exception_class": type(error).__name__,
        "phase": "local_output_contract",
        "reason_code": (
            reason_code
            if isinstance(reason_code, str) and reason_code
            else "local_output_contract_unclassified"
        ),
    }


def _receipt_from_error(error: Exception) -> dict[str, Any] | None:
    receipt = getattr(error, "receipt", None)
    return None if receipt is None else receipt.to_dict()


def _validate_receipt(
    receipt: Mapping[str, Any],
    payload: Mapping[str, Any],
    *,
    provider_completed: bool,
    failure: Mapping[str, Any] | None,
) -> None:
    required = {
        "provider",
        "requested_model",
        "returned_model",
        "logical_calls",
        "api_calls",
        "latency_ms",
        "request_fingerprint",
        "prompt_fingerprint",
        "usage",
        "metadata",
    }
    if set(receipt) != required:
        raise ActuatorLiveExecutionError("provider receipt schema drifted")
    if (
        receipt["provider"] != "openai_responses"
        or receipt["requested_model"] != core.MODEL
        or type(receipt["logical_calls"]) is not int
        or receipt["logical_calls"] != 1
        or type(receipt["api_calls"]) is not int
        or receipt["api_calls"] != 1
        or receipt["request_fingerprint"] != fingerprint(payload)
        or receipt["prompt_fingerprint"] != INSTRUCTIONS_FINGERPRINT
        or not isinstance(receipt["latency_ms"], (int, float))
        or isinstance(receipt["latency_ms"], bool)
        or not math.isfinite(float(receipt["latency_ms"]))
        or float(receipt["latency_ms"]) < 0.0
    ):
        raise ActuatorLiveExecutionError("provider receipt binding drifted")

    metadata = receipt["metadata"]
    metadata_keys = {
        "receipt_schema_version",
        "status",
        "service_tier",
        "response_id_sha256",
        "server_request_id_sha256",
        "client_request_id_sha256",
        "provider_body_sha256",
        "provider_body_byte_count",
        "http_observed",
        "http_status_code",
        "parse_boundary",
        "failure_phase",
        "failure_reason_code",
        "failure_type",
        "response_schema_fingerprint",
        "semantic_protocol_fingerprint",
        "reasoning_effort",
        "max_output_tokens",
        "store",
        "previous_response_id",
        "truncation",
        "sdk_version",
        "pydantic_version",
        "python_version",
        "attempt",
        "retry_count",
        "api_call_count_semantics",
        "attempt_outcome",
        "refusal_count",
    }
    expected_semantic_protocol = fingerprint(
        {
            "model": core.MODEL,
            "instructions_fingerprint": INSTRUCTIONS_FINGERPRINT,
            "input_fingerprint": fingerprint(payload),
            "text_schema_fingerprint": RESPONSE_SCHEMA_FINGERPRINT,
            "reasoning": {"effort": core.REASONING_EFFORT},
            "max_output_tokens": core.MAX_OUTPUT_TOKENS,
            "store": False,
            "service_tier": "default",
            "truncation": "disabled",
            "timeout_seconds": float(core.TIMEOUT_SECONDS),
        }
    )
    if (
        not isinstance(metadata, Mapping)
        or set(metadata) != metadata_keys
        or metadata.get("receipt_schema_version") != RECEIPT_SCHEMA_VERSION
        or type(metadata.get("attempt")) is not int
        or metadata.get("attempt") != 1
        or type(metadata.get("retry_count")) is not int
        or metadata.get("retry_count") != 0
        or metadata.get("reasoning_effort") != core.REASONING_EFFORT
        or metadata.get("max_output_tokens") != core.MAX_OUTPUT_TOKENS
        or metadata.get("store") is not False
        or metadata.get("previous_response_id") is not False
        or metadata.get("truncation") != "disabled"
        or metadata.get("sdk_version") != importlib.metadata.version("openai")
        or metadata.get("pydantic_version") != importlib.metadata.version("pydantic")
        or metadata.get("python_version") != sys.version.split()[0]
        or metadata.get("api_call_count_semantics") != "attempted_client_call"
        or metadata.get("response_schema_fingerprint") != RESPONSE_SCHEMA_FINGERPRINT
        or metadata.get("semantic_protocol_fingerprint") != expected_semantic_protocol
        or not _is_sha256(metadata.get("client_request_id_sha256"))
    ):
        raise ActuatorLiveExecutionError("provider receipt runtime drifted")

    usage = receipt["usage"]
    usage_keys = {
        "exact_provider_tokens",
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "cached_input_tokens",
        "cache_write_tokens",
        "reasoning_tokens",
    }
    if not isinstance(usage, Mapping) or set(usage) != usage_keys:
        raise ActuatorLiveExecutionError("provider usage missing")
    if provider_completed:
        if (
            receipt["returned_model"] != core.MODEL
            or usage.get("exact_provider_tokens") is not True
            or metadata.get("status") != "completed"
            or metadata.get("attempt_outcome") != "completed"
            or metadata.get("service_tier") != "default"
            or metadata.get("http_observed") is not True
            or metadata.get("http_status_code") != 200
            or metadata.get("parse_boundary") != "succeeded"
            or not _is_sha256(metadata.get("response_id_sha256"))
            or not _is_sha256(metadata.get("server_request_id_sha256"))
            or not _is_sha256(metadata.get("provider_body_sha256"))
            or not isinstance(metadata.get("provider_body_byte_count"), int)
            or metadata.get("provider_body_byte_count", 0) <= 0
            or metadata.get("failure_phase") is not None
            or metadata.get("failure_reason_code") is not None
            or metadata.get("failure_type") is not None
            or metadata.get("refusal_count") != 0
        ):
            raise ActuatorLiveExecutionError("completed receipt contract drifted")
    else:
        if not isinstance(failure, Mapping) or set(failure) != {
            "category",
            "exception_class",
            "phase",
            "reason_code",
        }:
            raise ActuatorLiveExecutionError("provider failure record drifted")
        phase = failure["phase"]
        reason = failure["reason_code"]
        if (
            failure["category"] != "provider_boundary_error"
            or failure["exception_class"] != "OpenAIProviderBoundaryError"
            or phase not in BOUNDARY_REASON_CODES_BY_PHASE
            or reason not in BOUNDARY_REASON_CODES_BY_PHASE[phase]
            or metadata.get("failure_phase") != phase
            or metadata.get("failure_reason_code") != reason
            or metadata.get("failure_type") != reason
            or metadata.get("attempt_outcome") == "completed"
        ):
            raise ActuatorLiveExecutionError("provider failure/receipt mismatch")
        expected_failure_statuses = {
            "request_call": {"no_http_response"},
            "http_status": {"http_status_error"},
            "sdk_response_parse": {"http_success_unparsed", "sdk_parse_error"},
            "provider_contract": {
                "completed",
                "incomplete",
                "failed",
                "cancelled",
                "queued",
                "in_progress",
                "other",
                "provider_contract_error",
            },
        }
        if metadata.get("status") not in expected_failure_statuses[phase]:
            raise ActuatorLiveExecutionError("provider failure status drifted")
    for key, value in usage.items():
        if key == "exact_provider_tokens":
            continue
        if value is not None and (
            not isinstance(value, int) or isinstance(value, bool) or value < 0
        ):
            raise ActuatorLiveExecutionError("provider usage value drifted")
    token_keys = usage_keys - {"exact_provider_tokens"}
    if usage["exact_provider_tokens"] is True:
        if any(type(usage[key]) is not int for key in token_keys):
            raise ActuatorLiveExecutionError("exact provider usage is incomplete")
        if usage["total_tokens"] != usage["input_tokens"] + usage["output_tokens"]:
            raise ActuatorLiveExecutionError("exact provider usage total drifted")
        if (
            usage["cached_input_tokens"] > usage["input_tokens"]
            or usage["reasoning_tokens"] > usage["output_tokens"]
        ):
            raise ActuatorLiveExecutionError("exact provider usage detail drifted")
    elif usage["exact_provider_tokens"] is False:
        if any(usage[key] is not None for key in token_keys):
            raise ActuatorLiveExecutionError("inexact provider usage retained tokens")
    else:
        raise ActuatorLiveExecutionError("provider usage exactness flag drifted")


def _validate_live_receipt(
    provider: OpenAIActuatorProviderLiveR01,
    receipt: Mapping[str, Any],
    payload: Mapping[str, Any],
    *,
    provider_completed: bool,
    failure: Mapping[str, Any] | None,
) -> None:
    if provider.audit_receipts != [_clone(receipt)]:
        raise ActuatorLiveExecutionError("provider audit receipt differs from return")
    _validate_receipt(
        receipt,
        payload,
        provider_completed=provider_completed,
        failure=failure,
    )


def _append_journal(path: Path, row: Mapping[str, Any]) -> None:
    raw = _canonical_bytes(row, trailing_newline=True)
    with path.open("ab") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def _started_journal_row(row: Mapping[str, Any]) -> dict[str, Any]:
    payload_fingerprint = row.get("provider_input_fingerprint_sha256")
    if payload_fingerprint is None:
        payload_fingerprint = fingerprint(row["payload"])
    return {
        "schema_version": JOURNAL_SCHEMA,
        "event": "ATTEMPT_STARTED",
        "run_position": row["run_position"],
        "block_id": row["block_id"],
        "block_position": row["block_position"],
        "blinded_request_id": row["blinded_request_id"],
        "provider_input_fingerprint_sha256": payload_fingerprint,
    }


def _terminal_journal_row(
    attempt: Mapping[str, Any],
    *,
    provider_output: Mapping[str, Any] | None,
    compiled_output: Mapping[str, Any] | None,
) -> dict[str, Any]:
    return {
        "schema_version": JOURNAL_SCHEMA,
        "event": "ATTEMPT_TERMINAL",
        "attempt": _clone(attempt),
        "provider_output": _clone(provider_output),
        "compiled_output": _clone(compiled_output),
    }


def _journal_bytes(execution: Mapping[str, Any]) -> bytes:
    rows: list[dict[str, Any]] = []
    outputs = execution["provider_outputs"]
    compiled = execution["compiled_outputs"]
    for attempt in execution["attempts"]:
        rows.append(_started_journal_row(attempt))
        rows.append(
            _terminal_journal_row(
                attempt,
                provider_output=outputs.get(attempt["blinded_request_id"]),
                compiled_output=compiled.get(attempt["blinded_request_id"]),
            )
        )
    return b"".join(_canonical_bytes(row, trailing_newline=True) for row in rows)


def _freeze_receipt_guard_failure(
    journal_path: Path,
    *,
    row: Mapping[str, Any],
    receipt: Mapping[str, Any],
) -> None:
    _append_journal(
        journal_path,
        {
            "schema_version": JOURNAL_SCHEMA,
            "event": "IRRECOVERABLE_RECEIPT_GUARD_FAILURE",
            "run_position": row["run_position"],
            "block_id": row["block_id"],
            "block_position": row["block_position"],
            "blinded_request_id": row["blinded_request_id"],
            "provider_input_fingerprint_sha256": fingerprint(row["payload"]),
            "receipt": _clone(receipt),
            "failure": {
                "category": "local_receipt_guard_error",
                "phase": "immediate_post_call_receipt_guard",
                "reason_code": "live_receipt_or_audit_mismatch",
            },
        },
    )


def _execute_gold_free(
    material: Mapping[str, Any], *, journal_path: Path
) -> dict[str, Any]:
    rows = material["attempts"]
    cases = material["cases"]
    # Construction happens after all sixteen payloads have been sealed and the
    # durable plan/journal exist. Each instance can make exactly one call.
    providers = {
        row["blinded_request_id"]: OpenAIActuatorProviderLiveR01() for row in rows
    }
    attempts: list[dict[str, Any]] = []
    provider_outputs: dict[str, dict[str, Any]] = {}
    compiled_outputs: dict[str, dict[str, Any]] = {}

    for row in rows:
        blind_id = row["blinded_request_id"]
        payload = row["payload"]
        provider = providers[blind_id]

        # The start marker is durable before crossing the irreversible boundary.
        # A process crash therefore burns this namespace and cannot be resumed.
        _append_journal(journal_path, _started_journal_row(row))
        try:
            public_output, receipt = provider.generate(payload)
        except OpenAIProviderBoundaryError as error:
            receipt_value = _receipt_from_error(error)
            if receipt_value is None:
                raise ActuatorLiveExecutionError(
                    "provider boundary failure omitted its receipt"
                ) from None
            failure = _failure_record(error)
            try:
                _validate_live_receipt(
                    provider,
                    receipt_value,
                    payload,
                    provider_completed=False,
                    failure=failure,
                )
            except Exception:
                _freeze_receipt_guard_failure(
                    journal_path, row=row, receipt=receipt_value
                )
                raise ActuatorLiveExecutionError(
                    "live receipt guard failed; in-flight namespace frozen"
                ) from None
            attempt = {
                **{key: _clone(row[key]) for key in row if key != "payload"},
                "provider_input_fingerprint_sha256": fingerprint(payload),
                "receipt": receipt_value,
                "failure": failure,
                "status": "PROVIDER_BOUNDARY_ERROR",
            }
            attempts.append(attempt)
            _append_journal(
                journal_path,
                _terminal_journal_row(
                    attempt, provider_output=None, compiled_output=None
                ),
            )
            break

        receipt_value = receipt.to_dict()
        try:
            _validate_live_receipt(
                provider,
                receipt_value,
                payload,
                provider_completed=True,
                failure=None,
            )
        except Exception:
            _freeze_receipt_guard_failure(journal_path, row=row, receipt=receipt_value)
            raise ActuatorLiveExecutionError(
                "live receipt guard failed; in-flight namespace frozen"
            ) from None

        public_output_value = _clone(public_output)
        provider_outputs[blind_id] = public_output_value
        try:
            compiled = core.compile_output(
                public_output_value,
                payload=payload,
                case=cases[row["case_id"]],
            )
        except Exception as error:
            failure = _failure_record(error)
            attempt = {
                **{key: _clone(row[key]) for key in row if key != "payload"},
                "provider_input_fingerprint_sha256": fingerprint(payload),
                "provider_output_fingerprint_sha256": fingerprint(public_output_value),
                "receipt": receipt_value,
                "failure": failure,
                "status": "LOCAL_OUTPUT_CONTRACT_ERROR",
            }
            attempts.append(attempt)
            _append_journal(
                journal_path,
                _terminal_journal_row(
                    attempt,
                    provider_output=public_output_value,
                    compiled_output=None,
                ),
            )
            break

        compiled_value = _clone(compiled)
        compiled_outputs[blind_id] = compiled_value
        attempt = {
            **{key: _clone(row[key]) for key in row if key != "payload"},
            "provider_input_fingerprint_sha256": fingerprint(payload),
            "provider_output_fingerprint_sha256": fingerprint(public_output_value),
            "compiled_output_fingerprint_sha256": compiled_value["fingerprint_sha256"],
            "receipt": receipt_value,
            "failure": None,
            "status": "COMPLETED",
        }
        attempts.append(attempt)
        _append_journal(
            journal_path,
            _terminal_journal_row(
                attempt,
                provider_output=public_output_value,
                compiled_output=compiled_value,
            ),
        )

    complete = (
        len(attempts) == 16
        and all(row["status"] == "COMPLETED" for row in attempts)
        and [row["run_position"] for row in attempts] == list(range(1, 17))
    )
    return {
        "attempts": attempts,
        "provider_outputs": provider_outputs,
        "compiled_outputs": compiled_outputs,
        "run_status": "COMPLETE" if complete else "INCOMPLETE",
        "unattempted_blinded_request_ids": [
            row["blinded_request_id"] for row in rows[len(attempts) :]
        ],
    }


def _usage_summary(attempts: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    fields = (
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "cached_input_tokens",
        "cache_write_tokens",
        "reasoning_tokens",
    )
    totals = {field: 0 for field in fields}
    exact = True
    latency_ms = 0.0
    logical_calls = 0
    api_calls = 0
    for attempt in attempts:
        receipt = attempt["receipt"]
        usage = receipt["usage"]
        exact = exact and usage.get("exact_provider_tokens") is True
        for field in fields:
            value = usage.get(field)
            if value is None:
                exact = False
            else:
                totals[field] += int(value)
        latency_ms += float(receipt["latency_ms"])
        logical_calls += int(receipt["logical_calls"])
        api_calls += int(receipt["api_calls"])
    return {
        "logical_calls": logical_calls,
        "api_calls": api_calls,
        "latency_ms": latency_ms,
        "exact_provider_tokens": exact,
        **totals,
    }


def _downstream_signature(
    output: Mapping[str, Any], compiled: Mapping[str, Any]
) -> str:
    """Fingerprint typed downstream state while excluding the schedule receipt."""

    return fingerprint(
        {
            "current_answer": output["current_answer"],
            "decision_slots": output["decision_slots"],
            "selected_candidate_edge_ids": output["selected_candidate_edge_ids"],
            "selected_path_id": compiled["selected_path_id"],
            "active_necessary_support_closure": compiled[
                "active_necessary_support_closure"
            ],
            "invalidated_evidence_ids": compiled["invalidated_evidence_ids"],
            "stable_support_evidence_ids": compiled["stable_support_evidence_ids"],
        }
    )


def _effect_endpoints(
    execution: Mapping[str, Any], material: Mapping[str, Any]
) -> dict[str, Any]:
    rows = material["attempts"]
    output_by_blind = execution["provider_outputs"]
    compiled_by_blind = execution["compiled_outputs"]
    controllers = {
        row["case_id"]: row for row in material["projection"]["controller_audits"]
    }
    by_block: dict[str, dict[str, Mapping[str, Any]]] = {}
    for row in rows:
        by_block.setdefault(row["block_id"], {})[row["treatment_id"]] = row

    block_rows: list[dict[str, Any]] = []
    for block_id, case_id, trial_id, _order in core.WILLIAMS_BLOCKS:
        arms = by_block[block_id]
        controller = controllers[case_id]

        def compiled(arm: str) -> Mapping[str, Any]:
            return compiled_by_blind[arms[arm]["blinded_request_id"]]

        def output(arm: str) -> Mapping[str, Any]:
            return output_by_blind[arms[arm]["blinded_request_id"]]

        x_alignment = core.alignment(compiled("X"), controller["q_x"])
        z_alignment = core.alignment(compiled("Z"), controller["q_x"])
        d_alignment = core.alignment(compiled("D"), controller["q_d"])
        c_alignment = core.alignment(compiled("C"), controller["q_d"])
        block_rows.append(
            {
                "block_id": block_id,
                "case_id": case_id,
                "trial_id": trial_id,
                "x_adherence": compiled("X")["inspection_plan"]["adherence"] is True,
                "z_adherence": compiled("Z")["inspection_plan"]["reviewed_evidence_ids"]
                == compiled("Z")["inspection_plan"]["expected_reviewed_evidence_ids"],
                "d_adherence": compiled("D")["inspection_plan"]["adherence"] is True,
                "c_adherence": compiled("C")["inspection_plan"]["adherence"] is True,
                "alignment_x_q_x": x_alignment,
                "alignment_z_q_x": z_alignment,
                "delta_xz": x_alignment - z_alignment,
                "alignment_d_q_d": d_alignment,
                "alignment_c_q_d": c_alignment,
                "delta_dc": d_alignment - c_alignment,
                "downstream_signature_by_arm": {
                    arm: _downstream_signature(output(arm), compiled(arm))
                    for arm in core.ARMS
                },
            }
        )

    x_deltas = [float(row["delta_xz"]) for row in block_rows]
    dc_deltas = [float(row["delta_dc"]) for row in block_rows]
    x_aggregate = math.fsum(x_deltas)
    dc_aggregate = math.fsum(dc_deltas)
    x_positive = [
        row["block_id"] for row in block_rows if row["delta_xz"] > EFFECT_EPSILON
    ]
    dc_positive = [
        row["block_id"] for row in block_rows if row["delta_dc"] > EFFECT_EPSILON
    ]
    x_z_adherence_pass = all(
        row["x_adherence"] and row["z_adherence"] for row in block_rows
    )
    dc_adherence_pass = all(
        row["d_adherence"] and row["c_adherence"] for row in block_rows
    )
    x_propagation_pass = (
        x_z_adherence_pass and x_aggregate > EFFECT_EPSILON and len(x_positive) >= 3
    )
    dc_placement_pass = (
        dc_adherence_pass and dc_aggregate > EFFECT_EPSILON and len(dc_positive) >= 3
    )
    return {
        "effect_epsilon": EFFECT_EPSILON,
        "blocks": block_rows,
        "channel_adherence": {
            "status": "PASS" if x_z_adherence_pass else "FAIL",
            "x_adherent_blocks": [
                row["block_id"] for row in block_rows if row["x_adherence"]
            ],
            "z_adherent_blocks": [
                row["block_id"] for row in block_rows if row["z_adherence"]
            ],
            "required_per_arm": 4,
        },
        "positive_control": {
            "status": "POSITIVE" if x_propagation_pass else "NULL",
            "aggregate_delta_xz": x_aggregate,
            "positive_blocks": x_positive,
            "required_positive_blocks": 3,
        },
        "d_c_adherence": {
            "status": "PASS" if dc_adherence_pass else "FAIL",
            "d_adherent_blocks": [
                row["block_id"] for row in block_rows if row["d_adherence"]
            ],
            "c_adherent_blocks": [
                row["block_id"] for row in block_rows if row["c_adherence"]
            ],
            "required_per_arm": 4,
        },
        "gradient_placement": {
            "status": "POSITIVE" if dc_placement_pass else "NULL",
            "aggregate_delta_dc": dc_aggregate,
            "positive_blocks": dc_positive,
            "required_positive_blocks": 3,
        },
    }


def _quality_grades(
    execution: Mapping[str, Any],
    material: Mapping[str, Any],
    lock: Mapping[str, Any],
) -> dict[str, Any]:
    # This is the first parse of semantic gold and occurs only after all sixteen
    # provider outputs have passed the public compiler.
    raw_gold = core.GOLD_PATH.read_bytes()
    observed_receipt = {
        "path": str(core.GOLD_PATH.relative_to(ROOT)),
        "bytes": len(raw_gold),
        "sha256": _sha256_bytes(raw_gold),
    }
    if observed_receipt != lock["sources"]["post_call_gold"]:
        raise ActuatorLiveExecutionError("post-call semantic gold bytes drifted")
    gold = core._gold_map(_load_json_bytes(raw_gold, "post-call semantic gold"))
    grades: dict[str, dict[str, Any]] = {}
    for row in material["attempts"]:
        blind_id = row["blinded_request_id"]
        grades[blind_id] = core.grade_quality(
            execution["provider_outputs"][blind_id],
            execution["compiled_outputs"][blind_id],
            gold[row["case_id"]],
        )
    passed = sum(grade["status"] == "PASS" for grade in grades.values())
    return {
        "status": "PASS" if passed == 16 else "FAIL",
        "secondary_only": True,
        "gold_loaded": True,
        "observed_gold_receipt": observed_receipt,
        "pass_count": passed,
        "attempt_count": 16,
        "by_blinded_request_id": grades,
    }


def _not_assessed_endpoints() -> dict[str, Any]:
    return {
        "effect_epsilon": EFFECT_EPSILON,
        "blocks": [],
        "channel_adherence": {"status": "NOT_ASSESSED"},
        "positive_control": {"status": "NOT_ASSESSED"},
        "d_c_adherence": {"status": "NOT_ASSESSED"},
        "gradient_placement": {"status": "NOT_ASSESSED"},
    }


def _finalize(
    execution: Mapping[str, Any],
    *,
    material: Mapping[str, Any],
    preflight_value: Mapping[str, Any],
    source_snapshot: Mapping[str, str],
    lock: Mapping[str, Any],
) -> dict[str, Any]:
    _validate_execution(execution, material)
    complete = execution["run_status"] == "COMPLETE"
    local_contract_failure = any(
        row["status"] == "LOCAL_OUTPUT_CONTRACT_ERROR" for row in execution["attempts"]
    )
    endpoints = (
        _effect_endpoints(execution, material)
        if complete
        else _not_assessed_endpoints()
    )
    quality = (
        _quality_grades(execution, material, lock)
        if complete
        else {
            "status": "NOT_ASSESSED",
            "secondary_only": True,
            "gold_loaded": False,
            "observed_gold_receipt": None,
            "pass_count": 0,
            "attempt_count": len(execution["attempts"]),
            "by_blinded_request_id": {},
        }
    )

    reason_code: str
    if local_contract_failure:
        terminal_status = "STOP_OUTPUT_CONTRACT"
        reason_code = "PUBLIC_OUTPUT_COMPILER_REJECTED"
    elif not complete:
        terminal_status = "INCOMPLETE_NOT_ASSESSED"
        reason_code = "FIXED_ATTEMPT_SEQUENCE_INCOMPLETE"
    elif endpoints["channel_adherence"]["status"] != "PASS":
        terminal_status = "STOP_CHANNEL_ADHERENCE_NULL"
        reason_code = "X_Z_SCHEDULE_ADHERENCE_NOT_8_OF_8"
    elif endpoints["positive_control"]["status"] != "POSITIVE":
        terminal_status = "STOP_ACTUATOR_ECHO_ONLY"
        reason_code = "X_NON_ECHO_PROPAGATION_NULL"
    elif endpoints["d_c_adherence"]["status"] != "PASS":
        terminal_status = "STOP_GRADIENT_PLACEMENT_NULL"
        reason_code = "D_C_SCHEDULE_ADHERENCE_NOT_8_OF_8"
    elif endpoints["gradient_placement"]["status"] != "POSITIVE":
        terminal_status = "STOP_GRADIENT_PLACEMENT_NULL"
        reason_code = "D_C_DIRECTIONAL_PLACEMENT_NULL"
    else:
        terminal_status = "PROMOTE_V0_6_4_ACTUATOR_GATE"
        reason_code = "ALL_FROZEN_ACTUATOR_GATES_PASSED"

    result = {
        "schema_version": RESULT_SCHEMA,
        "mode": "openai_live_actuator_calibration_v0_6_3_r01",
        "claim_boundary": list(CLAIM_BOUNDARY),
        "preflight_anchor_tag_object": PRELIGHT_ANCHOR_TAG_OBJECT,
        "preflight_anchor_commit": PRELIGHT_ANCHOR_COMMIT,
        "policy_lock_fingerprint_sha256": preflight_value[
            "policy_lock_fingerprint_sha256"
        ],
        "projection_fingerprint_sha256": material["projection"]["fingerprint_sha256"],
        "preflight": _clone(preflight_value),
        "source_snapshot_sha256": dict(source_snapshot),
        "execution": _clone(execution),
        "endpoints": endpoints,
        "quality_status": quality,
        "gold_loaded_after_complete_compilation": quality["gold_loaded"],
        "decision": {
            "run_status": execution["run_status"],
            "terminal_status": terminal_status,
            "reason_code": reason_code,
            "promotion_ready": terminal_status == "PROMOTE_V0_6_4_ACTUATOR_GATE",
            "quality_is_promotion_gate": False,
        },
        "usage": _usage_summary(execution["attempts"]),
    }
    return _seal(result)


def _calls_bytes(result: Mapping[str, Any]) -> bytes:
    rows: list[dict[str, Any]] = []
    for attempt in result["execution"]["attempts"]:
        rows.append(
            {
                "schema_version": CALL_SCHEMA,
                "run_position": attempt["run_position"],
                "block_id": attempt["block_id"],
                "block_position": attempt["block_position"],
                "blinded_request_id": attempt["blinded_request_id"],
                "status": attempt["status"],
                "failure": _clone(attempt.get("failure")),
                "receipt": _clone(attempt["receipt"]),
            }
        )
    return b"".join(_canonical_bytes(row, trailing_newline=True) for row in rows)


def _provider_inputs_artifact(material: Mapping[str, Any]) -> dict[str, Any]:
    return _seal(
        {
            "schema_version": PROVIDER_INPUTS_SCHEMA,
            "projection_fingerprint_sha256": material["projection"][
                "fingerprint_sha256"
            ],
            "payloads": [
                {
                    **{key: _clone(row[key]) for key in row if key != "payload"},
                    "provider_payload_sha256": fingerprint(row["payload"]),
                    "payload": _clone(row["payload"]),
                }
                for row in material["attempts"]
            ],
        }
    )


def _report(result: Mapping[str, Any]) -> str:
    decision = result["decision"]
    endpoints = result["endpoints"]
    lines = [
        "# EBRT v0.6.3 live actuator calibration r01",
        "",
        f"Terminal status: **{decision['terminal_status']}**",
        "",
        "## Frozen gate summary",
        "",
        "| Gate | Status |",
        "| --- | --- |",
        f"| Run | {decision['run_status']} |",
        f"| X/Z channel adherence | {endpoints['channel_adherence']['status']} |",
        f"| X non-echo propagation | {endpoints['positive_control']['status']} |",
        f"| D/C schedule adherence | {endpoints['d_c_adherence']['status']} |",
        f"| D/C gradient placement | {endpoints['gradient_placement']['status']} |",
        f"| Secondary quality | {result['quality_status']['status']} |",
        "",
        f"Reason code: `{decision['reason_code']}`",
        "",
    ]
    if result["execution"]["run_status"] == "COMPLETE":
        lines.extend(
            [
                "## Block effects",
                "",
                "| Block | Case | Trial | X adheres | Z adheres | D adheres | C adheres | delta X-Z | delta D-C |",
                "| --- | --- | ---: | --- | --- | --- | --- | ---: | ---: |",
            ]
        )
        for row in endpoints["blocks"]:
            lines.append(
                "| {block} | {case} | {trial} | {x} | {z} | {d} | {c} | {dxz:.12g} | {ddc:.12g} |".format(
                    block=row["block_id"],
                    case=row["case_id"],
                    trial=row["trial_id"],
                    x="PASS" if row["x_adherence"] else "FAIL",
                    z="PASS" if row["z_adherence"] else "FAIL",
                    d="PASS" if row["d_adherence"] else "FAIL",
                    c="PASS" if row["c_adherence"] else "FAIL",
                    dxz=float(row["delta_xz"]),
                    ddc=float(row["delta_dc"]),
                )
            )
        lines.extend(
            [
                "",
                f"Aggregate X-Z: `{endpoints['positive_control']['aggregate_delta_xz']:.12g}`",
                "",
                f"Aggregate D-C: `{endpoints['gradient_placement']['aggregate_delta_dc']:.12g}`",
                "",
            ]
        )
    lines.extend(
        [
            "## Boundary",
            "",
            *[f"- {item}" for item in result["claim_boundary"]],
            "",
        ]
    )
    return "\n".join(lines)


def _manifest_value(
    *,
    files: Mapping[str, bytes],
    result: Mapping[str, Any],
    lock: Mapping[str, Any],
) -> dict[str, Any]:
    receipts = {
        name: {"bytes": len(raw), "sha256": _sha256_bytes(raw)}
        for name, raw in files.items()
    }
    return _seal(
        {
            "schema_version": MANIFEST_SCHEMA,
            "status": "SEALED_LIVE_RESULT",
            "terminal_status": result["decision"]["terminal_status"],
            "run_status": result["decision"]["run_status"],
            "policy_lock_fingerprint_sha256": lock["fingerprint_sha256"],
            "result_fingerprint_sha256": result["fingerprint_sha256"],
            "source_snapshot_sha256": result["source_snapshot_sha256"],
            "artifacts": receipts,
            "claim_boundary": list(CLAIM_BOUNDARY),
        }
    )


def _materialize_files(
    result: Mapping[str, Any],
    *,
    material: Mapping[str, Any],
    lock: Mapping[str, Any],
    journal_bytes: bytes,
) -> dict[str, bytes]:
    files = {
        "result.json": _pretty_bytes(result),
        "calls.jsonl": _calls_bytes(result),
        "attempt_journal.jsonl": journal_bytes,
        "provider_inputs.json": _pretty_bytes(_provider_inputs_artifact(material)),
        "projection_bundle.json": _pretty_bytes(material["projection"]),
        "report.md": _report(result).encode("utf-8"),
    }
    manifest = _manifest_value(files=files, result=result, lock=lock)
    files["manifest.json"] = _pretty_bytes(manifest)
    if set(files) != set(ARTIFACT_FILES):
        raise ActuatorLiveExecutionError("artifact file set drifted before publish")
    return files


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _publish(output: Path, files: Mapping[str, bytes]) -> None:
    if output != DEFAULT_OUTPUT or output.is_symlink() or output.parent.is_symlink():
        raise ActuatorLiveExecutionError("live publish namespace is noncanonical")
    if output.exists():
        raise ActuatorLiveExecutionError(f"output already exists: {output}")
    if set(files) != set(ARTIFACT_FILES):
        raise ActuatorLiveExecutionError("artifact file set drifted before publish")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    try:
        for name in ARTIFACT_FILES:
            path = temporary / name
            path.write_bytes(files[name])
            with path.open("rb") as handle:
                os.fsync(handle.fileno())
        _fsync_directory(temporary)
        os.replace(temporary, output)
        _fsync_directory(output.parent)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def run_live() -> dict[str, Any]:
    output = DEFAULT_OUTPUT
    material = _preflight_materialize(require_authorization=True)
    lock = material["lock"]
    source_before = _source_snapshot(lock)
    staging = _staging_directory(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    staging.mkdir(mode=0o700)
    _fsync_directory(output.parent)
    plan = _seal(
        {
            "schema_version": "ebrt-actuator-live-inflight-plan-v0.6.3-r01",
            "status": "IRREVERSIBLE_16_CALL_BLOCK_NOT_YET_STARTED",
            "preflight_anchor_tag_object": PRELIGHT_ANCHOR_TAG_OBJECT,
            "preflight_anchor_commit": PRELIGHT_ANCHOR_COMMIT,
            "policy_lock_fingerprint_sha256": lock["fingerprint_sha256"],
            "projection_fingerprint_sha256": material["projection"][
                "fingerprint_sha256"
            ],
            "call_order_blinded_request_ids": [
                row["blinded_request_id"] for row in material["attempts"]
            ],
            "payload_fingerprints": {
                row["blinded_request_id"]: fingerprint(row["payload"])
                for row in material["attempts"]
            },
            "source_snapshot_sha256": source_before,
            "execution_authorization": material["preflight"]["execution_authorization"],
            "no_resume": True,
        }
    )
    plan_path = staging / "plan.json"
    plan_path.write_bytes(_pretty_bytes(plan))
    with plan_path.open("rb") as handle:
        os.fsync(handle.fileno())
    _fsync_directory(staging)
    journal_path = staging / "attempt_journal.jsonl"
    journal_path.touch(mode=0o600)
    with journal_path.open("rb") as handle:
        os.fsync(handle.fileno())
    _fsync_directory(staging)

    with _semantic_gold_denied() as gold_counts:
        execution = _execute_gold_free(material, journal_path=journal_path)
        _validate_execution(execution, material)
        journal_bytes = journal_path.read_bytes()
        if journal_bytes != _journal_bytes(execution):
            raise ActuatorLiveExecutionError("durable attempt journal drifted")
        source_after = _source_snapshot(lock)
    if gold_counts["attempted_gold_accesses"] != 0:
        raise ActuatorLiveExecutionError(
            "semantic gold access occurred during provider execution"
        )
    if source_after != source_before:
        raise ActuatorLiveExecutionError("locked sources changed during live execution")

    result = _finalize(
        execution,
        material=material,
        preflight_value=material["preflight"],
        source_snapshot=source_before,
        lock=lock,
    )
    files = _materialize_files(
        result,
        material=material,
        lock=lock,
        journal_bytes=journal_bytes,
    )
    _publish(output, files)
    validate_bundle(output)
    shutil.rmtree(staging)
    _fsync_directory(output.parent)
    return {
        "artifact_directory": str(output),
        "run_status": result["decision"]["run_status"],
        "terminal_status": result["decision"]["terminal_status"],
        "reason_code": result["decision"]["reason_code"],
        "result_fingerprint_sha256": result["fingerprint_sha256"],
        "usage": result["usage"],
    }


def _read_artifact_directory(output: Path) -> dict[str, bytes]:
    if not output.is_dir() or output.is_symlink():
        raise ActuatorLiveExecutionError(f"artifact directory unavailable: {output}")
    observed: list[str] = []
    for path in output.rglob("*"):
        if path.is_symlink() or not path.is_file() or path.parent != output:
            raise ActuatorLiveExecutionError(
                "artifact directory has noncanonical entry"
            )
        observed.append(path.name)
    if set(observed) != set(ARTIFACT_FILES) or len(observed) != len(ARTIFACT_FILES):
        raise ActuatorLiveExecutionError("artifact directory file set drifted")
    return {name: (output / name).read_bytes() for name in ARTIFACT_FILES}


def _load_json_bytes(raw: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(
            raw.decode("utf-8"),
            parse_constant=_reject_constant,
            object_pairs_hook=_reject_duplicates,
        )
    except ActuatorLiveExecutionError:
        raise
    except Exception as error:
        raise ActuatorLiveExecutionError(f"invalid artifact JSON: {label}") from error
    if not isinstance(value, dict):
        raise ActuatorLiveExecutionError(f"artifact JSON root invalid: {label}")
    return value


def _validate_execution(
    execution: Mapping[str, Any], material: Mapping[str, Any]
) -> None:
    if set(execution) != {
        "attempts",
        "provider_outputs",
        "compiled_outputs",
        "run_status",
        "unattempted_blinded_request_ids",
    }:
        raise ActuatorLiveExecutionError("execution schema drifted")
    attempts = execution["attempts"]
    if not isinstance(attempts, list) or not attempts or len(attempts) > 16:
        raise ActuatorLiveExecutionError("attempt ledger malformed")
    schedule = material["attempts"]
    expected_prefix = schedule[: len(attempts)]
    if [row.get("blinded_request_id") for row in attempts] != [
        row["blinded_request_id"] for row in expected_prefix
    ]:
        raise ActuatorLiveExecutionError("attempt order drifted")
    if any(row.get("status") != "COMPLETED" for row in attempts[:-1]):
        raise ActuatorLiveExecutionError("execution continued after terminal failure")
    allowed_statuses = {
        "COMPLETED",
        "PROVIDER_BOUNDARY_ERROR",
        "LOCAL_OUTPUT_CONTRACT_ERROR",
    }
    if any(row.get("status") not in allowed_statuses for row in attempts):
        raise ActuatorLiveExecutionError("attempt status unknown")

    outputs = execution["provider_outputs"]
    compiled = execution["compiled_outputs"]
    if not isinstance(outputs, dict) or not isinstance(compiled, dict):
        raise ActuatorLiveExecutionError("execution output maps malformed")
    observed_output_ids: set[str] = set()
    observed_compiled_ids: set[str] = set()
    for attempt, scheduled in zip(attempts, expected_prefix, strict=True):
        blind_id = scheduled["blinded_request_id"]
        payload = scheduled["payload"]
        expected_identity = {
            key: scheduled[key] for key in scheduled if key != "payload"
        }
        if any(attempt.get(key) != value for key, value in expected_identity.items()):
            raise ActuatorLiveExecutionError("attempt schedule binding drifted")
        if attempt.get("provider_input_fingerprint_sha256") != fingerprint(payload):
            raise ActuatorLiveExecutionError("attempt provider input drifted")
        status = attempt["status"]
        failure = attempt.get("failure")
        if status == "COMPLETED" and failure is not None:
            raise ActuatorLiveExecutionError(
                "completed attempt retained a failure record"
            )
        base_keys = set(expected_identity) | {
            "provider_input_fingerprint_sha256",
            "receipt",
            "failure",
            "status",
        }
        expected_attempt_keys = (
            base_keys
            if status == "PROVIDER_BOUNDARY_ERROR"
            else base_keys | {"provider_output_fingerprint_sha256"}
            if status == "LOCAL_OUTPUT_CONTRACT_ERROR"
            else base_keys
            | {
                "provider_output_fingerprint_sha256",
                "compiled_output_fingerprint_sha256",
            }
        )
        if set(attempt) != expected_attempt_keys:
            raise ActuatorLiveExecutionError("attempt schema drifted")
        provider_completed = status != "PROVIDER_BOUNDARY_ERROR"
        _validate_receipt(
            attempt["receipt"],
            payload,
            provider_completed=provider_completed,
            failure=failure if not provider_completed else None,
        )
        if status == "PROVIDER_BOUNDARY_ERROR":
            if blind_id in outputs or blind_id in compiled or failure is None:
                raise ActuatorLiveExecutionError("provider failure retained output")
            continue

        public_output = outputs.get(blind_id)
        if not isinstance(public_output, dict):
            raise ActuatorLiveExecutionError("provider-completed output missing")
        observed_output_ids.add(blind_id)
        if attempt.get("provider_output_fingerprint_sha256") != fingerprint(
            public_output
        ):
            raise ActuatorLiveExecutionError("provider output fingerprint drifted")
        if status == "LOCAL_OUTPUT_CONTRACT_ERROR":
            if blind_id in compiled or failure is None:
                raise ActuatorLiveExecutionError("rejected output retained compilation")
            try:
                core.compile_output(
                    public_output,
                    payload=payload,
                    case=material["cases"][scheduled["case_id"]],
                )
            except Exception as error:
                if _failure_record(error) != failure:
                    raise ActuatorLiveExecutionError(
                        "local output failure reason drifted"
                    ) from error
            else:
                raise ActuatorLiveExecutionError("rejected output now compiles")
            continue

        expected_compiled = core.compile_output(
            public_output,
            payload=payload,
            case=material["cases"][scheduled["case_id"]],
        )
        observed = compiled.get(blind_id)
        if observed != expected_compiled:
            raise ActuatorLiveExecutionError("compiled output differs from recompile")
        if (
            attempt.get("compiled_output_fingerprint_sha256")
            != observed["fingerprint_sha256"]
        ):
            raise ActuatorLiveExecutionError("compiled output fingerprint drifted")
        observed_compiled_ids.add(blind_id)

    if set(outputs) != observed_output_ids or set(compiled) != observed_compiled_ids:
        raise ActuatorLiveExecutionError("execution output key set drifted")
    complete = len(attempts) == 16 and all(
        row["status"] == "COMPLETED" for row in attempts
    )
    if not complete and attempts[-1]["status"] not in {
        "PROVIDER_BOUNDARY_ERROR",
        "LOCAL_OUTPUT_CONTRACT_ERROR",
    }:
        raise ActuatorLiveExecutionError(
            "incomplete execution lacks a terminal failed attempt"
        )
    if execution["run_status"] != ("COMPLETE" if complete else "INCOMPLETE"):
        raise ActuatorLiveExecutionError("execution run status drifted")
    if execution["unattempted_blinded_request_ids"] != [
        row["blinded_request_id"] for row in schedule[len(attempts) :]
    ]:
        raise ActuatorLiveExecutionError("unattempted request set drifted")


def validate_bundle(output: Path = DEFAULT_OUTPUT) -> None:
    lock = _load_lock()
    files = _read_artifact_directory(output)
    manifest = _load_json_bytes(files["manifest.json"], "manifest.json")
    if files["manifest.json"] != _pretty_bytes(manifest):
        raise ActuatorLiveExecutionError("manifest JSON encoding is noncanonical")
    if manifest.get("schema_version") != MANIFEST_SCHEMA:
        raise ActuatorLiveExecutionError("manifest schema drifted")
    if manifest.get("fingerprint_sha256") != fingerprint(
        {
            key: _clone(value)
            for key, value in manifest.items()
            if key != "fingerprint_sha256"
        }
    ):
        raise ActuatorLiveExecutionError("manifest fingerprint drifted")
    expected_non_manifest = set(ARTIFACT_FILES) - {"manifest.json"}
    if set(manifest.get("artifacts", {})) != expected_non_manifest:
        raise ActuatorLiveExecutionError("manifest artifact table drifted")
    for name in expected_non_manifest:
        receipt = manifest["artifacts"][name]
        if receipt != {
            "bytes": len(files[name]),
            "sha256": _sha256_bytes(files[name]),
        }:
            raise ActuatorLiveExecutionError(f"artifact receipt drifted: {name}")

    material = _materialize_projection()
    if files["projection_bundle.json"] != _pretty_bytes(material["projection"]):
        raise ActuatorLiveExecutionError(
            "published projection differs from sealed preflight"
        )
    provider_inputs = _load_json_bytes(
        files["provider_inputs.json"], "provider_inputs.json"
    )
    if files["provider_inputs.json"] != _pretty_bytes(provider_inputs):
        raise ActuatorLiveExecutionError(
            "provider inputs JSON encoding is noncanonical"
        )
    if provider_inputs != _provider_inputs_artifact(material):
        raise ActuatorLiveExecutionError(
            "provider inputs differ from sealed projection"
        )

    result = _load_json_bytes(files["result.json"], "result.json")
    if files["result.json"] != _pretty_bytes(result):
        raise ActuatorLiveExecutionError("result JSON encoding is noncanonical")
    if result.get("schema_version") != RESULT_SCHEMA or result.get(
        "fingerprint_sha256"
    ) != fingerprint(
        {
            key: _clone(value)
            for key, value in result.items()
            if key != "fingerprint_sha256"
        }
    ):
        raise ActuatorLiveExecutionError("result schema or fingerprint drifted")
    if result.get("source_snapshot_sha256") != _source_snapshot(lock):
        raise ActuatorLiveExecutionError("result source snapshot drifted")
    recorded_authorization = result.get("preflight", {}).get("execution_authorization")
    if not isinstance(recorded_authorization, Mapping):
        raise ActuatorLiveExecutionError("result execution authorization missing")
    _validate_recorded_execution_authorization(recorded_authorization)
    expected_preflight = _build_preflight_record(
        lock=lock,
        material=material,
        source_snapshot=result["source_snapshot_sha256"],
        require_api_key=False,
        execution_authorization=recorded_authorization,
    )
    if result.get("preflight") != expected_preflight:
        raise ActuatorLiveExecutionError("result preflight differs from rederivation")
    _validate_execution(result["execution"], material)
    expected_result = _finalize(
        result["execution"],
        material=material,
        preflight_value=expected_preflight,
        source_snapshot=result["source_snapshot_sha256"],
        lock=lock,
    )
    if result != expected_result:
        raise ActuatorLiveExecutionError(
            "result differs from independent recomputation"
        )
    if files["calls.jsonl"] != _calls_bytes(result):
        raise ActuatorLiveExecutionError("calls ledger drifted")
    if files["attempt_journal.jsonl"] != _journal_bytes(result["execution"]):
        raise ActuatorLiveExecutionError("attempt journal drifted")
    if files["report.md"] != _report(result).encode("utf-8"):
        raise ActuatorLiveExecutionError("report drifted")
    if manifest != _manifest_value(
        files={name: files[name] for name in expected_non_manifest},
        result=result,
        lock=lock,
    ):
        raise ActuatorLiveExecutionError("manifest differs from reconstruction")


def _print_json(value: Mapping[str, Any]) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("emit-lock")
    subparsers.add_parser("component-self-test")
    subparsers.add_parser("preflight")
    subparsers.add_parser("run-live")
    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "emit-lock":
        _print_json(policy_lock_material())
    elif args.command == "component-self-test":
        _print_json(component_self_test())
    elif args.command == "preflight":
        _print_json(preflight())
    elif args.command == "run-live":
        _print_json(run_live())
    elif args.command == "validate":
        validate_bundle(args.output)
        _print_json({"artifact_directory": str(args.output), "status": "VALID"})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
