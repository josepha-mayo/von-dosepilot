#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json,math
from pathlib import Path
class CurveEvidenceError(ValueError): pass
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def same(a,b,label,tol=0.0):
    if isinstance(b,float):
        if not math.isclose(float(a),b,rel_tol=0.0,abs_tol=tol): raise CurveEvidenceError(label)
    elif a!=b: raise CurveEvidenceError(label)
def verify(root):
    root=Path(root).resolve()
    j=json.loads((root/"evidence/budget_upgrade_curve_20261006.json").read_text())
    same(j["schema"],"dosepilot.budget_upgrade_curve.evidence.v1","SCHEMA")
    same(j["frozen_before_outcome_commit"],"b205cf6","FREEZE_COMMIT")
    budgets=[48,52,56,60,64,68,72]
    expected=[0.0015432725382030184,0.0014019868255279698,0.0013359466877716313,0.0012450200703377984,0.0011448586813828535,0.001053102723517891,0.0010055928901387746]
    vals=[j["budgets"][str(b)]["mse"] for b in budgets]
    for a,b in zip(vals,expected): same(a,b,"MSE",1e-15)
    if not all(vals[i+1]<vals[i] for i in range(6)): raise CurveEvidenceError("MONOTONE")
    same(j["current_64_well_successor"]["beats_uncalibrated_68_well_mse"],True,"SUCC68")
    same(j["current_64_well_successor"]["uncalibrated_72_beats_successor"],True,"BASE72")
    freeze=root/"study/budget_upgrade_curve/FREEZE.json"
    same(sha(freeze),j["hashes"]["freeze_sha256"],"FREEZE_HASH")
    fr=json.loads(freeze.read_text())
    for rel,h in fr["source_sha256"].items():
        if sha(root/rel)!=h: raise CurveEvidenceError("SOURCE_HASH:"+rel)
    for key in ("patient_level_rows_published","prediction_arrays_published","selection_adjusted","candidate_promotion_allowed","protected22_access","independent_validation"):
        same(j[key],False,"BOUNDARY_"+key)
    return {"status":"PASS","budget_count":7,"mse48":vals[0],"mse64":vals[4],"mse72":vals[-1],
      "current_successor_beats_base68":True,"base72_beats_current_successor":True,
      "protected22_access":False,"independent_validation":False}
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--root",type=Path,default=Path(__file__).resolve().parents[2]);a=ap.parse_args()
    print(json.dumps(verify(a.root),indent=2))
if __name__=="__main__":main()
