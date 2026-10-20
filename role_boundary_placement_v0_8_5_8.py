#!/usr/bin/env python3
"""One role-boundary placement experiment, portable across MLX, TRT-LLM and API.

No core changes or gradient intervention. Same public prompts and strict grader;
separate sealed backend profiles, readiness gates, costs and result denominators.
"""

from __future__ import annotations

import argparse
from collections import Counter
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import time
from typing import Any

import source_field_ablation_v0_8_5_7 as previous
from ebrt_core import (
    EBRTError,
    SharedMLXRuntime,
    _seal,
    _sealed_snapshot,
)

ROOT = Path(__file__).resolve().parent
VERSION = "v0.8.5.8"
BASE_COMMIT = "1a799f40e2466c9a48fe7cef13a9677eebf731d9"
DEPENDENCIES = (Path(__file__).name, *previous.DEPENDENCIES)
t = previous.transport
d = previous.diagnostic
READY = ("state_format", "state_task")
SCHEDULE = (
    ("pair1_early", "early"),
    ("pair1_late", "late"),
    ("pair2_late", "late"),
    ("pair2_early", "early"),
)
ORDER = (*READY, *(key for key, _ in SCHEDULE))
ROLE_LINES = (
    "decision_support_ids must contain only evidence that directly determines answer.",
    "revision_event_id must contain the late correction that authorizes revision.",
    "preserved_constraint_ids must contain stable constraints that must remain unchanged but do not determine answer.",
    "Keep the three evidence destinations pairwise disjoint.",
    "Do not cite superseded evidence in any destination.",
)
API_MODEL = "gpt-5.6-sol"
API_CAP_MICRO_USD = 400_000
API_INPUT_RATE = 5  # Conservative: $4/M input * 1.25 cache-write rate.
API_OUTPUT_RATE = 20
BACKENDS = ("mlx", "furnace", "openai")
BOUNDARY = {
    "scope": "ONE_CONTAMINATED_CASE_RECORDED_CALCULATION_AB_BA",
    "intervention": "MOVE_EXISTING_FIVE_ROLE_LINES_WITHOUT_ADDING_OR_DUPLICATING_TEXT",
    "numeric_source": "OLD_ACTUAL_CALCULATION_NO_NEW_CALCULATOR",
    "gold_in_provider_input": False,
    "grader_changed": False,
    "gradient_utility": "NOT_ASSESSED_NO_GRADIENT_INTERVENTION",
    "cross_backend": "PORTABILITY_NOT_MATCHED_COMPUTE_OR_MODEL_SUPERIORITY",
    "private_reasoning": "NOT_OBSERVED",
    "default_promotion": "NONE",
}
Json = dict[str, Any]


def require(ok: bool, code: str) -> None:
    if not ok:
        raise EBRTError("V0858_" + code)


def compile_prompts() -> Json:
    source = previous.recorded_source()
    early = previous.compile_final(
        d.numeric_case().task, "without_source", source["raw_text"]
    )
    lines = early["prompt"].split("\n")
    require(all(lines.count(line) == 1 for line in ROLE_LINES), "ROLE_LINES_NOT_UNIQUE")
    block = "\n".join(ROLE_LINES)
    require(block in early["prompt"], "ROLE_BLOCK_NOT_CONTIGUOUS")
    remainder = [line for line in lines if line not in ROLE_LINES]
    end = remainder.index("END_PUBLIC_CALCULATION_RECORD") + 1
    late = "\n".join(remainder[:end] + list(ROLE_LINES) + remainder[end:])
    require(Counter(late.split("\n")) == Counter(lines), "CONTENT_CHANGED")
    prompts = {key: previous.bridge.static_prompts()[key] for key in READY}
    prompts.update(
        {key: early["prompt"] if arm == "early" else late for key, arm in SCHEDULE}
    )
    return {
        key: _seal(
            {
                "key": key,
                "arm": dict(SCHEDULE).get(key),
                "prompt": prompt,
                "prompt_sha256": t.sha(prompt),
            }
        )
        for key, prompt in prompts.items()
    }


def protocol() -> Json:
    old_root = ROOT / "artifacts/source_field_ablation_v0_8_5_7/r01"
    old_lock = ROOT / "policy_lock_source_field_ablation_v0_8_5_7.json"
    old = t.load_json(old_root / "results.json")
    require(
        old["fingerprint_sha256"]
        == "000bcf5324141fd47a979c9ee1db77622b6e6c7a8dd24c814bf019f37ddb1a57",
        "OLD_RESULT_CHANGED",
    )
    previous.verify_run(
        old, t.load_json(old_lock), previous.read_journal(old_root / "journal.jsonl")
    )
    inputs = (
        *previous.SOURCE_FILES,
        str(old_lock.relative_to(ROOT)),
        *(
            str((old_root / name).relative_to(ROOT))
            for name in ("results.json", "journal.jsonl", "verification.json")
        ),
    )
    return _seal(
        {
            "schema_version": "ebrt-role-placement-protocol-" + VERSION,
            "base_commit": BASE_COMMIT,
            "source_sha256": {name: t.file_sha(ROOT / name) for name in DEPENDENCIES},
            "recorded_inputs_sha256": {
                name: t.file_sha(ROOT / name) for name in inputs
            },
            "source_receipt": previous.recorded_source(),
            "invocations": compile_prompts(),
            "call_order": list(ORDER),
            "maximum_generations_per_backend": 6,
            "automatic_retry": False,
            "post_call_contract": d.numeric_case().contract.to_dict(),
            "claim_boundary": BOUNDARY,
        }
    )


def validate_protocol(value: Json) -> Json:
    value = _sealed_snapshot(value, "V0858_PROTOCOL")
    require(value == protocol(), "PROTOCOL_CHANGED")
    return value


