#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, sys
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/"study"),str(ROOT/"study"/"engine")]
import evaluate as first
from compact_train import load_prepared
from methods import patient_folds
from sparse_methods import LAMBDAS, fit_sparse_context
from coverage_methods import CoveragePredictor, acquire, catalog_from_features, fit_prediction_context, orientation_errors, plan_panel, validate_plan

EXPECTED_CURVES="b192dc242362d74c4faa941752792336c7610d9bd403cccbf1cee7a8a1fc7c94"
EXPECTED_CATALOG="84eae3976307448ac696852d39d1b2376cce479d8af5e386ce04097020deff5e"
EXPECTED_R13=0.001144858681382854
B48=48
TARGETS=24
BOOTSTRAP_SEED=20261006
BOOTSTRAP_REPS=100000

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def write_json(path,obj):
    Path(path).write_text(json.dumps(obj,indent=2,allow_nan=False)+"\n",encoding="utf-8",newline="\n")

def validate48(plan,catalog=None):
    sel=np.asarray(plan["selected_native_indices"],int)
    own=np.asarray(plan["coordinate_target_indices"],int)
    a=np.asarray(plan["orientation_A_plate_indices"],int)
    b=np.asarray(plan["orientation_B_plate_indices"],int)
    counts=np.bincount(own,minlength=TARGETS)
    if sel.shape!=(B48,) or len(set(sel.tolist()))!=B48:
        raise ValueError("48-plan must contain 48 distinct native doses")
    if own.shape!=(B48,) or not np.array_equal(counts,np.full(TARGETS,2)):
        raise ValueError("48-plan must contain exactly two native doses per target")
    if a.shape!=(B48,) or b.shape!=(B48,) or not np.array_equal(b,1-a):
        raise ValueError("48-plan orientations malformed")
    if int((a==0).sum())!=24 or int((a==1).sum())!=24:
        raise ValueError("48-plan must buy 24 wells from each plate")
    if catalog is not None:
        if not np.array_equal(own,catalog.native_target_indices[sel]):
            raise ValueError("48-plan target ownership changed")
        if plan["selected_native_ids"]!=list(map(str,catalog.native_ids[sel])):
            raise ValueError("48-plan native identities changed")

def derive48(full_plan,catalog):
    validate_plan(full_plan,catalog)
    selected=[]; ownership=[]; plates=[]
    choices=full_plan["choices"]
    if len(choices)!=TARGETS:
        raise ValueError("full plan choices changed")
    for target,row in enumerate(choices):
        if int(row["target_index"])!=target:
            raise ValueError("choice order changed")
        subset=list(map(int,row["best2"]))
        if len(subset)!=2:
            raise ValueError("best2 changed")
        selected.extend(subset); ownership.extend([target,target]); plates.extend([0,1])
    plan={
      "library_id":catalog.library_id,
      "selected_native_indices":selected,
      "selected_native_ids":[str(catalog.native_ids[q]) for q in selected],
      "coordinate_target_indices":ownership,
      "selected_concentrations_nM":[str(catalog.concentrations[q]) for q in selected],
      "orientation_A_plate_indices":plates,
      "orientation_B_plate_indices":[1-p for p in plates],
      "treatment_wells_per_orientation":48,
      "plate_wells_per_orientation":{"p1":24,"p2":24},
      "prediction_semantics":"raw purchased single-well normalized viability",
      "ablation_semantics":"same R13 allocation objective, all targets forced to best fitting-only size-2 subset"
    }
    validate48(plan,catalog)
    return plan

def acquire48(replicates,plan,orientation):
    validate48(plan)
    if orientation not in ("A","B"): raise ValueError("orientation")
    x=np.asarray(replicates,float)
    sel=np.asarray(plan["selected_native_indices"],int)
    plates=np.asarray(plan[f"orientation_{orientation}_plate_indices"],int)
    paid=x[:,sel,plates].copy()
    if paid.shape!=(len(x),B48) or not np.isfinite(paid).all():
        raise ValueError("48 acquisition malformed")
    return paid

def fit_context48(a,b,y,patients,plan,target_ids):
    validate48(plan)
    if a.shape!=b.shape or a.shape!=(len(y),B48): raise ValueError("48 fitting arrays malformed")
    return fit_sparse_context(np.concatenate((a,b)),np.concatenate((y,y)),np.concatenate((patients,patients)),plan["selected_native_ids"],target_ids)

