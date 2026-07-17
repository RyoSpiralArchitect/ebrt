#!/usr/bin/env python3
"""Render an EBRT v0.2 instrumentation trace as one self-contained HTML figure.

The renderer is intentionally a research instrument, not a product interface.
It uses only the Python standard library, performs no network access, and does
not invent missing experimental evidence. Basic speed, turn angle, and
normalized acceleration may be derived from supplied state vectors when the
trace does not already contain those series; missing semantic or leverage
scores remain visibly missing.

Examples:

    python3 render_instrumentation_v0_2.py trace.json --output-html trace.html
    python3 render_instrumentation_v0_2.py --input-json trace.json \
        --output-html trace.html --title "EBRT counterfactual inspection"
    python3 render_instrumentation_v0_2.py --self-test
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


RENDERER_VERSION = "ebrt-instrument-renderer-v0.2"
DEFAULT_TITLE = "EBRT v0.2 counterfactual instrumentation"

COLOR = {
    "ink": "#17202a",
    "muted": "#61707d",
    "grid": "#dfe6eb",
    "baseline": "#4169a1",
    "final": "#d65a4a",
    "delta": "#7d4caf",
    "speed": "#16857a",
    "angle": "#c47b1a",
    "acceleration": "#9b4d83",
    "event": "#b23a48",
    "target": "#177245",
    "candidate": "#4775c1",
    "selected": "#e07a1f",
    "surface": "#ffffff",
    "wash": "#f5f7f8",
}


def _validate_json_value(value: Any, path: str = "$") -> None:
    if value is None or isinstance(value, (str, int, bool)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"non-finite JSON number at {path}")
        return
    if isinstance(value, Mapping):
        for key, child in value.items():
            if not isinstance(key, str):
                raise TypeError(f"JSON object key at {path} is not a string: {key!r}")
            _validate_json_value(child, f"{path}.{key}")
        return
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, child in enumerate(value):
            _validate_json_value(child, f"{path}[{index}]")
        return
    raise TypeError(f"unsupported JSON value at {path}: {type(value).__name__}")


def _canonical_json(value: Any, *, pretty: bool = False) -> str:
    _validate_json_value(value)
    if pretty:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _embedded_json(value: Any) -> str:
    # A script element is terminated by HTML parsing before JavaScript or JSON
    # parsing. Escaping these characters prevents user text from closing it.
    return (
        _canonical_json(value)
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
    )


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _as_sequence(value: Any) -> Sequence[Any]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return value
    return ()


def _path_get(root: Any, path: str) -> Any:
    current = root
    for component in path.split("."):
        if not isinstance(current, Mapping) or component not in current:
            return None
        current = current[component]
    return current


def _first(root: Any, *paths: str, default: Any = None) -> Any:
    for path in paths:
        value = _path_get(root, path)
        if value is not None:
            return value
    return default


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _integer(value: Any) -> int | None:
    number = _number(value)
    if number is None:
        return None
    return int(number)


def _format_number(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "yes" if value else "no"
    number = _number(value)
    if number is not None:
        if number == int(number) and abs(number) < 1e12:
            return str(int(number))
        return f"{number:.5g}"
    if isinstance(value, str):
        return value
    return _canonical_json(value)


def _vector(value: Any) -> list[float] | None:
    sequence = _as_sequence(value)
    if not sequence:
        return None
    result: list[float] = []
    for item in sequence:
        number = _number(item)
        if number is None:
            return None
        result.append(number)
    return result


def _state_vectors(value: Any) -> list[list[float]]:
    if isinstance(value, Mapping):
        nested = _first(
            value,
            "states",
            "vectors",
            "values",
            "data",
            "trajectory",
        )
        if nested is not None and nested is not value:
            return _state_vectors(nested)
        return []
    vectors: list[list[float]] = []
    for item in _as_sequence(value):
        candidate = item
        if isinstance(item, Mapping):
            candidate = _first(
                item,
                "state",
                "vector",
                "values",
                "coordinates",
            )
        vector = _vector(candidate)
        if vector is not None:
            vectors.append(vector)
            continue
        scalar = _number(candidate)
        if scalar is not None:
            vectors.append([scalar])
    return vectors


def _numeric_series(value: Any) -> list[float | None]:
    if isinstance(value, Mapping):
        nested = _first(value, "values", "data", "series", "value")
        if nested is not None and nested is not value:
            return _numeric_series(nested)
        return []
    result: list[float | None] = []
    for item in _as_sequence(value):
        if isinstance(item, Mapping):
            item = _first(item, "value", "score", "magnitude")
        result.append(_number(item))
    return result


def _records(value: Any, *container_keys: str) -> list[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        for key in container_keys:
            if key in value:
                return _records(value[key], *container_keys)
        if any(key in value for key in ("source_step", "event_index", "target_steps")):
            return [value]
        mapped = [child for child in value.values() if isinstance(child, Mapping)]
        if mapped and len(mapped) == len(value):
            return sorted(
                mapped,
                key=lambda item: (
                    _integer(item.get("source_step"))
                    if _integer(item.get("source_step")) is not None
                    else 10**12,
                    _integer(item.get("event_index"))
                    if _integer(item.get("event_index")) is not None
                    else 10**12,
                ),
            )
        return []
    return [item for item in _as_sequence(value) if isinstance(item, Mapping)]


def _norm(vector: Sequence[float]) -> float:
    return math.sqrt(sum(float(value) ** 2 for value in vector))


def _difference_norm(left: Sequence[float], right: Sequence[float]) -> float | None:
    if len(left) != len(right):
        return None
    return _norm([float(a) - float(b) for a, b in zip(left, right)])


def _state_norms(states: Sequence[Sequence[float]]) -> list[float]:
    return [_norm(state) for state in states]


def _speed(states: Sequence[Sequence[float]]) -> list[float | None]:
    if not states:
        return []
    result: list[float | None] = [0.0]
    for prior, current in zip(states, states[1:]):
        result.append(_difference_norm(current, prior))
    return result


def _velocities(states: Sequence[Sequence[float]]) -> list[list[float] | None]:
    result: list[list[float] | None] = [None]
    for prior, current in zip(states, states[1:]):
        if len(prior) != len(current):
            result.append(None)
        else:
            result.append([float(b) - float(a) for a, b in zip(prior, current)])
    return result


def _turn_angle(states: Sequence[Sequence[float]]) -> list[float | None]:
    velocities = _velocities(states)
    result: list[float | None] = [None] * len(velocities)
    for index in range(2, len(velocities)):
        prior = velocities[index - 1]
        current = velocities[index]
        if prior is None or current is None:
            continue
        denominator = _norm(prior) * _norm(current)
        if denominator <= 1e-12:
            continue
        cosine = sum(a * b for a, b in zip(prior, current)) / denominator
        result[index] = math.acos(max(-1.0, min(1.0, cosine)))
    return result


def _normalized_acceleration(
    states: Sequence[Sequence[float]],
) -> list[float | None]:
    velocities = _velocities(states)
    result: list[float | None] = [None] * len(velocities)
    for index in range(2, len(velocities)):
        prior = velocities[index - 1]
        current = velocities[index]
        if prior is None or current is None or len(prior) != len(current):
            continue
        acceleration = _norm([b - a for a, b in zip(prior, current)])
        result[index] = acceleration / max(_norm(prior), 1e-12)
    return result


@dataclass(frozen=True)
class PlotSeries:
    name: str
    values: tuple[float | None, ...]
    color: str
    x_start: int = 0
    dashed: bool = False


@dataclass(frozen=True)
class PlotMarker:
    step: int
    label: str
    color: str


class TraceAdapter:
    """Small compatibility layer while the v0.2 trace schema is settling."""

    def __init__(self, trace: Mapping[str, Any]) -> None:
        self.trace = trace

    def geometry(self, kind: str) -> Mapping[str, Any]:
        aliases = {
            "baseline": (
                "baseline_geometry",
                "geometry.baseline",
                "instrumentation.baseline_geometry",
            ),
            "final": (
                "final_geometry",
                "geometry.final",
                "instrumentation.final_geometry",
            ),
            "delta": (
                "delta_geometry",
                "geometry.delta",
                "instrumentation.delta_geometry",
            ),
        }
        return _as_mapping(_first(self.trace, *aliases[kind], default={}))

    def states(self, kind: str) -> list[list[float]]:
        geometry = self.geometry(kind)
        direct = _first(geometry, "states", "full.states", "state_vectors")
        if direct is None:
            direct = _first(
                self.trace,
                f"{kind}_states",
                f"instrumentation.{kind}_states",
            )
        return _state_vectors(direct)

    def metric(self, kind: str, name: str) -> tuple[list[float | None], str]:
        geometry = self.geometry(kind)
        aliases = {
            "speed": ("speed", "velocity_norm"),
            "turn_angle": ("turn_angle", "turn_angles"),
            "normalized_acceleration": (
                "normalized_acceleration",
                "normalized_accelerations",
            ),
        }[name]
        paths: list[str] = []
        for alias in aliases:
            paths.extend((f"full.{alias}", alias))
        supplied = _first(geometry, *paths)
        values = _numeric_series(supplied)
        if values:
            return values, "trace"
        states = self.states(kind)
        derived = {
            "speed": _speed,
            "turn_angle": _turn_angle,
            "normalized_acceleration": _normalized_acceleration,
        }[name](states)
        return derived, "derived from supplied states"

    def observations(self) -> list[Any]:
        return list(
            _as_sequence(
                _first(
                    self.trace,
                    "observations",
                    "session.observations",
                    "instrumentation.observations",
                    default=[],
                )
            )
        )

    def events(self) -> list[Mapping[str, Any]]:
        raw = _first(
            self.trace,
            "event_candidates",
            "events",
            "instrumentation.event_candidates",
            default=[],
        )
        return _records(raw, "event_candidates", "events", "items", "records")

    def mirrors(self) -> list[Mapping[str, Any]]:
        raw = _first(
            self.trace,
            "revision_mirrors",
            "revisions",
            "instrumentation.revision_mirrors",
            default=[],
        )
        return _records(raw, "revision_mirrors", "revisions", "items", "records")

    def leverage_container(self) -> Any:
        return _first(
            self.trace,
            "candidate_control_leverage",
            "metrics.candidate_control_leverage",
            "instrumentation.candidate_control_leverage",
            default={},
        )


def _event_source(event: Mapping[str, Any]) -> int | None:
    return _integer(_first(event, "source_step", "event.source_step", "source", "step"))


def _joined_source(event: Mapping[str, Any], mirror: Mapping[str, Any]) -> int | None:
    source = _event_source(event)
    return _event_source(mirror) if source is None else source


def _event_index(event: Mapping[str, Any], fallback: int) -> int:
    value = _integer(_first(event, "event_index", "index"))
    return fallback if value is None else value


def _event_detected(event: Mapping[str, Any]) -> bool:
    if "detected" in event:
        return bool(event["detected"])
    status = str(_first(event, "status", "event_status", default="")).lower()
    return status not in {"none", "no_event", "not_detected", "negative"}


def _join_events_and_mirrors(
    adapter: TraceAdapter,
) -> list[tuple[int, Mapping[str, Any], Mapping[str, Any]]]:
    events = list(adapter.events())
    mirrors = list(adapter.mirrors())
    mirror_by_source: dict[int, Mapping[str, Any]] = {}
    mirror_by_index: dict[int, Mapping[str, Any]] = {}
    for index, mirror in enumerate(mirrors):
        source = _event_source(mirror)
        if source is not None:
            mirror_by_source[source] = mirror
        mirror_by_index[_event_index(mirror, index)] = mirror

    joined: list[tuple[int, Mapping[str, Any], Mapping[str, Any]]] = []
    used_mirror_ids: set[int] = set()
    for fallback, event in enumerate(events):
        index = _event_index(event, fallback)
        source = _event_source(event)
        mirror = (
            mirror_by_source.get(source)
            if source is not None
            else mirror_by_index.get(index)
        )
        if mirror is None and source is None:
            mirror = mirror_by_index.get(index, {})
        elif mirror is None:
            mirror = {}
        if mirror:
            used_mirror_ids.add(id(mirror))
        joined.append((index, event, mirror))
    for fallback, mirror in enumerate(mirrors):
        if id(mirror) in used_mirror_ids:
            continue
        index = _event_index(mirror, len(events) + fallback)
        joined.append((index, {}, mirror))
    return sorted(
        joined,
        key=lambda item: (
            _event_source(item[1])
            if _event_source(item[1]) is not None
            else (
                _event_source(item[2]) if _event_source(item[2]) is not None else 10**12
            ),
            item[0],
        ),
    )


def _global_markers(adapter: TraceAdapter) -> list[PlotMarker]:
    steps: list[int] = []
    for _, event, mirror in _join_events_and_mirrors(adapter):
        source = _joined_source(event, mirror)
        if source is None:
            continue
        if event and not _event_detected(event) and not mirror:
            continue
        if source not in steps:
            steps.append(source)
    return [
        PlotMarker(step=step, label=f"E{index + 1}", color=COLOR["event"])
        for index, step in enumerate(sorted(steps))
    ]


def _series_points(series: PlotSeries) -> list[tuple[float, float]]:
    return [
        (float(series.x_start + index), float(value))
        for index, value in enumerate(series.values)
        if value is not None and math.isfinite(float(value))
    ]


def _line_chart(
    *,
    title: str,
    series: Sequence[PlotSeries],
    markers: Sequence[PlotMarker] = (),
    width: int = 920,
    height: int = 292,
    y_label: str = "value",
) -> str:
    available = [(item, _series_points(item)) for item in series]
    available = [(item, points) for item, points in available if points]
    if not available:
        return (
            '<div class="empty-panel">'
            f"<strong>{html.escape(title)}</strong><br>"
            "No compatible numeric series was supplied."
            "</div>"
        )
    all_points = [point for _, points in available for point in points]
    xs = [point[0] for point in all_points]
    ys = [point[1] for point in all_points]
    x_min = min(xs + [float(marker.step) for marker in markers] or xs)
    x_max = max(xs + [float(marker.step) for marker in markers] or xs)
    if x_max == x_min:
        x_max = x_min + 1.0
    y_min = min(ys)
    y_max = max(ys)
    if y_min == y_max:
        padding = max(abs(y_min) * 0.1, 1.0)
    else:
        padding = (y_max - y_min) * 0.08
    y_min -= padding
    y_max += padding
    left, right, top, bottom = 72.0, 24.0, 42.0, 48.0
    plot_width = width - left - right
    plot_height = height - top - bottom

    def sx(value: float) -> float:
        return left + (value - x_min) / (x_max - x_min) * plot_width

    def sy(value: float) -> float:
        return top + (y_max - value) / (y_max - y_min) * plot_height

    pieces = [
        f'<svg class="chart" viewBox="0 0 {width} {height}" '
        f'role="img" aria-label="{html.escape(title)}">',
        f"<title>{html.escape(title)}</title>",
        f'<rect x="0" y="0" width="{width}" height="{height}" rx="8" '
        f'fill="{COLOR["surface"]}"/>',
        f'<text x="{left:.1f}" y="24" class="chart-title">{html.escape(title)}</text>',
    ]
    for index in range(5):
        fraction = index / 4
        value = y_max - fraction * (y_max - y_min)
        y = top + fraction * plot_height
        pieces.extend(
            [
                f'<line x1="{left:.1f}" x2="{left + plot_width:.1f}" '
                f'y1="{y:.2f}" y2="{y:.2f}" stroke="{COLOR["grid"]}"/>',
                f'<text x="{left - 8:.1f}" y="{y + 4:.2f}" '
                f'class="axis-label" text-anchor="end">{value:.3g}</text>',
            ]
        )
    for index in range(5):
        fraction = index / 4
        value = x_min + fraction * (x_max - x_min)
        x = left + fraction * plot_width
        pieces.extend(
            [
                f'<line x1="{x:.2f}" x2="{x:.2f}" y1="{top:.1f}" '
                f'y2="{top + plot_height:.1f}" stroke="{COLOR["grid"]}"/>',
                f'<text x="{x:.2f}" y="{top + plot_height + 22:.1f}" '
                f'class="axis-label" text-anchor="middle">{value:.3g}</text>',
            ]
        )
    for marker in markers:
        if not x_min <= marker.step <= x_max:
            continue
        x = sx(float(marker.step))
        pieces.extend(
            [
                f'<line x1="{x:.2f}" x2="{x:.2f}" y1="{top:.1f}" '
                f'y2="{top + plot_height:.1f}" stroke="{marker.color}" '
                'stroke-width="1.5" stroke-dasharray="5 4"/>',
                f'<text x="{x + 4:.2f}" y="{top + 12:.1f}" '
                f'fill="{marker.color}" class="marker-label">'
                f"{html.escape(marker.label)}</text>",
            ]
        )
    for item, points in available:
        coordinates = " ".join(f"{sx(x):.2f},{sy(y):.2f}" for x, y in points)
        dash = ' stroke-dasharray="7 5"' if item.dashed else ""
        pieces.append(
            f'<polyline points="{coordinates}" fill="none" '
            f'stroke="{item.color}" stroke-width="2.3" '
            f'stroke-linejoin="round" stroke-linecap="round"{dash}/>'
        )
    legend_x = left
    for item, _ in available:
        pieces.extend(
            [
                f'<line x1="{legend_x:.1f}" x2="{legend_x + 22:.1f}" '
                f'y1="{height - 12:.1f}" y2="{height - 12:.1f}" '
                f'stroke="{item.color}" stroke-width="3"/>',
                f'<text x="{legend_x + 28:.1f}" y="{height - 8:.1f}" '
                f'class="legend-label">{html.escape(item.name)}</text>',
            ]
        )
        legend_x += 34 + 7.1 * len(item.name)
    pieces.extend(
        [
            f'<text x="16" y="{top + plot_height / 2:.1f}" '
            'class="axis-label" text-anchor="middle" '
            f'transform="rotate(-90 16 {top + plot_height / 2:.1f})">'
            f"{html.escape(y_label)}</text>",
            f'<text x="{left + plot_width / 2:.1f}" y="{height - 8:.1f}" '
            'class="axis-label" text-anchor="middle">step</text>',
            "</svg>",
        ]
    )
    return "".join(pieces)


def _global_separation(adapter: TraceAdapter) -> tuple[str, dict[str, Any]]:
    baseline = adapter.states("baseline")
    final = adapter.states("final")
    delta = adapter.states("delta")
    separations: list[float | None] = []
    for index in range(max(len(baseline), len(final), len(delta))):
        if index < len(baseline) and index < len(final):
            separations.append(_difference_norm(baseline[index], final[index]))
        elif index < len(delta):
            separations.append(_norm(delta[index]))
        else:
            separations.append(None)
    chart = _line_chart(
        title="Global baseline/final mirror separation",
        series=(
            PlotSeries(
                "baseline state norm",
                tuple(_state_norms(baseline)),
                COLOR["baseline"],
            ),
            PlotSeries(
                "final state norm",
                tuple(_state_norms(final)),
                COLOR["final"],
            ),
            PlotSeries("mirror separation ‖Δh‖", tuple(separations), COLOR["delta"]),
        ),
        markers=_global_markers(adapter),
        y_label="state norm / separation",
    )
    finite = [value for value in separations if value is not None]
    summary = {
        "step_count": max(len(baseline), len(final)),
        "max_separation": max(finite) if finite else None,
        "terminal_separation": finite[-1] if finite else None,
    }
    return chart, summary


def _kinematic_charts(adapter: TraceAdapter) -> str:
    markers = _global_markers(adapter)
    baseline_speed, baseline_speed_source = adapter.metric("baseline", "speed")
    final_speed, final_speed_source = adapter.metric("final", "speed")
    speed_chart = _line_chart(
        title="Trajectory speed",
        series=(
            PlotSeries("baseline speed", tuple(baseline_speed), COLOR["baseline"]),
            PlotSeries("final speed", tuple(final_speed), COLOR["final"]),
        ),
        markers=markers,
        width=452,
        height=278,
        y_label="speed",
    )
    baseline_turn, baseline_turn_source = adapter.metric("baseline", "turn_angle")
    final_turn, final_turn_source = adapter.metric("final", "turn_angle")
    metric_name = "turn angle"
    source_note = f"baseline: {baseline_turn_source}; final: {final_turn_source}"
    secondary_series = (
        PlotSeries("baseline turn", tuple(baseline_turn), COLOR["baseline"]),
        PlotSeries("final turn", tuple(final_turn), COLOR["final"]),
    )
    if not any(value is not None for value in [*baseline_turn, *final_turn]):
        baseline_turn, baseline_acc_source = adapter.metric(
            "baseline", "normalized_acceleration"
        )
        final_turn, final_acc_source = adapter.metric(
            "final", "normalized_acceleration"
        )
        metric_name = "normalized acceleration"
        source_note = f"baseline: {baseline_acc_source}; final: {final_acc_source}"
        secondary_series = (
            PlotSeries(
                "baseline norm. accel.", tuple(baseline_turn), COLOR["baseline"]
            ),
            PlotSeries("final norm. accel.", tuple(final_turn), COLOR["final"]),
        )
    secondary_chart = _line_chart(
        title=metric_name.capitalize(),
        series=secondary_series,
        markers=markers,
        width=452,
        height=278,
        y_label=metric_name,
    )
    return (
        '<div class="chart-grid">'
        f'<div>{speed_chart}<p class="source-note">baseline: '
        f"{html.escape(baseline_speed_source)}; final: "
        f"{html.escape(final_speed_source)}</p></div>"
        f'<div>{secondary_chart}<p class="source-note">'
        f"{html.escape(source_note)}</p></div>"
        "</div>"
    )


def _candidate_records(event: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    raw = _first(
        event,
        "candidates",
        "route_candidates",
        "routing.candidates",
        default=[],
    )
    return _records(raw, "candidates", "route_candidates", "items", "records")


def _candidate_step(candidate: Mapping[str, Any], fallback: int) -> int:
    value = _integer(_first(candidate, "step", "target_step", "prior_step", "index"))
    return fallback if value is None else value


def _semantic_score(candidate: Mapping[str, Any]) -> tuple[float | None, str]:
    for key in (
        "semantic_score",
        "semantic_anchor_score",
        "combined_semantic_score",
        "logit",
        "attention",
    ):
        value = _number(candidate.get(key))
        if value is not None:
            return value, key
    return None, "unavailable"


def _extract_leverage_by_step(value: Any) -> dict[int, float]:
    result: dict[int, float] = {}
    if isinstance(value, Mapping):
        nested = _first(
            value,
            "candidates",
            "candidate_control_leverage",
            "values",
            "records",
            "items",
        )
        if nested is not None and nested is not value:
            result.update(_extract_leverage_by_step(nested))
        for key, child in value.items():
            try:
                step = int(key)
            except (TypeError, ValueError):
                step = None
            if step is not None:
                if isinstance(child, Mapping):
                    leverage = _number(
                        _first(
                            child,
                            "control_leverage",
                            "leverage",
                            "source_gain",
                            "terminal_gain",
                            "score",
                        )
                    )
                else:
                    leverage = _number(child)
                if leverage is not None:
                    result[step] = leverage
        step = _integer(
            _first(value, "step", "target_step", "prior_step", "candidate_step")
        )
        leverage = _number(
            _first(
                value,
                "control_leverage",
                "leverage",
                "source_gain",
                "terminal_gain",
            )
        )
        if step is not None and leverage is not None:
            result[step] = leverage
        return result
    for item in _as_sequence(value):
        result.update(_extract_leverage_by_step(item))
    return result


def _event_leverage(
    adapter: TraceAdapter,
    event: Mapping[str, Any],
    event_index: int,
) -> dict[int, float]:
    result = _extract_leverage_by_step(event)
    container = adapter.leverage_container()
    source = _event_source(event)
    selected: Any = container
    if isinstance(container, Mapping):
        events = _first(container, "events", "records", "items", "candidates")
        if events is not None:
            selected = events
        else:
            for key in (
                str(source) if source is not None else "",
                str(event_index),
                f"event_{event_index}",
            ):
                if key and key in container:
                    selected = container[key]
                    break
    if isinstance(selected, Sequence) and not isinstance(
        selected, (str, bytes, bytearray)
    ):
        matching = []
        for item in selected:
            if not isinstance(item, Mapping):
                continue
            item_source = _event_source(item)
            item_index = _integer(_first(item, "event_index", "index"))
            if (
                source is not None and item_source == source
            ) or item_index == event_index:
                matching.append(item)
        if matching:
            # The settled schema stores one row per source/candidate pair, so
            # retain every matching row rather than selecting only the first.
            selected = matching
        elif source is not None:
            # Do not combine leverage rows from different events merely because
            # they reuse the same candidate step number.
            selected = []
    result.update(_extract_leverage_by_step(selected))
    return result


def _candidate_scatter(
    candidates: Sequence[Mapping[str, Any]],
    leverage: Mapping[int, float],
) -> tuple[str, list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    points: list[tuple[int, float, float, bool]] = []
    for fallback, candidate in enumerate(candidates):
        step = _candidate_step(candidate, fallback)
        semantic, semantic_field = _semantic_score(candidate)
        candidate_leverage = _number(_first(candidate, "control_leverage", "leverage"))
        if candidate_leverage is None:
            candidate_leverage = leverage.get(step)
        selected = bool(_first(candidate, "selected", "is_selected", default=False))
        row = {
            "step": step,
            "semantic": semantic,
            "semantic_field": semantic_field,
            "control_leverage": candidate_leverage,
            "topic_similarity": _number(candidate.get("topic_similarity")),
            "contradiction": _number(candidate.get("contradiction")),
            "recency": _number(candidate.get("recency")),
            "attention": _number(candidate.get("attention")),
            "selected": selected,
        }
        rows.append(row)
        if semantic is not None and candidate_leverage is not None:
            points.append((step, semantic, candidate_leverage, selected))
    if not points:
        return (
            '<div class="empty-panel compact"><strong>Semantic score × control leverage</strong><br>'
            "No candidate has both supplied values. The renderer does not infer "
            "control leverage from unrelated aggregate gains.</div>",
            rows,
        )
    width, height = 520, 286
    left, right, top, bottom = 66.0, 24.0, 38.0, 54.0
    plot_width = width - left - right
    plot_height = height - top - bottom
    xs = [point[1] for point in points]
    ys = [point[2] for point in points]

    def bounds(values: Sequence[float]) -> tuple[float, float]:
        low, high = min(values), max(values)
        if low == high:
            padding = max(abs(low) * 0.1, 0.5)
        else:
            padding = (high - low) * 0.1
        return low - padding, high + padding

    x_min, x_max = bounds(xs)
    y_min, y_max = bounds(ys)

    def sx(value: float) -> float:
        return left + (value - x_min) / (x_max - x_min) * plot_width

    def sy(value: float) -> float:
        return top + (y_max - value) / (y_max - y_min) * plot_height

    pieces = [
        f'<svg class="chart scatter" viewBox="0 0 {width} {height}" '
        'role="img" aria-label="Candidate semantic score versus control leverage">',
        "<title>Candidate semantic score versus control leverage</title>",
        f'<rect width="{width}" height="{height}" rx="8" fill="{COLOR["surface"]}"/>',
        f'<text x="{left}" y="23" class="chart-title">Semantic score × control leverage</text>',
    ]
    for index in range(5):
        fraction = index / 4
        x = left + fraction * plot_width
        y = top + fraction * plot_height
        x_value = x_min + fraction * (x_max - x_min)
        y_value = y_max - fraction * (y_max - y_min)
        pieces.extend(
            [
                f'<line x1="{x:.2f}" x2="{x:.2f}" y1="{top}" y2="{top + plot_height}" '
                f'stroke="{COLOR["grid"]}"/>',
                f'<line x1="{left}" x2="{left + plot_width}" y1="{y:.2f}" y2="{y:.2f}" '
                f'stroke="{COLOR["grid"]}"/>',
                f'<text x="{x:.2f}" y="{top + plot_height + 20}" class="axis-label" '
                f'text-anchor="middle">{x_value:.3g}</text>',
                f'<text x="{left - 8}" y="{y + 4:.2f}" class="axis-label" '
                f'text-anchor="end">{y_value:.3g}</text>',
            ]
        )
    for step, semantic, candidate_leverage, selected in points:
        color = COLOR["selected"] if selected else COLOR["candidate"]
        radius = 7 if selected else 5
        pieces.extend(
            [
                f'<circle cx="{sx(semantic):.2f}" cy="{sy(candidate_leverage):.2f}" '
                f'r="{radius}" fill="{color}" stroke="#ffffff" stroke-width="1.5"/>',
                f'<text x="{sx(semantic) + 8:.2f}" y="{sy(candidate_leverage) - 7:.2f}" '
                f'class="point-label">s{step}</text>',
            ]
        )
    pieces.extend(
        [
            f'<text x="{left + plot_width / 2}" y="{height - 9}" class="axis-label" '
            'text-anchor="middle">semantic candidate score</text>',
            f'<text x="15" y="{top + plot_height / 2}" class="axis-label" '
            f'text-anchor="middle" transform="rotate(-90 15 {top + plot_height / 2})">'
            "control leverage</text>",
            "</svg>",
        ]
    )
    return "".join(pieces), rows


def _candidate_table(rows: Sequence[Mapping[str, Any]]) -> str:
    if not rows:
        return '<p class="muted">No candidate records supplied.</p>'
    headers = (
        "step",
        "semantic",
        "semantic field",
        "control leverage",
        "topic similarity",
        "contradiction",
        "recency",
        "attention",
        "selected",
    )
    keys = (
        "step",
        "semantic",
        "semantic_field",
        "control_leverage",
        "topic_similarity",
        "contradiction",
        "recency",
        "attention",
        "selected",
    )
    body = []
    for row in rows:
        body.append(
            "<tr>"
            + "".join(
                f"<td>{html.escape(_format_number(row.get(key)))}</td>" for key in keys
            )
            + "</tr>"
        )
    return (
        '<div class="table-wrap"><table><thead><tr>'
        + "".join(f"<th>{html.escape(label)}</th>" for label in headers)
        + "</tr></thead><tbody>"
        + "".join(body)
        + "</tbody></table></div>"
    )


def _steps(value: Any) -> list[int]:
    result: list[int] = []
    if isinstance(value, Mapping):
        value = _first(value, "steps", "targets", "values", default=[])
    for item in _as_sequence(value):
        step = _integer(item)
        if step is not None:
            result.append(step)
    scalar = _integer(value)
    if scalar is not None:
        result.append(scalar)
    return result


def _event_status(event: Mapping[str, Any], mirror: Mapping[str, Any]) -> str:
    supplied = _first(event, "status", "event_status")
    if bool(_first(event, "suppressed", default=False)):
        return "suppressed"
    accepted = _first(mirror, "accepted", "revision.accepted")
    rolled_back = bool(
        _first(mirror, "rolled_back", "revision.rolled_back", default=False)
    )
    if accepted is True and rolled_back:
        prefix = str(supplied).replace("_", " ") if supplied else "accepted"
        if "accepted" not in prefix.lower():
            prefix += " · accepted"
        return prefix + " · rollback to best checkpoint"
    if accepted is True:
        prefix = str(supplied).replace("_", " ") if supplied else "accepted"
        return prefix if "accepted" in prefix.lower() else prefix + " · accepted"
    if accepted is False:
        prefix = str(supplied).replace("_", " ") if supplied else "rejected"
        return prefix if "rejected" in prefix.lower() else prefix + " · rejected"
    if supplied:
        return str(supplied).replace("_", " ")
    return "detected" if _event_detected(event) else "not detected"


def _local_mirror_chart(event: Mapping[str, Any], mirror: Mapping[str, Any]) -> str:
    before = _state_vectors(
        _first(
            mirror,
            "before_states",
            "mirror_states",
            "affected_states_before",
            "local.before_states",
        )
    )
    after = _state_vectors(
        _first(
            mirror,
            "after_states",
            "revised_states",
            "affected_states_after",
            "local.after_states",
        )
    )
    delta = _state_vectors(
        _first(
            mirror,
            "delta_states",
            "local_state_deltas",
            "local.delta_states",
        )
    )
    earliest = _integer(_first(mirror, "earliest_replay_step", "replay.earliest_step"))
    if earliest is None:
        earliest = 0
    separation: list[float | None] = []
    for index in range(max(len(before), len(after), len(delta))):
        if index < len(before) and index < len(after):
            separation.append(_difference_norm(before[index], after[index]))
        elif index < len(delta):
            separation.append(_norm(delta[index]))
        else:
            separation.append(None)
    targets = _steps(
        _first(mirror, "targets", "target_steps", "event.target_steps", default=[])
    )
    if not targets:
        targets = [
            _candidate_step(candidate, index)
            for index, candidate in enumerate(_candidate_records(event))
            if bool(_first(candidate, "selected", "is_selected", default=False))
        ]
    markers = [
        PlotMarker(step=target, label=f"target s{target}", color=COLOR["target"])
        for target in targets
    ]
    source = _joined_source(event, mirror)
    if source is not None:
        markers.append(
            PlotMarker(step=source, label=f"source s{source}", color=COLOR["event"])
        )
    series = [
        PlotSeries(
            "before state norm",
            tuple(_state_norms(before)),
            COLOR["baseline"],
            x_start=earliest,
        ),
        PlotSeries(
            "after state norm",
            tuple(_state_norms(after)),
            COLOR["final"],
            x_start=earliest,
        ),
        PlotSeries(
            "local separation ‖Δh‖",
            tuple(separation),
            COLOR["delta"],
            x_start=earliest,
        ),
    ]
    propagation = _numeric_series(
        _first(
            mirror,
            "propagation_separation",
            "terminal_diagnostics.separation_curve",
            default=[],
        )
    )
    if propagation:
        series.append(
            PlotSeries(
                "propagation ‖Δh‖ (later revisions suppressed)",
                tuple(propagation),
                COLOR["acceleration"],
                x_start=0,
            )
        )
    return _line_chart(
        title="Per-event local mirror separation",
        series=tuple(series),
        markers=markers,
        width=520,
        height=286,
        y_label="state norm / separation",
    )


def _detail(label: str, value: Any) -> str:
    return (
        "<div><dt>"
        + html.escape(label)
        + "</dt><dd>"
        + html.escape(_format_number(value))
        + "</dd></div>"
    )


def _event_details(event: Mapping[str, Any], mirror: Mapping[str, Any]) -> str:
    targets = _steps(_first(mirror, "targets", "target_steps", default=[]))
    if not targets:
        targets = [
            _candidate_step(candidate, index)
            for index, candidate in enumerate(_candidate_records(event))
            if bool(_first(candidate, "selected", "is_selected", default=False))
        ]
    energy = _first(mirror, "energy", "revision.energy", default={})
    energy_map = _as_mapping(energy)
    energy_before = _first(energy_map, "before", "energy_before")
    if energy_before is None:
        energy_before = _first(mirror, "energy_before", "revision.energy_before")
    energy_after = _first(energy_map, "after", "energy_after")
    if energy_after is None:
        energy_after = _first(mirror, "energy_after", "revision.energy_after")
    energy_drop = _number(_first(energy_map, "drop", "energy_drop"))
    if energy_drop is None:
        energy_drop = _number(_first(mirror, "energy_drop", "revision.energy_drop"))
    if energy_drop is None:
        before_number = _number(energy_before)
        after_number = _number(energy_after)
        if before_number is not None and after_number is not None:
            energy_drop = before_number - after_number
    details = [
        _detail("source step", _joined_source(event, mirror)),
        _detail("prior step", _first(event, "prior_step", "event.prior_step")),
        _detail("eligible steps", _steps(_first(event, "eligible_steps", default=[]))),
        _detail("selected targets", targets),
        _detail("event score", _first(event, "event_score", "score")),
        _detail(
            "earliest replay",
            _first(mirror, "earliest_replay_step", "replay.earliest_step"),
        ),
        _detail("local steps", _first(mirror, "local_steps", "replay.local_steps")),
        _detail(
            "replay span",
            _first(mirror, "replay_span_steps", "replay_span", "replay.span"),
        ),
        _detail(
            "replay distance", _first(mirror, "replay_distance", "replay.distance")
        ),
        _detail(
            "route distances",
            _first(mirror, "route_distances", "routing.route_distances"),
        ),
        _detail("accepted", _first(mirror, "accepted", "revision.accepted")),
        _detail("rolled back", _first(mirror, "rolled_back", "revision.rolled_back")),
        _detail(
            "accepted checkpoint",
            _first(mirror, "accepted_checkpoint", "revision.accepted_checkpoint"),
        ),
        _detail("energy before", energy_before),
        _detail("energy after", energy_after),
        _detail("energy drop", energy_drop),
        _detail(
            "control magnitude",
            _first(
                mirror,
                "control_magnitude",
                "magnitudes.control",
                "magnitudes.control_delta_l2",
                "magnitudes.control_delta_norm",
            ),
        ),
        _detail(
            "target state magnitude",
            _first(
                mirror,
                "state_magnitude",
                "target_state_delta_l2",
                "magnitudes.state",
                "magnitudes.state_delta_l2",
                "magnitudes.state_delta_max",
                "magnitudes.target_state_separation",
            ),
        ),
        _detail(
            "source magnitude",
            _first(
                mirror,
                "source_magnitude",
                "magnitudes.source",
                "magnitudes.source_state_delta_l2",
                "magnitudes.source_state_separation",
            ),
        ),
        _detail(
            "terminal magnitude",
            _first(
                mirror,
                "terminal_magnitude",
                "magnitudes.terminal",
                "magnitudes.terminal_state_delta_l2",
                "magnitudes.terminal_state_separation",
            ),
        ),
        _detail(
            "propagation survival",
            _first(
                mirror,
                "propagation_survival_ratio",
                "magnitudes.propagation_survival_ratio",
            ),
        ),
        _detail(
            "unrelated-state leakage",
            _first(
                mirror,
                "unrelated_state_leakage",
                "unrelated_state_leakage_max",
                "magnitudes.unrelated_state_leakage",
            ),
        ),
        _detail(
            "source target-projection gain",
            _first(mirror, "source_target_projection_gain"),
        ),
        _detail(
            "terminal target-projection gain",
            _first(mirror, "terminal_target_projection_gain"),
        ),
        _detail("decay distance", _first(mirror, "decay_distance")),
        _detail("backward calls", _first(mirror, "backward_calls")),
        _detail("replayed state steps", _first(mirror, "replayed_state_steps")),
    ]
    return '<dl class="detail-grid">' + "".join(details) + "</dl>"


def _render_event_sections(adapter: TraceAdapter) -> str:
    sections: list[str] = []
    for display_index, (index, event, mirror) in enumerate(
        _join_events_and_mirrors(adapter), start=1
    ):
        source = _joined_source(event, mirror)
        status = _event_status(event, mirror)
        candidates = _candidate_records(event)
        leverage = _event_leverage(adapter, event, index)
        scatter, rows = _candidate_scatter(candidates, leverage)
        local = _local_mirror_chart(event, mirror)
        event_payload = {"event_candidate": event, "revision_mirror": mirror}
        sections.append(
            '<section class="event-panel">'
            '<div class="event-heading">'
            f'<div><p class="eyebrow">event {display_index}</p>'
            f"<h3>Source step {html.escape(_format_number(source))}</h3></div>"
            f'<span class="status">{html.escape(status)}</span>'
            "</div>"
            '<div class="event-figures">'
            f"<div>{local}</div><div>{scatter}</div>"
            "</div>"
            f"{_event_details(event, mirror)}"
            "<h4>Candidate audit table</h4>"
            f"{_candidate_table(rows)}"
            "<details><summary>Event-level raw record</summary><pre>"
            f"{html.escape(_canonical_json(event_payload, pretty=True))}"
            "</pre></details>"
            "</section>"
        )
    if not sections:
        return (
            '<section class="event-panel"><h3>No event records</h3>'
            '<p class="muted">The global geometry remains inspectable, but the '
            "trace contains no event candidate or revision mirror records.</p></section>"
        )
    return "".join(sections)


def _metadata_table(trace: Mapping[str, Any]) -> str:
    fields = (
        ("schema", _first(trace, "schema_version", default="unversioned")),
        ("model", _first(trace, "model", default="not supplied")),
        ("model version", _first(trace, "model_version", default="not supplied")),
        ("monolith SHA-256", _first(trace, "monolith_sha256", default="not supplied")),
        (
            "source session fingerprint",
            _first(trace, "source_session_fingerprint", default="not supplied"),
        ),
        (
            "trace fingerprint",
            _first(trace, "trace_fingerprint", default="not supplied"),
        ),
    )
    return (
        '<dl class="metadata">'
        + "".join(_detail(label, value) for label, value in fields)
        + "</dl>"
    )


def _summary_cards(adapter: TraceAdapter, separation: Mapping[str, Any]) -> str:
    joined = _join_events_and_mirrors(adapter)
    accepted = sum(
        int(bool(_first(mirror, "accepted", "revision.accepted", default=False)))
        for _, _, mirror in joined
    )
    rollback = sum(
        int(bool(_first(mirror, "rolled_back", "revision.rolled_back", default=False)))
        for _, _, mirror in joined
    )
    cards = (
        ("trajectory steps", separation.get("step_count")),
        ("event records", len(joined)),
        ("accepted revisions", accepted),
        ("rollback-to-best flags", rollback),
        ("max global separation", separation.get("max_separation")),
        ("terminal separation", separation.get("terminal_separation")),
    )
    return (
        '<div class="summary-cards">'
        + "".join(
            '<div class="summary-card"><span>'
            + html.escape(label)
            + "</span><strong>"
            + html.escape(_format_number(value))
            + "</strong></div>"
            for label, value in cards
        )
        + "</div>"
    )


def _claim_boundary(trace: Mapping[str, Any]) -> str:
    claims = list(_as_sequence(_first(trace, "claim_boundary", default=[])))
    default_claim = (
        "This figure is a descriptive research instrument. It does not establish "
        "language-model reasoning improvement or hidden-state intervention in GPT."
    )
    if default_claim not in claims:
        claims.insert(0, default_claim)
    return (
        "<ul>"
        + "".join(f"<li>{html.escape(str(claim))}</li>" for claim in claims)
        + "</ul>"
    )


def _provenance(trace: Mapping[str, Any]) -> str:
    values = {
        "config": _first(trace, "config", default={}),
        "adapter_provenance": _first(trace, "adapter_provenance", default={}),
        "execution_metrics": _first(trace, "execution_metrics", "metrics", default={}),
        "explicit_metadata": _first(trace, "metadata", default={}),
    }
    return html.escape(_canonical_json(values, pretty=True))


def render_trace_html(
    trace: Mapping[str, Any],
    *,
    title: str = DEFAULT_TITLE,
) -> str:
    """Return deterministic standalone HTML for one JSON-compatible trace."""

    if not isinstance(trace, Mapping):
        raise TypeError("trace must be a JSON object")
    _validate_json_value(trace)
    adapter = TraceAdapter(trace)
    global_chart, separation = _global_separation(adapter)
    embedded = _embedded_json(trace)
    pretty = html.escape(_canonical_json(trace, pretty=True))
    safe_title = html.escape(title)
    observation_count = len(adapter.observations())
    stylesheet = f"""
    :root {{ color-scheme: light; --ink:{COLOR["ink"]}; --muted:{COLOR["muted"]};
      --wash:{COLOR["wash"]}; --surface:{COLOR["surface"]}; --grid:{COLOR["grid"]}; }}
    * {{ box-sizing: border-box; }}
    body {{ margin:0; background:#eef2f4; color:var(--ink); font-family:Inter,ui-sans-serif,
      system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; line-height:1.45; }}
    main {{ max-width:1120px; margin:0 auto; padding:40px 28px 72px; }}
    h1,h2,h3,h4,p {{ margin-top:0; }}
    h1 {{ font-size:clamp(2rem,5vw,3.35rem); max-width:860px; letter-spacing:-.045em;
      line-height:1.02; margin-bottom:16px; }}
    h2 {{ margin:44px 0 16px; font-size:1.45rem; }}
    h3 {{ margin-bottom:0; }} h4 {{ margin:24px 0 10px; }}
    .eyebrow {{ color:#475968; font-size:.72rem; text-transform:uppercase; letter-spacing:.14em;
      font-weight:750; margin-bottom:8px; }}
    .lede {{ max-width:850px; color:#42515c; font-size:1.03rem; }}
    .topline {{ display:flex; align-items:flex-start; justify-content:space-between; gap:24px; }}
    .download {{ appearance:none; border:1px solid #1e2a33; border-radius:6px; background:#1e2a33;
      color:#fff; padding:10px 13px; font:inherit; font-weight:650; cursor:pointer; white-space:nowrap; }}
    .metadata,.detail-grid {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:1px;
      padding:1px; background:var(--grid); border:1px solid var(--grid); border-radius:8px;
      overflow:hidden; }}
    .metadata > div,.detail-grid > div {{ background:var(--surface); padding:12px 14px; min-width:0; }}
    dt {{ color:var(--muted); font-size:.72rem; text-transform:uppercase; letter-spacing:.08em; }}
    dd {{ margin:4px 0 0; font-size:.88rem; overflow-wrap:anywhere; }}
    .summary-cards {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:10px; margin:22px 0; }}
    .summary-card {{ background:var(--surface); border:1px solid var(--grid); border-radius:8px;
      padding:14px; display:flex; flex-direction:column; gap:4px; }}
    .summary-card span {{ color:var(--muted); font-size:.75rem; text-transform:uppercase; letter-spacing:.06em; }}
    .summary-card strong {{ font-size:1.35rem; }}
    .chart {{ width:100%; height:auto; display:block; border:1px solid var(--grid); border-radius:9px; }}
    .chart-title {{ font-weight:700; font-size:14px; fill:{COLOR["ink"]}; }}
    .axis-label,.legend-label,.marker-label,.point-label {{ font-size:10px; fill:{COLOR["muted"]}; }}
    .marker-label {{ font-weight:700; }} .point-label {{ fill:{COLOR["ink"]}; font-weight:650; }}
    .chart-grid,.event-figures {{ display:grid; grid-template-columns:1fr 1fr; gap:14px; align-items:start; }}
    .source-note {{ color:var(--muted); font-size:.76rem; margin:7px 4px 0; }}
    .event-panel {{ background:var(--wash); border:1px solid #d8e0e5; border-radius:11px;
      padding:20px; margin:16px 0; }}
    .event-heading {{ display:flex; justify-content:space-between; align-items:center; gap:16px; margin-bottom:16px; }}
    .status {{ background:#fff; border:1px solid #ced8de; border-radius:999px; padding:6px 10px;
      font-size:.78rem; font-weight:700; text-transform:uppercase; letter-spacing:.05em; }}
    .detail-grid {{ margin-top:16px; }}
    .empty-panel {{ min-height:230px; background:#fff; border:1px dashed #aebbc4; border-radius:9px;
      padding:28px; color:var(--muted); display:flex; flex-direction:column; justify-content:center; }}
    .empty-panel.compact {{ min-height:286px; }}
    .table-wrap {{ overflow-x:auto; border:1px solid var(--grid); border-radius:7px; background:#fff; }}
    table {{ border-collapse:collapse; width:100%; font-size:.78rem; }}
    th,td {{ padding:8px 9px; border-bottom:1px solid var(--grid); text-align:right; white-space:nowrap; }}
    th:first-child,td:first-child {{ text-align:left; }} th {{ background:#edf2f5; color:#475968; }}
    details {{ margin-top:16px; }} summary {{ cursor:pointer; color:#334b5b; font-weight:650; }}
    pre {{ white-space:pre-wrap; overflow-wrap:anywhere; max-height:520px; overflow:auto; background:#17202a;
      color:#e8eef2; border-radius:8px; padding:16px; font:12px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace; }}
    .boundary {{ background:#fff7e8; border:1px solid #ead8ad; border-radius:9px; padding:17px 20px; }}
    .boundary li {{ margin:5px 0; }} .muted {{ color:var(--muted); }}
    footer {{ margin-top:40px; color:var(--muted); font-size:.8rem; }}
    @media (max-width:780px) {{ main {{ padding:28px 16px 52px; }} .topline,.event-heading {{ align-items:flex-start;
      flex-direction:column; }} .metadata,.detail-grid,.summary-cards {{ grid-template-columns:1fr 1fr; }}
      .chart-grid,.event-figures {{ grid-template-columns:1fr; }} }}
    @media print {{ body {{ background:#fff; }} main {{ max-width:none; padding:12mm; }} .download {{ display:none; }}
      .event-panel {{ break-inside:avoid; }} details {{ display:none; }} }}
    """
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{safe_title}</title>
<style>{stylesheet}</style>
</head>
<body>
<main>
  <header>
    <p class="eyebrow">research instrument · {RENDERER_VERSION}</p>
    <div class="topline">
      <div>
        <h1>{safe_title}</h1>
        <p class="lede">A descriptive mirror of global trajectory geometry and event-local
        intervention evidence. It keeps semantic candidate preference, control leverage,
        replay propagation, and revision policy visibly separate.</p>
      </div>
      <button class="download" id="download-trace" type="button">Download raw trace JSON</button>
    </div>
    {_metadata_table(trace)}
    {_summary_cards(adapter, separation)}
    <p class="source-note">Observation records embedded: {observation_count}. No timestamp is
    generated by the renderer; any date shown in the payload is explicit input metadata.</p>
  </header>

  <section>
    <h2>Global counterfactual mirror</h2>
    {global_chart}
    <h2>Trajectory kinematics</h2>
    {_kinematic_charts(adapter)}
  </section>

  <section>
    <h2>Event-local audits</h2>
    {_render_event_sections(adapter)}
  </section>

  <section>
    <h2>Claim boundary</h2>
    <div class="boundary">{_claim_boundary(trace)}</div>
  </section>

  <section>
    <h2>Configuration and provenance</h2>
    <details><summary>Config, adapter provenance, metrics, and explicit metadata</summary>
      <pre>{_provenance(trace)}</pre>
    </details>
    <details><summary>Complete embedded trace</summary><pre>{pretty}</pre></details>
  </section>

  <footer>Deterministic renderer: identical trace and title inputs produce identical HTML bytes.</footer>
</main>
<script id="ebrt-trace-data" type="application/json">{embedded}</script>
<script>
(() => {{
  "use strict";
  const button = document.getElementById("download-trace");
  const payload = document.getElementById("ebrt-trace-data").textContent;
  button.addEventListener("click", () => {{
    const blob = new Blob([payload + "\\n"], {{type: "application/json"}});
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "ebrt_v0_2_trace.json";
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }});
}})();
</script>
</body>
</html>
"""


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    except BaseException:
        try:
            temporary_path.unlink()
        except FileNotFoundError:
            pass
        raise


def _self_test_trace() -> dict[str, Any]:
    baseline_states = [
        [0.0, 0.0, 0.0],
        [0.3, 0.1, 0.0],
        [0.5, 0.3, 0.1],
        [0.7, 0.2, 0.2],
        [0.8, 0.0, 0.25],
    ]
    final_states = [
        [0.0, 0.0, 0.0],
        [0.2, 0.15, 0.0],
        [0.35, 0.45, 0.15],
        [0.42, 0.50, 0.3],
        [0.48, 0.42, 0.36],
    ]
    return {
        "schema_version": "ebrt-instrumentation-v0.2-test",
        "model": "frozen-toy-generator",
        "model_version": "self-test",
        "monolith_sha256": "0" * 64,
        "config": {"revision_steps": 4, "top_k": 1},
        "observations": [
            {"step": 0, "text": "Initial support."},
            {"step": 1, "text": "Context with </script><script>unsafe()</script>."},
            {"step": 2, "text": "Candidate distractor."},
            {"step": 3, "text": "Later evidence rejects the premise."},
            {"step": 4, "text": "Downstream consequence."},
        ],
        "baseline_geometry": {
            "full": {
                "states": baseline_states,
                "speed": [0.0, 0.3162, 0.3, 0.2449, 0.2062],
                "turn_angle": [None, None, 0.43, 1.01, 0.72],
                "normalized_acceleration": [None, None, 0.31, 0.74, 0.45],
            },
        },
        "final_geometry": {
            "full": {
                "states": final_states,
                "speed": [0.0, 0.25, 0.364, 0.186, 0.106],
                "turn_angle": [None, None, 0.31, 0.66, 0.55],
                "normalized_acceleration": [None, None, 0.24, 0.48, 0.38],
            },
        },
        "delta_geometry": {
            "full": {
                "states": [
                    [b - a for a, b in zip(before, after)]
                    for before, after in zip(baseline_states, final_states)
                ]
            }
        },
        "event_candidates": [
            {
                "event_index": 0,
                "source_step": 3,
                "prior_step": 0,
                "eligible_steps": [0, 2],
                "event_score": 0.73,
                "detected": True,
                "status": "committed",
                "candidates": [
                    {
                        "step": 0,
                        "topic_similarity": 0.92,
                        "contradiction": 0.84,
                        "recency": 0.2,
                        "logit": 1.24,
                        "attention": 0.68,
                        "selected": True,
                    },
                    {
                        "step": 2,
                        "topic_similarity": 0.74,
                        "contradiction": 0.62,
                        "recency": 0.9,
                        "logit": 1.06,
                        "attention": 0.32,
                        "selected": False,
                    },
                ],
            }
        ],
        "revision_mirrors": [
            {
                "event_index": 0,
                "source_step": 3,
                "targets": [0],
                "earliest_replay_step": 0,
                "local_steps": [0, 1, 2, 3],
                "replay_span_steps": 4,
                "replay_distance": 3,
                "route_distances": {"0": 3},
                "mirror_states": baseline_states[:4],
                "revised_states": final_states[:4],
                "delta_states": [
                    [b - a for a, b in zip(before, after)]
                    for before, after in zip(baseline_states[:4], final_states[:4])
                ],
                "magnitudes": {
                    "control_delta_l2": 0.81,
                    "state_delta_l2": 0.69,
                    "source_state_delta_l2": 0.54,
                    "terminal_state_delta_l2": 0.46,
                },
                "source_target_projection_gain": 0.31,
                "terminal_target_projection_gain": 0.24,
                "propagation_survival_ratio": 0.85,
                "propagation_separation": [0.08, 0.21, 0.39, 0.54, 0.46],
                "unrelated_state_leakage_max": 0.08,
                "accepted": True,
                "rolled_back": True,
                "energy_before": 1.2,
                "energy_after": 0.43,
                "energy_drop": 0.77,
            }
        ],
        "candidate_control_leverage": {
            "enabled": True,
            "method": "self-test finite difference",
            "epsilon": 0.001,
            "candidates": [
                {"source_step": 3, "candidate_step": 0, "control_leverage": 0.58},
                {"source_step": 3, "candidate_step": 2, "control_leverage": 0.76},
                # Same candidate index under another source catches accidental
                # cross-event joins in the settled top-level row format.
                {"source_step": 4, "candidate_step": 0, "control_leverage": 99.0},
            ],
        },
        "metrics": {"target_topic_success": 1},
        "source_session_fingerprint": "session-self-test",
        "trace_fingerprint": "trace-self-test",
        "metadata": {"captured_at": "explicit-self-test-time"},
        "claim_boundary": ["Self-test payload; no external validity claim."],
    }


def run_self_test() -> dict[str, Any]:
    trace = _self_test_trace()
    adapter = TraceAdapter(trace)
    event = adapter.events()[0]
    leverage = _event_leverage(adapter, event, 0)
    if leverage != {0: 0.58, 2: 0.76}:
        raise AssertionError(f"candidate leverage joined across events: {leverage}")
    sequential_trace = json.loads(json.dumps(trace))
    sequential_trace["event_candidates"].insert(
        0,
        {
            "event_index": 0,
            "source_step": 1,
            "detected": False,
            "status": "not_detected",
            "candidates": [],
        },
    )
    joined = _join_events_and_mirrors(TraceAdapter(sequential_trace))
    non_event = next(item for item in joined if _event_source(item[1]) == 1)
    if non_event[2]:
        raise AssertionError("non-event inherited a revision mirror by list index")
    first = render_trace_html(trace, title="Deterministic self-test figure")
    second = render_trace_html(trace, title="Deterministic self-test figure")
    if first != second:
        raise AssertionError("identical inputs did not produce identical HTML")
    required = (
        "Global baseline/final mirror separation",
        "Trajectory speed",
        "Turn angle",
        "Per-event local mirror separation",
        "propagation ‖Δh‖ (later revisions suppressed)",
        "Semantic score × control leverage",
        "accepted · rollback to best checkpoint",
        "Download raw trace JSON",
        'id="ebrt-trace-data"',
    )
    for needle in required:
        if needle not in first:
            raise AssertionError(f"rendered figure omitted required element: {needle}")
    if "</script><script>unsafe()" in first:
        raise AssertionError("embedded JSON permits script-element termination")
    match = re.search(
        r'<script id="ebrt-trace-data" type="application/json">(.*?)</script>',
        first,
        flags=re.DOTALL,
    )
    if match is None:
        raise AssertionError("embedded trace payload not found")
    recovered = json.loads(match.group(1))
    if recovered != trace:
        raise AssertionError("embedded trace payload does not round-trip")
    with tempfile.TemporaryDirectory(prefix="ebrt-renderer-self-test-") as directory:
        output = Path(directory) / "figure.html"
        _atomic_write(output, first)
        if output.read_text(encoding="utf-8") != first:
            raise AssertionError("atomic output write changed rendered bytes")
    return {
        "status": "PASS",
        "renderer_version": RENDERER_VERSION,
        "deterministic_sha256": hashlib.sha256(first.encode("utf-8")).hexdigest(),
        "html_bytes": len(first.encode("utf-8")),
        "checks": [
            "deterministic byte-for-byte render",
            "global baseline/final mirror separation",
            "speed and turn-angle geometry",
            "event markers and local mirror separation",
            "semantic-score versus control-leverage candidates",
            "source-keyed sequential event/mirror joining",
            "route, replay, acceptance and rollback details",
            "safe embedded JSON round-trip and raw download payload",
            "atomic UTF-8 output write",
        ],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Render one EBRT v0.2 trace as a deterministic, dependency-free "
            "HTML/SVG research figure."
        )
    )
    parser.add_argument("trace", nargs="?", type=Path, help="input trace JSON")
    parser.add_argument("--input-json", type=Path, help="input trace JSON (flag form)")
    parser.add_argument("--output-html", type=Path, help="output standalone HTML")
    parser.add_argument("--title", default=DEFAULT_TITLE, help="explicit figure title")
    parser.add_argument(
        "--self-test", action="store_true", help="run deterministic renderer checks"
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.self_test:
        if (
            args.trace is not None
            or args.input_json is not None
            or args.output_html is not None
        ):
            raise SystemExit(
                "--self-test cannot be combined with input or output arguments"
            )
        print(_canonical_json(run_self_test(), pretty=True))
        return 0
    if args.trace is not None and args.input_json is not None:
        raise SystemExit(
            "provide the trace positionally or with --input-json, not both"
        )
    input_path = args.input_json or args.trace
    if input_path is None:
        raise SystemExit("an input trace is required (TRACE or --input-json TRACE)")
    if args.output_html is None:
        raise SystemExit("--output-html is required")
    try:
        loaded = json.loads(input_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"could not read trace JSON: {error}") from error
    if not isinstance(loaded, Mapping):
        raise SystemExit("trace JSON root must be an object")
    rendered = render_trace_html(loaded, title=args.title)
    _atomic_write(args.output_html, rendered)
    print(
        _canonical_json(
            {
                "status": "PASS",
                "renderer_version": RENDERER_VERSION,
                "output_html": args.output_html.name,
                "sha256": hashlib.sha256(rendered.encode("utf-8")).hexdigest(),
                "bytes": len(rendered.encode("utf-8")),
            },
            pretty=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
