#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,importlib.util,json
from pathlib import Path
import numpy as np

HERE=Path(__file__).resolve().parent
STUDY=HERE.parent
REPO=STUDY.parent
PARENT_PATH=STUDY/"budget72_bandwidth07_residual"/"run_study.py"
spec=importlib.util.spec_from_file_location("parent72bw_globalquad",PARENT_PATH)
parent=importlib.util.module_from_spec(spec);spec.loader.exec_module(parent)
from global_quadratic72 import GlobalQuadratic72

STRENGTHS=(0.0,0.0625,0.125,0.25,0.5,1.0)
OPTIONS=parent.OPTIONS
EXPECTED_FRONTIER=0.0009326007417880046
BOOTSTRAP_SEED=20261006
BOOTSTRAP_REPS=100000

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write_new(p,v):
    Path(p).write_text(json.dumps(v,indent=2,allow_nan=False)+"\n",encoding="utf-8",newline="\n")

def build_bundle(x,y,patients,catalog,indices):
    full=parent.plan_panel_fast(x[indices],y[indices],patients[indices],catalog)
    plan=parent.bc.derive_budget(full,catalog,24)
    paidA=parent.bc.acquire_budget(x[indices],plan,"A")
    paidB=parent.bc.acquire_budget(x[indices],plan,"B")
    context=parent.bc.fit_context(paidA,paidB,y[indices],patients[indices],plan,catalog.target_ids)
    base=parent.bc.Predictor(context,plan,0.01)
    z=np.r_[paidA,paidB]
    z=(z-base.mean_x)/base.scale_x
    residual=np.r_[y[indices]-base.predict(paidA),y[indices]-base.predict(paidB)]
    w=np.tile(parent.patient_weights(patients[indices]),2)/2
    owner=np.asarray(plan["coordinate_target_indices"],int)
    models={};coefs={}
    for strength in STRENGTHS:
        m=GlobalQuadratic72(z,residual,w,owner,strength,0.7)
        models[strength]=m
        coefs[strength]=[np.zeros_like(residual)]+[
          m.coefficients(ridge,frac)[0] for frac,ridge in OPTIONS[1:]]
    return plan,base,models,coefs

def predict_all(x,indices,bundle):
    plan,base,models,coefs=bundle
    out=np.empty((len(STRENGTHS),len(OPTIONS),2,len(indices),24))
    for oi,o in enumerate(("A","B")):
        paid=parent.bc.acquire_budget(x[indices],plan,o)
        zq=(paid-base.mean_x)/base.scale_x
        bp=base.predict(paid)
        for si,strength in enumerate(STRENGTHS):
            cross=models[strength].centered_cross(zq)
            for ri,coef in enumerate(coefs[strength]):
                out[si,ri,oi]=bp+cross@coef
    return out

def select_joint(x,y,patients,catalog,outer_indices,outer_fold):
    inner,_=parent.patient_folds(
      patients[outer_indices],3,parent.evaluate.SALT+f"|inner|{outer_fold}")
    oof=np.full((len(STRENGTHS),len(OPTIONS),2,len(outer_indices),24),np.nan)
    for k in range(3):
        fit=outer_indices[inner!=k]
        val=outer_indices[inner==k]
        if set(patients[fit])&set(patients[val]):
            raise AssertionError("inner patient leakage")
        pred=predict_all(x,val,build_bundle(x,y,patients,catalog,fit))
        for si in range(len(STRENGTHS)):
            for ri in range(len(OPTIONS)):
                for orient in range(2):
                    oof[si,ri,orient,inner==k,:]=pred[si,ri,orient]
    if not np.isfinite(oof).all():
        raise AssertionError("inner OOF incomplete")
    rows=[]
    for si,strength in enumerate(STRENGTHS):
        for ri,opt in enumerate(OPTIONS):
            _,pt=parent.patient_target_losses(
              y[outer_indices],oof[si,ri,0],oof[si,ri,1],patients[outer_indices])
            rows.append({"strength_index":si,"quadratic_strength":strength,
                         "option_index":ri,"option":opt,"mse":float(pt.mean())})
    best=min(rows,key=lambda r:(r["mse"],r["strength_index"],r["option_index"]))
    return best,rows

def check_freeze(curves,catalog,frontier):
    fr=json.loads((HERE/"FREEZE.json").read_text(encoding="utf-8"))
    if fr["state"]!="FROZEN_BEFORE_CANDIDATE_OUTCOME":
        raise ValueError("freeze state")
    for k,p in {"train_curves":curves,"catalog":catalog,"frontier72":frontier}.items():
        if sha(p)!=fr["input_sha256"][k]:
            raise ValueError("input changed "+k)
    for rel,h in fr["source_sha256"].items():
        if sha(REPO/rel)!=h:
            raise ValueError("source changed "+rel)
    for rel,h in fr["dependency_sha256"].items():
        if sha(REPO/rel)!=h:
            raise ValueError("dependency changed "+rel)
    return fr

