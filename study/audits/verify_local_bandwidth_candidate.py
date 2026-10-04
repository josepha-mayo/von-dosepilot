#!/usr/bin/env python3
"""Response-free consistency check for the local-bandwidth candidate branch."""
from pathlib import Path
import argparse,hashlib,json

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def require(ok,msg):
    if not ok:raise ValueError(msg)

def verify(root):
    root=Path(root)
    evidence=json.loads((root/"evidence/local_bandwidth_candidate_20261004.json").read_text())
    index=json.loads((root/"evidence/EVIDENCE_INDEX.json").read_text())
    require(evidence["schema"]=="dosepilot.local_bandwidth_candidate.v1","SCHEMA")
    require(evidence["status"]=="VERIFIED_DEVELOPMENT_CANDIDATE_NOT_PUBLIC_INCUMBENT","STATUS")
    require(evidence["bandwidths_use_target_labels"] is False,"RESPONSE_FREE_GEOMETRY")
    require(abs(evidence["metrics"]["local"]["mse"]-.0010581496990391417)<1e-15,"LOCAL_MSE")
    require(abs(evidence["metrics"]["bandwidth07"]["mse"]-.0010582750420801538)<1e-15,"REFERENCE_MSE")
    c=evidence["comparison_vs_bandwidth07"]
    require(c["patient_wins"]==32 and c["patient_losses"]==27 and c["fold_wins"]==4,"BREADTH")
    require(c["p90_nonworse"] is True and c["selection_corrected"] is False,"TAIL_OR_INTERVAL_SCOPE")
    require(evidence["target_nonworse_vs_bandwidth07"]==12,"TARGET_NONWORSE")
    require(len(evidence["target_regressions_vs_bandwidth07"])==12,"TARGET_REGRESSIONS")
    stability=evidence["geometry_stability"]
    require(stability["min_correlation"]>.94 and stability["max_target_cv"]<.023,"GEOMETRY_STABILITY")
    require(abs(stability["final_geomean"]-.7)<1e-15,"GEOMEAN")
    require(evidence["public_reproduction"]["status"]=="PASS","PUBLIC_REPLAY")
    require(evidence["public_reproduction"]["old_prediction_input"] is False,"NO_OLD_PREDICTIONS")
    require(evidence["public_reproduction"]["private_metadata_kit_used"] is False,"NO_PRIVATE_KIT")
    runtime=evidence["runtime_verification"]
    require(runtime["status"]=="PASS" and runtime["requests_checked"]==238,"RUNTIME")
    require(runtime["maximum_prediction_difference"]<=2.3e-16,"RUNTIME_PARITY")
    require(runtime["single_missing_positions_checked"]==64 and runtime["all_missing_cases_withheld"],"MISSINGNESS")
    source_map={
      "local_bandwidth_additive":"study/hybrid_residual/local_bandwidth_additive.py",
      "local_bandwidth_inference":"study/hybrid_residual/local_bandwidth_inference.py",
      "reproduce_local_bandwidth":"study/hybrid_residual/reproduce_local_bandwidth.py",
      "test_local_bandwidth_additive":"study/hybrid_residual/test_local_bandwidth_additive.py"}
    for key,path in source_map.items():
        require(sha(root/path)==evidence["source_sha256"][key],"SOURCE_HASH:"+key)
    # The stable public release must remain bandwidth-0.7 on this candidate branch.
    current=index["bandwidth_successor"]
    require(current["current_internal_incumbent"] is True,"BANDWIDTH07_REMAINS_PUBLIC_INCUMBENT")
    require(abs(current["mse"]-.0010582750420801538)<1e-15,"PUBLIC_INCUMBENT_MSE")
    require(evidence["release_decision"]["public_incumbent_replaced"] is False,"NO_SILENT_PROMOTION")
    require(evidence["repeated_adaptive_development"] is True and evidence["independent_validation"] is False,"VALIDATION_SCOPE")
    return {"status":"PASS","candidate_mse":evidence["metrics"]["local"]["mse"],
      "public_incumbent_mse":current["mse"],"public_incumbent_replaced":False,
      "response_labels_used_for_geometry":False,"public_replay":"PASS",
      "runtime_requests_checked":238,"target_regressions":12,
      "private_patient_rows_read":False,"protected_response_access":False}

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--root",type=Path,default=Path("."))
    a=p.parse_args();print(json.dumps(verify(a.root),indent=2))
