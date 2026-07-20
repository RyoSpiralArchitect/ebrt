#!/usr/bin/env python3
"""Portable, network-zero verifier for the frozen v0.6.3-live-r01 artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parent
DEFAULT_ARTIFACT = ROOT / "artifacts" / "actuator_calibration_v0_6_3_live_r01"

EXPECTED_FILES = {
    "attempt_journal.jsonl": (
        3281,
        "e22dbef8fb874d7e3c3fcd1fb8f6f87a68ca55f8188d4e228af7219c769a1f0a",
    ),
    "calls.jsonl": (
        2085,
        "0f2e2b465c51d9d21cc740b5325f24084aafcc2184725873e22dcf8dc31c2ac9",
    ),
    "manifest.json": (
        3786,
        "4bf105c325a800f9108262caaf6133f2d15be1c0353b61f8c0eaba37ed1309aa",
    ),
    "projection_bundle.json": (
        147098,
        "ffb6d232fb77131b2f978a725ed8564e5dc42481763235eaf3f52ac57ab3a2a4",
    ),
    "provider_inputs.json": (
        134557,
        "84d75b31ea5254b47045b327ad96a6b53dfa94c20561b3bbd177352da70e50cf",
    ),
    "report.md": (
        1709,
        "665a56935ecd5f77fc93196eb1c2e45b000143118865c99a03db87b81534e16c",
    ),
    "result.json": (
        15654,
        "5ed4442042dec4c252ea19dc445fa305a066dd59ed0a9ad16158138767b7c748",
    ),
}
EXPECTED_RESULT_FINGERPRINT = (
    "52b3878b877d7c006d7521d98de4ee3ce398cd5b279e577fe1bd9eebbd168a29"
)
EXPECTED_MANIFEST_FINGERPRINT = (
    "b30206e4416787267cd947ce73be3f9015bc6dd442a94739f6adf2823c3d7a9b"
)
EXPECTED_AUTHORIZATION_TAG_OBJECT = "eb76d2573073f34b020de8b37d877cf6670f917b"
EXPECTED_AUTHORIZED_COMMIT = "012791fc942107bf442e5db91be197a803ced599"


class VerificationError(RuntimeError):
    """The copied artifact differs from the frozen published result."""


def _reject_constant(value: str) -> Any:
    raise VerificationError(f"non-finite JSON constant: {value}")


def _reject_duplicates(pairs: Iterable[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise VerificationError(f"duplicate JSON key: {key}")
        output[key] = value
    return output


def _load_json(raw: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(
            raw.decode("utf-8"),
            parse_constant=_reject_constant,
            object_pairs_hook=_reject_duplicates,
        )
    except VerificationError:
        raise
    except Exception as error:
        raise VerificationError(f"invalid JSON: {label}") from error
    if not isinstance(value, dict):
        raise VerificationError(f"JSON root is not an object: {label}")
    return value


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _fingerprint(value: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _read_exact_files(directory: Path) -> dict[str, bytes]:
    if directory.is_symlink() or not directory.is_dir():
        raise VerificationError("artifact directory is unavailable or a symlink")
    observed: dict[str, bytes] = {}
    for path in directory.rglob("*"):
        if path.is_symlink() or not path.is_file() or path.parent != directory:
            raise VerificationError("artifact contains a noncanonical entry")
        observed[path.name] = path.read_bytes()
    if set(observed) != set(EXPECTED_FILES):
        raise VerificationError("artifact file set differs from the frozen result")
    for name, (expected_bytes, expected_sha) in EXPECTED_FILES.items():
        raw = observed[name]
        if len(raw) != expected_bytes or _sha256(raw) != expected_sha:
            raise VerificationError(f"frozen byte receipt differs: {name}")
    return observed


def _jsonl_rows(raw: bytes, label: str) -> list[dict[str, Any]]:
    if not raw.endswith(b"\n"):
        raise VerificationError(f"JSONL lacks a trailing newline: {label}")
    return [
        _load_json(line, f"{label}:{index}")
        for index, line in enumerate(raw.splitlines(), start=1)
    ]


def verify(directory: Path) -> dict[str, Any]:
    files = _read_exact_files(directory)
    result = _load_json(files["result.json"], "result.json")
    manifest = _load_json(files["manifest.json"], "manifest.json")

    result_without_fingerprint = {
        key: value for key, value in result.items() if key != "fingerprint_sha256"
    }
    if (
        result.get("fingerprint_sha256") != EXPECTED_RESULT_FINGERPRINT
        or _fingerprint(result_without_fingerprint) != EXPECTED_RESULT_FINGERPRINT
    ):
        raise VerificationError("result fingerprint differs")
    manifest_without_fingerprint = {
        key: value for key, value in manifest.items() if key != "fingerprint_sha256"
    }
    if (
        manifest.get("fingerprint_sha256") != EXPECTED_MANIFEST_FINGERPRINT
        or _fingerprint(manifest_without_fingerprint) != EXPECTED_MANIFEST_FINGERPRINT
    ):
        raise VerificationError("manifest fingerprint differs")

    for name in set(EXPECTED_FILES) - {"manifest.json"}:
        expected_receipt = {
            "bytes": len(files[name]),
            "sha256": _sha256(files[name]),
        }
        if manifest.get("artifacts", {}).get(name) != expected_receipt:
            raise VerificationError(f"manifest receipt differs: {name}")

    decision = result.get("decision", {})
    if decision != {
        "promotion_ready": False,
        "quality_is_promotion_gate": False,
        "reason_code": "PUBLIC_OUTPUT_COMPILER_REJECTED",
        "run_status": "INCOMPLETE",
        "terminal_status": "STOP_OUTPUT_CONTRACT",
    }:
        raise VerificationError("terminal decision differs")
    attempts = result.get("execution", {}).get("attempts", [])
    if len(attempts) != 1:
        raise VerificationError("attempt count differs")
    attempt = attempts[0]
    if (
        attempt.get("run_position") != 1
        or attempt.get("status") != "LOCAL_OUTPUT_CONTRACT_ERROR"
        or attempt.get("failure", {}).get("reason_code") != "EXACT_ONE_CLOSURE_FAILED"
        or result.get("gold_loaded_after_complete_compilation") is not False
        or len(result.get("execution", {}).get("unattempted_blinded_request_ids", []))
        != 15
    ):
        raise VerificationError("terminal attempt contract differs")
    authorization = result.get("preflight", {}).get("execution_authorization", {})
    if (
        authorization.get("tag_object") != EXPECTED_AUTHORIZATION_TAG_OBJECT
        or authorization.get("authorized_commit") != EXPECTED_AUTHORIZED_COMMIT
        or authorization.get("execution_head_commit") != EXPECTED_AUTHORIZED_COMMIT
    ):
        raise VerificationError("execution authorization differs")

    calls = _jsonl_rows(files["calls.jsonl"], "calls.jsonl")
    journal = _jsonl_rows(files["attempt_journal.jsonl"], "attempt_journal.jsonl")
    if len(calls) != 1 or [row.get("event") for row in journal] != [
        "ATTEMPT_STARTED",
        "ATTEMPT_TERMINAL",
    ]:
        raise VerificationError("call or journal ledger differs")

    return {
        "status": "VALID_FROZEN_TERMINAL_ARTIFACT",
        "artifact_directory": str(directory),
        "run_status": decision["run_status"],
        "terminal_status": decision["terminal_status"],
        "reason_code": decision["reason_code"],
        "attempt_count": len(attempts),
        "provider_api_calls": result["usage"]["api_calls"],
        "gold_loaded": result["gold_loaded_after_complete_compilation"],
        "result_fingerprint_sha256": EXPECTED_RESULT_FINGERPRINT,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-dir", type=Path, default=DEFAULT_ARTIFACT)
    args = parser.parse_args()
    print(json.dumps(verify(args.artifact_dir), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
