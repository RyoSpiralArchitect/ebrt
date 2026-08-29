#!/usr/bin/env python3
"""Immutable-model and imported-code integrity wrapper for EBRT v0.8.3.

The r06 successor loads the exact locked model from an unlinked read-only disk
image and binds the installed files plus actual origins of the imported local
runtime modules.  It repeats known cases only for integrity.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import re
import subprocess
import sys
import tempfile
from importlib.metadata import distribution, packages_distributions
from pathlib import Path
from typing import Any, Mapping, Sequence

import role_stratified_uptake_canary_v0_8_3 as base
import role_stratified_uptake_integrity_v0_8_3_3 as loader_bound
import role_stratified_uptake_integrity_v0_8_3_4 as runtime_bound
from ebrt_core import (
    EBRTError,
    MLXLocalAdapter,
    SharedMLXRuntime,
    _canonical_bytes,
    _fingerprint,
    _seal,
    _sealed_snapshot,
    build_model_invocation,
)
from local_output_diff_corpus_v0_8_2 import build_direct_invocation


LOCK_SCHEMA_VERSION = "ebrt-role-uptake-immutable-lock-v0.8.3.5"
RUN_SCHEMA_VERSION = "ebrt-role-uptake-immutable-run-v0.8.3.5"
SELF_TEST_SCHEMA_VERSION = "ebrt-role-uptake-immutable-self-test-v0.8.3.5"
RECORDED_DISTRIBUTIONS = tuple(sorted(runtime_bound.EXPECTED_RUNTIME["distributions"]))
CRITICAL_MODULES = (
    "huggingface_hub",
    "mlx.core",
    "mlx_lm",
    "mlx_lm.generate",
    "mlx_lm.sample_utils",
    "mlx_lm.utils",
    "numpy",
    "numpy._core._multiarray_umath",
    "safetensors",
    "safetensors._safetensors_rust",
    "tokenizers",
    "tokenizers.tokenizers",
    "torch",
    "torch._C",
    "transformers",
)
IMMUTABLE_MODEL_POLICY = {
    "source_materialization": "PRIVATE_APFS_COPY_ON_WRITE_CLONE",
    "execution_medium": "UNLINKED_READ_ONLY_APFS_DISK_IMAGE",
    "hdiutil_path": "/usr/bin/hdiutil",
    "image_format": "UDRO",
    "mount_flags": ["readonly", "nobrowse"],
    "backing_image_path_unlinked_before_model_load": True,
    "loader_receives_writable_source_path": False,
    "model_manifest_check": "EXACT_LOCKED_BLOB_HASH_BEFORE_AND_AFTER_CALLS",
}
CLAIM_BOUNDARY = (
    "This r06 execution repeats already observed cases only to bind an owner-nonwritable model medium and imported runtime code.",
    "The repeated outputs are contaminated by known r01-r05 results and are not fresh scientific replication evidence.",
    "The model loader receives an unlinked read-only APFS disk-image mount whose exact seven files are checked before and after calls.",
    "Recorded distribution file sets and actual imported module origins are content-hashed and matched to the pre-call lock.",
    "The receipt is not hardware, kernel, code-signing, or malicious-root attestation.",
    "All original v0.8.3 effect-attribution, one-model, public-role, and stop-gradient boundaries remain unchanged.",
)

JsonObject = dict[str, Any]


def _canonical_distribution_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as source:
            while chunk := source.read(1024 * 1024):
                digest.update(chunk)
    except OSError as error:
        raise EBRTError("ROLE_IMMUTABLE_SOURCE_READ_FAILED") from error
    return digest.hexdigest()


def _load_json(path: Path) -> JsonObject:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise EBRTError("ROLE_IMMUTABLE_ARTIFACT_READ_FAILED") from error
    if not isinstance(value, dict):
        raise EBRTError("ROLE_IMMUTABLE_ARTIFACT_TYPE_INVALID")
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _run_command(arguments: Sequence[str], error_code: str) -> None:
    try:
        completed = subprocess.run(
            list(arguments),
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as error:
        raise EBRTError(error_code) from error
    if completed.returncode != 0:
        raise EBRTError(error_code)


def _distribution_content_receipt() -> tuple[JsonObject, dict[Path, tuple[str, str]]]:
    summaries: list[JsonObject] = []
    origin_index: dict[Path, tuple[str, str]] = {}
    for distribution_name in RECORDED_DISTRIBUTIONS:
        package = distribution(distribution_name)
        rows: list[JsonObject] = []
        files = package.files
        if files is None:
            raise EBRTError("ROLE_IMMUTABLE_DISTRIBUTION_FILES_MISSING")
        for item in sorted(files, key=lambda value: str(value)):
            if item.hash is None:
                continue
            try:
                path = Path(package.locate_file(item)).resolve(strict=True)
            except OSError as error:
                raise EBRTError("ROLE_IMMUTABLE_DISTRIBUTION_FILE_MISSING") from error
            if not path.is_file():
                raise EBRTError("ROLE_IMMUTABLE_DISTRIBUTION_FILE_INVALID")
            row = {
                "relative_path": str(item),
                "size_bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
            rows.append(row)
            origin_index[path] = (distribution_name, str(item))
        if not rows:
            raise EBRTError("ROLE_IMMUTABLE_DISTRIBUTION_MANIFEST_EMPTY")
        summaries.append(
            {
                "distribution": distribution_name,
                "version": package.version,
                "hashed_file_count": len(rows),
                "hashed_bytes": sum(row["size_bytes"] for row in rows),
                "files_fingerprint_sha256": _fingerprint(rows),
            }
        )
    return (
        _seal(
            {
                "schema_version": "ebrt-distribution-content-summary-v0.8.3.5",
                "distributions": summaries,
            }
        ),
        origin_index,
    )


def _imported_module_receipt(
    origin_index: Mapping[Path, tuple[str, str]],
) -> JsonObject:
    admitted = {_canonical_distribution_name(value) for value in RECORDED_DISTRIBUTIONS}
    package_map = packages_distributions()
    rows: list[JsonObject] = []
    critical_rows: list[JsonObject] = []
    seen: set[str] = set()
    for module_name, module in sorted(sys.modules.items()):
        top_level = module_name.split(".", 1)[0]
        mapped_distributions = {
            _canonical_distribution_name(value)
            for value in package_map.get(top_level, [])
        }
        if not admitted.intersection(mapped_distributions):
            continue
        origin_value = getattr(module, "__file__", None)
        if origin_value is None:
            continue
        origin_path = Path(origin_value)
        if not origin_path.is_absolute():
            top_module = sys.modules.get(top_level)
            top_origin = getattr(top_module, "__file__", None)
            if top_origin is None:
                raise EBRTError("ROLE_IMMUTABLE_MODULE_ORIGIN_MISSING")
            origin_path = Path(top_origin).parent / origin_path
        try:
            origin = origin_path.resolve(strict=True)
        except OSError as error:
            raise EBRTError("ROLE_IMMUTABLE_MODULE_ORIGIN_MISSING") from error
        binding = origin_index.get(origin)
        if binding is None:
            raise EBRTError("ROLE_IMMUTABLE_MODULE_ORIGIN_OUTSIDE_DISTRIBUTION")
        distribution_name, relative_path = binding
        row = {
            "module": module_name,
            "distribution": distribution_name,
            "distribution_relative_path": relative_path,
            "size_bytes": origin.stat().st_size,
            "sha256": _sha256(origin),
        }
        rows.append(row)
        seen.add(module_name)
        if module_name in CRITICAL_MODULES:
            critical_rows.append(row)
    missing = sorted(set(CRITICAL_MODULES) - seen)
    if missing:
        raise EBRTError("ROLE_IMMUTABLE_CRITICAL_MODULE_MISSING")
    return _seal(
        {
            "schema_version": "ebrt-imported-module-summary-v0.8.3.5",
            "module_count": len(rows),
            "all_origins_within_recorded_distributions": True,
            "module_manifest_fingerprint_sha256": _fingerprint(rows),
            "critical_modules": critical_rows,
        }
    )


def _runtime_code_receipt() -> JsonObject:
    for module_name in CRITICAL_MODULES:
        try:
            importlib.import_module(module_name)
        except ImportError as error:
            raise EBRTError("ROLE_IMMUTABLE_CRITICAL_MODULE_IMPORT_FAILED") from error
    distributions, origin_index = _distribution_content_receipt()
    modules = _imported_module_receipt(origin_index)
    return _seal(
        {
            "schema_version": "ebrt-runtime-code-receipt-v0.8.3.5",
            "distribution_content": distributions,
            "imported_modules": modules,
        }
    )


def _prepare_runtime(model_path: str) -> tuple[SharedMLXRuntime, JsonObject]:
    runtime = SharedMLXRuntime(
        model_path,
        model_id=base.MODEL_ID,
        max_tokens=base.DEFAULT_MAX_TOKENS,
        seed=0,
        prompt_rendering_mode="chat_template",
    )
    runtime._load()
    rendered = runtime._tokenizer.apply_chat_template(
        [{"role": "user", "content": "EBRT runtime-code probe."}],
        tokenize=False,
        add_generation_prompt=True,
    )
    if not isinstance(rendered, str) or not rendered:
        raise EBRTError("ROLE_IMMUTABLE_CHAT_TEMPLATE_PROBE_FAILED")
    return runtime, _runtime_code_receipt()


def probe_runtime_code(model_path: str) -> JsonObject:
    _runtime, receipt = _prepare_runtime(model_path)
    return receipt


def _validate_runtime_code_shape(value: Any) -> JsonObject:
    receipt = _sealed_snapshot(value, "ROLE_IMMUTABLE_RUNTIME_CODE")
    if (
        set(receipt)
        != {
            "schema_version",
            "distribution_content",
            "imported_modules",
            "fingerprint_sha256",
        }
        or receipt.get("schema_version") != "ebrt-runtime-code-receipt-v0.8.3.5"
    ):
        raise EBRTError("ROLE_IMMUTABLE_RUNTIME_CODE_SHAPE_INVALID")
    distributions = _sealed_snapshot(
        receipt.get("distribution_content"), "ROLE_IMMUTABLE_DISTRIBUTIONS"
    )
    distribution_rows = distributions.get("distributions")
    if (
        distributions.get("schema_version")
        != "ebrt-distribution-content-summary-v0.8.3.5"
        or not isinstance(distribution_rows, list)
        or [row.get("distribution") for row in distribution_rows]
        != list(RECORDED_DISTRIBUTIONS)
        or any(
            not isinstance(row, Mapping)
            or set(row)
            != {
                "distribution",
                "version",
                "hashed_file_count",
                "hashed_bytes",
                "files_fingerprint_sha256",
            }
            or row.get("version")
            != runtime_bound.EXPECTED_RUNTIME["distributions"].get(
                row.get("distribution")
            )
            or type(row.get("hashed_file_count")) is not int
            or row["hashed_file_count"] <= 0
            or type(row.get("hashed_bytes")) is not int
            or row["hashed_bytes"] <= 0
            or not isinstance(row.get("files_fingerprint_sha256"), str)
            or len(row["files_fingerprint_sha256"]) != 64
            for row in distribution_rows
        )
    ):
        raise EBRTError("ROLE_IMMUTABLE_DISTRIBUTION_SUMMARY_INVALID")
    modules = _sealed_snapshot(
        receipt.get("imported_modules"), "ROLE_IMMUTABLE_MODULES"
    )
    critical = modules.get("critical_modules")
    if (
        modules.get("schema_version") != "ebrt-imported-module-summary-v0.8.3.5"
        or type(modules.get("module_count")) is not int
        or modules["module_count"] < len(CRITICAL_MODULES)
        or modules.get("all_origins_within_recorded_distributions") is not True
        or not isinstance(modules.get("module_manifest_fingerprint_sha256"), str)
        or len(modules["module_manifest_fingerprint_sha256"]) != 64
        or not isinstance(critical, list)
        or [row.get("module") for row in critical] != list(CRITICAL_MODULES)
    ):
        raise EBRTError("ROLE_IMMUTABLE_MODULE_SUMMARY_INVALID")
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
            or row.get("distribution") not in RECORDED_DISTRIBUTIONS
            or not isinstance(row.get("distribution_relative_path"), str)
            or not row["distribution_relative_path"]
            or type(row.get("size_bytes")) is not int
            or row["size_bytes"] <= 0
            or not isinstance(row.get("sha256"), str)
            or len(row["sha256"]) != 64
        ):
            raise EBRTError("ROLE_IMMUTABLE_CRITICAL_MODULE_ROW_INVALID")
    return receipt


def lock_spec(
    base_lock: Mapping[str, Any],
    source_lock: Mapping[str, Any],
    snapshot_lock: Mapping[str, Any],
    loader_lock: Mapping[str, Any],
    runtime_lock: Mapping[str, Any],
    runtime_code: Mapping[str, Any],
) -> JsonObject:
    locked_runtime = runtime_bound.validate_lock(
        runtime_lock,
        base_lock,
        source_lock,
        snapshot_lock,
        loader_lock,
    )
    code = _validate_runtime_code_shape(runtime_code)
    return _seal(
        {
            "schema_version": LOCK_SCHEMA_VERSION,
            "status": "LOCKED_BEFORE_PROVIDER_CALLS",
            "wrapper_sha256": _sha256(Path(__file__)),
            "runtime_lock_fingerprint_sha256": locked_runtime["fingerprint_sha256"],
            "runtime_code": code,
            "runtime_code_fingerprint_sha256": code["fingerprint_sha256"],
            "immutable_model_policy": IMMUTABLE_MODEL_POLICY,
            "replication_status": "INTEGRITY_REPLICATION_OVER_KNOWN_R01_R05_CASES",
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
) -> JsonObject:
    observed = _sealed_snapshot(value, "ROLE_IMMUTABLE_LOCK")
    runtime_code = _validate_runtime_code_shape(observed.get("runtime_code"))
    expected = lock_spec(
        base_lock,
        source_lock,
        snapshot_lock,
        loader_lock,
        runtime_lock,
        runtime_code,
    )
    if _canonical_bytes(observed) != _canonical_bytes(expected):
        raise EBRTError("ROLE_IMMUTABLE_LOCK_MISMATCH")
    return observed


def _run_canary_with_runtime(
    runtime: SharedMLXRuntime, base_lock: Mapping[str, Any]
) -> JsonObject:
    locked = base.validate_lock(base_lock)
    descriptor = MLXLocalAdapter(
        runtime, adapter_id="role-uptake-canary-model"
    ).descriptor
    if descriptor.model_id != base.MODEL_ID:
        raise EBRTError("ROLE_IMMUTABLE_MODEL_ID_MISMATCH")
    cells: list[JsonObject] = []
    for index, case in enumerate(base.build_cases()):
        top_k, role, compile_receipt = base.compile_case(case)
        programs = {base.ARM_TOP_K: top_k, base.ARM_ROLE: role}
        invocations = {
            base.ARM_DIRECT: build_direct_invocation(case.task),
            base.ARM_TOP_K: build_model_invocation(
                case.task, top_k, prompt_policy="credit_first"
            ),
            base.ARM_ROLE: build_model_invocation(
                case.task, role, prompt_policy="credit_first"
            ),
        }
        results: dict[str, JsonObject] = {}
        for arm_id in base.CALL_SCHEDULES[index]:
            results[arm_id] = base._invoke(
                runtime,
                case.task,
                invocations[arm_id],
            )
        semantic = {
            arm_id: base._common_output_grade(results[arm_id], case.contract)
            for arm_id in base.ARM_IDS
        }
        uptake = {
            arm_id: base.provider_uptake(
                case.task,
                programs[arm_id],
                results[arm_id],
            )
            for arm_id in (base.ARM_TOP_K, base.ARM_ROLE)
        }
        cells.append(
            _seal(
                {
                    "case_id": case.task.task_id,
                    "family": case.family,
                    "task": case.task.to_public_dict(),
                    "post_call_contract": case.contract.to_dict(),
                    "call_order": list(base.CALL_SCHEDULES[index]),
                    "compiled": {
                        "trajectory": compile_receipt["trajectory"],
                        base.ARM_TOP_K: {
                            "program": top_k.to_dict(),
                            "coverage": base.compiler_coverage(case.task, top_k),
                        },
                        base.ARM_ROLE: {
                            "program": role.to_dict(),
                            "coverage": base.compiler_coverage(case.task, role),
                        },
                    },
                    "arms": {
                        arm_id: {
                            "invocation_fingerprint_sha256": invocations[arm_id][
                                "fingerprint_sha256"
                            ],
                            "result": results[arm_id],
                            "semantic_grade": semantic[arm_id],
                            "provider_uptake": uptake.get(arm_id),
                        }
                        for arm_id in base.ARM_IDS
                    },
                    "diffs": {
                        "direct_to_top_k": base._output_diff(
                            base.ARM_DIRECT,
                            results[base.ARM_DIRECT],
                            base.ARM_TOP_K,
                            results[base.ARM_TOP_K],
                        ),
                        "top_k_to_role": base._output_diff(
                            base.ARM_TOP_K,
                            results[base.ARM_TOP_K],
                            base.ARM_ROLE,
                            results[base.ARM_ROLE],
                        ),
                    },
                }
            )
        )
    return _seal(
        {
            "schema_version": base.RUN_SCHEMA_VERSION,
            "status": "COMPLETE",
            "policy_lock_fingerprint_sha256": locked["fingerprint_sha256"],
            "model_adapter": descriptor.to_dict(),
            "execution_policy": locked["execution_policy"],
            "cases": cells,
            "summary": base._summary(cells),
            "native_state_capture_status": "DISABLED",
            "effect_attribution_status": "NOT_ASSESSED",
            "generalization_status": "ONE_MODEL_DEVELOPMENT_CANARY_ONLY",
            "claim_boundary": list(base.CLAIM_BOUNDARY),
        }
    )


def _mounted_model_run(
    model_path: str,
    base_lock: Mapping[str, Any],
    locked_runtime_code: Mapping[str, Any],
) -> tuple[JsonObject, JsonObject, JsonObject, JsonObject]:
    mounted = False
    with tempfile.TemporaryDirectory(prefix="ebrt-v0835-") as temporary:
        root = Path(temporary)
        source = root / "source"
        mountpoint = root / "mount"
        image = root / "model.dmg"
        source.mkdir(mode=0o700)
        mountpoint.mkdir(mode=0o700)
        clone_receipt = loader_bound._clone_exact_snapshot(model_path, source)
        _run_command(
            (
                "/usr/bin/hdiutil",
                "create",
                "-quiet",
                "-srcfolder",
                str(source),
                "-format",
                "UDRO",
                "-volname",
                "EBRT_LOCKED_MODEL",
                str(image),
            ),
            "ROLE_IMMUTABLE_IMAGE_CREATE_FAILED",
        )
        try:
            _run_command(
                (
                    "/usr/bin/hdiutil",
                    "attach",
                    "-quiet",
                    "-readonly",
                    "-nobrowse",
                    "-mountpoint",
                    str(mountpoint),
                    str(image),
                ),
                "ROLE_IMMUTABLE_IMAGE_ATTACH_FAILED",
            )
            mounted = True
            image.unlink()
            if image.exists() or not os.statvfs(mountpoint).f_flag & os.ST_RDONLY:
                raise EBRTError("ROLE_IMMUTABLE_MOUNT_NOT_READ_ONLY")
            manifest_before = loader_bound._validate_staged_tree(mountpoint)
            runtime, runtime_code_before = _prepare_runtime(str(mountpoint))
            if _canonical_bytes(runtime_code_before) != _canonical_bytes(
                locked_runtime_code
            ):
                raise EBRTError("ROLE_IMMUTABLE_RUNTIME_CODE_MISMATCH")
            base_run = _run_canary_with_runtime(runtime, base_lock)
            runtime_code_after = _runtime_code_receipt()
            if _canonical_bytes(runtime_code_after) != _canonical_bytes(
                locked_runtime_code
            ):
                raise EBRTError("ROLE_IMMUTABLE_RUNTIME_CODE_CHANGED")
            manifest_after = loader_bound._validate_staged_tree(mountpoint)
            if _canonical_bytes(manifest_before) != _canonical_bytes(manifest_after):
                raise EBRTError("ROLE_IMMUTABLE_MODEL_BYTES_CHANGED")
            mount_receipt = _seal(
                {
                    "status": "PASS",
                    "filesystem_read_only": True,
                    "backing_image_path_unlinked_before_model_load": True,
                    "loader_received_only_mount_path": True,
                    "source_clone_fingerprint_sha256": clone_receipt[
                        "fingerprint_sha256"
                    ],
                    "model_manifest_fingerprint_before": manifest_before[
                        "fingerprint_sha256"
                    ],
                    "model_manifest_fingerprint_after": manifest_after[
                        "fingerprint_sha256"
                    ],
                }
            )
            return base_run, mount_receipt, runtime_code_before, runtime_code_after
        finally:
            if mounted:
                _run_command(
                    ("/usr/bin/hdiutil", "detach", "-quiet", str(mountpoint)),
                    "ROLE_IMMUTABLE_IMAGE_DETACH_FAILED",
                )


def run_integrity_replication(
    model_path: str,
    lock: Mapping[str, Any],
    base_lock: Mapping[str, Any],
    source_lock: Mapping[str, Any],
    snapshot_lock: Mapping[str, Any],
    loader_lock: Mapping[str, Any],
    runtime_lock: Mapping[str, Any],
) -> JsonObject:
    locked = validate_lock(
        lock,
        base_lock,
        source_lock,
        snapshot_lock,
        loader_lock,
        runtime_lock,
    )
    runtime_before = runtime_bound._validate_runtime()
    base_run, mount_receipt, code_before, code_after = _mounted_model_run(
        model_path,
        base_lock,
        locked["runtime_code"],
    )
    runtime_after = runtime_bound._validate_runtime()
    if _canonical_bytes(runtime_before) != _canonical_bytes(runtime_after):
        raise EBRTError("ROLE_IMMUTABLE_RUNTIME_VERSION_CHANGED")
    return _seal(
        {
            "schema_version": RUN_SCHEMA_VERSION,
            "status": "COMPLETE",
            "policy_lock_fingerprint_sha256": locked["fingerprint_sha256"],
            "mount_receipt": mount_receipt,
            "runtime_version_before": runtime_before,
            "runtime_version_after": runtime_after,
            "runtime_code_before": code_before,
            "runtime_code_after": code_after,
            "base_run": base_run,
            "summary": base_run["summary"],
            "replication_status": "INTEGRITY_REPLICATION_OVER_KNOWN_R01_R05_CASES",
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
) -> JsonObject:
    locked = validate_lock(
        lock,
        base_lock,
        source_lock,
        snapshot_lock,
        loader_lock,
        runtime_lock,
    )
    snapshot = _sealed_snapshot(value, "ROLE_IMMUTABLE_RUN")
    expected_keys = {
        "schema_version",
        "status",
        "policy_lock_fingerprint_sha256",
        "mount_receipt",
        "runtime_version_before",
        "runtime_version_after",
        "runtime_code_before",
        "runtime_code_after",
        "base_run",
        "summary",
        "replication_status",
        "effect_attribution_status",
        "claim_boundary",
        "fingerprint_sha256",
    }
    mount = _sealed_snapshot(snapshot.get("mount_receipt"), "ROLE_IMMUTABLE_MOUNT")
    locked_runtime = _sealed_snapshot(runtime_lock.get("runtime"), "ROLE_RUNTIME")
    locked_code = _validate_runtime_code_shape(locked.get("runtime_code"))
    expected_mount_keys = {
        "status",
        "filesystem_read_only",
        "backing_image_path_unlinked_before_model_load",
        "loader_received_only_mount_path",
        "source_clone_fingerprint_sha256",
        "model_manifest_fingerprint_before",
        "model_manifest_fingerprint_after",
        "fingerprint_sha256",
    }
    if (
        set(snapshot) != expected_keys
        or snapshot.get("schema_version") != RUN_SCHEMA_VERSION
        or snapshot.get("status") != "COMPLETE"
        or snapshot.get("policy_lock_fingerprint_sha256")
        != locked["fingerprint_sha256"]
        or set(mount) != expected_mount_keys
        or mount.get("status") != "PASS"
        or mount.get("filesystem_read_only") is not True
        or mount.get("backing_image_path_unlinked_before_model_load") is not True
        or mount.get("loader_received_only_mount_path") is not True
        or mount.get("model_manifest_fingerprint_before")
        != mount.get("model_manifest_fingerprint_after")
        or _canonical_bytes(snapshot.get("runtime_version_before"))
        != _canonical_bytes(locked_runtime)
        or _canonical_bytes(snapshot.get("runtime_version_after"))
        != _canonical_bytes(locked_runtime)
        or _canonical_bytes(snapshot.get("runtime_code_before"))
        != _canonical_bytes(locked_code)
        or _canonical_bytes(snapshot.get("runtime_code_after"))
        != _canonical_bytes(locked_code)
        or snapshot.get("replication_status")
        != "INTEGRITY_REPLICATION_OVER_KNOWN_R01_R05_CASES"
        or snapshot.get("effect_attribution_status") != "NOT_ASSESSED"
        or snapshot.get("claim_boundary") != list(CLAIM_BOUNDARY)
    ):
        raise EBRTError("ROLE_IMMUTABLE_RUN_HEADER_INVALID")
    base_verification = base.verify_run(snapshot.get("base_run"), base_lock)
    if _canonical_bytes(snapshot.get("summary")) != _canonical_bytes(
        snapshot["base_run"]["summary"]
    ):
        raise EBRTError("ROLE_IMMUTABLE_SUMMARY_MISMATCH")
    return _seal(
        {
            "schema_version": "ebrt-role-uptake-immutable-verification-v0.8.3.5",
            "status": "PASS",
            "run_fingerprint_sha256": snapshot["fingerprint_sha256"],
            "base_verification_fingerprint_sha256": base_verification[
                "fingerprint_sha256"
            ],
            "checks": {
                "pre_call_lock_exact": True,
                "owner_nonwritable_model_mount": True,
                "backing_image_path_unlinked": True,
                "exact_model_manifest_unchanged": True,
                "distribution_file_content_bound": True,
                "imported_module_origins_and_hashes_bound": True,
                "runtime_versions_unchanged": True,
                "base_run_portably_verified": True,
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
) -> JsonObject:
    locked_runtime = runtime_bound.validate_lock(
        runtime_lock,
        base_lock,
        source_lock,
        snapshot_lock,
        loader_lock,
    )
    checks = {
        "runtime_lock_chain_exact": locked_runtime["fingerprint_sha256"]
        == runtime_lock["fingerprint_sha256"],
        "disk_image_format_is_read_only": IMMUTABLE_MODEL_POLICY["image_format"]
        == "UDRO",
        "backing_path_must_be_unlinked": IMMUTABLE_MODEL_POLICY[
            "backing_image_path_unlinked_before_model_load"
        ]
        is True,
        "writable_source_never_reaches_loader": IMMUTABLE_MODEL_POLICY[
            "loader_receives_writable_source_path"
        ]
        is False,
        "critical_module_set_nonempty": bool(CRITICAL_MODULES),
    }
    if not all(checks.values()):
        raise EBRTError("ROLE_IMMUTABLE_SELF_TEST_FAILED")
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
        if args.command == "self-test":
            value = self_test(
                base_lock,
                source_lock,
                snapshot_lock,
                loader_lock,
                runtime_lock,
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
            )
        else:  # pragma: no cover
            raise EBRTError("ROLE_IMMUTABLE_COMMAND_UNKNOWN")
        print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except EBRTError as error:
        print(json.dumps({"status": "ERROR", "error_code": str(error)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
