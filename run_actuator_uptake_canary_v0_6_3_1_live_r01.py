#!/usr/bin/env python3
"""Sealed four-call hosted execution for the EBRT v0.6.3.1 uptake canary.

The network-zero v0.6.3.1 monolith owns the fixture, local float64 backward,
four immutable evidence permutations, typed provider output, public compiler,
and decision classifier.  This file adds only the separately authorized hosted
boundary and durable result plumbing.

Exactly four calls are attempted in the frozen C, X, D, Z order.  A provider or
public-output structural failure is recorded and the remaining arms continue;
such a block is never assessed and semantic gold is never read.  Pre-call,
source, journal, provider-audit, or receipt-integrity failure is irrecoverable:
the in-flight namespace remains on disk and no further call is made.  There is
no retry, resume, reorder, subset, backfill, or compatibility fallback.
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
from typing import Any, Callable, Iterator, Mapping, Sequence
from unittest import mock

from openai import OpenAI

import actuator_uptake_canary_v0_6_3_1 as core
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
LOCK_PATH = ROOT / "policy_lock_actuator_uptake_canary_v0_6_3_1_live_r01.json"
PREFLIGHT_DIR = ROOT / "artifacts" / "actuator_uptake_canary_v0_6_3_1_preflight"
COMMITTED_PROJECTION_PATH = PREFLIGHT_DIR / "projection_bundle.json"
COMMITTED_PREFLIGHT_MANIFEST_PATH = PREFLIGHT_DIR / "manifest.json"
COMMITTED_ZERO_CALL_POLICY_PATH = (
    ROOT / "policy_lock_actuator_uptake_canary_v0_6_3_1.json"
)
DEFAULT_OUTPUT = ROOT / "artifacts" / "actuator_uptake_canary_v0_6_3_1_live_r01"
EXECUTION_AUTHORIZATION_TAG = "v0.6.3.1-live-r01-authorized"

PREFLIGHT_ANCHOR_TAG = "v0.6.3.1-preflight"
PREFLIGHT_ANCHOR_TAG_OBJECT = "ea987355a1f720aa0859f6ad92f874cf21d0fbe5"
PREFLIGHT_ANCHOR_COMMIT = "c5e1244055e5d7f83493698119549c49df718ed7"
PREFLIGHT_MANIFEST_BYTES_SHA256 = (
    "b118576c2e3ffcee66a34831622944fac8e7123270cca7cdad98b8295daf4131"
)
PREFLIGHT_PROJECTION_BYTES_SHA256 = (
    "a87de8b219d7d5f27eade5122f919483d9653948a037929e21b3417c1964e62a"
)
ZERO_CALL_POLICY_BYTES_SHA256 = (
    "bde4ad54569c4e71c1745104575756690d632422f1bd589fda4b5c695787c4dd"
)
EXPECTED_EXECUTION_ORDER = ("C", "X", "D", "Z")

MODEL = "gpt-5.6-sol"
REASONING_EFFORT = "low"
MAX_OUTPUT_TOKENS = 1024
TIMEOUT_SECONDS = 60

LOCK_SCHEMA = "ebrt-actuator-uptake-live-policy-v0.6.3.1-r01"
RESULT_SCHEMA = "ebrt-actuator-uptake-live-result-v0.6.3.1-r01"
CALL_SCHEMA = "ebrt-actuator-uptake-live-call-v0.6.3.1-r01"
JOURNAL_SCHEMA = "ebrt-actuator-uptake-live-journal-v0.6.3.1-r01"
PROVIDER_INPUTS_SCHEMA = "ebrt-actuator-uptake-live-inputs-v0.6.3.1-r01"
MANIFEST_SCHEMA = "ebrt-actuator-uptake-live-manifest-v0.6.3.1-r01"

ARTIFACT_FILES = (
    "result.json",
    "calls.jsonl",
    "attempt_journal.jsonl",
    "provider_inputs.json",
    "projection_bundle.json",
    "report.md",
    "manifest.json",
)

OUTPUT_STRUCTURAL_REASON_CODES = frozenset(
    {
        "OUTPUT_SCHEMA_INVALID",
        "OUTPUT_CHECKPOINT_DRIFT",
        "OUTPUT_ANSWER_NOT_ALLOWED",
        "OUTPUT_FORMAT_NOT_ALLOWED",
        "OUTPUT_CLOSURE_ID_UNKNOWN",
        "OUTPUT_REVIEWED_EVIDENCE_DUPLICATE",
        "OUTPUT_REVIEWED_EVIDENCE_UNKNOWN",
    }
)

POSITIVE_CONTROL_STATUSES = frozenset(
    {
        "POSITIVE_CONTROL_CEILING",
        "CHANNEL_OPEN_DIRECTIONAL",
        "ACTUATOR_CHANNEL_INERT",
        "CHANNEL_OPEN_ADVERSE",
        "CHANNEL_OPEN_DIRECTION_AMBIGUOUS",
    }
)
GRADIENT_PLACEMENT_STATUSES = frozenset(
    {
        "D_C_TARGET_CEILING",
        "GRADIENT_PLACEMENT_DIRECTIONAL",
        "GRADIENT_PLACEMENT_NULL",
        "GRADIENT_PLACEMENT_ADVERSE",
        "GRADIENT_PLACEMENT_AMBIGUOUS",
    }
)
DECISION_CLAIM_BOUNDARY = (
    "PROMOTE_TO_FRESH_REPLICATION opens only a separately sealed replication gate.",
    "This four-call classification is not a quality, causal, or population-level result.",
)

SOURCE_PATHS = {
    "runner": "run_actuator_uptake_canary_v0_6_3_1_live_r01.py",
    "core": "actuator_uptake_canary_v0_6_3_1.py",
    "fixture": "fixtures/actuator_uptake_canary_v0_6_3_1.json",
    "post_call_gold": "fixtures/actuator_uptake_canary_gold_v0_6_3_1.json",
    "zero_call_policy": "policy_lock_actuator_uptake_canary_v0_6_3_1.json",
    "zero_call_manifest": (
        "artifacts/actuator_uptake_canary_v0_6_3_1_preflight/manifest.json"
    ),
    "zero_call_projection": (
        "artifacts/actuator_uptake_canary_v0_6_3_1_preflight/projection_bundle.json"
    ),
    "response_boundary": "openai_response_boundary_v0_4_3.py",
    "provider_base": "openai_reasoning_provider_v0_4.py",
    "receipt_contract": "language_replay_bridge_v0_4.py",
    "requirements": "requirements.txt",
    "requirements_live": "requirements-live.txt",
    "protocol_note": "docs/RND_ACTUATOR_UPTAKE_CANARY_V0_6_3_1_LIVE_R01.md",
}

CLAIM_BOUNDARY = (
    "This is one sealed four-call actuator-uptake canary, not a population estimate or quality benchmark.",
    "The sole intentionally treatment-varying semantic payload field is evidence order.",
    "The provider never sees C/X/D/Z, treatment metadata, gradient values, controller internals, closure roles, gold, or grades.",
    "The local float64 backward pass ends before JSON; no gradient crosses GPT or the provider boundary.",
    "Known stale or mixed closures are valid semantic endpoints; only transport, parse, schema, and unknown-ID failures are structural invalidity.",
    "A positive canary opens only a separately sealed fresh replication; it never directly promotes v0.6.4.",
    "The fixed serial C-to-X-to-D-to-Z block cannot separate treatment order from temporal or provider drift.",
    "Provider receipts and execution provenance are operator-attested local records, not provider-signed proof.",
    "The authorization tag prevents accidental execution from an unreviewed checkout but does not provide global exactly-once semantics across clones.",
    "The semantic-gold barrier is a locked Path.read_bytes guard, not an operating-system sandbox.",
    "No result supports hidden-state editing, causal superiority, quality improvement, or general reasoning improvement.",
)

PROVIDER_INSTRUCTIONS = (
    "Return only the strict public uptake-canary output. Treat the ordered raw "
    "evidence as the sole semantic authority and inspect the immutable chunks in "
    "the order supplied. Select exactly one candidate closure ID from the supplied "
    "catalog. Return exactly the first three inspected evidence IDs, in inspection "
    "order, as reviewed_evidence_ids. Derive current_answer and record_format only "
    "from the raw evidence and allowed values. Do not return private chain-of-thought, "
    "hidden reasoning, a model-written closure, treatment metadata, or extra fields."
)
INSTRUCTIONS_FINGERPRINT = fingerprint(PROVIDER_INSTRUCTIONS)
RESPONSE_SCHEMA_FINGERPRINT = fingerprint(core.UptakeProviderOutput.model_json_schema())


class UptakeLiveExecutionError(RuntimeError):
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
    output.pop("fingerprint_sha256", None)
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
    raise UptakeLiveExecutionError(f"nonfinite JSON constant rejected: {value}")


def _reject_duplicates(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise UptakeLiveExecutionError(f"duplicate JSON key rejected: {key}")
        output[key] = value
    return output


def _reject_nonfinite(value: Any, *, label: str) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise UptakeLiveExecutionError(f"nonfinite JSON number rejected: {label}")
    if isinstance(value, Mapping):
        for child in value.values():
            _reject_nonfinite(child, label=label)
    elif isinstance(value, list):
        for child in value:
            _reject_nonfinite(child, label=label)


def _strict_json_bytes(raw: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(
            raw.decode("utf-8"),
            parse_constant=_reject_constant,
            object_pairs_hook=_reject_duplicates,
        )
    except UptakeLiveExecutionError:
        raise
    except Exception as error:
        raise UptakeLiveExecutionError(f"invalid JSON: {label}") from error
    _reject_nonfinite(value, label=label)
    if not isinstance(value, dict):
        raise UptakeLiveExecutionError(f"JSON root is not an object: {label}")
    return value


def _strict_load(path: Path) -> dict[str, Any]:
    return _strict_json_bytes(path.read_bytes(), str(path))


def _file_receipt(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    return {
        "path": str(path.relative_to(ROOT)),
        "bytes": len(raw),
        "sha256": _sha256_bytes(raw),
    }


def _anchored_post_call_gold_receipt() -> dict[str, Any]:
    if _sha256_path(COMMITTED_ZERO_CALL_POLICY_PATH) != ZERO_CALL_POLICY_BYTES_SHA256:
        raise UptakeLiveExecutionError("committed zero-call policy bytes drifted")
    policy = _strict_load(COMMITTED_ZERO_CALL_POLICY_PATH)
    receipt = policy.get("sources", {}).get("post_call_gold")
    expected_path = SOURCE_PATHS["post_call_gold"]
    if (
        not isinstance(receipt, Mapping)
        or set(receipt) != {"path", "bytes", "sha256"}
        or receipt.get("path") != expected_path
        or type(receipt.get("bytes")) is not int
        or int(receipt["bytes"]) <= 0
        or not _is_sha256(receipt.get("sha256"))
    ):
        raise UptakeLiveExecutionError("anchored post-call gold receipt invalid")
    return _clone(receipt)


def _file_receipts() -> dict[str, dict[str, Any]]:
    gold_receipt = _anchored_post_call_gold_receipt()
    return {
        label: (
            gold_receipt if label == "post_call_gold" else _file_receipt(ROOT / path)
        )
        for label, path in SOURCE_PATHS.items()
    }


def _runtime_contract() -> dict[str, Any]:
    return {
        "provider": "openai_responses",
        "api": "responses.with_raw_response.parse+raw.parse",
        "model": MODEL,
        "reasoning_effort": REASONING_EFFORT,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "timeout_seconds": TIMEOUT_SECONDS,
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


def _source_snapshot(lock: Mapping[str, Any]) -> dict[str, str]:
    snapshot: dict[str, str] = {}
    for label, receipt in lock["sources"].items():
        if label != "post_call_gold":
            snapshot[label] = _sha256_path(ROOT / receipt["path"])
    return snapshot


@contextmanager
def _network_denied() -> Iterator[dict[str, int]]:
    counts = {"network_calls": 0}

    def denied(*_args: Any, **_kwargs: Any) -> None:
        counts["network_calls"] += 1
        raise AssertionError("network forbidden during v0.6.3.1 live preflight")

    with (
        mock.patch.object(socket, "getaddrinfo", side_effect=denied),
        mock.patch.object(socket, "create_connection", side_effect=denied),
        mock.patch.object(socket.socket, "connect", side_effect=denied),
        mock.patch.object(socket.socket, "connect_ex", side_effect=denied),
    ):
        yield counts


@contextmanager
def _semantic_gold_denied() -> Iterator[dict[str, int]]:
    counts = {"attempted_gold_accesses": 0}
    original = Path.read_bytes
    gold_path = core.GOLD_PATH.resolve()

    def guarded(path: Path) -> bytes:
        if path.resolve() == gold_path:
            counts["attempted_gold_accesses"] += 1
            raise UptakeLiveExecutionError(
                "semantic gold access attempted before four valid compilations"
            )
        return original(path)

    with mock.patch.object(Path, "read_bytes", guarded):
        yield counts


def _materialize_projection() -> dict[str, Any]:
    if (
        _sha256_path(COMMITTED_PREFLIGHT_MANIFEST_PATH)
        != PREFLIGHT_MANIFEST_BYTES_SHA256
    ):
        raise UptakeLiveExecutionError("committed preflight manifest bytes drifted")
    if _sha256_path(COMMITTED_PROJECTION_PATH) != PREFLIGHT_PROJECTION_BYTES_SHA256:
        raise UptakeLiveExecutionError("committed preflight projection bytes drifted")
    if _sha256_path(COMMITTED_ZERO_CALL_POLICY_PATH) != ZERO_CALL_POLICY_BYTES_SHA256:
        raise UptakeLiveExecutionError("committed zero-call policy bytes drifted")

    fixture = core._strict_load(core.FIXTURE_PATH)
    core.validate_fixture(fixture)
    controller = core.derive_controller(fixture)
    with _network_denied() as counts:
        rebuilt = core.build_projection(fixture, controller)
    if counts["network_calls"] != 0:
        raise UptakeLiveExecutionError("projection attempted network access")
    committed = _strict_load(COMMITTED_PROJECTION_PATH)
    if _canonical_bytes(rebuilt) != _canonical_bytes(committed):
        raise UptakeLiveExecutionError(
            "rebuilt projection differs from committed bytes"
        )
    if tuple(committed.get("execution_order", ())) != EXPECTED_EXECUTION_ORDER:
        raise UptakeLiveExecutionError("frozen execution order is not C,X,D,Z")

    payload_rows = committed.get("provider_payloads")
    key_rows = committed.get("public_treatment_key")
    if not isinstance(payload_rows, list) or len(payload_rows) != 4:
        raise UptakeLiveExecutionError("projection payload table is not four rows")
    if not isinstance(key_rows, list) or len(key_rows) != 4:
        raise UptakeLiveExecutionError("projection treatment table is not four rows")
    payload_by_blind = {
        row.get("blinded_request_id"): row
        for row in payload_rows
        if isinstance(row, Mapping)
    }
    key_by_sequence = {
        row.get("sequence_index"): row for row in key_rows if isinstance(row, Mapping)
    }
    if len(payload_by_blind) != 4 or len(key_by_sequence) != 4:
        raise UptakeLiveExecutionError("projection identity set drifted")

    attempts: list[dict[str, Any]] = []
    case = fixture["case"]
    for sequence_index, expected_arm in enumerate(EXPECTED_EXECUTION_ORDER, start=1):
        key = key_by_sequence.get(sequence_index)
        if (
            key is None
            or key.get("treatment_id") != expected_arm
            or set(key) != {"sequence_index", "blinded_request_id", "treatment_id"}
        ):
            raise UptakeLiveExecutionError("projection treatment sequence drifted")
        blind_id = key["blinded_request_id"]
        wrapper = payload_by_blind.get(blind_id)
        if (
            wrapper is None
            or wrapper.get("sequence_index") != sequence_index
            or set(wrapper) != {"sequence_index", "blinded_request_id", "payload"}
        ):
            raise UptakeLiveExecutionError("scheduled sealed payload is missing")
        sealed_payload = _clone(wrapper["payload"])
        core._validate_fingerprint(sealed_payload, "live sealed payload")
        raw_payload = core._unseal(sealed_payload, "live sealed payload")
        audit = core.validate_provider_payload(raw_payload, case=case)
        if audit["payload_fingerprint_sha256"] != sealed_payload["fingerprint_sha256"]:
            raise UptakeLiveExecutionError(
                "raw/sealed provider payload binding drifted"
            )
        attempts.append(
            {
                "sequence_index": sequence_index,
                "blinded_request_id": blind_id,
                "treatment_id": expected_arm,
                "sealed_payload": sealed_payload,
                "raw_payload": raw_payload,
            }
        )
    return {
        "projection": committed,
        "fixture": fixture,
        "controller": controller,
        "case": case,
        "attempts": attempts,
    }


class OpenAIUptakeProviderLiveR01(InstrumentedResponsesClientBase):
    """Exactly-one-attempt provider over the raw, arm-free public payload."""

    def __init__(
        self, *, case: Mapping[str, Any], client: OpenAI | Any | None = None
    ) -> None:
        super().__init__(
            model=MODEL,
            reasoning_effort=REASONING_EFFORT,
            timeout_seconds=float(TIMEOUT_SECONDS),
            client=client,
        )
        self._case = _clone(case)

    @property
    def provenance(self) -> dict[str, Any]:
        return {
            **_runtime_contract(),
            "instructions_fingerprint_sha256": INSTRUCTIONS_FINGERPRINT,
            "response_schema_fingerprint_sha256": RESPONSE_SCHEMA_FINGERPRINT,
            "receipt_schema_version": RECEIPT_SCHEMA_VERSION,
        }

    def generate(
        self, raw_payload: Mapping[str, Any]
    ) -> tuple[dict[str, Any], ProviderReceipt]:
        core.validate_provider_payload(raw_payload, case=self._case)
        public_input = json.loads(canonical_json(dict(raw_payload)))
        parsed, receipt = self._parse(
            input_payload=public_input,
            instructions=PROVIDER_INSTRUCTIONS,
            text_format=core.UptakeProviderOutput,
            max_output_tokens=MAX_OUTPUT_TOKENS,
        )
        if not isinstance(parsed, core.UptakeProviderOutput):
            raise AssertionError("provider returned the wrong structured-output type")
        public_output = parsed.model_dump(mode="json")
        reparsed = core.UptakeProviderOutput.model_validate(public_output)
        if canonical_json(reparsed.model_dump(mode="json")) != canonical_json(
            public_output
        ):
            raise AssertionError("public uptake output did not round-trip exactly")
        return public_output, receipt


class _FakeRawResponse:
    def __init__(self, parsed: core.UptakeProviderOutput) -> None:
        self.status_code = 200
        self.headers = {"x-request-id": "v0631-live-offline-server-request"}
        self.content = b'{"offline":"v0631-live-provider-self-test"}'
        self._parsed = parsed

    def parse(self) -> Any:
        usage = SimpleNamespace(
            input_tokens=41,
            output_tokens=23,
            total_tokens=64,
            input_tokens_details=SimpleNamespace(cached_tokens=0, cache_write_tokens=0),
            output_tokens_details=SimpleNamespace(reasoning_tokens=5),
        )
        return SimpleNamespace(
            id="resp-v0631-live-offline",
            model=MODEL,
            service_tier="default",
            status="completed",
            error=None,
            incomplete_details=None,
            output=[],
            output_parsed=self._parsed,
            usage=usage,
        )


class _FakeRawParseEndpoint:
    def __init__(self, parsed: core.UptakeProviderOutput) -> None:
        self._parsed = parsed
        self.calls: list[dict[str, Any]] = []

    def parse(self, **kwargs: Any) -> _FakeRawResponse:
        self.calls.append(dict(kwargs))
        return _FakeRawResponse(self._parsed)


class _FakeOpenAIClient:
    def __init__(self, parsed: core.UptakeProviderOutput) -> None:
        self.max_retries = 0
        self.endpoint = _FakeRawParseEndpoint(parsed)
        self.responses = SimpleNamespace(
            with_raw_response=SimpleNamespace(parse=self.endpoint.parse)
        )


def policy_lock_material() -> dict[str, Any]:
    """Build the live authorization lock without parsing semantic gold."""

    material = _materialize_projection()
    projection = material["projection"]
    manifest = _strict_load(COMMITTED_PREFLIGHT_MANIFEST_PATH)
    zero_policy = _strict_load(COMMITTED_ZERO_CALL_POLICY_PATH)
    call_schedule = [
        {
            "sequence_index": row["sequence_index"],
            "blinded_request_id": row["blinded_request_id"],
            "treatment_id": row["treatment_id"],
            "provider_payload_fingerprint_sha256": row["sealed_payload"][
                "fingerprint_sha256"
            ],
        }
        for row in material["attempts"]
    ]
    return _seal(
        {
            "schema_version": LOCK_SCHEMA,
            "status": "PREREGISTERED_EXACT_FOUR_CALL_LIVE_BLOCK",
            "preflight_anchor": {
                "tag_name": PREFLIGHT_ANCHOR_TAG,
                "tag_object": PREFLIGHT_ANCHOR_TAG_OBJECT,
                "commit": PREFLIGHT_ANCHOR_COMMIT,
                "manifest_bytes_sha256": PREFLIGHT_MANIFEST_BYTES_SHA256,
                "projection_bytes_sha256": PREFLIGHT_PROJECTION_BYTES_SHA256,
                "zero_call_policy_bytes_sha256": ZERO_CALL_POLICY_BYTES_SHA256,
                "manifest_fingerprint_sha256": manifest["fingerprint_sha256"],
                "projection_fingerprint_sha256": projection["fingerprint_sha256"],
                "zero_call_policy_fingerprint_sha256": zero_policy[
                    "fingerprint_sha256"
                ],
            },
            "sources": _file_receipts(),
            "runtime": _runtime_contract(),
            "instructions_fingerprint_sha256": INSTRUCTIONS_FINGERPRINT,
            "response_schema_fingerprint_sha256": RESPONSE_SCHEMA_FINGERPRINT,
            "execution": {
                "provider_calls_authorized": 4,
                "exact_attempt_count": 4,
                "execution_order": list(EXPECTED_EXECUTION_ORDER),
                "call_schedule": call_schedule,
                "no_retry": True,
                "no_resume": True,
                "no_reorder": True,
                "no_backfill": True,
                "continue_after_structural_invalid_arm": True,
                "stop_after_integrity_guard_failure": True,
                "authorization_tag": EXECUTION_AUTHORIZATION_TAG,
                "authorization_requires_exact_head": True,
                "authorization_requires_origin_main_ancestry": True,
                "authorization_requires_preflight_anchor_ancestry": True,
                "gold_loaded_after_four_valid_compilations_only": True,
                "structural_invalid_block_status": "INCOMPLETE_NOT_ASSESSED",
                "positive_result": "PROMOTE_TO_FRESH_REPLICATION",
                "direct_v0_6_4_promotion_allowed": False,
            },
            "provider_visibility": {
                "only_raw_payload_sent": True,
                "sealed_payload_compiled_locally": True,
                "forbidden_metadata": sorted(core.FORBIDDEN_PROVIDER_KEYS),
            },
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
        raise UptakeLiveExecutionError(
            "live policy lock or locked source bytes drifted"
        )
    if lock.get("fingerprint_sha256") != fingerprint(
        {
            key: _clone(value)
            for key, value in lock.items()
            if key != "fingerprint_sha256"
        }
    ):
        raise UptakeLiveExecutionError("live policy fingerprint drifted")
    return lock


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
        raise UptakeLiveExecutionError(
            "git authorization boundary unavailable"
        ) from error
    return completed.stdout.strip()


def _git_bytes(*args: str) -> bytes:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=ROOT,
            check=True,
            capture_output=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise UptakeLiveExecutionError("git artifact boundary unavailable") from error
    return completed.stdout


def _load_authorized_lock(commit: str) -> dict[str, Any]:
    lock_path = str(LOCK_PATH.relative_to(ROOT))
    raw = _git_bytes("show", f"{commit}:{lock_path}")
    lock = _strict_json_bytes(raw, f"{commit}:{lock_path}")
    if (
        lock.get("schema_version") != LOCK_SCHEMA
        or lock.get("status") != "PREREGISTERED_EXACT_FOUR_CALL_LIVE_BLOCK"
        or lock.get("fingerprint_sha256")
        != fingerprint(
            {
                key: _clone(value)
                for key, value in lock.items()
                if key != "fingerprint_sha256"
            }
        )
    ):
        raise UptakeLiveExecutionError("authorized lock schema or fingerprint drifted")
    return lock


def _validate_authorized_source_blobs(
    lock: Mapping[str, Any], *, commit: str, include_gold: bool
) -> None:
    sources = lock.get("sources")
    if not isinstance(sources, Mapping) or set(sources) != set(SOURCE_PATHS):
        raise UptakeLiveExecutionError("authorized source receipt set drifted")
    for label, expected_path in SOURCE_PATHS.items():
        receipt = sources[label]
        if (
            not isinstance(receipt, Mapping)
            or set(receipt) != {"path", "bytes", "sha256"}
            or receipt.get("path") != expected_path
            or type(receipt.get("bytes")) is not int
            or int(receipt["bytes"]) <= 0
            or not _is_sha256(receipt.get("sha256"))
        ):
            raise UptakeLiveExecutionError("authorized source receipt invalid")
        if label == "post_call_gold" and not include_gold:
            continue
        raw = _git_bytes("show", f"{commit}:{expected_path}")
        if receipt != {
            "path": expected_path,
            "bytes": len(raw),
            "sha256": _sha256_bytes(raw),
        }:
            raise UptakeLiveExecutionError(
                f"authorized source blob differs from receipt: {label}"
            )


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
        raise UptakeLiveExecutionError(
            "git authorization boundary unavailable"
        ) from error
    if completed.returncode == 0:
        return True
    if completed.returncode == 1:
        return False
    raise UptakeLiveExecutionError("git authorization ref probe failed")


def _observe_authorization_tag(*, allow_pending: bool) -> dict[str, Any]:
    repository_root = Path(_git_text("rev-parse", "--show-toplevel")).resolve()
    if repository_root != ROOT:
        raise UptakeLiveExecutionError("execution repository root drifted")
    if (
        not _tag_ref_exists(PREFLIGHT_ANCHOR_TAG)
        or _git_text("rev-parse", "--verify", f"refs/tags/{PREFLIGHT_ANCHOR_TAG}")
        != PREFLIGHT_ANCHOR_TAG_OBJECT
        or _git_text("cat-file", "-t", PREFLIGHT_ANCHOR_TAG_OBJECT) != "tag"
        or _git_text("rev-parse", f"refs/tags/{PREFLIGHT_ANCHOR_TAG}^{{commit}}")
        != PREFLIGHT_ANCHOR_COMMIT
    ):
        raise UptakeLiveExecutionError("annotated preflight anchor tag drifted")
    if not _tag_ref_exists(EXECUTION_AUTHORIZATION_TAG):
        if allow_pending:
            return {
                "status": "PENDING_ANNOTATED_TAG",
                "tag_name": EXECUTION_AUTHORIZATION_TAG,
            }
        raise UptakeLiveExecutionError("execution authorization tag is unavailable")
    tag_object = _git_text(
        "rev-parse", "--verify", f"refs/tags/{EXECUTION_AUTHORIZATION_TAG}"
    )
    if not _is_git_oid(tag_object) or _git_text("cat-file", "-t", tag_object) != "tag":
        raise UptakeLiveExecutionError("execution authorization tag is not annotated")
    commit = _git_text(
        "rev-parse", f"refs/tags/{EXECUTION_AUTHORIZATION_TAG}^{{commit}}"
    )
    if not _is_git_oid(commit):
        raise UptakeLiveExecutionError("execution authorization commit is malformed")
    try:
        _git_text("merge-base", "--is-ancestor", commit, "refs/remotes/origin/main")
    except UptakeLiveExecutionError as error:
        raise UptakeLiveExecutionError(
            "authorized execution commit is not reachable from local origin/main"
        ) from error
    try:
        _git_text("merge-base", "--is-ancestor", PREFLIGHT_ANCHOR_COMMIT, commit)
    except UptakeLiveExecutionError as error:
        raise UptakeLiveExecutionError(
            "authorized execution commit does not descend from preflight anchor"
        ) from error
    return {
        "status": "AUTHORIZED_ANNOTATED_TAG",
        "tag_name": EXECUTION_AUTHORIZATION_TAG,
        "tag_object": tag_object,
        "authorized_commit": commit,
        "provenance_scope": "OPERATOR_ATTESTED_NOT_CRYPTOGRAPHICALLY_AUTHENTICATED",
    }


def _observe_execution_authorization(*, allow_pending: bool) -> dict[str, Any]:
    tag = _observe_authorization_tag(allow_pending=allow_pending)
    if tag.get("status") == "PENDING_ANNOTATED_TAG":
        return tag
    commit = tag["authorized_commit"]
    head = _git_text("rev-parse", "HEAD")
    if not _is_git_oid(head) or head != commit:
        raise UptakeLiveExecutionError(
            "live execution HEAD is not exact authorized commit"
        )
    locked_paths = [
        receipt_path
        for label, receipt_path in SOURCE_PATHS.items()
        if label != "post_call_gold"
    ] + [str(LOCK_PATH.relative_to(ROOT))]
    try:
        _git_text("ls-files", "--error-unmatch", "--", *locked_paths)
        _git_text("diff", "--quiet", commit, "--", *locked_paths)
    except UptakeLiveExecutionError as error:
        raise UptakeLiveExecutionError(
            "authorized execution sources are untracked or dirty"
        ) from error
    return {
        **tag,
        "execution_head_commit": head,
        "head_matches_authorized_commit": True,
    }


def _validate_recorded_execution_authorization(
    authorization: Mapping[str, Any],
    *,
    observer: Callable[..., Mapping[str, Any]] = _observe_authorization_tag,
) -> None:
    if (
        set(authorization)
        != {
            "status",
            "tag_name",
            "tag_object",
            "authorized_commit",
            "execution_head_commit",
            "head_matches_authorized_commit",
            "provenance_scope",
        }
        or authorization.get("status") != "AUTHORIZED_ANNOTATED_TAG"
        or authorization.get("tag_name") != EXECUTION_AUTHORIZATION_TAG
        or authorization.get("head_matches_authorized_commit") is not True
        or authorization.get("authorized_commit")
        != authorization.get("execution_head_commit")
        or authorization.get("provenance_scope")
        != "OPERATOR_ATTESTED_NOT_CRYPTOGRAPHICALLY_AUTHENTICATED"
    ):
        raise UptakeLiveExecutionError("recorded execution authorization invalid")
    observed = observer(allow_pending=False)
    if (
        observed["tag_object"] != authorization["tag_object"]
        or observed["authorized_commit"] != authorization["authorized_commit"]
    ):
        raise UptakeLiveExecutionError("execution authorization tag drifted")


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
    raw_payload: Mapping[str, Any],
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
        raise UptakeLiveExecutionError("provider receipt schema drifted")
    if (
        receipt["provider"] != "openai_responses"
        or receipt["requested_model"] != MODEL
        or type(receipt["logical_calls"]) is not int
        or receipt["logical_calls"] != 1
        or type(receipt["api_calls"]) is not int
        or receipt["api_calls"] != 1
        or receipt["request_fingerprint"] != fingerprint(raw_payload)
        or receipt["prompt_fingerprint"] != INSTRUCTIONS_FINGERPRINT
        or not isinstance(receipt["latency_ms"], (int, float))
        or isinstance(receipt["latency_ms"], bool)
        or not math.isfinite(float(receipt["latency_ms"]))
        or float(receipt["latency_ms"]) < 0.0
    ):
        raise UptakeLiveExecutionError("provider receipt binding drifted")

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
            "model": MODEL,
            "instructions_fingerprint": INSTRUCTIONS_FINGERPRINT,
            "input_fingerprint": fingerprint(raw_payload),
            "text_schema_fingerprint": RESPONSE_SCHEMA_FINGERPRINT,
            "reasoning": {"effort": REASONING_EFFORT},
            "max_output_tokens": MAX_OUTPUT_TOKENS,
            "store": False,
            "service_tier": "default",
            "truncation": "disabled",
            "timeout_seconds": float(TIMEOUT_SECONDS),
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
        or metadata.get("reasoning_effort") != REASONING_EFFORT
        or metadata.get("max_output_tokens") != MAX_OUTPUT_TOKENS
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
        raise UptakeLiveExecutionError("provider receipt runtime drifted")
    for key in (
        "response_id_sha256",
        "server_request_id_sha256",
        "provider_body_sha256",
    ):
        if metadata.get(key) is not None and not _is_sha256(metadata.get(key)):
            raise UptakeLiveExecutionError("provider receipt digest drifted")
    if metadata.get("provider_body_byte_count") is not None and (
        type(metadata.get("provider_body_byte_count")) is not int
        or int(metadata["provider_body_byte_count"]) < 0
    ):
        raise UptakeLiveExecutionError("provider body byte count drifted")

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
        raise UptakeLiveExecutionError("provider usage missing")
    if provider_completed:
        if (
            receipt["returned_model"] != MODEL
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
            or type(metadata.get("provider_body_byte_count")) is not int
            or int(metadata["provider_body_byte_count"]) <= 0
            or metadata.get("failure_phase") is not None
            or metadata.get("failure_reason_code") is not None
            or metadata.get("failure_type") is not None
            or metadata.get("refusal_count") != 0
        ):
            raise UptakeLiveExecutionError("completed receipt contract drifted")
    else:
        if not isinstance(failure, Mapping) or set(failure) != {
            "category",
            "exception_class",
            "phase",
            "reason_code",
        }:
            raise UptakeLiveExecutionError("provider failure record drifted")
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
            raise UptakeLiveExecutionError("provider failure/receipt mismatch")
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
            raise UptakeLiveExecutionError("provider failure status drifted")
    for key, value in usage.items():
        if key == "exact_provider_tokens":
            continue
        if value is not None and (
            not isinstance(value, int) or isinstance(value, bool) or value < 0
        ):
            raise UptakeLiveExecutionError("provider usage value drifted")
    token_keys = usage_keys - {"exact_provider_tokens"}
    if usage["exact_provider_tokens"] is True:
        if any(type(usage[key]) is not int for key in token_keys):
            raise UptakeLiveExecutionError("exact provider usage is incomplete")
        if usage["total_tokens"] != usage["input_tokens"] + usage["output_tokens"]:
            raise UptakeLiveExecutionError("exact provider usage total drifted")
        if (
            usage["cached_input_tokens"] > usage["input_tokens"]
            or usage["reasoning_tokens"] > usage["output_tokens"]
        ):
            raise UptakeLiveExecutionError("exact provider usage detail drifted")
    elif usage["exact_provider_tokens"] is False:
        if any(usage[key] is not None for key in token_keys):
            raise UptakeLiveExecutionError("inexact provider usage retained tokens")
    else:
        raise UptakeLiveExecutionError("provider usage exactness flag drifted")


def _validate_live_receipt(
    provider: Any,
    receipt: Mapping[str, Any],
    raw_payload: Mapping[str, Any],
    *,
    provider_completed: bool,
    failure: Mapping[str, Any] | None,
) -> None:
    if provider.audit_receipts != [_clone(receipt)]:
        raise UptakeLiveExecutionError("provider audit receipt differs from return")
    _validate_receipt(
        receipt,
        raw_payload,
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
        payload_fingerprint = row["sealed_payload"]["fingerprint_sha256"]
    return {
        "schema_version": JOURNAL_SCHEMA,
        "event": "ATTEMPT_STARTED",
        "sequence_index": row["sequence_index"],
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
        blind_id = attempt["blinded_request_id"]
        rows.append(_started_journal_row(attempt))
        rows.append(
            _terminal_journal_row(
                attempt,
                provider_output=outputs.get(blind_id),
                compiled_output=compiled.get(blind_id),
            )
        )
    return b"".join(_canonical_bytes(row, trailing_newline=True) for row in rows)


def _assert_journal_prefix(path: Path, expected: bytes) -> None:
    if path.is_symlink() or not path.is_file() or path.read_bytes() != expected:
        raise UptakeLiveExecutionError("durable attempt journal prefix drifted")


def _freeze_guard_failure(
    journal_path: Path,
    *,
    row: Mapping[str, Any] | None,
    phase: str,
) -> None:
    _append_journal(
        journal_path,
        {
            "schema_version": JOURNAL_SCHEMA,
            "event": "IRRECOVERABLE_GUARD_FAILURE",
            "sequence_index": None if row is None else row["sequence_index"],
            "blinded_request_id": None if row is None else row["blinded_request_id"],
            "phase": phase,
            "failure": {
                "category": "local_integrity_guard_error",
                "reason_code": "attempt_burned_no_resume",
            },
        },
    )


def _attempt_identity(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "sequence_index": row["sequence_index"],
        "blinded_request_id": row["blinded_request_id"],
        "treatment_id": row["treatment_id"],
    }


def _validate_pre_call_row(
    row: Mapping[str, Any], *, material: Mapping[str, Any]
) -> None:
    sequence_index = row["sequence_index"]
    expected = material["attempts"][sequence_index - 1]
    if _attempt_identity(row) != _attempt_identity(expected):
        raise UptakeLiveExecutionError("attempt row identity drifted")
    sealed = row["sealed_payload"]
    raw = row["raw_payload"]
    core._validate_fingerprint(sealed, "pre-call sealed payload")
    if core._unseal(sealed, "pre-call sealed payload") != raw:
        raise UptakeLiveExecutionError("pre-call raw/sealed payload drifted")
    audit = core.validate_provider_payload(raw, case=material["case"])
    if audit["payload_fingerprint_sha256"] != sealed["fingerprint_sha256"]:
        raise UptakeLiveExecutionError("pre-call provider payload fingerprint drifted")


ProviderFactory = Callable[[Mapping[str, Any], Mapping[str, Any]], Any]
SourceGuard = Callable[[], None]


def _execute_gold_free(
    material: Mapping[str, Any],
    *,
    journal_path: Path,
    provider_factory: ProviderFactory | None = None,
    source_guard: SourceGuard | None = None,
) -> dict[str, Any]:
    """Attempt all four arms unless an integrity guard burns the namespace."""

    rows = material["attempts"]
    if (
        len(rows) != 4
        or tuple(row["treatment_id"] for row in rows) != EXPECTED_EXECUTION_ORDER
    ):
        raise UptakeLiveExecutionError("live attempt schedule drifted")
    if provider_factory is None:

        def provider_factory(case: Mapping[str, Any], _row: Mapping[str, Any]) -> Any:
            return OpenAIUptakeProviderLiveR01(case=case)

    if source_guard is None:

        def source_guard() -> None:
            return None

    providers = [provider_factory(material["case"], row) for row in rows]
    if len(providers) != 4 or any(provider.audit_receipts for provider in providers):
        raise UptakeLiveExecutionError("provider pre-call audit state is not empty")

    attempts: list[dict[str, Any]] = []
    provider_outputs: dict[str, dict[str, Any]] = {}
    compiled_outputs: dict[str, dict[str, Any]] = {}
    expected_journal = b""

    for row, provider in zip(rows, providers, strict=True):
        try:
            source_guard()
            _assert_journal_prefix(journal_path, expected_journal)
            if provider.audit_receipts:
                raise UptakeLiveExecutionError("provider audit state nonempty pre-call")
            _validate_pre_call_row(row, material=material)
        except Exception:
            _freeze_guard_failure(journal_path, row=row, phase="pre_call_integrity")
            raise UptakeLiveExecutionError(
                "pre-call integrity guard failed; in-flight namespace frozen"
            ) from None

        start = _started_journal_row(row)
        _append_journal(journal_path, start)
        expected_journal += _canonical_bytes(start, trailing_newline=True)
        try:
            _assert_journal_prefix(journal_path, expected_journal)
        except Exception:
            _freeze_guard_failure(journal_path, row=row, phase="pre_call_journal")
            raise UptakeLiveExecutionError(
                "journal guard failed before provider call; namespace frozen"
            ) from None

        raw_payload = row["raw_payload"]
        sealed_payload = row["sealed_payload"]
        blind_id = row["blinded_request_id"]
        try:
            public_output, receipt = provider.generate(raw_payload)
        except OpenAIProviderBoundaryError as error:
            receipt_value = _receipt_from_error(error)
            if receipt_value is None:
                _freeze_guard_failure(
                    journal_path, row=row, phase="missing_provider_failure_receipt"
                )
                raise UptakeLiveExecutionError(
                    "provider boundary failure omitted receipt; namespace frozen"
                ) from None
            failure = _failure_record(error)
            try:
                _validate_live_receipt(
                    provider,
                    receipt_value,
                    raw_payload,
                    provider_completed=False,
                    failure=failure,
                )
                source_guard()
            except Exception:
                _freeze_guard_failure(
                    journal_path,
                    row=row,
                    phase="post_call_receipt_or_source",
                )
                raise UptakeLiveExecutionError(
                    "post-call receipt guard failed; in-flight namespace frozen"
                ) from None
            attempt = {
                **_attempt_identity(row),
                "provider_input_fingerprint_sha256": sealed_payload[
                    "fingerprint_sha256"
                ],
                "receipt": receipt_value,
                "failure": failure,
                "status": "PROVIDER_BOUNDARY_ERROR",
            }
            attempts.append(attempt)
            terminal = _terminal_journal_row(
                attempt, provider_output=None, compiled_output=None
            )
            _append_journal(journal_path, terminal)
            expected_journal += _canonical_bytes(terminal, trailing_newline=True)
            _assert_journal_prefix(journal_path, expected_journal)
            continue
        except Exception:
            _freeze_guard_failure(
                journal_path, row=row, phase="unexpected_provider_exception"
            )
            raise UptakeLiveExecutionError(
                "unexpected provider exception; in-flight namespace frozen"
            ) from None

        receipt_value = receipt.to_dict()
        try:
            _validate_live_receipt(
                provider,
                receipt_value,
                raw_payload,
                provider_completed=True,
                failure=None,
            )
            source_guard()
        except Exception:
            _freeze_guard_failure(
                journal_path,
                row=row,
                phase="post_call_receipt_or_source",
            )
            raise UptakeLiveExecutionError(
                "post-call receipt guard failed; in-flight namespace frozen"
            ) from None

        public_output_value = _clone(public_output)
        provider_outputs[blind_id] = public_output_value
        try:
            compiled = core.compile_public_output(
                public_output_value,
                payload=sealed_payload,
                case=material["case"],
            )
            core.validate_compiled_output(
                compiled,
                fixture=material["fixture"],
                expected_payload=sealed_payload,
            )
        except core.UptakeCanaryError as error:
            if error.reason_code not in OUTPUT_STRUCTURAL_REASON_CODES:
                _freeze_guard_failure(
                    journal_path,
                    row=row,
                    phase="non_output_core_invariant_failure",
                )
                raise UptakeLiveExecutionError(
                    "non-output core invariant failed; in-flight namespace frozen"
                ) from None
            failure = _failure_record(error)
            attempt = {
                **_attempt_identity(row),
                "provider_input_fingerprint_sha256": sealed_payload[
                    "fingerprint_sha256"
                ],
                "provider_output_fingerprint_sha256": fingerprint(public_output_value),
                "receipt": receipt_value,
                "failure": failure,
                "status": "LOCAL_OUTPUT_CONTRACT_ERROR",
            }
            attempts.append(attempt)
            terminal = _terminal_journal_row(
                attempt,
                provider_output=public_output_value,
                compiled_output=None,
            )
            _append_journal(journal_path, terminal)
            expected_journal += _canonical_bytes(terminal, trailing_newline=True)
            _assert_journal_prefix(journal_path, expected_journal)
            continue
        except Exception:
            _freeze_guard_failure(
                journal_path, row=row, phase="unexpected_local_compiler_exception"
            )
            raise UptakeLiveExecutionError(
                "unexpected local compiler exception; in-flight namespace frozen"
            ) from None

        compiled_value = _clone(compiled)
        compiled_outputs[blind_id] = compiled_value
        attempt = {
            **_attempt_identity(row),
            "provider_input_fingerprint_sha256": sealed_payload["fingerprint_sha256"],
            "provider_output_fingerprint_sha256": fingerprint(public_output_value),
            "compiled_output_fingerprint_sha256": compiled_value["fingerprint_sha256"],
            "receipt": receipt_value,
            "failure": None,
            "status": "COMPLETED",
        }
        attempts.append(attempt)
        terminal = _terminal_journal_row(
            attempt,
            provider_output=public_output_value,
            compiled_output=compiled_value,
        )
        _append_journal(journal_path, terminal)
        expected_journal += _canonical_bytes(terminal, trailing_newline=True)
        _assert_journal_prefix(journal_path, expected_journal)

    if len(attempts) != 4:
        raise UptakeLiveExecutionError("four-call loop did not reach four terminals")
    invalid_ids = [
        row["blinded_request_id"] for row in attempts if row["status"] != "COMPLETED"
    ]
    return {
        "attempts": attempts,
        "provider_outputs": provider_outputs,
        "compiled_outputs": compiled_outputs,
        "attempt_block_status": "COMPLETE_EXACT_FOUR_TERMINALS",
        "assessment_status": (
            "READY_FOR_POST_CALL_GOLD" if not invalid_ids else "INCOMPLETE_NOT_ASSESSED"
        ),
        "invalid_blinded_request_ids": invalid_ids,
        "unattempted_blinded_request_ids": [],
    }


def _validate_execution(
    execution: Mapping[str, Any], material: Mapping[str, Any]
) -> None:
    if set(execution) != {
        "attempts",
        "provider_outputs",
        "compiled_outputs",
        "attempt_block_status",
        "assessment_status",
        "invalid_blinded_request_ids",
        "unattempted_blinded_request_ids",
    }:
        raise UptakeLiveExecutionError("execution schema drifted")
    attempts = execution["attempts"]
    if not isinstance(attempts, list) or len(attempts) != 4:
        raise UptakeLiveExecutionError("execution does not contain four terminals")
    schedule = material["attempts"]
    if [_attempt_identity(row) for row in attempts] != [
        _attempt_identity(row) for row in schedule
    ]:
        raise UptakeLiveExecutionError("attempt order or identity drifted")
    if execution["attempt_block_status"] != "COMPLETE_EXACT_FOUR_TERMINALS":
        raise UptakeLiveExecutionError("attempt block terminal status drifted")
    if execution["unattempted_blinded_request_ids"] != []:
        raise UptakeLiveExecutionError(
            "completed attempt block retained unattempted arms"
        )
    allowed_statuses = {
        "COMPLETED",
        "PROVIDER_BOUNDARY_ERROR",
        "LOCAL_OUTPUT_CONTRACT_ERROR",
    }
    if any(row.get("status") not in allowed_statuses for row in attempts):
        raise UptakeLiveExecutionError("attempt status unknown")

    outputs = execution["provider_outputs"]
    compiled = execution["compiled_outputs"]
    if not isinstance(outputs, dict) or not isinstance(compiled, dict):
        raise UptakeLiveExecutionError("execution output maps malformed")
    observed_output_ids: set[str] = set()
    observed_compiled_ids: set[str] = set()
    for attempt, scheduled in zip(attempts, schedule, strict=True):
        blind_id = scheduled["blinded_request_id"]
        raw_payload = scheduled["raw_payload"]
        sealed_payload = scheduled["sealed_payload"]
        if (
            attempt.get("provider_input_fingerprint_sha256")
            != sealed_payload["fingerprint_sha256"]
        ):
            raise UptakeLiveExecutionError("attempt provider input binding drifted")
        status = attempt["status"]
        failure = attempt.get("failure")
        base_keys = {
            "sequence_index",
            "blinded_request_id",
            "treatment_id",
            "provider_input_fingerprint_sha256",
            "receipt",
            "failure",
            "status",
        }
        expected_keys = (
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
        if set(attempt) != expected_keys:
            raise UptakeLiveExecutionError("attempt schema drifted")
        provider_completed = status != "PROVIDER_BOUNDARY_ERROR"
        _validate_receipt(
            attempt["receipt"],
            raw_payload,
            provider_completed=provider_completed,
            failure=failure if not provider_completed else None,
        )
        if status == "PROVIDER_BOUNDARY_ERROR":
            if blind_id in outputs or blind_id in compiled or failure is None:
                raise UptakeLiveExecutionError("provider failure retained output")
            continue
        output = outputs.get(blind_id)
        if not isinstance(output, dict):
            raise UptakeLiveExecutionError("provider-completed output missing")
        observed_output_ids.add(blind_id)
        if attempt["provider_output_fingerprint_sha256"] != fingerprint(output):
            raise UptakeLiveExecutionError("provider output fingerprint drifted")
        if status == "LOCAL_OUTPUT_CONTRACT_ERROR":
            if blind_id in compiled or failure is None:
                raise UptakeLiveExecutionError("rejected output retained compilation")
            try:
                core.compile_public_output(
                    output, payload=sealed_payload, case=material["case"]
                )
            except core.UptakeCanaryError as error:
                if (
                    error.reason_code not in OUTPUT_STRUCTURAL_REASON_CODES
                    or _failure_record(error) != failure
                ):
                    raise UptakeLiveExecutionError(
                        "local output failure reason drifted"
                    ) from error
            else:
                raise UptakeLiveExecutionError("rejected output now compiles")
            continue
        if failure is not None:
            raise UptakeLiveExecutionError("completed output retained failure")
        expected_compiled = core.compile_public_output(
            output, payload=sealed_payload, case=material["case"]
        )
        core.validate_compiled_output(
            expected_compiled,
            fixture=material["fixture"],
            expected_payload=sealed_payload,
        )
        observed_compiled = compiled.get(blind_id)
        if observed_compiled != expected_compiled:
            raise UptakeLiveExecutionError("compiled output differs from recompile")
        if (
            attempt["compiled_output_fingerprint_sha256"]
            != observed_compiled["fingerprint_sha256"]
        ):
            raise UptakeLiveExecutionError("compiled output fingerprint drifted")
        observed_compiled_ids.add(blind_id)

    if set(outputs) != observed_output_ids or set(compiled) != observed_compiled_ids:
        raise UptakeLiveExecutionError("execution output key set drifted")
    invalid_ids = [
        row["blinded_request_id"] for row in attempts if row["status"] != "COMPLETED"
    ]
    if execution["invalid_blinded_request_ids"] != invalid_ids:
        raise UptakeLiveExecutionError("invalid arm ledger drifted")
    expected_assessment = (
        "READY_FOR_POST_CALL_GOLD" if not invalid_ids else "INCOMPLETE_NOT_ASSESSED"
    )
    if execution["assessment_status"] != expected_assessment:
        raise UptakeLiveExecutionError("execution assessment readiness drifted")


def _incomplete_decision(execution: Mapping[str, Any]) -> dict[str, Any]:
    arm_by_blind = {
        row["blinded_request_id"]: row["treatment_id"] for row in execution["attempts"]
    }
    return _seal(
        {
            "schema_version": "ebrt-actuator-uptake-decision-v0.6.3.1",
            "assessment_status": "INCOMPLETE",
            "positive_control_status": "NOT_ASSESSED",
            "gradient_placement_status": "NOT_ASSESSED",
            "terminal_decision": "INCOMPLETE_NOT_ASSESSED",
            "invalid_arms": sorted(
                arm_by_blind[item] for item in execution["invalid_blinded_request_ids"]
            ),
            "direct_v0_6_4_promotion_allowed": False,
        }
    )


def _load_post_call_gold(
    lock: Mapping[str, Any], fixture: Mapping[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """The only semantic-gold byte read in a valid live finalization."""

    raw = core.GOLD_PATH.read_bytes()
    receipt = {
        "path": str(core.GOLD_PATH.relative_to(ROOT)),
        "bytes": len(raw),
        "sha256": _sha256_bytes(raw),
    }
    if receipt != lock["sources"]["post_call_gold"]:
        raise UptakeLiveExecutionError("post-call semantic gold bytes drifted")
    gold = _strict_json_bytes(raw, "post-call semantic gold")
    core.validate_gold(gold, fixture)
    return gold, receipt


def _load_post_call_gold_at_commit(
    lock: Mapping[str, Any], fixture: Mapping[str, Any], *, commit: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    expected = lock["sources"]["post_call_gold"]
    raw = _git_bytes("show", f"{commit}:{expected['path']}")
    receipt = {
        "path": expected["path"],
        "bytes": len(raw),
        "sha256": _sha256_bytes(raw),
    }
    if receipt != expected:
        raise UptakeLiveExecutionError("authorized post-call gold blob drifted")
    gold = _strict_json_bytes(raw, "authorized post-call semantic gold")
    core.validate_gold(gold, fixture)
    return gold, receipt


GoldLoader = Callable[[], tuple[Any, dict[str, Any]]]
Classifier = Callable[..., dict[str, Any]]


def _classify_after_execution(
    execution: Mapping[str, Any],
    *,
    material: Mapping[str, Any],
    gold_loader: GoldLoader,
    classifier: Classifier,
) -> tuple[dict[str, Any], dict[str, Any], Any | None]:
    """Keep gold and the classifier unreachable until four valid terminals exist."""

    _validate_execution(execution, material)
    if execution["assessment_status"] != "READY_FOR_POST_CALL_GOLD":
        return (
            _incomplete_decision(execution),
            {
                "loaded": False,
                "classification_load_count": 0,
                "observed_receipt": None,
            },
            None,
        )
    if (
        len(execution["attempts"]) != 4
        or any(row["status"] != "COMPLETED" for row in execution["attempts"])
        or len(execution["compiled_outputs"]) != 4
    ):
        raise UptakeLiveExecutionError("gold gate reached without four valid outputs")
    gold, receipt = gold_loader()
    compiled_by_arm = {
        row["treatment_id"]: execution["compiled_outputs"][row["blinded_request_id"]]
        for row in execution["attempts"]
    }
    decision = classifier(
        compiled_by_arm,
        gold=gold,
        fixture=material["fixture"],
    )
    if (
        not isinstance(decision, Mapping)
        or not _is_sha256(decision.get("fingerprint_sha256"))
        or decision.get("assessment_status") != "ASSESSED"
        or decision.get("direct_v0_6_4_promotion_allowed") is not False
    ):
        raise UptakeLiveExecutionError("post-call classifier result invalid")
    return (
        _clone(decision),
        {
            "loaded": True,
            "classification_load_count": 1,
            "observed_receipt": _clone(receipt),
        },
        gold,
    )


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


def _assemble_result(
    execution: Mapping[str, Any],
    *,
    material: Mapping[str, Any],
    preflight_value: Mapping[str, Any],
    source_snapshot: Mapping[str, str],
    lock: Mapping[str, Any],
    decision: Mapping[str, Any],
    gold_audit: Mapping[str, Any],
) -> dict[str, Any]:
    _validate_execution(execution, material)
    result = {
        "schema_version": RESULT_SCHEMA,
        "mode": "openai_live_actuator_uptake_canary_v0_6_3_1_r01",
        "claim_boundary": list(CLAIM_BOUNDARY),
        "preflight_anchor_tag_object": PREFLIGHT_ANCHOR_TAG_OBJECT,
        "preflight_anchor_commit": PREFLIGHT_ANCHOR_COMMIT,
        "policy_lock_fingerprint_sha256": lock["fingerprint_sha256"],
        "projection_fingerprint_sha256": material["projection"]["fingerprint_sha256"],
        "preflight": _clone(preflight_value),
        "source_snapshot_sha256": dict(source_snapshot),
        "execution": _clone(execution),
        "semantic_gold": _clone(gold_audit),
        "decision": _clone(decision),
        "direct_v0_6_4_promotion_allowed": False,
        "usage": _usage_summary(execution["attempts"]),
    }
    return _seal(result)


def _finalize(
    execution: Mapping[str, Any],
    *,
    material: Mapping[str, Any],
    preflight_value: Mapping[str, Any],
    source_snapshot: Mapping[str, str],
    lock: Mapping[str, Any],
) -> tuple[dict[str, Any], Any | None]:
    decision, gold_audit, in_memory_gold = _classify_after_execution(
        execution,
        material=material,
        gold_loader=lambda: _load_post_call_gold(lock, material["fixture"]),
        classifier=core.classify_canary,
    )
    return (
        _assemble_result(
            execution,
            material=material,
            preflight_value=preflight_value,
            source_snapshot=source_snapshot,
            lock=lock,
            decision=decision,
            gold_audit=gold_audit,
        ),
        in_memory_gold,
    )


def _fake_output(row: Mapping[str, Any], closure_id: str) -> dict[str, Any]:
    return core._fake_output(closure_id, payload=row["sealed_payload"])


class _DictReceipt:
    def __init__(self, value: Mapping[str, Any]) -> None:
        self._value = _clone(value)

    def to_dict(self) -> dict[str, Any]:
        return _clone(self._value)


class _TamperedReceiptProvider:
    def __init__(self, inner: OpenAIUptakeProviderLiveR01) -> None:
        self.inner = inner
        self.audit_receipts: list[dict[str, Any]] = []

    def generate(
        self, payload: Mapping[str, Any]
    ) -> tuple[dict[str, Any], _DictReceipt]:
        output, receipt = self.inner.generate(payload)
        value = receipt.to_dict()
        value["request_fingerprint"] = "0" * 64
        self.audit_receipts = [_clone(value)]
        return output, _DictReceipt(value)


def _fake_provider_factory(
    outputs_by_arm: Mapping[str, Mapping[str, Any]],
    *,
    endpoint_log: list[_FakeRawParseEndpoint],
    tamper_arm: str | None = None,
) -> ProviderFactory:
    def factory(case: Mapping[str, Any], row: Mapping[str, Any]) -> Any:
        parsed = core.UptakeProviderOutput.model_validate(
            outputs_by_arm[row["treatment_id"]]
        )
        client = _FakeOpenAIClient(parsed)
        endpoint_log.append(client.endpoint)
        provider = OpenAIUptakeProviderLiveR01(case=case, client=client)
        return (
            _TamperedReceiptProvider(provider)
            if row["treatment_id"] == tamper_arm
            else provider
        )

    return factory


def _fake_assessed_classifier(
    compiled_outputs: Mapping[str, Mapping[str, Any]],
    *,
    gold: Any,
    fixture: Mapping[str, Any],
) -> dict[str, Any]:
    del gold, fixture
    if set(compiled_outputs) != set(core.ARMS):
        raise UptakeLiveExecutionError("offline classifier arm set drifted")
    return _seal(
        {
            "schema_version": "ebrt-actuator-uptake-decision-v0.6.3.1",
            "assessment_status": "ASSESSED",
            "positive_control_status": "ACTUATOR_CHANNEL_INERT",
            "gradient_placement_status": "GRADIENT_PLACEMENT_NULL",
            "terminal_decision": "STOP_CHANNEL_INERT",
            "selected_closure_by_arm": {
                arm: compiled_outputs[arm]["selected_closure_id"] for arm in core.ARMS
            },
            "endpoint_fingerprint_by_arm": {
                arm: compiled_outputs[arm]["fingerprint_sha256"] for arm in core.ARMS
            },
            "invalid_arms": [],
            "direct_v0_6_4_promotion_allowed": False,
            "claim_boundary": list(DECISION_CLAIM_BOUNDARY),
        }
    )


def _run_fake_block(
    material: Mapping[str, Any],
    outputs_by_arm: Mapping[str, Mapping[str, Any]],
    *,
    tamper_arm: str | None = None,
) -> tuple[dict[str, Any] | None, bytes, list[_FakeRawParseEndpoint], Exception | None]:
    endpoints: list[_FakeRawParseEndpoint] = []
    execution: dict[str, Any] | None = None
    caught: Exception | None = None
    with tempfile.TemporaryDirectory(prefix="ebrt-v0631-live-block-test-") as directory:
        journal = Path(directory) / "attempt_journal.jsonl"
        journal.touch(mode=0o600)
        try:
            execution = _execute_gold_free(
                material,
                journal_path=journal,
                provider_factory=_fake_provider_factory(
                    outputs_by_arm,
                    endpoint_log=endpoints,
                    tamper_arm=tamper_arm,
                ),
            )
        except Exception as error:
            caught = error
        journal_bytes = journal.read_bytes()
    return execution, journal_bytes, endpoints, caught


def _offline_preflight_record(
    *,
    lock: Mapping[str, Any],
    material: Mapping[str, Any],
    source_snapshot: Mapping[str, str],
) -> dict[str, Any]:
    component_stub = _seal(
        {
            "schema_version": "ebrt-actuator-uptake-live-component-self-test-v0.6.3.1-r01",
            "status": "PASS_NETWORK_ZERO",
            "checks": {"offline_artifact_fixture": True},
            "provider_calls": 0,
            "network_calls": 0,
            "simulated_api_calls": 0,
        }
    )
    return _seal(
        {
            "schema_version": "ebrt-actuator-uptake-live-preflight-v0.6.3.1-r01",
            "status": "OFFLINE_SELF_TEST",
            "expected_api_attempts": 4,
            "execution_order": list(EXPECTED_EXECUTION_ORDER),
            "call_order_blinded_request_ids": [
                row["blinded_request_id"] for row in material["attempts"]
            ],
            "payload_fingerprints": {
                row["blinded_request_id"]: row["sealed_payload"]["fingerprint_sha256"]
                for row in material["attempts"]
            },
            "projection_fingerprint_sha256": material["projection"][
                "fingerprint_sha256"
            ],
            "policy_lock_fingerprint_sha256": lock["fingerprint_sha256"],
            "provider": _expected_provider_provenance(),
            "component_self_test": component_stub,
            "execution_authorization": {
                "status": "OFFLINE_SELF_TEST",
                "tag_name": EXECUTION_AUTHORIZATION_TAG,
            },
            "source_snapshot_sha256": dict(source_snapshot),
            "post_call_gold_expected_receipt": _clone(
                lock["sources"]["post_call_gold"]
            ),
            "gold_loaded": False,
            "provider_calls": 0,
            "network_calls": 0,
        }
    )


def _provider_transport_self_test(material: Mapping[str, Any]) -> dict[str, Any]:
    row = material["attempts"][0]
    closure_id = material["case"]["candidate_closures"][0]["closure_id"]
    output = _fake_output(row, closure_id)
    parsed = core.UptakeProviderOutput.model_validate(output)
    fake = _FakeOpenAIClient(parsed)
    provider = OpenAIUptakeProviderLiveR01(case=material["case"], client=fake)
    public_output, receipt = provider.generate(row["raw_payload"])
    receipt_value = receipt.to_dict()
    _validate_live_receipt(
        provider,
        receipt_value,
        row["raw_payload"],
        provider_completed=True,
        failure=None,
    )
    call = fake.endpoint.calls[0] if len(fake.endpoint.calls) == 1 else {}
    sent = json.loads(call.get("input", "{}"))
    checks = {
        "one_fake_transport_call": len(fake.endpoint.calls) == 1,
        "exact_public_output_roundtrip": public_output == output,
        "raw_payload_sent_without_seal": "fingerprint_sha256" not in sent
        and sent == row["raw_payload"],
        "request_receipt_matches_sealed_fingerprint": receipt_value[
            "request_fingerprint"
        ]
        == row["sealed_payload"]["fingerprint_sha256"],
        "provider_metadata_absent": not (
            core._recursive_keys(sent) & core.FORBIDDEN_PROVIDER_KEYS
        ),
        "runtime_arguments_pinned": (
            call.get("model") == MODEL
            and call.get("instructions") == PROVIDER_INSTRUCTIONS
            and call.get("reasoning") == {"effort": REASONING_EFFORT}
            and call.get("max_output_tokens") == MAX_OUTPUT_TOKENS
            and call.get("store") is False
            and call.get("service_tier") == "default"
            and call.get("truncation") == "disabled"
            and call.get("timeout") == float(TIMEOUT_SECONDS)
            and call.get("text_format") is core.UptakeProviderOutput
            and set(call.get("extra_headers", {})) == {"X-Client-Request-Id"}
        ),
    }
    if not all(checks.values()):
        raise UptakeLiveExecutionError("offline provider transport self-test failed")
    return _seal(
        {
            "schema_version": "ebrt-actuator-uptake-provider-self-test-v0.6.3.1-r01",
            "status": "PASS",
            "checks": checks,
            "provider_calls": 0,
            "simulated_api_calls": 1,
        }
    )


def component_self_test() -> dict[str, Any]:
    with _network_denied() as network_counts, _semantic_gold_denied() as gold_counts:
        material = _materialize_projection()
        transport = _provider_transport_self_test(material)
        candidates = material["case"]["candidate_closures"]
        default_id = candidates[0]["closure_id"]
        event = material["case"]["public_event_contract"]
        stale_id = next(
            row["closure_id"]
            for row in candidates
            if event["invalidated_evidence_id"] in row["selected_evidence_ids"]
            and event["late_event_evidence_id"] not in row["selected_evidence_ids"]
        )
        default_outputs = {
            row["treatment_id"]: _fake_output(row, default_id)
            for row in material["attempts"]
        }

        success, success_journal, success_endpoints, success_error = _run_fake_block(
            material, default_outputs
        )
        if success is None:
            raise UptakeLiveExecutionError(
                "offline success block failed"
            ) from success_error
        _validate_execution(success, material)
        load_counts = {"gold": 0, "classifier": 0}

        def fake_loader() -> tuple[Any, dict[str, Any]]:
            load_counts["gold"] += 1
            return object(), {"path": "offline", "bytes": 1, "sha256": "1" * 64}

        def counted_classifier(*args: Any, **kwargs: Any) -> dict[str, Any]:
            load_counts["classifier"] += 1
            return _fake_assessed_classifier(*args, **kwargs)

        success_decision, success_gold, _success_gold_value = _classify_after_execution(
            success,
            material=material,
            gold_loader=fake_loader,
            classifier=counted_classifier,
        )

        stale_outputs = dict(default_outputs)
        stale_outputs["C"] = _fake_output(material["attempts"][0], stale_id)
        stale, stale_journal, stale_endpoints, stale_error = _run_fake_block(
            material, stale_outputs
        )
        if stale is None:
            raise UptakeLiveExecutionError(
                "offline stale endpoint block failed"
            ) from stale_error
        _validate_execution(stale, material)
        stale_decision, stale_gold, _stale_gold_value = _classify_after_execution(
            stale,
            material=material,
            gold_loader=fake_loader,
            classifier=counted_classifier,
        )

        invalid_outputs = dict(default_outputs)
        invalid_outputs["X"] = {
            **invalid_outputs["X"],
            "selected_closure_id": "K_unknown_structural_canary",
        }
        invalid, invalid_journal, invalid_endpoints, invalid_error = _run_fake_block(
            material, invalid_outputs
        )
        if invalid is None:
            raise UptakeLiveExecutionError(
                "offline structural-invalid block stopped early"
            ) from invalid_error
        _validate_execution(invalid, material)

        def forbidden_gold_loader() -> tuple[Any, dict[str, Any]]:
            raise AssertionError("gold loader reached for structural-invalid block")

        invalid_decision, invalid_gold, invalid_gold_value = _classify_after_execution(
            invalid,
            material=material,
            gold_loader=forbidden_gold_loader,
            classifier=counted_classifier,
        )

        _guard_execution, guard_journal, guard_endpoints, guard_error = _run_fake_block(
            material, default_outputs, tamper_arm="C"
        )
        with mock.patch.object(
            _sys_modules_self(), "_tag_ref_exists", return_value=False
        ):
            try:
                _observe_execution_authorization(allow_pending=False)
            except UptakeLiveExecutionError:
                tag_denied = True
            else:
                tag_denied = False
        artifact_self_test = _offline_artifact_self_test(
            material=material,
            assessed_execution=success,
            assessed_decision=success_decision,
            incomplete_execution=invalid,
            incomplete_decision=invalid_decision,
        )
        recorded_authorization = {
            "status": "AUTHORIZED_ANNOTATED_TAG",
            "tag_name": EXECUTION_AUTHORIZATION_TAG,
            "tag_object": "a" * 40,
            "authorized_commit": "b" * 40,
            "execution_head_commit": "b" * 40,
            "head_matches_authorized_commit": True,
            "provenance_scope": "OPERATOR_ATTESTED_NOT_CRYPTOGRAPHICALLY_AUTHENTICATED",
        }
        _validate_recorded_execution_authorization(
            recorded_authorization,
            observer=lambda **_kwargs: {
                "status": "AUTHORIZED_ANNOTATED_TAG",
                "tag_name": EXECUTION_AUTHORIZATION_TAG,
                "tag_object": "a" * 40,
                "authorized_commit": "b" * 40,
                "provenance_scope": "OPERATOR_ATTESTED_NOT_CRYPTOGRAPHICALLY_AUTHENTICATED",
            },
        )

    success_statuses = [row["status"] for row in success["attempts"]]
    stale_c = next(row for row in stale["attempts"] if row["treatment_id"] == "C")
    invalid_statuses = [row["status"] for row in invalid["attempts"]]
    checks = {
        "committed_projection_rederived": material["projection"]["fingerprint_sha256"]
        == "65af77712b529bb028aeae22e3eba5d6d943b0299a0b2951758445afcfe83216",
        "provider_transport_pass": transport["status"] == "PASS",
        "success_four_calls_four_terminals": success_statuses == ["COMPLETED"] * 4
        and len(success_endpoints) == 4
        and success_journal == _journal_bytes(success)
        and success_journal.count(b'"event":"ATTEMPT_STARTED"') == 4
        and success_journal.count(b'"event":"ATTEMPT_TERMINAL"') == 4,
        "success_gold_delayed_exactly_once": load_counts["gold"] == 2
        and load_counts["classifier"] == 2
        and success_gold["classification_load_count"] == 1
        and success_decision["assessment_status"] == "ASSESSED",
        "known_stale_semantic_arm_compiles_and_continues": stale_c["status"]
        == "COMPLETED"
        and stale["assessment_status"] == "READY_FOR_POST_CALL_GOLD"
        and len(stale_endpoints) == 4
        and stale_journal == _journal_bytes(stale)
        and stale_journal.count(b'"event":"ATTEMPT_TERMINAL"') == 4
        and stale_gold["loaded"] is True
        and stale_decision["assessment_status"] == "ASSESSED",
        "structural_invalid_continues_all_four_without_gold": invalid_statuses
        == ["COMPLETED", "LOCAL_OUTPUT_CONTRACT_ERROR", "COMPLETED", "COMPLETED"]
        and len(invalid_endpoints) == 4
        and invalid_journal == _journal_bytes(invalid)
        and invalid_journal.count(b'"event":"ATTEMPT_STARTED"') == 4
        and invalid_journal.count(b'"event":"ATTEMPT_TERMINAL"') == 4
        and invalid["assessment_status"] == "INCOMPLETE_NOT_ASSESSED"
        and invalid_gold["loaded"] is False
        and invalid_gold_value is None
        and invalid_decision["terminal_decision"] == "INCOMPLETE_NOT_ASSESSED",
        "receipt_guard_stops_and_burns": isinstance(
            guard_error, UptakeLiveExecutionError
        )
        and sum(len(endpoint.calls) for endpoint in guard_endpoints) == 1
        and guard_journal.count(b'"event":"ATTEMPT_STARTED"') == 1
        and guard_journal.count(b'"event":"ATTEMPT_TERMINAL"') == 0
        and guard_journal.count(b'"event":"IRRECOVERABLE_GUARD_FAILURE"') == 1
        and ("0" * 64).encode() not in guard_journal,
        "authorization_tag_denied_before_merge_tag": tag_denied,
        "recorded_authorization_survives_later_head": True,
        "offline_artifact_contract_pass": artifact_self_test["status"] == "PASS"
        and all(artifact_self_test["checks"].values()),
        "network_calls_zero": network_counts["network_calls"] == 0,
        "semantic_gold_path_reads_zero": gold_counts["attempted_gold_accesses"] == 0,
        "sdk_versions_pinned": (
            importlib.metadata.version("openai") == EXPECTED_OPENAI_SDK_VERSION
            and importlib.metadata.version("pydantic") == EXPECTED_PYDANTIC_VERSION
        ),
    }
    if not all(checks.values()):
        failed = sorted(key for key, value in checks.items() if not value)
        raise UptakeLiveExecutionError(f"component self-test failed: {failed}")
    return _seal(
        {
            "schema_version": "ebrt-actuator-uptake-live-component-self-test-v0.6.3.1-r01",
            "status": "PASS_NETWORK_ZERO",
            "checks": checks,
            "provider_calls": 0,
            "network_calls": 0,
            "simulated_api_calls": 13,
        }
    )


def _sys_modules_self() -> Any:
    return sys.modules[__name__]


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
        raise UptakeLiveExecutionError("component self-test did not pass")
    manifest = _strict_load(COMMITTED_PREFLIGHT_MANIFEST_PATH)
    projection = material["projection"]
    if (
        manifest.get("status") != "READY_ZERO_CALL_PREFLIGHT_ONLY"
        or manifest.get("live_execution_authorized") is not False
        or manifest.get("provider_calls") != 0
        or manifest.get("network_calls") != 0
        or manifest.get("projection_fingerprint_sha256")
        != projection["fingerprint_sha256"]
    ):
        raise UptakeLiveExecutionError("committed zero-call manifest drifted")
    if require_api_key and not os.environ.get("OPENAI_API_KEY"):
        raise UptakeLiveExecutionError("OPENAI_API_KEY is unavailable")
    expected_provenance = {
        **_runtime_contract(),
        "instructions_fingerprint_sha256": INSTRUCTIONS_FINGERPRINT,
        "response_schema_fingerprint_sha256": RESPONSE_SCHEMA_FINGERPRINT,
        "receipt_schema_version": RECEIPT_SCHEMA_VERSION,
    }
    if require_api_key:
        providers = [
            OpenAIUptakeProviderLiveR01(case=material["case"])
            for _row in material["attempts"]
        ]
        if (
            len(providers) != 4
            or any(provider.provenance != expected_provenance for provider in providers)
            or any(provider.audit_receipts for provider in providers)
        ):
            raise UptakeLiveExecutionError("provider runtime differs across attempts")
    if (
        lock["runtime"] != _runtime_contract()
        or lock["instructions_fingerprint_sha256"] != INSTRUCTIONS_FINGERPRINT
        or lock["response_schema_fingerprint_sha256"] != RESPONSE_SCHEMA_FINGERPRINT
        or lock["execution"]["provider_calls_authorized"] != 4
    ):
        raise UptakeLiveExecutionError("live runtime differs from policy lock")
    return _seal(
        {
            "schema_version": "ebrt-actuator-uptake-live-preflight-v0.6.3.1-r01",
            "status": (
                "READY_EXACT_FOUR_CALL_LIVE_BLOCK"
                if execution_authorization.get("status") == "AUTHORIZED_ANNOTATED_TAG"
                else "READY_CONTRACT_ONLY_AWAITING_EXECUTION_TAG"
            ),
            "expected_api_attempts": 4,
            "execution_order": list(EXPECTED_EXECUTION_ORDER),
            "call_order_blinded_request_ids": [
                row["blinded_request_id"] for row in material["attempts"]
            ],
            "payload_fingerprints": {
                row["blinded_request_id"]: row["sealed_payload"]["fingerprint_sha256"]
                for row in material["attempts"]
            },
            "projection_fingerprint_sha256": projection["fingerprint_sha256"],
            "policy_lock_fingerprint_sha256": lock["fingerprint_sha256"],
            "provider": expected_provenance,
            "component_self_test": component,
            "execution_authorization": _clone(execution_authorization),
            "source_snapshot_sha256": dict(source_snapshot),
            "post_call_gold_expected_receipt": _clone(
                lock["sources"]["post_call_gold"]
            ),
            "gold_loaded": False,
            "provider_calls": 0,
            "network_calls": 0,
        }
    )


def _preflight_materialize(
    *, require_api_key: bool, require_authorization: bool
) -> dict[str, Any]:
    output = DEFAULT_OUTPUT
    if output.is_symlink() or output.parent.is_symlink():
        raise UptakeLiveExecutionError("live namespace contains a symlink")
    if output.exists():
        raise UptakeLiveExecutionError(f"output already exists: {output}")
    if _staging_directory(output).exists():
        raise UptakeLiveExecutionError(
            f"unresolved prior attempt journal exists: {_staging_directory(output)}"
        )
    with _semantic_gold_denied() as gold_counts:
        lock = _load_lock()
        source_before = _source_snapshot(lock)
        material = _materialize_projection()
        authorization = _observe_execution_authorization(
            allow_pending=not require_authorization
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
        raise UptakeLiveExecutionError("semantic gold access occurred in preflight")
    if source_after != source_before:
        raise UptakeLiveExecutionError("locked sources changed during preflight")
    return {
        **material,
        "lock": lock,
        "preflight": preflight_value,
        "source_snapshot": source_before,
    }


def preflight() -> dict[str, Any]:
    return _clone(
        _preflight_materialize(require_api_key=False, require_authorization=False)[
            "preflight"
        ]
    )


def _calls_bytes(result: Mapping[str, Any]) -> bytes:
    rows = [
        {
            "schema_version": CALL_SCHEMA,
            "sequence_index": attempt["sequence_index"],
            "blinded_request_id": attempt["blinded_request_id"],
            "treatment_id": attempt["treatment_id"],
            "status": attempt["status"],
            "failure": _clone(attempt.get("failure")),
            "receipt": _clone(attempt["receipt"]),
        }
        for attempt in result["execution"]["attempts"]
    ]
    return b"".join(_canonical_bytes(row, trailing_newline=True) for row in rows)


def _provider_inputs_artifact(material: Mapping[str, Any]) -> dict[str, Any]:
    return _seal(
        {
            "schema_version": PROVIDER_INPUTS_SCHEMA,
            "projection_fingerprint_sha256": material["projection"][
                "fingerprint_sha256"
            ],
            "execution_order": list(EXPECTED_EXECUTION_ORDER),
            "payloads": [
                {
                    "sequence_index": row["sequence_index"],
                    "blinded_request_id": row["blinded_request_id"],
                    "treatment_id": row["treatment_id"],
                    "provider_payload_fingerprint_sha256": row["sealed_payload"][
                        "fingerprint_sha256"
                    ],
                    "sealed_payload": _clone(row["sealed_payload"]),
                }
                for row in material["attempts"]
            ],
            "provider_received_unsealed_payload_only": True,
        }
    )


def _report(result: Mapping[str, Any]) -> str:
    decision = result["decision"]
    lines = [
        "# EBRT v0.6.3.1 live-r01",
        "",
        f"- Attempt block: `{result['execution']['attempt_block_status']}`",
        f"- Assessment: `{decision['assessment_status']}`",
        f"- Terminal decision: `{decision['terminal_decision']}`",
        f"- Calls: `{result['usage']['api_calls']}/4`",
        f"- Gold loaded: `{str(result['semantic_gold']['loaded']).lower()}`",
        "",
        "## Public outputs",
        "",
        "| Position | Arm | Status | Closure |",
        "|---:|---|---|---|",
    ]
    outputs = result["execution"]["provider_outputs"]
    for attempt in result["execution"]["attempts"]:
        output = outputs.get(attempt["blinded_request_id"], {})
        lines.append(
            "| {position} | {arm} | {status} | {closure} |".format(
                position=attempt["sequence_index"],
                arm=attempt["treatment_id"],
                status=attempt["status"],
                closure=output.get("selected_closure_id", "—"),
            )
        )
    lines.extend(["", "## Boundary", "", *[f"- {item}" for item in CLAIM_BOUNDARY], ""])
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
            "attempt_block_status": result["execution"]["attempt_block_status"],
            "assessment_status": result["decision"]["assessment_status"],
            "terminal_decision": result["decision"]["terminal_decision"],
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
    files["manifest.json"] = _pretty_bytes(
        _manifest_value(files=files, result=result, lock=lock)
    )
    if set(files) != set(ARTIFACT_FILES):
        raise UptakeLiveExecutionError("artifact file set drifted before publish")
    return files


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _publish_directory(
    output: Path, files: Mapping[str, bytes], *, require_canonical_output: bool
) -> None:
    if (
        (require_canonical_output and output != DEFAULT_OUTPUT)
        or output.is_symlink()
        or output.parent.is_symlink()
    ):
        raise UptakeLiveExecutionError("live publish namespace is noncanonical")
    if output.exists():
        raise UptakeLiveExecutionError(f"output already exists: {output}")
    if set(files) != set(ARTIFACT_FILES):
        raise UptakeLiveExecutionError("artifact file set drifted before publish")
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


def _publish(output: Path, files: Mapping[str, bytes]) -> None:
    _publish_directory(output, files, require_canonical_output=True)


def _read_artifact_directory(output: Path) -> dict[str, bytes]:
    if not output.is_dir() or output.is_symlink():
        raise UptakeLiveExecutionError(f"artifact directory unavailable: {output}")
    observed: list[str] = []
    for path in output.rglob("*"):
        if path.is_symlink() or not path.is_file() or path.parent != output:
            raise UptakeLiveExecutionError("artifact directory has noncanonical entry")
        observed.append(path.name)
    if set(observed) != set(ARTIFACT_FILES) or len(observed) != len(ARTIFACT_FILES):
        raise UptakeLiveExecutionError("artifact directory file set drifted")
    return {name: (output / name).read_bytes() for name in ARTIFACT_FILES}


def _expected_provider_provenance() -> dict[str, Any]:
    return {
        **_runtime_contract(),
        "instructions_fingerprint_sha256": INSTRUCTIONS_FINGERPRINT,
        "response_schema_fingerprint_sha256": RESPONSE_SCHEMA_FINGERPRINT,
        "receipt_schema_version": RECEIPT_SCHEMA_VERSION,
    }


def _terminal_from_classifier_statuses(positive: str, placement: str) -> str:
    if (
        positive == "CHANNEL_OPEN_DIRECTIONAL"
        and placement == "GRADIENT_PLACEMENT_DIRECTIONAL"
    ):
        return "PROMOTE_TO_FRESH_REPLICATION"
    if positive == "POSITIVE_CONTROL_CEILING":
        return "STOP_POSITIVE_CONTROL_CEILING_NOT_ASSESSED"
    if positive == "ACTUATOR_CHANNEL_INERT":
        return "STOP_CHANNEL_INERT"
    if positive == "CHANNEL_OPEN_DIRECTION_AMBIGUOUS":
        return "STOP_CHANNEL_AMBIGUOUS"
    if positive == "CHANNEL_OPEN_ADVERSE":
        return "STOP_CHANNEL_ADVERSE"
    if placement == "D_C_TARGET_CEILING":
        return "STOP_PLACEMENT_CEILING_NOT_ASSESSED"
    if placement == "GRADIENT_PLACEMENT_NULL":
        return "STOP_PLACEMENT_NULL"
    if placement == "GRADIENT_PLACEMENT_AMBIGUOUS":
        return "STOP_PLACEMENT_AMBIGUOUS"
    return "STOP_PLACEMENT_ADVERSE"


def _validate_assessed_decision_relationships(
    decision: Mapping[str, Any], execution: Mapping[str, Any]
) -> None:
    expected_keys = {
        "schema_version",
        "assessment_status",
        "positive_control_status",
        "gradient_placement_status",
        "terminal_decision",
        "selected_closure_by_arm",
        "endpoint_fingerprint_by_arm",
        "invalid_arms",
        "direct_v0_6_4_promotion_allowed",
        "claim_boundary",
        "fingerprint_sha256",
    }
    selected = {
        row["treatment_id"]: execution["compiled_outputs"][row["blinded_request_id"]][
            "selected_closure_id"
        ]
        for row in execution["attempts"]
    }
    endpoints = decision.get("endpoint_fingerprint_by_arm")
    positive = decision.get("positive_control_status")
    placement = decision.get("gradient_placement_status")
    if (
        set(decision) != expected_keys
        or decision.get("schema_version") != "ebrt-actuator-uptake-decision-v0.6.3.1"
        or decision.get("assessment_status") != "ASSESSED"
        or positive not in POSITIVE_CONTROL_STATUSES
        or placement not in GRADIENT_PLACEMENT_STATUSES
        or decision.get("terminal_decision")
        != _terminal_from_classifier_statuses(str(positive), str(placement))
        or decision.get("selected_closure_by_arm") != selected
        or not isinstance(endpoints, Mapping)
        or set(endpoints) != set(core.ARMS)
        or not all(_is_sha256(value) for value in endpoints.values())
        or decision.get("invalid_arms") != []
        or decision.get("direct_v0_6_4_promotion_allowed") is not False
        or decision.get("claim_boundary") != list(DECISION_CLAIM_BOUNDARY)
    ):
        raise UptakeLiveExecutionError("assessed decision contract drifted")
    if (positive in {"POSITIVE_CONTROL_CEILING", "ACTUATOR_CHANNEL_INERT"}) is not (
        selected["Z"] == selected["X"]
    ):
        raise UptakeLiveExecutionError("positive-control closure relation drifted")
    if (placement in {"D_C_TARGET_CEILING", "GRADIENT_PLACEMENT_NULL"}) is not (
        selected["D"] == selected["C"]
    ):
        raise UptakeLiveExecutionError("placement closure relation drifted")


def _validate_preflight_record(
    preflight_value: Mapping[str, Any],
    *,
    material: Mapping[str, Any],
    lock: Mapping[str, Any],
    source_snapshot: Mapping[str, str],
    require_recorded_authorization: bool,
) -> None:
    expected_keys = {
        "schema_version",
        "status",
        "expected_api_attempts",
        "execution_order",
        "call_order_blinded_request_ids",
        "payload_fingerprints",
        "projection_fingerprint_sha256",
        "policy_lock_fingerprint_sha256",
        "provider",
        "component_self_test",
        "execution_authorization",
        "source_snapshot_sha256",
        "post_call_gold_expected_receipt",
        "gold_loaded",
        "provider_calls",
        "network_calls",
        "fingerprint_sha256",
    }
    component = preflight_value.get("component_self_test")
    authorization = preflight_value.get("execution_authorization")
    if (
        set(preflight_value) != expected_keys
        or preflight_value.get("schema_version")
        != "ebrt-actuator-uptake-live-preflight-v0.6.3.1-r01"
        or preflight_value.get("expected_api_attempts") != 4
        or preflight_value.get("execution_order") != list(EXPECTED_EXECUTION_ORDER)
        or preflight_value.get("call_order_blinded_request_ids")
        != [row["blinded_request_id"] for row in material["attempts"]]
        or preflight_value.get("payload_fingerprints")
        != {
            row["blinded_request_id"]: row["sealed_payload"]["fingerprint_sha256"]
            for row in material["attempts"]
        }
        or preflight_value.get("projection_fingerprint_sha256")
        != material["projection"]["fingerprint_sha256"]
        or preflight_value.get("policy_lock_fingerprint_sha256")
        != lock["fingerprint_sha256"]
        or preflight_value.get("provider") != _expected_provider_provenance()
        or not isinstance(component, Mapping)
        or component.get("status") != "PASS_NETWORK_ZERO"
        or component.get("provider_calls") != 0
        or component.get("network_calls") != 0
        or component.get("fingerprint_sha256")
        != fingerprint(
            {
                key: _clone(value)
                for key, value in component.items()
                if key != "fingerprint_sha256"
            }
        )
        or preflight_value.get("source_snapshot_sha256") != source_snapshot
        or preflight_value.get("post_call_gold_expected_receipt")
        != lock["sources"]["post_call_gold"]
        or preflight_value.get("gold_loaded") is not False
        or preflight_value.get("provider_calls") != 0
        or preflight_value.get("network_calls") != 0
        or preflight_value.get("fingerprint_sha256")
        != fingerprint(
            {
                key: _clone(value)
                for key, value in preflight_value.items()
                if key != "fingerprint_sha256"
            }
        )
    ):
        raise UptakeLiveExecutionError("preflight record drifted")
    if require_recorded_authorization:
        if preflight_value.get(
            "status"
        ) != "READY_EXACT_FOUR_CALL_LIVE_BLOCK" or not isinstance(
            authorization, Mapping
        ):
            raise UptakeLiveExecutionError("live preflight authorization missing")
        _validate_recorded_execution_authorization(authorization)
    elif preflight_value.get("status") != "OFFLINE_SELF_TEST" or authorization != {
        "status": "OFFLINE_SELF_TEST",
        "tag_name": EXECUTION_AUTHORIZATION_TAG,
    }:
        raise UptakeLiveExecutionError("offline preflight marker drifted")


def _validate_bundle_files(
    files: Mapping[str, bytes],
    *,
    material: Mapping[str, Any],
    lock: Mapping[str, Any],
    expected_source_snapshot: Mapping[str, str],
    expected_decision: Mapping[str, Any],
    require_recorded_authorization: bool,
) -> dict[str, Any]:
    if set(files) != set(ARTIFACT_FILES):
        raise UptakeLiveExecutionError("artifact byte map file set drifted")
    manifest = _strict_json_bytes(files["manifest.json"], "manifest.json")
    if files["manifest.json"] != _pretty_bytes(manifest):
        raise UptakeLiveExecutionError("manifest JSON encoding is noncanonical")
    non_manifest = set(ARTIFACT_FILES) - {"manifest.json"}
    if (
        set(manifest)
        != {
            "schema_version",
            "status",
            "attempt_block_status",
            "assessment_status",
            "terminal_decision",
            "policy_lock_fingerprint_sha256",
            "result_fingerprint_sha256",
            "source_snapshot_sha256",
            "artifacts",
            "claim_boundary",
            "fingerprint_sha256",
        }
        or set(manifest.get("artifacts", {})) != non_manifest
    ):
        raise UptakeLiveExecutionError("manifest schema drifted")
    for name in non_manifest:
        if manifest["artifacts"][name] != {
            "bytes": len(files[name]),
            "sha256": _sha256_bytes(files[name]),
        }:
            raise UptakeLiveExecutionError(f"artifact receipt drifted: {name}")
    if files["projection_bundle.json"] != _pretty_bytes(material["projection"]):
        raise UptakeLiveExecutionError("published projection differs from preflight")
    inputs = _strict_json_bytes(files["provider_inputs.json"], "provider_inputs.json")
    if files["provider_inputs.json"] != _pretty_bytes(
        inputs
    ) or inputs != _provider_inputs_artifact(material):
        raise UptakeLiveExecutionError("provider inputs artifact drifted")
    result = _strict_json_bytes(files["result.json"], "result.json")
    result_keys = {
        "schema_version",
        "mode",
        "claim_boundary",
        "preflight_anchor_tag_object",
        "preflight_anchor_commit",
        "policy_lock_fingerprint_sha256",
        "projection_fingerprint_sha256",
        "preflight",
        "source_snapshot_sha256",
        "execution",
        "semantic_gold",
        "decision",
        "direct_v0_6_4_promotion_allowed",
        "usage",
        "fingerprint_sha256",
    }
    if (
        files["result.json"] != _pretty_bytes(result)
        or set(result) != result_keys
        or result.get("schema_version") != RESULT_SCHEMA
        or result.get("mode") != "openai_live_actuator_uptake_canary_v0_6_3_1_r01"
        or result.get("claim_boundary") != list(CLAIM_BOUNDARY)
        or result.get("preflight_anchor_tag_object") != PREFLIGHT_ANCHOR_TAG_OBJECT
        or result.get("preflight_anchor_commit") != PREFLIGHT_ANCHOR_COMMIT
        or result.get("policy_lock_fingerprint_sha256") != lock["fingerprint_sha256"]
        or result.get("projection_fingerprint_sha256")
        != material["projection"]["fingerprint_sha256"]
        or result.get("source_snapshot_sha256") != expected_source_snapshot
        or result.get("direct_v0_6_4_promotion_allowed") is not False
        or result.get("fingerprint_sha256")
        != fingerprint(
            {
                key: _clone(value)
                for key, value in result.items()
                if key != "fingerprint_sha256"
            }
        )
    ):
        raise UptakeLiveExecutionError("result top-level contract drifted")
    _validate_preflight_record(
        result["preflight"],
        material=material,
        lock=lock,
        source_snapshot=expected_source_snapshot,
        require_recorded_authorization=require_recorded_authorization,
    )
    _validate_execution(result["execution"], material)
    if result.get("usage") != _usage_summary(result["execution"]["attempts"]):
        raise UptakeLiveExecutionError("result usage drifted")
    decision = result.get("decision")
    if not isinstance(decision, Mapping) or decision != expected_decision:
        raise UptakeLiveExecutionError("decision differs from exact reclassification")
    if decision.get("fingerprint_sha256") != fingerprint(
        {
            key: _clone(value)
            for key, value in decision.items()
            if key != "fingerprint_sha256"
        }
    ):
        raise UptakeLiveExecutionError("decision fingerprint drifted")
    if result["execution"]["assessment_status"] == "INCOMPLETE_NOT_ASSESSED":
        if result["semantic_gold"] != {
            "loaded": False,
            "classification_load_count": 0,
            "observed_receipt": None,
        } or decision != _incomplete_decision(result["execution"]):
            raise UptakeLiveExecutionError("incomplete block accessed gold or decision")
    else:
        if result["semantic_gold"] != {
            "loaded": True,
            "classification_load_count": 1,
            "observed_receipt": lock["sources"]["post_call_gold"],
        }:
            raise UptakeLiveExecutionError("assessed block gold audit drifted")
        _validate_assessed_decision_relationships(decision, result["execution"])
    if files["calls.jsonl"] != _calls_bytes(result):
        raise UptakeLiveExecutionError("calls ledger drifted")
    if files["attempt_journal.jsonl"] != _journal_bytes(result["execution"]):
        raise UptakeLiveExecutionError("attempt journal drifted")
    if files["report.md"] != _report(result).encode("utf-8"):
        raise UptakeLiveExecutionError("report drifted")
    expected_manifest = _manifest_value(
        files={name: files[name] for name in non_manifest}, result=result, lock=lock
    )
    if manifest != expected_manifest:
        raise UptakeLiveExecutionError("manifest differs from reconstruction")
    return result


def _operation_rejected(operation: Callable[[], Any]) -> bool:
    try:
        operation()
    except Exception:
        return True
    return False


def _offline_artifact_self_test(
    *,
    material: Mapping[str, Any],
    assessed_execution: Mapping[str, Any],
    assessed_decision: Mapping[str, Any],
    incomplete_execution: Mapping[str, Any],
    incomplete_decision: Mapping[str, Any],
) -> dict[str, Any]:
    lock = policy_lock_material()
    source_snapshot = _source_snapshot(lock)
    preflight_value = _offline_preflight_record(
        lock=lock, material=material, source_snapshot=source_snapshot
    )
    assessed_result = _assemble_result(
        assessed_execution,
        material=material,
        preflight_value=preflight_value,
        source_snapshot=source_snapshot,
        lock=lock,
        decision=assessed_decision,
        gold_audit={
            "loaded": True,
            "classification_load_count": 1,
            "observed_receipt": lock["sources"]["post_call_gold"],
        },
    )
    incomplete_result = _assemble_result(
        incomplete_execution,
        material=material,
        preflight_value=preflight_value,
        source_snapshot=source_snapshot,
        lock=lock,
        decision=incomplete_decision,
        gold_audit={
            "loaded": False,
            "classification_load_count": 0,
            "observed_receipt": None,
        },
    )
    assessed_files = _materialize_files(
        assessed_result,
        material=material,
        lock=lock,
        journal_bytes=_journal_bytes(assessed_execution),
    )
    incomplete_files = _materialize_files(
        incomplete_result,
        material=material,
        lock=lock,
        journal_bytes=_journal_bytes(incomplete_execution),
    )

    def validate_assessed(files: Mapping[str, bytes]) -> None:
        _validate_bundle_files(
            files,
            material=material,
            lock=lock,
            expected_source_snapshot=source_snapshot,
            expected_decision=assessed_decision,
            require_recorded_authorization=False,
        )

    def publish_and_read(root: Path, name: str, files: Mapping[str, bytes]) -> Path:
        output = root / name
        _publish_directory(output, files, require_canonical_output=False)
        _read_artifact_directory(output)
        return output

    with tempfile.TemporaryDirectory(
        prefix="ebrt-v0631-live-artifact-test-"
    ) as directory:
        root = Path(directory)
        assessed_dir = publish_and_read(root, "assessed", assessed_files)
        validate_assessed(_read_artifact_directory(assessed_dir))
        incomplete_dir = publish_and_read(root, "incomplete", incomplete_files)
        _validate_bundle_files(
            _read_artifact_directory(incomplete_dir),
            material=material,
            lock=lock,
            expected_source_snapshot=source_snapshot,
            expected_decision=incomplete_decision,
            require_recorded_authorization=False,
        )

        extra_dir = publish_and_read(root, "extra", assessed_files)
        (extra_dir / "extra.json").write_bytes(b"{}\n")
        extra_rejected = _operation_rejected(
            lambda: _read_artifact_directory(extra_dir)
        )

        missing_dir = publish_and_read(root, "missing", assessed_files)
        (missing_dir / "report.md").unlink()
        missing_rejected = _operation_rejected(
            lambda: _read_artifact_directory(missing_dir)
        )

        symlink_dir = publish_and_read(root, "symlink", assessed_files)
        (symlink_dir / "report.md").unlink()
        (symlink_dir / "report.md").symlink_to(symlink_dir / "result.json")
        symlink_rejected = _operation_rejected(
            lambda: _read_artifact_directory(symlink_dir)
        )

    byte_tampered = dict(assessed_files)
    byte_tampered["result.json"] = assessed_files["result.json"] + b" "
    byte_tamper_rejected = _operation_rejected(lambda: validate_assessed(byte_tampered))

    tampered_result = _clone(assessed_result)
    tampered_decision = _clone(tampered_result["decision"])
    tampered_decision.pop("fingerprint_sha256")
    tampered_decision["terminal_decision"] = "PROMOTE_TO_FRESH_REPLICATION"
    tampered_result["decision"] = _seal(tampered_decision)
    tampered_result.pop("fingerprint_sha256")
    tampered_result = _seal(tampered_result)
    terminal_tampered_files = _materialize_files(
        tampered_result,
        material=material,
        lock=lock,
        journal_bytes=_journal_bytes(assessed_execution),
    )
    terminal_reseal_rejected = _operation_rejected(
        lambda: validate_assessed(terminal_tampered_files)
    )
    fake_raw_body_absent = all(
        b"v0631-live-provider-self-test" not in raw
        for files in (assessed_files, incomplete_files)
        for raw in files.values()
    )
    checks = {
        "assessed_bundle_materialized_published_validated": True,
        "incomplete_bundle_materialized_published_validated_without_gold": True,
        "extra_file_rejected": extra_rejected,
        "missing_file_rejected": missing_rejected,
        "symlink_rejected": symlink_rejected,
        "byte_tamper_rejected": byte_tamper_rejected,
        "assessed_terminal_reseal_rejected": terminal_reseal_rejected,
        "fake_raw_provider_body_absent": fake_raw_body_absent,
    }
    if not all(checks.values()):
        raise UptakeLiveExecutionError("offline artifact self-test failed")
    return _seal(
        {
            "schema_version": "ebrt-actuator-uptake-live-artifact-self-test-v0.6.3.1-r01",
            "status": "PASS",
            "checks": checks,
            "provider_calls": 0,
            "network_calls": 0,
        }
    )


def _validate_bundle(
    output: Path = DEFAULT_OUTPUT, *, in_memory_gold: Mapping[str, Any] | None = None
) -> None:
    """Validate an authorized bundle; assessed results are exactly reclassified."""

    files = _read_artifact_directory(output)
    preview = _strict_json_bytes(files["result.json"], "result.json")
    authorization = preview.get("preflight", {}).get("execution_authorization")
    if not isinstance(authorization, Mapping):
        raise UptakeLiveExecutionError("result authorization missing")
    _validate_recorded_execution_authorization(authorization)
    commit = str(authorization["authorized_commit"])
    lock = _load_authorized_lock(commit)
    if preview.get("policy_lock_fingerprint_sha256") != lock["fingerprint_sha256"]:
        raise UptakeLiveExecutionError("result/authorized lock fingerprint drifted")
    _validate_authorized_source_blobs(lock, commit=commit, include_gold=False)
    expected_source_snapshot = {
        label: receipt["sha256"]
        for label, receipt in lock["sources"].items()
        if label != "post_call_gold"
    }
    if _source_snapshot(lock) != expected_source_snapshot:
        raise UptakeLiveExecutionError(
            "current validator sources differ from authorized source receipts"
        )
    material = _materialize_projection()
    _validate_execution(preview["execution"], material)
    compiled_by_arm = {
        row["treatment_id"]: preview["execution"]["compiled_outputs"][
            row["blinded_request_id"]
        ]
        for row in preview["execution"]["attempts"]
        if row["status"] == "COMPLETED"
    }
    if preview["execution"]["assessment_status"] == "READY_FOR_POST_CALL_GOLD":
        if in_memory_gold is None:
            gold, _receipt = _load_post_call_gold_at_commit(
                lock, material["fixture"], commit=commit
            )
        else:
            gold = _clone(in_memory_gold)
            core.validate_gold(gold, material["fixture"])
        expected_decision = core.classify_canary(
            compiled_by_arm, gold=gold, fixture=material["fixture"]
        )
    else:
        if in_memory_gold is not None:
            raise UptakeLiveExecutionError(
                "incomplete validation received semantic gold"
            )
        expected_decision = _incomplete_decision(preview["execution"])
    result = _validate_bundle_files(
        files,
        material=material,
        lock=lock,
        expected_source_snapshot=expected_source_snapshot,
        expected_decision=expected_decision,
        require_recorded_authorization=True,
    )
    expected_preflight = _build_preflight_record(
        lock=lock,
        material=material,
        source_snapshot=expected_source_snapshot,
        require_api_key=False,
        execution_authorization=result["preflight"]["execution_authorization"],
    )
    if result["preflight"] != expected_preflight:
        raise UptakeLiveExecutionError("preflight differs from exact rederivation")


def run_live() -> dict[str, Any]:
    output = DEFAULT_OUTPUT
    material = _preflight_materialize(require_api_key=True, require_authorization=True)
    lock = material["lock"]
    source_before = _source_snapshot(lock)
    authorization = material["preflight"]["execution_authorization"]
    staging = _staging_directory(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    staging.mkdir(mode=0o700)
    _fsync_directory(output.parent)
    plan = _seal(
        {
            "schema_version": "ebrt-actuator-uptake-live-inflight-plan-v0.6.3.1-r01",
            "status": "IRREVERSIBLE_FOUR_CALL_BLOCK_NOT_YET_STARTED",
            "policy_lock_fingerprint_sha256": lock["fingerprint_sha256"],
            "projection_fingerprint_sha256": material["projection"][
                "fingerprint_sha256"
            ],
            "execution_order": list(EXPECTED_EXECUTION_ORDER),
            "call_order_blinded_request_ids": [
                row["blinded_request_id"] for row in material["attempts"]
            ],
            "payload_fingerprints": {
                row["blinded_request_id"]: row["sealed_payload"]["fingerprint_sha256"]
                for row in material["attempts"]
            },
            "source_snapshot_sha256": source_before,
            "execution_authorization": authorization,
            "no_resume": True,
        }
    )
    plan_path = staging / "plan.json"
    plan_path.write_bytes(_pretty_bytes(plan))
    with plan_path.open("rb") as handle:
        os.fsync(handle.fileno())
    journal_path = staging / "attempt_journal.jsonl"
    journal_path.touch(mode=0o600)
    with journal_path.open("rb") as handle:
        os.fsync(handle.fileno())
    _fsync_directory(staging)

    def live_source_guard() -> None:
        observed_lock = _load_lock()
        if observed_lock["fingerprint_sha256"] != lock["fingerprint_sha256"]:
            raise UptakeLiveExecutionError("policy lock changed during live block")
        if _source_snapshot(observed_lock) != source_before:
            raise UptakeLiveExecutionError("locked source changed during live block")
        observed_authorization = _observe_execution_authorization(allow_pending=False)
        if (
            observed_authorization["tag_object"] != authorization["tag_object"]
            or observed_authorization["authorized_commit"]
            != authorization["authorized_commit"]
        ):
            raise UptakeLiveExecutionError("authorization changed during live block")

    with _semantic_gold_denied() as gold_counts:
        execution = _execute_gold_free(
            material,
            journal_path=journal_path,
            source_guard=live_source_guard,
        )
        live_source_guard()
        _validate_execution(execution, material)
        journal_bytes = journal_path.read_bytes()
        if journal_bytes != _journal_bytes(execution):
            raise UptakeLiveExecutionError("durable attempt journal drifted")
    if gold_counts["attempted_gold_accesses"] != 0:
        raise UptakeLiveExecutionError(
            "semantic gold accessed during provider execution"
        )

    # Semantic gold is loaded exactly once here only when all four arms compiled.
    result, in_memory_gold = _finalize(
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
    # Public validation deliberately does not reopen semantic gold.
    _validate_bundle(output, in_memory_gold=in_memory_gold)
    shutil.rmtree(staging)
    _fsync_directory(output.parent)
    return {
        "artifact_directory": str(output),
        "attempt_block_status": result["execution"]["attempt_block_status"],
        "assessment_status": result["decision"]["assessment_status"],
        "terminal_decision": result["decision"]["terminal_decision"],
        "result_fingerprint_sha256": result["fingerprint_sha256"],
        "usage": result["usage"],
    }


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
        _validate_bundle(args.output)
        _print_json({"artifact_directory": str(args.output), "status": "VALID"})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
