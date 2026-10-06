#!/usr/bin/env python3
from __future__ import annotations
import argparse
import hashlib
import json
import sys
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/"study"),str(ROOT/"study"/"engine")]
import evaluate as first
from compact_train import load_prepared
from methods import patient_folds
from sparse_methods import LAMBDAS, fit_sparse_context
from coverage_methods import plan_panel, catalog_from_features, orientation_errors

BUDGETS=(48,52,56,60,64,68,72)
UPGRADES=(0,4,8,12,16,20,24)
EXPECTED48=0.0015432725382030184
EXPECTED64=0.001144858681382854
TARGETS=24

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def write_json(path,obj):
    Path(path).write_text(json.dumps(obj,indent=2,allow_nan=False)+"\n",encoding="utf-8",newline="\n")

def validate_budget(plan,catalog,k):
    budget=48+k
    sel=np.asarray(plan["selected_native_indices"],int)
    own=np.asarray(plan["coordinate_target_indices"],int)
    a=np.asarray(plan["orientation_A_plate_indices"],int)
    b=np.asarray(plan["orientation_B_plate_indices"],int)
    counts=np.bincount(own,minlength=TARGETS)
    if sel.shape!=(budget,) or len(set(sel.tolist()))!=budget:
        raise ValueError("budget size or uniqueness")
    if int((counts==3).sum())!=k or int((counts==2).sum())!=TARGETS-k:
        raise ValueError("target dose counts")
    if a.shape!=(budget,) or b.shape!=(budget,) or not np.array_equal(b,1-a):
        raise ValueError("orientation shape")
    if int((a==0).sum())!=budget//2 or int((a==1).sum())!=budget//2:
        raise ValueError("plate balance")
    if not np.array_equal(own,catalog.native_target_indices[sel]):
        raise ValueError("ownership")
    if plan["selected_native_ids"]!=list(map(str,catalog.native_ids[sel])):
        raise ValueError("native identities")

def derive_budget(full_plan,catalog,k):
    if k not in UPGRADES: raise ValueError("upgrade count")
    choices=full_plan["choices"]
    ranked=sorted(choices,key=lambda r:(-r["upgrade_gain"],r["target_id"]))
    upgraded={int(r["target_index"]) for r in ranked[:k]}
    order=sorted(upgraded,key=lambda t:str(catalog.target_ids[t]))
    starts={t:i%2 for i,t in enumerate(order)}
    selected=[]; own=[]; plate=[]
    for t in range(TARGETS):
        subset=list(map(int,choices[t]["best3" if t in upgraded else "best2"]))
        start=starts.get(t,0)
        selected.extend(subset)
        own.extend([t]*len(subset))
        plate.extend([(start+i)%2 for i in range(len(subset))])
    plan={
      "selected_native_indices":selected,
      "selected_native_ids":[str(catalog.native_ids[q]) for q in selected],
      "coordinate_target_indices":own,
      "orientation_A_plate_indices":plate,
      "orientation_B_plate_indices":[1-p for p in plate],
      "upgrade_count":k,
      "treatment_wells_per_orientation":48+k
    }
    validate_budget(plan,catalog,k)
    if k==16:
        keys=("selected_native_indices","selected_native_ids","coordinate_target_indices","orientation_A_plate_indices","orientation_B_plate_indices")
        for key in keys:
            if list(plan[key])!=list(full_plan[key]):
                raise ValueError("64-well derived plan differs from R13")
    return plan

def acquire_budget(x,plan,o):
    if o not in ("A","B"): raise ValueError("orientation")
    sel=np.asarray(plan["selected_native_indices"],int)
    plates=np.asarray(plan[f"orientation_{o}_plate_indices"],int)
    out=np.asarray(x,float)[:,sel,plates].copy()
    if not np.isfinite(out).all(): raise ValueError("nonfinite paid values")
    return out

def fit_context(a,b,y,patients,plan,target_ids):
    xx=np.concatenate((a,b))
    yy=np.concatenate((y,y))
    pp=np.concatenate((patients,patients))
    return fit_sparse_context(xx,yy,pp,plan["selected_native_ids"],target_ids)

