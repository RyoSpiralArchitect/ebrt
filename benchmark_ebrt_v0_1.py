#!/usr/bin/env python3
"""Matched offline benchmark for the frozen EBRT v0.1 mechanism.

This file deliberately imports, but never edits, ``ebrt_monolith_v0_1.py``.
It compares five matched arms:

    A  one-pass forward-only baseline
    B  event detection with a zero revision budget
    C  detected event plus random eligible backward routing and revision
    D  the unmodified full EBRT v0.1 execution path
    E  detected event plus annotated gold-target routing (privileged diagnostic)

The benchmark remains a synthetic mechanism benchmark. Structured topic,
stance, confidence, and revision-cue fields are oracle inputs; results do not
establish better language-model reasoning or natural-language event detection.

Examples:

    python3 benchmark_ebrt_v0_1.py self-test
    python3 benchmark_ebrt_v0_1.py quick
    python3 benchmark_ebrt_v0_1.py full
    python3 benchmark_ebrt_v0_1.py profile --profile-warmups 5 --profile-repeats 30
"""

from __future__ import annotations

import argparse
import csv
import dataclasses
import hashlib
import importlib.util
import json
import math
import os
import platform
import random
import resource
import statistics
import subprocess
import sys
import tempfile
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import torch


SCHEMA_VERSION = "ebrt-benchmark-v0.1"
EXPECTED_MONOLITH_SHA256 = (
    "b1702f2868839d989cc3a9321d227436a23c3dad6cc86483edee9d5dbab3a529"
)
DEFAULT_MONOLITH = Path(__file__).with_name("ebrt_monolith_v0_1.py")
ARMS = (
    "A_forward_only_1pass",
    "B_detect_only_budget0",
    "C_random_route_revision",
    "D_ebrt_full",
    "E_oracle_route_revision",
)
PAIRED_COMPARISONS = (
    ("D_ebrt_full", "A_forward_only_1pass", "full_minus_forward"),
    ("D_ebrt_full", "C_random_route_revision", "full_minus_random_route"),
    ("E_oracle_route_revision", "D_ebrt_full", "oracle_minus_full"),
    ("B_detect_only_budget0", "A_forward_only_1pass", "detect_minus_forward"),
    ("D_ebrt_full", "B_detect_only_budget0", "full_minus_detect"),
    ("E_oracle_route_revision", "B_detect_only_budget0", "oracle_minus_detect"),
)
CLAIM_BOUNDARY = (
    "This is a fixed synthetic mechanism benchmark, not a language-model reasoning benchmark.",
    "Event inputs and revision targets are derived from oracle-structured topic, stance, confidence, and cue fields.",
    "The frozen generator is a tiny continuous-state toy model, not a pretrained Transformer hidden manifold.",
    "Energy reduction is an optimized in-system objective and is not treated as independent quality evidence.",
    "Runtime and memory measurements apply only to the recorded software, hardware, dtype, and benchmark protocol.",
    "No result establishes natural-language semantic detection, pretrained-model repair, or production generalization.",
)


@dataclass(frozen=True)
class ExpectedEvent:
    source_step: int
    topic: str
    target_steps: tuple[int, ...]
    revision_target: float

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass(frozen=True)
class BenchmarkCase:
    case_id: str
    family: str
    observations: tuple[dict[str, Any], ...]
    expected_events: tuple[ExpectedEvent, ...]
    expected_final_labels: dict[str, str]
    routing_informative: bool
    expected_suppressed_events: int
    config_overrides: dict[str, Any] = field(default_factory=dict)
    note: str = ""

    def to_dict(self, include_observations: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "case_id": self.case_id,
            "family": self.family,
            "expected_events": [item.to_dict() for item in self.expected_events],
            "expected_final_labels": dict(self.expected_final_labels),
            "routing_informative": self.routing_informative,
            "expected_suppressed_events": self.expected_suppressed_events,
            "config_overrides": dict(self.config_overrides),
            "note": self.note,
        }
        if include_observations:
            payload["observations"] = [dict(item) for item in self.observations]
        return payload


@dataclass
class Execution:
    arm: str
    config: Any
    engine: Any
    observations: list[Any]
    baseline_states: torch.Tensor
    final_states: torch.Tensor
    controls: torch.Tensor
    detected_events: list[Any]
    committed_events: list[Any]
    suppressed_events: list[Any]
    revisions: list[Any]
    decoded: dict[str, Any]
    decode_call_count: int
    core_hash_before: str
    core_hash_after: str
    backward_calls: int
    generator_step_calls: int
    internal_elapsed_ms: float
    external_wall_ms: float
    process_peak_rss_mib: float


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _stable_int(*parts: Any, modulus: int = 2**31 - 1) -> int:
    material = "|".join(str(part) for part in parts).encode("utf-8")
    return int.from_bytes(hashlib.sha256(material).digest()[:8], "big") % modulus


def _route_seed(case_id: str, model_seed: int) -> int:
    del case_id
    return 10_000 + model_seed


def _peak_rss_mib() -> float:
    raw = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    divisor = 1024.0 * 1024.0 if sys.platform == "darwin" else 1024.0
    return raw / divisor


def _sync(device: str) -> None:
    if device.startswith("cuda") and torch.cuda.is_available():
        torch.cuda.synchronize()


def _assert_monolith_sha(path: Path) -> str:
    if not path.is_file():
        raise FileNotFoundError(f"EBRT monolith not found: {path}")
    actual = _sha256(path)
    if actual != EXPECTED_MONOLITH_SHA256:
        raise RuntimeError(
            "frozen monolith SHA256 mismatch: "
            f"expected={EXPECTED_MONOLITH_SHA256} actual={actual} path={path}"
        )
    return actual


def _load_monolith(path: Path) -> Any:
    _assert_monolith_sha(path)
    module_name = "ebrt_monolith_v0_1_frozen_benchmark"
    sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not create import spec for {path}")
    module = importlib.util.module_from_spec(spec)
    # dataclasses resolves annotation owners through sys.modules during import.
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _observation(
    topic: str,
    stance: float,
    text: str,
    *,
    confidence: float = 1.0,
    revision_cue: float = 1.0,
) -> dict[str, Any]:
    return {
        "topic": topic,
        "stance": float(stance),
        "text": text,
        "confidence": float(confidence),
        "revision_cue": float(revision_cue),
    }


def _stance_label(value: float) -> str:
    if value > 0.15:
        return "supports"
    if value < -0.15:
        return "rejects"
    return "uncertain"


def _derive_expected_events(
    observations: Sequence[Mapping[str, Any]], threshold: float = 0.55
) -> tuple[ExpectedEvent, ...]:
    """Independent structured-oracle labeler matching the documented contract."""

    anchors: dict[str, int] = {}
    events: list[ExpectedEvent] = []
    for source_step, current in enumerate(observations):
        topic = str(current["topic"]).strip().lower()
        if topic not in anchors:
            anchors[topic] = source_step
            continue
        prior_step = anchors[topic]
        prior = observations[prior_step]
        current_stance = float(current["stance"])
        prior_stance = float(prior["stance"])
        current_confidence = float(current.get("confidence", 1.0))
        prior_confidence = float(prior.get("confidence", 1.0))
        cue = float(current.get("revision_cue", 1.0))
        event_score = (
            abs(current_stance - prior_stance)
            * 0.5
            * min(current_confidence, prior_confidence)
            * cue
        )
        if event_score > 0.0 and event_score >= threshold:
            revision_target = prior_stance + cue * current_confidence * (
                current_stance - prior_stance
            )
            events.append(
                ExpectedEvent(
                    source_step=source_step,
                    topic=topic,
                    target_steps=(prior_step,),
                    revision_target=float(revision_target),
                )
            )
            anchors[topic] = source_step
        elif prior_confidence < threshold and current_confidence > prior_confidence:
            anchors[topic] = source_step
    return tuple(events)


def _expected_labels(
    observations: Sequence[Mapping[str, Any]],
) -> dict[str, str]:
    latest: dict[str, Mapping[str, Any]] = {}
    for item in observations:
        latest[str(item["topic"]).strip().lower()] = item
    return {
        topic: _stance_label(float(item["stance"]) * float(item.get("confidence", 1.0)))
        for topic, item in latest.items()
    }


def _make_case(
    case_id: str,
    family: str,
    observations: Sequence[Mapping[str, Any]],
    *,
    routing_informative: bool | None = None,
    config_overrides: Mapping[str, Any] | None = None,
    note: str = "",
) -> BenchmarkCase:
    clean = tuple(dict(item) for item in observations)
    expected = _derive_expected_events(clean)
    if routing_informative is None:
        informative = any(
            sum(
                1
                for prior in clean[: event.source_step]
                if str(prior["topic"]).strip().lower() == event.topic
            )
            > len(event.target_steps)
            for event in expected
        )
    else:
        informative = routing_informative
    overrides = dict(config_overrides or {})
    expected_suppressed_events = max(
        0, len(expected) - int(overrides.get("max_events", 4))
    )
    return BenchmarkCase(
        case_id=case_id,
        family=family,
        observations=clean,
        expected_events=expected,
        expected_final_labels=_expected_labels(clean),
        routing_informative=informative,
        expected_suppressed_events=expected_suppressed_events,
        config_overrides=overrides,
        note=note,
    )