def identity(backend: str) -> Json:
    packages = {
        "mlx": ("torch", "mlx", "mlx-lm", "transformers", "tokenizers"),
        "furnace": (
            "torch",
            "tensorrt-llm",
            "transformers",
            "tokenizers",
            "nvidia-modelopt",
        ),
        "openai": ("torch", "openai"),
    }[backend]
    return {
        "python": platform.python_version(),
        "machine": platform.machine(),
        "packages": {name: importlib.metadata.version(name) for name in packages},
    }


def api_request(prompt: str) -> Json:
    return {
        "model": API_MODEL,
        "input": prompt,
        "reasoning": {"effort": "low"},
        "max_output_tokens": 2048,
        "store": False,
        "service_tier": "default",
    }


def api_client():
    from openai import OpenAI

    require(bool(os.environ.get("OPENAI_API_KEY")), "API_KEY_UNAVAILABLE")
    # Never inherit a proxy endpoint or transmit credentials to a caller-supplied host.
    return OpenAI(base_url="https://api.openai.com/v1", max_retries=0, timeout=60.0)


def preflight(backend: str, model_path: str | None, locked: Json) -> Json:
    validate_protocol(locked)
    require(backend in BACKENDS, "BACKEND_INVALID")
    os.environ.update(
        HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1"
    )
    rendered, files, runtime_config, cost = {}, {}, {}, None
    if backend == "openai":
        client = api_client()
        require(client.models.retrieve(API_MODEL).id == API_MODEL, "API_MODEL_MISMATCH")
        counts = {}
        for key, row in locked["invocations"].items():
            request = api_request(row["prompt"])
            if row["prompt_sha256"] not in counts:
                n = client.responses.input_tokens.count(
                    model=API_MODEL, input=row["prompt"], reasoning={"effort": "low"}
                ).input_tokens
                require(type(n) is int and 0 < n <= 4096, "API_INPUT_BUDGET")
                counts[row["prompt_sha256"]] = n
            rendered[key] = _seal(
                {"request": request, "input_tokens": counts[row["prompt_sha256"]]}
            )
        worst = sum(
            row["input_tokens"] * API_INPUT_RATE + 2048 * API_OUTPUT_RATE
            for row in rendered.values()
        )
        require(worst <= API_CAP_MICRO_USD, "API_TOTAL_BUDGET")
        cost = {
            "rates_checked_on": "2026-10-20",
            "max_total_micro_usd": API_CAP_MICRO_USD,
            "reserved_worst_case_micro_usd": worst,
            "input_micro_usd_per_token": API_INPUT_RATE,
            "output_micro_usd_per_token": API_OUTPUT_RATE,
            "source": "https://developers.openai.com/api/docs/models/gpt-5.6-sol",
            "metadata_requests": 1,
            "input_count_requests": len(counts),
        }
        model_id, model_path = API_MODEL, None
        runtime_config = {
            "max_retries": 0,
            "timeout_seconds": 60,
            "base_url": "https://api.openai.com/v1",
        }
    else:
        require(model_path is not None, "MODEL_PATH_REQUIRED")
        path = Path(model_path).expanduser().absolute()
        require(path.is_dir(), "MODEL_NOT_FOUND")
        if backend == "mlx":
            runtime = SharedMLXRuntime(str(path), max_tokens=96)
            require(runtime.model_id == previous.MODEL_ID, "MLX_MODEL_MISMATCH")
            from mlx_lm.utils import load_tokenizer

            tokenizer = load_tokenizer(
                path,
                {"local_files_only": True},
                eos_token_ids=t.load_json(path / "config.json").get("eos_token_id"),
            )
            model_id = runtime.model_id
            runtime_config = {
                "seed": 0,
                "temperature": 0.0,
                "max_tokens": 96,
                "cross_call_kv_cache": "NONE",
            }
        else:
            require(
                path.name == "c170c708c41dac9275d15a8fff4eca08d52bab71"
                and path.parent.parent.name
                == "models--mistralai--Mistral-7B-Instruct-v0.3",
                "FURNACE_SNAPSHOT_INVALID",
            )
            require(
                sys.executable.startswith(
                    "/home/ryospiralarchitect/.venvs/aether-synth-trtllm-1.2.1-cu131-py312/"
                ),
                "MANAGED_RUNTIME_REQUIRED",
            )
            import torch

            require(torch.cuda.is_available(), "CUDA_UNAVAILABLE")
            from transformers import AutoTokenizer

            tokenizer = AutoTokenizer.from_pretrained(
                path, local_files_only=True, trust_remote_code=False
            )
            model_id = "mistralai/Mistral-7B-Instruct-v0.3@" + path.name
            runtime_config = {
                "backend": "pytorch",
                "dtype": "bfloat16",
                "tensor_parallel_size": 1,
                "max_batch_size": 1,
                "max_seq_len": 4096,
                "max_num_tokens": 4096,
                "enable_chunked_prefill": False,
                "disable_overlap_scheduler": True,
                "kv_cache": {
                    "enable_block_reuse": False,
                    "enable_partial_reuse": False,
                    "max_tokens": 4096,
                    "free_gpu_memory_fraction": 0.2,
                },
                "sampling": {"max_tokens": 96, "temperature": 0.0, "seed": 0},
                "gpu": torch.cuda.get_device_name(0),
            }
        rendered = {
            key: previous.bridge.validate_render(
                t.render(tokenizer, row["prompt"]), row["prompt"]
            )
            for key, row in locked["invocations"].items()
        }
        files = t.snapshot_files(path)
        model_path = str(path)
    return _seal(
        {
            "schema_version": "ebrt-role-placement-profile-" + VERSION,
            "status": "PASS_ZERO_GENERATION",
            "backend": backend,
            "protocol_sha256": locked["fingerprint_sha256"],
            "model_id": model_id,
            "model_path": model_path,
            "snapshot_files": files,
            "runtime": identity(backend),
            "runtime_config": runtime_config,
            "rendered": rendered,
            "api_cost_policy": cost,
            "generation_calls": 0,
        }
    )


