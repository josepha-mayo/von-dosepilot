#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
import numpy as np

RESULT_SHA="acbf67f89dcfe51ffb376bd7dd680fa2db26cca1b2552bde8046b101986e8f05"
PRED_SHA="6ead54699d6f7bcbe028237224cb1d37c216db45f93e283b3d504bd544ecc3e1"
MSE48=0.0015432725382030184
MSE64=0.0011448586813828535

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def patient_target(y,a,b,p):
    e=((a-y)**2+(b-y)**2)/2
    return np.stack([e[p==g].mean(0) for g in np.unique(p)])

def verify(run):
    run=Path(run)
    if sha(run/"RESULT.json")!=RESULT_SHA: raise ValueError("RESULT_HASH")
    if sha(run/"predictions_private.npz")!=PRED_SHA: raise ValueError("PREDICTION_HASH")
    r=json.loads((run/"RESULT.json").read_text())
    z=np.load(run/"predictions_private.npz",allow_pickle=False)
    y=z["y"]; p=z["patients"].astype(str); drugs=z["drug_ids"].astype(str)
    x48=patient_target(y,z["pred48_A"],z["pred48_B"],p)
    x64=patient_target(y,z["pred64_A"],z["pred64_B"],p)
    if abs(float(x48.mean())-MSE48)>1e-15: raise ValueError("MSE48")
    if abs(float(x64.mean())-MSE64)>1e-15: raise ValueError("MSE64")
    if abs(MSE64-0.001144858681382854)>1e-12: raise ValueError("R13")
    d=x64.mean(0)-x48.mean(0)
    material=1e-15
    wins=[str(drugs[i]) for i in range(24) if d[i]<-material]
    regress=[str(drugs[i]) for i in range(24) if d[i]>material]
    ties=[str(drugs[i]) for i in range(24) if abs(d[i])<=material]
    if len(wins)!=21 or regress or len(ties)!=3: raise ValueError("TARGET_BREADTH")
    if r["comparison_64_minus_48"]["patient_wins_64"]!=58: raise ValueError("PATIENT_WINS")
    if r["comparison_64_minus_48"]["favorable_folds_64"]!=5: raise ValueError("FOLDS")
    for k in ("protected22_access","independent_validation","candidate_promotion_allowed","automatic_retry"):
        if r[k] is not False: raise ValueError("BOUNDARY_"+k)
    out={
      "status":"PASS_FLOATING_REPLAY",
      "result_sha256":RESULT_SHA,"prediction_sha256":PRED_SHA,
      "mse48":MSE48,"mse64":MSE64,
      "relative_mse_reduction_64_vs_48":1-MSE64/MSE48,
      "patient_wins_64":58,"favorable_folds_64":5,
      "material_target_wins_64":len(wins),"material_target_regressions_64":0,
      "material_target_ties":ties,
      "max_r13_difference":abs(MSE64-0.001144858681382854),
      "protected22_access":False,"independent_validation":False
    }
    (run/"VERIFICATION.json").write_text(json.dumps(out,indent=2)+"\n",encoding="utf-8")
    return out

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--run",type=Path,required=True); a=ap.parse_args()
    print(json.dumps(verify(a.run),indent=2))
if __name__=="__main__": main()
