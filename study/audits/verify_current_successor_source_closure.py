#!/usr/bin/env python3
"""Response-free verifier for the current successor's published source-closure receipt.

This verifier checks repository-visible facts only. It does not read or decode private
prediction arrays and therefore does not independently reconstruct the original
producer mapping from private prediction bytes. It verifies the frozen mapping is
internally consistent with every consumer freeze and that all declared source files
match their frozen SHA-256 digests.
"""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

class ClosureError(ValueError):
    pass

def sha(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1<<20),b""):
            h.update(chunk)
    return h.hexdigest()

def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))

def prediction_declarations(freeze: dict) -> dict[str,str]:
    out={}
    for k,v in freeze.get("input_sha256",{}).items():
        if "prediction" in k.lower() and isinstance(v,str):
            out[k]=v
    for k,v in freeze.items():
        if "prediction" in k.lower() and k.lower().endswith("sha256") and isinstance(v,str):
            out[k]=v
    return out

def verify(root: Path) -> dict:
    receipt_path=root/"evidence/current_successor_source_closure_20261006.json"
    result_path=root/"evidence/orientation_specific_control_quality_rank1_20261006.json"
    if not receipt_path.is_file(): raise ClosureError("MISSING_RECEIPT")
    if not result_path.is_file(): raise ClosureError("MISSING_CURRENT_RESULT")
    receipt=load(receipt_path); result=load(result_path)
    if receipt.get("schema")!="dosepilot.current_successor_source_closure.v1":
        raise ClosureError("SCHEMA")
    if receipt.get("role")!="RESPONSE_FREE_SOURCE_PROVENANCE_CLOSURE_NOT_NUMERICAL_REPLAY":
        raise ClosureError("ROLE")
    stages=receipt.get("stages",[])
    edges=receipt.get("prediction_edges",[])
    if receipt.get("stage_count")!=len(stages) or len(stages)!=49:
        raise ClosureError("STAGE_COUNT")
    if receipt.get("prediction_edge_count")!=len(edges) or len(edges)!=172:
        raise ClosureError("EDGE_COUNT")
    if receipt.get("missing_source_stages")!=[]:
        raise ClosureError("MISSING_SOURCE_STAGES")
    if receipt.get("unmapped_prediction_hashes")!=[]:
        raise ClosureError("UNMAPPED_PREDICTIONS")
    if receipt.get("all_source_hashes_match") is not True:
        raise ClosureError("RECEIPT_SOURCE_HASH_STATUS")

    result_mse=result["metrics"]["candidate"]["mse"]
    result_prediction=result["hashes"]["prediction_sha256"]
    if abs(receipt["current_development_mse"]-result_mse)>1e-15:
        raise ClosureError("CURRENT_MSE")
    if receipt["current_prediction_sha256"]!=result_prediction:
        raise ClosureError("CURRENT_PREDICTION_HASH")
    if receipt["current_stage"]!="orientation_specific_control_quality_rank1":
        raise ClosureError("CURRENT_STAGE")

    stage_names=[x["stage"] for x in stages]
    if len(set(stage_names))!=len(stage_names):
        raise ClosureError("DUPLICATE_STAGE")
    stage_set=set(stage_names)
    freezes={}
    source_files_checked=0
    for row in stages:
        name=row["stage"]
        fp=root/"study"/name/"FREEZE.json"
        if not fp.is_file(): raise ClosureError("MISSING_FREEZE:"+name)
        fr=load(fp); freezes[name]=fr
        if fr.get("schema")!=row.get("freeze_schema"):
            raise ClosureError("FREEZE_SCHEMA:"+name)
        if fr.get("protected22_access") is not False:
            raise ClosureError("FREEZE_PROTECTED22:"+name)
        if fr.get("independent_validation") is not False:
            raise ClosureError("FREEZE_INDEPENDENT_VALIDATION:"+name)
        bad=[]
        declared=fr.get("source_sha256",{})
        if row.get("source_files")!=len(declared):
            raise ClosureError("SOURCE_FILE_COUNT:"+name)
        for rel,expected in declared.items():
            p=(root/rel).resolve()
            try: p.relative_to(root.resolve())
            except ValueError: raise ClosureError("PATH_ESCAPE:"+rel)
            source_files_checked+=1
            if not p.is_file() or sha(p)!=expected:
                bad.append(rel)
        if bad or row.get("source_hashes_match") is not True:
            raise ClosureError("SOURCE_HASH:"+name+":"+",".join(bad[:3]))
    if source_files_checked!=receipt.get("source_files_checked") or source_files_checked!=251:
        raise ClosureError("SOURCE_TOTAL")

    public_ref=receipt["public_bandwidth_reference_prediction_sha256"]
    seen_edges=set()
    for edge in edges:
        consumer=edge["consumer"]; key=edge["input_key"]; h=edge["prediction_sha256"]
        sig=(consumer,key,h)
        if sig in seen_edges: raise ClosureError("DUPLICATE_EDGE")
        seen_edges.add(sig)
        if consumer not in stage_set: raise ClosureError("UNKNOWN_CONSUMER:"+consumer)
        declarations=prediction_declarations(freezes[consumer])
        if declarations.get(key)!=h:
            raise ClosureError("CONSUMER_DECLARATION:"+consumer+":"+key)
        role=edge["producer_role"]
        producer=edge.get("producer_stage")
        if role=="public_bandwidth_replay":
            if producer is not None or h!=public_ref:
                raise ClosureError("PUBLIC_REFERENCE_EDGE:"+consumer+":"+key)
        elif role=="frozen_adaptive_stage":
            if producer not in stage_set:
                raise ClosureError("UNKNOWN_PRODUCER:"+str(producer))
        else:
            raise ClosureError("PRODUCER_ROLE:"+str(role))

    boundary=receipt.get("audit_boundary",{})
    required_false=("prediction_arrays_decoded_for_this_source_closure_audit",
                    "protected22_access","independent_validation",
                    "full_clean_room_numerical_replay_claimed",
                    "accepted_kaggle_entry_changed")
    for k in required_false:
        if boundary.get(k) is not False: raise ClosureError("BOUNDARY:"+k)
    if boundary.get("prediction_bytes_hashed_for_producer_mapping") is not True:
        raise ClosureError("BOUNDARY_HASH_MAPPING")
    if boundary.get("official_competition_score") is not None:
        raise ClosureError("BOUNDARY_SCORE")

    return {
        "status":"PASS",
        "stages":len(stages),
        "prediction_edges":len(edges),
        "source_files_checked":source_files_checked,
        "missing_source_stages":0,
        "unmapped_prediction_hashes":0,
        "current_stage":receipt["current_stage"],
        "current_development_mse":receipt["current_development_mse"],
        "current_prediction_sha256":receipt["current_prediction_sha256"],
        "protected22_access":False,
        "private_prediction_arrays_read":False,
        "producer_mapping_reconstructed_from_private_bytes":False,
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--root",type=Path,default=Path("."))
    args=ap.parse_args()
    print(json.dumps(verify(args.root.resolve()),indent=2))

if __name__=="__main__":
    main()