def validate_profile(value: Json, locked: Json) -> Json:
    p = _sealed_snapshot(value, "V0858_PROFILE")
    require(
        set(p)
        == {
            "schema_version",
            "status",
            "backend",
            "protocol_sha256",
            "model_id",
            "model_path",
            "snapshot_files",
            "runtime",
            "runtime_config",
            "rendered",
            "api_cost_policy",
            "generation_calls",
            "fingerprint_sha256",
        },
        "PROFILE_SHAPE",
    )
    require(
        p["schema_version"] == "ebrt-role-placement-profile-" + VERSION
        and p["protocol_sha256"] == locked["fingerprint_sha256"],
        "PROFILE_BINDING",
    )
    require(
        p["backend"] in BACKENDS
        and p["status"] == "PASS_ZERO_GENERATION"
        and type(p["generation_calls"]) is int
        and p["generation_calls"] == 0,
        "PROFILE_INVALID",
    )
    require(set(p["rendered"]) == set(ORDER), "PROFILE_CALLS")
    for key, row in p["rendered"].items():
        _sealed_snapshot(row, "V0858_RENDER")
        if p["backend"] == "openai":
            require(
                row["request"] == api_request(locked["invocations"][key]["prompt"]),
                "API_REQUEST_CHANGED",
            )
            require(
                type(row["input_tokens"]) is int and 0 < row["input_tokens"] <= 4096,
                "API_INPUT_BUDGET",
            )
        else:
            previous.bridge.validate_render(row, locked["invocations"][key]["prompt"])
    if p["backend"] == "openai":
        policy = p["api_cost_policy"]
        worst = sum(
            row["input_tokens"] * API_INPUT_RATE + 2048 * API_OUTPUT_RATE
            for row in p["rendered"].values()
        )
        require(
            policy["reserved_worst_case_micro_usd"] == worst <= API_CAP_MICRO_USD
            and policy["max_total_micro_usd"] == API_CAP_MICRO_USD,
            "API_COST_POLICY",
        )
        require(
            policy["input_micro_usd_per_token"] == API_INPUT_RATE
            and policy["output_micro_usd_per_token"] == API_OUTPUT_RATE,
            "API_RATES_CHANGED",
        )
        require(
            p["model_id"] == API_MODEL
            and p["runtime_config"]
            == {
                "max_retries": 0,
                "timeout_seconds": 60,
                "base_url": "https://api.openai.com/v1",
            },
            "API_RUNTIME_CHANGED",
        )
    else:
        expected_id = (
            previous.MODEL_ID
            if p["backend"] == "mlx"
            else "mistralai/Mistral-7B-Instruct-v0.3@c170c708c41dac9275d15a8fff4eca08d52bab71"
        )
        require(
            p["model_id"] == expected_id
            and p["api_cost_policy"] is None
            and type(p["model_path"]) is str,
            "LOCAL_PROFILE_IDENTITY",
        )
        require(
            type(p["snapshot_files"]) is dict and bool(p["snapshot_files"]),
            "SNAPSHOT_INVALID",
        )
        for name, file in p["snapshot_files"].items():
            require(
                name == Path(name).name
                and set(file) == {"size", "sha256"}
                and type(file["size"]) is int
                and file["size"] >= 0
                and type(file["sha256"]) is str
                and re.fullmatch(r"[0-9a-f]{64}", file["sha256"]) is not None,
                "SNAPSHOT_INVALID",
            )
    return p