def build_correctness_cases() -> list[BenchmarkCase]:
    """Return the fixed, auditable 48-case v0.1 correctness suite."""

    cases: list[BenchmarkCase] = []

    # 6 stable trajectories: same-topic changes stay safely below threshold.
    for index in range(6):
        sign = 1.0 if index % 2 == 0 else -1.0
        initial = sign * (0.65 + 0.04 * (index % 3))
        later = initial - sign * (0.08 + 0.01 * index)
        cases.append(
            _make_case(
                f"stable_{index:02d}",
                "stable_no_shift",
                [
                    _observation("context", 0.05, f"stable context {index}"),
                    _observation("claim", initial, f"stable anchor {index}"),
                    _observation("aux", 0.25, f"stable auxiliary {index}"),
                    _observation("claim", later, f"stable confirmation {index}"),
                ],
                routing_informative=False,
                note="No event should be detected.",
            )
        )

    # 6 event scores just below the default threshold.
    below_differences = (1.00, 1.02, 1.04, 1.06, 1.08, 1.09)
    for index, difference in enumerate(below_differences):
        sign = 1.0 if index % 2 == 0 else -1.0
        initial = sign
        later = initial - sign * difference
        cases.append(
            _make_case(
                f"threshold_negative_{index:02d}",
                "threshold_negative",
                [
                    _observation("claim", initial, f"negative anchor {index}"),
                    _observation("context", 0.10, f"negative context {index}"),
                    _observation("claim", later, f"negative boundary {index}"),
                ],
                routing_informative=False,
                note=f"Expected event score={0.5 * difference:.3f} < 0.55.",
            )
        )

    # 6 threshold-equal/positive cases.
    positive_differences = (1.10, 1.11, 1.20, 1.40, 1.60, 2.00)
    for index, difference in enumerate(positive_differences):
        sign = 1.0 if index % 2 == 0 else -1.0
        initial = sign
        later = initial - sign * difference
        cases.append(
            _make_case(
                f"threshold_positive_{index:02d}",
                "threshold_positive",
                [
                    _observation("claim", initial, f"positive anchor {index}"),
                    _observation("context", -0.05, f"positive context {index}"),
                    _observation("claim", later, f"positive boundary {index}"),
                ],
                routing_informative=False,
                note=f"Expected event score={0.5 * difference:.3f} >= 0.55.",
            )
        )

    # 6 simple single-anchor premise shifts.
    for index in range(6):
        sign = 1.0 if index % 2 == 0 else -1.0
        initial = sign * (0.80 + 0.04 * (index % 3))
        current = -sign * (0.35 + 0.05 * (index % 3))
        cases.append(
            _make_case(
                f"single_shift_{index:02d}",
                "single_anchor_shift",
                [
                    _observation("route", -0.20, f"single route {index}"),
                    _observation("claim", initial, f"single anchor {index}"),
                    _observation("budget", 0.30, f"single budget {index}"),
                    _observation("claim", current, f"single shift {index}"),
                ],
                routing_informative=False,
                note="One eligible same-topic target; mechanism efficacy only.",
            )
        )

    # 12 routing cases: aligned, recency trap, contradiction trap, stale anchor.
    for index in range(3):
        cases.append(
            _make_case(
                f"routing_aligned_{index:02d}",
                "multi_anchor_routing",
                [
                    _observation("claim", 1.00, f"aligned active anchor {index}"),
                    _observation(
                        "claim", 0.20 + 0.08 * index, f"aligned distractor {index}"
                    ),
                    _observation("context", 0.10, f"aligned context {index}"),
                    _observation(
                        "claim", -0.45 - 0.05 * index, f"aligned shift {index}"
                    ),
                ],
                routing_informative=True,
                note="Contradiction signal should favor the active anchor.",
            )
        )
    for index in range(3):
        cases.append(
            _make_case(
                f"routing_recency_trap_{index:02d}",
                "multi_anchor_routing",
                [
                    _observation("claim", 1.00, f"recency active anchor {index}"),
                    _observation("context", 0.10, f"recency context {index}"),
                    _observation(
                        "claim", 0.98 - 0.005 * index, f"recency distractor {index}"
                    ),
                    _observation(
                        "claim", -0.20 - 0.02 * index, f"recency shift {index}"
                    ),
                ],
                routing_informative=True,
                note="A nearly identical recent observation can beat the active anchor.",
            )
        )
    for index in range(3):
        cases.append(
            _make_case(
                f"routing_contradiction_trap_{index:02d}",
                "multi_anchor_routing",
                [
                    _observation("claim", 0.40, f"contradiction active anchor {index}"),
                    _observation("context", -0.10, f"contradiction context {index}"),
                    _observation(
                        "claim",
                        1.00 - 0.02 * index,
                        f"contradiction distractor {index}",
                    ),
                    _observation("claim", -0.80, f"contradiction shift {index}"),
                ],
                routing_informative=True,
                note="An inactive extreme stance has stronger contradiction than the active anchor.",
            )
        )
    for index in range(3):
        cases.append(
            _make_case(
                f"routing_stale_anchor_{index:02d}",
                "multi_anchor_routing",
                [
                    _observation("claim", 1.00, f"stale first anchor {index}"),
                    _observation("context", 0.05, f"stale context {index}"),
                    _observation("claim", -0.30, f"stale first shift {index}"),
                    _observation(
                        "claim",
                        -0.29 + 0.002 * index,
                        f"stale recent distractor {index}",
                    ),
                    _observation("claim", 0.80, f"stale second shift {index}"),
                ],
                routing_informative=True,
                note="The second event should target the committed anchor, not a recent stale observation.",
            )
        )

    # 6 multi-topic trajectories; cross-topic observations are routing negatives.
    for index in range(6):
        sign = 1.0 if index % 2 == 0 else -1.0
        cases.append(
            _make_case(
                f"interleaved_topics_{index:02d}",
                "interleaved_topics",
                [
                    _observation(
                        "primary", sign, f"interleaved primary anchor {index}"
                    ),
                    _observation("budget", 0.30, f"interleaved budget {index}"),
                    _observation("route", -0.25, f"interleaved route {index}"),
                    _observation("schedule", 0.45, f"interleaved schedule {index}"),
                    _observation("budget", 0.25, f"interleaved budget repeat {index}"),
                    _observation("primary", -0.35 * sign, f"interleaved shift {index}"),
                ],
                routing_informative=False,
                note="Only the same-topic earlier state is routing-eligible.",
            )
        )

    # 4 sequential/hysteresis/budget cases.
    cases.append(
        _make_case(
            "sequential_two_events",
            "sequential_and_budget",
            [
                _observation("claim", 1.00, "sequential initial"),
                _observation("context", 0.10, "sequential context"),
                _observation("claim", -0.30, "sequential first shift"),
                _observation("claim", -0.25, "sequential confirmation"),
                _observation("claim", 0.85, "sequential second shift"),
            ],
            routing_informative=True,
            note="Both events should be committed with the default budget.",
        )
    )
    cases.append(
        _make_case(
            "sequential_budget_one",
            "sequential_and_budget",
            [
                _observation("claim", 1.00, "budget initial"),
                _observation("context", 0.10, "budget context"),
                _observation("claim", -0.30, "budget first shift"),
                _observation("claim", -0.25, "budget confirmation"),
                _observation("claim", 0.85, "budget suppressed shift"),
            ],
            routing_informative=True,
            config_overrides={"max_events": 1},
            note="The second event is detected but suppressed by max_events=1.",
        )
    )
    cases.append(
        _make_case(
            "weak_preview_confirmation",
            "sequential_and_budget",
            [
                _observation("claim", 1.00, "preview initial"),
                _observation(
                    "claim",
                    -1.00,
                    "weak preview",
                    confidence=0.20,
                ),
                _observation("claim", -1.00, "strong confirmation"),
            ],
            routing_informative=True,
            note="A weak preview must not mask the later high-confidence event.",
        )
    )
    cases.append(
        _make_case(
            "weak_initial_anchor_promotion",
            "sequential_and_budget",
            [
                _observation(
                    "claim",
                    1.00,
                    "unestablished guess",
                    confidence=0.00,
                ),
                _observation("claim", -1.00, "promoted anchor"),
                _observation("claim", 1.00, "promotion first shift"),
                _observation("claim", -1.00, "promotion second shift"),
            ],
            routing_informative=True,
            note="The zero-confidence initial guess must be replaced as the anchor.",
        )
    )

    # 2 longer correctness cases.
    for length in (32, 64):
        observations: list[dict[str, Any]] = [
            _observation("claim", 1.00, f"long anchor length {length}")
        ]
        auxiliary_topics = ("context", "budget", "route")
        for step in range(1, length - 1):
            topic = auxiliary_topics[(step - 1) % len(auxiliary_topics)]
            stance = {"context": 0.10, "budget": 0.30, "route": -0.20}[topic]
            observations.append(
                _observation(topic, stance, f"long filler {length}:{step}")
            )
        observations.append(
            _observation("claim", -0.35, f"long final shift length {length}")
        )
        cases.append(
            _make_case(
                f"long_horizon_{length}",
                "long_horizon_correctness",
                observations,
                routing_informative=False,
                note="Long no-distractor shift for accounting and state propagation.",
            )
        )

    if len(cases) != 48:
        raise AssertionError(
            f"correctness suite must contain 48 cases, got {len(cases)}"
        )
    identifiers = [item.case_id for item in cases]
    if len(set(identifiers)) != len(identifiers):
        raise AssertionError("correctness case IDs must be unique")
    expected_family_counts = {
        "stable_no_shift": 6,
        "threshold_negative": 6,
        "threshold_positive": 6,
        "single_anchor_shift": 6,
        "multi_anchor_routing": 12,
        "interleaved_topics": 6,
        "sequential_and_budget": 4,
        "long_horizon_correctness": 2,
    }
    observed_family_counts: dict[str, int] = defaultdict(int)
    for case in cases:
        observed_family_counts[case.family] += 1
    if dict(observed_family_counts) != expected_family_counts:
        raise AssertionError(
            "correctness family counts changed: "
            f"expected={expected_family_counts} actual={dict(observed_family_counts)}"
        )
    for case in cases:
        if not case.routing_informative:
            continue
        top_k = int(case.config_overrides.get("top_k", 1))
        informative = False
        for event in case.expected_events:
            eligible_count = sum(
                1
                for prior in case.observations[: event.source_step]
                if str(prior["topic"]).strip().lower() == event.topic
            )
            informative = informative or eligible_count > top_k
        if not informative:
            raise AssertionError(
                f"routing-informative case has no choice beyond top_k: {case.case_id}"
            )
    return cases