def execute(curves,catalog_path,frontier_path,output):
    fr=check_freeze(curves,catalog_path,frontier_path)
    data,features,_=parent.load_prepared(curves,catalog_path)
    x=features["x_replicates"];y=data["y"];patients=data["patient_ids"].astype(str)
    catalog=parent.bc.catalog_from_features(features)
    ref=np.load(frontier_path,allow_pickle=False)
    if not np.array_equal(ref["y"],y) or not np.array_equal(ref["patients"].astype(str),patients):
        raise ValueError("frontier identity")
    folds=ref["folds"];refA=ref["candidate_A"].copy();refB=ref["candidate_B"].copy()
    rm=parent.metrics(y,refA,refB,patients,folds)
    if abs(rm["mse"]-EXPECTED_FRONTIER)>1e-15:
        raise ValueError("frontier control")
    candA=np.full_like(y,np.nan);candB=np.full_like(y,np.nan);records=[]
    for f in range(5):
        tr=np.flatnonzero(folds!=f);te=np.flatnonzero(folds==f)
        if set(patients[tr])&set(patients[te]):
            raise AssertionError("outer patient leakage")
        best,rows=select_joint(x,y,patients,catalog,tr,f)
        bundle=build_bundle(x,y,patients,catalog,tr)
        pred=predict_all(x,te,bundle)
        si=int(best["strength_index"]);ri=int(best["option_index"])
        candA[te]=pred[si,ri,0];candB[te]=pred[si,ri,1]
        records.append({"fold":f,"selected":best,"all_inner_candidates":rows})
        print(json.dumps({"event":"outer_complete","fold":f,
                          "quadratic_strength":best["quadratic_strength"],
                          "option":best["option"],"inner_mse":best["mse"]}),flush=True)
    if not np.isfinite(candA).all() or not np.isfinite(candB).all():
        raise AssertionError("candidate OOF incomplete")
    cm=parent.metrics(y,candA,candB,patients,folds)
    pdiff=cm["patient_losses"]-rm["patient_losses"]
    tdiff=cm["target_mse"]-rm["target_mse"]
    rng=np.random.default_rng(BOOTSTRAP_SEED)
    idx=rng.integers(0,len(pdiff),size=(BOOTSTRAP_REPS,len(pdiff)))
    boot=pdiff[idx].mean(1)
    comp={
      "relative_mse_gain":float(1-cm["mse"]/rm["mse"]),
      "patient_wins":int((pdiff<0).sum()),
      "patient_losses":int((pdiff>0).sum()),
      "fold_wins":int(sum(a<b for a,b in zip(cm["fold_mse"],rm["fold_mse"]))),
      "target_wins":int((tdiff<-1e-15).sum()),
      "target_regressions":int((tdiff>1e-15).sum()),
      "p90_nonworse":bool(cm["p90_patient_rmse"]<=rm["p90_patient_rmse"]),
      "bootstrap_percentile_95_ci":[float(np.quantile(boot,.025)),float(np.quantile(boot,.975))],
      "bootstrap_fraction_below_zero":float((boot<0).mean())
    }
    gate={"mse":cm["mse"]<rm["mse"],"patients":comp["patient_wins"]>=30,
          "folds":comp["fold_wins"]==5,"p90":comp["p90_nonworse"]}
    decision="GLOBAL_QUADRATIC_SUCCESSOR" if all(gate.values()) else "REJECT_GLOBAL_QUADRATIC"
    output=Path(output)
    if output.exists(): raise ValueError("output exists")
    output.mkdir(parents=True,exist_ok=False)
    np.savez_compressed(output/"predictions_private.npz",
      candidate_A=candA,candidate_B=candB,frontier_A=refA,frontier_B=refB,
      y=y,patients=patients,folds=folds,sample_ids=data["sample_ids"],drug_ids=data["drug_ids"])
    result={
      "schema":"dosepilot.budget72_global_quadratic.result.v1",
      "status":"COMPLETE",
      "role":"FROZEN_INNER_ONLY_GLOBAL_QUADRATIC_AUGMENTATION",
      "candidate":{"mse":cm["mse"],"p90_patient_rmse":cm["p90_patient_rmse"],
                   "fold_mse":cm["fold_mse"],"orientation_mse":cm["orientation_mse"]},
      "frontier72":{"mse":rm["mse"],"p90_patient_rmse":rm["p90_patient_rmse"],
                    "fold_mse":rm["fold_mse"],"orientation_mse":rm["orientation_mse"]},
      "candidate_vs_frontier":dict(comp,gate=gate),
      "selections":records,
      "treatment_wells":72,
      "decision":decision,
      "prediction_sha256":sha(output/"predictions_private.npz"),
      "input_sha256":fr["input_sha256"],"source_sha256":fr["source_sha256"],
      "target_specific_selection":False,"orientation_specific_selection":False,
      "protected22_access":False,"independent_validation":False,"automatic_retry":False
    }
    write_new(output/"RESULT.json",result)
    print(json.dumps({"decision":decision,"candidate":result["candidate"],
      "vs_frontier":result["candidate_vs_frontier"],
      "selected":[{"fold":r["fold"],"quadratic_strength":r["selected"]["quadratic_strength"],
                   "option":r["selected"]["option"]} for r in records]},indent=2))
    return result

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--curves",type=Path,required=True)
    ap.add_argument("--catalog",type=Path,required=True)
    ap.add_argument("--frontier72",type=Path,required=True)
    ap.add_argument("--output",type=Path,required=True)
    a=ap.parse_args()
    execute(a.curves,a.catalog,a.frontier72,a.output)

if __name__=="__main__":
    main()