class Predictor48:
    def __init__(self,context,plan,lam):
        validate48(plan)
        if lam not in LAMBDAS: raise ValueError("lambda")
        self.mean_x=context.mean_x.copy(); self.scale_x=context.scale_x.copy(); self.mean_y=context.mean_y.copy()
        own=np.asarray(plan["coordinate_target_indices"])
        self.beta=np.zeros((B48,TARGETS))
        for target in range(TARGETS):
            cols=np.flatnonzero(own==target)
            self.beta[cols,target]=np.linalg.solve(context.cxx[np.ix_(cols,cols)]+float(lam)*np.eye(len(cols)),context.cxy[cols,target])
    def predict(self,paid):
        paid=np.asarray(paid,float)
        if paid.ndim!=2 or paid.shape[1]!=B48 or not np.isfinite(paid).all(): raise ValueError("48 prediction input")
        out=self.mean_y+((paid-self.mean_x)/self.scale_x)@self.beta
        if not np.isfinite(out).all(): raise ValueError("nonfinite prediction")
        return out

def patient_target_losses(cell_target_losses,patients):
    patients=np.asarray(patients,str)
    ids=np.asarray(sorted(set(patients)))
    return ids,np.stack([cell_target_losses[patients==g].mean(axis=0) for g in ids])

def choose_lambdas(x,y,patients,catalog,outer_fold):
    inner,_=patient_folds(patients,3,first.SALT+f"|inner|{outer_fold}")
    oof={arm:{o:[np.full_like(y,np.nan) for _ in LAMBDAS] for o in ("A","B")} for arm in ("48","64")}
    for f in range(3):
        tr,va=inner!=f,inner==f
        if set(patients[tr])&set(patients[va]): raise AssertionError("inner patient leakage")
        p64=plan_panel(x[tr],y[tr],patients[tr],catalog)
        p48=derive48(p64,catalog)
        a64,b64=[acquire(x[tr],p64,o) for o in ("A","B")]
        c64=fit_prediction_context(a64,b64,y[tr],patients[tr],p64,catalog.target_ids)
        a48,b48=[acquire48(x[tr],p48,o) for o in ("A","B")]
        c48=fit_context48(a48,b48,y[tr],patients[tr],p48,catalog.target_ids)
        v64={o:acquire(x[va],p64,o) for o in ("A","B")}
        v48={o:acquire48(x[va],p48,o) for o in ("A","B")}
        for i,lam in enumerate(LAMBDAS):
            m64=CoveragePredictor(c64,p64,lam)
            m48=Predictor48(c48,p48,lam)
            for o in ("A","B"):
                oof["64"][o][i][va]=m64.predict(v64[o])
                oof["48"][o][i][va]=m48.predict(v48[o])
    chosen={}
    for arm in ("48","64"):
        rows=[]
        for i,lam in enumerate(LAMBDAS):
            pa,pb=oof[arm]["A"][i],oof[arm]["B"][i]
            if not np.isfinite(pa).all() or not np.isfinite(pb).all():
                raise AssertionError("inner OOF incomplete")
            _,pt=patient_target_losses(orientation_errors(y,pa,pb),patients)
            rows.append({"lambda_index":i,"lambda":float(lam),"mean_expected_mse":float(pt.mean())})
        chosen[arm]={"selected":min(rows,key=lambda r:(r["mean_expected_mse"],r["lambda_index"])),"all":rows}
    return chosen

def metrics(y,pa,pb,patients,folds):
    _,pt=patient_target_losses(orientation_errors(y,pa,pb),patients)
    per=pt.mean(axis=1)
    groups=np.asarray(sorted(set(patients)))
    pf=np.asarray([int(np.unique(folds[patients==g])[0]) for g in groups])
    return {
      "mse":float(per.mean()),
      "p90_patient_rmse":float(np.quantile(np.sqrt(per),0.9)),
      "patient_losses":per,
      "target_mse":pt.mean(axis=0),
      "fold_mse":[float(per[pf==f].mean()) for f in range(5)]
    }

def check_freeze(curves,catalog):
    here=Path(__file__).resolve().parent
    fr=json.loads((here/"FREEZE.json").read_text(encoding="utf-8"))
    if fr["state"]!="FROZEN_BEFORE_FIRST_REAL_DATA_EVALUATION":
        raise ValueError("freeze state")
    if sha(curves)!=fr["input_sha256"]["train_curves"] or sha(catalog)!=fr["input_sha256"]["catalog"]:
        raise ValueError("input hash changed")
    for rel,h in fr["source_sha256"].items():
        if sha(ROOT/rel)!=h: raise ValueError("source changed: "+rel)
    return fr

