#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json,sys
from pathlib import Path
import numpy as np

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import run_study as rs

RESULT_SHA="e3fb536604b5d147168df35cf75c421206e3499575c8795fd45d1eaf009745f9"
PRED_SHA="72f803893e252a88777dbf2e5ef918d452da697da986d72adcbcb61f9e749a65"

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def verify(run,curves,catalog,budget_predictions,current_successor):
    run=Path(run)
    if sha(run/"RESULT.json")!=RESULT_SHA:
        raise ValueError("RESULT_HASH")
    if sha(run/"predictions_private.npz")!=PRED_SHA:
        raise ValueError("PREDICTION_HASH")
    result=json.loads((run/"RESULT.json").read_text(encoding="utf-8"))
    saved=np.load(run/"predictions_private.npz",allow_pickle=False)
    rs.check_freeze(curves,catalog,budget_predictions,current_successor)
    data,features,_=rs.load_prepared(curves,catalog)
    x=features["x_replicates"]
    y=data["y"]
    patients=data["patient_ids"].astype(str)
    cat=rs.bc.catalog_from_features(features)
    folds=saved["folds"]
    candA=np.full_like(y,np.nan)
    candB=np.full_like(y,np.nan)
    baseA=np.full_like(y,np.nan)
    baseB=np.full_like(y,np.nan)
    for f in range(5):
        tr=np.flatnonzero(folds!=f)
        te=np.flatnonzero(folds==f)
        chosen,scores=rs.select_option(x,y,patients,cat,tr,f)
        if chosen!=int(result["selections"][f]["selected_index"]):
            raise ValueError("SELECTION_MISMATCH")
        bundle=rs.build_bundle(x,y,patients,cat,tr)
        pred=rs.predict_options(x,te,bundle)
        baseA[te]=pred[0,0];baseB[te]=pred[0,1]
        candA[te]=pred[chosen,0];candB[te]=pred[chosen,1]
    maxdiff=max(
      float(np.max(np.abs(candA-saved["candidate_A"]))),
      float(np.max(np.abs(candB-saved["candidate_B"]))),
      float(np.max(np.abs(baseA-saved["base72_A"]))),
      float(np.max(np.abs(baseB-saved["base72_B"]))))
    if maxdiff>1e-12:
        raise ValueError("REPLAY_MISMATCH")
    cm=rs.metrics(y,candA,candB,patients,folds)
    if abs(cm["mse"]-float(result["candidate"]["mse"]))>1e-15:
        raise ValueError("MSE_MISMATCH")
    _,ct=rs.patient_target_losses(y,candA,candB,patients)
    _,bt=rs.patient_target_losses(y,baseA,baseB,patients)
    d=ct.mean(0)-bt.mean(0)
    regress=[str(saved["drug_ids"][i]) for i in range(24) if d[i]>1e-15]
    if regress!=["Methotrexate","Panobinostat"]:
        raise ValueError("TARGET_BREADTH")
    out={
      "status":"PASS_FLOATING_REPLAY",
      "max_prediction_difference":maxdiff,
      "candidate_mse":cm["mse"],
      "base72_mse":float(result["base72"]["mse"]),
      "relative_mse_gain":float(result["candidate_vs_base72"]["relative_mse_gain"]),
      "patient_wins":int(result["candidate_vs_base72"]["patient_wins"]),
      "fold_wins":int(result["candidate_vs_base72"]["fold_wins"]),
      "target_wins":int(result["candidate_vs_base72"]["target_wins"]),
      "target_regressions":regress,
      "prediction_sha256":PRED_SHA,
      "result_sha256":RESULT_SHA,
      "protected22_access":False,
      "independent_validation":False
    }
    (run/"VERIFICATION.json").write_text(json.dumps(out,indent=2)+"\n",encoding="utf-8")
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--run",type=Path,required=True)
    ap.add_argument("--curves",type=Path,required=True)
    ap.add_argument("--catalog",type=Path,required=True)
    ap.add_argument("--budget-predictions",type=Path,required=True)
    ap.add_argument("--current-successor",type=Path,required=True)
    a=ap.parse_args()
    print(json.dumps(verify(a.run,a.curves,a.catalog,a.budget_predictions,a.current_successor),indent=2))

if __name__=="__main__":
    main()
