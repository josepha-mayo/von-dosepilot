#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json,math
from pathlib import Path

class BudgetEvidenceError(ValueError): pass
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def same(a,b,label,tol=0.0):
    if isinstance(b,float):
        if not math.isclose(float(a),b,rel_tol=0.0,abs_tol=tol): raise BudgetEvidenceError(label)
    elif a!=b: raise BudgetEvidenceError(label)

def verify(root):
    root=Path(root).resolve()
    p=root/"evidence/budget48_two_dose_ablation_20261006.json"
    j=json.loads(p.read_text(encoding="utf-8"))
    same(j["schema"],"dosepilot.budget48_two_dose_ablation.evidence.v1","SCHEMA")
    same(j["frozen_before_outcome_commit"],"fd4564a","FREEZE_COMMIT")
    same(j["arm48"]["mse"],0.0015432725382030184,"MSE48",1e-15)
    same(j["arm64"]["mse"],0.0011448586813828535,"MSE64",1e-15)
    same(j["comparison"]["relative_mse_reduction_64_vs_48"],0.2581616966268815,"RELATIVE_MSE",1e-15)
    same(j["comparison"]["patient_wins_64"],58,"PATIENT_WINS")
    same(j["comparison"]["favorable_outer_folds_64"],5,"FOLD_WINS")
    same(j["comparison"]["material_target_wins_64"],21,"TARGET_WINS")
    same(j["comparison"]["material_target_regressions_64"],0,"TARGET_REGRESSIONS")
    same(j["comparison"]["material_target_ties"],["5-FU","Bemcentinib","Napabucasin"],"TARGET_TIES")
    lo,hi=j["comparison"]["bootstrap_percentile_95_ci_64_minus_48"]
    if not (lo<hi<0): raise BudgetEvidenceError("BOOTSTRAP_DIRECTION")
    freeze=root/"study/budget48_two_dose_ablation/FREEZE.json"
    same(sha(freeze),j["hashes"]["freeze_sha256"],"FREEZE_HASH")
    fr=json.loads(freeze.read_text(encoding="utf-8"))
    for rel,h in fr["source_sha256"].items():
        if sha(root/rel)!=h: raise BudgetEvidenceError("SOURCE_HASH:"+rel)
    for key in ("patient_level_rows_published","prediction_arrays_published","selection_adjusted","candidate_promotion_allowed","protected22_access","independent_validation"):
        same(j[key],False,"BOUNDARY_"+key)
    return {"status":"PASS","mse48":j["arm48"]["mse"],"mse64":j["arm64"]["mse"],
      "relative_mse_reduction":j["comparison"]["relative_mse_reduction_64_vs_48"],
      "patient_wins_64":58,"favorable_folds_64":5,"material_target_regressions_64":0,
      "protected22_access":False,"independent_validation":False}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--root",type=Path,default=Path(__file__).resolve().parents[2]); a=ap.parse_args()
    print(json.dumps(verify(a.root),indent=2))
if __name__=="__main__": main()
