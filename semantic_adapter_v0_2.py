#!/usr/bin/env python3
"""Versioned semantic-input boundary for EBRT v0.2.

The frozen v0.1 mechanism consumes five explicit fields.  This module makes the
producer of those fields auditable without pretending that the current
structured oracle is a learned semantic detector.  It intentionally depends
only on the Python standard library; provider-backed adapters can implement the
same :class:`SemanticAdapter` protocol in separate modules later.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping, Protocol, Sequence, runtime_checkable


SEMANTIC_SCHEMA_VERSION = "ebrt-semantic-observation-v0.2"


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _input_sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class AdapterProvenance:
    """Stable description of how semantic fields were produced."""

    adapter_name: str
    adapter_version: str
    provider: str
    model: str | None
    semantic_source: str
    deterministic: bool
    parameters: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["schema_version"] = SEMANTIC_SCHEMA_VERSION
        payload["parameters"] = dict(self.parameters)
        return payload


@dataclass(frozen=True)
class AdaptedObservation:
    """Validated semantic observation plus non-behavioral provenance keys."""

    topic: str
    stance: float
    text: str
    confidence: float
    revision_cue: float
    source_id: str
    input_sha256: str

    def __post_init__(self) -> None:
        if not self.topic.strip():
            raise ValueError("topic must not be empty")
        if not self.text.strip():
            raise ValueError("text must not be empty")
        for name, value in (
            ("stance", self.stance),
            ("confidence", self.confidence),
            ("revision_cue", self.revision_cue),
        ):
            if not math.isfinite(value):
                raise ValueError(f"{name} must be finite")
        if not -1.0 <= self.stance <= 1.0:
            raise ValueError("stance must be in [-1, 1]")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be in [0, 1]")
        if not 0.0 <= self.revision_cue <= 1.0:
            raise ValueError("revision_cue must be in [0, 1]")
        if not self.source_id:
            raise ValueError("source_id must not be empty")

    def to_observation_mapping(self) -> dict[str, Any]:
        """Return exactly the behavioral fields accepted by frozen EBRT v0.1."""

        return {
            "topic": self.topic,
            "stance": self.stance,
            "text": self.text,
            "confidence": self.confidence,
            "revision_cue": self.revision_cue,
        }

    def to_trace_dict(self, provenance: AdapterProvenance) -> dict[str, Any]:
        return {
            "schema_version": SEMANTIC_SCHEMA_VERSION,
            **self.to_observation_mapping(),
            "source_id": self.source_id,
            "input_sha256": self.input_sha256,
            "provenance": provenance.to_dict(),
        }


@runtime_checkable
class SemanticAdapter(Protocol):
    """Replaceable boundary from an external chunk to EBRT semantic fields."""

    @property
    def provenance(self) -> AdapterProvenance: ...

    def observe(
        self,
        chunk: Mapping[str, Any],
        *,
        source_id: str | None = None,
    ) -> AdaptedObservation: ...

    def observe_many(
        self,
        chunks: Sequence[Mapping[str, Any]],
    ) -> list[AdaptedObservation]: ...


class StructuredOracleAdapter:
    """Pass validated, explicitly structured oracle fields into EBRT.

    This adapter does no language understanding.  Its provenance deliberately
    says ``structured_oracle`` so downstream reports cannot confuse these
    fields with autonomous model judgments.
    """

    def __init__(self, *, canonicalize_topics: bool = True) -> None:
        self.canonicalize_topics = bool(canonicalize_topics)
        self._provenance = AdapterProvenance(
            adapter_name="StructuredOracleAdapter",
            adapter_version="0.2",
            provider="local",
            model=None,
            semantic_source="structured_oracle",
            deterministic=True,
            parameters={"canonicalize_topics": self.canonicalize_topics},
        )

    @property
    def provenance(self) -> AdapterProvenance:
        return self._provenance

    def observe(
        self,
        chunk: Mapping[str, Any],
        *,
        source_id: str | None = None,
    ) -> AdaptedObservation:
        if not isinstance(chunk, Mapping):
            raise TypeError("StructuredOracleAdapter expects a mapping")
        if "topic" not in chunk or "stance" not in chunk:
            raise ValueError("structured oracle input requires topic and stance")
        raw_topic = str(chunk["topic"]).strip()
        topic = raw_topic.casefold() if self.canonicalize_topics else raw_topic
        text = str(chunk.get("text", raw_topic)).strip()
        canonical_input = {
            "topic": raw_topic,
            "stance": float(chunk["stance"]),
            "text": text,
            "confidence": float(chunk.get("confidence", 1.0)),
            "revision_cue": float(chunk.get("revision_cue", 1.0)),
        }
        digest = _input_sha256(canonical_input)
        return AdaptedObservation(
            topic=topic,
            stance=canonical_input["stance"],
            text=text,
            confidence=canonical_input["confidence"],
            revision_cue=canonical_input["revision_cue"],
            source_id=source_id or f"structured:{digest[:16]}",
            input_sha256=digest,
        )

    def observe_many(
        self,
        chunks: Sequence[Mapping[str, Any]],
    ) -> list[AdaptedObservation]:
        return [
            self.observe(chunk, source_id=f"structured:{index}")
            for index, chunk in enumerate(chunks)
        ]


def run_self_tests() -> dict[str, Any]:
    adapter = StructuredOracleAdapter()
    source = {
        "topic": " Load_Limit ",
        "stance": -0.25,
        "text": "A revised measurement.",
        "confidence": 0.8,
        "revision_cue": 0.75,
    }
    first = adapter.observe(source, source_id="fixture:0")
    second = adapter.observe(source, source_id="fixture:0")
    if first != second:
        raise AssertionError("structured adapter is not deterministic")
    if first.topic != "load_limit":
        raise AssertionError("topic canonicalization failed")
    if set(first.to_observation_mapping()) != {
        "topic",
        "stance",
        "text",
        "confidence",
        "revision_cue",
    }:
        raise AssertionError("behavioral mapping leaked provenance fields")
    if not isinstance(adapter, SemanticAdapter):
        raise AssertionError("adapter does not satisfy SemanticAdapter protocol")
    trace = first.to_trace_dict(adapter.provenance)
    if trace["provenance"]["semantic_source"] != "structured_oracle":
        raise AssertionError("oracle provenance was not explicit")
    return {
        "status": "PASS",
        "schema_version": SEMANTIC_SCHEMA_VERSION,
        "checks": [
            "deterministic structured adaptation",
            "validated bounded fields",
            "behavioral/provenance separation",
            "runtime protocol compatibility",
        ],
    }


if __name__ == "__main__":
    print(json.dumps(run_self_tests(), ensure_ascii=False, indent=2))