class Predictor:
    def __init__(self,context,plan,lam):
        own=np.asarray(plan["coordinate_target_indices"])
        n=len(own)
        self.mean_x=context.mean_x.copy()
        self.scale_x=context.scale_x.copy()
        self.mean_y=context.mean_y.copy()
        self.beta=np.zeros((n,TARGETS))
        for t in range(TARGETS):
            cols=np.flatnonzero(own==t)
            mat=context.cxx[np.ix_(cols,cols)]+float(lam)*np.eye(len(cols))
            self.beta[cols,t]=np.linalg.solve(mat,context.cxy[cols,t])

    def predict(self,paid):
        paid=np.asarray(paid,float)
        out=self.mean_y+((paid-self.mean_x)/self.scale_x)@self.beta
        if not np.isfinite(out).all(): raise ValueError("nonfinite prediction")
        return out

def patient_target_losses(losses,patients):
    patients=np.asarray(patients,str)
    ids=np.asarray(sorted(set(patients)))
    return ids,np.stack([losses[patients==g].mean(axis=0) for g in ids])

def metrics(y,pa,pb,patients,folds):
    _,pt=patient_target_losses(orientation_errors(y,pa,pb),patients)
    per=pt.mean(axis=1)
    groups=np.asarray(sorted(set(patients)))
    pf=np.asarray([int(np.unique(folds[patients==g])[0]) for g in groups])
    return {
      "mse":float(per.mean()),
      "p90_patient_rmse":float(np.quantile(np.sqrt(per),0.9)),
      "fold_mse":[float(per[pf==f].mean()) for f in range(5)],
      "patient_losses":per,
      "target_mse":pt.mean(axis=0)
    }

def choose_lambdas(x,y,patients,catalog,outer_fold):
    inner,_=patient_folds(patients,3,first.SALT+f"|inner|{outer_fold}")
    oof={b:{o:[np.full_like(y,np.nan) for _ in LAMBDAS] for o in ("A","B")} for b in BUDGETS}
    for f in range(3):
        tr,va=inner!=f,inner==f
        if set(patients[tr])&set(patients[va]): raise AssertionError("inner leakage")
        full=plan_panel(x[tr],y[tr],patients[tr],catalog)
        for budget,k in zip(BUDGETS,UPGRADES):
            plan=derive_budget(full,catalog,k)
            a,b=[acquire_budget(x[tr],plan,o) for o in ("A","B")]
            ctx=fit_context(a,b,y[tr],patients[tr],plan,catalog.target_ids)
            va_paid={o:acquire_budget(x[va],plan,o) for o in ("A","B")}
            for i,lam in enumerate(LAMBDAS):
                model=Predictor(ctx,plan,lam)
                for o in ("A","B"):
                    oof[budget][o][i][va]=model.predict(va_paid[o])
    chosen={}
    for budget in BUDGETS:
        rows=[]
        for i,lam in enumerate(LAMBDAS):
            a=oof[budget]["A"][i]; b=oof[budget]["B"][i]
            if not np.isfinite(a).all() or not np.isfinite(b).all():
                raise AssertionError("inner OOF incomplete")
            _,pt=patient_target_losses(orientation_errors(y,a,b),patients)
            rows.append({"lambda_index":i,"lambda":float(lam),"mean_expected_mse":float(pt.mean())})
        chosen[budget]={"selected":min(rows,key=lambda r:(r["mean_expected_mse"],r["lambda_index"])),"all":rows}
    return chosen

def check_freeze(curves,catalog):
    here=Path(__file__).resolve().parent
    fr=json.loads((here/"FREEZE.json").read_text(encoding="utf-8"))
    if fr["state"]!="FROZEN_BEFORE_FIRST_REAL_DATA_EVALUATION": raise ValueError("freeze state")
    if sha(curves)!=fr["input_sha256"]["train_curves"]: raise ValueError("curve hash")
    if sha(catalog)!=fr["input_sha256"]["catalog"]: raise ValueError("catalog hash")
    for rel,h in fr["source_sha256"].items():
        if sha(ROOT/rel)!=h: raise ValueError("source changed: "+rel)
    return fr

