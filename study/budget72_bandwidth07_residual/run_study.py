#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,importlib.util,json,sys
from pathlib import Path
import numpy as np

HERE=Path(__file__).resolve().parent
STUDY=HERE.parent
REPO=STUDY.parent
sys.path[:0]=[str(STUDY),str(STUDY/"engine"),str(STUDY/"acceleration"),str(HERE)]
from compact_train import load_prepared
from methods import patient_folds
import evaluate
from fast_coverage import plan_panel_fast
from bandwidth_additive72 import BandwidthAdditive72

BC_PATH=STUDY/"budget_upgrade_curve"/"run_study.py"
spec=importlib.util.spec_from_file_location("budget_curve",BC_PATH)
bc=importlib.util.module_from_spec(spec);spec.loader.exec_module(bc)

OPTIONS=[("identity",0.0)]+[(f,l) for f in (0.1,0.3,0.6) for l in (0.1,1.0,10.0)]
EXPECTED72=0.0010055928901387746
EXPECTED64SUCCESSOR=0.001042745722096212
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

def patient_weights(patients):
    ids,inv,count=np.unique(patients,return_inverse=True,return_counts=True)
    return 1.0/(len(ids)*count[inv])

def build_bundle(x,y,patients,catalog,indices):
    full=plan_panel_fast(x[indices],y[indices],patients[indices],catalog)
    plan=bc.derive_budget(full,catalog,24)
    paidA=bc.acquire_budget(x[indices],plan,"A")
    paidB=bc.acquire_budget(x[indices],plan,"B")
    context=bc.fit_context(paidA,paidB,y[indices],patients[indices],plan,catalog.target_ids)
    base=bc.Predictor(context,plan,0.01)
    z=np.r_[paidA,paidB]
    z=(z-base.mean_x)/base.scale_x
    residual=np.r_[y[indices]-base.predict(paidA),y[indices]-base.predict(paidB)]
    w=np.tile(patient_weights(patients[indices]),2)/2
    owner=np.asarray(plan["coordinate_target_indices"],int)
    model=BandwidthAdditive72(z,residual,w,owner,0.7)
    coefs=[np.zeros_like(residual)]
    for frac,lam in OPTIONS[1:]:
        coefs.append(model.coefficients(lam,frac)[0])
    return plan,base,model,coefs

def predict_options(x,indices,bundle):
    plan,base,model,coefs=bundle
    out=np.empty((len(OPTIONS),2,len(indices),24))
    for oi,o in enumerate(("A","B")):
        paid=bc.acquire_budget(x[indices],plan,o)
        zq=(paid-base.mean_x)/base.scale_x
        bp=base.predict(paid)
        cross=model.centered_cross(zq)
        for i,c in enumerate(coefs):
            out[i,oi]=bp+cross@c
    return out

