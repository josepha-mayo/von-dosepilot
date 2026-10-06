#!/usr/bin/env python3
"""Verify the published grouped conformal reliability diagnostic."""
from __future__ import annotations
import argparse, json, math
from pathlib import Path

class ReliabilityError(ValueError):
    pass

def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))

def same(a,b,label,tol=0.0):
    if isinstance(b,float):
        if not math.isclose(float(a),b,rel_tol=0.0,abs_tol=tol): raise ReliabilityError(label)
    elif a!=b: raise ReliabilityError(label)

def verify(root: Path):
    root=root.resolve()
    p=root/"evidence/current_successor_grouped_conformal_20261006.json"
    if not p.is_file(): raise ReliabilityError("MISSING_RECEIPT")
    j=load(p)
    same(j["schema"],"dosepilot.current_successor_grouped_conformal.v1","SCHEMA")
    same(j["status"],"PASS","STATUS")
    same(j["role"],"POST_HOC_GROUPED_OOF_RELIABILITY_DIAGNOSTIC_NOT_CONFIRMATORY","ROLE")
    same(j["population"],{"samples":119,"whole_patients":59,"targets":24,"orientations":2,"outer_patient_folds":5},"POPULATION")
    same(j["score_definition"],"maximum absolute residual across all samples from one patient, separately per target and A/B orientation","SCORE")
    same(set(j["levels"]),{"0.80","0.90","0.95"},"LEVELS")
    expected={
      "0.80":(0.8100282485875706,[0.8100282485875706,0.8100282485875706],0.7966101694915254,19),
      "0.90":(0.9194915254237288,[0.9173728813559322,0.9216101694915254],0.9067796610169492,24),
      "0.95":(0.9593926553672316,[0.9611581920903954,0.9576271186440678],0.9491525423728814,19),
    }
    for key,(coverage,orient,min_cov,n_targets) in expected.items():
        x=j["levels"][key]
        same(x["coverage"],coverage,"COVERAGE_"+key,1e-15)
        same(x["orientation_coverage"],orient,"ORIENTATION_"+key)
        same(x["target_coverage_min"],min_cov,"TARGET_MIN_"+key,1e-15)
        same(x["targets_at_or_above_nominal"],n_targets,"TARGET_COUNT_"+key)
        same(len(x["folds"]),5,"FOLDS_"+key)
        same(sum(f["test_patients"] for f in x["folds"]),59,"FOLD_PATIENTS_"+key)
        if any(f["calibration_patients"] not in (47,48) for f in x["folds"]):
            raise ReliabilityError("CALIBRATION_PATIENTS_"+key)
    dep=j["deployment_preparation"]
    same(dep["role"],"ALL_OOF_PATIENT_CALIBRATION_RADII_NOT_PROSPECTIVELY_VALIDATED","DEPLOYMENT_ROLE")
    same(set(dep["radii"]),{"0.80","0.90","0.95"},"DEPLOYMENT_LEVELS")
    for key,block in dep["radii"].items():
        rows=block["rows"]
        same(len(rows),24,"RADII_ROWS_"+key)
        same(len({r["drug"] for r in rows}),24,"RADII_DRUGS_"+key)
        if any(r["orientation_A_radius"]<=0 or r["orientation_B_radius"]<=0 for r in rows):
            raise ReliabilityError("NONPOSITIVE_RADIUS_"+key)
    for key in ("selection_adjusted","finite_sample_guarantee_claimed","independent_validation","protected22_access","patient_level_rows_published","prediction_arrays_published"):
        same(j[key],False,"BOUNDARY_"+key)
    return {
      "status":"PASS",
      "coverage_80":j["levels"]["0.80"]["coverage"],
      "coverage_90":j["levels"]["0.90"]["coverage"],
      "coverage_95":j["levels"]["0.95"]["coverage"],
      "targets_at_or_above_90":j["levels"]["0.90"]["targets_at_or_above_nominal"],
      "whole_patients":59,
      "protected22_access":False,
      "independent_validation":False
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--root",type=Path,default=Path(__file__).resolve().parents[2])
    args=ap.parse_args()
    print(json.dumps(verify(args.root),indent=2,sort_keys=True))

if __name__=="__main__":
    main()