def execute(curves,catalog_path,output):
    fr=check_freeze(curves,catalog_path)
    data,features,_=load_prepared(curves,catalog_path)
    y=data["y"]; patients=data["patient_ids"].astype(str)
    x=features["x_replicates"]; catalog=catalog_from_features(features)
    folds,_=patient_folds(patients,5,first.SALT+"|outer")
    pred={b:{o:np.full_like(y,np.nan) for o in ("A","B")} for b in BUDGETS}
    selections=[]
    for f in range(5):
        tr,te=folds!=f,folds==f
        if set(patients[tr])&set(patients[te]): raise AssertionError("outer leakage")
        chosen=choose_lambdas(x[tr],y[tr],patients[tr],catalog,f)
        full=plan_panel(x[tr],y[tr],patients[tr],catalog)
        fold_sel={"outer_fold":f,"budgets":{}}
        for budget,k in zip(BUDGETS,UPGRADES):
            plan=derive_budget(full,catalog,k)
            a,b=[acquire_budget(x[tr],plan,o) for o in ("A","B")]
            ctx=fit_context(a,b,y[tr],patients[tr],plan,catalog.target_ids)
            lam=chosen[budget]["selected"]["lambda"]
            model=Predictor(ctx,plan,lam)
            for o in ("A","B"):
                pred[budget][o][te]=model.predict(acquire_budget(x[te],plan,o))
            fold_sel["budgets"][str(budget)]=chosen[budget]
        selections.append(fold_sel)
        print(json.dumps({"event":"outer_complete","fold":f,
              "lambdas":{str(b):chosen[b]["selected"]["lambda"] for b in BUDGETS}}),flush=True)
    results={}
    private={}
    for budget in BUDGETS:
        a=pred[budget]["A"]; b=pred[budget]["B"]
        if not np.isfinite(a).all() or not np.isfinite(b).all():
            raise AssertionError("OOF incomplete")
        m=metrics(y,a,b,patients,folds)
        results[str(budget)]={
          "treatment_wells":budget,
          "plate_wells":[budget//2,budget//2],
          "upgrade_count":budget-48,
          "mse":m["mse"],
          "p90_patient_rmse":m["p90_patient_rmse"],
          "fold_mse":m["fold_mse"]
        }
        private[budget]=m
    if abs(results["48"]["mse"]-EXPECTED48)>1e-12: raise ValueError("48 reproduction")
    if abs(results["64"]["mse"]-EXPECTED64)>1e-12: raise ValueError("64 reproduction")
    adjacent=[]
    for lo,hi in zip(BUDGETS[:-1],BUDGETS[1:]):
        pm=private[hi]["patient_losses"]-private[lo]["patient_losses"]
        tm=private[hi]["target_mse"]-private[lo]["target_mse"]
        adjacent.append({
          "from_wells":lo,"to_wells":hi,"added_wells":hi-lo,
          "absolute_mse_reduction":results[str(lo)]["mse"]-results[str(hi)]["mse"],
          "relative_mse_reduction":1-results[str(hi)]["mse"]/results[str(lo)]["mse"],
          "patient_wins_higher_budget":int((pm<0).sum()),
          "patient_losses_higher_budget":int((pm>0).sum()),
          "favorable_folds_higher_budget":int(sum(a<b for a,b in zip(results[str(hi)]["fold_mse"],results[str(lo)]["fold_mse"]))),
          "target_wins_higher_budget":int((tm<-1e-15).sum()),
          "target_regressions_higher_budget":int((tm>1e-15).sum())
        })
    result={
      "schema":"dosepilot.budget_upgrade_curve.result.v1",
      "status":"PASS",
      "role":"POST_HOC_MEASUREMENT_BUDGET_CURVE_NOT_CANDIDATE_PROMOTION",
      "population":{"samples":119,"whole_patients":59,"targets":24},
      "budgets":results,
      "adjacent_comparisons":adjacent,
      "selection_by_outer_fold":selections,
      "input_sha256":fr["input_sha256"],
      "source_sha256":fr["source_sha256"],
      "protected22_access":False,
      "independent_validation":False,
      "selection_adjusted":False,
      "candidate_promotion_allowed":False,
      "automatic_retry":False,
      "warning":"Repeated adaptive Lib1 development; this frozen budget curve is retrospective and not independent validation."
    }
    output=Path(output); output.mkdir(parents=True,exist_ok=False)
    write_json(output/"RESULT.json",result)
    np.savez_compressed(output/"predictions_private.npz",y=y,patients=patients,folds=folds,
      **{f"pred{budget}_{o}":pred[budget][o] for budget in BUDGETS for o in ("A","B")})
    print(json.dumps({"event":"complete","budgets":results,"adjacent":adjacent},indent=2),flush=True)
    return result

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--curves",type=Path,required=True)
    ap.add_argument("--catalog",type=Path,required=True)
    ap.add_argument("--output",type=Path,required=True)
    a=ap.parse_args()
    if a.output.exists(): raise SystemExit("output exists; no retry")
    execute(a.curves,a.catalog,a.output)

if __name__=="__main__":
    main()