class Runtime:
    def __init__(self, profile: Json):
        self.p, self.engine = profile, None

    def invoke(self, key: str, prompt: str, render: Json) -> Json:
        started = time.perf_counter()
        p = self.p
        result = {
            "key": key,
            "status": "ERROR",
            "raw_text": None,
            "partial_text": None,
            "error_code": None,
            "input_tokens": render["input_tokens"],
            "output_tokens": 0,
            "reasoning_tokens": None,
            "token_ids": None,
            "reported_model": p["model_id"],
            "finish_reason": None,
            "response_id": None,
            "service_tier": None,
        }
        try:
            if p["backend"] == "mlx":
                if self.engine is None:
                    self.engine = t.LocalRuntime(p["model_path"])
                r = self.engine.invoke(key, prompt, render)
                result.update(
                    status="COMPLETE" if r["status"] == "COMPLETE" else "ERROR",
                    raw_text=r["raw_text"],
                    partial_text=r["partial_text"],
                    error_code=r["error_code"],
                    output_tokens=r["output_tokens"],
                    token_ids=r["output_token_ids"],
                    finish_reason=r["finish_reason"],
                )
            elif p["backend"] == "furnace":
                from tensorrt_llm import LLM, SamplingParams
                from tensorrt_llm.llmapi import KvCacheConfig

                if self.engine is None:
                    config = {
                        k: v
                        for k, v in p["runtime_config"].items()
                        if k not in ("kv_cache", "sampling", "gpu")
                    }
                    self.engine = LLM(
                        model=p["model_path"],
                        trust_remote_code=False,
                        kv_cache_config=KvCacheConfig(
                            **p["runtime_config"]["kv_cache"]
                        ),
                        **config,
                    )
                output = self.engine.generate(
                    [render["token_ids"]],
                    SamplingParams(**p["runtime_config"]["sampling"]),
                    use_tqdm=False,
                )[0]
                candidate = output.outputs[0]
                ids = list(candidate.token_ids)
                require(len(ids) <= 96, "FURNACE_OUTPUT_CEILING")
                result.update(
                    status="COMPLETE",
                    raw_text=candidate.text,
                    output_tokens=len(ids),
                    token_ids=ids,
                    finish_reason=str(candidate.finish_reason),
                )
            else:
                if self.engine is None:
                    self.engine = api_client()
                r = self.engine.responses.create(**render["request"])
                result.update(
                    reported_model=r.model,
                    response_id=r.id,
                    service_tier=r.service_tier,
                    finish_reason=r.status,
                    partial_text=r.output_text,
                )
                require(r.usage is not None, "API_USAGE_UNKNOWN")
                result.update(
                    input_tokens=r.usage.input_tokens,
                    output_tokens=r.usage.output_tokens,
                    reasoning_tokens=getattr(
                        r.usage.output_tokens_details, "reasoning_tokens", None
                    ),
                )
                require(
                    r.model == p["model_id"] and r.service_tier == "default",
                    "API_IDENTITY_CHANGED",
                )
                require(
                    r.usage.input_tokens <= render["input_tokens"]
                    and r.usage.output_tokens <= 2048,
                    "API_USAGE_EXCEEDS_RESERVATION",
                )
                require(
                    r.status == "completed" and bool(r.output_text),
                    "API_INCOMPLETE_OR_EMPTY",
                )
                result.update(
                    status="COMPLETE", raw_text=r.output_text, partial_text=None
                )
        except Exception as exc:
            result.update(
                status="ERROR",
                raw_text=None,
                error_code=str(exc)
                if isinstance(exc, EBRTError)
                else type(exc).__name__,
            )
        result["latency_ms"] = (time.perf_counter() - started) * 1000
        return _seal(result)


def terminal_valid(row: Json, p: Json, key: str) -> None:
    r = _sealed_snapshot(row, "V0858_TERMINAL")
    require(
        set(r)
        == {
            "key",
            "status",
            "raw_text",
            "partial_text",
            "error_code",
            "input_tokens",
            "output_tokens",
            "reasoning_tokens",
            "token_ids",
            "reported_model",
            "finish_reason",
            "response_id",
            "service_tier",
            "latency_ms",
            "fingerprint_sha256",
        },
        "TERMINAL_SHAPE",
    )
    require(
        r["key"] == key and r["status"] in ("COMPLETE", "ERROR"), "TERMINAL_BINDING"
    )
    for field in ("input_tokens", "output_tokens"):
        require(type(r[field]) is int and r[field] >= 0, "USAGE_INVALID")
    require(
        type(r["latency_ms"]) in (float, int)
        and math.isfinite(r["latency_ms"])
        and r["latency_ms"] >= 0,
        "LATENCY_INVALID",
    )
    if r["status"] == "COMPLETE":
        require(
            type(r["raw_text"]) is str
            and bool(r["raw_text"])
            and r["partial_text"] is None
            and r["error_code"] is None,
            "COMPLETE_TEXT_INVALID",
        )
        require(r["reported_model"] == p["model_id"], "MODEL_IDENTITY")
        require(
            0 < r["output_tokens"] <= (2048 if p["backend"] == "openai" else 96),
            "OUTPUT_BUDGET",
        )
        require(r["input_tokens"] <= p["rendered"][key]["input_tokens"], "INPUT_BUDGET")
        if p["backend"] == "openai":
            require(
                r["finish_reason"] == "completed"
                and r["service_tier"] == "default"
                and r["token_ids"] is None,
                "API_TERMINAL_INVALID",
            )
        else:
            require(
                type(r["token_ids"]) is list
                and len(r["token_ids"]) == r["output_tokens"]
                and all(type(i) is int and i >= 0 for i in r["token_ids"]),
                "OUTPUT_IDS",
            )
            require(
                r["input_tokens"] == p["rendered"][key]["input_tokens"],
                "LOCAL_INPUT_COUNT",
            )
    else:
        require(
            r["raw_text"] is None
            and type(r["error_code"]) is str
            and bool(r["error_code"]),
            "ERROR_INVALID",
        )


def ready(rows: list[Json]) -> bool:
    return (
        len(rows) >= 2
        and all(r["terminal"]["status"] == "COMPLETE" for r in rows[:2])
        and (
            rows[0]["terminal"]["raw_text"] == previous.prior.FORMAT_EXPECTED
            and t.quality(
                rows[1]["terminal"]["raw_text"], previous.prior.build_readiness_case()
            )["strict_grade"]["status"]
            == "PASS"
        )
    )