def _event_count_case(event_count: int, length: int = 32) -> BenchmarkCase:
    event_positions = {
        0: (),
        1: (length - 1,),
        2: (length // 2, length - 1),
        4: (length // 4, length // 2, 3 * length // 4, length - 1),
    }[event_count]
    current_stance = 1.0
    observations: list[dict[str, Any]] = [
        _observation("claim", current_stance, f"event-count {event_count} anchor")
    ]
    for step in range(1, length):
        if step in event_positions:
            current_stance = -0.35 if current_stance > 0 else 0.85
            observations.append(
                _observation(
                    "claim",
                    current_stance,
                    f"event-count {event_count} shift {step}",
                )
            )
        else:
            observations.append(
                _observation("context", 0.10, f"event-count filler {step}")
            )
    return _make_case(
        f"scale_event_count_{event_count}",
        "scaling_event_count",
        observations,
        routing_informative=event_count > 1,
        config_overrides={"max_events": max(4, event_count)},
    )


def build_scaling_cases(lengths: Sequence[int]) -> list[BenchmarkCase]:
    cases: list[BenchmarkCase] = []
    for length in lengths:
        if length < 4:
            raise ValueError("scaling lengths must be >= 4")
        stable = [
            _observation("claim", 0.20, f"scaling stable {length}:{step}")
            for step in range(length)
        ]
        cases.append(
            _make_case(
                f"scale_no_event_t{length}",
                "scaling_length_no_event",
                stable,
                routing_informative=False,
            )
        )
        shifted = [_observation("claim", 1.00, f"scaling anchor {length}")]
        shifted.extend(
            _observation("claim", 0.90, f"scaling distractor {length}:{step}")
            for step in range(1, length - 1)
        )
        shifted.append(_observation("claim", -0.30, f"scaling shift {length}"))
        cases.append(
            _make_case(
                f"scale_one_event_t{length}",
                "scaling_length_one_event",
                shifted,
                routing_informative=True,
            )
        )

    for revision_steps in (1, 4, 8, 16, 32, 64):
        observations = [_observation("claim", 1.00, "step-sweep anchor")]
        observations.extend(
            _observation("context", 0.10, f"step-sweep filler {step}")
            for step in range(1, 31)
        )
        observations.append(_observation("claim", -0.35, "step-sweep shift"))
        cases.append(
            _make_case(
                f"scale_revision_steps_{revision_steps}",
                "scaling_revision_steps",
                observations,
                routing_informative=False,
                config_overrides={"revision_steps": revision_steps},
            )
        )

    cases.extend(_event_count_case(count) for count in (0, 1, 2, 4))

    for label, target_step in (("far", 0), ("middle", 16), ("near", 30)):
        observations = [
            _observation("context", 0.10, f"distance filler {step}")
            for step in range(32)
        ]
        observations[target_step] = _observation(
            "claim", 1.00, f"distance {label} anchor"
        )
        observations[-1] = _observation("claim", -0.35, f"distance {label} shift")
        cases.append(
            _make_case(
                f"scale_replay_distance_{label}",
                "scaling_replay_distance",
                observations,
                routing_informative=False,
            )
        )

    for top_k in (1, 2, 4):
        observations = [
            _observation("claim", 1.00, "top-k active anchor"),
            _observation("claim", 0.90, "top-k distractor one"),
            _observation("claim", 0.80, "top-k distractor two"),
            _observation("claim", 0.70, "top-k distractor three"),
            _observation("context", 0.10, "top-k context"),
            _observation("claim", -0.35, "top-k shift"),
        ]
        cases.append(
            _make_case(
                f"scale_top_k_{top_k}",
                "scaling_top_k",
                observations,
                routing_informative=True,
                config_overrides={"top_k": top_k},
            )
        )

    identifiers = [item.case_id for item in cases]
    if len(set(identifiers)) != len(identifiers):
        raise AssertionError("scaling case IDs must be unique")
    return cases


def _build_config(
    module: Any,
    case: BenchmarkCase,
    *,
    model_seed: int,
    revision_steps: int,
    device: str,
    dtype: str,
) -> Any:
    values: dict[str, Any] = {
        "seed": model_seed,
        "revision_steps": revision_steps,
        "device": device,
        "dtype": dtype,
    }
    values.update(case.config_overrides)
    config = module.EBRTConfig(**values)
    config.validate()
    return config


def _random_reasoner_class(module: Any) -> type:
    class RandomRoutingReasoner(module.EventDrivenBackwardReasoner):
        def __init__(self, config: Any, route_seed: int) -> None:
            super().__init__(config)
            self._benchmark_route_rng = random.Random(route_seed)

        def _detect_event(
            self,
            observations: Sequence[Any],
            source_step: int,
            prefix_states: torch.Tensor,
            active_prior: Any,
        ) -> Any:
            event = super()._detect_event(
                observations, source_step, prefix_states, active_prior
            )
            if event is None:
                return None
            topic = observations[source_step].topic.strip().lower()
            eligible = [
                index
                for index in range(source_step)
                if observations[index].topic.strip().lower() == topic
            ]
            k = min(len(event.target_steps), len(eligible))
            selected = tuple(sorted(self._benchmark_route_rng.sample(eligible, k=k)))
            return dataclasses.replace(event, target_steps=selected)

    return RandomRoutingReasoner


def _oracle_reasoner_class(module: Any) -> type:
    class OracleRoutingReasoner(module.EventDrivenBackwardReasoner):
        def __init__(self, config: Any, expected: Mapping[int, ExpectedEvent]) -> None:
            super().__init__(config)
            self._benchmark_expected = dict(expected)

        def _detect_event(
            self,
            observations: Sequence[Any],
            source_step: int,
            prefix_states: torch.Tensor,
            active_prior: Any,
        ) -> Any:
            event = super()._detect_event(
                observations, source_step, prefix_states, active_prior
            )
            if event is None or source_step not in self._benchmark_expected:
                return event
            gold = self._benchmark_expected[source_step]
            topic = observations[source_step].topic.strip().lower()
            eligible = [
                index
                for index in range(source_step)
                if observations[index].topic.strip().lower() == topic
            ]
            k = min(len(event.target_steps), len(eligible))
            selected: list[int] = []
            for target in gold.target_steps:
                if target in eligible and target not in selected and len(selected) < k:
                    selected.append(target)
            for target in event.target_steps:
                if target in eligible and target not in selected and len(selected) < k:
                    selected.append(target)
            for target in eligible:
                if target not in selected and len(selected) < k:
                    selected.append(target)
            if len(selected) != k:
                raise AssertionError("oracle routing could not preserve target count")
            return dataclasses.replace(event, target_steps=tuple(sorted(selected)))

    return OracleRoutingReasoner


def _to_observations(module: Any, case: BenchmarkCase) -> list[Any]:
    return [module.Observation.from_mapping(dict(item)) for item in case.observations]


def _run_forward_only(
    module: Any,
    case: BenchmarkCase,
    config: Any,
) -> Execution:
    external_started = time.perf_counter_ns()
    engine = module.EventDrivenBackwardReasoner(config)
    observations = _to_observations(module, case)
    for observation in observations:
        observation.validate()
    internal_started = time.perf_counter_ns()
    engine.decode_call_count = 0
    engine.generator.step_call_count = 0
    core_hash_before = engine.generator.frozen_hash()
    engine.codec.prepare_topics(observations)
    encoded = engine.codec.encode_many(observations)
    controls = torch.zeros(
        len(observations),
        config.control_dim,
        device=encoded.device,
        dtype=encoded.dtype,
    )
    states = engine.generator.rollout(encoded, controls).detach()
    decoded = engine._decode(observations, states)
    core_hash_after = engine.generator.frozen_hash()
    internal_elapsed_ms = (time.perf_counter_ns() - internal_started) / 1e6
    _sync(config.device)
    external_wall_ms = (time.perf_counter_ns() - external_started) / 1e6
    return Execution(
        arm="A_forward_only_1pass",
        config=config,
        engine=engine,
        observations=observations,
        baseline_states=states.cpu(),
        final_states=states.cpu(),
        controls=controls.detach().cpu(),
        detected_events=[],
        committed_events=[],
        suppressed_events=[],
        revisions=[],
        decoded=decoded,
        decode_call_count=engine.decode_call_count,
        core_hash_before=core_hash_before,
        core_hash_after=core_hash_after,
        backward_calls=0,
        generator_step_calls=engine.generator.step_call_count,
        internal_elapsed_ms=internal_elapsed_ms,
        external_wall_ms=external_wall_ms,
        process_peak_rss_mib=_peak_rss_mib(),
    )


def run_arm(
    module: Any,
    case: BenchmarkCase,
    arm: str,
    *,
    model_seed: int,
    route_seed: int,
    revision_steps: int,
    device: str = "cpu",
    dtype: str = "float32",
) -> Execution:
    if arm not in ARMS:
        raise ValueError(f"unknown benchmark arm: {arm}")
    config = _build_config(
        module,
        case,
        model_seed=model_seed,
        revision_steps=revision_steps,
        device=device,
        dtype=dtype,
    )
    if arm == "A_forward_only_1pass":
        return _run_forward_only(module, case, config)

    expected = {event.source_step: event for event in case.expected_events}
    external_started = time.perf_counter_ns()
    if arm == "B_detect_only_budget0":
        config = dataclasses.replace(config, max_events=0)
        engine = module.EventDrivenBackwardReasoner(config)
    elif arm == "C_random_route_revision":
        engine = _random_reasoner_class(module)(config, route_seed)
    elif arm == "D_ebrt_full":
        engine = module.EventDrivenBackwardReasoner(config)
    elif arm == "E_oracle_route_revision":
        engine = _oracle_reasoner_class(module)(config, expected)
    else:  # pragma: no cover - ARMS validation above keeps this unreachable.
        raise AssertionError(arm)

    observations = _to_observations(module, case)
    result = engine.run(observations)
    _sync(config.device)
    external_wall_ms = (time.perf_counter_ns() - external_started) / 1e6
    detected_events = sorted(
        [*result.events, *result.suppressed_events],
        key=lambda item: item.source_step,
    )
    return Execution(
        arm=arm,
        config=config,
        engine=engine,
        observations=observations,
        baseline_states=result.baseline_states,
        final_states=result.final_states,
        controls=result.controls,
        detected_events=detected_events,
        committed_events=list(result.events),
        suppressed_events=list(result.suppressed_events),
        revisions=list(result.revisions),
        decoded=result.decoded,
        decode_call_count=result.decode_call_count,
        core_hash_before=result.core_hash_before,
        core_hash_after=result.core_hash_after,
        backward_calls=result.backward_calls,
        generator_step_calls=result.generator_step_calls,
        internal_elapsed_ms=result.elapsed_ms,
        external_wall_ms=external_wall_ms,
        process_peak_rss_mib=_peak_rss_mib(),
    )


def _belief_score(
    execution: Execution, states: torch.Tensor, step: int, topic: str
) -> float:
    q = execution.config.topic_dim
    topic_vector = execution.engine.codec.topic_vector(topic).detach().cpu()
    return float((states[step, q : 2 * q] @ topic_vector).item())


def _safe_ratio(numerator: float, denominator: float) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator


def _event_metrics(
    case: BenchmarkCase, execution: Execution
) -> dict[str, int | float | None]:
    if execution.arm == "A_forward_only_1pass":
        return {
            "event_tp": None,
            "event_fp": None,
            "event_fn": None,
            "event_precision": None,
            "event_recall": None,
            "event_f1": None,
        }
    expected = {item.source_step for item in case.expected_events}
    detected = {item.source_step for item in execution.detected_events}
    tp = len(expected & detected)
    fp = len(detected - expected)
    fn = len(expected - detected)
    precision = _safe_ratio(tp, tp + fp)
    recall = _safe_ratio(tp, tp + fn)
    if precision is None or recall is None or precision + recall == 0:
        f1 = None if precision is None or recall is None else 0.0
    else:
        f1 = 2.0 * precision * recall / (precision + recall)
    return {
        "event_tp": tp,
        "event_fp": fp,
        "event_fn": fn,
        "event_precision": precision,
        "event_recall": recall,
        "event_f1": f1,
    }


def _routing_metrics(
    case: BenchmarkCase, execution: Execution
) -> dict[str, int | float | None]:
    if execution.arm not in {
        "C_random_route_revision",
        "D_ebrt_full",
        "E_oracle_route_revision",
    }:
        return {
            "gold_route_count": None,
            "route_hit_count": None,
            "routing_recall_at_k": None,
            "routing_recall_conditional": None,
            "executed_gold_route_count": None,
            "executed_route_hit_count": None,
            "executed_routing_recall_at_k": None,
            "attention_mass_on_gold": None,
        }
    detected = {item.source_step: item for item in execution.detected_events}
    committed = {item.source_step: item for item in execution.committed_events}
    gold_count = 0
    hit_count = 0
    conditional_gold_count = 0
    conditional_hit_count = 0
    executed_gold_count = 0
    executed_hit_count = 0
    masses: list[float] = []
    for expected in case.expected_events:
        if expected.source_step not in detected:
            gold_count += len(expected.target_steps)
            masses.extend(0.0 for _ in expected.target_steps)
            continue
        event = detected[expected.source_step]
        selected = set(event.target_steps)
        for target in expected.target_steps:
            gold_count += 1
            conditional_gold_count += 1
            hit_count += int(target in selected)
            conditional_hit_count += int(target in selected)
            mass = (
                float(event.attention_weights[target])
                if target < len(event.attention_weights)
                else 0.0
            )
            masses.append(mass)
        if expected.source_step in committed:
            executed = committed[expected.source_step]
            executed_selected = set(executed.target_steps)
            for target in expected.target_steps:
                executed_gold_count += 1
                executed_hit_count += int(target in executed_selected)
    return {
        "gold_route_count": gold_count,
        "route_hit_count": hit_count,
        "routing_recall_at_k": _safe_ratio(hit_count, gold_count),
        "routing_recall_conditional": _safe_ratio(
            conditional_hit_count, conditional_gold_count
        ),
        "executed_gold_route_count": executed_gold_count,
        "executed_route_hit_count": executed_hit_count,
        "executed_routing_recall_at_k": _safe_ratio(
            executed_hit_count, executed_gold_count
        ),
        "attention_mass_on_gold": statistics.fmean(masses) if masses else None,
    }


def _task_metrics(case: BenchmarkCase, execution: Execution) -> dict[str, Any]:
    actual = {
        str(item["topic"]).strip().lower(): str(item["label"])
        for item in execution.decoded.get("beliefs", [])
    }
    correct = sum(
        int(actual.get(topic) == expected)
        for topic, expected in case.expected_final_labels.items()
    )
    total = len(case.expected_final_labels)
    target_topics = sorted({event.topic for event in case.expected_events})
    target_correct = sum(
        int(actual.get(topic) == case.expected_final_labels.get(topic))
        for topic in target_topics
    )
    return {
        "correct_topic_count": correct,
        "expected_topic_count": total,
        "toy_task_success": int(correct == total),
        "topic_accuracy": _safe_ratio(correct, total),
        "target_topic_count": len(target_topics),
        "target_topic_correct_count": target_correct,
        "target_topic_success": (
            int(target_correct == len(target_topics)) if target_topics else None
        ),
        "target_topic_accuracy": _safe_ratio(target_correct, len(target_topics)),
    }


def _distance_metrics(case: BenchmarkCase, execution: Execution) -> dict[str, Any]:
    source_gains: list[float] = []
    target_gains: list[float] = []
    baseline_source_distances: list[float] = []
    final_source_distances: list[float] = []
    for expected in case.expected_events:
        baseline_source = _belief_score(
            execution, execution.baseline_states, expected.source_step, expected.topic
        )
        final_source = _belief_score(
            execution, execution.final_states, expected.source_step, expected.topic
        )
        baseline_distance = abs(baseline_source - expected.revision_target)
        final_distance = abs(final_source - expected.revision_target)
        baseline_source_distances.append(baseline_distance)
        final_source_distances.append(final_distance)
        source_gains.append(baseline_distance - final_distance)
        for target_step in expected.target_steps:
            baseline_target = _belief_score(
                execution, execution.baseline_states, target_step, expected.topic
            )
            final_target = _belief_score(
                execution, execution.final_states, target_step, expected.topic
            )
            target_gains.append(
                abs(baseline_target - expected.revision_target)
                - abs(final_target - expected.revision_target)
            )
    return {
        "baseline_source_distance": (
            statistics.fmean(baseline_source_distances)
            if baseline_source_distances
            else None
        ),
        "final_source_distance": (
            statistics.fmean(final_source_distances) if final_source_distances else None
        ),
        "source_distance_gain": statistics.fmean(source_gains)
        if source_gains
        else None,
        "target_distance_gain": statistics.fmean(target_gains)
        if target_gains
        else None,
    }


def _energy_metrics(execution: Execution) -> dict[str, Any]:
    drops = [item.energy_before - item.energy_after for item in execution.revisions]
    relative = [
        (item.energy_before - item.energy_after) / max(abs(item.energy_before), 1e-12)
        for item in execution.revisions
    ]
    return {
        "energy_drop_abs": sum(drops) if drops else None,
        "energy_drop_relative_mean": statistics.fmean(relative) if relative else None,
        "attempted_revision_count": len(execution.revisions),
        "accepted_revision_count": sum(
            int(item.accepted) for item in execution.revisions
        ),
        "rollback_count": sum(int(item.rolled_back) for item in execution.revisions),
        "revision_wall_ms": sum(
            float(item.wall_time_ms) for item in execution.revisions
        ),
        "reported_replayed_state_steps": sum(
            int(item.replayed_state_steps) for item in execution.revisions
        ),
    }


def make_trial_row(
    case: BenchmarkCase,
    execution: Execution,
    *,
    mode: str,
    model_seed: int,
    route_seed: int,
    repeat_index: int,
) -> dict[str, Any]:
    event = _event_metrics(case, execution)
    routing = _routing_metrics(case, execution)
    task = _task_metrics(case, execution)
    distance = _distance_metrics(case, execution)
    energy = _energy_metrics(execution)
    trajectory_length = len(case.observations)
    prefix_recompute_steps = sum(
        int(item.event.source_step) + 1 for item in execution.revisions
    )
    replay_formula_steps = sum(
        (execution.config.revision_steps + 2)
        * (item.event.source_step - item.earliest_replay_step + 1)
        for item in execution.revisions
    )
    if execution.arm == "A_forward_only_1pass":
        expected_generator_steps = trajectory_length
        base_forward_steps = trajectory_length
    else:
        expected_generator_steps = (
            2 * trajectory_length + prefix_recompute_steps + replay_formula_steps
        )
        base_forward_steps = 2 * trajectory_length
    max_control_norm = float(
        torch.linalg.vector_norm(execution.controls, dim=-1).max().item()
    )
    finite = bool(
        torch.isfinite(execution.final_states).all().item()
        and torch.isfinite(execution.controls).all().item()
    )
    committed_targets = {
        target
        for revision in execution.revisions
        for target in revision.event.target_steps
    }
    non_target_indices = [
        index for index in range(trajectory_length) if index not in committed_targets
    ]
    if non_target_indices:
        non_target_control_max = float(
            torch.linalg.vector_norm(execution.controls[non_target_indices], dim=-1)
            .max()
            .item()
        )
    else:
        non_target_control_max = 0.0
    state_delta_max = float(
        torch.linalg.vector_norm(
            execution.final_states - execution.baseline_states, dim=-1
        )
        .max()
        .item()
    )
    pre_target_drift_values = [
        float(value)
        for revision in execution.revisions
        for value in revision.state_delta_norms[: revision.earliest_replay_step]
    ]
    pre_target_drift_max = max(pre_target_drift_values, default=0.0)
    revised_topics = {
        execution.observations[event.source_step].topic.strip().lower()
        for event in execution.committed_events
    }
    unrelated_indices = [
        index
        for index, observation in enumerate(execution.observations)
        if revised_topics and observation.topic.strip().lower() not in revised_topics
    ]
    unrelated_topic_state_drift_max = (
        float(
            torch.linalg.vector_norm(
                execution.final_states[unrelated_indices]
                - execution.baseline_states[unrelated_indices],
                dim=-1,
            )
            .max()
            .item()
        )
        if unrelated_indices
        else 0.0
    )
    expected_suppressed = (
        None
        if execution.arm == "A_forward_only_1pass"
        else (
            len(case.expected_events)
            if execution.arm == "B_detect_only_budget0"
            else case.expected_suppressed_events
        )
    )
    revision_overhead_steps = execution.generator_step_calls - base_forward_steps
    source_gain_per_revision_step = (
        float(distance["source_distance_gain"]) / revision_overhead_steps
        if distance["source_distance_gain"] is not None and revision_overhead_steps > 0
        else None
    )
    target_gain_per_backward_call = (
        float(distance["target_distance_gain"]) / execution.backward_calls
        if distance["target_distance_gain"] is not None and execution.backward_calls > 0
        else None
    )
    row: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "mode": mode,
        "run_id": f"{mode}:{case.case_id}:{execution.arm}:{model_seed}:{repeat_index}",
        "case_id": case.case_id,
        "family": case.family,
        "arm": execution.arm,
        "model_seed": model_seed,
        "route_seed": route_seed,
        "repeat_index": repeat_index,
        "trajectory_length": trajectory_length,
        "routing_informative": int(case.routing_informative),
        "revision_steps": execution.config.revision_steps,
        "top_k": execution.config.top_k,
        "max_events": execution.config.max_events,
        "expected_event_count": len(case.expected_events),
        "expected_suppressed_event_count": expected_suppressed,
        "detected_event_count": len(execution.detected_events),
        "committed_event_count": len(execution.committed_events),
        "suppressed_event_count": len(execution.suppressed_events),
        **event,
        **routing,
        **task,
        **distance,
        **energy,
        "generator_step_calls": execution.generator_step_calls,
        "expected_generator_step_calls": expected_generator_steps,
        "generator_accounting_ok": int(
            execution.generator_step_calls == expected_generator_steps
        ),
        "base_forward_steps": base_forward_steps,
        "derived_revision_overhead_steps": (revision_overhead_steps),
        "prefix_recompute_steps": prefix_recompute_steps,
        "formula_replayed_state_steps": replay_formula_steps,
        "backward_calls": execution.backward_calls,
        "decode_call_count": execution.decode_call_count,
        "core_unchanged": int(execution.core_hash_before == execution.core_hash_after),
        "finite_outputs": int(finite),
        "max_control_norm_observed": max_control_norm,
        "control_norm_saturated": int(
            max_control_norm >= execution.config.max_control_norm - 1e-5
        ),
        "non_target_control_max": non_target_control_max,
        "state_delta_max": state_delta_max,
        "pre_target_state_drift_max": pre_target_drift_max,
        "unrelated_topic_state_drift_max": unrelated_topic_state_drift_max,
        "source_gain_per_revision_step": source_gain_per_revision_step,
        "target_gain_per_backward_call": target_gain_per_backward_call,
        "internal_elapsed_ms": execution.internal_elapsed_ms,
        "external_wall_ms": execution.external_wall_ms,
        # ru_maxrss is a process-lifetime high-water mark. It is useful for
        # diagnostics but is explicitly not a per-arm isolated memory delta.
        "process_cumulative_peak_rss_mib": execution.process_peak_rss_mib,
    }
    return row


def _numeric_values(rows: Sequence[Mapping[str, Any]], field_name: str) -> list[float]:
    values: list[float] = []
    for row in rows:
        value = row.get(field_name)
        if value is None or isinstance(value, bool):
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number):
            values.append(number)
    return values


