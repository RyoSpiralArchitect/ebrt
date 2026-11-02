#!/usr/bin/env python3
"""V0.9.1 delayed terminal credit: network-zero proof plus sealed Responses pilot.

Separate research canary; does not replace the EBRT mainline core. Public
linear dynamics are fully specified and known to the controller. The hosted
comparison measures answer/support changes, not native-model gradients.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import tempfile
from pathlib import Path
from typing import Any

import torch

DTYPE = torch.float64
SCHEMA = "ebrt-delayed-terminal-credit-v0.9.1"
INSTRUCTIONS = (
    "Compute the updated integer output from the visible evidence. Return only "
    "the specified JSON fields. Include the two transformation records and "
    "the late event as support, and include input receipts precisely when their "
    "net algebraic coefficient in the updated terminal output is nonzero. "
    "A zero coefficient after cancellation is not support. Do not include the "
    "obsolete selector record. Review allocation is not evidence or an answer."
)
CASES = (
    {"id":"shifted_readout","x":[3,5,2],"A":[[1,1,0],[0,1,1],[1,0,1]],
     "B":[[2,-1,0],[0,1,1],[1,0,-1]],"old":[1,0,0],"new":[0,0,1],"bias":2},
    {"id":"merged_register","x":[4,2,7],"A":[[1,0,1],[1,1,0],[0,2,1]],
     "B":[[1,1,0],[0,1,-1],[1,-1,0]],"old":[0,1,0],"new":[1,0,0],"bias":-3},
    {"id":"cancelled_branch","x":[2,6,4],"A":[[2,1,0],[0,1,2],[1,0,1]],
     "B":[[1,0,1],[1,-1,0],[0,1,1]],"old":[0,0,1],"new":[0,1,0],"bias":4},
)
ARMS = ("direct", "scrambled", "adjoint")
SCHEDULE = ((0,"direct"),(0,"scrambled"),(0,"adjoint"),
            (1,"scrambled"),(1,"adjoint"),(1,"direct"),
            (2,"adjoint"),(2,"direct"),(2,"scrambled"))
IDS = ("E_A", "E_B", "E_C", "E_T1", "E_T2", "E_OLD", "E_EVENT")
OUTPUT_FORMAT = {"type":"json_schema","name":"delayed_credit_output",
    "schema":{"type":"object","additionalProperties":False,
              "properties":{"answer":{"type":"string"},
                            "support_ids":{"type":"array","items":{"type":"string"}}},
              "required":["answer","support_ids"]},"strict":True}


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def sha(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def sealed(value: dict) -> dict:
    return {**value, "fingerprint_sha256":sha(value)}


def check_seal(value: dict) -> bool:
    return value.get("fingerprint_sha256") == sha({k:v for k,v in value.items() if k != "fingerprint_sha256"})


def dynamics(case: dict, controls: torch.Tensor) -> torch.Tensor:
    x = torch.tensor(case["x"], dtype=DTYPE) + controls
    A = torch.tensor(case["A"], dtype=DTYPE)
    B = torch.tensor(case["B"], dtype=DTYPE)
    c = torch.tensor(case["new"], dtype=DTYPE)
    return c @ B @ A @ x + case["bias"]


def oracle(case: dict) -> dict:
    # Independent exact integer arithmetic, no torch/autograd.
    t1 = [sum(a*b for a,b in zip(row,case["x"])) for row in case["A"]]
    t2 = [sum(a*b for a,b in zip(row,t1)) for row in case["B"]]
    old = sum(a*b for a,b in zip(case["old"],t2))
    new = sum(a*b for a,b in zip(case["new"],t2)) + case["bias"]
    coeff = [sum(case["new"][i] * case["B"][i][j] * case["A"][j][k]
                 for i in range(3) for j in range(3)) for k in range(3)]
    supports = [IDS[k] for k,v in enumerate(coeff) if v != 0]
    return {"old":old,"answer":str(new),"coefficient":coeff,
            "support_ids":supports+["E_T1","E_T2","E_EVENT"]}


def credit(case: dict) -> dict:
    controls = torch.zeros(3,dtype=DTYPE,requires_grad=True)
    old = oracle(case)["old"]
    terminal = dynamics(case,controls)
    loss = 0.5*(terminal-old)**2
    loss.backward()
    gradient = [float(v) for v in controls.grad]
    # Immediate pre-event state matches its own public stage-1 contract.
    local_u = torch.zeros(3,dtype=DTYPE,requires_grad=True)
    A = torch.tensor(case["A"], dtype=DTYPE)
    base = A @ torch.tensor(case["x"], dtype=DTYPE)
    (0.5*((A @ (torch.tensor(case["x"], dtype=DTYPE) + local_u)-base)**2).sum()).backward()
    immediate = [float(v) for v in local_u.grad]
    eps=1e-5
    finite=[]
    for i in range(3):
        plus=torch.zeros(3,dtype=DTYPE);minus=plus.clone()
        plus[i]=eps;minus[i]=-eps
        lp=0.5*(dynamics(case,plus)-old)**2
        lm=0.5*(dynamics(case,minus)-old)**2
        finite.append(float((lp-lm)/(2*eps)))
    if any(abs(a-b)>1e-7 for a,b in zip(gradient,finite)):
        raise RuntimeError("GRADIENT_FINITE_DIFFERENCE_MISMATCH")
    if not all(v==0 for v in immediate) or not any(abs(v)>1e-9 for v in gradient):
        raise RuntimeError("DELAYED_CREDIT_CONTRACT_FAILED")
    return {"terminal_gradient":gradient,"immediate_gradient":immediate,
            "finite_difference":finite,"terminal_residual":float(terminal.detach())-old}


def units(values: list[float],total:int=100) -> list[int]:
    absolute=[abs(x) for x in values]
    s=sum(absolute)
    if s<=0: raise ValueError("EMPTY_CREDIT")
    raw=[v*total/s for v in absolute]
    out=[math.floor(v) for v in raw]
    for i in sorted(range(len(raw)),key=lambda i:(-(raw[i]-out[i]),i))[:total-sum(out)]:
        out[i]+=1
    assert sum(out)==total
    return out


def allocation(case: dict, arm: str) -> dict:
    adjoint=units(credit(case)["terminal_gradient"])
    scrambled=adjoint[-1:]+adjoint[:-1]
    if adjoint == scrambled: raise RuntimeError("SCRAMBLED_CONTROL_INERT")
    weight = adjoint if arm=="adjoint" else scrambled if arm=="scrambled" else None
    return {"site_weights":weight,"mode":arm}


def prompt(case: dict,arm: str) -> str:
    old=oracle(case)["old"]
    rows=[
       f"E_A: initial A={case['x'][0]}",
       f"E_B: initial B={case['x'][1]}",
       f"E_C: initial C={case['x'][2]}",
       f"E_T1: stage 1 applies matrix {json.dumps(case['A'],separators=(',',':'))} to column (A,B,C)",
       f"E_T2: stage 2 applies matrix {json.dumps(case['B'],separators=(',',':'))} to stage-1 column",
       f"E_OLD: prior output {old} used selector {case['old']} with offset 0",
       f"E_EVENT: late revision: replace prior selector with {case['new']} and offset {case['bias']}",
    ]
    a=allocation(case,arm)
    weights=a["site_weights"]
    review = "No externally allocated review weights." if weights is None else (
      "Public review weights (relative, not evidence): " +
      ", ".join(f"{key}={n}" for key,n in zip(IDS[:3],weights)))
    return ("Compute the current integer terminal output after E_EVENT. "
            "Matrix rows multiply the preceding column vector. "
            "Return exactly answer as an integer string and support_ids as a chronologically "
            "ordered array of evidence IDs.\n" + "\n".join(rows) + "\n" + review)


def make_plan(model: str, ceiling: int) -> dict:
    if not model or not 128<=ceiling<=4096: raise ValueError("invalid config")
    rows=[]
    for case_index,arm in SCHEDULE:
        case=CASES[case_index]; text=prompt(case,arm)
        rows.append({"case_id":case["id"],"arm":arm,"prompt":text,
                     "prompt_sha256":hashlib.sha256(text.encode()).hexdigest()})
    return sealed({"schema_version":SCHEMA,"model":model,"max_output_tokens":ceiling,
                   "source_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                   "instructions_sha256":hashlib.sha256(INSTRUCTIONS.encode()).hexdigest(),
                   "output_format_sha256":sha(OUTPUT_FORMAT),"schedule":rows,
                   "planned_calls":len(rows),"retries":0,"status":"LOCKED_UNCONSUMED"})


def write_exclusive(path:Path, value:dict)->None:
    path.parent.mkdir(parents=True,exist_ok=True)
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,"wb") as f:
        f.write(canonical(value)+b"\n")


def replace_report(path:Path,value:dict)->None:
    fd,temp=tempfile.mkstemp(prefix=".ebrt-",dir=path.parent)
    os.fchmod(fd,0o600)
    with os.fdopen(fd,"wb") as f:
        f.write(canonical(sealed(value))+b"\n")
    os.replace(temp,path)


def read_json(path:Path)->dict:
    return json.loads(path.read_text())


def verify_plan(plan:dict)->None:
    if not check_seal(plan): raise RuntimeError("PLAN_FINGERPRINT_INVALID")
    expected=make_plan(plan["model"],plan["max_output_tokens"])
    if plan!=expected: raise RuntimeError("PLAN_SOURCE_OR_SCHEDULE_MISMATCH")


def parse_output(text:str)->dict:
    result=json.loads(text)
    if type(result) is not dict or set(result)!={"answer","support_ids"}:
        raise ValueError("OUTPUT_SCHEMA_INVALID")
    if type(result["answer"]) is not str or type(result["support_ids"]) is not list:
        raise ValueError("OUTPUT_TYPE_INVALID")
    if not all(type(v) is str for v in result["support_ids"]):
        raise ValueError("OUTPUT_SUPPORT_TYPE_INVALID")
    return result


def grade(row:dict, raw:str)->dict:
    case=next(x for x in CASES if x["id"]==row["case_id"])
    expected=oracle(case)
    try:
        got=parse_output(raw)
    except (ValueError,TypeError):
        return {"schema_valid":False,"answer_correct":False,"support_exact":False,"strict":False}
    ids=got["support_ids"]
    domain_valid=len(set(ids))==len(ids) and all(v in IDS for v in ids)
    answer=got["answer"]==expected["answer"]
    support=domain_valid and ids==expected["support_ids"]
    return {"schema_valid":True,"answer_correct":answer,
            "support_exact":support,"strict":answer and support}


def offline_checks()->dict:
    cases=[]
    for case in CASES:
        c=credit(case);o=oracle(case)
        weights=allocation(case,"adjoint")["site_weights"]
        sham=allocation(case,"scrambled")["site_weights"]
        assert sorted(weights)==sorted(sham) and weights!=sham
        assert all(x==0 for x in c["immediate_gradient"])
        assert any(abs(x)>0 for x in c["terminal_gradient"])
        assert "E_EVENT" in o["support_ids"]
        assert o["answer"] not in ("",)
        assert all("expected_answer" not in prompt(case,a) for a in ARMS)
        cases.append({"id":case["id"],"local_gradient":c["immediate_gradient"],
                      "terminal_gradient":c["terminal_gradient"],
                      "adjoint_weights":weights,"sham_weights":sham,
                      "oracle_answer_private_to_grader":o["answer"]})
    assert len(SCHEDULE)==9 and all(sum(1 for k,a in SCHEDULE if k==i)==3 for i in range(3))
    return {"status":"PASS","network_calls":0,"cases":cases}


def run(plan:dict, destination:Path)->dict:
    verify_plan(plan)
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY_UNAVAILABLE: zero provider calls")
    if destination.exists():raise RuntimeError("REPORT_ALREADY_EXISTS")
    from openai import OpenAI
    client=OpenAI(max_retries=0, timeout=60.0)
    report={"schema_version":SCHEMA,"plan_fingerprint_sha256":plan["fingerprint_sha256"],
            "status":"RUNNING","attempts":[]}
    write_exclusive(destination,sealed(report))
    for index,row in enumerate(plan["schedule"]):
        report["attempts"].append({"index":index,"case_id":row["case_id"],"arm":row["arm"],
                                   "prompt_sha256":row["prompt_sha256"],"status":"STARTED"})
        replace_report(destination,report)  # START journal before dispatch; no rescue/retry.
        slot=report["attempts"][-1]
        try:
            response=client.responses.create(
                model=plan["model"],
                instructions=INSTRUCTIONS,
                input=[{"role":"user","content":row["prompt"]}],
                text={"format":OUTPUT_FORMAT},
                max_output_tokens=plan["max_output_tokens"],
                store=False,
            )
            raw=response.output_text or ""
            if response.status!="completed": raise RuntimeError("PROVIDER_INCOMPLETE")
            if response.model != plan["model"]: raise RuntimeError("RETURNED_MODEL_DRIFT")
            slot.update(status="COMPLETED",raw=raw,grade=grade(row,raw),
                        provider_response_id=getattr(response, "id", None),
                        returned_model=response.model,
                        usage={"input_tokens":response.usage.input_tokens if response.usage else None,
                               "output_tokens":response.usage.output_tokens if response.usage else None})
        except Exception as error:
            slot.update(status="ERROR",reason=type(error).__name__)
            report["status"]="STOP_ON_PROVIDER_ERROR"
            replace_report(destination,report)
            return sealed(report)
        replace_report(destination,report)
    report["status"]="COMPLETE_EXACT_NINE_TERMINALS"
    replace_report(destination,report)
    return sealed(report)


def verify_report(plan:dict,report:dict)->dict:
    verify_plan(plan)
    if not check_seal(report) or report.get("plan_fingerprint_sha256")!=plan["fingerprint_sha256"]:
        raise RuntimeError("REPORT_BINDING_INVALID")
    attempts=report["attempts"]
    if len(attempts)>len(SCHEDULE):raise RuntimeError("ATTEMPT_OVERFLOW")
    for index,slot in enumerate(attempts):
        row=plan["schedule"][index]
        if (slot["index"],slot["case_id"],slot["arm"],slot["prompt_sha256"]) != (index,row["case_id"],row["arm"],row["prompt_sha256"]):
            raise RuntimeError("ATTEMPT_SCHEDULE_DRIFT")
        if slot["status"]=="COMPLETED" and slot["grade"]!=grade(row,slot["raw"]):
            raise RuntimeError("GRADE_REPLAY_MISMATCH")
    complete=report["status"]=="COMPLETE_EXACT_NINE_TERMINALS" and len(attempts)==9 and all(a["status"]=="COMPLETED" for a in attempts)
    by_arm={arm:{"strict":0,"answer":0,"support":0,"completed":0} for arm in ARMS}
    for slot in attempts:
        if slot["status"]!="COMPLETED":continue
        sums=by_arm[slot["arm"]];sums["completed"]+=1
        for key,grade_key in (("strict","strict"),("answer","answer_correct"),("support","support_exact")):
            sums[key]+=int(slot["grade"][grade_key])
    return sealed({"schema_version":SCHEMA,"status":"DESCRIPTIVE_ONLY" if complete else "INCOMPLETE_NOT_ASSESSED",
                   "api_calls_attempted":len(attempts),"by_arm":by_arm,
                   "local_nonlocal_mechanism":"PROVEN_ON_PUBLIC_LINEAR_SURROGATE",
                   "hosted_gradient_causal_effect":"NOT_ASSESSED",
                   "model_quality_superiority":"NOT_ESTABLISHED"})


def main()->int:
    p=argparse.ArgumentParser(description=__doc__); sub=p.add_subparsers(dest="cmd",required=True)
    sub.add_parser("self-test")
    plan=sub.add_parser("plan");plan.add_argument("--model",required=True);plan.add_argument("--max-output-tokens",type=int,default=384);plan.add_argument("--output",type=Path,required=True)
    runp=sub.add_parser("run");runp.add_argument("--plan",type=Path,required=True);runp.add_argument("--output",type=Path,required=True)
    ver=sub.add_parser("verify");ver.add_argument("--plan",type=Path,required=True);ver.add_argument("--report",type=Path,required=True)
    args=p.parse_args()
    if args.cmd=="self-test":result=offline_checks()
    elif args.cmd=="plan":result=make_plan(args.model,args.max_output_tokens);write_exclusive(args.output,result)
    elif args.cmd=="run":result=run(read_json(args.plan),args.output)
    else:result=verify_report(read_json(args.plan),read_json(args.report))
    print(json.dumps(result,sort_keys=True,indent=2,ensure_ascii=False));return 0


if __name__=="__main__":raise SystemExit(main())
