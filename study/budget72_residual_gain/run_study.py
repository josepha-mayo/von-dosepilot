#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,importlib.util,json,sys
from pathlib import Path
import numpy as np

HERE=Path(__file__).resolve().parent
STUDY=HERE.parent
REPO=STUDY.parent
PARENT=STUDY/"budget72_bandwidth07_residual"/"run_study.py"
spec=importlib.util.spec_from_file_location("parent72bw",PARENT)
parent=importlib.util.module_from_spec(spec);spec.loader.exec_module(parent)

EXPECTED_GLOBAL=0.0009326007417880046
BOOTSTRAP_SEED=20261006
BOOTSTRAP_REPS=100000
GAINS=(0.5,0.75,1.0,1.25,1.5)
CANDIDATES=[(0,0.0)]+[(i,g) for i in range(1,len(parent.OPTIONS)) for g in GAINS]

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def write_new(p,v):
    Path(p).write_text(json.dumps(v,indent=2,allow_nan=False)+"\n",encoding="utf-8",newline="\n")

def check_freeze(curves,catalog,budget_predictions,global_frontier):
    fr=json.loads((HERE/"FREEZE.json").read_text(encoding="utf-8"))
    if fr["state"]!="FROZEN_BEFORE_CANDIDATE_OUTCOME":
        raise ValueError("freeze state")
    paths={
      "train_curves":curves,
      "catalog":catalog,
      "budget_curve_predictions":budget_predictions,
      "global_frontier_predictions":global_frontier
    }
    for k,p in paths.items():
        if sha(p)!=fr["input_sha256"][k]:
            raise ValueError("input changed "+k)
    for rel,h in fr["source_sha256"].items():
        if sha(REPO/rel)!=h:
            raise ValueError("source changed "+rel)
    for rel,h in fr["dependency_sha256"].items():
        if sha(REPO/rel)!=h:
            raise ValueError("dependency changed "+rel)
    return fr

def select_global_gain(x,y,patients,catalog,outer_indices,outer_fold):
    inner,_=parent.patient_folds(
      patients[outer_indices],3,parent.evaluate.SALT+f"|inner|{outer_fold}")
    oof=np.full((len(parent.OPTIONS),2,len(outer_indices),24),np.nan)
    for k in range(3):
        fit=outer_indices[inner!=k]
        val=outer_indices[inner==k]
        if set(patients[fit])&set(patients[val]):
            raise AssertionError("inner patient leakage")
        bundle=parent.build_bundle(x,y,patients,catalog,fit)
        pred=parent.predict_options(x,val,bundle)
        oof[:,:,inner==k]=pred
    if not np.isfinite(oof).all():
        raise AssertionError("inner OOF incomplete")
    base=oof[0]
    scores=[]
    for option,gain in CANDIDATES:
        pred=base if option==0 else base+gain*(oof[option]-base)
        _,pt=parent.patient_target_losses(
          y[outer_indices],pred[0],pred[1],patients[outer_indices])
        scores.append(float(pt.mean()))
    chosen=min(range(len(CANDIDATES)),key=lambda i:(scores[i],i))
    return CANDIDATES[chosen],scores

