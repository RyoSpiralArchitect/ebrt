#!/usr/bin/env python3
"""Two-call hosted integration check over EBRT's known synthetic fixture.

Provider receipts stay in a local-only report. This is not a fresh benchmark
or evidence of a gradient-specific or general reasoning improvement.
"""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import re
import sys
import time
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from ebrt_core import (
    AdapterDescriptor, CallableModelAdapter, EBRTError, PublicRevisionActuator,
    RevisionEngine, _fingerprint, _parse_model_text, _seal,
    build_demo_contract, build_demo_task,
)
from ebrt_demo import _prompt_records
from local_output_diff_corpus_v0_8_2 import _common_output_grade, build_direct_invocation


SCHEMA_VERSION = "ebrt-hosted-comparison-v0.8.6"
PRIVACY = "LOCAL_ONLY_REVIEW_BEFORE_EXPORT"
ARMS = ("direct_full_context", "ebrt_credit_first")
EFFORTS = ("none", "minimal", "low", "medium", "high", "xhigh")


@dataclass(frozen=True)
class HostedConfig:
    model: str
    reasoning_effort: str = "low"
    max_output_tokens: int = 1024
    timeout_seconds: float = 60.0

    def __post_init__(self) -> None:
        if not isinstance(self.model, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}", self.model):
            raise EBRTError("HOSTED_MODEL_INVALID")
        if self.reasoning_effort not in EFFORTS:
            raise EBRTError("HOSTED_REASONING_EFFORT_INVALID")
        if type(self.max_output_tokens) is not int or not 16 <= self.max_output_tokens <= 4096:
            raise EBRTError("HOSTED_TOKEN_LIMIT_INVALID")
        if (isinstance(self.timeout_seconds, bool)
                or not isinstance(self.timeout_seconds, (int, float))
                or not math.isfinite(self.timeout_seconds)
                or not 0 < self.timeout_seconds <= 300):
            raise EBRTError("HOSTED_TIMEOUT_INVALID")

    def to_dict(self) -> dict[str, Any]:
        return {
            "model": self.model, "reasoning_effort": self.reasoning_effort,
            "max_output_tokens": self.max_output_tokens,
            "timeout_seconds": self.timeout_seconds, "max_retries": 0,
            "store": False, "service_tier": "default", "truncation": "disabled",
            "text_verbosity": "low",
        }


def _field(value: Any, name: str, default: Any = None) -> Any:
    return value.get(name, default) if isinstance(value, Mapping) else getattr(value, name, default)


def _safe_identifier(value: Any) -> str | None:
    return value if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9._:/-]{1,512}", value) else None


def _usage(value: Any) -> dict[str, int | None]:
    details = _field(value, "output_tokens_details")
    values = {name: _field(value, name) for name in ("input_tokens", "output_tokens", "total_tokens")}
    values["reasoning_tokens"] = _field(details, "reasoning_tokens")
    return {key: number if type(number) is int and number >= 0 else None for key, number in values.items()}


