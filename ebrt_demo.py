#!/usr/bin/env python3
"""Read one real, network-zero EBRT backward revision as text or JSON.

The public trajectory is computed by the current core. Generation uses the
same fixed test double in both arms; its output cannot demonstrate model
quality or a causal effect of backward credit.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Mapping, Sequence

from ebrt_core import (
    AdapterDescriptor,
    CallableModelAdapter,
    EBRTError,
    _parse_model_text,
    _seal,
    build_demo_contract,
    build_demo_task,
)
from ebrt_engine import RevisionEngine
from local_output_diff_corpus_v0_8_2 import (
    _common_output_grade,
    build_direct_invocation,
)


SCHEMA_VERSION = "ebrt-comparison-demo-v1"
SCRIPTED_REPLY = "ANSWER=PROVE\nSUPPORT=R6,R4,R2"


def _prompt_records(invocation: Mapping[str, Any]) -> tuple[list[Any], list[Any]]:
    """Compare actual model-visible data, allowing different evidence order."""
    lines = str(invocation["prompt"]).splitlines()
    headers = [json.loads(line[10:]) for line in lines if line.startswith("TASK_JSON ")]
    evidence = [
        json.loads(line[14:]) for line in lines if line.startswith("EVIDENCE_JSON ")
    ]
    return headers, sorted(evidence, key=lambda row: row["evidence_id"])


def run_demo() -> dict[str, Any]:
    """Run the existing synthetic fixture without changing the core or its gold."""
    task = build_demo_task()
    contract = build_demo_contract()
    requests: list[dict[str, Any]] = []

    def scripted_reply(invocation: Mapping[str, Any]) -> str:
        requests.append(json.loads(json.dumps(invocation)))
        # Intentionally ignores both prompts. Never manufacture a baseline loss.
        return SCRIPTED_REPLY

    descriptor = AdapterDescriptor(
        adapter_id="comparison-demo-scripted",
        model_id="deterministic/fixed-reply@v1",
        interface_kind="deterministic_conformance",
        state_visibility="public_only",
        differentiable_through_model=False,
    )
    direct_invocation = build_direct_invocation(task)
    direct_text = scripted_reply(direct_invocation)
    direct_answer, direct_support = _parse_model_text(direct_text, task=task)
    engine_result = RevisionEngine().run(
        task,
        CallableModelAdapter(descriptor=descriptor, callback=scripted_reply),
        post_run_contract=contract,
    )
    ebrt_invocation = requests[-1]
    outputs = {
        "direct_full_context": {
            "answer": direct_answer,
            "support_ids": list(direct_support),
            "raw_text": direct_text,
        },
        "ebrt_credit_first": {
            key: engine_result["model_result"][key]
            for key in ("answer", "support_ids", "raw_text")
        },
    }
    headers, evidence = _prompt_records(direct_invocation)
    expected_evidence = sorted(
        [{"evidence_id": row.evidence_id, "text": row.text} for row in task.evidence],
        key=lambda row: row["evidence_id"],
    )
    matched = {
        "same_task_and_full_evidence": (headers, evidence)
        == _prompt_records(ebrt_invocation),
        "complete_evidence_including_late_correction": evidence == expected_evidence,
        "direct_has_no_external_actuator": "actuator_program" not in direct_invocation,
        "same_scripted_generator_called_twice": len(requests) == 2,
    }
    if not all(matched.values()):
        raise EBRTError("DEMO_COMPARISON_INPUT_MISMATCH")

    arms = {}
    for name, invocation in (
        ("direct_full_context", direct_invocation),
        ("ebrt_credit_first", ebrt_invocation),
    ):
        output = outputs[name]
        arms[name] = {
            "invocation": invocation,
            "output": output,
            # Both arms use the same output-only grade. The core's separate
            # post-run receipt also checks compiled preservation constraints.
            "output_grade": _common_output_grade({"status": "PARSED", **output}, contract),
        }
    checks_pass = (
        engine_result["status"] == "PASS"
        and engine_result["post_run_contract"]["status"] == "PASS"
        and all(arm["output_grade"]["status"] == "PASS" for arm in arms.values())
    )
    return _seal(
        {
            "schema_version": SCHEMA_VERSION,
            "status": "PASS" if checks_pass else "FAIL",
            "evidence_label": "CONFORMANCE_ONLY",
            "engine_protocol": engine_result["engine_protocol"],
            "actuator_policy": engine_result["actuator_policy"],
            "task": task.to_public_dict(),
            "generator": {
                "adapter": descriptor.to_dict(),
                "behavior": "Fixed reply, independent of prompt and controls, in both arms.",
                "timing": "Omitted from this deterministic report; no timing comparison.",
            },
            "trajectory": engine_result["trajectory"],
            "actuator": engine_result["actuator"],
            "arms": arms,
            "output_diff": {
                "answer_changed": outputs["direct_full_context"]["answer"]
                != outputs["ebrt_credit_first"]["answer"],
                "support_changed": set(outputs["direct_full_context"]["support_ids"])
                != set(outputs["ebrt_credit_first"]["support_ids"]),
                "raw_text_changed": direct_text != outputs["ebrt_credit_first"]["raw_text"],
            },
            "verification": {
                "structural": engine_result["structural_verification"],
                "post_run_contract": engine_result["post_run_contract"],
                "matched_inputs": matched,
            },
            "external_model_execution_status": "NOT_RUN",
            "effect_attribution_status": "NOT_ASSESSED",
            "claim_boundary": [
                "Known synthetic fixture; not a fresh benchmark.",
                "Loss and credit describe a hand-built public surrogate, not private model reasoning.",
                "Revised rows replay past sites after the late event; they do not change the original history.",
                "Both full-context prompts contain the late correction; only EBRT carries the revision program and credit-first order.",
                "The fixed scripted outputs demonstrate wiring, not generator uptake or reasoning improvement.",
            ],
        }
    )


def render_text(report: Mapping[str, Any]) -> str:
    task = report["task"]
    trajectory = report["trajectory"]
    before_ids = set(task["before_horizon_evidence_ids"])
    event_id = task["event"]["correction_evidence_id"]
    late = next(row for row in task["evidence"] if row["evidence_id"] == event_id)
    lines = [
        "EBRT | one late correction, one real backward pass",
        "CONFORMANCE_ONLY | no API key or model download required",
        f"Actuator policy: {report['actuator_policy']}",
        "",
        "1. Input and original decision",
        f"   {task['question']}",
        f"   Prior answer: {task['prior_state']['answer']}",
        f"   Prior support: {','.join(task['prior_state']['active_support_ids'])}",
    ]
    lines.extend(
        f"   {row['evidence_id']}: {row['text']}"
        for row in task["evidence"]
        if row["evidence_id"] in before_ids
    )
    lines.extend(
        [
            "",
            f"2. Late event at step {late['ordinal']}",
            f"   {event_id}: {late['text']}",
            "",
            "3. Backward credit and bounded controls",
            "   Step  Evidence  Role                  Gradient    Control",
        ]
    )
    for row in trajectory["credit_map"]:
        lines.append(
            f"   {row['step']:>4}  {row['evidence_id']:<8}  {row['role']:<20}"
            f"  {row['gradient']:>+9.6f}  {row['control']:>+9.6f}"
        )
    lines.extend(
        [
            f"   Control L2: {trajectory['control_l2']:.6f} / {trajectory['control_budget']:.6f}",
            "",
            "4. Replay after the event: public surrogate states",
            "   State axes: revision, invalidation, stability",
            "   Evidence     Zero control                 EBRT control",
        ]
    )
    for neutral, revised in zip(
        trajectory["neutral"]["trajectory"],
        trajectory["revised"]["trajectory"],
        strict=True,
    ):
        def state_text(row: Mapping[str, Any]) -> str:
            return ", ".join(f"{row['state'][axis]:+.3f}" for axis in trajectory["axis_ids"])

        lines.append(
            f"   {neutral['evidence_id']:<8}  ({state_text(neutral)})  ({state_text(revised)})"
        )
    lines.extend(
        [
            f"   Surrogate objective: {trajectory['neutral']['loss']['total']:.6f}"
            f" -> {trajectory['revised']['loss']['total']:.6f}",
            "   These are post-event replays, not edits to the original history.",
            "",
            "5. Compiled revision program",
        ]
    )
    actuator = report["actuator"]
    lines.extend(
        f"   REINSPECT {row['evidence_id']}: {row['allocation_units']} allocation units"
        for row in actuator["reinspect"]
    )
    lines.extend(
        [
            f"   SUPPRESS {','.join(actuator['suppress_evidence_ids'])}",
            f"   PRESERVE {','.join(actuator['preserve_evidence_ids'])}",
            "",
            "6. Full-context generation: SAME fixed scripted reply in both arms",
            "   Arm                    Answer  Support   Output contract",
        ]
    )
    for name, arm in report["arms"].items():
        output = arm["output"]
        lines.append(
            f"   {name:<22} {output['answer']:<7} {','.join(output['support_ids']):<9}"
            f" {arm['output_grade']['status']}"
        )
    diff = report["output_diff"]
    lines.extend(
        [
            f"   Output changed: answer={diff['answer_changed']}, support={diff['support_changed']}",
            "   The test double ignores prompts; output equality is expected.",
            "",
            f"Checks: mechanism={'PASS' if all(trajectory['checks'].values()) else 'FAIL'}, "
            f"structure={report['verification']['structural']['status']}, "
            f"post-run contract={report['verification']['post_run_contract']['status']}",
            f"Result: {report['status']} | effect attribution: {report['effect_attribution_status']}",
            "Known synthetic fixture. No real-model quality or causal improvement claim.",
            "Use --json for complete trajectories, prompts, checks, and fingerprints.",
        ]
    )
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="print a deterministic JSON report")
    args = parser.parse_args(argv)
    try:
        report = run_demo()
    except EBRTError as error:
        if args.json:
            print(json.dumps({"status": "ERROR", "reason_code": str(error)}))
        else:
            print(f"EBRT demo failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
          if args.json else render_text(report), end="\n" if args.json else "")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
