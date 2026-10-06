#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,importlib.util,json,sys
from pathlib import Path
import numpy as np

HERE=Path(__file__).resolve().parent
STUDY=HERE.parent
REPO=STUDY.parent
sys.path[:0]=[str(STUDY),str(STUDY/"engine")]
from compact_train import load_prepared

UP=STUDY/"orientation_specific_control_quality_rank1"/"run_study.py"
spec=importlib.util.spec_from_file_location("transfer_recipe",UP)
recipe=importlib.util.module_from_spec(spec);spec.loader.exec_module(recipe)

EXPECTED72=0.0010055928901387746
EXPECTED64SUCCESSOR=0.001042745722096212
A_STRENGTH=1.0/9.0
B_STRENGTH=1.0/3.0
BOOTSTRAP_SEED=20261006
BOOTSTRAP_REPS=100000

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write_new(p,v):
    Path(p).write_text(json.dumps(v,indent=2,allow_nan=False)+"\n",encoding="utf-8",newline="\n")

def patient_target_losses(y,a,b,patients):
    e=((a-y)**2+(b-y)**2)/2
    groups=np.unique(patients)
    return groups,np.stack([e[patients==g].mean(0) for g in groups])

def metrics(y,a,b,patients,folds):
    groups,pt=patient_target_losses(y,a,b,patients)
    per=pt.mean(1)
    pf=np.array([folds[np.flatnonzero(patients==g)[0]] for g in groups])
    return {
      "mse":float(per.mean()),
      "p90_patient_rmse":float(np.quantile(np.sqrt(per),0.9)),
      "fold_mse":[float(per[pf==f].mean()) for f in range(5)],
      "orientation_mse":[
        float(np.mean([((a[patients==g]-y[patients==g])**2).mean() for g in groups])),
        float(np.mean([((b[patients==g]-y[patients==g])**2).mean() for g in groups]))
      ],
      "patient_losses":per,
      "target_mse":pt.mean(0)
    }

def check_freeze(curve_predictions,control_features,current_successor,curves,catalog):
    fr=json.loads((HERE/"FREEZE.json").read_text(encoding="utf-8"))
    if fr["state"]!="FROZEN_BEFORE_CANDIDATE_OUTCOME": raise ValueError("freeze state")
    paths={
      "budget_curve_predictions":curve_predictions,
      "control_quality_features":control_features,
      "current_64_successor":current_successor,
      "train_curves":curves,
      "catalog":catalog
    }
    for k,p in paths.items():
        if sha(p)!=fr["input_sha256"][k]: raise ValueError("input changed "+k)
    for rel,h in fr["source_sha256"].items():
        if sha(REPO/rel)!=h: raise ValueError("source changed "+rel)
    for rel,h in fr["dependency_sha256"].items():
        if sha(REPO/rel)!=h: raise ValueError("dependency changed "+rel)
    return fr