class HostedResponsesRuntime:
    """One shared configuration and an explicit attempt limit, without retries."""

    def __init__(self, config: HostedConfig, client: Any = None, *, max_attempts: int = 2) -> None:
        if type(max_attempts) is not int or not 1 <= max_attempts <= 9:
            raise EBRTError("HOSTED_CALL_LIMIT_INVALID")
        self.config = config
        self.max_attempts = max_attempts
        if client is None:
            if not os.environ.get("OPENAI_API_KEY"):
                raise EBRTError("HOSTED_API_KEY_MISSING")
            try:
                from openai import OpenAI
            except ImportError:
                raise EBRTError("HOSTED_SDK_MISSING") from None
            try:
                client = OpenAI(base_url="https://api.openai.com/v1", max_retries=0, timeout=config.timeout_seconds)
            except Exception:
                raise EBRTError("HOSTED_CLIENT_INITIALIZATION_FAILED") from None
        if type(getattr(client, "max_retries", None)) is not int or client.max_retries != 0:
            raise EBRTError("HOSTED_RETRIES_MUST_BE_ZERO")
        self.client = client
        self.attempts = 0
        self.receipts: list[dict[str, Any]] = []

    def generate(self, invocation: Mapping[str, Any]) -> str:
        if self.attempts >= self.max_attempts:
            raise EBRTError("HOSTED_CALL_BUDGET_EXHAUSTED")
        prompt = invocation.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            raise EBRTError("HOSTED_PROMPT_INVALID")
        self.attempts += 1
        receipt = {
            "attempt": self.attempts,
            "request_fingerprint_sha256": invocation.get("fingerprint_sha256"),
            "generation_config_fingerprint_sha256": _fingerprint(self.config.to_dict()),
            "requested_model": self.config.model, "returned_model": None,
            "response_id": None, "provider_request_id": None,
            "usage": _usage(None), "status": "STARTED", "error_code": None,
        }
        self.receipts.append(receipt)
        started = time.perf_counter()
        try:
            response = self.client.responses.create(
                model=self.config.model, input=prompt,
                reasoning={"effort": self.config.reasoning_effort},
                text={"verbosity": "low"}, max_output_tokens=self.config.max_output_tokens,
                store=False, service_tier="default", truncation="disabled",
                timeout=self.config.timeout_seconds,
            )
        except Exception as error:
            code = {
                "APITimeoutError": "HOSTED_PROVIDER_TIMEOUT",
                "APIConnectionError": "HOSTED_PROVIDER_CONNECTION_ERROR",
                "AuthenticationError": "HOSTED_PROVIDER_AUTHENTICATION_ERROR",
                "PermissionDeniedError": "HOSTED_PROVIDER_PERMISSION_DENIED",
                "RateLimitError": "HOSTED_PROVIDER_RATE_LIMIT",
            }.get(type(error).__name__, "HOSTED_PROVIDER_ERROR")
            receipt.update(status="ERROR", error_code=code)
            status = getattr(error, "status_code", None)
            receipt["http_status"] = status if type(status) is int else None
            raise EBRTError(code) from None
        finally:
            receipt["latency_ms"] = (time.perf_counter() - started) * 1000.0
        receipt.update(
            returned_model=_safe_identifier(_field(response, "model")),
            response_id=_safe_identifier(_field(response, "id")),
            provider_request_id=_safe_identifier(_field(response, "_request_id")),
            usage=_usage(_field(response, "usage")),
        )
        try:
            if _field(response, "error") is not None:
                raise EBRTError("HOSTED_RESPONSE_ERROR")
            if _field(response, "status") != "completed" or _field(response, "incomplete_details") is not None:
                raise EBRTError("HOSTED_RESPONSE_INCOMPLETE")
            output = _field(response, "output")
            if not isinstance(output, (list, tuple)):
                raise EBRTError("HOSTED_RESPONSE_OUTPUT_INVALID")
            for item in output:
                if _field(item, "type") == "message" and _field(item, "status") not in (None, "completed"):
                    raise EBRTError("HOSTED_RESPONSE_INCOMPLETE")
                contents = _field(item, "content", [])
                if contents is None:
                    contents = []
                if not isinstance(contents, (list, tuple)):
                    raise EBRTError("HOSTED_RESPONSE_OUTPUT_INVALID")
                for content in contents:
                    if _field(content, "type") == "refusal":
                        raise EBRTError("HOSTED_RESPONSE_REFUSAL")
            text = _field(response, "output_text")
            if not isinstance(text, str) or not text.strip():
                raise EBRTError("HOSTED_RESPONSE_TEXT_MISSING")
            if receipt["returned_model"] is None:
                raise EBRTError("HOSTED_RESPONSE_MODEL_MISSING")
        except EBRTError as error:
            receipt.update(status="ERROR", error_code=str(error))
            raise
        receipt["status"] = "COMPLETED"
        return text