def assess(rows: list[Json], p: Json) -> Json:
    require(
        0 < len(rows) <= 6 and [r["key"] for r in rows] == list(ORDER[: len(rows)]),
        "SCHEDULE_INVALID",
    )
    for row in rows:
        terminal_valid(row["terminal"], p, row["key"])
    errors = [
        i for i, row in enumerate(rows) if row["terminal"]["status"] != "COMPLETE"
    ]
    require(not errors or errors == [len(rows) - 1], "GENERATION_AFTER_ERROR")
    if not errors:
        require(len(rows) == (6 if ready(rows) else 2), "READINESS_OR_CALL_COUNT")
    require(len(rows) <= 2 or ready(rows), "FINALS_BEFORE_READINESS")
    finals = {}
    for row in rows[2:]:
        raw = row["terminal"]["raw_text"]
        q = t.quality(raw, d.numeric_case())
        finals[row["key"]] = {
            "arm": dict(SCHEDULE)[row["key"]],
            "raw_text": raw,
            "execution_status": row["terminal"]["status"],
            "quality": q,
            "edit_diagnostics": d.state_edit_diagnostics(
                d.numeric_case(), q["public_state"]
            ),
        }
    pairs = []
    for i in (1, 2):
        a, b = f"pair{i}_early", f"pair{i}_late"
        if a in finals and b in finals:
            pair = t.compare(finals[a], finals[b], a, b)
            pair["execution_order"] = [key for key, _ in SCHEDULE if key in (a, b)]
            if any(finals[k]["execution_status"] != "COMPLETE" for k in (a, b)):
                pair["strict_repair"] = pair["strict_regression"] = None
            pairs.append(pair)
    return {
        "run_status": "ERROR_STOP_NO_RETRY"
        if errors
        else ("COMPLETE_SIX_CALL_BLOCK" if ready(rows) else "READINESS_STOP"),
        "readiness_passed": ready(rows),
        "logical_generations": len(rows),
        "new_calculation_calls": 0,
        "final_denominator": len(finals),
        "parsed_finals": sum(
            r["quality"]["public_state"] is not None for r in finals.values()
        ),
        "strict_final_passes": sum(
            r["quality"]["strict_grade"]["status"] == "PASS" for r in finals.values()
        ),
        "finals": finals,
        "pairs_early_to_late": pairs,
        "total_input_tokens": sum(r["terminal"]["input_tokens"] for r in rows),
        "total_output_tokens": sum(r["terminal"]["output_tokens"] for r in rows),
        "summed_call_latency_ms": sum(r["terminal"]["latency_ms"] for r in rows),
        "effect_attribution": "NOT_ESTABLISHED_ONE_KNOWN_CASE",
        "api_cost_status": "RESERVATION_RETAINED_UNCERTAIN"
        if p["backend"] == "openai" and errors
        else "NOT_AN_INVOICE",
    }


def expected_journal(a: Json) -> list[Json]:
    events = [
        (
            "START",
            {
                "protocol_sha256": a["protocol_sha256"],
                "profile_sha256": a["profile"]["fingerprint_sha256"],
                "commit": a["commit"],
            },
        )
    ]
    for row in a["rows"]:
        events += [
            (
                "DISPATCH",
                {
                    k: row[k]
                    for k in ("key", "invocation", "rendered", "reserved_micro_usd")
                },
            ),
            ("TERMINAL", row["terminal"]),
        ]
    events.append(("FINISH", {"artifact_sha256": a["fingerprint_sha256"]}))
    journal = []
    for kind, payload in events:
        journal.append(
            _seal(
                {
                    "kind": kind,
                    "payload": payload,
                    "previous_sha256": journal[-1]["fingerprint_sha256"]
                    if journal
                    else None,
                }
            )
        )
    return journal


def verify(a: Json, locked: Json, journal: list[Json]) -> Json:
    validate_protocol(locked)
    a = _sealed_snapshot(a, "V0858_RUN")
    require(
        a["schema_version"] == "ebrt-role-placement-run-" + VERSION
        and a["protocol_sha256"] == locked["fingerprint_sha256"]
        and a["claim_boundary"] == BOUNDARY,
        "RUN_BINDING",
    )
    require(re.fullmatch(r"[0-9a-f]{40}", a["commit"]) is not None, "COMMIT_INVALID")
    p = validate_profile(a["profile"], locked)
    for row in a["rows"]:
        require(
            row["invocation"] == locked["invocations"][row["key"]]
            and row["rendered"] == p["rendered"][row["key"]],
            "DISPATCH_CHANGED",
        )
        require(
            row["reserved_micro_usd"] == reservation(p, row["key"]),
            "RESERVATION_CHANGED",
        )
    require(a["assessment"] == assess(a["rows"], p), "GRADES_CHANGED")
    require(journal == expected_journal(a), "JOURNAL_CHANGED")
    return _seal(
        {
            "status": "PASS",
            "model_generations": 0,
            "artifact_sha256": a["fingerprint_sha256"],
            "scope": "PROTOCOL_SOURCE_PROMPTS_PROFILE_GRADES_JOURNAL_NOT_AUTHENTICITY",
        }
    )


def reservation(p: Json, key: str) -> int:
    return (
        p["rendered"][key]["input_tokens"] * API_INPUT_RATE + 2048 * API_OUTPUT_RATE
        if p["backend"] == "openai"
        else 0
    )


def require_published(paths: list[Path], commit: str) -> None:
    require(
        re.fullmatch(r"[0-9a-f]{40}", commit) is not None
        and t.git("rev-parse", "HEAD") == commit,
        "COMMIT_INVALID",
    )
    branch = t.git("branch", "--show-current")
    require(bool(branch) and branch not in ("main", "master"), "BRANCH_INVALID")
    remote = t.git("ls-remote", "origin", "refs/heads/" + branch).split()
    require(bool(remote) and remote[0] == commit, "PREPARATION_NOT_PUSHED")
    for path in paths:
        relative = path.resolve().relative_to(ROOT)
        require(
            subprocess.check_output(
                ["git", "show", commit + ":" + str(relative)], cwd=ROOT
            )
            == path.read_bytes(),
            "COMMITTED_BYTES_CHANGED",
        )