def _percentile(values: Sequence[float], probability: float) -> float | None:
    if not values:
        return None
    if not 0.0 <= probability <= 1.0:
        raise ValueError("probability must be in [0, 1]")
    ordered = sorted(float(value) for value in values)
    if len(ordered) == 1:
        return ordered[0]
    position = probability * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _distribution_summary(values: Sequence[float]) -> dict[str, float | int | None]:
    clean = [float(value) for value in values if math.isfinite(float(value))]
    if not clean:
        return {
            "n": 0,
            "mean": None,
            "median": None,
            "p95": None,
            "mad": None,
            "minimum": None,
            "maximum": None,
        }
    median = statistics.median(clean)
    return {
        "n": len(clean),
        "mean": statistics.fmean(clean),
        "median": median,
        "p95": _percentile(clean, 0.95),
        "mad": statistics.median(abs(value - median) for value in clean),
        "minimum": min(clean),
        "maximum": max(clean),
    }


def _weighted_ratio(
    rows: Sequence[Mapping[str, Any]], numerator: str, denominator: str
) -> float | None:
    numerator_sum = 0.0
    denominator_sum = 0.0
    for row in rows:
        left = row.get(numerator)
        right = row.get(denominator)
        if left is None or right is None:
            continue
        numerator_sum += float(left)
        denominator_sum += float(right)
    return _safe_ratio(numerator_sum, denominator_sum)