def execute(curves,catalog_path,output):
    fr=check_freeze(curves,catalog_path)
    data,features,_=load_prepared(curves,catalog_path)
    y=data["y"]; patients=data["patient_ids"].astype(str)
    x=features["x_replicates"]; samples=data["sample_ids"].astype(str)
    catalog=catalog_from_features(features)
    folds,assignments=patient_folds(patients,5,first.SALT+"|outer")
    pred={arm:{o:np.full_like(y,np.nan) for o in ("A","B")} for arm in ("48","64")}
    selections=[]; plan_rows=[]
    for f in range(5):
        tr,te=folds!=f,folds==f
        if set(patients[tr])&set(patients[te]):
            raise AssertionError("outer patient leakage")
        sel=choose_lambdas(x[tr],y[tr],patients[tr],catalog,f)
        p64=plan_panel(x[tr],y[tr],patients[tr],catalog)
        p48=derive48(p64,catalog)
        c64=fit_prediction_context(acquire(x[tr],p64,"A"),acquire(x[tr],p64,"B"),y[tr],patients[tr],p64,catalog.target_ids)
        c48=fit_context48(acquire48(x[tr],p48,"A"),acquire48(x[tr],p48,"B"),y[tr],patients[tr],p48,catalog.target_ids)
        m64=CoveragePredictor(c64,p64,sel["64"]["selected"]["lambda"])
        m48=Predictor48(c48,p48,sel["48"]["selected"]["lambda"])
        for o in ("A","B"):
            pred["64"][o][te]=m64.predict(acquire(x[te],p64,o))
            pred["48"][o][te]=m48.predict(acquire48(x[te],p48,o))
        selections.append({"outer_fold":f,"selection":sel})
        plan_rows.append({
          "outer_fold":f,"wells48":48,"plates48":[24,24],
          "wells64":64,"plates64":[32,32],
          "upgraded64":p64["upgraded_target_ids"]
        })
        print(json.dumps({
          "event":"outer_complete","fold":f,
          "lambda48":sel["48"]["selected"]["lambda"],
          "lambda64":sel["64"]["selected"]["lambda"]
        }),flush=True)
    if any(not np.isfinite(pred[a][o]).all() for a in pred for o in ("A","B")):
        raise AssertionError("OOF incomplete")
    m48=metrics(y,pred["48"]["A"],pred["48"]["B"],patients,folds)
    m64=metrics(y,pred["64"]["A"],pred["64"]["B"],patients,folds)
    if abs(m64["mse"]-EXPECTED_R13)>1e-12:
        raise ValueError(f"R13 reproduction failed {m64['mse']}")
    patient_delta=m64["patient_losses"]-m48["patient_losses"]
    target_delta=m64["target_mse"]-m48["target_mse"]
    rng=np.random.default_rng(BOOTSTRAP_SEED)
    idx=rng.integers(0,len(patient_delta),size=(BOOTSTRAP_REPS,len(patient_delta)))
    boot=patient_delta[idx].mean(axis=1)
    result={
      "schema":"dosepilot.budget48_two_dose_ablation.result.v1",
      "status":"PASS",
      "role":"POST_HOC_BUDGET_ABLATION_NOT_CANDIDATE_PROMOTION",
      "population":{"samples":119,"whole_patients":59,"targets":24},
      "arm48":{"treatment_wells":48,"plate_wells":[24,24],"mse":m48["mse"],
               "p90_patient_rmse":m48["p90_patient_rmse"],"fold_mse":m48["fold_mse"]},
      "arm64":{"treatment_wells":64,"plate_wells":[32,32],"mse":m64["mse"],
               "p90_patient_rmse":m64["p90_patient_rmse"],"fold_mse":m64["fold_mse"]},
      "comparison_64_minus_48":{
        "mean_loss_difference":float(patient_delta.mean()),
        "relative_mse_change":float(m64["mse"]/m48["mse"]-1),
        "patient_wins_64":int((patient_delta<0).sum()),
        "patient_losses_64":int((patient_delta>0).sum()),
        "favorable_folds_64":int(sum(a<b for a,b in zip(m64["fold_mse"],m48["fold_mse"]))),
        "target_wins_64":int((target_delta<0).sum()),
        "target_losses_64":int((target_delta>0).sum()),
        "bootstrap_percentile_95_ci":[float(np.quantile(boot,.025)),float(np.quantile(boot,.975))],
        "bootstrap_fraction_64_better":float((boot<0).mean())
      },
      "selection_by_outer_fold":selections,
      "plan_audit":plan_rows,
      "input_sha256":fr["input_sha256"],
      "source_sha256":fr["source_sha256"],
      "protected22_access":False,
      "independent_validation":False,
      "selection_adjusted":False,
      "candidate_promotion_allowed":False,
      "automatic_retry":False,
      "warning":"Repeated adaptive Lib1 development; this is a retrospective budget ablation, not independent validation."
    }
    output=Path(output); output.mkdir(parents=True,exist_ok=False)
    write_json(output/"RESULT.json",result)
    np.savez_compressed(
      output/"predictions_private.npz",y=y,patients=patients,samples=samples,
      folds=folds,drug_ids=catalog.target_ids,
      pred48_A=pred["48"]["A"],pred48_B=pred["48"]["B"],
      pred64_A=pred["64"]["A"],pred64_B=pred["64"]["B"])
    write_json(output/"FOLD_ASSIGNMENTS.json",assignments)
    print(json.dumps(result,indent=2),flush=True)
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
