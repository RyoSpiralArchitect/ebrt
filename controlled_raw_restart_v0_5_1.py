#!/usr/bin/env python3
"""Pure bridge from a case-bound temporal EBRT map to raw-context restart input.

This module is deliberately network-free and gold-free.  It binds one public
case to a supplied v0.5-T recurrence, optimizes that local recurrence, and
projects four structurally matched prompt envelopes.  The hosted-model call,
downstream grading, and artifact publication belong to a separate runner.

No gradient crosses the JSON projection.  Transition controls remain controls
over named public operations at named temporal floors; they are never relabeled
as evidence truth or hidden-model attention.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import socket
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence
from unittest import mock

import benchmark_aperture_controls_v0_4_1 as v041
import benchmark_aperture_controls_v0_4_2 as v042
from language_replay_bridge_v0_4 import (
    CardResult,
    CaseSpec,
    ProviderReceipt,
    ProviderUsage,
    ReasoningCard,
)
from temporal_adjoint_state_controller_v0_5_t import (
    EXECUTION_CONTROL_MAP_SCHEMA_VERSION,
    SUITE_SCHEMA_VERSION,
    TemporalAdjointStateController,
    TemporalPairedSuite,
)


ROOT = Path(__file__).resolve().parent
DEFAULT_FIXTURE_PATH = ROOT / "fixtures" / "controlled_raw_restart_v0_5_1_canary.json"

FIXTURE_SCHEMA_VERSION = "ebrt-controlled-raw-restart-canary-v0.5.1"
ENVELOPE_SCHEMA_VERSION = "ebrt-controlled-raw-restart-envelope-v0.5.1"
REQUEST_SCHEMA_VERSION = "ebrt-controlled-raw-restart-request-v0.5.1"

ARM_ZERO = "raw_restart_zero_control"
ARM_TEXTUAL = "raw_restart_textual_envelope"
ARM_PERMUTATION = "raw_restart_matched_permutation"
ARM_GRADIENT = "controlled_raw_restart"
ARM_ORDER = (ARM_ZERO, ARM_TEXTUAL, ARM_PERMUTATION, ARM_GRADIENT)

_ENVELOPE_FIELDS = frozenset(
    {
        "schema_version",
        "revision_context",
        "temporal_controls",
        "instructions_fragment",
    }
)
_CONTROL_FIELDS = frozenset(
    {
        "floor_id",
        "floor_ordinal",
        "operator_name",
        "target_kind",
        "target_id",
        "role",
        "delta",
    }
)
_PROVENANCE_FIELDS = frozenset(
    {
        "fixture_id",
        "case_id",
        "binding_id",
        "event_id",
        "event_triggered",
        "case_fingerprint_sha256",
        "binding_fingerprint_sha256",
        "semantic_payload_sha256",
        "program_fingerprint_sha256",
        "source_control_map_fingerprint_sha256",
        "projected_controls_fingerprint_sha256",
        "source_control_status",
    }
)
_FORBIDDEN_KEYS = frozenset(
    {
        "answer_key",
        "correct_answer",
        "downstream_verdict",
        "evaluation_label",
        "expected_answer",
        "gold",
        "gold_label",
        "grading",
        "machine_success",
        "provider_output",
        "reasoning_text",
        "reasoning_tokens",
        "strict_grade",
    }
)

_COMMON_INSTRUCTIONS_FRAGMENT = (
    "Use the ordered raw evidence as the semantic authority. If revision_context is "
    "present, apply its explicit public invalidation lineage. Apply each temporal "
    "control only to its named public operation at its named floor. A zero control is "
    "exact identity; a nonzero control changes operation emphasis, not evidence truth."
)


class BridgeSchemaError(ValueError):
    """An exact bridge, fixture, map, or projection contract was violated."""


def canonical_json_bytes(value: Any, *, trailing_newline: bool = False) -> bytes:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return encoded + (b"\n" if trailing_newline else b"")


def fingerprint(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _is_sha256(value: Any) -> bool:
    text = str(value)
    return len(text) == 64 and all(char in "0123456789abcdef" for char in text)


def _exact_mapping(value: Any, label: str, fields: set[str]) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise BridgeSchemaError(f"{label} must be an object")
    actual = set(value)
    if actual != fields:
        raise BridgeSchemaError(
            f"{label} fields drifted: missing={sorted(fields - actual)} "
            f"unknown={sorted(actual - fields)}"
        )
    return value


def _string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise BridgeSchemaError(f"{label} must be a trimmed nonempty string")
    return value


def _bool(value: Any, label: str) -> bool:
    if type(value) is not bool:
        raise BridgeSchemaError(f"{label} must be boolean")
    return value


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise BridgeSchemaError(f"{label} must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise BridgeSchemaError(f"{label} must be a finite number")
    return result


def _unique_strings(
    value: Any, label: str, *, nonempty: bool = False
) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise BridgeSchemaError(f"{label} must be an array")
    result = tuple(_string(item, f"{label} item") for item in value)
    if nonempty and not result:
        raise BridgeSchemaError(f"{label} must not be empty")
    if len(result) != len(set(result)):
        raise BridgeSchemaError(f"{label} must not contain duplicates")
    return result


def _reject_forbidden_keys(value: Any, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key)
            if key_text.casefold() in _FORBIDDEN_KEYS:
                raise BridgeSchemaError(f"{path}.{key_text}: forbidden field")
            _reject_forbidden_keys(child, f"{path}.{key_text}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_forbidden_keys(child, f"{path}[{index}]")


def _load_json_exact(path: Path) -> dict[str, Any]:
    def pairs_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        output: dict[str, Any] = {}
        for key, value in pairs:
            if key in output:
                raise BridgeSchemaError(f"duplicate JSON key: {key!r}")
            output[key] = value
        return output

    value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs_hook)
    if not isinstance(value, dict):
        raise BridgeSchemaError("fixture root must be an object")
    return value


@dataclass(frozen=True)
class EvidenceBinding:
    role: str
    evidence_id: str
    public_summary: str
    source_kind: str
    evidence_value: float

    @classmethod
    def from_mapping(cls, value: Any, label: str) -> "EvidenceBinding":
        item = _exact_mapping(
            value,
            label,
            {
                "role",
                "evidence_id",
                "public_summary",
                "source_kind",
                "evidence_value",
            },
        )
        source_kind = _string(item["source_kind"], f"{label}.source_kind")
        if source_kind not in {"raw_history", "revision_event", "stable_context"}:
            raise BridgeSchemaError(f"{label}.source_kind is unsupported")
        return cls(
            role=_string(item["role"], f"{label}.role"),
            evidence_id=_string(item["evidence_id"], f"{label}.evidence_id"),
            public_summary=_string(item["public_summary"], f"{label}.public_summary"),
            source_kind=source_kind,
            evidence_value=_number(item["evidence_value"], f"{label}.evidence_value"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "evidence_id": self.evidence_id,
            "public_summary": self.public_summary,
            "source_kind": self.source_kind,
            "evidence_value": self.evidence_value,
        }


@dataclass(frozen=True)
class TransitionBinding:
    operator_id: str
    public_name: str
    transition_control_id: str

    @classmethod
    def from_mapping(cls, value: Any, label: str) -> "TransitionBinding":
        item = _exact_mapping(
            value,
            label,
            {"operator_id", "public_name", "transition_control_id"},
        )
        return cls(
            operator_id=_string(item["operator_id"], f"{label}.operator_id"),
            public_name=_string(item["public_name"], f"{label}.public_name"),
            transition_control_id=_string(
                item["transition_control_id"], f"{label}.transition_control_id"
            ),
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "operator_id": self.operator_id,
            "public_name": self.public_name,
            "transition_control_id": self.transition_control_id,
        }


@dataclass(frozen=True)
class BindingEvent:
    event_id: str
    triggered: bool
    correction_evidence_id: str
    relevant: bool
    revision_cue: float
    invalidated_evidence_ids: tuple[str, ...]

    @classmethod
    def from_mapping(cls, value: Any) -> "BindingEvent":
        item = _exact_mapping(
            value,
            "case_program_binding.event",
            {
                "event_id",
                "triggered",
                "correction_evidence_id",
                "relevant",
                "revision_cue",
                "invalidated_evidence_ids",
            },
        )
        cue = _number(item["revision_cue"], "event.revision_cue")
        if not 0.0 <= cue <= 1.0:
            raise BridgeSchemaError("event.revision_cue must be in [0, 1]")
        triggered = _bool(item["triggered"], "event.triggered")
        invalidated = _unique_strings(
            item["invalidated_evidence_ids"], "event.invalidated_evidence_ids"
        )
        if not triggered and invalidated:
            raise BridgeSchemaError(
                "a non-triggered event must not invalidate evidence"
            )
        return cls(
            event_id=_string(item["event_id"], "event.event_id"),
            triggered=triggered,
            correction_evidence_id=_string(
                item["correction_evidence_id"], "event.correction_evidence_id"
            ),
            relevant=_bool(item["relevant"], "event.relevant"),
            revision_cue=cue,
            invalidated_evidence_ids=invalidated,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "triggered": self.triggered,
            "correction_evidence_id": self.correction_evidence_id,
            "relevant": self.relevant,
            "revision_cue": self.revision_cue,
            "invalidated_evidence_ids": list(self.invalidated_evidence_ids),
        }


@dataclass(frozen=True)
class CaseProgramBinding:
    binding_id: str
    case_id: str
    suite_id: str
    pair_id: str
    order_variant: str
    state_axes: tuple[str, ...]
    initial_state: tuple[float, ...]
    evidence_bindings: tuple[EvidenceBinding, ...]
    modeled_evidence_ids: tuple[str, ...]
    passthrough_evidence_ids: tuple[str, ...]
    transition_bindings: tuple[TransitionBinding, ...]
    event: BindingEvent
    terminal_decision_target: float
    sham_source_index_by_target: tuple[int, ...]
    program_spec_fingerprint_sha256: str

    @classmethod
    def from_mapping(cls, value: Any) -> "CaseProgramBinding":
        item = _exact_mapping(
            value,
            "case_program_binding",
            {
                "binding_id",
                "case_id",
                "suite_id",
                "pair_id",
                "order_variant",
                "state_axes",
                "initial_state",
                "evidence_bindings",
                "modeled_evidence_ids",
                "passthrough_evidence_ids",
                "transition_bindings",
                "event",
                "terminal_decision_target",
                "sham_source_index_by_target",
                "program_spec_fingerprint_sha256",
            },
        )
        state_axes = _unique_strings(
            item["state_axes"], "binding.state_axes", nonempty=True
        )
        if state_axes != ("premise", "decision", "stable"):
            raise BridgeSchemaError(
                "binding state axes must remain premise/decision/stable"
            )
        initial = item["initial_state"]
        if not isinstance(initial, list) or len(initial) != len(state_axes):
            raise BridgeSchemaError("binding.initial_state dimension drifted")
        initial_state = tuple(
            _number(entry, f"binding.initial_state[{index}]")
            for index, entry in enumerate(initial)
        )
        evidence_raw = item["evidence_bindings"]
        transition_raw = item["transition_bindings"]
        if not isinstance(evidence_raw, list) or not isinstance(transition_raw, list):
            raise BridgeSchemaError("binding arrays are malformed")
        evidence = tuple(
            EvidenceBinding.from_mapping(entry, f"evidence_bindings[{index}]")
            for index, entry in enumerate(evidence_raw)
        )
        transitions = tuple(
            TransitionBinding.from_mapping(entry, f"transition_bindings[{index}]")
            for index, entry in enumerate(transition_raw)
        )
        if tuple(entry.role for entry in evidence) != (
            "legacy_premise",
            "correction_premise",
            "stable_context",
        ):
            raise BridgeSchemaError("evidence binding roles drifted")
        if tuple(entry.transition_control_id for entry in transitions) != (
            "decision_write",
            "revision_mix",
            "stable_carry",
        ):
            raise BridgeSchemaError("transition binding controls drifted")
        sham_raw = item["sham_source_index_by_target"]
        if not isinstance(sham_raw, list) or any(
            type(entry) is not int for entry in sham_raw
        ):
            raise BridgeSchemaError("binding sham permutation must contain integers")
        sham = tuple(sham_raw)
        if sorted(sham) != list(range(len(transitions))) or sham == tuple(
            range(len(transitions))
        ):
            raise BridgeSchemaError(
                "binding sham permutation must be nonidentity exact"
            )
        program_hash = _string(
            item["program_spec_fingerprint_sha256"],
            "binding.program_spec_fingerprint_sha256",
        )
        if not _is_sha256(program_hash):
            raise BridgeSchemaError("binding program fingerprint is not SHA-256")
        target = _number(
            item["terminal_decision_target"], "binding.terminal_decision_target"
        )
        if not -1.0 <= target <= 1.0:
            raise BridgeSchemaError("binding terminal target must be in [-1, 1]")
        result = cls(
            binding_id=_string(item["binding_id"], "binding.binding_id"),
            case_id=_string(item["case_id"], "binding.case_id"),
            suite_id=_string(item["suite_id"], "binding.suite_id"),
            pair_id=_string(item["pair_id"], "binding.pair_id"),
            order_variant=_string(item["order_variant"], "binding.order_variant"),
            state_axes=state_axes,
            initial_state=initial_state,
            evidence_bindings=evidence,
            modeled_evidence_ids=_unique_strings(
                item["modeled_evidence_ids"],
                "binding.modeled_evidence_ids",
                nonempty=True,
            ),
            passthrough_evidence_ids=_unique_strings(
                item["passthrough_evidence_ids"],
                "binding.passthrough_evidence_ids",
                nonempty=True,
            ),
            transition_bindings=transitions,
            event=BindingEvent.from_mapping(item["event"]),
            terminal_decision_target=target,
            sham_source_index_by_target=sham,
            program_spec_fingerprint_sha256=program_hash,
        )
        if result.program_spec_fingerprint_sha256 != fingerprint(
            result.program_spec_payload()
        ):
            raise BridgeSchemaError("binding program-spec fingerprint mismatch")
        return result

    def program_spec_payload(self) -> dict[str, Any]:
        payload = self.to_dict()
        payload.pop("program_spec_fingerprint_sha256")
        return payload

    def to_dict(self) -> dict[str, Any]:
        return {
            "binding_id": self.binding_id,
            "case_id": self.case_id,
            "suite_id": self.suite_id,
            "pair_id": self.pair_id,
            "order_variant": self.order_variant,
            "state_axes": list(self.state_axes),
            "initial_state": list(self.initial_state),
            "evidence_bindings": [entry.to_dict() for entry in self.evidence_bindings],
            "modeled_evidence_ids": list(self.modeled_evidence_ids),
            "passthrough_evidence_ids": list(self.passthrough_evidence_ids),
            "transition_bindings": [
                entry.to_dict() for entry in self.transition_bindings
            ],
            "event": self.event.to_dict(),
            "terminal_decision_target": self.terminal_decision_target,
            "sham_source_index_by_target": list(self.sham_source_index_by_target),
            "program_spec_fingerprint_sha256": self.program_spec_fingerprint_sha256,
        }


@dataclass(frozen=True)
class ProjectionPolicy:
    policy_id: str
    arm_order: tuple[str, ...]
    raw_context_delivery: str
    control_lane: str
    numeric_precision: int
    provider_envelope_allowlist: tuple[str, ...]

    @classmethod
    def from_mapping(cls, value: Any) -> "ProjectionPolicy":
        item = _exact_mapping(
            value,
            "projection_policy",
            {
                "policy_id",
                "arm_order",
                "raw_context_delivery",
                "control_lane",
                "numeric_precision",
                "provider_envelope_allowlist",
            },
        )
        precision = item["numeric_precision"]
        if type(precision) is not int or not 6 <= precision <= 16:
            raise BridgeSchemaError("projection numeric precision must be in [6, 16]")
        result = cls(
            policy_id=_string(item["policy_id"], "projection policy id"),
            arm_order=_unique_strings(
                item["arm_order"], "projection arm order", nonempty=True
            ),
            raw_context_delivery=_string(
                item["raw_context_delivery"], "raw context delivery"
            ),
            control_lane=_string(item["control_lane"], "control lane"),
            numeric_precision=precision,
            provider_envelope_allowlist=_unique_strings(
                item["provider_envelope_allowlist"],
                "provider envelope allowlist",
                nonempty=True,
            ),
        )
        if result.arm_order != ARM_ORDER:
            raise BridgeSchemaError("projection arm order drifted")
        if result.raw_context_delivery != "ordered_all_raw_evidence_exactly_once":
            raise BridgeSchemaError("raw-context delivery policy drifted")
        if result.control_lane != "transition":
            raise BridgeSchemaError("bridge must use the temporal transition lane")
        if set(result.provider_envelope_allowlist) != _ENVELOPE_FIELDS:
            raise BridgeSchemaError("provider envelope allowlist drifted")
        return result

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "arm_order": list(self.arm_order),
            "raw_context_delivery": self.raw_context_delivery,
            "control_lane": self.control_lane,
            "numeric_precision": self.numeric_precision,
            "provider_envelope_allowlist": list(self.provider_envelope_allowlist),
        }


@dataclass(frozen=True)
class ControlledRawRestartFixture:
    fixture_id: str
    status: str
    case: CaseSpec
    binding: CaseProgramBinding
    projection_policy: ProjectionPolicy
    source_case_fingerprint_sha256: str
    binding_fingerprint_sha256: str
    fixture_fingerprint_sha256: str
    claim_boundary: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": FIXTURE_SCHEMA_VERSION,
            "fixture_id": self.fixture_id,
            "status": self.status,
            "case": self.case.trace_dict(),
            "case_program_binding": self.binding.to_dict(),
            "projection_policy": self.projection_policy.to_dict(),
            "source_case_fingerprint_sha256": self.source_case_fingerprint_sha256,
            "binding_fingerprint_sha256": self.binding_fingerprint_sha256,
            "fixture_fingerprint_sha256": self.fixture_fingerprint_sha256,
            "claim_boundary": list(self.claim_boundary),
        }


@dataclass(frozen=True)
class ArmProjection:
    arm_id: str
    guidance_mode: str
    prompt_envelope: Mapping[str, Any] | None
    provenance: Mapping[str, Any]
    source_case_fingerprint_sha256: str
    binding_fingerprint_sha256: str
    program_fingerprint_sha256: str
    source_control_map_fingerprint_sha256: str
    projected_controls_fingerprint_sha256: str

    @property
    def instructions_fragment(self) -> str:
        return _COMMON_INSTRUCTIONS_FRAGMENT

    def to_dict(self) -> dict[str, Any]:
        return {
            "arm_id": self.arm_id,
            "guidance_mode": self.guidance_mode,
            "prompt_envelope": (
                None
                if self.prompt_envelope is None
                else copy.deepcopy(dict(self.prompt_envelope))
            ),
            "provenance": copy.deepcopy(dict(self.provenance)),
            "fingerprints": {
                "source_case_fingerprint_sha256": self.source_case_fingerprint_sha256,
                "binding_fingerprint_sha256": self.binding_fingerprint_sha256,
                "program_fingerprint_sha256": self.program_fingerprint_sha256,
                "source_control_map_fingerprint_sha256": (
                    self.source_control_map_fingerprint_sha256
                ),
                "projected_controls_fingerprint_sha256": (
                    self.projected_controls_fingerprint_sha256
                ),
            },
        }


def _fixture_material_without_fingerprint(value: Mapping[str, Any]) -> dict[str, Any]:
    material = copy.deepcopy(dict(value))
    material.pop("fixture_fingerprint_sha256", None)
    return material


def load_bridge_fixture(
    path: Path | str = DEFAULT_FIXTURE_PATH,
) -> ControlledRawRestartFixture:
    raw = _load_json_exact(Path(path))
    _reject_forbidden_keys(raw)
    root = _exact_mapping(
        raw,
        "fixture",
        {
            "schema_version",
            "fixture_id",
            "status",
            "case",
            "case_program_binding",
            "projection_policy",
            "source_case_fingerprint_sha256",
            "binding_fingerprint_sha256",
            "fixture_fingerprint_sha256",
            "claim_boundary",
        },
    )
    if root["schema_version"] != FIXTURE_SCHEMA_VERSION:
        raise BridgeSchemaError("fixture schema version drifted")
    if root["status"] != "DEV_CANARY":
        raise BridgeSchemaError("fixture must remain DEV_CANARY")
    case_value = _exact_mapping(
        root["case"],
        "case",
        {
            "case_id",
            "family",
            "question",
            "answer_choices",
            "decision_slots",
            "initial_evidence",
            "late_evidence",
        },
    )
    case = CaseSpec.from_mapping(case_value)
    binding = CaseProgramBinding.from_mapping(root["case_program_binding"])
    policy = ProjectionPolicy.from_mapping(root["projection_policy"])
    source_hash = _string(
        root["source_case_fingerprint_sha256"], "source case fingerprint"
    )
    binding_hash = _string(root["binding_fingerprint_sha256"], "binding fingerprint")
    fixture_hash = _string(root["fixture_fingerprint_sha256"], "fixture fingerprint")
    if not all(_is_sha256(item) for item in (source_hash, binding_hash, fixture_hash)):
        raise BridgeSchemaError("fixture contains a malformed SHA-256")
    if source_hash != fingerprint(case.trace_dict()):
        raise BridgeSchemaError("source case fingerprint mismatch")
    if binding_hash != fingerprint(binding.to_dict()):
        raise BridgeSchemaError("binding fingerprint mismatch")
    if fixture_hash != fingerprint(_fixture_material_without_fingerprint(root)):
        raise BridgeSchemaError("fixture fingerprint mismatch")
    if binding.case_id != case.case_id:
        raise BridgeSchemaError("binding case_id does not match the public case")
    raw_ids = set(case.evidence_ids)
    modeled = set(binding.modeled_evidence_ids)
    passthrough = set(binding.passthrough_evidence_ids)
    if modeled & passthrough or modeled | passthrough != raw_ids:
        raise BridgeSchemaError(
            "modeled and passthrough evidence must partition the case"
        )
    if tuple(entry.evidence_id for entry in binding.evidence_bindings) != (
        binding.modeled_evidence_ids
    ):
        raise BridgeSchemaError("evidence binding order does not match modeled IDs")
    if binding.event.correction_evidence_id != case.late_evidence.evidence_id:
        raise BridgeSchemaError("event correction evidence is not the late raw chunk")
    if not set(binding.event.invalidated_evidence_ids) <= set(
        entry.evidence_id for entry in case.initial_evidence
    ):
        raise BridgeSchemaError("event invalidation references non-prior evidence")
    claims = _unique_strings(root["claim_boundary"], "claim boundary", nonempty=True)
    return ControlledRawRestartFixture(
        fixture_id=_string(root["fixture_id"], "fixture id"),
        status="DEV_CANARY",
        case=case,
        binding=binding,
        projection_policy=policy,
        source_case_fingerprint_sha256=source_hash,
        binding_fingerprint_sha256=binding_hash,
        fixture_fingerprint_sha256=fixture_hash,
        claim_boundary=claims,
    )


def _operators(binding: CaseProgramBinding) -> list[dict[str, Any]]:
    evidence = {entry.role: entry for entry in binding.evidence_bindings}
    transitions = {
        entry.transition_control_id: entry for entry in binding.transition_bindings
    }
    zero_matrix = [[0.0, 0.0, 0.0] for _ in range(3)]
    return [
        {
            "operator_id": "legacy",
            "public_name": "Read legacy route premise",
            "activation": "tanh",
            "evidence_id": evidence["legacy_premise"].evidence_id,
            "transition_control_id": None,
            "base_matrix": [[0.65, 0.0, 0.0], [0.0, 0.8, 0.0], [0.0, 0.0, 0.8]],
            "evidence_direction": [1.0, 0.0, 0.0],
            "transition_basis": zero_matrix,
        },
        {
            "operator_id": "correction",
            "public_name": "Integrate registry correction",
            "activation": "tanh",
            "evidence_id": evidence["correction_premise"].evidence_id,
            "transition_control_id": None,
            "base_matrix": [[0.65, 0.0, 0.0], [0.0, 0.8, 0.0], [0.0, 0.0, 0.8]],
            "evidence_direction": [1.0, 0.0, 0.0],
            "transition_basis": zero_matrix,
        },
        {
            "operator_id": transitions["decision_write"].operator_id,
            "public_name": transitions["decision_write"].public_name,
            "activation": "tanh",
            "evidence_id": None,
            "transition_control_id": "decision_write",
            "base_matrix": [[0.9, 0.0, 0.0], [0.9, 0.1, 0.0], [0.0, 0.0, 0.8]],
            "evidence_direction": [0.0, 0.0, 0.0],
            "transition_basis": [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 0.0]],
        },
        {
            "operator_id": transitions["revision_mix"].operator_id,
            "public_name": transitions["revision_mix"].public_name,
            "activation": "tanh",
            "evidence_id": None,
            "transition_control_id": "revision_mix",
            "base_matrix": [[0.9, 0.0, 0.0], [0.15, 0.6, 0.0], [0.0, 0.0, 0.8]],
            "evidence_direction": [0.0, 0.0, 0.0],
            "transition_basis": [
                [0.0, 0.0, 0.0],
                [0.7071067811865476, -0.7071067811865476, 0.0],
                [0.0, 0.0, 0.0],
            ],
        },
        {
            "operator_id": "stable_read",
            "public_name": "Read unrelated stable cargo state",
            "activation": "tanh",
            "evidence_id": evidence["stable_context"].evidence_id,
            "transition_control_id": None,
            "base_matrix": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
            "evidence_direction": [0.0, 0.0, 1.0],
            "transition_basis": zero_matrix,
        },
        {
            "operator_id": transitions["stable_carry"].operator_id,
            "public_name": transitions["stable_carry"].public_name,
            "activation": "tanh",
            "evidence_id": None,
            "transition_control_id": "stable_carry",
            "base_matrix": [[0.95, 0.0, 0.0], [0.0, 0.95, 0.0], [0.0, 0.0, 0.7]],
            "evidence_direction": [0.0, 0.0, 0.0],
            "transition_basis": [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, 1.0]],
        },
    ]


def build_case_temporal_suite(
    fixture: ControlledRawRestartFixture,
) -> TemporalPairedSuite:
    binding = fixture.binding
    semantic: dict[str, Any] = {
        "schema_version": SUITE_SCHEMA_VERSION,
        "suite_id": binding.suite_id,
        "state_axes": list(binding.state_axes),
        "initial_state": list(binding.initial_state),
        "evidence_specs": [
            {
                "evidence_id": entry.evidence_id,
                "public_summary": entry.public_summary,
                "source_kind": entry.source_kind,
            }
            for entry in binding.evidence_bindings
        ],
        "operators": _operators(binding),
        "leaf_control_ids": list(binding.modeled_evidence_ids),
        "transition_control_ids": [
            entry.transition_control_id for entry in binding.transition_bindings
        ],
        "trace_orders": [
            {
                "order_variant": "early_correction",
                "operator_ids": [
                    "stable_read",
                    "legacy",
                    "correction",
                    "decision",
                    "revision",
                    "stable_carry",
                ],
            },
            {
                "order_variant": "late_correction",
                "operator_ids": [
                    "stable_read",
                    "legacy",
                    "decision",
                    "correction",
                    "revision",
                    "stable_carry",
                ],
            },
        ],
        "pair_parameters": [
            {
                "pair_id": binding.pair_id,
                "evidence_values": {
                    entry.evidence_id: entry.evidence_value
                    for entry in binding.evidence_bindings
                },
                "terminal_decision_target": binding.terminal_decision_target,
            }
        ],
        "sham_source_index_by_target": list(binding.sham_source_index_by_target),
        "revision_event": {
            "event_id": binding.event.event_id,
            "triggered": binding.event.triggered,
            "correction_evidence_id": binding.event.correction_evidence_id,
            "decision_state_axis": "decision",
            "stable_state_axis": "stable",
        },
    }
    payload = {
        **semantic,
        "provenance": {
            "adapter_name": "case-bound-public-temporal-adapter",
            "adapter_version": "0.5.1-canary",
            "semantic_source": "explicit_dev_case_program_binding",
            "deterministic": True,
            "semantic_payload_sha256": fingerprint(semantic),
        },
        "claim_boundary": [
            "The case-program topology, values, order, and terminal target are explicit DEV oracle inputs.",
            "The supplied temporal program is not dependency discovery or a hidden-state representation.",
            "No provider output or downstream grade enters this temporal program.",
        ],
    }
    suite = TemporalPairedSuite.from_mapping(payload)
    if tuple(entry.evidence_id for entry in suite.evidence_specs) != (
        binding.modeled_evidence_ids
    ):
        raise BridgeSchemaError("materialized suite lost exact case evidence binding")
    return suite


def _program_descriptor(program: Any) -> dict[str, Any]:
    return {
        "suite_id": program.suite_id,
        "semantic_payload_sha256": program.semantic_payload_sha256,
        "pair_id": program.pair_id,
        "order_variant": program.order_variant,
        "state_axes": list(program.state_axes),
        "event_id": program.event_id,
        "event_triggered": program.event_triggered,
        "floors": [
            {
                "floor_id": floor.floor_id,
                "floor_ordinal": floor.floor_ordinal,
                "operator_id": floor.operator_id,
                "operator_name": floor.public_name,
                "activation": floor.activation,
                "evidence_id": floor.evidence_id,
                "transition_control_id": floor.transition_control_id,
            }
            for floor in program.floors
        ],
    }


def _verify_source_control_map(control_map: Mapping[str, Any], program: Any) -> None:
    if control_map.get("schema_version") != EXECUTION_CONTROL_MAP_SCHEMA_VERSION:
        raise BridgeSchemaError("source execution-control-map schema drifted")
    stored = control_map.get("fingerprint_sha256")
    material = copy.deepcopy(dict(control_map))
    material.pop("fingerprint_sha256", None)
    if stored != fingerprint(material):
        raise BridgeSchemaError("source execution-control-map fingerprint mismatch")
    source = control_map.get("source")
    if not isinstance(source, Mapping):
        raise BridgeSchemaError("source execution-control-map lacks source")
    expected_source = {
        "suite_id": program.suite_id,
        "semantic_payload_sha256": program.semantic_payload_sha256,
        "pair_id": program.pair_id,
        "order_variant": program.order_variant,
        "event_id": program.event_id,
        "event_triggered": program.event_triggered,
    }
    if dict(source) != expected_source:
        raise BridgeSchemaError(
            "control-map source does not match materialized program"
        )
    expected_controls = set(program.transition_control_ids)
    controls = control_map.get("controls")
    if (
        not isinstance(controls, list)
        or {row.get("target_id") for row in controls if isinstance(row, Mapping)}
        != expected_controls
    ):
        raise BridgeSchemaError("source control targets do not match program")


def _rounded(value: float, precision: int) -> float:
    result = round(float(value), precision)
    return 0.0 if result == -0.0 else result


def _role(delta: float, threshold: float) -> str:
    if delta > threshold:
        return "increase"
    if delta < -threshold:
        return "decrease"
    return "preserve"


def _project_control_rows(
    *,
    program: Any,
    deltas_by_target: Mapping[str, float],
    role_delta: float,
    precision: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for floor in program.floors:
        target = floor.transition_control_id
        if target is None:
            continue
        delta = _rounded(deltas_by_target[target], precision)
        rows.append(
            {
                "floor_id": floor.floor_id,
                "floor_ordinal": floor.floor_ordinal,
                "operator_name": floor.public_name,
                "target_kind": "transition",
                "target_id": target,
                "role": _role(delta, role_delta),
                "delta": delta,
            }
        )
    rows.sort(key=lambda row: (row["floor_ordinal"], row["target_id"]))
    return rows


def _revision_context(fixture: ControlledRawRestartFixture) -> dict[str, Any]:
    event = fixture.binding.event
    return {
        "late_evidence_id": event.correction_evidence_id,
        "relevant": event.relevant,
        "revision_cue": event.revision_cue,
        "invalidated_evidence_ids": list(event.invalidated_evidence_ids),
    }


def _validate_prompt_envelope(
    envelope: Mapping[str, Any], fixture: ControlledRawRestartFixture
) -> None:
    if set(envelope) != _ENVELOPE_FIELDS:
        raise BridgeSchemaError("prompt envelope escaped its exact allowlist")
    if envelope.get("schema_version") != ENVELOPE_SCHEMA_VERSION:
        raise BridgeSchemaError("prompt envelope schema drifted")
    if envelope.get("instructions_fragment") != _COMMON_INSTRUCTIONS_FRAGMENT:
        raise BridgeSchemaError("prompt envelope instruction fragment drifted")
    revision_context = envelope.get("revision_context")
    if revision_context is not None and revision_context != _revision_context(fixture):
        raise BridgeSchemaError("prompt revision context drifted")
    if not fixture.binding.event.triggered and revision_context is not None:
        raise BridgeSchemaError("no-event envelope must not expose revision context")
    controls = envelope.get("temporal_controls")
    if not isinstance(controls, list) or len(controls) not in {
        0,
        len(fixture.binding.transition_bindings),
    }:
        raise BridgeSchemaError("prompt envelope control count drifted")
    for row in controls:
        if not isinstance(row, Mapping) or set(row) != _CONTROL_FIELDS:
            raise BridgeSchemaError("prompt control row escaped its exact allowlist")
        if row.get("target_kind") != "transition":
            raise BridgeSchemaError("prompt control escaped the transition lane")
        delta = row.get("delta")
        if not isinstance(delta, int | float) or isinstance(delta, bool):
            raise BridgeSchemaError("prompt control delta must be numeric")
        if not math.isfinite(float(delta)):
            raise BridgeSchemaError("prompt control delta must be finite")
        if row.get("role") not in {"increase", "decrease", "preserve"}:
            raise BridgeSchemaError("prompt control role drifted")
    expected_targets = tuple(
        entry.transition_control_id for entry in fixture.binding.transition_bindings
    )
    expected_names = tuple(
        entry.public_name for entry in fixture.binding.transition_bindings
    )
    if controls and (
        tuple(row["target_id"] for row in controls) != expected_targets
        or tuple(row["operator_name"] for row in controls) != expected_names
    ):
        raise BridgeSchemaError("prompt control target order drifted")


def _validate_projection_provenance(
    provenance: Mapping[str, Any],
    fixture: ControlledRawRestartFixture,
    controls: Sequence[Mapping[str, Any]],
) -> None:
    if set(provenance) != _PROVENANCE_FIELDS:
        raise BridgeSchemaError("external projection provenance escaped its allowlist")
    if provenance.get("projected_controls_fingerprint_sha256") != fingerprint(controls):
        raise BridgeSchemaError("external projected-control fingerprint mismatch")
    if provenance.get("case_fingerprint_sha256") != (
        fixture.source_case_fingerprint_sha256
    ) or provenance.get("binding_fingerprint_sha256") != (
        fixture.binding_fingerprint_sha256
    ):
        raise BridgeSchemaError("external provenance case/binding fingerprint drifted")
    if (
        provenance.get("fixture_id") != fixture.fixture_id
        or provenance.get("case_id") != fixture.case.case_id
    ):
        raise BridgeSchemaError("external provenance fixture/case identity drifted")


def build_arm_bundle(
    fixture: ControlledRawRestartFixture,
) -> dict[str, ArmProjection]:
    suite = build_case_temporal_suite(fixture)
    program = suite.materialize(fixture.binding.pair_id, fixture.binding.order_variant)
    program_fingerprint = fingerprint(_program_descriptor(program))
    controller = TemporalAdjointStateController()
    result = controller.optimize(program, "transition")
    source_map = result.to_execution_control_map()
    _verify_source_control_map(source_map, program)
    source_map_fingerprint = str(source_map["fingerprint_sha256"])
    source_deltas = {
        str(row["target_id"]): float(row["delta"]) for row in source_map["controls"]
    }
    transition_ids = tuple(program.transition_control_ids)
    zero_deltas = {target: 0.0 for target in transition_ids}
    permutation = fixture.binding.sham_source_index_by_target
    permuted_deltas = {
        target: source_deltas[transition_ids[permutation[index]]]
        for index, target in enumerate(transition_ids)
    }
    arm_deltas = {
        ARM_ZERO: zero_deltas,
        ARM_TEXTUAL: zero_deltas,
        ARM_PERMUTATION: permuted_deltas,
        ARM_GRADIENT: source_deltas,
    }
    guidance_modes = {
        ARM_ZERO: "raw_only_full_context",
        ARM_TEXTUAL: "textual_revision_only",
        ARM_PERMUTATION: "matched_permutation_temporal_control",
        ARM_GRADIENT: "gradient_temporal_control",
    }
    output: dict[str, ArmProjection] = {}
    for arm_id in ARM_ORDER:
        projected_rows = _project_control_rows(
            program=program,
            deltas_by_target=arm_deltas[arm_id],
            role_delta=controller.config.role_delta,
            precision=fixture.projection_policy.numeric_precision,
        )
        event_active = fixture.binding.event.triggered
        provider_rows = (
            projected_rows
            if event_active and arm_id in {ARM_PERMUTATION, ARM_GRADIENT}
            else []
        )
        rows_fingerprint = fingerprint(provider_rows)
        guidance_mode = guidance_modes[arm_id] if event_active else "no_event_identity"
        provenance = {
            "fixture_id": fixture.fixture_id,
            "case_id": fixture.case.case_id,
            "binding_id": fixture.binding.binding_id,
            "event_id": fixture.binding.event.event_id,
            "event_triggered": event_active,
            "case_fingerprint_sha256": fixture.source_case_fingerprint_sha256,
            "binding_fingerprint_sha256": fixture.binding_fingerprint_sha256,
            "semantic_payload_sha256": program.semantic_payload_sha256,
            "program_fingerprint_sha256": program_fingerprint,
            "source_control_map_fingerprint_sha256": source_map_fingerprint,
            "projected_controls_fingerprint_sha256": rows_fingerprint,
            "source_control_status": source_map["status"],
        }
        envelope = (
            {
                "schema_version": ENVELOPE_SCHEMA_VERSION,
                "revision_context": _revision_context(fixture),
                "temporal_controls": provider_rows,
                "instructions_fragment": _COMMON_INSTRUCTIONS_FRAGMENT,
            }
            if event_active and arm_id != ARM_ZERO
            else None
        )
        if envelope is not None:
            _validate_prompt_envelope(envelope, fixture)
        _validate_projection_provenance(provenance, fixture, provider_rows)
        output[arm_id] = ArmProjection(
            arm_id=arm_id,
            guidance_mode=guidance_mode,
            prompt_envelope=envelope,
            provenance=provenance,
            source_case_fingerprint_sha256=fixture.source_case_fingerprint_sha256,
            binding_fingerprint_sha256=fixture.binding_fingerprint_sha256,
            program_fingerprint_sha256=program_fingerprint,
            source_control_map_fingerprint_sha256=source_map_fingerprint,
            projected_controls_fingerprint_sha256=rows_fingerprint,
        )
    if fixture.binding.event.triggered:
        gradient_values = sorted(
            row["delta"]
            for row in output[ARM_GRADIENT].prompt_envelope["temporal_controls"]
        )
        sham_values = sorted(
            row["delta"]
            for row in output[ARM_PERMUTATION].prompt_envelope["temporal_controls"]
        )
        if gradient_values != sham_values:
            raise BridgeSchemaError(
                "matched permutation changed the control-value multiset"
            )
    return output


def _resolve_projection(
    fixture: ControlledRawRestartFixture,
    arm: str | ArmProjection,
) -> ArmProjection:
    if isinstance(arm, ArmProjection):
        if arm.arm_id not in ARM_ORDER:
            raise BridgeSchemaError("unknown ArmProjection arm_id")
        expected = build_arm_bundle(fixture)[arm.arm_id]
        if canonical_json_bytes(arm.to_dict()) != canonical_json_bytes(
            expected.to_dict()
        ):
            raise BridgeSchemaError(
                "ArmProjection drifted from its exact arm projection"
            )
        return arm
    if arm not in ARM_ORDER:
        raise BridgeSchemaError(f"unknown controlled-restart arm: {arm!r}")
    return build_arm_bundle(fixture)[arm]


def _walk_mappings(value: Any) -> Iterator[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        yield value
        for child in value.values():
            yield from _walk_mappings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_mappings(child)


def _validate_raw_payload(
    payload: Mapping[str, Any], fixture: ControlledRawRestartFixture
) -> None:
    expected = [entry.public_dict() for entry in fixture.case.all_evidence]
    if payload.get("all_raw_evidence") != expected:
        raise BridgeSchemaError("restart payload raw evidence drifted from exact order")
    all_raw_keys = sum("all_raw_evidence" in item for item in _walk_mappings(payload))
    if all_raw_keys != 1:
        raise BridgeSchemaError("all_raw_evidence must occur exactly once")
    outside = dict(payload)
    outside.pop("all_raw_evidence", None)
    raw_pairs = {(entry.evidence_id, entry.text) for entry in fixture.case.all_evidence}
    for item in _walk_mappings(outside):
        if (item.get("evidence_id"), item.get("text")) in raw_pairs:
            raise BridgeSchemaError(
                "raw evidence was duplicated outside all_raw_evidence"
            )
    _reject_forbidden_keys(payload)


def build_restart_payload(
    fixture: ControlledRawRestartFixture,
    arm: str | ArmProjection,
) -> dict[str, Any]:
    projection = _resolve_projection(fixture, arm)
    payload = {
        "schema_version": REQUEST_SCHEMA_VERSION,
        "case_id": fixture.case.case_id,
        "question": fixture.case.question,
        "answer_choices": list(fixture.case.answer_choices),
        "decision_slots": [entry.to_dict() for entry in fixture.case.decision_slots],
        "checkpoint_id": f"{fixture.case.case_id}:full_context_final",
        "all_raw_evidence": [
            entry.public_dict() for entry in fixture.case.all_evidence
        ],
        "allowed_evidence_ids": list(fixture.case.evidence_ids),
        "revision_control_envelope": (
            None
            if projection.prompt_envelope is None
            else copy.deepcopy(dict(projection.prompt_envelope))
        ),
    }
    _validate_raw_payload(payload, fixture)
    return payload


def _provider_receipt(value: Mapping[str, Any]) -> ProviderReceipt:
    usage = value.get("usage")
    if not isinstance(usage, Mapping):
        raise BridgeSchemaError("provider receipt usage must be an object")
    return ProviderReceipt(
        provider=str(value["provider"]),
        requested_model=value.get("requested_model"),
        returned_model=value.get("returned_model"),
        logical_calls=int(value["logical_calls"]),
        api_calls=int(value["api_calls"]),
        latency_ms=float(value["latency_ms"]),
        request_fingerprint=str(value["request_fingerprint"]),
        prompt_fingerprint=str(value["prompt_fingerprint"]),
        usage=ProviderUsage(**dict(usage)),
        metadata=dict(value.get("metadata", {})),
    )


def _validator_context(fixture: ControlledRawRestartFixture) -> Any:
    event = fixture.binding.event
    return v041.FixedRevisionEnvelope(
        late_evidence=fixture.case.late_evidence,
        topic="controlled_raw_restart_validator_bound",
        stance=0.0,
        confidence=1.0,
        revision_cue=event.revision_cue,
        relevant=event.relevant,
        invalidated_evidence_ids=event.invalidated_evidence_ids,
        public_summary="validator-only public event bound",
    )


def validate_public_card(
    fixture: ControlledRawRestartFixture,
    arm: str | ArmProjection,
    card_value: Mapping[str, Any],
    receipt_value: Mapping[str, Any] | None = None,
) -> ReasoningCard:
    """Apply the stable v0.4.2 local contract; perform no correctness grading."""

    projection = _resolve_projection(fixture, arm)
    payload = build_restart_payload(fixture, projection)
    card = ReasoningCard.from_mapping(card_value)
    if receipt_value is None:
        receipt = ProviderReceipt(
            provider="local_contract_validation",
            requested_model=None,
            returned_model=None,
            logical_calls=0,
            api_calls=0,
            latency_ms=0.0,
            request_fingerprint=fingerprint(payload),
            prompt_fingerprint=fingerprint(projection.instructions_fragment),
            usage=ProviderUsage(exact_provider_tokens=False),
            metadata={"attempt_outcome": "local_validation_only"},
        )
    else:
        receipt = _provider_receipt(receipt_value)
    result = CardResult(card=card, receipt=receipt)
    v042._validate_mapping_result(
        fixture.case,
        _validator_context(fixture),
        payload,
        result,
        seen_raw_ids=fixture.case.evidence_ids,
    )
    return card


def _support_ids(card: ReasoningCard) -> list[str]:
    output: list[str] = []
    for evidence_id in card.evidence_ids:
        if evidence_id not in output:
            output.append(evidence_id)
    for fact in card.decision_facts:
        for evidence_id in fact.evidence_ids:
            if evidence_id not in output:
                output.append(evidence_id)
    return output


def _ordered(values: Sequence[str], source_order: Sequence[str]) -> list[str]:
    order = {value: index for index, value in enumerate(source_order)}
    return sorted(set(values), key=lambda value: (order.get(value, len(order)), value))


def public_card_diff(
    fixture: ControlledRawRestartFixture,
    before_value: Mapping[str, Any],
    after_value: Mapping[str, Any],
) -> dict[str, Any]:
    before = ReasoningCard.from_mapping(before_value)
    after = ReasoningCard.from_mapping(after_value)
    slot_order = [entry.slot_id for entry in fixture.case.decision_slots]
    evidence_order = list(fixture.case.evidence_ids)
    before_facts = {entry.slot: entry for entry in before.decision_facts}
    after_facts = {entry.slot: entry for entry in after.decision_facts}
    fact_changes: list[dict[str, Any]] = []
    for slot in slot_order:
        old = before_facts.get(slot)
        new = after_facts.get(slot)
        old_public = (
            None
            if old is None
            else {"value": old.value, "evidence_ids": list(old.evidence_ids)}
        )
        new_public = (
            None
            if new is None
            else {"value": new.value, "evidence_ids": list(new.evidence_ids)}
        )
        if old_public != new_public:
            fact_changes.append(
                {"slot": slot, "before": old_public, "after": new_public}
            )
    before_support = _support_ids(before)
    after_support = _support_ids(after)
    return {
        "answer_before": before.current_answer,
        "answer_after": after.current_answer,
        "answer_changed": before.current_answer != after.current_answer,
        "support_before_ids": _ordered(before_support, evidence_order),
        "support_after_ids": _ordered(after_support, evidence_order),
        "support_added_ids": _ordered(
            set(after_support) - set(before_support), evidence_order
        ),
        "support_dropped_ids": _ordered(
            set(before_support) - set(after_support), evidence_order
        ),
        "invalidated_added_ids": _ordered(
            set(after.invalidated_evidence_ids) - set(before.invalidated_evidence_ids),
            evidence_order,
        ),
        "invalidated_dropped_ids": _ordered(
            set(before.invalidated_evidence_ids) - set(after.invalidated_evidence_ids),
            evidence_order,
        ),
        "decision_fact_changes": fact_changes,
        "derived_from": "public_reasoning_cards_only",
    }


def _refresh_fixture_fingerprints(raw: dict[str, Any]) -> None:
    case = CaseSpec.from_mapping(raw["case"])
    binding = raw["case_program_binding"]
    program_material = copy.deepcopy(binding)
    program_material.pop("program_spec_fingerprint_sha256", None)
    binding["program_spec_fingerprint_sha256"] = fingerprint(program_material)
    raw["source_case_fingerprint_sha256"] = fingerprint(case.trace_dict())
    raw["binding_fingerprint_sha256"] = fingerprint(binding)
    raw["fixture_fingerprint_sha256"] = fingerprint(
        _fixture_material_without_fingerprint(raw)
    )


def _recursive_diff_paths(before: Any, after: Any, path: str = "") -> tuple[str, ...]:
    """Return deterministic JSON-pointer-like paths whose public values differ."""

    if type(before) is not type(after):
        return (path or "/",)
    if isinstance(before, Mapping):
        output: list[str] = []
        for key in sorted(set(before) | set(after), key=str):
            child = f"{path}/{key}"
            if key not in before or key not in after:
                output.append(child)
            else:
                output.extend(_recursive_diff_paths(before[key], after[key], child))
        return tuple(output)
    if isinstance(before, list):
        output = []
        if len(before) != len(after):
            output.append(f"{path}/#length")
        for index, (before_item, after_item) in enumerate(zip(before, after)):
            output.extend(
                _recursive_diff_paths(
                    before_item,
                    after_item,
                    f"{path}/{index}",
                )
            )
        return tuple(output)
    return () if before == after else (path or "/",)


def _fixture_from_raw_for_self_test(raw: dict[str, Any]) -> ControlledRawRestartFixture:
    _refresh_fixture_fingerprints(raw)
    with mock.patch.object(Path, "read_text", return_value=json.dumps(raw)):
        return load_bridge_fixture(Path("self-test-fixture.json"))


def _card_payload(
    checkpoint_id: str,
    *,
    answer: str,
    current_code: str,
    bay: str,
    active_ids: Sequence[str],
    invalidated_ids: Sequence[str],
) -> dict[str, Any]:
    return {
        "schema_version": "ebrt-public-reasoning-card-v0.4",
        "checkpoint_id": checkpoint_id,
        "claim": "A compact public contract-test card.",
        "topic": "route_contract_test",
        "stance": 0.0,
        "confidence": 0.8,
        "evidence_ids": list(active_ids),
        "current_answer": answer,
        "revision_cue": 1.0,
        "decision_facts": [
            {"slot": "current_code", "value": current_code, "evidence_ids": ["R6"]},
            {"slot": "bay", "value": bay, "evidence_ids": ["R2", "R6"]},
            {"slot": "cargo_seal", "value": "SEALED", "evidence_ids": ["R5"]},
        ],
        "invalidated_evidence_ids": list(invalidated_ids),
    }


def run_self_tests(path: Path = DEFAULT_FIXTURE_PATH) -> dict[str, Any]:
    fixture = load_bridge_fixture(path)
    with mock.patch.object(
        socket, "socket", side_effect=AssertionError("network used")
    ):
        first = build_arm_bundle(fixture)
        second = build_arm_bundle(fixture)
        payloads = {
            arm: build_restart_payload(fixture, first[arm]) for arm in ARM_ORDER
        }
    if canonical_json_bytes({key: value.to_dict() for key, value in first.items()}) != (
        canonical_json_bytes({key: value.to_dict() for key, value in second.items()})
    ):
        raise AssertionError("arm projection is not deterministic")
    if tuple(first) != ARM_ORDER:
        raise AssertionError("arm order drifted")
    if len({item.program_fingerprint_sha256 for item in first.values()}) != 1:
        raise AssertionError("arms did not share one case-specific temporal program")
    if (
        len({item.source_control_map_fingerprint_sha256 for item in first.values()})
        != 1
    ):
        raise AssertionError("arms did not share one source control map")
    expected_checkpoint_id = f"{fixture.case.case_id}:full_context_final"
    for arm_id, payload in payloads.items():
        _validate_raw_payload(payload, fixture)
        if payload["checkpoint_id"] != expected_checkpoint_id:
            raise AssertionError("provider checkpoint id exposed arm identity")
        envelope = payload["revision_control_envelope"]
        if arm_id == ARM_ZERO:
            if envelope is not None:
                raise AssertionError("raw-only arm received a revision envelope")
            continue
        if not isinstance(envelope, Mapping):
            raise AssertionError("guided arm is missing its public envelope")
        if set(envelope) != _ENVELOPE_FIELDS:
            raise AssertionError("provider envelope escaped its blinded allowlist")
        if envelope["instructions_fragment"] != _COMMON_INSTRUCTIONS_FRAGMENT:
            raise AssertionError("provider instruction fragment differs by arm")
        if any(
            key in envelope
            for key in ("arm_id", "guidance_mode", "source", "provenance")
        ):
            raise AssertionError("provider envelope exposed external arm metadata")
    for arm_id, projection in first.items():
        external = projection.to_dict()
        if external["arm_id"] != arm_id or external["guidance_mode"] != (
            projection.guidance_mode
        ):
            raise AssertionError("external projection lost arm identity")
        if set(external["provenance"]) != _PROVENANCE_FIELDS:
            raise AssertionError("external projection lost source provenance")
    textual_rows = first[ARM_TEXTUAL].prompt_envelope["temporal_controls"]
    if textual_rows:
        raise AssertionError("textual-only arm exposed temporal control rows")
    if first[ARM_TEXTUAL].prompt_envelope["revision_context"] != _revision_context(
        fixture
    ):
        raise AssertionError("textual-only arm lost its public revision context")
    gradient_rows = first[ARM_GRADIENT].prompt_envelope["temporal_controls"]
    sham_rows = first[ARM_PERMUTATION].prompt_envelope["temporal_controls"]
    gradient_by_target = {row["target_id"]: row["delta"] for row in gradient_rows}
    sham_by_target = {row["target_id"]: row["delta"] for row in sham_rows}
    if sorted(gradient_by_target.values()) != sorted(sham_by_target.values()):
        raise AssertionError("matched permutation changed control values")
    if gradient_by_target == sham_by_target:
        raise AssertionError("matched permutation collapsed to identity")
    sham_gradient_diff = set(
        _recursive_diff_paths(payloads[ARM_PERMUTATION], payloads[ARM_GRADIENT])
    )
    expected_sham_gradient_diff = {
        f"/revision_control_envelope/temporal_controls/{index}/{field}"
        for index, (sham_row, gradient_row) in enumerate(zip(sham_rows, gradient_rows))
        for field in ("delta", "role")
        if sham_row[field] != gradient_row[field]
    }
    if not sham_gradient_diff or sham_gradient_diff != expected_sham_gradient_diff:
        raise AssertionError(
            "matched/gradient provider payload difference escaped row delta/role: "
            f"{sorted(sham_gradient_diff)}"
        )
    tampered_projection = copy.deepcopy(first[ARM_GRADIENT])
    tampered_projection.prompt_envelope["temporal_controls"][0]["delta"] = 0.0
    try:
        build_restart_payload(fixture, tampered_projection)
    except BridgeSchemaError:
        pass
    else:
        raise AssertionError("tampered blinded ArmProjection was accepted")
    valid = _card_payload(
        payloads[ARM_GRADIENT]["checkpoint_id"],
        answer="AMBER",
        current_code="B2",
        bay="AMBER",
        active_ids=("R2", "R5", "R6"),
        invalidated_ids=("R3",),
    )
    validate_public_card(fixture, first[ARM_GRADIENT], valid)
    invalid = copy.deepcopy(valid)
    invalid["evidence_ids"].append("R3")
    try:
        validate_public_card(fixture, first[ARM_GRADIENT], invalid)
    except v042.LocalContractViolation as error:
        if error.reason_code != "invalidated_active_support":
            raise AssertionError("stable local reason code drifted") from error
    else:
        raise AssertionError("invalidated support escaped stable local validation")
    before = copy.deepcopy(valid)
    before["checkpoint_id"] = payloads[ARM_ZERO]["checkpoint_id"]
    before["current_answer"] = "AMBER"
    before["decision_facts"][0]["value"] = "A1"
    before["decision_facts"][0]["evidence_ids"] = ["R3"]
    before["decision_facts"][1]["value"] = "AMBER"
    before["decision_facts"][1]["evidence_ids"] = ["R2", "R3"]
    before["evidence_ids"] = ["R2", "R3", "R5"]
    before["invalidated_evidence_ids"] = []
    after = copy.deepcopy(valid)
    after["current_answer"] = "BLUE"
    after["decision_facts"][1]["value"] = "BLUE"
    diff_one = public_card_diff(fixture, before, after)
    diff_two = public_card_diff(fixture, before, after)
    if diff_one != diff_two or not diff_one["answer_changed"]:
        raise AssertionError("public-card diff is not deterministic")
    raw = _load_json_exact(path)
    tampered = copy.deepcopy(raw)
    tampered["case_program_binding"]["terminal_decision_target"] = 0.1
    try:
        _fixture_from_raw_for_self_test(
            {
                **tampered,
                "fixture_fingerprint_sha256": raw["fixture_fingerprint_sha256"],
            }
        )
    except BridgeSchemaError:
        pass
    else:
        # _fixture_from_raw refreshes declarations intentionally; test the real
        # stale-declaration path separately below.
        stale_path_value = copy.deepcopy(raw)
        stale_path_value["case_program_binding"]["terminal_decision_target"] = 0.1
        with mock.patch.object(
            Path, "read_text", return_value=json.dumps(stale_path_value)
        ):
            try:
                load_bridge_fixture(Path("stale-self-test.json"))
            except BridgeSchemaError:
                pass
            else:
                raise AssertionError("stale binding fingerprint was accepted")
    control_map = (
        TemporalAdjointStateController()
        .optimize(
            build_case_temporal_suite(fixture).materialize(
                fixture.binding.pair_id, fixture.binding.order_variant
            ),
            "transition",
        )
        .to_execution_control_map()
    )
    control_map["controls"][0]["delta"] = 0.123
    try:
        _verify_source_control_map(
            control_map,
            build_case_temporal_suite(fixture).materialize(
                fixture.binding.pair_id, fixture.binding.order_variant
            ),
        )
    except BridgeSchemaError:
        pass
    else:
        raise AssertionError("tampered control map fingerprint was accepted")
    no_event_raw = _load_json_exact(path)
    no_event_raw["fixture_id"] = f"{no_event_raw['fixture_id']}_no_event_self_test"
    no_event_raw["case_program_binding"]["event"]["triggered"] = False
    no_event_raw["case_program_binding"]["event"]["relevant"] = False
    no_event_raw["case_program_binding"]["event"]["revision_cue"] = 0.0
    no_event_raw["case_program_binding"]["event"]["invalidated_evidence_ids"] = []
    no_event_fixture = _fixture_from_raw_for_self_test(no_event_raw)
    no_event_arms = build_arm_bundle(no_event_fixture)
    for projection in no_event_arms.values():
        if projection.prompt_envelope is not None:
            raise AssertionError("no-event projection was not raw-only identity")
        if projection.provenance["source_control_status"] != "NO_EVENT_IDENTITY":
            raise AssertionError("no-event control source did not remain identity")
        if projection.projected_controls_fingerprint_sha256 != fingerprint([]):
            raise AssertionError("no-event projection retained provider controls")
    no_event_payloads = {
        arm: build_restart_payload(no_event_fixture, projection)
        for arm, projection in no_event_arms.items()
    }
    if len({canonical_json_bytes(value) for value in no_event_payloads.values()}) != 1:
        raise AssertionError("no-event provider payloads exposed arm identity")
    forbidden = _load_json_exact(path)
    forbidden["case_program_binding"]["gold"] = "forbidden"
    with mock.patch.object(Path, "read_text", return_value=json.dumps(forbidden)):
        try:
            load_bridge_fixture(Path("forbidden-self-test.json"))
        except BridgeSchemaError:
            pass
        else:
            raise AssertionError("forbidden gold field escaped fixture validation")
    return {
        "status": "PASS",
        "fixture_id": fixture.fixture_id,
        "case_id": fixture.case.case_id,
        "arms": list(ARM_ORDER),
        "program_fingerprint_sha256": first[ARM_GRADIENT].program_fingerprint_sha256,
        "source_control_map_fingerprint_sha256": (
            first[ARM_GRADIENT].source_control_map_fingerprint_sha256
        ),
        "checks": [
            "exact case-program binding and source fingerprints",
            "case-specific v0.5-T program materialization",
            "raw-only arm receives no revision-control envelope",
            "textual-only arm receives revision context without control rows",
            "guided envelopes expose no arm labels or provenance fingerprints",
            "matched/gradient differ only at control-row delta and role",
            "matched permutation preserves the control-value multiset",
            "ordered cumulative raw context appears exactly once",
            "stable v0.4.2 local public-card reason codes",
            "deterministic public-card-only output diff",
            "stale fixture and control-map fingerprints are rejected",
            "no-event projection is exact identity",
            "pure bridge completes while sockets are denied",
        ],
        "claim_boundary": (
            "Network-free, gold-free projection over an explicit DEV oracle binding; "
            "no hosted-model improvement is established."
        ),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    self_test = subparsers.add_parser("self-test")
    self_test.add_argument("--input-json", type=Path, default=DEFAULT_FIXTURE_PATH)
    validate = subparsers.add_parser("validate")
    validate.add_argument("--input-json", type=Path, default=DEFAULT_FIXTURE_PATH)
    inspect = subparsers.add_parser("inspect")
    inspect.add_argument("--input-json", type=Path, default=DEFAULT_FIXTURE_PATH)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "self-test":
        output = run_self_tests(args.input_json)
    else:
        fixture = load_bridge_fixture(args.input_json)
        if args.command == "validate":
            build_case_temporal_suite(fixture)
            output = {
                "status": "PASS",
                "fixture_id": fixture.fixture_id,
                "fixture_fingerprint_sha256": fixture.fixture_fingerprint_sha256,
            }
        else:
            output = {
                "fixture_id": fixture.fixture_id,
                "arms": {
                    key: value.to_dict()
                    for key, value in build_arm_bundle(fixture).items()
                },
            }
    print(
        json.dumps(
            output, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