def check_freeze(curves,catalog,budget_predictions,current_successor):
    fr=json.loads((HERE/"FREEZE.json").read_text(encoding="utf-8"))
    if fr["state"]!="FROZEN_BEFORE_CANDIDATE_OUTCOME":
        raise ValueError("freeze state")
    paths={
      "train_curves":curves,
      "catalog":catalog,
      "budget_curve_predictions":budget_predictions,
      "current_64_successor":current_successor
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

def select_option(x,y,patients,catalog,outer_indices,outer_fold):
    inner,_=patient_folds(patients[outer_indices],3,evaluate.SALT+f"|inner|{outer_fold}")
    oof=np.full((len(OPTIONS),2,len(outer_indices),24),np.nan)
    for k in range(3):
        fit=outer_indices[inner!=k]
        val=outer_indices[inner==k]
        if set(patients[fit])&set(patients[val]):
            raise AssertionError("inner patient leakage")
        bundle=build_bundle(x,y,patients,catalog,fit)
        pred=predict_options(x,val,bundle)
        oof[:,:,inner==k]=pred
    if not np.isfinite(oof).all():
        raise AssertionError("inner OOF incomplete")
    scores=[]
    for i in range(len(OPTIONS)):
        _,pt=patient_target_losses(
          y[outer_indices],oof[i,0],oof[i,1],patients[outer_indices])
        scores.append(float(pt.mean()))
    chosen=min(range(len(OPTIONS)),key=lambda i:(scores[i],i))
    return chosen,scores

def execute(curves,catalog_path,budget_predictions,current_successor,output):
    fr=check_freeze(curves,catalog_path,budget_predictions,current_successor)
    data,features,_=load_prepared(curves,catalog_path)
    x=features["x_replicates"]
    y=data["y"]
    patients=data["patient_ids"].astype(str)
    catalog=bc.catalog_from_features(features)
    budget=np.load(budget_predictions,allow_pickle=False)
    prior=np.load(current_successor,allow_pickle=False)
    if not np.array_equal(budget["y"],y) or not np.array_equal(budget["patients"].astype(str),patients):
        raise ValueError("budget identity")
    if not np.array_equal(prior["y"],y) or not np.array_equal(prior["patients"].astype(str),patients):
        raise ValueError("successor identity")
    folds=budget["folds"]
    if not np.array_equal(prior["folds"],folds):
        raise ValueError("fold identity")
    recomputed,_=patient_folds(patients,5,evaluate.SALT+"|outer")
    if not np.array_equal(recomputed,folds):
        raise ValueError("outer fold recipe changed")
    base72A=budget["pred72_A"].copy()
    base72B=budget["pred72_B"].copy()
    priorA=prior["candidate"][0].copy()
    priorB=prior["candidate"][1].copy()
    bm=metrics(y,base72A,base72B,patients,folds)
    pm=metrics(y,priorA,priorB,patients,folds)
    if abs(bm["mse"]-EXPECTED72)>1e-15:
        raise ValueError("72 base control")
    if abs(pm["mse"]-EXPECTED64SUCCESSOR)>1e-15:
        raise ValueError("64 successor control")
    candA=np.full_like(y,np.nan)
    candB=np.full_like(y,np.nan)
    regenA=np.full_like(y,np.nan)
    regenB=np.full_like(y,np.nan)
    selections=[]
    for f in range(5):
        tr=np.flatnonzero(folds!=f)
        te=np.flatnonzero(folds==f)
        if set(patients[tr])&set(patients[te]):
            raise AssertionError("outer patient leakage")
        chosen,scores=select_option(x,y,patients,catalog,tr,f)
        bundle=build_bundle(x,y,patients,catalog,tr)
        pred=predict_options(x,te,bundle)
        regenA[te]=pred[0,0]
        regenB[te]=pred[0,1]
        candA[te]=pred[chosen,0]
        candB[te]=pred[chosen,1]
        plan=bundle[0]
        bc.validate_budget(plan,catalog,24)
        selections.append({
          "fold":f,
          "selected_index":chosen,
          "selected_option":OPTIONS[chosen],
          "inner_mse":scores,
          "treatment_wells":72,
          "per_plate":[36,36]
        })
        print(json.dumps({"event":"outer_complete","fold":f,
                          "selected":OPTIONS[chosen],"inner_mse":scores[chosen]}),flush=True)
    if not np.isfinite(candA).all() or not np.isfinite(candB).all():
        raise AssertionError("candidate OOF incomplete")
    base_replay_maxdiff=max(
      float(np.max(np.abs(regenA-base72A))),
      float(np.max(np.abs(regenB-base72B))))
    if base_replay_maxdiff>1e-12:
        raise ValueError(f"72 base replay mismatch {base_replay_maxdiff}")
    cm=metrics(y,candA,candB,patients,folds)
    pdiff=cm["patient_losses"]-bm["patient_losses"]
    tdiff=cm["target_mse"]-bm["target_mse"]
    rng=np.random.default_rng(BOOTSTRAP_SEED)
    idx=rng.integers(0,len(pdiff),size=(BOOTSTRAP_REPS,len(pdiff)))
    boot=pdiff[idx].mean(1)
    comp_base={
      "relative_mse_gain":float(1-cm["mse"]/bm["mse"]),
      "patient_wins":int((pdiff<0).sum()),
      "patient_losses":int((pdiff>0).sum()),
      "fold_wins":int(sum(a<b for a,b in zip(cm["fold_mse"],bm["fold_mse"]))),
      "target_wins":int((tdiff<-1e-15).sum()),
      "target_regressions":int((tdiff>1e-15).sum()),
      "p90_nonworse":bool(cm["p90_patient_rmse"]<=bm["p90_patient_rmse"]),
      "bootstrap_percentile_95_ci":[float(np.quantile(boot,.025)),float(np.quantile(boot,.975))],
      "bootstrap_fraction_below_zero":float((boot<0).mean())
    }
    ppdiff=cm["patient_losses"]-pm["patient_losses"]
    comp_prior={
      "relative_mse_gain":float(1-cm["mse"]/pm["mse"]),
      "patient_wins":int((ppdiff<0).sum()),
      "patient_losses":int((ppdiff>0).sum()),
      "fold_wins":int(sum(a<b for a,b in zip(cm["fold_mse"],pm["fold_mse"]))),
      "p90_nonworse":bool(cm["p90_patient_rmse"]<=pm["p90_patient_rmse"])
    }
    gate={
      "mse":cm["mse"]<bm["mse"],
      "patients":comp_base["patient_wins"]>=30,
      "folds":comp_base["fold_wins"]==5,
      "p90":comp_base["p90_nonworse"]
    }
    decision="LOWER_ERROR_72_WELL_RESIDUAL_FRONTIER" if all(gate.values()) else "REJECT_RESIDUAL_TRANSFER"
    output=Path(output)
    if output.exists():
        raise ValueError("output exists")
    output.mkdir(parents=True,exist_ok=False)
    np.savez_compressed(
      output/"predictions_private.npz",
      candidate_A=candA,candidate_B=candB,
      base72_A=base72A,base72_B=base72B,
      current64_A=priorA,current64_B=priorB,
      regenerated72_A=regenA,regenerated72_B=regenB,
      y=y,patients=patients,folds=folds,
      sample_ids=data["sample_ids"],drug_ids=data["drug_ids"])
    result={
      "schema":"dosepilot.budget72_bandwidth07_residual.result.v1",
      "status":"COMPLETE",
      "role":"FROZEN_TRANSFER_OF_EXISTING_BANDWIDTH07_RESIDUAL_FAMILY",
      "candidate":{"mse":cm["mse"],"p90_patient_rmse":cm["p90_patient_rmse"],
                   "fold_mse":cm["fold_mse"],"orientation_mse":cm["orientation_mse"]},
      "base72":{"mse":bm["mse"],"p90_patient_rmse":bm["p90_patient_rmse"],
                "fold_mse":bm["fold_mse"]},
      "current64_successor":{"mse":pm["mse"],"p90_patient_rmse":pm["p90_patient_rmse"],
                             "fold_mse":pm["fold_mse"]},
      "candidate_vs_base72":dict(comp_base,gate=gate),
      "candidate_vs_current64_successor":comp_prior,
      "selections":selections,
      "base72_replay_maxdiff":base_replay_maxdiff,
      "decision":decision,
      "prediction_sha256":sha(output/"predictions_private.npz"),
      "input_sha256":fr["input_sha256"],
      "source_sha256":fr["source_sha256"],
      "protected22_access":False,
      "independent_validation":False,
      "automatic_retry":False
    }
    write_new(output/"RESULT.json",result)
    print(json.dumps({"decision":decision,"candidate":result["candidate"],
      "vs_base72":result["candidate_vs_base72"],
      "vs_current64":result["candidate_vs_current64_successor"],
      "base_replay_maxdiff":base_replay_maxdiff},indent=2))
    return result

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--curves",type=Path,required=True)
    ap.add_argument("--catalog",type=Path,required=True)
    ap.add_argument("--budget-predictions",type=Path,required=True)
    ap.add_argument("--current-successor",type=Path,required=True)
    ap.add_argument("--output",type=Path,required=True)
    a=ap.parse_args()
    execute(a.curves,a.catalog,a.budget_predictions,a.current_successor,a.output)

if __name__=="__main__":
    main()
