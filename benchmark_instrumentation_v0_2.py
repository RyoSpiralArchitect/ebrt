#!/usr/bin/env python3
"""Evidence benchmark for EBRT v0.2 counterfactual instrumentation.

The benchmark treats event-local mirrors as counterfactual observability, not
as access to private chain-of-thought. Curvature and attention/leverage
alignment are exploratory geometric diagnostics; they are never interpreted as
standalone reasoning-quality measures.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import math
import os
import platform
import random
import statistics
import sys
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import torch

import benchmark_ebrt_v0_1 as v01


SCHEMA_VERSION = "ebrt-instrumentation-benchmark-v0.2"
EXPECTED_TRACE_SCHEMA = "ebrt-instrumentation-v0.2"
DEFAULT_INSTRUMENTATION = Path(__file__).with_name("instrumentation_ebrt_v0_2.py")
DEFAULT_MONOLITH = Path(__file__).with_name("ebrt_monolith_v0_1.py")
DEFAULT_SEMANTIC_ADAPTER = Path(__file__).with_name("semantic_adapter_v0_2.py")
V01_BENCHMARK_PATH = Path(v01.__file__).resolve()
DEFAULT_OUTPUT_DIR = Path("artifacts/benchmark_instrumentation_v0_2")
BOOTSTRAP_SEED = 20_260_718
EPSILON = 1e-12
GEOMETRY_EPSILON = 1e-8
LEVERAGE_EPSILON = 1e-3

CLAIM_BOUNDARY = (
    "This benchmark measures a structured synthetic mechanism, not natural-language reasoning quality.",
    "Event-local mirrors are matched counterfactual execution traces, not private chain-of-thought or model introspection.",
    "Turn angle and curvature are coordinate-sensitive geometric proxies; lower or higher values are not inherently better.",
    "Semantic attention and offline target-aligned source-projection leverage answer different questions: why a premise is implicated versus how one predefined local control direction changes the event-source belief projection.",
    "Candidate control_leverage uses a centered finite difference when both requested endpoints are feasible and a radially projected forward one-sided difference at the control boundary; it is not full-state controllability, an objective gradient, or proof of causal optimality.",
    "Outcome and leakage associations are descriptive on the fixed 48-case suite and do not establish external validity or causality.",
    "Paired seeds control the toy generator initialization but do not close case-selection, representation, or future hosted-model nondeterminism.",
)


@dataclass(frozen=True)
class GeometrySummary:
    step_count: int
    separation_auc: float
    separation_mean: float
    separation_max: float
    separation_terminal: float
    mirror_turn_angle_mean: float | None
    revised_turn_angle_mean: float | None
    excess_turn_angle_mean: float | None
    mirror_curvature_mean: float | None
    revised_curvature_mean: float | None
    excess_curvature_mean: float | None
    undefined_turn_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_count": self.step_count,
            "separation_auc": self.separation_auc,
            "separation_mean": self.separation_mean,
            "separation_max": self.separation_max,
            "separation_terminal": self.separation_terminal,
            "mirror_turn_angle_mean": self.mirror_turn_angle_mean,
            "revised_turn_angle_mean": self.revised_turn_angle_mean,
            "excess_turn_angle_mean": self.excess_turn_angle_mean,
            "mirror_curvature_mean": self.mirror_curvature_mean,
            "revised_curvature_mean": self.revised_curvature_mean,
            "excess_curvature_mean": self.excess_curvature_mean,
            "undefined_turn_count": self.undefined_turn_count,
        }


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


def _as_tensor(value: Any) -> torch.Tensor:
    if isinstance(value, torch.Tensor):
        return value.detach().cpu().to(torch.float64)
    return torch.as_tensor(value, dtype=torch.float64)


def _finite_mean(values: Iterable[float | None]) -> float | None:
    clean = [
        float(value)
        for value in values
        if value is not None and math.isfinite(float(value))
    ]
    return statistics.fmean(clean) if clean else None


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


def _trapezoid_auc(values: Sequence[float]) -> float:
    if len(values) < 2:
        return 0.0
    return sum((left + right) * 0.5 for left, right in zip(values, values[1:]))


def turn_angle_and_curvature(
    states: Any, *, epsilon: float = EPSILON
) -> tuple[list[float | None], list[float | None]]:
    """Return discrete turn angle and arc-length-normalized curvature.

    Undefined turns caused by a near-zero adjacent displacement remain None;
    they are not silently interpreted as straight motion.
    """

    tensor = _as_tensor(states)
    if tensor.ndim != 2:
        raise ValueError("states must have shape [T, D]")
    if tensor.shape[0] < 3:
        return [], []
    deltas = tensor[1:] - tensor[:-1]
    angles: list[float | None] = []
    curvatures: list[float | None] = []
    for previous, following in zip(deltas[:-1], deltas[1:]):
        previous_norm = float(torch.linalg.vector_norm(previous).item())
        following_norm = float(torch.linalg.vector_norm(following).item())
        if previous_norm <= epsilon or following_norm <= epsilon:
            angles.append(None)
            curvatures.append(None)
            continue
        cosine = float(
            torch.dot(previous, following).item() / (previous_norm * following_norm)
        )
        angle = math.acos(max(-1.0, min(1.0, cosine)))
        local_arc = 0.5 * (previous_norm + following_norm)
        angles.append(angle)
        curvatures.append(angle / max(local_arc, epsilon))
    return angles, curvatures


def summarize_mirror_geometry(
    mirror_states: Any, revised_states: Any
) -> GeometrySummary:
    mirror = _as_tensor(mirror_states)
    revised = _as_tensor(revised_states)
    if mirror.ndim != 2 or revised.ndim != 2:
        raise ValueError("mirror and revised states must have shape [T, D]")
    if mirror.shape != revised.shape:
        raise ValueError(
            f"mirror/revised shape mismatch: {tuple(mirror.shape)} != {tuple(revised.shape)}"
        )
    if mirror.shape[0] == 0:
        raise ValueError("mirror/revised trajectories must not be empty")
    separation = [
        float(value)
        for value in torch.linalg.vector_norm(revised - mirror, dim=-1).tolist()
    ]
    mirror_angles, mirror_curvatures = turn_angle_and_curvature(mirror)
    revised_angles, revised_curvatures = turn_angle_and_curvature(revised)
    angle_pairs = [
        (left, right)
        for left, right in zip(mirror_angles, revised_angles)
        if left is not None and right is not None
    ]
    curvature_pairs = [
        (left, right)
        for left, right in zip(mirror_curvatures, revised_curvatures)
        if left is not None and right is not None
    ]
    return GeometrySummary(
        step_count=int(mirror.shape[0]),
        separation_auc=_trapezoid_auc(separation),
        separation_mean=statistics.fmean(separation),
        separation_max=max(separation),
        separation_terminal=separation[-1],
        mirror_turn_angle_mean=_finite_mean(mirror_angles),
        revised_turn_angle_mean=_finite_mean(revised_angles),
        excess_turn_angle_mean=(
            statistics.fmean(right - left for left, right in angle_pairs)
            if angle_pairs
            else None
        ),
        mirror_curvature_mean=_finite_mean(mirror_curvatures),
        revised_curvature_mean=_finite_mean(revised_curvatures),
        excess_curvature_mean=(
            statistics.fmean(right - left for left, right in curvature_pairs)
            if curvature_pairs
            else None
        ),
        undefined_turn_count=sum(
            int(left is None or right is None)
            for left, right in zip(mirror_angles, revised_angles)
        ),
    )


def _average_ranks(values: Sequence[float]) -> list[float]:
    ordered = sorted(
        enumerate(float(value) for value in values), key=lambda item: item[1]
    )
    ranks = [0.0] * len(ordered)
    cursor = 0
    while cursor < len(ordered):
        end = cursor + 1
        while end < len(ordered) and ordered[end][1] == ordered[cursor][1]:
            end += 1
        average = 0.5 * ((cursor + 1) + end)
        for position in range(cursor, end):
            ranks[ordered[position][0]] = average
        cursor = end
    return ranks


def pearson_correlation(left: Sequence[float], right: Sequence[float]) -> float | None:
    if len(left) != len(right):
        raise ValueError("correlation inputs must have equal length")
    if len(left) < 2:
        return None
    left_mean = statistics.fmean(left)
    right_mean = statistics.fmean(right)
    left_centered = [value - left_mean for value in left]
    right_centered = [value - right_mean for value in right]
    denominator = math.sqrt(
        sum(value * value for value in left_centered)
        * sum(value * value for value in right_centered)
    )
    if denominator <= EPSILON:
        return None
    return (
        sum(
            left_value * right_value
            for left_value, right_value in zip(left_centered, right_centered)
        )
        / denominator
    )


def spearman_correlation(left: Sequence[float], right: Sequence[float]) -> float | None:
    if len(left) != len(right):
        raise ValueError("correlation inputs must have equal length")
    if len(left) < 2:
        return None
    return pearson_correlation(_average_ranks(left), _average_ranks(right))


def candidate_alignment_metrics(
    candidates: Sequence[Mapping[str, Any]], selected_steps: Sequence[int]
) -> dict[str, Any]:
    """Compare semantics with target-aligned source-projection leverage."""

    boundary_limited_count = sum(
        int(bool(item.get("boundary_limited", False))) for item in candidates
    )
    clean = [
        item
        for item in candidates
        if item.get("semantic_attention") is not None
        and item.get("control_leverage") is not None
        and math.isfinite(float(item["semantic_attention"]))
        and math.isfinite(float(item["control_leverage"]))
    ]
    if not clean:
        return {
            "candidate_count": 0,
            "boundary_limited_candidate_count": boundary_limited_count,
            "boundary_limited_candidate_fraction": None,
            "attention_leverage_spearman": None,
            "selected_is_max_leverage": None,
            "selected_leverage_regret": None,
            "attention_mass_on_max_leverage": None,
            "semantic_gold_is_max_leverage": None,
            "selected_hits_semantic_gold": None,
        }
    attention = [float(item["semantic_attention"]) for item in clean]
    leverage = [float(item["control_leverage"]) for item in clean]
    max_leverage = max(leverage)
    tolerance = max(1e-12, abs(max_leverage) * 1e-9)
    max_steps = {
        int(item["candidate_step"])
        for item in clean
        if abs(float(item["control_leverage"]) - max_leverage) <= tolerance
    }
    selected = set(int(step) for step in selected_steps)
    semantic_gold = {
        int(item["candidate_step"])
        for item in clean
        if int(item.get("is_semantic_gold", 0)) == 1
    }
    selected_leverage = [
        float(item["control_leverage"])
        for item in clean
        if int(item["candidate_step"]) in selected
    ]
    return {
        "candidate_count": len(clean),
        "boundary_limited_candidate_count": boundary_limited_count,
        "boundary_limited_candidate_fraction": boundary_limited_count / len(clean),
        "attention_leverage_spearman": spearman_correlation(attention, leverage),
        "selected_is_max_leverage": int(bool(selected & max_steps)),
        "selected_leverage_regret": (
            max_leverage - max(selected_leverage) if selected_leverage else None
        ),
        "attention_mass_on_max_leverage": sum(
            float(item["semantic_attention"])
            for item in clean
            if int(item["candidate_step"]) in max_steps
        ),
        "semantic_gold_is_max_leverage": (
            int(bool(semantic_gold & max_steps)) if semantic_gold else None
        ),
        "selected_hits_semantic_gold": (
            int(bool(selected & semantic_gold)) if semantic_gold else None
        ),
    }


def case_cluster_bootstrap(
    rows: Sequence[Mapping[str, Any]],
    statistic: Any,
    *,
    seed: int = BOOTSTRAP_SEED,
    resamples: int = 2_000,
) -> dict[str, Any]:
    """Resample cases while retaining every paired seed/event within a case."""

    if resamples < 1:
        raise ValueError("resamples must be >= 1")
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["case_id"])].append(row)
    case_ids = sorted(grouped)
    if not case_ids:
        return {"case_count": 0, "estimate": None, "ci_low": None, "ci_high": None}
    estimate = statistic(list(rows))
    if estimate is None or not math.isfinite(float(estimate)):
        return {
            "case_count": len(case_ids),
            "estimate": None,
            "ci_low": None,
            "ci_high": None,
        }
    rng = random.Random(seed)
    draws: list[float] = []
    for _ in range(resamples):
        sampled_rows: list[Mapping[str, Any]] = []
        for _ in case_ids:
            sampled_rows.extend(grouped[rng.choice(case_ids)])
        value = statistic(sampled_rows)
        if value is not None and math.isfinite(float(value)):
            draws.append(float(value))
    return {
        "case_count": len(case_ids),
        "estimate": float(estimate),
        "ci_low": _percentile(draws, 0.025),
        "ci_high": _percentile(draws, 0.975),
    }


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    fieldnames = sorted({str(key) for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        if not fieldnames:
            handle.write("")
            return
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in fieldnames})


def _load_module(path: Path, module_name: str) -> Any:
    if not path.is_file():
        raise FileNotFoundError(path)
    sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _numeric(rows: Sequence[Mapping[str, Any]], field: str) -> list[float]:
    values: list[float] = []
    for row in rows:
        value = row.get(field)
        if value is None or isinstance(value, bool):
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number):
            values.append(number)
    return values


def _distribution(values: Sequence[float]) -> dict[str, Any]:
    if not values:
        return {"n": 0, "mean": None, "median": None, "p05": None, "p95": None}
    return {
        "n": len(values),
        "mean": statistics.fmean(values),
        "median": statistics.median(values),
        "p05": _percentile(values, 0.05),
        "p95": _percentile(values, 0.95),
    }


def _field_correlation(
    rows: Sequence[Mapping[str, Any]], left_field: str, right_field: str
) -> float | None:
    paired: list[tuple[float, float]] = []
    for row in rows:
        left = row.get(left_field)
        right = row.get(right_field)
        if left is None or right is None:
            continue
        try:
            left_number = float(left)
            right_number = float(right)
        except (TypeError, ValueError):
            continue
        if math.isfinite(left_number) and math.isfinite(right_number):
            paired.append((left_number, right_number))
    return spearman_correlation(
        [item[0] for item in paired], [item[1] for item in paired]
    )


def _group_mean_difference(
    rows: Sequence[Mapping[str, Any]],
    metric_field: str,
    group_field: str,
) -> float | None:
    positive: list[float] = []
    negative: list[float] = []
    for row in rows:
        metric = row.get(metric_field)
        group = row.get(group_field)
        if metric is None or group is None:
            continue
        try:
            metric_number = float(metric)
            group_number = int(group)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(metric_number):
            continue
        (positive if group_number == 1 else negative).append(metric_number)
    if not positive or not negative:
        return None
    return statistics.fmean(positive) - statistics.fmean(negative)


def _field_mean(rows: Sequence[Mapping[str, Any]], field: str) -> float | None:
    values = _numeric(rows, field)
    return statistics.fmean(values) if values else None


def _seed_invariant_by_case_source(
    rows: Sequence[Mapping[str, Any]], field: str
) -> bool:
    """Check whether a metric repeats exactly across seeds per case/event source."""

    grouped: dict[tuple[str, int], list[float]] = defaultdict(list)
    for row in rows:
        value = row.get(field)
        if value is None:
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number):
            grouped[(str(row["case_id"]), int(row["source_step"]))].append(number)
    return bool(grouped) and all(
        max(values) - min(values) <= EPSILON for values in grouped.values()
    )


def build_outcome_associations(
    event_rows: Sequence[Mapping[str, Any]],
    *,
    bootstrap_resamples: int,
) -> list[dict[str, Any]]:
    """Build descriptive, case-clustered geometry/outcome associations."""

    correlations = (
        ("separation_auc", "source_projection_gain"),
        ("separation_auc_per_step", "source_projection_gain"),
        ("separation_mean", "source_projection_gain"),
        ("post_source_auc", "source_projection_gain"),
        ("post_source_mean", "source_projection_gain"),
        ("post_source_retention_ratio", "source_projection_gain"),
        ("separation_terminal", "source_projection_gain"),
        ("excess_turn_angle_mean", "source_projection_gain"),
        ("excess_curvature_mean", "source_projection_gain"),
        ("control_delta_norm", "source_projection_gain"),
        ("control_efficiency", "unrelated_state_leakage"),
        ("attention_leverage_spearman", "source_projection_gain"),
        ("selected_is_max_leverage", "source_projection_gain"),
    )
    results: list[dict[str, Any]] = []
    for index, (left, right) in enumerate(correlations):
        selected_rows = (
            [row for row in event_rows if int(row.get("candidate_count", 0)) > 1]
            if left
            in {
                "attention_leverage_spearman",
                "selected_is_max_leverage",
                "semantic_gold_is_max_leverage",
                "selected_hits_semantic_gold",
            }
            else list(event_rows)
        )

        def correlation_statistic(
            rows: Sequence[Mapping[str, Any]],
            left: str = left,
            right: str = right,
        ) -> float | None:
            return _field_correlation(rows, left, right)

        bootstrap = case_cluster_bootstrap(
            selected_rows,
            correlation_statistic,
            seed=BOOTSTRAP_SEED + index,
            resamples=bootstrap_resamples,
        )
        results.append(
            {
                "kind": "spearman_association",
                "left_metric": left,
                "right_metric": right,
                "case_cluster_bootstrap": bootstrap,
                "interpretation": "descriptive association; not a causal estimand",
            }
        )
    for index, metric in enumerate(
        (
            "separation_auc",
            "separation_terminal",
            "excess_turn_angle_mean",
            "excess_curvature_mean",
            "control_efficiency",
            "selected_is_max_leverage",
        )
    ):
        selected_rows = (
            [row for row in event_rows if int(row.get("candidate_count", 0)) > 1]
            if metric == "selected_is_max_leverage"
            else list(event_rows)
        )

        def mean_difference_statistic(
            rows: Sequence[Mapping[str, Any]], metric: str = metric
        ) -> float | None:
            return _group_mean_difference(rows, metric, "outcome_success")

        bootstrap = case_cluster_bootstrap(
            selected_rows,
            mean_difference_statistic,
            seed=BOOTSTRAP_SEED + 100 + index,
            resamples=bootstrap_resamples,
        )
        results.append(
            {
                "kind": "successful_minus_unsuccessful_mean",
                "left_metric": metric,
                "right_metric": "outcome_success",
                "case_cluster_bootstrap": bootstrap,
                "interpretation": "post-outcome descriptive split; not a randomized contrast",
            }
        )
    return results


def summarize_measurements(
    trial_rows: Sequence[Mapping[str, Any]],
    event_rows: Sequence[Mapping[str, Any]],
    candidate_rows: Sequence[Mapping[str, Any]],
    *,
    bootstrap_resamples: int,
) -> dict[str, Any]:
    boundary_flags = _numeric(candidate_rows, "boundary_limited")
    probe_control_norms = _numeric(candidate_rows, "probe_control_norm_max")
    control_norm_limits = _numeric(candidate_rows, "max_control_norm")
    boundary_limited_count = sum(int(value > 0.5) for value in boundary_flags)
    observed_probe_control_norm_max = (
        max(probe_control_norms) if probe_control_norms else None
    )
    frozen_control_norm_max = (
        max(control_norm_limits) if control_norm_limits else None
    )
    probe_bound_tolerance = 1e-5
    event_fields = (
        "separation_auc",
        "separation_auc_per_step",
        "separation_mean",
        "separation_max",
        "separation_terminal",
        "post_source_auc",
        "post_source_mean",
        "post_source_retention_ratio",
        "source_projection_gain",
        "target_projection_gain",
        "terminal_projection_gain",
        "propagation_survival_ratio",
        "unrelated_state_leakage",
        "control_delta_norm",
        "control_efficiency",
        "mirror_turn_angle_mean",
        "revised_turn_angle_mean",
        "excess_turn_angle_mean",
        "mirror_curvature_mean",
        "revised_curvature_mean",
        "excess_curvature_mean",
        "boundary_limited_candidate_count",
        "boundary_limited_candidate_fraction",
        "attention_leverage_spearman",
        "selected_is_max_leverage",
        "selected_leverage_regret",
        "semantic_gold_is_max_leverage",
        "selected_hits_semantic_gold",
    )
    trial_fields = (
        "target_topic_success",
        "topic_accuracy",
        "source_distance_gain",
        "target_distance_gain",
        "unrelated_topic_state_drift_max",
        "source_gain_per_revision_step",
        "target_gain_per_backward_call",
    )
    candidate_fields = (
        "semantic_attention",
        "control_leverage",
        "boundary_limited",
        "probe_control_norm_max",
    )
    alignment_fields = (
        "attention_leverage_spearman",
        "selected_is_max_leverage",
        "selected_leverage_regret",
        "semantic_gold_is_max_leverage",
        "selected_hits_semantic_gold",
    )
    informative_event_rows = [
        row for row in event_rows if int(row.get("candidate_count", 0)) > 1
    ]
    alignment_bootstrap: dict[str, dict[str, Any]] = {}
    for index, field in enumerate(alignment_fields):

        def mean_statistic(
            rows: Sequence[Mapping[str, Any]], field: str = field
        ) -> float | None:
            return _field_mean(rows, field)

        alignment_bootstrap[field] = case_cluster_bootstrap(
            informative_event_rows,
            mean_statistic,
            seed=BOOTSTRAP_SEED + 300 + index,
            resamples=bootstrap_resamples,
        )
    return {
        "counts": {
            "trial_rows": len(trial_rows),
            "event_rows": len(event_rows),
            "multi_candidate_event_rows": len(informative_event_rows),
            "multi_candidate_cases": len(
                {str(row["case_id"]) for row in informative_event_rows}
            ),
            "multi_candidate_case_sources": len(
                {
                    (str(row["case_id"]), int(row["source_step"]))
                    for row in informative_event_rows
                }
            ),
            "multi_candidate_families": len(
                {str(row["family"]) for row in informative_event_rows}
            ),
            "candidate_rows": len(candidate_rows),
            "cases": len({str(row["case_id"]) for row in trial_rows}),
            "model_seeds": len({int(row["model_seed"]) for row in trial_rows}),
        },
        "trial_metrics": {
            field: _distribution(_numeric(trial_rows, field)) for field in trial_fields
        },
        "event_metrics": {
            field: _distribution(_numeric(event_rows, field)) for field in event_fields
        },
        "informative_alignment_metrics": {
            field: _distribution(_numeric(informative_event_rows, field))
            for field in alignment_fields
        },
        "informative_alignment_case_cluster_bootstrap": alignment_bootstrap,
        "informative_alignment_seed_invariant_by_case_source": {
            field: _seed_invariant_by_case_source(informative_event_rows, field)
            for field in alignment_fields
        },
        "candidate_control_leverage_definition": (
            "Feasible centered or radially projected forward one-sided finite "
            "difference of target-aligned event-source belief projection along "
            "one normalized topic-aligned control direction."
        ),
        "probe_feasibility": {
            "candidate_count": len(candidate_rows),
            "boundary_limited_candidate_count": boundary_limited_count,
            "boundary_limited_candidate_fraction": (
                boundary_limited_count / len(candidate_rows)
                if candidate_rows
                else None
            ),
            "observed_probe_control_norm_max": observed_probe_control_norm_max,
            "frozen_control_norm_max": frozen_control_norm_max,
            "assertion_tolerance": probe_bound_tolerance,
            "within_frozen_control_bound": (
                observed_probe_control_norm_max
                <= frozen_control_norm_max + probe_bound_tolerance
                if observed_probe_control_norm_max is not None
                and frozen_control_norm_max is not None
                else None
            ),
        },
        "candidate_metrics": {
            field: _distribution(_numeric(candidate_rows, field))
            for field in candidate_fields
        },
        "outcome_associations": build_outcome_associations(
            event_rows, bootstrap_resamples=bootstrap_resamples
        ),
        "uncertainty_note": (
            "Intervals resample case clusters while retaining all paired model seeds and "
            "events within each selected case. They describe this fixed synthetic suite."
        ),
    }


def _format_number(value: Any, digits: int = 4) -> str:
    if value is None:
        return "—"
    return f"{float(value):.{digits}f}"


def render_report(results: Mapping[str, Any]) -> str:
    summary = results["summary"]
    counts = summary["counts"]
    event_metrics = summary["event_metrics"]
    informative_alignment = summary["informative_alignment_metrics"]
    alignment_bootstrap = summary["informative_alignment_case_cluster_bootstrap"]
    alignment_seed_invariant = summary[
        "informative_alignment_seed_invariant_by_case_source"
    ]
    trial_metrics = summary["trial_metrics"]
    probe_feasibility = summary["probe_feasibility"]
    lines = [
        "# EBRT v0.2 instrumentation benchmark",
        "",
        "## Outcome",
        "",
        f"- Mode: `{results['mode']}`",
        f"- Trials: {counts['trial_rows']} across {counts['cases']} cases and {counts['model_seeds']} paired seeds",
        f"- Instrumented events: {counts['event_rows']}",
        f"- Multi-candidate events: {counts['multi_candidate_event_rows']}",
        (
            "- Multi-candidate support: "
            f"{counts['multi_candidate_cases']} case clusters, "
            f"{counts['multi_candidate_case_sources']} case-source fixtures, "
            f"{counts['multi_candidate_families']} families"
        ),
        f"- Offline candidate probes: {counts['candidate_rows']}",
        "",
        "The event-local mirror is the attribution baseline. Curvature and semantic/source-projection-leverage",
        "alignment are exploratory diagnostics and are not standalone quality measures.",
        "",
        "## Core measurements",
        "",
        "| Metric | Mean | Median | 5th–95th percentile |",
        "| --- | ---: | ---: | ---: |",
    ]
    for field in (
        "separation_auc",
        "separation_auc_per_step",
        "post_source_auc",
        "post_source_mean",
        "post_source_retention_ratio",
        "source_projection_gain",
        "target_projection_gain",
        "terminal_projection_gain",
        "unrelated_state_leakage",
        "control_efficiency",
        "excess_turn_angle_mean",
        "excess_curvature_mean",
    ):
        metric = event_metrics[field]
        lines.append(
            f"| `{field}` | {_format_number(metric['mean'])} | "
            f"{_format_number(metric['median'])} | "
            f"{_format_number(metric['p05'])}–{_format_number(metric['p95'])} |"
        )
    lines.extend(
        [
            "",
            "## Candidate routing alignment",
            "",
            "Single-candidate events make selection agreement mechanical, so the",
            "multi-candidate column is the informative routing comparison.",
            "Here `control_leverage` is only the target-aligned event-source belief",
            "projection finite difference along one predefined topic-aligned control",
            "direction. Boundary samples are radially projected through the frozen",
            "control constraint; this is not an objective gradient or full controllability.",
            "",
            (
                f"Boundary-limited probes: {probe_feasibility['boundary_limited_candidate_count']}/"
                f"{probe_feasibility['candidate_count']} "
                f"({_format_number(100.0 * probe_feasibility['boundary_limited_candidate_fraction'], 2)}%). "
                f"Maximum evaluated control norm: "
                f"{_format_number(probe_feasibility['observed_probe_control_norm_max'], 9)} "
                f"against the frozen-core limit "
                f"{_format_number(probe_feasibility['frozen_control_norm_max'], 2)} "
                f"with {probe_feasibility['assertion_tolerance']:.0e} assertion tolerance; "
                f"bound check: {'PASS' if probe_feasibility['within_frozen_control_bound'] else 'FAIL'}."
            ),
            "",
            "| Metric | All events (mean; n) | Multi-candidate only (mean; n) | Case-cluster 95% CI |",
            "| --- | ---: | ---: | ---: |",
        ]
    )
    for field in (
        "attention_leverage_spearman",
        "selected_is_max_leverage",
        "selected_leverage_regret",
        "semantic_gold_is_max_leverage",
        "selected_hits_semantic_gold",
    ):
        all_metric = event_metrics[field]
        informative_metric = informative_alignment[field]
        bootstrap = alignment_bootstrap[field]
        lines.append(
            f"| `{field}` | {_format_number(all_metric['mean'])}; {all_metric['n']} | "
            f"{_format_number(informative_metric['mean'])}; {informative_metric['n']} | "
            f"[{_format_number(bootstrap['ci_low'])}, {_format_number(bootstrap['ci_high'])}] |"
        )
    lines.extend(
        [
            "",
            (
                "All five multi-candidate alignment metrics were seed-invariant within "
                "each case-source fixture. The 512 event rows therefore do not represent "
                "512 independent routing situations."
                if all(alignment_seed_invariant.values())
                else "At least one alignment metric varied across seeds within a fixture."
            ),
            "",
            "## Session outcomes",
            "",
            "| Metric | Mean |",
            "| --- | ---: |",
        ]
    )
    for field in (
        "target_topic_success",
        "source_distance_gain",
        "target_distance_gain",
        "unrelated_topic_state_drift_max",
    ):
        lines.append(f"| `{field}` | {_format_number(trial_metrics[field]['mean'])} |")
    lines.extend(
        [
            "",
            "## Outcome and leakage associations",
            "",
            "| Kind | Geometry/control metric | Outcome metric | Estimate | Case-cluster 95% CI |",
            "| --- | --- | --- | ---: | ---: |",
        ]
    )
    for item in summary["outcome_associations"]:
        bootstrap = item["case_cluster_bootstrap"]
        lines.append(
            f"| {item['kind']} | `{item['left_metric']}` | `{item['right_metric']}` | "
            f"{_format_number(bootstrap['estimate'])} | "
            f"[{_format_number(bootstrap['ci_low'])}, {_format_number(bootstrap['ci_high'])}] |"
        )
    lines.extend(
        [
            "",
            "These associations are discovery signals. A non-zero association does not show",
            "that curvature or leverage causes a better revision; obvious magnitude, distance,",
            "sequence-length, and representation confounds remain.",
            "",
            "## Claim boundary",
            "",
            *[f"- {statement}" for statement in results["claim_boundary"]],
            "",
        ]
    )
    return "\n".join(lines)


def write_bundle(
    output_dir: Path,
    *,
    trial_rows: Sequence[Mapping[str, Any]],
    event_rows: Sequence[Mapping[str, Any]],
    candidate_rows: Sequence[Mapping[str, Any]],
    results: Mapping[str, Any],
    manifest_base: Mapping[str, Any],
) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_names = (
        "trials.csv",
        "events.csv",
        "candidates.csv",
        "results.json",
        "benchmark_report.md",
    )
    with tempfile.TemporaryDirectory(
        prefix=".ebrt-v02-stage-", dir=output_dir.parent
    ) as temporary:
        stage = Path(temporary)
        _write_csv(stage / "trials.csv", trial_rows)
        _write_csv(stage / "events.csv", event_rows)
        _write_csv(stage / "candidates.csv", candidate_rows)
        _write_json(stage / "results.json", results)
        (stage / "benchmark_report.md").write_text(
            render_report(results), encoding="utf-8"
        )
        artifacts = {
            name: {
                "sha256": _sha256(stage / name),
                "bytes": (stage / name).stat().st_size,
            }
            for name in artifact_names
        }
        manifest = {**dict(manifest_base), "artifacts": artifacts}
        _write_json(stage / "manifest.json", manifest)
        for name in (*artifact_names, "manifest.json"):
            os.replace(stage / name, output_dir / name)
    return manifest


def _first_present(mapping: Mapping[str, Any], names: Sequence[str]) -> Any:
    for name in names:
        if name in mapping:
            return mapping[name]
    return None


def _projection_score(
    engine: Any, states: torch.Tensor, local_index: int, topic: str
) -> float:
    q = int(engine.config.topic_dim)
    topic_vector = engine.codec.topic_vector(topic).detach().cpu().to(torch.float64)
    state = states[local_index].detach().cpu().to(torch.float64)
    return float((state[q : 2 * q] @ topic_vector).item())


def _distance_gain(before: float, after: float, target: float) -> float:
    return abs(before - target) - abs(after - target)


def _normalise_leverage_rows(trace: Mapping[str, Any]) -> list[dict[str, Any]]:
    payload = trace.get("candidate_control_leverage")
    if payload is None:
        return []
    if isinstance(payload, Mapping):
        raw = payload.get("candidates", [])
        max_control_norm = payload.get("max_control_norm")
    elif isinstance(payload, Sequence) and not isinstance(payload, (str, bytes)):
        raw = payload
        max_control_norm = None
    else:
        raise TypeError("candidate_control_leverage must be a mapping or sequence")
    rows: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, Mapping):
            raise TypeError("candidate leverage rows must be mappings")
        leverage = _first_present(
            item,
            (
                "control_leverage",
                "gradient_norm",
                "objective_gradient_norm",
                "local_gradient_norm",
            ),
        )
        rows.append(
            {
                **dict(item),
                "source_step": int(item["source_step"]),
                "candidate_step": int(item["candidate_step"]),
                "control_leverage": float(leverage) if leverage is not None else None,
                "max_control_norm": max_control_norm,
            }
        )
    return rows


def _candidate_rows_for_event(
    case: Any,
    mirror: Mapping[str, Any],
    leverage_rows: Sequence[Mapping[str, Any]],
    *,
    model_seed: int,
) -> list[dict[str, Any]]:
    source_step = int(mirror["source_step"])
    candidate_steps = [int(value) for value in mirror.get("candidate_steps", [])]
    attention_weights = [float(value) for value in mirror.get("attention_weights", [])]
    selected = {int(value) for value in mirror.get("target_steps", [])}
    leverage_by_step = {
        int(item["candidate_step"]): item
        for item in leverage_rows
        if int(item["source_step"]) == source_step
    }
    expected_by_source = {int(item.source_step): item for item in case.expected_events}
    gold_steps = set(
        int(value)
        for value in (
            expected_by_source[source_step].target_steps
            if source_step in expected_by_source
            else ()
        )
    )
    rows: list[dict[str, Any]] = []
    for candidate_step in candidate_steps:
        leverage = leverage_by_step.get(candidate_step, {})
        attention = (
            attention_weights[candidate_step]
            if candidate_step < len(attention_weights)
            else _first_present(leverage, ("semantic_attention", "attention_weight"))
        )
        rows.append(
            {
                "schema_version": SCHEMA_VERSION,
                "case_id": case.case_id,
                "family": case.family,
                "model_seed": model_seed,
                "source_step": source_step,
                "candidate_step": candidate_step,
                "semantic_attention": float(attention)
                if attention is not None
                else None,
                "control_leverage": leverage.get("control_leverage"),
                "finite_difference_scheme": leverage.get("finite_difference_scheme"),
                "boundary_limited": (
                    int(bool(leverage["boundary_limited"]))
                    if leverage.get("boundary_limited") is not None
                    else None
                ),
                "plus_requested_feasible": (
                    int(bool(leverage["plus_requested_feasible"]))
                    if leverage.get("plus_requested_feasible") is not None
                    else None
                ),
                "minus_requested_feasible": (
                    int(bool(leverage["minus_requested_feasible"]))
                    if leverage.get("minus_requested_feasible") is not None
                    else None
                ),
                "requested_epsilon": leverage.get("requested_epsilon"),
                "actual_plus_delta_norm": leverage.get("actual_plus_delta_norm"),
                "actual_minus_delta_norm": leverage.get("actual_minus_delta_norm"),
                "control_norm_before": leverage.get("control_norm_before"),
                "requested_plus_control_norm": leverage.get(
                    "requested_plus_control_norm"
                ),
                "requested_minus_control_norm": leverage.get(
                    "requested_minus_control_norm"
                ),
                "plus_control_norm": leverage.get("plus_control_norm"),
                "minus_control_norm": leverage.get("minus_control_norm"),
                "probe_control_norm_max": leverage.get("probe_control_norm_max"),
                "max_control_norm": leverage.get("max_control_norm"),
                "semantic_score": leverage.get("semantic_score"),
                "target_aligned_terminal_belief_derivative": leverage.get(
                    "target_aligned_terminal_belief_derivative"
                ),
                "source_state_derivative_norm": leverage.get(
                    "source_state_derivative_norm"
                ),
                "terminal_state_derivative_norm": leverage.get(
                    "terminal_state_derivative_norm"
                ),
                "is_selected": int(candidate_step in selected),
                "is_semantic_gold": int(candidate_step in gold_steps),
                "candidate_distance": source_step - candidate_step,
            }
        )
    finite_leverage = [
        float(row["control_leverage"])
        for row in rows
        if row["control_leverage"] is not None
        and math.isfinite(float(row["control_leverage"]))
    ]
    if finite_leverage:
        maximum = max(finite_leverage)
        tolerance = max(1e-12, abs(maximum) * 1e-9)
        for row in rows:
            value = row["control_leverage"]
            row["is_max_leverage"] = int(
                value is not None and abs(float(value) - maximum) <= tolerance
            )
    else:
        for row in rows:
            row["is_max_leverage"] = None
    return rows


def _event_row(
    case: Any,
    engine: Any,
    result: Any,
    mirror: Mapping[str, Any],
    candidate_rows: Sequence[Mapping[str, Any]],
    trial_row: Mapping[str, Any],
    *,
    model_seed: int,
) -> dict[str, Any]:
    source_step = int(mirror["source_step"])
    local_steps = [int(value) for value in mirror["local_steps"]]
    mirror_states = _as_tensor(mirror["mirror_states"])
    revised_states = _as_tensor(mirror["revised_states"])
    if len(local_steps) != mirror_states.shape[0]:
        raise AssertionError("local_steps and mirror_states length differ")
    local_geometry = summarize_mirror_geometry(mirror_states, revised_states).to_dict()
    event_by_source = {
        int(item.source_step): item
        for item in [*result.events, *result.suppressed_events]
    }
    if source_step not in event_by_source:
        raise AssertionError(f"mirror has no matching event at source {source_step}")
    event = event_by_source[source_step]
    topic = case.observations[source_step]["topic"].strip().lower()
    local_index = {step: index for index, step in enumerate(local_steps)}
    source_local = local_index[source_step]
    mirror_source = _projection_score(engine, mirror_states, source_local, topic)
    revised_source = _projection_score(engine, revised_states, source_local, topic)
    local_source_gain = _distance_gain(
        mirror_source, revised_source, float(event.revision_target)
    )
    target_gains: list[float] = []
    target_separations: list[float] = []
    for target_step in mirror.get("target_steps", []):
        target_step = int(target_step)
        if target_step not in local_index:
            continue
        index = local_index[target_step]
        before = _projection_score(engine, mirror_states, index, topic)
        after = _projection_score(engine, revised_states, index, topic)
        target_gains.append(_distance_gain(before, after, float(event.revision_target)))
        target_separations.append(
            float(
                torch.linalg.vector_norm(
                    revised_states[index] - mirror_states[index]
                ).item()
            )
        )
    separations = [
        float(value)
        for value in torch.linalg.vector_norm(
            revised_states - mirror_states, dim=-1
        ).tolist()
    ]
    propagation_separation = [
        float(value) for value in mirror.get("propagation_separation", separations)
    ]
    if not propagation_separation:
        raise AssertionError("propagation_separation must not be empty")
    if not 0 <= source_step < len(propagation_separation):
        raise AssertionError("source_step falls outside propagation_separation")
    separation_auc = _trapezoid_auc(propagation_separation)
    post_source_separation = propagation_separation[source_step:]
    post_source_auc = _trapezoid_auc(post_source_separation)
    post_source_mean = statistics.fmean(post_source_separation)
    post_source_source_value = post_source_separation[0]
    post_source_retention_ratio = (
        post_source_separation[-1] / post_source_source_value
        if post_source_source_value > EPSILON
        else None
    )
    unrelated = [
        separations[index]
        for index, absolute_step in enumerate(local_steps)
        if case.observations[absolute_step]["topic"].strip().lower() != topic
    ]
    magnitudes = dict(mirror.get("magnitudes", {}))
    control_delta_norm = _first_present(
        magnitudes, ("control_delta_l2", "control_delta_norm")
    )
    if control_delta_norm is None:
        before_controls = _as_tensor(mirror["controls_before"])
        after_controls = _as_tensor(mirror["controls_after"])
        control_delta_norm = float(
            torch.linalg.vector_norm(after_controls - before_controls).item()
        )
    source_separation = separations[source_local]
    target_separation = (
        statistics.fmean(target_separations) if target_separations else None
    )
    source_gain = float(mirror.get("source_target_projection_gain", local_source_gain))
    terminal_gain = float(mirror.get("terminal_target_projection_gain", source_gain))
    survival = mirror.get("propagation_survival_ratio")
    leakage = float(
        mirror.get("unrelated_state_leakage_max", max(unrelated, default=0.0))
    )
    alignment = candidate_alignment_metrics(
        candidate_rows, [int(value) for value in mirror.get("target_steps", [])]
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "case_id": case.case_id,
        "family": case.family,
        "model_seed": model_seed,
        "source_step": source_step,
        "event_topic": topic,
        "event_score": float(event.score),
        "revision_target": float(event.revision_target),
        "target_steps": json.dumps(
            list(mirror.get("target_steps", [])), separators=(",", ":")
        ),
        "candidate_count": alignment["candidate_count"],
        "accepted": int(bool(mirror.get("accepted", False))),
        "rolled_back": int(bool(mirror.get("rolled_back", False))),
        "earliest_replay_step": int(mirror["earliest_replay_step"]),
        "replay_span_steps": int(mirror["replay_span_steps"]),
        "replay_distance": int(mirror["replay_distance"]),
        "step_count": len(propagation_separation),
        "separation_auc": separation_auc,
        "separation_auc_per_step": separation_auc
        / max(1, len(propagation_separation) - 1),
        "separation_mean": statistics.fmean(propagation_separation),
        "separation_max": max(propagation_separation),
        "separation_terminal": propagation_separation[-1],
        "post_source_step_count": len(post_source_separation),
        "post_source_auc": post_source_auc,
        "post_source_mean": post_source_mean,
        "post_source_retention_ratio": post_source_retention_ratio,
        "local_step_count": local_geometry["step_count"],
        "local_separation_auc": local_geometry["separation_auc"],
        "local_separation_mean": local_geometry["separation_mean"],
        "local_separation_max": local_geometry["separation_max"],
        "local_separation_terminal": local_geometry["separation_terminal"],
        "mirror_turn_angle_mean": local_geometry["mirror_turn_angle_mean"],
        "revised_turn_angle_mean": local_geometry["revised_turn_angle_mean"],
        "excess_turn_angle_mean": local_geometry["excess_turn_angle_mean"],
        "mirror_curvature_mean": local_geometry["mirror_curvature_mean"],
        "revised_curvature_mean": local_geometry["revised_curvature_mean"],
        "excess_curvature_mean": local_geometry["excess_curvature_mean"],
        "undefined_turn_count": local_geometry["undefined_turn_count"],
        "source_projection_before": mirror_source,
        "source_projection_after": revised_source,
        "source_projection_gain": source_gain,
        "local_source_projection_gain": local_source_gain,
        "source_projection_gain_consistency_error": abs(
            source_gain - local_source_gain
        ),
        "target_projection_gain": _finite_mean(target_gains),
        "terminal_projection_gain": terminal_gain,
        "source_state_separation": source_separation,
        "target_state_separation": target_separation,
        "propagation_survival_ratio": (
            float(survival) if survival is not None else None
        ),
        "decay_distance": mirror.get("decay_distance"),
        "unrelated_state_leakage": leakage,
        "control_delta_norm": float(control_delta_norm),
        "control_efficiency": (
            source_gain / float(control_delta_norm)
            if float(control_delta_norm) > EPSILON
            else None
        ),
        **alignment,
        "outcome_success": trial_row.get("target_topic_success"),
        "session_source_distance_gain": trial_row.get("source_distance_gain"),
        "session_unrelated_topic_drift": trial_row.get(
            "unrelated_topic_state_drift_max"
        ),
    }


def _v01_execution(engine: Any, result: Any, observations: list[Any]) -> Any:
    detected = sorted(
        [*result.events, *result.suppressed_events], key=lambda item: item.source_step
    )
    return v01.Execution(
        arm="D_ebrt_full",
        config=result.config,
        engine=engine,
        observations=observations,
        baseline_states=result.baseline_states,
        final_states=result.final_states,
        controls=result.controls,
        detected_events=detected,
        committed_events=list(result.events),
        suppressed_events=list(result.suppressed_events),
        revisions=list(result.revisions),
        decoded=result.decoded,
        decode_call_count=result.decode_call_count,
        core_hash_before=result.core_hash_before,
        core_hash_after=result.core_hash_after,
        backward_calls=result.backward_calls,
        generator_step_calls=result.generator_step_calls,
        internal_elapsed_ms=0.0,
        external_wall_ms=0.0,
        process_peak_rss_mib=0.0,
    )


def _deterministic_trial_row(
    case: Any,
    engine: Any,
    result: Any,
    observations: list[Any],
    trace: Mapping[str, Any],
    *,
    model_seed: int,
) -> dict[str, Any]:
    execution = _v01_execution(engine, result, observations)
    row = v01.make_trial_row(
        case,
        execution,
        mode="instrumentation-v0.2",
        model_seed=model_seed,
        route_seed=v01._route_seed(case.case_id, model_seed),
        repeat_index=0,
    )
    for nondeterministic in (
        "internal_elapsed_ms",
        "external_wall_ms",
        "process_cumulative_peak_rss_mib",
        "revision_wall_ms",
    ):
        row.pop(nondeterministic, None)
    row["schema_version"] = SCHEMA_VERSION
    row["trace_fingerprint"] = trace.get("trace_fingerprint")
    row["instrumented_event_count"] = len(trace.get("revision_mirrors", []))
    return row


def _aggregate_event_fields(
    trial_row: dict[str, Any], rows: Sequence[Mapping[str, Any]]
) -> None:
    fields = (
        "separation_auc",
        "separation_auc_per_step",
        "post_source_auc",
        "post_source_mean",
        "post_source_retention_ratio",
        "separation_terminal",
        "source_projection_gain",
        "target_projection_gain",
        "unrelated_state_leakage",
        "control_efficiency",
        "excess_turn_angle_mean",
        "excess_curvature_mean",
        "attention_leverage_spearman",
        "selected_is_max_leverage",
        "semantic_gold_is_max_leverage",
        "selected_hits_semantic_gold",
    )
    for field in fields:
        trial_row[f"event_{field}_mean"] = _finite_mean(
            float(row[field]) if row.get(field) is not None else None for row in rows
        )


def run_instrumented_case(
    instrumentation: Any,
    base_module: Any,
    case: Any,
    *,
    model_seed: int,
    revision_steps: int,
    adapter_provenance: Mapping[str, Any] | None,
    candidate_control_leverage: bool,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], Any, Any]:
    config = v01._build_config(
        base_module,
        case,
        model_seed=model_seed,
        revision_steps=revision_steps,
        device="cpu",
        dtype="float32",
    )
    observations = v01._to_observations(base_module, case)
    engine = instrumentation.InstrumentedEventDrivenBackwardReasoner(
        config, capture_deep=False
    )
    session = engine.run_instrumented(
        observations,
        candidate_control_leverage=candidate_control_leverage,
        leverage_epsilon=LEVERAGE_EPSILON,
        adapter_provenance=adapter_provenance,
    )
    result = session.result
    trace = session.trace
    if trace.get("schema_version") != EXPECTED_TRACE_SCHEMA:
        raise AssertionError(
            f"unexpected instrumentation schema: {trace.get('schema_version')!r}"
        )
    trial_row = _deterministic_trial_row(
        case,
        engine,
        result,
        observations,
        trace,
        model_seed=model_seed,
    )
    leverage_rows = _normalise_leverage_rows(trace)
    all_candidate_rows: list[dict[str, Any]] = []
    event_rows: list[dict[str, Any]] = []
    for mirror in trace.get("revision_mirrors", []):
        candidate_rows = _candidate_rows_for_event(
            case,
            mirror,
            leverage_rows,
            model_seed=model_seed,
        )
        all_candidate_rows.extend(candidate_rows)
        event_rows.append(
            _event_row(
                case,
                engine,
                result,
                mirror,
                candidate_rows,
                trial_row,
                model_seed=model_seed,
            )
        )
    _aggregate_event_fields(trial_row, event_rows)
    return trial_row, event_rows, all_candidate_rows, result, trace


def run_matrix(
    instrumentation: Any,
    base_module: Any,
    cases: Sequence[Any],
    *,
    model_seeds: Sequence[int],
    revision_steps: int,
    adapter_provenance: Mapping[str, Any] | None,
    progress: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    trial_rows: list[dict[str, Any]] = []
    event_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []
    completed = 0
    total = len(cases) * len(model_seeds)
    for model_seed in model_seeds:
        for case in cases:
            trial, events, candidates, _, _ = run_instrumented_case(
                instrumentation,
                base_module,
                case,
                model_seed=model_seed,
                revision_steps=revision_steps,
                adapter_provenance=adapter_provenance,
                candidate_control_leverage=True,
            )
            trial_rows.append(trial)
            event_rows.extend(events)
            candidate_rows.extend(candidates)
            completed += 1
            if progress and (
                completed == total or completed % max(1, total // 20) == 0
            ):
                print(f"instrumentation progress {completed}/{total}", file=sys.stderr)
    trial_rows.sort(key=lambda row: (int(row["model_seed"]), str(row["case_id"])))
    event_rows.sort(
        key=lambda row: (
            int(row["model_seed"]),
            str(row["case_id"]),
            int(row["source_step"]),
        )
    )
    candidate_rows.sort(
        key=lambda row: (
            int(row["model_seed"]),
            str(row["case_id"]),
            int(row["source_step"]),
            int(row["candidate_step"]),
        )
    )
    return trial_rows, event_rows, candidate_rows


def _source_manifest(
    *,
    mode: str,
    monolith_path: Path,
    instrumentation_path: Path,
    semantic_adapter_path: Path,
    v01_benchmark_path: Path,
    fixture_sha: str,
    model_seeds: Sequence[int],
    revision_steps: int,
    bootstrap_resamples: int,
) -> dict[str, Any]:
    benchmark_path = Path(__file__).resolve()
    return {
        "schema_version": SCHEMA_VERSION,
        "mode": mode,
        "source": {
            "monolith_file": monolith_path.name,
            "monolith_sha256": _sha256(monolith_path),
            "instrumentation_file": instrumentation_path.name,
            "instrumentation_sha256": _sha256(instrumentation_path),
            "semantic_adapter_file": semantic_adapter_path.name,
            "semantic_adapter_sha256": _sha256(semantic_adapter_path),
            "v01_benchmark_file": v01_benchmark_path.name,
            "v01_benchmark_sha256": _sha256(v01_benchmark_path),
            "benchmark_file": benchmark_path.name,
            "benchmark_sha256": _sha256(benchmark_path),
            "fixture_sha256": fixture_sha,
        },
        "environment": {
            "python": platform.python_version(),
            "torch": torch.__version__,
            "platform": platform.platform(),
            "machine": platform.machine(),
            "device": "cpu",
            "dtype": "float32",
        },
        "protocol": {
            "case_suite": "frozen v0.1 48-case correctness suite",
            "arm": "D_ebrt_full instrumented",
            "model_seeds": list(model_seeds),
            "revision_steps": revision_steps,
            "candidate_control_leverage": True,
            "candidate_control_leverage_method": (
                "feasible_centered_or_projected_forward_one_sided_topic_aligned_control"
            ),
            "candidate_control_leverage_definition": (
                "target_aligned_event_source_belief_projection_sensitivity_"
                "to_one_normalized_topic_aligned_requested_actuation_after_"
                "the_frozen_radial_control_projection"
            ),
            "candidate_control_leverage_epsilon": LEVERAGE_EPSILON,
            "geometry_epsilon": GEOMETRY_EPSILON,
            "bootstrap_seed": BOOTSTRAP_SEED,
            "bootstrap_resamples": bootstrap_resamples,
            "pairing_unit": ["case_id", "model_seed"],
            "timing_fields_excluded_for_determinism": True,
        },
        "claim_boundary": list(CLAIM_BOUNDARY),
    }


def run_benchmark(
    *,
    mode: str,
    instrumentation_path: Path,
    monolith_path: Path,
    output_dir: Path,
    revision_steps: int | None,
    bootstrap_resamples: int | None,
    progress: bool,
) -> dict[str, Any]:
    if mode not in {"quick", "full"}:
        raise ValueError(mode)
    instrumentation_path = instrumentation_path.resolve()
    monolith_path = monolith_path.resolve()
    semantic_adapter_path = instrumentation_path.with_name(
        DEFAULT_SEMANTIC_ADAPTER.name
    ).resolve()
    v01_benchmark_path = V01_BENCHMARK_PATH.resolve()
    monolith_sha_before = v01._assert_monolith_sha(monolith_path)
    # Install the canonical module name before importing the instrumentation layer.
    base_module = _load_module(monolith_path, "ebrt_monolith_v0_1")
    instrumentation = _load_module(
        instrumentation_path, "instrumentation_ebrt_v0_2_benchmark"
    )
    adapter_module = _load_module(semantic_adapter_path, "semantic_adapter_v0_2")
    adapter_provenance = adapter_module.StructuredOracleAdapter().provenance.to_dict()
    cases = v01.build_correctness_cases()
    fixture_sha = hashlib.sha256(
        _canonical_json([case.to_dict() for case in cases]).encode("utf-8")
    ).hexdigest()
    model_seeds = tuple(range(4 if mode == "quick" else 32))
    resolved_steps = (
        revision_steps if revision_steps is not None else (8 if mode == "quick" else 32)
    )
    resolved_bootstrap = (
        bootstrap_resamples
        if bootstrap_resamples is not None
        else (500 if mode == "quick" else 2_000)
    )
    trial_rows, event_rows, candidate_rows = run_matrix(
        instrumentation,
        base_module,
        cases,
        model_seeds=model_seeds,
        revision_steps=resolved_steps,
        adapter_provenance=adapter_provenance,
        progress=progress,
    )
    summary = summarize_measurements(
        trial_rows,
        event_rows,
        candidate_rows,
        bootstrap_resamples=resolved_bootstrap,
    )
    results = {
        "schema_version": SCHEMA_VERSION,
        "status": "PASS",
        "mode": mode,
        "summary": summary,
        "observer_neutrality": {
            "core_unchanged_rate": _finite_mean(
                float(row["core_unchanged"]) for row in trial_rows
            ),
            "generator_accounting_pass_rate": _finite_mean(
                float(row["generator_accounting_ok"]) for row in trial_rows
            ),
            "finite_output_rate": _finite_mean(
                float(row["finite_outputs"]) for row in trial_rows
            ),
            "note": "Full output equivalence is exercised by --self-test; these are run-wide invariants.",
        },
        "claim_boundary": list(CLAIM_BOUNDARY),
    }
    manifest_base = _source_manifest(
        mode=mode,
        monolith_path=monolith_path,
        instrumentation_path=instrumentation_path,
        semantic_adapter_path=semantic_adapter_path,
        v01_benchmark_path=v01_benchmark_path,
        fixture_sha=fixture_sha,
        model_seeds=model_seeds,
        revision_steps=resolved_steps,
        bootstrap_resamples=resolved_bootstrap,
    )
    manifest_base["counts"] = summary["counts"]
    manifest = write_bundle(
        output_dir,
        trial_rows=trial_rows,
        event_rows=event_rows,
        candidate_rows=candidate_rows,
        results=results,
        manifest_base=manifest_base,
    )
    monolith_sha_after = v01._assert_monolith_sha(monolith_path)
    if monolith_sha_before != monolith_sha_after:
        raise AssertionError("frozen monolith changed during instrumentation benchmark")
    return {
        "status": "PASS",
        "mode": mode,
        "output_dir": str(output_dir.resolve()),
        "trial_count": len(trial_rows),
        "event_count": len(event_rows),
        "candidate_count": len(candidate_rows),
        "monolith_sha256": monolith_sha_after,
        "artifact_names": sorted(manifest["artifacts"]),
    }


def _assert_geometry_math() -> None:
    straight = torch.tensor([[0.0, 0.0], [1.0, 0.0], [2.0, 0.0]])
    straight_angles, straight_curvature = turn_angle_and_curvature(straight)
    if not math.isclose(float(straight_angles[0]), 0.0, abs_tol=1e-12):
        raise AssertionError("straight trajectory has non-zero turn angle")
    if not math.isclose(float(straight_curvature[0]), 0.0, abs_tol=1e-12):
        raise AssertionError("straight trajectory has non-zero curvature")

    corner = torch.tensor([[0.0, 0.0], [1.0, 0.0], [1.0, 1.0]])
    corner_angles, corner_curvature = turn_angle_and_curvature(corner)
    if not math.isclose(float(corner_angles[0]), math.pi / 2.0, rel_tol=1e-7):
        raise AssertionError("right-angle fixture failed")
    reversal = torch.tensor([[0.0, 0.0], [1.0, 0.0], [0.0, 0.0]])
    reversal_angles, _ = turn_angle_and_curvature(reversal)
    if not math.isclose(float(reversal_angles[0]), math.pi, rel_tol=1e-7):
        raise AssertionError("reversal fixture failed")
    duplicate = torch.tensor([[0.0, 0.0], [0.0, 0.0], [1.0, 0.0]])
    duplicate_angles, duplicate_curvature = turn_angle_and_curvature(duplicate)
    if duplicate_angles != [None] or duplicate_curvature != [None]:
        raise AssertionError("zero-speed turn must remain undefined")

    rotation = torch.tensor([[0.0, -1.0], [1.0, 0.0]])
    transformed = corner @ rotation.T + torch.tensor([4.0, -3.0])
    transformed_angles, transformed_curvature = turn_angle_and_curvature(transformed)
    if not math.isclose(
        float(corner_angles[0]), float(transformed_angles[0]), rel_tol=1e-7
    ):
        raise AssertionError("turn angle is not rotation/translation invariant")
    if not math.isclose(
        float(corner_curvature[0]), float(transformed_curvature[0]), rel_tol=1e-7
    ):
        raise AssertionError("curvature is not rotation/translation invariant")
    scaled_angles, scaled_curvature = turn_angle_and_curvature(corner * 3.0)
    if not math.isclose(float(corner_angles[0]), float(scaled_angles[0]), rel_tol=1e-7):
        raise AssertionError("turn angle changed under uniform scaling")
    if not math.isclose(
        float(corner_curvature[0]), float(scaled_curvature[0]) * 3.0, rel_tol=1e-7
    ):
        raise AssertionError("documented inverse-scale curvature behavior changed")

    geometry = summarize_mirror_geometry(corner, corner.clone())
    if geometry.separation_max != 0.0 or geometry.separation_auc != 0.0:
        raise AssertionError("identical mirror trajectories have non-zero separation")


def run_self_tests(
    instrumentation_path: Path = DEFAULT_INSTRUMENTATION,
    monolith_path: Path = DEFAULT_MONOLITH,
) -> dict[str, Any]:
    _assert_geometry_math()
    alignment = candidate_alignment_metrics(
        [
            {"candidate_step": 0, "semantic_attention": 0.2, "control_leverage": 0.1},
            {"candidate_step": 1, "semantic_attention": 0.8, "control_leverage": 0.9},
        ],
        [1],
    )
    if alignment["selected_is_max_leverage"] != 1:
        raise AssertionError("candidate alignment selected-max fixture failed")
    if not math.isclose(float(alignment["attention_leverage_spearman"]), 1.0):
        raise AssertionError("candidate alignment rank fixture failed")
    bootstrap_rows = [
        {"case_id": "a", "x": 1.0, "y": 1.0},
        {"case_id": "a", "x": 2.0, "y": 2.0},
        {"case_id": "b", "x": 3.0, "y": 3.0},
    ]
    first_bootstrap = case_cluster_bootstrap(
        bootstrap_rows,
        lambda rows: _field_correlation(rows, "x", "y"),
        seed=9,
        resamples=50,
    )
    second_bootstrap = case_cluster_bootstrap(
        bootstrap_rows,
        lambda rows: _field_correlation(rows, "x", "y"),
        seed=9,
        resamples=50,
    )
    if first_bootstrap != second_bootstrap:
        raise AssertionError("case-cluster bootstrap is not deterministic")

    instrumentation_path = instrumentation_path.resolve()
    monolith_path = monolith_path.resolve()
    semantic_adapter_path = instrumentation_path.with_name(
        DEFAULT_SEMANTIC_ADAPTER.name
    ).resolve()
    v01_benchmark_path = V01_BENCHMARK_PATH.resolve()
    monolith_sha_before = v01._assert_monolith_sha(monolith_path)
    instrumentation_sha_before = _sha256(instrumentation_path)
    semantic_adapter_sha_before = _sha256(semantic_adapter_path)
    v01_benchmark_sha_before = _sha256(v01_benchmark_path)
    base_module = _load_module(monolith_path, "ebrt_monolith_v0_1")
    instrumentation = _load_module(
        instrumentation_path, "instrumentation_ebrt_v0_2_benchmark"
    )
    instrumentation_report = instrumentation.run_self_tests()
    if instrumentation_report.get("status") != "PASS":
        raise AssertionError("instrumentation core self-test failed")
    adapter_module = _load_module(semantic_adapter_path, "semantic_adapter_v0_2")
    provenance = adapter_module.StructuredOracleAdapter().provenance.to_dict()
    cases = v01.build_correctness_cases()
    by_id = {case.case_id: case for case in cases}
    selected = [
        by_id["stable_00"],
        by_id["threshold_positive_00"],
        by_id["routing_contradiction_trap_00"],
        by_id["sequential_two_events"],
    ]
    trial_rows: list[dict[str, Any]] = []
    event_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []
    traces: dict[str, Mapping[str, Any]] = {}
    for case in selected:
        trial, events, candidates, result, trace = run_instrumented_case(
            instrumentation,
            base_module,
            case,
            model_seed=7,
            revision_steps=4,
            adapter_provenance=provenance,
            candidate_control_leverage=True,
        )
        trial_rows.append(trial)
        event_rows.extend(events)
        candidate_rows.extend(candidates)
        traces[case.case_id] = trace
        config = v01._build_config(
            base_module,
            case,
            model_seed=7,
            revision_steps=4,
            device="cpu",
            dtype="float32",
        )
        observations = v01._to_observations(base_module, case)
        plain = base_module.EventDrivenBackwardReasoner(config).run(observations)
        if not torch.equal(result.final_states, plain.final_states):
            raise AssertionError(
                f"instrumentation changed final states: {case.case_id}"
            )
        if not torch.equal(result.controls, plain.controls):
            raise AssertionError(f"instrumentation changed controls: {case.case_id}")
        if result.decoded != plain.decoded:
            raise AssertionError(f"instrumentation changed decode: {case.case_id}")
        if [
            v01._event_signature(event, include_targets=True) for event in result.events
        ] != [
            v01._event_signature(event, include_targets=True) for event in plain.events
        ]:
            raise AssertionError(f"instrumentation changed events: {case.case_id}")
        if (
            result.generator_step_calls,
            result.backward_calls,
            result.decode_call_count,
            result.core_hash_after,
        ) != (
            plain.generator_step_calls,
            plain.backward_calls,
            plain.decode_call_count,
            plain.core_hash_after,
        ):
            raise AssertionError(
                f"instrumentation changed execution counters: {case.case_id}"
            )
        if trace["candidate_control_leverage"]["execution_counter_neutral"] is not True:
            raise AssertionError("candidate probe was not execution-counter neutral")

    if traces["stable_00"]["revision_mirrors"]:
        raise AssertionError("stable trace unexpectedly contains a revision mirror")
    for case in selected[1:]:
        trace = traces[case.case_id]
        if len(trace["revision_mirrors"]) != len(
            [row for row in event_rows if row["case_id"] == case.case_id]
        ):
            raise AssertionError(f"mirror/event row count mismatch: {case.case_id}")
    if not candidate_rows:
        raise AssertionError("candidate leverage self-test produced no candidates")
    if any(row["control_leverage"] is None for row in candidate_rows):
        raise AssertionError("candidate leverage field is missing")

    boundary_case = by_id["weak_initial_anchor_promotion"]
    boundary_trace = run_instrumented_case(
        instrumentation,
        base_module,
        boundary_case,
        model_seed=2,
        revision_steps=32,
        adapter_provenance=provenance,
        candidate_control_leverage=True,
    )[4]
    raw_boundary_rows = boundary_trace["candidate_control_leverage"]["candidates"]
    limited_rows = [row for row in raw_boundary_rows if row["boundary_limited"]]
    if not limited_rows:
        raise AssertionError("real boundary regression did not limit any probe")
    if any(
        row["finite_difference_scheme"] != "projected_forward_one_sided"
        for row in limited_rows
    ):
        raise AssertionError("real boundary regression used an unsafe probe scheme")
    boundary_config = v01._build_config(
        base_module,
        boundary_case,
        model_seed=2,
        revision_steps=32,
        device="cpu",
        dtype="float32",
    )
    if any(
        float(row["probe_control_norm_max"])
        > float(boundary_config.max_control_norm) + 1e-5
        for row in raw_boundary_rows
    ):
        raise AssertionError("real boundary regression exceeded the control bound")

    repeated = run_instrumented_case(
        instrumentation,
        base_module,
        by_id["routing_contradiction_trap_00"],
        model_seed=7,
        revision_steps=4,
        adapter_provenance=provenance,
        candidate_control_leverage=True,
    )[4]
    if (
        repeated["trace_fingerprint"]
        != traces["routing_contradiction_trap_00"]["trace_fingerprint"]
    ):
        raise AssertionError("instrumentation trace fingerprint is not deterministic")

    summary = summarize_measurements(
        trial_rows, event_rows, candidate_rows, bootstrap_resamples=50
    )
    results = {
        "schema_version": SCHEMA_VERSION,
        "status": "PASS",
        "mode": "self-test",
        "summary": summary,
        "claim_boundary": list(CLAIM_BOUNDARY),
    }
    fixture_sha = hashlib.sha256(
        _canonical_json([case.to_dict() for case in cases]).encode("utf-8")
    ).hexdigest()
    manifest_base = _source_manifest(
        mode="self-test",
        monolith_path=monolith_path,
        instrumentation_path=instrumentation_path,
        semantic_adapter_path=semantic_adapter_path,
        v01_benchmark_path=v01_benchmark_path,
        fixture_sha=fixture_sha,
        model_seeds=(7,),
        revision_steps=4,
        bootstrap_resamples=50,
    )
    with tempfile.TemporaryDirectory(prefix="ebrt-v02-benchmark-self-test-") as temp:
        first_dir = Path(temp) / "first"
        second_dir = Path(temp) / "second"
        write_bundle(
            first_dir,
            trial_rows=trial_rows,
            event_rows=event_rows,
            candidate_rows=candidate_rows,
            results=results,
            manifest_base=manifest_base,
        )
        write_bundle(
            second_dir,
            trial_rows=trial_rows,
            event_rows=event_rows,
            candidate_rows=candidate_rows,
            results=results,
            manifest_base=manifest_base,
        )
        names = (
            "trials.csv",
            "events.csv",
            "candidates.csv",
            "results.json",
            "benchmark_report.md",
            "manifest.json",
        )
        for name in names:
            if (first_dir / name).read_bytes() != (second_dir / name).read_bytes():
                raise AssertionError(f"bundle artifact is not deterministic: {name}")

    monolith_sha_after = v01._assert_monolith_sha(monolith_path)
    instrumentation_sha_after = _sha256(instrumentation_path)
    semantic_adapter_sha_after = _sha256(semantic_adapter_path)
    v01_benchmark_sha_after = _sha256(v01_benchmark_path)
    if monolith_sha_before != monolith_sha_after:
        raise AssertionError("monolith changed during v0.2 benchmark self-test")
    if instrumentation_sha_before != instrumentation_sha_after:
        raise AssertionError(
            "instrumentation source changed during benchmark self-test"
        )
    if semantic_adapter_sha_before != semantic_adapter_sha_after:
        raise AssertionError("semantic adapter changed during benchmark self-test")
    if v01_benchmark_sha_before != v01_benchmark_sha_after:
        raise AssertionError("v0.1 benchmark changed during v0.2 self-test")
    return {
        "status": "PASS",
        "schema_version": SCHEMA_VERSION,
        "correctness_case_count": len(cases),
        "selected_case_count": len(selected),
        "trial_count": len(trial_rows),
        "event_count": len(event_rows),
        "candidate_count": len(candidate_rows),
        "boundary_regression_case": boundary_case.case_id,
        "boundary_limited_candidate_count": len(limited_rows),
        "monolith_sha256": monolith_sha_after,
        "instrumentation_sha256": instrumentation_sha_after,
        "semantic_adapter_sha256": semantic_adapter_sha_after,
        "v01_benchmark_sha256": v01_benchmark_sha_after,
        "checks": [
            "geometry straight/turn/reversal/zero-speed fixtures",
            "translation and orthogonal-rotation invariance",
            "documented uniform-scale behavior",
            "candidate attention/leverage rank diagnostics",
            "deterministic case-cluster bootstrap",
            "instrumentation observer neutrality against frozen v0.1",
            "event-local mirrors and candidate leverage rows",
            "real boundary leverage probes stay in the frozen control ball",
            "diagnostic execution-counter neutrality",
            "deterministic trace fingerprint and artifact bundle",
            "frozen source SHA guards before and after",
        ],
        "claim_boundary": list(CLAIM_BOUNDARY),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evidence benchmark for EBRT v0.2 counterfactual instrumentation."
    )
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--self-test", action="store_true")
    modes.add_argument("--quick", action="store_true")
    modes.add_argument("--full", action="store_true")
    parser.add_argument("--instrumentation", type=Path, default=DEFAULT_INSTRUMENTATION)
    parser.add_argument("--monolith", type=Path, default=DEFAULT_MONOLITH)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--revision-steps", type=int)
    parser.add_argument("--bootstrap-resamples", type=int)
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--no-progress", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.threads < 1:
        raise SystemExit("--threads must be >= 1")
    torch.set_num_threads(args.threads)
    try:
        torch.set_num_interop_threads(args.threads)
    except RuntimeError:
        pass
    if args.self_test:
        report = run_self_tests(args.instrumentation, args.monolith)
    else:
        mode = "quick" if args.quick else "full"
        output_dir = args.output_dir or (DEFAULT_OUTPUT_DIR / mode)
        report = run_benchmark(
            mode=mode,
            instrumentation_path=args.instrumentation,
            monolith_path=args.monolith,
            output_dir=output_dir,
            revision_steps=args.revision_steps,
            bootstrap_resamples=args.bootstrap_resamples,
            progress=not args.no_progress,
        )
    print(
        json.dumps(
            report, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