def execute(curves,catalog_path,budget_predictions,global_frontier,output):
    fr=check_freeze(curves,catalog_path,budget_predictions,global_frontier)
    data,features,_=parent.load_prepared(curves,catalog_path)
    x=features["x_replicates"]
    y=data["y"]
    patients=data["patient_ids"].astype(str)
    catalog=parent.bc.catalog_from_features(features)
    budget=np.load(budget_predictions,allow_pickle=False)
    globalz=np.load(global_frontier,allow_pickle=False)
    if not np.array_equal(budget["y"],y) or not np.array_equal(budget["patients"].astype(str),patients):
        raise ValueError("budget identity")
    if not np.array_equal(globalz["y"],y) or not np.array_equal(globalz["patients"].astype(str),patients):
        raise ValueError("global frontier identity")
    folds=budget["folds"]
    if not np.array_equal(globalz["folds"],folds):
        raise ValueError("fold identity")
    baseA=budget["pred72_A"].copy()
    baseB=budget["pred72_B"].copy()
    globalA=globalz["candidate_A"].copy()
    globalB=globalz["candidate_B"].copy()
    gm=parent.metrics(y,globalA,globalB,patients,folds)
    if abs(gm["mse"]-EXPECTED_GLOBAL)>1e-15:
        raise ValueError("global frontier control")
    candA=np.full_like(y,np.nan)
    candB=np.full_like(y,np.nan)
    regenA=np.full_like(y,np.nan)
    regenB=np.full_like(y,np.nan)
    records=[]
    for f in range(5):
        tr=np.flatnonzero(folds!=f)
        te=np.flatnonzero(folds==f)
        if set(patients[tr])&set(patients[te]):
            raise AssertionError("outer patient leakage")
        (option,gain),scores=select_global_gain(x,y,patients,catalog,tr,f)
        bundle=parent.build_bundle(x,y,patients,catalog,tr)
        pred=parent.predict_options(x,te,bundle)
        regenA[te]=pred[0,0]
        regenB[te]=pred[0,1]
        candA[te]=pred[0,0] if option==0 else pred[0,0]+gain*(pred[option,0]-pred[0,0])
        candB[te]=pred[0,1] if option==0 else pred[0,1]+gain*(pred[option,1]-pred[0,1])
        records.append({
          "fold":f,
          "selected_option_index":int(option),
          "selected_option":parent.OPTIONS[int(option)],
          "selected_gain":float(gain),
          "inner_candidate_mse":scores
        })
        print(json.dumps({"event":"outer_complete","fold":f,
          "selected_option":parent.OPTIONS[int(option)],
          "selected_gain":float(gain),
          "inner_mse":float(min(scores))}),flush=True)
    if not np.isfinite(candA).all() or not np.isfinite(candB).all():
        raise AssertionError("candidate OOF incomplete")
    replay=max(float(np.max(np.abs(regenA-baseA))),float(np.max(np.abs(regenB-baseB))))
    if replay>1e-12:
        raise ValueError("base72 replay")
    cm=parent.metrics(y,candA,candB,patients,folds)
    bm=parent.metrics(y,baseA,baseB,patients,folds)
    pdiff=cm["patient_losses"]-gm["patient_losses"]
    tdiff=cm["target_mse"]-gm["target_mse"]
    rng=np.random.default_rng(BOOTSTRAP_SEED)
    idx=rng.integers(0,len(pdiff),size=(BOOTSTRAP_REPS,len(pdiff)))
    boot=pdiff[idx].mean(1)
    comp_global={
      "relative_mse_gain":float(1-cm["mse"]/gm["mse"]),
      "patient_wins":int((pdiff<0).sum()),
      "patient_losses":int((pdiff>0).sum()),
      "fold_wins":int(sum(a<b for a,b in zip(cm["fold_mse"],gm["fold_mse"]))),
      "target_wins":int((tdiff<-1e-15).sum()),
      "target_regressions":int((tdiff>1e-15).sum()),
      "p90_nonworse":bool(cm["p90_patient_rmse"]<=gm["p90_patient_rmse"]),
      "bootstrap_percentile_95_ci":[float(np.quantile(boot,.025)),float(np.quantile(boot,.975))],
      "bootstrap_fraction_below_zero":float((boot<0).mean())
    }
    bdiff=cm["patient_losses"]-bm["patient_losses"]
    comp_base={
      "relative_mse_gain":float(1-cm["mse"]/bm["mse"]),
      "patient_wins":int((bdiff<0).sum()),
      "patient_losses":int((bdiff>0).sum()),
      "fold_wins":int(sum(a<b for a,b in zip(cm["fold_mse"],bm["fold_mse"]))),
      "p90_nonworse":bool(cm["p90_patient_rmse"]<=bm["p90_patient_rmse"])
    }
    gate={
      "mse":cm["mse"]<gm["mse"],
      "patients":comp_global["patient_wins"]>=30,
      "folds":comp_global["fold_wins"]==5,
      "p90":comp_global["p90_nonworse"]
    }
    decision="GAIN_SUCCESSOR" if all(gate.values()) else "REJECT_GAIN"
    output=Path(output)
    if output.exists():
        raise ValueError("output exists")
    output.mkdir(parents=True,exist_ok=False)
    np.savez_compressed(output/"predictions_private.npz",
      candidate_A=candA,candidate_B=candB,
      global_A=globalA,global_B=globalB,
      base72_A=baseA,base72_B=baseB,
      y=y,patients=patients,folds=folds,
      sample_ids=data["sample_ids"],drug_ids=data["drug_ids"])
    result={
      "schema":"dosepilot.budget72_residual_gain.result.v1",
      "status":"COMPLETE",
      "role":"FROZEN_INNER_ONLY_GLOBAL_RESIDUAL_GAIN_SELECTION",
      "candidate":{"mse":cm["mse"],"p90_patient_rmse":cm["p90_patient_rmse"],
                   "fold_mse":cm["fold_mse"],"orientation_mse":cm["orientation_mse"]},
      "global_frontier":{"mse":gm["mse"],"p90_patient_rmse":gm["p90_patient_rmse"],
                         "fold_mse":gm["fold_mse"]},
      "base72":{"mse":bm["mse"],"p90_patient_rmse":bm["p90_patient_rmse"],
                "fold_mse":bm["fold_mse"]},
      "candidate_vs_global":dict(comp_global,gate=gate),
      "candidate_vs_base72":comp_base,
      "fold_records":records,
      "base72_replay_maxdiff":replay,
      "decision":decision,
      "prediction_sha256":sha(output/"predictions_private.npz"),
      "input_sha256":fr["input_sha256"],
      "source_sha256":fr["source_sha256"],
      "outer_target_splicing":False,
      "protected22_access":False,
      "independent_validation":False,
      "automatic_retry":False
    }
    write_new(output/"RESULT.json",result)
    print(json.dumps({"decision":decision,"candidate":result["candidate"],
      "vs_global":result["candidate_vs_global"],
      "vs_base72":result["candidate_vs_base72"]},indent=2))
    return result

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--curves",type=Path,required=True)
    ap.add_argument("--catalog",type=Path,required=True)
    ap.add_argument("--budget-predictions",type=Path,required=True)
    ap.add_argument("--global-frontier",type=Path,required=True)
    ap.add_argument("--output",type=Path,required=True)
    a=ap.parse_args()
    execute(a.curves,a.catalog,a.budget_predictions,a.global_frontier,a.output)

if __name__=="__main__":
    main()