class _CaptureActuator(PublicRevisionActuator):
    """Retain verified core material even when subsequent generation fails."""

    def __init__(self) -> None:
        self.trajectory = None
        self.actuator = None

    def compile(self, task, optimized, *, lane_id):
        program = super().compile(task, optimized, lane_id=lane_id)
        self.trajectory = json.loads(json.dumps(optimized))
        self.actuator = program.to_dict()
        return program


def run_comparison(config: HostedConfig, *, client: Any = None) -> dict[str, Any]:
    task, contract = build_demo_task(), build_demo_contract()
    runtime = HostedResponsesRuntime(config, client)
    capture = _CaptureActuator()
    descriptor = AdapterDescriptor(
        adapter_id="openai-responses-hosted-v0.8.6", model_id="openai/" + config.model,
        interface_kind="hosted_api", state_visibility="public_only",
        differentiable_through_model=False,
        generation_config=tuple(sorted(config.to_dict().items())),
    )
    direct = build_direct_invocation(task)
    invocations = {ARMS[0]: direct}
    raw_text_by_arm: dict[str, str] = {}
    arms: dict[str, Any] = {}
    ebrt_receipt = None

    def callback(invocation):
        invocations[ARMS[1]] = json.loads(json.dumps(invocation))
        text = runtime.generate(invocation)
        raw_text_by_arm[ARMS[1]] = text
        return text

    for name in ARMS:
        result = None
        raw_text = None
        error_code = None
        try:
            if name == ARMS[0]:
                raw_text = runtime.generate(direct)
                raw_text_by_arm[name] = raw_text
                answer, support = _parse_model_text(raw_text, task=task)
                result = {"answer": answer, "support_ids": list(support), "raw_text": raw_text}
            else:
                ebrt_receipt = RevisionEngine(actuator_adapter=capture).run(
                    task, CallableModelAdapter(descriptor=descriptor, callback=callback),
                    post_run_contract=contract,
                )
                result = {key: ebrt_receipt["model_result"][key] for key in ("answer", "support_ids", "raw_text")}
            status = "PARSED"
        except EBRTError as error:
            error_code = str(error)
            status = "PROVIDER_ERROR" if error_code.startswith("HOSTED_") else "FORMAT_OR_CORE_ERROR"
        arms[name] = {
            "status": status, "error_code": error_code, "result": result,
            "raw_text": raw_text_by_arm.get(name),
            "invocation": invocations.get(name),
            "grade": _common_output_grade({"status": status, **(result or {})}, contract),
        }

    both_parsed = all(arms[name]["status"] == "PARSED" for name in ARMS)
    direct_result, controlled_result = (arms[name]["result"] for name in ARMS)
    matched = {
        "same_task_and_full_evidence": ARMS[1] in invocations and _prompt_records(direct) == _prompt_records(invocations[ARMS[1]]),
        "same_generation_configuration": len(runtime.receipts) == 2 and len({row["generation_config_fingerprint_sha256"] for row in runtime.receipts}) == 1,
        "same_returned_model": len(runtime.receipts) == 2 and runtime.receipts[0]["returned_model"] is not None and runtime.receipts[0]["returned_model"] == runtime.receipts[1]["returned_model"],
        "exactly_two_provider_attempts": runtime.attempts == 2,
    }
    mechanism = "PASS" if capture.trajectory and all(capture.trajectory["checks"].values()) else "NOT_ASSESSED"
    structure = ebrt_receipt["structural_verification"]["status"] if ebrt_receipt else "NOT_ASSESSED"
    contract_status = ebrt_receipt["post_run_contract"]["status"] if ebrt_receipt else "NOT_ASSESSED"
    passed = all(matched.values()) and mechanism == structure == contract_status == "PASS" and all(arm["grade"]["status"] == "PASS" for arm in arms.values())
    return _seal({
        "schema_version": SCHEMA_VERSION, "status": "PASS" if passed else "FAIL",
        "privacy": PRIVACY, "evidence_label": "INTEGRATION_CHECK_KNOWN_FIXTURE",
        "generation_config": config.to_dict(), "adapter": descriptor.to_dict(),
        "task": task.to_public_dict(), "arms": arms,
        "trajectory": capture.trajectory, "actuator": capture.actuator,
        "ebrt_receipt": ebrt_receipt, "provider_receipts": runtime.receipts,
        "actual_provider_calls": runtime.attempts,
        "verification": {"mechanism": mechanism, "structural": structure, "post_run_contract": contract_status, "matched_inputs": matched},
        "output_diff": {
            "answer_changed": direct_result["answer"] != controlled_result["answer"] if both_parsed else None,
            "support_changed": set(direct_result["support_ids"]) != set(controlled_result["support_ids"]) if both_parsed else None,
            "raw_text_changed": direct_result["raw_text"] != controlled_result["raw_text"] if both_parsed else None,
        },
        "effect_attribution_status": "NOT_ASSESSED",
        "claim_boundary": [
            "Known synthetic fixture, not a fresh benchmark or a quality estimate.",
            "The direct and EBRT arms change the prompt package, not just backward credit.",
            "One serial call per arm does not establish causal superiority or stable model behavior.",
            "Public surrogate descent and hosted generation remain separated by a stop-gradient boundary.",
            "Provider IDs, usage, timing, and outputs are local receipts; review before export.",
        ],
    })