def execute(curve_predictions,control_features,current_successor,curves,catalog_path,output):
    fr=check_freeze(curve_predictions,control_features,current_successor,curves,catalog_path)
    data,_,_=load_prepared(curves,catalog_path)
    y=data["y"];patients=data["patient_ids"].astype(str)
    base=np.load(curve_predictions,allow_pickle=False)
    prior=np.load(current_successor,allow_pickle=False)
    if not np.array_equal(base["y"],y) or not np.array_equal(base["patients"].astype(str),patients):
        raise ValueError("budget identity")
    if not np.array_equal(prior["y"],y) or not np.array_equal(prior["patients"].astype(str),patients):
        raise ValueError("successor identity")
    folds=base["folds"]
    if not np.array_equal(prior["folds"],folds): raise ValueError("fold identity")
    baseA=base["pred72_A"].copy();baseB=base["pred72_B"].copy()
    priorA=prior["candidate"][0].copy();priorB=prior["candidate"][1].copy()
    bm=metrics(y,baseA,baseB,patients,folds)
    pm=metrics(y,priorA,priorB,patients,folds)
    if abs(bm["mse"]-EXPECTED72)>1e-15: raise ValueError("72 base control")
    if abs(pm["mse"]-EXPECTED64SUCCESSOR)>1e-15: raise ValueError("64 successor control")
    Q=recipe.load_quality_features(control_features,data["sample_ids"])
    candA=baseA.copy();candB=baseB.copy();records=[]
    for f in range(5):
        tr=folds!=f;te=folds==f
        if set(patients[tr])&set(patients[te]): raise AssertionError("patient leakage")
        RA=y[tr]-baseA[tr];RB=y[tr]-baseB[tr]
        modelA=recipe.fit_rank1(recipe.A_level_basis(Q[tr]),RA,patients[tr])
        modelB=recipe.fit_rank1(recipe.B_full_quality_basis(Q[tr]),RB,patients[tr])
        deltaA=A_STRENGTH*recipe.predict_rank1(recipe.A_level_basis(Q[te]),modelA)
        deltaB=B_STRENGTH*recipe.predict_rank1(recipe.B_full_quality_basis(Q[te]),modelB)
        candA[te]=baseA[te]+deltaA
        candB[te]=baseB[te]+deltaB
        records.append({
          "fold":f,
          "training_patients":int(len(np.unique(patients[tr]))),
          "test_patients":int(len(np.unique(patients[te]))),
          "A_strength":A_STRENGTH,"B_strength":B_STRENGTH,
          "A_model":modelA,"B_model":modelB,
          "A_delta_sd":float(np.std(deltaA)),"B_delta_sd":float(np.std(deltaB))
        })
    cm=metrics(y,candA,candB,patients,folds)
    pdiff=cm["patient_losses"]-bm["patient_losses"]
    tdiff=cm["target_mse"]-bm["target_mse"]
    rng=np.random.default_rng(BOOTSTRAP_SEED)
    idx=rng.integers(0,len(pdiff),size=(BOOTSTRAP_REPS,len(pdiff)))
    boot=pdiff[idx].mean(1)
    comp_base={
      "relative_mse_gain":float(1-cm["mse"]/bm["mse"]),
      "patient_wins":int((pdiff<0).sum()),"patient_losses":int((pdiff>0).sum()),
      "fold_wins":int(sum(a<b for a,b in zip(cm["fold_mse"],bm["fold_mse"]))),
      "target_wins":int((tdiff<-1e-15).sum()),"target_regressions":int((tdiff>1e-15).sum()),
      "p90_nonworse":bool(cm["p90_patient_rmse"]<=bm["p90_patient_rmse"]),
      "bootstrap_percentile_95_ci":[float(np.quantile(boot,.025)),float(np.quantile(boot,.975))],
      "bootstrap_fraction_below_zero":float((boot<0).mean())
    }
    ppdiff=cm["patient_losses"]-pm["patient_losses"]
    comp_prior={
      "relative_mse_gain":float(1-cm["mse"]/pm["mse"]),
      "patient_wins":int((ppdiff<0).sum()),"patient_losses":int((ppdiff>0).sum()),
      "fold_wins":int(sum(a<b for a,b in zip(cm["fold_mse"],pm["fold_mse"]))),
      "p90_nonworse":bool(cm["p90_patient_rmse"]<=pm["p90_patient_rmse"])
    }
    gate={
      "mse":cm["mse"]<bm["mse"],
      "patients":comp_base["patient_wins"]>=30,
      "folds":comp_base["fold_wins"]==5,
      "p90":comp_base["p90_nonworse"]
    }
    decision="LOWER_ERROR_72_WELL_FRONTIER" if all(gate.values()) else "REJECT_TRANSFER"
    output=Path(output)
    if output.exists(): raise ValueError("output exists")
    output.mkdir(parents=True,exist_ok=False)
    np.savez_compressed(output/"predictions_private.npz",
      candidate_A=candA,candidate_B=candB,base72_A=baseA,base72_B=baseB,
      current64_A=priorA,current64_B=priorB,y=y,patients=patients,folds=folds,
      sample_ids=data["sample_ids"],drug_ids=data["drug_ids"])
    result={
      "schema":"dosepilot.budget72_transferred_control_rank1.result.v1",
      "status":"COMPLETE",
      "role":"FROZEN_NO_RETUNING_TRANSFER_ON_REPEATED_LIB1_DEVELOPMENT",
      "candidate":{"mse":cm["mse"],"p90_patient_rmse":cm["p90_patient_rmse"],
                   "fold_mse":cm["fold_mse"],"orientation_mse":cm["orientation_mse"]},
      "base72":{"mse":bm["mse"],"p90_patient_rmse":bm["p90_patient_rmse"],
                "fold_mse":bm["fold_mse"]},
      "current64_successor":{"mse":pm["mse"],"p90_patient_rmse":pm["p90_patient_rmse"],
                             "fold_mse":pm["fold_mse"]},
      "candidate_vs_base72":dict(comp_base,gate=gate),
      "candidate_vs_current64_successor":comp_prior,
      "fold_records":records,
      "decision":decision,
      "prediction_sha256":sha(output/"predictions_private.npz"),
      "input_sha256":fr["input_sha256"],
      "source_sha256":fr["source_sha256"],
      "hyperparameter_search":False,
      "protected22_access":False,
      "independent_validation":False,
      "automatic_retry":False
    }
    write_new(output/"RESULT.json",result)
    print(json.dumps({
      "decision":decision,
      "candidate":result["candidate"],
      "vs_base72":result["candidate_vs_base72"],
      "vs_current64":result["candidate_vs_current64_successor"]
    },indent=2))
    return result

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--curve-predictions",type=Path,required=True)
    ap.add_argument("--control-features",type=Path,required=True)
    ap.add_argument("--current-successor",type=Path,required=True)
    ap.add_argument("--curves",type=Path,required=True)
    ap.add_argument("--catalog",type=Path,required=True)
    ap.add_argument("--output",type=Path,required=True)
    a=ap.parse_args()
    execute(a.curve_predictions,a.control_features,a.current_successor,
            a.curves,a.catalog,a.output)
if __name__=="__main__":
    main()