def summarize_arms(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Aggregate correctness rows without treating seeds as independent cases."""

    summaries: list[dict[str, Any]] = []
    for arm in ARMS:
        selected = [row for row in rows if row.get("arm") == arm]
        if not selected:
            continue
        event_rows = [
            row for row in selected if row.get("target_topic_success") is not None
        ]
        stable_rows = [
            row for row in selected if int(row.get("expected_event_count", 0)) == 0
        ]
        informative = [
            row for row in selected if int(row.get("routing_informative", 0)) == 1
        ]
        latency = _distribution_summary(_numeric_values(selected, "external_wall_ms"))
        generator_steps = _distribution_summary(
            _numeric_values(selected, "generator_step_calls")
        )
        summaries.append(
            {
                "arm": arm,
                "trial_count": len(selected),
                "case_count": len({str(row["case_id"]) for row in selected}),
                "seed_count": len({int(row["model_seed"]) for row in selected}),
                "event_case_trial_count": len(event_rows),
                "target_topic_success_rate": (
                    statistics.fmean(
                        _numeric_values(event_rows, "target_topic_success")
                    )
                    if event_rows
                    else None
                ),
                "all_topic_success_rate": statistics.fmean(
                    _numeric_values(selected, "toy_task_success")
                ),
                "topic_accuracy_mean": statistics.fmean(
                    _numeric_values(selected, "topic_accuracy")
                ),
                "source_distance_gain_mean": (
                    statistics.fmean(
                        _numeric_values(event_rows, "source_distance_gain")
                    )
                    if _numeric_values(event_rows, "source_distance_gain")
                    else None
                ),
                "target_distance_gain_mean": (
                    statistics.fmean(
                        _numeric_values(event_rows, "target_distance_gain")
                    )
                    if _numeric_values(event_rows, "target_distance_gain")
                    else None
                ),
                "router_recall_at_k": _weighted_ratio(
                    selected, "route_hit_count", "gold_route_count"
                ),
                "executed_routing_recall_at_k": _weighted_ratio(
                    selected, "executed_route_hit_count", "executed_gold_route_count"
                ),
                "informative_router_recall_at_k": _weighted_ratio(
                    informative, "route_hit_count", "gold_route_count"
                ),
                "event_precision": _weighted_ratio(
                    selected, "event_tp", "detected_event_count"
                ),
                "event_recall": _weighted_ratio(
                    selected, "event_tp", "expected_event_count"
                ),
                "attempted_revisions_mean": statistics.fmean(
                    _numeric_values(selected, "attempted_revision_count")
                ),
                "accepted_revisions_mean": statistics.fmean(
                    _numeric_values(selected, "accepted_revision_count")
                ),
                "stable_attempted_revision_rate": (
                    statistics.fmean(
                        float(int(row.get("attempted_revision_count", 0)) > 0)
                        for row in stable_rows
                    )
                    if stable_rows
                    else None
                ),
                "stable_accepted_revision_rate": (
                    statistics.fmean(
                        float(int(row.get("accepted_revision_count", 0)) > 0)
                        for row in stable_rows
                    )
                    if stable_rows
                    else None
                ),
                "pre_target_state_drift_max": max(
                    _numeric_values(selected, "pre_target_state_drift_max"),
                    default=0.0,
                ),
                "unrelated_topic_state_drift_mean": statistics.fmean(
                    _numeric_values(selected, "unrelated_topic_state_drift_max")
                ),
                "source_gain_per_revision_step_mean": (
                    statistics.fmean(
                        _numeric_values(selected, "source_gain_per_revision_step")
                    )
                    if _numeric_values(selected, "source_gain_per_revision_step")
                    else None
                ),
                "target_gain_per_backward_call_mean": (
                    statistics.fmean(
                        _numeric_values(selected, "target_gain_per_backward_call")
                    )
                    if _numeric_values(selected, "target_gain_per_backward_call")
                    else None
                ),
                "external_wall_ms_median": latency["median"],
                "external_wall_ms_p95": latency["p95"],
                "external_wall_ms_mad": latency["mad"],
                "generator_steps_median": generator_steps["median"],
                "generator_steps_p95": generator_steps["p95"],
                "backward_calls_mean": statistics.fmean(
                    _numeric_values(selected, "backward_calls")
                ),
                "generator_accounting_pass_rate": statistics.fmean(
                    _numeric_values(selected, "generator_accounting_ok")
                ),
                "core_unchanged_rate": statistics.fmean(
                    _numeric_values(selected, "core_unchanged")
                ),
                "finite_output_rate": statistics.fmean(
                    _numeric_values(selected, "finite_outputs")
                ),
            }
        )
    return summaries


def exact_mcnemar_p_value(left_only: int, right_only: int) -> float:
    """Return the exact two-sided McNemar/binomial p-value."""

    if left_only < 0 or right_only < 0:
        raise ValueError("discordant counts must be non-negative")
    discordant = left_only + right_only
    if discordant == 0:
        return 1.0
    tail = sum(
        math.comb(discordant, index) for index in range(min(left_only, right_only) + 1)
    ) / (2.0**discordant)
    return min(1.0, 2.0 * tail)


def case_cluster_bootstrap_ci(
    case_deltas: Mapping[str, Sequence[float]],
    *,
    seed: int = 20_260_718,
    resamples: int = 2_000,
) -> dict[str, float | int | None]:
    """Bootstrap case-level means, preserving all seeds within each case."""

    if resamples < 1:
        raise ValueError("resamples must be >= 1")
    means = {
        str(case_id): statistics.fmean(float(value) for value in values)
        for case_id, values in case_deltas.items()
        if values
    }
    case_ids = sorted(means)
    if not case_ids:
        return {"case_count": 0, "estimate": None, "ci_low": None, "ci_high": None}
    estimate = statistics.fmean(means.values())
    rng = random.Random(seed)
    draws: list[float] = []
    for _ in range(resamples):
        sampled = [means[rng.choice(case_ids)] for _ in case_ids]
        draws.append(statistics.fmean(sampled))
    return {
        "case_count": len(case_ids),
        "estimate": estimate,
        "ci_low": _percentile(draws, 0.025),
        "ci_high": _percentile(draws, 0.975),
    }


def paired_contrasts(
    rows: Sequence[Mapping[str, Any]],
    *,
    bootstrap_seed: int = 20_260_718,
    bootstrap_resamples: int = 2_000,
) -> list[dict[str, Any]]:
    """Build paired arm contrasts keyed by case, model seed, and repeat."""

    indexed = {
        (
            str(row["case_id"]),
            int(row["model_seed"]),
            int(row.get("repeat_index", 0)),
            str(row["arm"]),
        ): row
        for row in rows
    }
    metrics = (
        "target_topic_success",
        "toy_task_success",
        "topic_accuracy",
        "source_distance_gain",
        "target_distance_gain",
        "external_wall_ms",
        "generator_step_calls",
    )
    results: list[dict[str, Any]] = []
    pair_keys = sorted(
        {
            (
                str(row["case_id"]),
                int(row["model_seed"]),
                int(row.get("repeat_index", 0)),
            )
            for row in rows
        }
    )
    for left_arm, right_arm, comparison in PAIRED_COMPARISONS:
        paired: list[tuple[str, Mapping[str, Any], Mapping[str, Any]]] = []
        for case_id, model_seed, repeat_index in pair_keys:
            left = indexed.get((case_id, model_seed, repeat_index, left_arm))
            right = indexed.get((case_id, model_seed, repeat_index, right_arm))
            if left is not None and right is not None:
                paired.append((case_id, left, right))
        metric_results: dict[str, Any] = {}
        for metric in metrics:
            deltas_by_case: dict[str, list[float]] = defaultdict(list)
            deltas: list[float] = []
            for case_id, left, right in paired:
                left_value = left.get(metric)
                right_value = right.get(metric)
                if left_value is None or right_value is None:
                    continue
                delta = float(left_value) - float(right_value)
                if math.isfinite(delta):
                    deltas.append(delta)
                    deltas_by_case[case_id].append(delta)
            bootstrap = case_cluster_bootstrap_ci(
                deltas_by_case,
                seed=bootstrap_seed
                + _stable_int(comparison, metric, modulus=10_000_000),
                resamples=bootstrap_resamples,
            )
            metric_results[metric] = {
                "paired_trial_count": len(deltas),
                "mean_delta": statistics.fmean(deltas) if deltas else None,
                "median_delta": statistics.median(deltas) if deltas else None,
                "case_cluster_bootstrap": bootstrap,
            }
        mcnemar: dict[str, Any] = {}
        for metric in ("target_topic_success", "toy_task_success"):
            left_only = 0
            right_only = 0
            concordant = 0
            paired_binary = 0
            for _, left, right in paired:
                left_value = left.get(metric)
                right_value = right.get(metric)
                if left_value is None or right_value is None:
                    continue
                left_binary = int(left_value)
                right_binary = int(right_value)
                paired_binary += 1
                if left_binary == right_binary:
                    concordant += 1
                elif left_binary == 1:
                    left_only += 1
                else:
                    right_only += 1
            mcnemar[metric] = {
                "paired_trial_count": paired_binary,
                "left_only_success": left_only,
                "right_only_success": right_only,
                "concordant": concordant,
                "exact_two_sided_p": exact_mcnemar_p_value(left_only, right_only),
            }
        results.append(
            {
                "comparison": comparison,
                "left_arm": left_arm,
                "right_arm": right_arm,
                "delta_direction": "left_minus_right",
                "paired_key": ["case_id", "model_seed", "repeat_index"],
                "metrics": metric_results,
                "mcnemar": mcnemar,
            }
        )
    return results


def build_statistical_summary(
    rows: Sequence[Mapping[str, Any]],
    *,
    bootstrap_seed: int = 20_260_718,
    bootstrap_resamples: int = 2_000,
) -> dict[str, Any]:
    return {
        "arm_summaries": summarize_arms(rows),
        "paired_contrasts": paired_contrasts(
            rows,
            bootstrap_seed=bootstrap_seed,
            bootstrap_resamples=bootstrap_resamples,
        ),
        "uncertainty_note": (
            "Confidence intervals resample case-level means while preserving all "
            "model seeds and paired arms within each case. They describe this fixed "
            "synthetic suite and do not establish external validity. Exact McNemar "
            "values are unadjusted repeated-seed diagnostics, not the primary "
            "inferential result."
        ),
    }


def run_statistics_helper_self_tests() -> None:
    if not math.isclose(exact_mcnemar_p_value(0, 3), 0.25):
        raise AssertionError("exact McNemar calculation failed")
    if exact_mcnemar_p_value(0, 0) != 1.0:
        raise AssertionError("zero-discordance McNemar result failed")
    bootstrap = case_cluster_bootstrap_ci(
        {"a": [1.0, 1.0], "b": [-1.0, -1.0]}, seed=3, resamples=100
    )
    if bootstrap["estimate"] != 0.0 or bootstrap["case_count"] != 2:
        raise AssertionError("case-cluster bootstrap aggregation failed")


def _event_signature(event: Any, *, include_targets: bool) -> tuple[Any, ...]:
    signature: tuple[Any, ...] = (
        int(event.source_step),
        str(event.kind),
        float(event.score),
        float(event.prior_stance),
        float(event.current_stance),
        float(event.revision_target),
        tuple(float(value) for value in event.attention_weights),
    )
    if include_targets:
        signature += (tuple(int(value) for value in event.target_steps),)
    return signature


def run_self_tests(monolith_path: Path = DEFAULT_MONOLITH) -> dict[str, Any]:
    """Run a small deterministic audit of adapters, labels, and accounting."""

    sha_before = _assert_monolith_sha(monolith_path)
    module = _load_monolith(monolith_path)
    cases = build_correctness_cases()
    by_id = {case.case_id: case for case in cases}
    selected = [
        by_id["stable_00"],
        by_id["threshold_positive_00"],
        by_id["routing_contradiction_trap_00"],
        by_id["sequential_budget_one"],
        by_id["weak_initial_anchor_promotion"],
    ]
    model_seed = 7
    revision_steps = 4
    executions: dict[tuple[str, str], Execution] = {}
    rows: list[dict[str, Any]] = []

    # Deliberately vary arm order by case; random routing must not depend on it.
    for case_index, case in enumerate(selected):
        arm_order = list(ARMS)
        random.Random(20260718 + case_index).shuffle(arm_order)
        route_seed = _route_seed(case.case_id, model_seed)
        for arm in arm_order:
            execution = run_arm(
                module,
                case,
                arm,
                model_seed=model_seed,
                route_seed=route_seed,
                revision_steps=revision_steps,
            )
            executions[(case.case_id, arm)] = execution
            rows.append(
                make_trial_row(
                    case,
                    execution,
                    mode="self-test",
                    model_seed=model_seed,
                    route_seed=route_seed,
                    repeat_index=0,
                )
            )

    if len(rows) != len(selected) * len(ARMS):
        raise AssertionError("self-test did not execute the full selected A-E matrix")
    threshold_case = by_id["threshold_positive_00"]
    threshold_expected = threshold_case.expected_events
    if len(threshold_expected) != 1:
        raise AssertionError("exact-threshold fixture must declare one event")
    if not math.isclose(
        threshold_expected[0].revision_target,
        -0.1,
        rel_tol=0.0,
        abs_tol=1e-12,
    ):
        raise AssertionError("exact-threshold fixture has an unexpected target")
    for row in rows:
        if row["generator_accounting_ok"] != 1:
            raise AssertionError(f"generator accounting mismatch: {row['run_id']}")
        if row["core_unchanged"] != 1:
            raise AssertionError(f"frozen core changed: {row['run_id']}")
        if row["finite_outputs"] != 1:
            raise AssertionError(f"non-finite output: {row['run_id']}")
        if row["decode_call_count"] != 1:
            raise AssertionError(f"decode count mismatch: {row['run_id']}")
        if row["attempted_revision_count"] < row["accepted_revision_count"]:
            raise AssertionError(f"accepted revisions exceed attempts: {row['run_id']}")
        if row["non_target_control_max"] > 1e-7:
            raise AssertionError(f"control leaked outside targets: {row['run_id']}")
        if row["pre_target_state_drift_max"] > 1e-7:
            raise AssertionError(f"state changed before target: {row['run_id']}")
        if row["max_control_norm_observed"] > 1.75001:
            raise AssertionError(
                f"control norm exceeded default bound: {row['run_id']}"
            )
        if (
            row["expected_suppressed_event_count"] is not None
            and row["suppressed_event_count"] != row["expected_suppressed_event_count"]
        ):
            raise AssertionError(f"suppression accounting mismatch: {row['run_id']}")

    for case in selected:
        forward = executions[(case.case_id, "A_forward_only_1pass")]
        detect = executions[(case.case_id, "B_detect_only_budget0")]
        if not torch.allclose(
            forward.final_states, detect.final_states, atol=1e-6, rtol=1e-6
        ):
            raise AssertionError(f"B output differs from A: {case.case_id}")
        if forward.decoded != detect.decoded:
            raise AssertionError(f"B decode differs from A: {case.case_id}")
        if detect.committed_events or detect.revisions:
            raise AssertionError(f"B committed a revision: {case.case_id}")
        expected_sources = {event.source_step for event in case.expected_events}
        for arm in ARMS[1:]:
            execution = executions[(case.case_id, arm)]
            actual_sources = {event.source_step for event in execution.detected_events}
            if actual_sources != expected_sources:
                raise AssertionError(
                    f"event label mismatch case={case.case_id} arm={arm}: "
                    f"expected={sorted(expected_sources)} actual={sorted(actual_sources)}"
                )

    stable = by_id["stable_00"]
    for arm in ARMS:
        row = next(
            item
            for item in rows
            if item["case_id"] == stable.case_id and item["arm"] == arm
        )
        if row["attempted_revision_count"] != 0 or row["accepted_revision_count"] != 0:
            raise AssertionError(f"stable case revised under {arm}")

    for case in selected:
        if not case.expected_events:
            continue
        oracle = executions[(case.case_id, "E_oracle_route_revision")]
        oracle_by_source = {
            event.source_step: event for event in oracle.detected_events
        }
        for expected in case.expected_events:
            selected_targets = set(oracle_by_source[expected.source_step].target_steps)
            if not set(expected.target_steps).issubset(selected_targets):
                raise AssertionError(
                    f"oracle route omitted gold target: {case.case_id} "
                    f"source={expected.source_step}"
                )

    routing_case = by_id["routing_contradiction_trap_00"]
    random_execution = executions[(routing_case.case_id, "C_random_route_revision")]
    full_execution = executions[(routing_case.case_id, "D_ebrt_full")]
    if len(random_execution.detected_events) != len(full_execution.detected_events):
        raise AssertionError("C and D event counts differ on routing audit case")
    for random_event, full_event in zip(
        random_execution.detected_events, full_execution.detected_events
    ):
        if _event_signature(random_event, include_targets=False) != _event_signature(
            full_event, include_targets=False
        ):
            raise AssertionError("C changed event metadata beyond target routing")
        for target in random_event.target_steps:
            if target >= random_event.source_step:
                raise AssertionError("C routed to a current/future step")
            if (
                routing_case.observations[target]["topic"].strip().lower()
                != routing_case.observations[random_event.source_step]["topic"]
                .strip()
                .lower()
            ):
                raise AssertionError("C routed outside the eligible topic")

    # Re-run C after D has already run. Its route and trajectory must be order-independent.
    repeat_random = run_arm(
        module,
        routing_case,
        "C_random_route_revision",
        model_seed=model_seed,
        route_seed=_route_seed(routing_case.case_id, model_seed),
        revision_steps=revision_steps,
    )
    if [event.target_steps for event in repeat_random.detected_events] != [
        event.target_steps for event in random_execution.detected_events
    ]:
        raise AssertionError("C routing depends on execution order")
    if not torch.allclose(
        repeat_random.final_states,
        random_execution.final_states,
        atol=1e-6,
        rtol=1e-6,
    ):
        raise AssertionError("C trajectory is not reproducible")

    sha_after = _assert_monolith_sha(monolith_path)
    if sha_after != sha_before:
        raise AssertionError("monolith SHA changed during benchmark self-test")
    sample = next(
        item
        for item in rows
        if item["case_id"] == routing_case.case_id and item["arm"] == "D_ebrt_full"
    )
    return {
        "status": "PASS",
        "schema_version": SCHEMA_VERSION,
        "monolith_sha256_before": sha_before,
        "monolith_sha256_after": sha_after,
        "correctness_case_count": len(cases),
        "selected_case_count": len(selected),
        "arm_count": len(ARMS),
        "trial_count": len(rows),
        "checks": [
            "strict frozen-monolith SHA guard before and after execution",
            "48 exact cases and exact family counts",
            "event score exactly equal to the threshold triggers deterministically",
            "every routing-informative fixture has more eligible states than top_k",
            "all A-E arms run with exact generator-step accounting",
            "B output equals A while committing no revision",
            "C and D preserve identical event metadata except target routing",
            "C routes only backward within the eligible topic",
            "E includes every detected gold target",
            "stable cases record zero attempted and accepted revisions",
            "expected event labels include detected and budget-suppressed events",
            "pre-target state locality and expected suppression accounting",
            "random routing is reproducible and execution-order independent",
            "frozen core, decode-once, finite output, control locality and bound",
        ],
        "sample_full_row": {
            key: sample[key]
            for key in (
                "case_id",
                "arm",
                "expected_event_count",
                "detected_event_count",
                "routing_recall_at_k",
                "routing_recall_conditional",
                "target_topic_success",
                "source_distance_gain",
                "target_distance_gain",
                "attempted_revision_count",
                "accepted_revision_count",
                "generator_step_calls",
                "expected_generator_step_calls",
            )
        },
        "memory_metric_note": (
            "process_cumulative_peak_rss_mib is ru_maxrss for the process lifetime; "
            "it is not an isolated per-arm memory delta"
        ),
        "claim_boundary": list(CLAIM_BOUNDARY),
    }


def _configure_runtime(threads: int) -> None:
    if threads < 1:
        raise ValueError("threads must be >= 1")
    torch.set_num_threads(threads)
    try:
        torch.set_num_interop_threads(1)
    except RuntimeError:
        # PyTorch permits setting inter-op threads only before parallel work.
        if torch.get_num_interop_threads() != 1:
            raise
    torch.use_deterministic_algorithms(True)


def run_correctness_matrix(
    module: Any,
    cases: Sequence[BenchmarkCase],
    *,
    model_seeds: Sequence[int],
    revision_steps: int,
    mode: str,
    device: str,
    dtype: str,
    progress: bool = True,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    total = len(cases) * len(model_seeds) * len(ARMS)
    completed = 0
    for model_seed in model_seeds:
        for case in cases:
            arm_order = list(ARMS)
            random.Random(
                _stable_int("arm-order", mode, case.case_id, model_seed)
            ).shuffle(arm_order)
            route_seed = _route_seed(case.case_id, model_seed)
            for arm in arm_order:
                execution = run_arm(
                    module,
                    case,
                    arm,
                    model_seed=model_seed,
                    route_seed=route_seed,
                    revision_steps=revision_steps,
                    device=device,
                    dtype=dtype,
                )
                row = make_trial_row(
                    case,
                    execution,
                    mode="correctness",
                    model_seed=model_seed,
                    route_seed=route_seed,
                    repeat_index=0,
                )
                if row["generator_accounting_ok"] != 1:
                    raise AssertionError(
                        f"generator accounting failed: {row['run_id']}"
                    )
                if row["core_unchanged"] != 1 or row["finite_outputs"] != 1:
                    raise AssertionError(f"integrity check failed: {row['run_id']}")
                if row["decode_call_count"] != 1:
                    raise AssertionError(f"decode count failed: {row['run_id']}")
                if (
                    row["max_control_norm_observed"]
                    > execution.config.max_control_norm + 1e-5
                ):
                    raise AssertionError(f"control bound failed: {row['run_id']}")
                if row["non_target_control_max"] > 1e-7:
                    raise AssertionError(f"control locality failed: {row['run_id']}")
                if row["pre_target_state_drift_max"] > 1e-7:
                    raise AssertionError(f"pre-target locality failed: {row['run_id']}")
                if (
                    row["expected_suppressed_event_count"] is not None
                    and row["suppressed_event_count"]
                    != row["expected_suppressed_event_count"]
                ):
                    raise AssertionError(
                        f"suppression accounting failed: {row['run_id']}"
                    )
                rows.append(row)
                completed += 1
                if progress and (completed == total or completed % 250 == 0):
                    print(
                        f"correctness progress {completed}/{total}",
                        file=sys.stderr,
                        flush=True,
                    )
    return rows


def _validate_profile_execution(case: BenchmarkCase, execution: Execution) -> None:
    expected_sources = {event.source_step for event in case.expected_events}
    actual_sources = {event.source_step for event in execution.detected_events}
    if execution.arm != "A_forward_only_1pass" and actual_sources != expected_sources:
        raise AssertionError(
            f"profile event mismatch case={case.case_id} arm={execution.arm} "
            f"expected={sorted(expected_sources)} actual={sorted(actual_sources)}"
        )
    if case.family == "scaling_length_no_event" and execution.detected_events:
        raise AssertionError(f"no-event profile emitted an event: {case.case_id}")
    if case.family == "scaling_top_k" and execution.committed_events:
        event = execution.committed_events[0]
        eligible = sum(
            1
            for item in case.observations[: event.source_step]
            if str(item["topic"]).strip().lower()
            == str(case.observations[event.source_step]["topic"]).strip().lower()
        )
        if len(event.target_steps) != min(execution.config.top_k, eligible):
            raise AssertionError(
                f"top-k profile did not select configured width: {case.case_id}"
            )
    if case.family == "scaling_replay_distance" and execution.revisions:
        expected_target = case.expected_events[0].target_steps[0]
        if execution.revisions[0].earliest_replay_step != expected_target:
            raise AssertionError(f"replay-distance target mismatch: {case.case_id}")


def run_profile_matrix(
    module: Any,
    cases: Sequence[BenchmarkCase],
    *,
    warmups: int,
    repeats: int,
    revision_steps: int,
    device: str,
    dtype: str,
    progress: bool = True,
) -> list[dict[str, Any]]:
    if warmups < 0 or repeats < 1:
        raise ValueError("profile warmups must be >= 0 and repeats must be >= 1")
    profile_arms = (
        "A_forward_only_1pass",
        "B_detect_only_budget0",
        "D_ebrt_full",
    )
    model_seed = 7
    route_seed = _route_seed("profile", model_seed)
    rows: list[dict[str, Any]] = []
    total = len(cases) * len(profile_arms) * repeats
    completed = 0
    for case in cases:
        for warmup_index in range(warmups):
            warmup_order = list(profile_arms)
            random.Random(
                _stable_int("profile-warmup", case.case_id, warmup_index)
            ).shuffle(warmup_order)
            for arm in warmup_order:
                execution = run_arm(
                    module,
                    case,
                    arm,
                    model_seed=model_seed,
                    route_seed=route_seed,
                    revision_steps=revision_steps,
                    device=device,
                    dtype=dtype,
                )
                _validate_profile_execution(case, execution)
        for repeat_index in range(repeats):
            arm_order = list(profile_arms)
            random.Random(
                _stable_int("profile-order", case.case_id, repeat_index)
            ).shuffle(arm_order)
            for arm in arm_order:
                execution = run_arm(
                    module,
                    case,
                    arm,
                    model_seed=model_seed,
                    route_seed=route_seed,
                    revision_steps=revision_steps,
                    device=device,
                    dtype=dtype,
                )
                _validate_profile_execution(case, execution)
                row = make_trial_row(
                    case,
                    execution,
                    mode="profile",
                    model_seed=model_seed,
                    route_seed=route_seed,
                    repeat_index=repeat_index,
                )
                if row["generator_accounting_ok"] != 1:
                    raise AssertionError(f"profile accounting failed: {row['run_id']}")
                if row["decode_call_count"] != 1 or row["core_unchanged"] != 1:
                    raise AssertionError(f"profile integrity failed: {row['run_id']}")
                if (
                    row["max_control_norm_observed"]
                    > execution.config.max_control_norm + 1e-5
                ):
                    raise AssertionError(
                        f"profile control bound failed: {row['run_id']}"
                    )
                if row["non_target_control_max"] > 1e-7:
                    raise AssertionError(
                        f"profile control locality failed: {row['run_id']}"
                    )
                if row["pre_target_state_drift_max"] > 1e-7:
                    raise AssertionError(
                        f"profile pre-target locality failed: {row['run_id']}"
                    )
                if (
                    row["expected_suppressed_event_count"] is not None
                    and row["suppressed_event_count"]
                    != row["expected_suppressed_event_count"]
                ):
                    raise AssertionError(
                        f"profile suppression accounting failed: {row['run_id']}"
                    )
                rows.append(row)
                completed += 1
                if progress and (completed == total or completed % 100 == 0):
                    print(
                        f"profile progress {completed}/{total}",
                        file=sys.stderr,
                        flush=True,
                    )
    return rows


def summarize_profile(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(str(row["case_id"]), str(row["family"]), str(row["arm"]))].append(row)
    summaries: list[dict[str, Any]] = []
    for (case_id, family, arm), selected in sorted(grouped.items()):
        latency = _distribution_summary(_numeric_values(selected, "external_wall_ms"))
        summaries.append(
            {
                "case_id": case_id,
                "family": family,
                "arm": arm,
                "repeat_count": len(selected),
                "trajectory_length": int(selected[0]["trajectory_length"]),
                "revision_steps": int(selected[0]["revision_steps"]),
                "top_k": int(selected[0]["top_k"]),
                "expected_event_count": int(selected[0]["expected_event_count"]),
                "external_wall_ms_median": latency["median"],
                "external_wall_ms_p95": latency["p95"],
                "external_wall_ms_mad": latency["mad"],
                "generator_steps_median": statistics.median(
                    _numeric_values(selected, "generator_step_calls")
                ),
                "backward_calls_median": statistics.median(
                    _numeric_values(selected, "backward_calls")
                ),
            }
        )
    return summaries


def _git_metadata(directory: Path) -> dict[str, Any]:
    def run(*arguments: str) -> str | None:
        completed = subprocess.run(
            ["git", *arguments],
            cwd=directory,
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            return None
        return completed.stdout.strip()

    commit = run("rev-parse", "HEAD")
    branch = run("branch", "--show-current")
    status = run("status", "--porcelain")
    return {
        "commit": commit,
        "branch": branch or None,
        "dirty_before_output": bool(status) if status is not None else None,
    }


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(
            payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False
        )
        + "\n",
        encoding="utf-8",
    )


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    if not rows:
        path.write_text("\n", encoding="utf-8")
        return
    fieldnames: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                fieldnames.append(str(key))
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def classify_failures(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for row in rows:
        reasons: list[str] = []
        if int(row.get("core_unchanged", 0)) != 1:
            reasons.append("frozen_core_changed")
        if int(row.get("finite_outputs", 0)) != 1:
            reasons.append("non_finite_output")
        if int(row.get("generator_accounting_ok", 0)) != 1:
            reasons.append("generator_accounting_mismatch")
        if row.get("event_fn") not in (None, 0):
            reasons.append("event_miss")
        if row.get("event_fp") not in (None, 0):
            reasons.append("false_event")
        gold_routes = row.get("gold_route_count")
        route_hits = row.get("route_hit_count")
        if (
            gold_routes is not None
            and float(gold_routes) > 0
            and float(route_hits or 0) < float(gold_routes)
        ):
            reasons.append("gold_route_miss")
        if row.get("target_topic_success") == 0:
            reasons.append("target_topic_failure")
        if (
            int(row.get("expected_event_count", 0)) == 0
            and int(row.get("attempted_revision_count", 0)) > 0
        ):
            reasons.append("unnecessary_revision_attempt")
        if int(row.get("rollback_count", 0)) > 0:
            reasons.append("rollback_to_best_checkpoint")
        if int(row.get("suppressed_event_count", 0)) > 0:
            reasons.append("budget_suppression")
        if not reasons:
            continue
        failures.append(
            {
                "run_id": row["run_id"],
                "case_id": row["case_id"],
                "family": row["family"],
                "arm": row["arm"],
                "model_seed": row["model_seed"],
                "reasons": reasons,
                "expected_event_count": row["expected_event_count"],
                "detected_event_count": row["detected_event_count"],
                "suppressed_event_count": row.get("suppressed_event_count"),
                "routing_recall_at_k": row.get("routing_recall_at_k"),
                "executed_routing_recall_at_k": row.get("executed_routing_recall_at_k"),
                "target_topic_success": row.get("target_topic_success"),
                "source_distance_gain": row.get("source_distance_gain"),
                "target_distance_gain": row.get("target_distance_gain"),
                "attempted_revision_count": row.get("attempted_revision_count"),
                "accepted_revision_count": row.get("accepted_revision_count"),
                "rollback_count": row.get("rollback_count"),
            }
        )
    return failures


def _summary_csv_rows(
    arm_summaries: Sequence[Mapping[str, Any]],
    profile_summaries: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for summary in arm_summaries:
        rows.append({"scope": "correctness_arm", **dict(summary)})
    for summary in profile_summaries:
        rows.append({"scope": "profile_case_arm", **dict(summary)})
    return rows


def _comparison_lookup(results: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    for item in results.get("paired_contrasts", []):
        if item.get("comparison") == name:
            return item
    return {}


def _format_number(value: Any, digits: int = 3) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.{digits}f}"


def _format_p_value(value: Any) -> str:
    if value is None:
        return "n/a"
    number = float(value)
    return f"{number:.2e}" if number < 0.0001 else f"{number:.4f}"


def _profile_lookup(
    summaries: Sequence[Mapping[str, Any]], case_id: str, arm: str
) -> Mapping[str, Any]:
    for item in summaries:
        if item.get("case_id") == case_id and item.get("arm") == arm:
            return item
    return {}


def _scaling_exponent(
    summaries: Sequence[Mapping[str, Any]],
    *,
    arm: str,
    first_length: int,
    last_length: int,
) -> float | None:
    first = _profile_lookup(summaries, f"scale_no_event_t{first_length}", arm)
    last = _profile_lookup(summaries, f"scale_no_event_t{last_length}", arm)
    first_ms = first.get("external_wall_ms_median")
    last_ms = last.get("external_wall_ms_median")
    if (
        first_ms is None
        or last_ms is None
        or float(first_ms) <= 0
        or float(last_ms) <= 0
    ):
        return None
    return math.log(float(last_ms) / float(first_ms)) / math.log(
        last_length / first_length
    )


def render_benchmark_report(results: Mapping[str, Any]) -> str:
    statistics_payload = results.get("correctness", {}).get("statistics", {})
    arms = {item["arm"]: item for item in statistics_payload.get("arm_summaries", [])}
    profile = results.get("profile", {}).get("summaries", [])
    lines = [
        "# EBRT v0.1 generated benchmark report",
        "",
        f"- Run ID: `{results['run_id']}`",
        f"- Mode: `{results['mode']}`",
        f"- Correctness trials: {results.get('correctness', {}).get('trial_count', 0)}",
        f"- Profile trials: {results.get('profile', {}).get('trial_count', 0)}",
        "- Scope: fixed structured synthetic mechanism suite",
        "",
        "> This report does not establish natural-language event detection, GPT or",
        "> Transformer hidden-state repair, or improved LLM reasoning accuracy.",
    ]
    if arms:
        lines.extend(
            [
                "",
                "## Correctness summary",
                "",
                "Target-topic success is primary on event-bearing cases. The all-topic",
                "conjunction is secondary because unrelated-topic memory can dominate it.",
                "",
                "| Arm | Target-topic success | All-topic success | Source gain | Target gain | Router recall | Informative recall | Median ms |",
                "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for arm in ARMS:
            item = arms.get(arm)
            if not item:
                continue
            lines.append(
                "| "
                + " | ".join(
                    (
                        arm,
                        _format_number(item.get("target_topic_success_rate")),
                        _format_number(item.get("all_topic_success_rate")),
                        _format_number(item.get("source_distance_gain_mean")),
                        _format_number(item.get("target_distance_gain_mean")),
                        _format_number(item.get("router_recall_at_k")),
                        _format_number(item.get("informative_router_recall_at_k")),
                        _format_number(item.get("external_wall_ms_median")),
                    )
                )
                + " |"
            )
        lines.extend(
            [
                "",
                "`router recall` includes proposals for budget-suppressed events; the",
                "machine-readable results also report executed-routing recall separately.",
                "Internal energy is retained as a diagnostic and is not a quality metric.",
                "",
                "## Paired contrasts",
                "",
                "| Contrast | Metric | Mean delta | Case-cluster 95% CI | Unadjusted McNemar p |",
                "| --- | --- | ---: | --- | ---: |",
            ]
        )
        for comparison_name, metric in (
            ("full_minus_forward", "target_topic_success"),
            ("full_minus_random_route", "source_distance_gain"),
            ("oracle_minus_full", "target_distance_gain"),
            ("detect_minus_forward", "external_wall_ms"),
        ):
            comparison = _comparison_lookup(statistics_payload, comparison_name)
            metric_result = comparison.get("metrics", {}).get(metric, {})
            bootstrap = metric_result.get("case_cluster_bootstrap", {})
            p_value = (
                comparison.get("mcnemar", {})
                .get("target_topic_success", {})
                .get("exact_two_sided_p")
                if metric == "target_topic_success"
                else None
            )
            ci_text = (
                f"[{_format_number(bootstrap.get('ci_low'))}, "
                f"{_format_number(bootstrap.get('ci_high'))}]"
            )
            lines.append(
                f"| {comparison_name} | {metric} | "
                f"{_format_number(metric_result.get('mean_delta'))} | {ci_text} | "
                f"{_format_p_value(p_value)} |"
            )
        full = arms.get("D_ebrt_full", {})
        random_arm = arms.get("C_random_route_revision", {})
        gold = arms.get("E_oracle_route_revision", {})
        lines.extend(
            [
                "",
                "McNemar values treat repeated case×seed pairs descriptively and do not",
                "adjust for within-case correlation. Case-cluster bootstrap intervals are",
                "the primary uncertainty summary.",
                "",
                "## Evidence-led bottleneck read",
                "",
                "- Full versus random routing must be judged on paired distance and route",
                "  metrics as well as the binary endpoint. In this run their target-topic",
                f"  success rates are {_format_number(full.get('target_topic_success_rate'))}",
                f"  and {_format_number(random_arm.get('target_topic_success_rate'))}.",
                "- The gold-route arm is a privileged annotated-target intervention, not a",
                "  presumed performance ceiling. Its target-distance gain is",
                f"  {_format_number(gold.get('target_distance_gain_mean'))}, while full",
                "  EBRT's is",
                f"  {_format_number(full.get('target_distance_gain_mean'))}. Compare this",
                "  with source-distance gain and final target-topic success before inferring",
                "  that the semantic anchor is the best recurrent control location.",
                "- Stable-case attempted and accepted revision rates are reported separately",
                "  in `results.json`; zero accepted revisions alone would not rule out wasted",
                "  detector or optimizer work.",
            ]
        )
    if profile:
        exponent_a = _scaling_exponent(
            profile,
            arm="A_forward_only_1pass",
            first_length=256,
            last_length=2048,
        )
        exponent_d = _scaling_exponent(
            profile,
            arm="D_ebrt_full",
            first_length=256,
            last_length=2048,
        )
        lines.extend(
            [
                "",
                "## Scaling profile",
                "",
                "The exponent below is a two-point engineering diagnostic from T=256 to",
                "T=2048, not a formal complexity proof.",
                "",
                f"- Forward-only no-event wall-time exponent: {_format_number(exponent_a, 2)}",
                f"- Full-scaffold no-event wall-time exponent: {_format_number(exponent_d, 2)}",
                "",
                "| Length | A median ms | B median ms | D median ms |",
                "| ---: | ---: | ---: | ---: |",
            ]
        )
        for length in (4, 16, 64, 256, 512, 1024, 2048):
            lines.append(
                f"| {length} | "
                f"{_format_number(_profile_lookup(profile, f'scale_no_event_t{length}', 'A_forward_only_1pass').get('external_wall_ms_median'))} | "
                f"{_format_number(_profile_lookup(profile, f'scale_no_event_t{length}', 'B_detect_only_budget0').get('external_wall_ms_median'))} | "
                f"{_format_number(_profile_lookup(profile, f'scale_no_event_t{length}', 'D_ebrt_full').get('external_wall_ms_median'))} |"
            )
        lines.extend(
            [
                "",
                "The implementation inspection predicts repeated prefix materialization and",
                "all-prior eligibility scans on long scaffolded runs, dense control tensors",
                "for sparse updates, and suffix replay multiplied by revision-step count.",
                "Treat the profile as confirmation or rejection of that ranking, not as an",
                "LLM-serving latency estimate.",
            ]
        )
    lines.extend(
        [
            "",
            "## Claim boundary",
            "",
            *[f"- {statement}" for statement in results.get("claim_boundary", [])],
            "",
            "Raw paired trials, summaries, failures, source digests, fixture digest,",
            "environment, and protocol are recorded beside this report.",
            "",
        ]
    )
    return "\n".join(lines)


def _artifact_record(path: Path) -> dict[str, Any]:
    return {"sha256": _sha256(path), "bytes": path.stat().st_size}


def write_benchmark_bundle(
    output_dir: Path,
    *,
    results: Mapping[str, Any],
    all_rows: Sequence[Mapping[str, Any]],
    summary_rows: Sequence[Mapping[str, Any]],
    failures: Sequence[Mapping[str, Any]],
    manifest_base: Mapping[str, Any],
) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    names = (
        "trials.csv",
        "summary.csv",
        "results.json",
        "benchmark_report.md",
        "failures.jsonl",
    )
    with tempfile.TemporaryDirectory(
        prefix=".ebrt-benchmark-stage-", dir=output_dir.parent
    ) as temporary:
        stage = Path(temporary)
        _write_csv(stage / "trials.csv", all_rows)
        _write_csv(stage / "summary.csv", summary_rows)
        _write_json(stage / "results.json", results)
        (stage / "benchmark_report.md").write_text(
            render_benchmark_report(results), encoding="utf-8"
        )
        with (stage / "failures.jsonl").open("w", encoding="utf-8") as handle:
            for failure in failures:
                handle.write(_canonical_json(failure) + "\n")
        artifacts = {name: _artifact_record(stage / name) for name in names}
        manifest = {**dict(manifest_base), "artifacts": artifacts}
        _write_json(stage / "manifest.json", manifest)
        for name in (*names, "manifest.json"):
            os.replace(stage / name, output_dir / name)
    return manifest


def run_benchmark(
    *,
    mode: str,
    monolith_path: Path,
    output_dir: Path,
    revision_steps: int | None,
    bootstrap_resamples: int | None,
    profile_warmups: int,
    profile_repeats: int,
    device: str,
    dtype: str,
    progress: bool,
) -> dict[str, Any]:
    if mode not in {"quick", "full", "profile"}:
        raise ValueError(f"unsupported benchmark mode: {mode}")
    monolith_path = monolith_path.resolve()
    monolith_sha_before = _assert_monolith_sha(monolith_path)
    benchmark_path = Path(__file__).resolve()
    benchmark_sha_before = _sha256(benchmark_path)
    started = time.perf_counter()
    created_at = datetime.now(timezone.utc).replace(microsecond=0)
    run_id = (
        f"ebrt-v0.1-{mode}-{created_at.strftime('%Y%m%dT%H%M%SZ')}-"
        f"{benchmark_sha_before[:8]}"
    )
    module = _load_monolith(monolith_path)
    correctness_cases = build_correctness_cases()
    fixture_sha = hashlib.sha256(
        _canonical_json([case.to_dict() for case in correctness_cases]).encode("utf-8")
    ).hexdigest()
    correctness_rows: list[dict[str, Any]] = []
    profile_rows: list[dict[str, Any]] = []
    model_seeds: tuple[int, ...] = ()
    resolved_revision_steps = revision_steps
    if mode in {"quick", "full"}:
        model_seeds = tuple(range(4 if mode == "quick" else 32))
        if resolved_revision_steps is None:
            resolved_revision_steps = 8 if mode == "quick" else 32
        correctness_rows = run_correctness_matrix(
            module,
            correctness_cases,
            model_seeds=model_seeds,
            revision_steps=resolved_revision_steps,
            mode=mode,
            device=device,
            dtype=dtype,
            progress=progress,
        )
    if mode in {"full", "profile"}:
        if resolved_revision_steps is None:
            resolved_revision_steps = 32
        profile_cases = build_scaling_cases((4, 16, 64, 256, 512, 1024, 2048))
        profile_rows = run_profile_matrix(
            module,
            profile_cases,
            warmups=profile_warmups,
            repeats=profile_repeats,
            revision_steps=resolved_revision_steps,
            device=device,
            dtype=dtype,
            progress=progress,
        )
    if resolved_revision_steps is None:
        raise AssertionError("revision steps were not resolved")
    resolved_bootstrap_resamples = bootstrap_resamples
    if resolved_bootstrap_resamples is None:
        resolved_bootstrap_resamples = 500 if mode == "quick" else 2_000
    if resolved_bootstrap_resamples < 1:
        raise ValueError("bootstrap resamples must be >= 1")
    statistics_payload = (
        build_statistical_summary(
            correctness_rows,
            bootstrap_seed=20_260_718,
            bootstrap_resamples=resolved_bootstrap_resamples,
        )
        if correctness_rows
        else {
            "arm_summaries": [],
            "paired_contrasts": [],
            "uncertainty_note": "No correctness matrix was run in profile-only mode.",
        }
    )
    profile_summaries = summarize_profile(profile_rows)
    failures = classify_failures(correctness_rows)
    failure_reason_counts: dict[str, int] = defaultdict(int)
    for failure in failures:
        for reason in failure["reasons"]:
            failure_reason_counts[str(reason)] += 1
    monolith_sha_after = _assert_monolith_sha(monolith_path)
    benchmark_sha_after = _sha256(benchmark_path)
    if monolith_sha_before != monolith_sha_after:
        raise AssertionError("frozen monolith changed during benchmark")
    if benchmark_sha_before != benchmark_sha_after:
        raise AssertionError("benchmark source changed during its own execution")
    elapsed_seconds = time.perf_counter() - started
    results: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "status": "PASS",
        "run_id": run_id,
        "mode": mode,
        "created_at_utc": created_at.isoformat().replace("+00:00", "Z"),
        "elapsed_seconds": elapsed_seconds,
        "correctness": {
            "case_count": len(correctness_cases) if correctness_rows else 0,
            "trial_count": len(correctness_rows),
            "model_seeds": list(model_seeds),
            "revision_steps": resolved_revision_steps,
            "statistics": statistics_payload,
        },
        "profile": {
            "trial_count": len(profile_rows),
            "warmups": profile_warmups if profile_rows else 0,
            "repeats": profile_repeats if profile_rows else 0,
            "summaries": profile_summaries,
            "latency_note": (
                "External wall time includes engine construction and execution. "
                "Median, p95, and MAD are descriptive for the recorded CPU environment."
            ),
        },
        "failures": {
            "record_count": len(failures),
            "reason_counts": dict(sorted(failure_reason_counts.items())),
            "note": (
                "Failure records are diagnostic flags, not all equivalent to task "
                "failure; rollback-to-best is retained as an auditable behavior."
            ),
        },
        "claim_boundary": list(CLAIM_BOUNDARY),
    }
    git = _git_metadata(benchmark_path.parent)
    portable_output_arg = (
        output_dir.as_posix() if not output_dir.is_absolute() else output_dir.name
    )
    manifest_base: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "mode": mode,
        "created_at_utc": results["created_at_utc"],
        "elapsed_seconds": elapsed_seconds,
        "source": {
            "monolith_file": monolith_path.name,
            "monolith_sha256_before": monolith_sha_before,
            "monolith_sha256_after": monolith_sha_after,
            "benchmark_file": benchmark_path.name,
            "benchmark_sha256_before": benchmark_sha_before,
            "benchmark_sha256_after": benchmark_sha_after,
            "fixture_sha256": fixture_sha,
            "fixture_case_count": len(correctness_cases),
        },
        "git": git,
        "environment": {
            "python_version": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "torch_version": torch.__version__,
            "platform": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor() or None,
            "device": device,
            "dtype": dtype,
            "torch_intraop_threads": torch.get_num_threads(),
            "torch_interop_threads": torch.get_num_interop_threads(),
        },
        "protocol": {
            "correctness_model_seeds": list(model_seeds),
            "random_route_seed_formula": "10000 + model_seed",
            "bootstrap_seed": 20_260_718,
            "bootstrap_resamples": resolved_bootstrap_resamples,
            "revision_steps": resolved_revision_steps,
            "arms": list(ARMS),
            "profile_lengths": (
                [4, 16, 64, 256, 512, 1024, 2048] if profile_rows else []
            ),
            "profile_arms": (
                [
                    "A_forward_only_1pass",
                    "B_detect_only_budget0",
                    "D_ebrt_full",
                ]
                if profile_rows
                else []
            ),
            "profile_warmups": profile_warmups if profile_rows else 0,
            "profile_repeats": profile_repeats if profile_rows else 0,
            "variant_order": "deterministically shuffled per case and seed/repeat",
            "pairing_key": ["case_id", "model_seed", "repeat_index"],
        },
        "counts": {
            "correctness_trials": len(correctness_rows),
            "profile_trials": len(profile_rows),
            "failure_records": len(failures),
        },
        "invocation": {
            "mode": mode,
            "output_bundle_name": output_dir.name,
            "progress_enabled": progress,
            "canonical_resolved_argv": [
                "python3",
                benchmark_path.name,
                f"--{mode}",
                "--output-dir",
                portable_output_arg,
                "--revision-steps",
                str(resolved_revision_steps),
                "--bootstrap-resamples",
                str(resolved_bootstrap_resamples),
                "--profile-warmups",
                str(profile_warmups),
                "--profile-repeats",
                str(profile_repeats),
                "--device",
                device,
                "--dtype",
                dtype,
                "--threads",
                str(torch.get_num_threads()),
            ],
        },
        "claim_boundary": list(CLAIM_BOUNDARY),
    }
    all_rows = [*correctness_rows, *profile_rows]
    summary_rows = _summary_csv_rows(
        statistics_payload.get("arm_summaries", []), profile_summaries
    )
    manifest = write_benchmark_bundle(
        output_dir,
        results=results,
        all_rows=all_rows,
        summary_rows=summary_rows,
        failures=failures,
        manifest_base=manifest_base,
    )
    return {
        "status": "PASS",
        "run_id": run_id,
        "mode": mode,
        "output_dir": str(output_dir.resolve()),
        "correctness_trials": len(correctness_rows),
        "profile_trials": len(profile_rows),
        "failure_records": len(failures),
        "elapsed_seconds": elapsed_seconds,
        "manifest_sha256": _sha256(output_dir.resolve() / "manifest.json"),
        "monolith_sha256": monolith_sha_after,
        "artifact_names": sorted(manifest["artifacts"]),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Matched synthetic mechanism benchmark for frozen EBRT v0.1."
    )
    parser.add_argument(
        "command",
        nargs="?",
        choices=("self-test", "quick", "full", "profile", "scaling"),
        help="optional subcommand alias for a benchmark mode",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="run the deterministic A-E benchmark harness audit",
    )
    parser.add_argument("--quick", action="store_true", help="run the quick matrix")
    parser.add_argument(
        "--full", action="store_true", help="run reportable full evidence"
    )
    parser.add_argument(
        "--profile",
        action="store_true",
        help="run the controlled scaling profile only",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="artifact bundle directory (default: benchmark_results/v0_1_<mode>)",
    )
    parser.add_argument(
        "--monolith",
        type=Path,
        default=DEFAULT_MONOLITH,
        help="path to the frozen ebrt_monolith_v0_1.py",
    )
    parser.add_argument("--revision-steps", type=int)
    parser.add_argument("--bootstrap-resamples", type=int)
    parser.add_argument("--profile-warmups", type=int, default=2)
    parser.add_argument("--profile-repeats", type=int, default=7)
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--dtype", choices=("float32", "float64"), default="float32")
    parser.add_argument(
        "--no-progress", action="store_true", help="suppress progress on stderr"
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    requested: list[str] = []
    if args.command:
        requested.append("profile" if args.command == "scaling" else args.command)
    for enabled, mode in (
        (args.self_test, "self-test"),
        (args.quick, "quick"),
        (args.full, "full"),
        (args.profile, "profile"),
    ):
        if enabled:
            requested.append(mode)
    unique = sorted(set(requested))
    if len(unique) != 1:
        raise SystemExit(
            "Select exactly one mode: --self-test, --quick, --full, or --profile."
        )
    mode = unique[0]
    _configure_runtime(args.threads)
    if mode == "self-test":
        run_statistics_helper_self_tests()
        report = run_self_tests(args.monolith.resolve())
    else:
        output_dir = args.output_dir or Path("benchmark_results") / f"v0_1_{mode}"
        report = run_benchmark(
            mode=mode,
            monolith_path=args.monolith,
            output_dir=output_dir,
            revision_steps=args.revision_steps,
            bootstrap_resamples=args.bootstrap_resamples,
            profile_warmups=args.profile_warmups,
            profile_repeats=args.profile_repeats,
            device=args.device,
            dtype=args.dtype,
            progress=not args.no_progress,
        )
    print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