def _open_output(path: str):
    target = Path(path).expanduser().resolve()
    checkout = Path(__file__).resolve().parent
    if target == checkout or checkout in target.parents:
        raise EBRTError("HOSTED_OUTPUT_INSIDE_CHECKOUT")
    try:
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        return os.fdopen(fd, "w", encoding="utf-8")
    except OSError:
        raise EBRTError("HOSTED_OUTPUT_UNAVAILABLE") from None


def render_text(report: Mapping[str, Any]) -> str:
    lines = [f"Hosted EBRT integration: {report['status']}",
             f"Model: {report['generation_config']['model']}",
             "Known synthetic fixture; one attempt per arm, no retries."]
    for name, arm in report["arms"].items():
        result = arm["result"]
        detail = f"answer={result['answer']} support={','.join(result['support_ids'])}" if result else arm["error_code"]
        lines.append(f"{name}: {arm['status']}; {detail}; output contract={arm['grade']['status']}")
    lines.extend([
        f"Checks: {report['verification']['mechanism']} mechanism; {report['verification']['structural']} structure; {report['verification']['post_run_contract']} post-run contract",
        f"Output changed: answer={report['output_diff']['answer_changed']}, support={report['output_diff']['support_changed']}",
        f"Provider attempts: {report['actual_provider_calls']}/2",
        f"Effect attribution: {report['effect_attribution_status']}",
        "Local receipts require review before export. No general quality improvement claim.",
    ])
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, help="an explicitly selected available model ID")
    parser.add_argument("--reasoning-effort", default="low", choices=EFFORTS)
    parser.add_argument("--max-output-tokens", type=int, default=1024, help="per attempt, 16..4096")
    parser.add_argument("--timeout", type=float, default=60.0, help="seconds per attempt, at most 300")
    parser.add_argument("--output", help="new local JSON file outside the checkout; never overwrites")
    args = parser.parse_args(argv)
    output = None
    try:
        config = HostedConfig(args.model, args.reasoning_effort, args.max_output_tokens, args.timeout)
        if args.output:
            output = _open_output(args.output)
        report = run_comparison(config)
        if output:
            json.dump(report, output, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
            output.write("\n")
        print(render_text(report), end="")
        return 0 if report["status"] == "PASS" else 1
    except EBRTError as error:
        if output:
            json.dump({"status": "ERROR", "privacy": PRIVACY, "error_code": str(error)}, output)
            output.write("\n")
        print(f"Hosted comparison failed: {error}", file=sys.stderr)
        return 1
    except OSError:
        print("Hosted comparison failed: HOSTED_OUTPUT_WRITE_FAILED", file=sys.stderr)
        return 1
    finally:
        if output:
            output.close()


if __name__ == "__main__":
    raise SystemExit(main())