def run(protocol_path: Path, profile_path: Path, output: Path, commit: str) -> Json:
    locked = validate_protocol(t.load_json(protocol_path))
    p = validate_profile(t.load_json(profile_path), locked)
    require_published(
        [
            protocol_path,
            profile_path,
            *(ROOT / n for n in locked["source_sha256"]),
            *(ROOT / n for n in locked["recorded_inputs_sha256"]),
        ],
        commit,
    )
    require(identity(p["backend"]) == p["runtime"], "RUNTIME_CHANGED")
    if p["backend"] != "openai":
        require(
            preflight(p["backend"], p["model_path"], locked) == p, "PREFLIGHT_CHANGED"
        )
    else:
        require(bool(os.environ.get("OPENAI_API_KEY")), "API_KEY_UNAVAILABLE")
    require(not output.exists(), "OUTPUT_EXISTS")
    t.write_new(
        profile_path.with_suffix(".execution-claim.json"),
        {
            "profile_sha256": p["fingerprint_sha256"],
            "protocol_sha256": locked["fingerprint_sha256"],
            "commit": commit,
            "status": "CLAIMED_NO_RETRY",
        },
    )
    output.mkdir(parents=True, exist_ok=False)
    runtime, rows, events = Runtime(p), [], []
    with (output / "journal.jsonl").open("x", encoding="utf-8") as stream:

        def record(kind, payload):
            row = _seal(
                {
                    "kind": kind,
                    "payload": payload,
                    "previous_sha256": events[-1]["fingerprint_sha256"]
                    if events
                    else None,
                }
            )
            stream.write(t.json_line(row) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
            events.append(row)

        record(
            "START",
            {
                "protocol_sha256": locked["fingerprint_sha256"],
                "profile_sha256": p["fingerprint_sha256"],
                "commit": commit,
            },
        )
        reserved = 0
        for key in ORDER:
            if len(rows) == 2 and not ready(rows):
                break
            cost = reservation(p, key)
            require(reserved + cost <= API_CAP_MICRO_USD, "TOTAL_RESERVATION_EXCEEDED")
            reserved += cost
            dispatch = {
                "key": key,
                "invocation": locked["invocations"][key],
                "rendered": p["rendered"][key],
                "reserved_micro_usd": cost,
            }
            record("DISPATCH", dispatch)
            try:
                terminal = runtime.invoke(
                    key, dispatch["invocation"]["prompt"], dispatch["rendered"]
                )
            except BaseException as exc:
                record(
                    "INTERRUPTED", {"key": key, "exception_type": type(exc).__name__}
                )
                raise
            record("TERMINAL", terminal)
            rows.append({**dispatch, "terminal": terminal})
            print(
                t.json_line(
                    {"backend": p["backend"], "call": key, "status": terminal["status"]}
                ),
                flush=True,
            )
            if terminal["status"] != "COMPLETE":
                break
        a = _seal(
            {
                "schema_version": "ebrt-role-placement-run-" + VERSION,
                "commit": commit,
                "protocol_sha256": locked["fingerprint_sha256"],
                "profile": p,
                "rows": rows,
                "assessment": assess(rows, p),
                "claim_boundary": BOUNDARY,
            }
        )
        record("FINISH", {"artifact_sha256": a["fingerprint_sha256"]})
    t.write_new(output / "results.json", a)
    t.write_new(output / "verification.json", verify(a, locked, events))
    return a


def self_test() -> Json:
    import copy
    import tempfile
    from unittest.mock import patch

    checks = {}
    locked = protocol()
    inv = locked["invocations"]
    before, after = inv["pair1_early"]["prompt"], inv["pair1_late"]["prompt"]
    checks["same_lines_and_bytes_no_duplication"] = Counter(
        before.splitlines()
    ) == Counter(after.splitlines()) and len(before.encode()) == len(after.encode())
    checks["only_position_changes"] = before != after and before.replace(
        "\n".join(ROLE_LINES) + "\n", ""
    ) == after.replace("\n".join(ROLE_LINES) + "\n", "")
    checks["late_after_record"] = after.index(ROLE_LINES[0]) > after.index(
        "END_PUBLIC_CALCULATION_RECORD"
    )
    checks["early_equals_actual_previous_dispatch"] = (
        before
        == t.load_json(
            ROOT / "artifacts/source_field_ablation_v0_8_5_7/r01/results.json"
        )["results"][3]["invocation"]["prompt"]
    )
    checks["both_pairs_identical_prompts"] = all(
        inv[f"pair1_{arm}"]["prompt"] == inv[f"pair2_{arm}"]["prompt"]
        for arm in ("early", "late")
    )
    checks["no_case_ids_added_in_role_block"] = all(
        re.search(r"R\d|CREDITS|15", line) is None for line in ROLE_LINES
    )
    checks["six_calls_two_readiness"] = (
        len(ORDER) == 6 and ORDER[:2] == READY and set(inv) == set(ORDER)
    )
    checks["no_hidden_chain_or_json_schema_api"] = set(api_request(before)) == {
        "model",
        "input",
        "reasoning",
        "max_output_tokens",
        "store",
        "service_tier",
    }
    # A mock API profile exercises the shared verifier without network or model execution.
    p = _seal(
        {
            "schema_version": "ebrt-role-placement-profile-" + VERSION,
            "status": "PASS_ZERO_GENERATION",
            "backend": "openai",
            "protocol_sha256": locked["fingerprint_sha256"],
            "model_id": API_MODEL,
            "model_path": None,
            "snapshot_files": {},
            "runtime": {"test": "SYNTHETIC"},
            "runtime_config": {
                "max_retries": 0,
                "timeout_seconds": 60,
                "base_url": "https://api.openai.com/v1",
            },
            "rendered": {
                key: _seal({"request": api_request(row["prompt"]), "input_tokens": 100})
                for key, row in inv.items()
            },
            "api_cost_policy": {
                "reserved_worst_case_micro_usd": 6 * (500 + 2048 * 20),
                "max_total_micro_usd": API_CAP_MICRO_USD,
                "input_micro_usd_per_token": 5,
                "output_micro_usd_per_token": 20,
            },
            "generation_calls": 0,
        }
    )

    def reseal(v):
        return _seal({k: x for k, x in v.items() if k != "fingerprint_sha256"})

    def rejected(fn):
        try:
            fn()
        except EBRTError:
            return True
        return False

    def output(answer="15_CREDITS", support=("R2", "R4")):
        return "STATE_JSON=" + t.json_line(
            {
                "answer": answer,
                "decision_support_ids": list(support),
                "revision_event_id": "R6",
                "preserved_constraint_ids": ["R5"],
            }
        )

    rows = []
    for key in ORDER:
        text = (
            previous.prior.FORMAT_EXPECTED
            if key == READY[0]
            else output(previous.prior.build_readiness_case().contract.expected_answer)
            if key == READY[1]
            else output(
                support=("R2", "R4", "R6") if key.endswith("early") else ("R2", "R4")
            )
        )
        terminal = _seal(
            {
                "key": key,
                "status": "COMPLETE",
                "raw_text": text,
                "partial_text": None,
                "error_code": None,
                "input_tokens": 100,
                "output_tokens": 50,
                "reasoning_tokens": 0,
                "token_ids": None,
                "reported_model": API_MODEL,
                "finish_reason": "completed",
                "response_id": "SYNTHETIC",
                "service_tier": "default",
                "latency_ms": 0.0,
            }
        )
        rows.append(
            {
                "key": key,
                "invocation": inv[key],
                "rendered": p["rendered"][key],
                "reserved_micro_usd": reservation(p, key),
                "terminal": terminal,
            }
        )

    def artifact(rs):
        return _seal(
            {
                "schema_version": "ebrt-role-placement-run-" + VERSION,
                "commit": BASE_COMMIT,
                "protocol_sha256": locked["fingerprint_sha256"],
                "profile": p,
                "rows": rs,
                "assessment": assess(rs, p),
                "claim_boundary": BOUNDARY,
            }
        )

    a = artifact(rows)
    checks["mock_four_final_denominator"] = a["assessment"]["final_denominator"] == 4
    checks["overlap_remains_unparsed"] = (
        a["assessment"]["finals"]["pair1_early"]["quality"]["parse_error"]
        == "V0852_STATE_CHANNELS_OVERLAP"
    )
    checks["no_regrade_of_early_state"] = a["assessment"]["parsed_finals"] == 2
    checks["pair_direction_early_to_late"] = all(
        pair["strict_repair"] for pair in a["assessment"]["pairs_early_to_late"]
    )
    checks["reverse_order_recorded"] = a["assessment"]["pairs_early_to_late"][1][
        "execution_order"
    ] == ["pair2_late", "pair2_early"]
    checks["mock_portable_verification"] = (
        verify(a, locked, expected_journal(a))["status"] == "PASS"
    )
    checks["tampered_grades_rejected"] = rejected(
        lambda: verify(reseal({**a, "assessment": {}}), locked, expected_journal(a))
    )
    checks["missing_journal_rejected"] = rejected(
        lambda: verify(a, locked, expected_journal(a)[:-1])
    )
    changed = copy.deepcopy(p)
    changed["rendered"]["pair1_late"] = p["rendered"]["pair1_early"]
    checks["wrong_profile_request_rejected"] = rejected(
        lambda: validate_profile(reseal(changed), locked)
    )
    changed = copy.deepcopy(p)
    changed["api_cost_policy"]["reserved_worst_case_micro_usd"] = 0
    checks["unreserved_api_rejected"] = rejected(
        lambda: validate_profile(reseal(changed), locked)
    )
    for key in READY:
        rs = copy.deepcopy(rows[:2])
        index = READY.index(key)
        rs[index]["terminal"] = reseal({**rs[index]["terminal"], "raw_text": "bad"})
        checks[key + "_stops_finals"] = assess(rs, p)["run_status"] == "READINESS_STOP"
    checks["missing_final_rejected"] = rejected(lambda: assess(rows[:-1], p))
    checks["reordered_final_rejected"] = rejected(
        lambda: assess([*rows[:2], rows[3], rows[2], *rows[4:]], p)
    )
    rs = copy.deepcopy(rows[:3])
    rs[-1]["terminal"] = reseal(
        {
            **rs[-1]["terminal"],
            "status": "ERROR",
            "raw_text": None,
            "error_code": "SYNTHETIC_TIMEOUT",
        }
    )
    checks["runtime_error_retained_no_retry"] = (
        assess(rs, p)["run_status"] == "ERROR_STOP_NO_RETRY"
    )
    checks["generation_after_error_rejected"] = rejected(
        lambda: assess(rs + rows[3:], p)
    )
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    key = "pair1_early"

    def api_response(**updates):
        return SimpleNamespace(
            **{
                "model": API_MODEL,
                "id": "SYNTHETIC",
                "service_tier": "default",
                "status": "completed",
                "output_text": output(),
                "usage": SimpleNamespace(
                    input_tokens=100,
                    output_tokens=50,
                    output_tokens_details=SimpleNamespace(reasoning_tokens=0),
                ),
                **updates,
            }
        )

    for name, response, expected in (
        ("completed", api_response(), "COMPLETE"),
        ("missing_usage", api_response(usage=None), "ERROR"),
        ("incomplete", api_response(status="incomplete"), "ERROR"),
        ("wrong_model", api_response(model="other"), "ERROR"),
        ("wrong_tier", api_response(service_tier="priority"), "ERROR"),
        (
            "excess_usage",
            api_response(
                usage=SimpleNamespace(
                    input_tokens=101, output_tokens=50, output_tokens_details=None
                )
            ),
            "ERROR",
        ),
    ):
        runtime = Runtime(p)
        runtime.engine = MagicMock()
        runtime.engine.responses.create.return_value = response
        actual = runtime.invoke(key, inv[key]["prompt"], p["rendered"][key])
        terminal_valid(actual, p, key)
        checks["api_" + name + "_single_attempt"] = (
            actual["status"] == expected
            and runtime.engine.responses.create.call_count == 1
            and runtime.engine.responses.create.call_args.kwargs
            == p["rendered"][key]["request"]
        )
    runtime = Runtime(p)
    runtime.engine = MagicMock()
    runtime.engine.responses.create.side_effect = RuntimeError("SENSITIVE_NOT_RECORDED")
    actual = runtime.invoke(key, inv[key]["prompt"], p["rendered"][key])
    checks["api_exception_sanitized_no_retry"] = (
        actual["error_code"] == "RuntimeError"
        and "SENSITIVE_NOT_RECORDED" not in json.dumps(actual)
        and runtime.engine.responses.create.call_count == 1
    )
    with tempfile.TemporaryDirectory(prefix="ebrt-role-placement-test-") as tmp:
        directory = Path(tmp)
        lp = directory / "protocol.json"
        pp = directory / "profile.json"
        out = directory / "run"
        t.write_new(lp, locked)
        t.write_new(pp, p)
        dispatched = []

        class MockRuntime:
            def __init__(self, profile):
                pass

            def invoke(self, key, prompt, render):
                journal = previous.read_journal(out / "journal.jsonl")
                require(
                    journal[-1]["kind"] == "DISPATCH"
                    and journal[-1]["payload"]["invocation"]["prompt"] == prompt,
                    "MOCK_DISPATCH",
                )
                dispatched.append(key)
                return rows[list(ORDER).index(key)]["terminal"]

        import contextlib
        import io

        with (
            patch.object(sys.modules[__name__], "require_published"),
            patch.object(sys.modules[__name__], "identity", return_value=p["runtime"]),
            patch.object(sys.modules[__name__], "Runtime", MockRuntime),
            patch.dict(os.environ, {"OPENAI_API_KEY": "SYNTHETIC_NOT_TRANSMITTED"}),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            made = run(lp, pp, out, BASE_COMMIT)
            checks["mock_dispatch_before_generation"] = dispatched == list(ORDER)
            checks["mock_saved_receipt_verifies"] = (
                verify(made, locked, previous.read_journal(out / "journal.jsonl"))[
                    "status"
                ]
                == "PASS"
            )
            try:
                run(lp, pp, directory / "retry", BASE_COMMIT)
                denied = False
            except FileExistsError:
                denied = True
            checks["execution_identity_cannot_rerun"] = denied and len(dispatched) == 6
            # Interruption must retain the claim, without inventing a terminal or rerun.
            other_profile = directory / "interrupted-profile.json"
            t.write_new(other_profile, p)
            out = directory / "interrupted-run"

            class InterruptedRuntime(MockRuntime):
                def invoke(self, key, prompt, render):
                    super().invoke(key, prompt, render)
                    raise KeyboardInterrupt

            with patch.object(sys.modules[__name__], "Runtime", InterruptedRuntime):
                try:
                    run(lp, other_profile, out, BASE_COMMIT)
                    interrupted = False
                except KeyboardInterrupt:
                    interrupted = True
                checks["interruption_keeps_partial_journal"] = (
                    interrupted
                    and [
                        r["kind"] for r in previous.read_journal(out / "journal.jsonl")
                    ]
                    == ["START", "DISPATCH", "INTERRUPTED"]
                    and not (out / "results.json").exists()
                )
                try:
                    run(lp, other_profile, directory / "interrupted-retry", BASE_COMMIT)
                    denied = False
                except FileExistsError:
                    denied = True
                checks["interruption_keeps_execution_claim"] = (
                    denied and len(dispatched) == 7
                )
    require(
        all(checks.values()),
        "SELF_TEST:" + ",".join(k for k, v in checks.items() if not v),
    )
    return _seal(
        {
            "status": "PASS",
            "checks": checks,
            "logical_model_calls": 0,
            "synthetic_outputs_only": True,
        }
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("self-test")
    spec = sub.add_parser("protocol")
    spec.add_argument("--output", type=Path, required=True)
    prep = sub.add_parser("preflight")
    prep.add_argument("--backend", choices=BACKENDS, required=True)
    prep.add_argument("--model")
    prep.add_argument("--protocol", type=Path, required=True)
    prep.add_argument("--output", type=Path, required=True)
    runp = sub.add_parser("run")
    runp.add_argument("--protocol", type=Path, required=True)
    runp.add_argument("--profile", type=Path, required=True)
    runp.add_argument("--output", type=Path, required=True)
    runp.add_argument("--commit", required=True)
    runp.add_argument("--execute-once", action="store_true", required=True)
    vp = sub.add_parser("verify")
    vp.add_argument("artifact", type=Path)
    vp.add_argument("--protocol", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "self-test":
            result = self_test()
        elif args.command == "protocol":
            result = protocol()
            t.write_new(args.output, result)
        elif args.command == "preflight":
            result = preflight(args.backend, args.model, t.load_json(args.protocol))
            validate_profile(result, t.load_json(args.protocol))
            t.write_new(args.output, result)
        elif args.command == "run":
            a = run(args.protocol, args.profile, args.output, args.commit)
            result = {
                "artifact_sha256": a["fingerprint_sha256"],
                "assessment": a["assessment"],
            }
        else:
            result = verify(
                t.load_json(args.artifact),
                t.load_json(args.protocol),
                previous.read_journal(args.artifact.parent / "journal.jsonl"),
            )
        print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
        return 0
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "ERROR",
                    "code": str(exc)
                    if isinstance(exc, EBRTError)
                    else type(exc).__name__,
                }
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
