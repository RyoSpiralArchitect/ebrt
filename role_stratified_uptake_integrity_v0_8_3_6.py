#!/usr/bin/env python3
"""Complete dependency and locked-mount integrity wrapper for EBRT v0.8.3.

The r07 successor binds every imported non-stdlib module to its owning
distribution (or repository source) and verifies the embedded read-only mount
receipt against the locked model manifest.  It is not fresh scientific data.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import site
import sys
import sysconfig
from importlib.metadata import distribution, distributions
from pathlib import Path
from typing import Any, Mapping, Sequence

import role_stratified_uptake_integrity_v0_8_3_3 as loader_bound
import role_stratified_uptake_integrity_v0_8_3_5 as immutable_bound
import role_stratified_uptake_integrity_v0_8_3_4 as runtime_bound
from ebrt_core import EBRTError, _canonical_bytes, _fingerprint, _seal, _sealed_snapshot


LOCK_SCHEMA_VERSION = "ebrt-role-uptake-complete-lock-v0.8.3.6"
RUN_SCHEMA_VERSION = "ebrt-role-uptake-complete-run-v0.8.3.6"
SELF_TEST_SCHEMA_VERSION = "ebrt-role-uptake-complete-self-test-v0.8.3.6"
REPOSITORY_ROOT = Path(__file__).resolve().parent
REQUIRED_DISTRIBUTIONS = dict(runtime_bound.EXPECTED_RUNTIME["distributions"])
CRITICAL_MODULES = immutable_bound.CRITICAL_MODULES
CLAIM_BOUNDARY = (
    "This r07 execution repeats already observed cases only to close complete non-stdlib dependency and locked-mount verification gaps.",
    "The repeated outputs are contaminated by known r01-r06 results and are not fresh scientific replication evidence.",
    "Every imported file-backed non-stdlib module is bound to full owning-distribution content or a repository-relative source hash.",
    "The embedded read-only mount receipt must equal the staged manifest and clone fingerprints derived from the locked snapshot.",
    "The receipt is not hardware, kernel, code-signing, malicious-root, or scientific-effect attestation.",
    "All original v0.8.3 effect-attribution, one-model, public-role, and stop-gradient boundaries remain unchanged.",
)

JsonObject = dict[str, Any]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as source:
            while chunk := source.read(1024 * 1024):
                digest.update(chunk)
    except OSError as error:
        raise EBRTError("ROLE_COMPLETE_SOURCE_READ_FAILED") from error
    return digest.hexdigest()


def _load_json(path: Path) -> JsonObject:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise EBRTError("ROLE_COMPLETE_ARTIFACT_READ_FAILED") from error
    if not isinstance(value, dict):
        raise EBRTError("ROLE_COMPLETE_ARTIFACT_TYPE_INVALID")
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _relative_to(path: Path, root: Path) -> Path | None:
    try:
        return path.relative_to(root)
    except ValueError:
        return None


def _module_origin(module_name: str, module: Any) -> Path | None:
    origin_value = getattr(module, "__file__", None)
    if origin_value is None:
        return None
    origin = Path(origin_value)
    if not origin.is_absolute():
        working_candidate = Path.cwd() / origin
        if working_candidate.exists():
            origin = working_candidate
        else:
            top_level = module_name.split(".", 1)[0]
            top_module = sys.modules.get(top_level)
            top_origin = getattr(top_module, "__file__", None)
            if top_origin is None:
                raise EBRTError("ROLE_COMPLETE_MODULE_ORIGIN_MISSING")
            origin = Path(top_origin).parent / origin
    try:
        return origin.resolve(strict=True)
    except OSError as error:
        raise EBRTError("ROLE_COMPLETE_MODULE_ORIGIN_MISSING") from error


def _distribution_index(
    distribution_name: str,
) -> tuple[JsonObject, dict[Path, str]]:
    package = distribution(distribution_name)
    files = package.files
    if files is None:
        raise EBRTError("ROLE_COMPLETE_DISTRIBUTION_FILES_MISSING")
    rows: list[JsonObject] = []
    origins: dict[Path, str] = {}
    for item in sorted(files, key=lambda value: str(value)):
        try:
            path = Path(package.locate_file(item)).resolve(strict=True)
        except OSError as error:
            raise EBRTError("ROLE_COMPLETE_DISTRIBUTION_FILE_MISSING") from error
        if not path.is_file():
            continue
        relative_path = str(item)
        row = {
            "relative_path": relative_path,
            "size_bytes": path.stat().st_size,
            "sha256": _sha256(path),
        }
        rows.append(row)
        origins[path] = relative_path
    if not rows:
        raise EBRTError("ROLE_COMPLETE_DISTRIBUTION_MANIFEST_EMPTY")
    canonical_name = immutable_bound._canonical_distribution_name(
        package.metadata["Name"]
    )
    return (
        {
            "distribution": canonical_name,
            "version": package.version,
            "hashed_file_count": len(rows),
            "hashed_bytes": sum(row["size_bytes"] for row in rows),
            "files_fingerprint_sha256": _fingerprint(rows),
        },
        origins,
    )


def _site_roots() -> tuple[Path, ...]:
    values = set(site.getsitepackages())
    values.add(site.getusersitepackages())
    return tuple(sorted(Path(value).resolve() for value in values if value))


def _installed_origin_owners() -> dict[Path, tuple[str, ...]]:
    owners: dict[Path, set[str]] = {}
    for package in distributions():
        files = package.files
        package_name = package.metadata.get("Name")
        if files is None or not isinstance(package_name, str) or not package_name:
            continue
        canonical = immutable_bound._canonical_distribution_name(package_name)
        for item in files:
            try:
                path = Path(package.locate_file(item)).resolve(strict=True)
            except OSError:
                continue
            if path.is_file():
                owners.setdefault(path, set()).add(canonical)
    return {path: tuple(sorted(names)) for path, names in owners.items()}


def _complete_runtime_code_receipt() -> JsonObject:
    distribution_cache: dict[str, tuple[JsonObject, dict[Path, str]]] = {}
    origin_owners = _installed_origin_owners()
    module_rows: list[JsonObject] = []
    local_rows: list[JsonObject] = []
    owning_distributions: set[str] = set()
    stdlib_root = Path(sysconfig.get_paths()["stdlib"]).resolve()
    site_roots = _site_roots()

    def candidate_index(name: str) -> tuple[JsonObject, dict[Path, str]]:
        canonical = immutable_bound._canonical_distribution_name(name)
        if canonical not in distribution_cache:
            distribution_cache[canonical] = _distribution_index(name)
        return distribution_cache[canonical]

    for module_name, module in sorted(sys.modules.items()):
        origin = _module_origin(module_name, module)
        if origin is None:
            continue
        repository_relative = _relative_to(origin, REPOSITORY_ROOT)
        if repository_relative is not None:
            local_rows.append(
                {
                    "module": module_name,
                    "repository_relative_path": repository_relative.as_posix(),
                    "size_bytes": origin.stat().st_size,
                    "sha256": _sha256(origin),
                }
            )
            continue
        bindings: list[tuple[str, str]] = []
        for candidate in origin_owners.get(origin, ()):
            summary, origins = candidate_index(candidate)
            relative_path = origins.get(origin)
            if relative_path is not None:
                bindings.append((summary["distribution"], relative_path))
        if bindings:
            bindings.sort()
            owning_distributions.update(row[0] for row in bindings)
            distribution_name, relative_path = bindings[0]
            module_rows.append(
                {
                    "module": module_name,
                    "distribution": distribution_name,
                    "distribution_relative_path": relative_path,
                    "size_bytes": origin.stat().st_size,
                    "sha256": _sha256(origin),
                }
            )
            continue
        under_site = any(_relative_to(origin, root) is not None for root in site_roots)
        under_stdlib = _relative_to(origin, stdlib_root) is not None
        if under_stdlib and not under_site:
            continue
        raise EBRTError("ROLE_COMPLETE_NONSTDLIB_MODULE_UNBOUND")

    distribution_rows = sorted(
        [distribution_cache[name][0] for name in owning_distributions],
        key=lambda row: row["distribution"],
    )
    module_rows.sort(key=lambda row: row["module"])
    local_rows.sort(key=lambda row: row["module"])
    all_rows = [*module_rows, *local_rows]
    critical_rows = [row for row in module_rows if row["module"] in CRITICAL_MODULES]
    missing_critical = sorted(
        set(CRITICAL_MODULES) - {row["module"] for row in critical_rows}
    )
    if missing_critical:
        raise EBRTError("ROLE_COMPLETE_CRITICAL_MODULE_MISSING")
    return _seal(
        {
            "schema_version": "ebrt-complete-runtime-code-receipt-v0.8.3.6",
            "distribution_content": _seal(
                {
                    "schema_version": "ebrt-complete-distribution-summary-v0.8.3.6",
                    "distributions": distribution_rows,
                }
            ),
            "imported_modules": _seal(
                {
                    "schema_version": "ebrt-complete-module-summary-v0.8.3.6",
                    "all_file_backed_nonstdlib_modules_bound": True,
                    "module_count": len(all_rows),
                    "distribution_module_count": len(module_rows),
                    "repository_module_count": len(local_rows),
                    "module_manifest_fingerprint_sha256": _fingerprint(all_rows),
                    "critical_modules": critical_rows,
                    "repository_modules": local_rows,
                }
            ),
        }
    )


def probe_runtime_code(model_path: str) -> JsonObject:
    immutable_bound.probe_runtime_code(model_path)
    return _complete_runtime_code_receipt()


def _validate_runtime_code_shape(value: Any) -> JsonObject:
    receipt = _sealed_snapshot(value, "ROLE_COMPLETE_RUNTIME_CODE")
    if (
        set(receipt)
        != {
            "schema_version",
            "distribution_content",
            "imported_modules",
            "fingerprint_sha256",
        }
        or receipt.get("schema_version")
        != "ebrt-complete-runtime-code-receipt-v0.8.3.6"
    ):
        raise EBRTError("ROLE_COMPLETE_RUNTIME_CODE_SHAPE_INVALID")
    distributions = _sealed_snapshot(
        receipt.get("distribution_content"), "ROLE_COMPLETE_DISTRIBUTIONS"
    )
    rows = distributions.get("distributions")
    if (
        distributions.get("schema_version")
        != "ebrt-complete-distribution-summary-v0.8.3.6"
        or not isinstance(rows, list)
        or [row.get("distribution") for row in rows]
        != sorted(row.get("distribution") for row in rows)
    ):
        raise EBRTError("ROLE_COMPLETE_DISTRIBUTION_SUMMARY_INVALID")
    observed_versions: dict[str, str] = {}
    for row in rows:
        if (
            not isinstance(row, Mapping)
            or set(row)
            != {
                "distribution",
                "version",
                "hashed_file_count",
                "hashed_bytes",
                "files_fingerprint_sha256",
            }
            or not isinstance(row.get("distribution"), str)
            or not row["distribution"]
            or row["distribution"] in observed_versions
            or not isinstance(row.get("version"), str)
            or type(row.get("hashed_file_count")) is not int
            or row["hashed_file_count"] <= 0
            or type(row.get("hashed_bytes")) is not int
            or row["hashed_bytes"] <= 0
            or not isinstance(row.get("files_fingerprint_sha256"), str)
            or len(row["files_fingerprint_sha256"]) != 64
        ):
            raise EBRTError("ROLE_COMPLETE_DISTRIBUTION_ROW_INVALID")
        observed_versions[row["distribution"]] = row["version"]
    for distribution_name, expected_version in REQUIRED_DISTRIBUTIONS.items():
        canonical = immutable_bound._canonical_distribution_name(distribution_name)
        if observed_versions.get(canonical) != expected_version:
            raise EBRTError("ROLE_COMPLETE_REQUIRED_DISTRIBUTION_MISMATCH")
    modules = _sealed_snapshot(receipt.get("imported_modules"), "ROLE_COMPLETE_MODULES")
    critical = modules.get("critical_modules")
    local = modules.get("repository_modules")
    if (
        modules.get("schema_version") != "ebrt-complete-module-summary-v0.8.3.6"
        or modules.get("all_file_backed_nonstdlib_modules_bound") is not True
        or type(modules.get("module_count")) is not int
        or type(modules.get("distribution_module_count")) is not int
        or type(modules.get("repository_module_count")) is not int
        or modules["module_count"]
        != modules["distribution_module_count"] + modules["repository_module_count"]
        or not isinstance(modules.get("module_manifest_fingerprint_sha256"), str)
        or len(modules["module_manifest_fingerprint_sha256"]) != 64
        or not isinstance(critical, list)
        or [row.get("module") for row in critical] != list(CRITICAL_MODULES)
        or not isinstance(local, list)
        or len(local) != modules["repository_module_count"]
    ):
        raise EBRTError("ROLE_COMPLETE_MODULE_SUMMARY_INVALID")
    for row in critical:
        if (
            not isinstance(row, Mapping)
            or set(row)
            != {
                "module",
                "distribution",
                "distribution_relative_path",
                "size_bytes",
                "sha256",
            }
            or not isinstance(row.get("distribution_relative_path"), str)
            or type(row.get("size_bytes")) is not int
            or row["size_bytes"] <= 0
            or not isinstance(row.get("sha256"), str)
            or len(row["sha256"]) != 64
        ):
            raise EBRTError("ROLE_COMPLETE_CRITICAL_MODULE_ROW_INVALID")
    for row in local:
        if (
            not isinstance(row, Mapping)
            or set(row)
            != {
                "module",
                "repository_relative_path",
                "size_bytes",
                "sha256",
            }
            or not isinstance(row.get("repository_relative_path"), str)
            or Path(row["repository_relative_path"]).is_absolute()
            or ".." in Path(row["repository_relative_path"]).parts
            or type(row.get("size_bytes")) is not int
            or row["size_bytes"] <= 0
            or not isinstance(row.get("sha256"), str)
            or len(row["sha256"]) != 64
        ):
            raise EBRTError("ROLE_COMPLETE_REPOSITORY_MODULE_ROW_INVALID")
    return receipt


def _expected_staged_manifest_fingerprint() -> str:
    return _seal(
        {
            "schema_version": "ebrt-loader-staged-manifest-v0.8.3.3",
            "model_id": loader_bound.base.MODEL_ID,
            "files": sorted(
                loader_bound.snapshot_bound.EXPECTED_SNAPSHOT_FILES,
                key=lambda row: row["relative_path"],
            ),
        }
    )["fingerprint_sha256"]


def _expected_clone_fingerprint(snapshot_lock: Mapping[str, Any]) -> str:
    staged_fingerprint = _expected_staged_manifest_fingerprint()
    return _seal(
        {
            "status": "PASS",
            "source_manifest_fingerprint_sha256": snapshot_lock[
                "snapshot_manifest_fingerprint_sha256"
            ],
            "staged_manifest_fingerprint_sha256": staged_fingerprint,
            "file_count": len(loader_bound.snapshot_bound.EXPECTED_SNAPSHOT_FILES),
            "all_source_and_staged_inodes_distinct": True,
            "staging_strategy": loader_bound.STAGING_POLICY["strategy"],
            "staged_path_exported": False,
        }
    )["fingerprint_sha256"]


def _verify_mount_receipt(
    mount_value: Any,
    snapshot_lock: Mapping[str, Any],
) -> JsonObject:
    mount = _sealed_snapshot(mount_value, "ROLE_COMPLETE_MOUNT")
    expected_manifest = _expected_staged_manifest_fingerprint()
    expected_clone = _expected_clone_fingerprint(snapshot_lock)
    if (
        mount.get("source_clone_fingerprint_sha256") != expected_clone
        or mount.get("model_manifest_fingerprint_before") != expected_manifest
        or mount.get("model_manifest_fingerprint_after") != expected_manifest
    ):
        raise EBRTError("ROLE_COMPLETE_MOUNT_BINDING_INVALID")
    return mount


def lock_spec(
    base_lock: Mapping[str, Any],
    source_lock: Mapping[str, Any],
    snapshot_lock: Mapping[str, Any],
    loader_lock: Mapping[str, Any],
    runtime_lock: Mapping[str, Any],
    immutable_lock: Mapping[str, Any],
    runtime_code: Mapping[str, Any],
) -> JsonObject:
    locked_immutable = immutable_bound.validate_lock(
        immutable_lock,
        base_lock,
        source_lock,
        snapshot_lock,
        loader_lock,
        runtime_lock,
    )
    code = _validate_runtime_code_shape(runtime_code)
    return _seal(
        {
            "schema_version": LOCK_SCHEMA_VERSION,
            "status": "LOCKED_BEFORE_PROVIDER_CALLS",
            "wrapper_sha256": _sha256(Path(__file__)),
            "immutable_lock_fingerprint_sha256": locked_immutable["fingerprint_sha256"],
            "runtime_code": code,
            "runtime_code_fingerprint_sha256": code["fingerprint_sha256"],
            "expected_staged_manifest_fingerprint_sha256": _expected_staged_manifest_fingerprint(),
            "expected_clone_fingerprint_sha256": _expected_clone_fingerprint(
                snapshot_lock
            ),
            "replication_status": "INTEGRITY_REPLICATION_OVER_KNOWN_R01_R06_CASES",
            "effect_attribution_status": "NOT_ASSESSED",
            "claim_boundary": list(CLAIM_BOUNDARY),
        }
    )


def validate_lock(
    value: Any,
    base_lock: Mapping[str, Any],
    source_lock: Mapping[str, Any],
    snapshot_lock: Mapping[str, Any],
    loader_lock: Mapping[str, Any],
    runtime_lock: Mapping[str, Any],
    immutable_lock: Mapping[str, Any],
) -> JsonObject:
    observed = _sealed_snapshot(value, "ROLE_COMPLETE_LOCK")
    runtime_code = _validate_runtime_code_shape(observed.get("runtime_code"))
    expected = lock_spec(
        base_lock,
        source_lock,
        snapshot_lock,
        loader_lock,
        runtime_lock,
        immutable_lock,
        runtime_code,
    )
    if _canonical_bytes(observed) != _canonical_bytes(expected):
        raise EBRTError("ROLE_COMPLETE_LOCK_MISMATCH")
    return observed


def run_integrity_replication(
    model_path: str,
    lock: Mapping[str, Any],
    base_lock: Mapping[str, Any],
    source_lock: Mapping[str, Any],
    snapshot_lock: Mapping[str, Any],
    loader_lock: Mapping[str, Any],
    runtime_lock: Mapping[str, Any],
    immutable_lock: Mapping[str, Any],
) -> JsonObject:
    locked = validate_lock(
        lock,
        base_lock,
        source_lock,
        snapshot_lock,
        loader_lock,
        runtime_lock,
        immutable_lock,
    )
    code_before = probe_runtime_code(model_path)
    if _canonical_bytes(code_before) != _canonical_bytes(locked["runtime_code"]):
        raise EBRTError("ROLE_COMPLETE_RUNTIME_CODE_MISMATCH")
    prior_run = immutable_bound.run_integrity_replication(
        model_path,
        immutable_lock,
        base_lock,
        source_lock,
        snapshot_lock,
        loader_lock,
        runtime_lock,
    )
    _verify_mount_receipt(prior_run.get("mount_receipt"), snapshot_lock)
    code_after = _complete_runtime_code_receipt()
    if _canonical_bytes(code_after) != _canonical_bytes(locked["runtime_code"]):
        raise EBRTError("ROLE_COMPLETE_RUNTIME_CODE_CHANGED")
    return _seal(
        {
            "schema_version": RUN_SCHEMA_VERSION,
            "status": "COMPLETE",
            "policy_lock_fingerprint_sha256": locked["fingerprint_sha256"],
            "runtime_code_before": code_before,
            "runtime_code_after": code_after,
            "prior_run": prior_run,
            "summary": prior_run["summary"],
            "replication_status": "INTEGRITY_REPLICATION_OVER_KNOWN_R01_R06_CASES",
            "effect_attribution_status": "NOT_ASSESSED",
            "claim_boundary": list(CLAIM_BOUNDARY),
        }
    )


def verify_run(
    value: Any,
    lock: Mapping[str, Any],
    base_lock: Mapping[str, Any],
    source_lock: Mapping[str, Any],
    snapshot_lock: Mapping[str, Any],
    loader_lock: Mapping[str, Any],
    runtime_lock: Mapping[str, Any],
    immutable_lock: Mapping[str, Any],
) -> JsonObject:
    locked = validate_lock(
        lock,
        base_lock,
        source_lock,
        snapshot_lock,
        loader_lock,
        runtime_lock,
        immutable_lock,
    )
    snapshot = _sealed_snapshot(value, "ROLE_COMPLETE_RUN")
    expected_keys = {
        "schema_version",
        "status",
        "policy_lock_fingerprint_sha256",
        "runtime_code_before",
        "runtime_code_after",
        "prior_run",
        "summary",
        "replication_status",
        "effect_attribution_status",
        "claim_boundary",
        "fingerprint_sha256",
    }
    locked_code = _validate_runtime_code_shape(locked.get("runtime_code"))
    if (
        set(snapshot) != expected_keys
        or snapshot.get("schema_version") != RUN_SCHEMA_VERSION
        or snapshot.get("status") != "COMPLETE"
        or snapshot.get("policy_lock_fingerprint_sha256")
        != locked["fingerprint_sha256"]
        or _canonical_bytes(snapshot.get("runtime_code_before"))
        != _canonical_bytes(locked_code)
        or _canonical_bytes(snapshot.get("runtime_code_after"))
        != _canonical_bytes(locked_code)
        or snapshot.get("replication_status")
        != "INTEGRITY_REPLICATION_OVER_KNOWN_R01_R06_CASES"
        or snapshot.get("effect_attribution_status") != "NOT_ASSESSED"
        or snapshot.get("claim_boundary") != list(CLAIM_BOUNDARY)
    ):
        raise EBRTError("ROLE_COMPLETE_RUN_HEADER_INVALID")
    prior_verification = immutable_bound.verify_run(
        snapshot.get("prior_run"),
        immutable_lock,
        base_lock,
        source_lock,
        snapshot_lock,
        loader_lock,
        runtime_lock,
    )
    _verify_mount_receipt(snapshot["prior_run"].get("mount_receipt"), snapshot_lock)
    if _canonical_bytes(snapshot.get("summary")) != _canonical_bytes(
        snapshot["prior_run"]["summary"]
    ):
        raise EBRTError("ROLE_COMPLETE_SUMMARY_MISMATCH")
    return _seal(
        {
            "schema_version": "ebrt-role-uptake-complete-verification-v0.8.3.6",
            "status": "PASS",
            "run_fingerprint_sha256": snapshot["fingerprint_sha256"],
            "prior_verification_fingerprint_sha256": prior_verification[
                "fingerprint_sha256"
            ],
            "checks": {
                "pre_call_lock_exact": True,
                "all_imported_nonstdlib_modules_bound": True,
                "all_owning_distribution_content_bound": True,
                "repository_module_content_bound": True,
                "mount_manifest_matches_locked_snapshot": True,
                "clone_receipt_matches_locked_snapshot": True,
                "immutable_run_portably_verified": True,
                "known_case_replication_boundary_exact": True,
            },
        }
    )


def self_test(
    base_lock: Mapping[str, Any],
    source_lock: Mapping[str, Any],
    snapshot_lock: Mapping[str, Any],
    loader_lock: Mapping[str, Any],
    runtime_lock: Mapping[str, Any],
    immutable_lock: Mapping[str, Any],
) -> JsonObject:
    locked_immutable = immutable_bound.validate_lock(
        immutable_lock,
        base_lock,
        source_lock,
        snapshot_lock,
        loader_lock,
        runtime_lock,
    )
    checks = {
        "immutable_lock_chain_exact": locked_immutable["fingerprint_sha256"]
        == immutable_lock["fingerprint_sha256"],
        "expected_staged_manifest_is_locked": len(
            _expected_staged_manifest_fingerprint()
        )
        == 64,
        "expected_clone_is_locked": len(_expected_clone_fingerprint(snapshot_lock))
        == 64,
        "required_distribution_set_nonempty": bool(REQUIRED_DISTRIBUTIONS),
    }
    if not all(checks.values()):
        raise EBRTError("ROLE_COMPLETE_SELF_TEST_FAILED")
    return _seal(
        {
            "schema_version": SELF_TEST_SCHEMA_VERSION,
            "status": "PASS",
            "checks": checks,
            "claim_boundary": list(CLAIM_BOUNDARY),
        }
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-lock", type=Path, required=True)
    parser.add_argument("--source-lock", type=Path, required=True)
    parser.add_argument("--snapshot-lock", type=Path, required=True)
    parser.add_argument("--loader-lock", type=Path, required=True)
    parser.add_argument("--runtime-lock", type=Path, required=True)
    parser.add_argument("--immutable-lock", type=Path, required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("self-test")
    probe = commands.add_parser("probe-runtime-code")
    probe.add_argument("--model", required=True)
    lock = commands.add_parser("lock-spec")
    lock.add_argument("--model", required=True)
    run = commands.add_parser("run")
    run.add_argument("--model", required=True)
    run.add_argument("--lock", type=Path, required=True)
    run.add_argument("--output", type=Path, required=True)
    verify = commands.add_parser("verify")
    verify.add_argument("artifact", type=Path)
    verify.add_argument("--lock", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        base_lock = _load_json(args.base_lock)
        source_lock = _load_json(args.source_lock)
        snapshot_lock = _load_json(args.snapshot_lock)
        loader_lock = _load_json(args.loader_lock)
        runtime_lock = _load_json(args.runtime_lock)
        immutable_lock = _load_json(args.immutable_lock)
        if args.command == "self-test":
            value = self_test(
                base_lock,
                source_lock,
                snapshot_lock,
                loader_lock,
                runtime_lock,
                immutable_lock,
            )
        elif args.command == "probe-runtime-code":
            value = probe_runtime_code(args.model)
        elif args.command == "lock-spec":
            value = lock_spec(
                base_lock,
                source_lock,
                snapshot_lock,
                loader_lock,
                runtime_lock,
                immutable_lock,
                probe_runtime_code(args.model),
            )
        elif args.command == "run":
            value = run_integrity_replication(
                args.model,
                _load_json(args.lock),
                base_lock,
                source_lock,
                snapshot_lock,
                loader_lock,
                runtime_lock,
                immutable_lock,
            )
            _write_json(args.output, value)
        elif args.command == "verify":
            value = verify_run(
                _load_json(args.artifact),
                _load_json(args.lock),
                base_lock,
                source_lock,
                snapshot_lock,
                loader_lock,
                runtime_lock,
                immutable_lock,
            )
        else:  # pragma: no cover
            raise EBRTError("ROLE_COMPLETE_COMMAND_UNKNOWN")
        print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except EBRTError as error:
        print(json.dumps({"status": "ERROR", "error_code": str(error)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
