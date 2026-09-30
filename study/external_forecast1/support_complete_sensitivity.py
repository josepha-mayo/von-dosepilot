#!/usr/bin/env python3
"""External CRC-organoid sparse-reconstruction replication.

Training data are the public community cohort. FORECAST-1 is evaluation only.
The protocol in PROTOCOL.md was frozen before aggregate external scoring.
"""
from __future__ import annotations
import argparse, hashlib, json, math, re, time
from itertools import combinations
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold

DRUGS = ("5FU","SN38","Regorafenib","Erlotinib","TAS-102","Gemcitabine")
LAMBDAS = (0.01,0.1,1.0,10.0)
ALPHA = 0.1
UPGRADES = 4
BUDGET = 16
SCALE_FLOOR = 0.05

def sha(path):
    with Path(path).open("rb") as f:
        return hashlib.file_digest(f,"sha256").hexdigest()

def dump(path,obj):
    with Path(path).open("x",encoding="utf-8") as f:
        json.dump(obj,f,indent=2,sort_keys=True,allow_nan=False)
        f.write("\n")

def patient_id(sample):
    m=re.match(r"^(WCB\d+)",str(sample))
    if not m: raise ValueError("Unexpected sample identity: "+str(sample))
    return m.group(1)

def compatible_dose_grids(a,b):
    """Same assay grid allowing only source-table decimal rounding."""
    a=np.asarray(a,float); b=np.asarray(b,float)
    return a.shape==b.shape and np.allclose(a,b,rtol=1e-3,atol=1e-12)
def load_raw(path):
    frame=pd.read_excel(path,sheet_name="Single agents",engine="openpyxl")
    if list(frame.columns[:2]) != ["Compound","Concentration (uM)"]:
        raise ValueError("Unexpected raw workbook schema")
    samples=np.asarray(list(map(str,frame.columns[2:])))
    if len(samples)!=len(set(samples)): raise ValueError("Duplicate sample column")
    patients=np.asarray([patient_id(s) for s in samples])
    blocks=[]; doses=[]
    for drug in DRUGS:
        part=frame.loc[frame["Compound"].eq(drug)]
        if len(part)!=9: raise ValueError(f"{drug}: expected 9 doses")
        x=part["Concentration (uM)"].to_numpy(float)
        if not np.isfinite(x).all() or np.any(x<=0) or np.any(np.diff(x)<=0):
            raise ValueError(f"{drug}: invalid dose grid")
        v=part.iloc[:,2:].to_numpy(float).T
        if v.shape!=(len(samples),9) or not np.isfinite(v).all():
            raise ValueError(f"{drug}: incomplete values")
        doses.append(x); blocks.append(v)
    return samples,patients,np.stack(blocks,axis=1),np.stack(doses)

def patient_weights(patients):
    patients=np.asarray(patients)
    ids,inv,cnt=np.unique(patients,return_inverse=True,return_counts=True)
    return 1.0/(len(ids)*cnt[inv])

def auc_targets(values,doses):
    values=np.asarray(values,float); doses=np.asarray(doses,float)
    out=np.empty(values.shape[:2],float)
    for j in range(values.shape[1]):
        x=np.log(doses[j]); out[:,j]=np.sum(np.diff(x)*(values[:,j,:-1]+values[:,j,1:])/2,axis=1)/(x[-1]-x[0])
    return out
def context(x,y,patients):
    w=patient_weights(patients)
    mx=np.sum(w[:,None]*x,axis=0); my=float(np.sum(w*y))
    xc=x-mx; scale=np.sqrt(np.sum(w[:,None]*xc*xc,axis=0))
    scale=np.maximum(scale,SCALE_FLOOR); z=xc/scale; yc=y-my
    cxx=(z*w[:,None]).T@z
    cxy=(z*w[:,None]).T@yc
    cyy=float(np.sum(w*yc*yc))
    return {"mean_x":mx,"scale_x":scale,"mean_y":my,"cxx":cxx,"cxy":cxy,"cyy":cyy}

def proxy_for(values,target,patients,subset):
    c=context(values[:,subset],target,patients)
    b=np.linalg.solve(c["cxx"]+ALPHA*np.eye(len(subset)),c["cxy"])
    return float(c["cyy"]-c["cxy"]@b)

def candidate_plan(values,targets,patients):
    choices=[]
    for j in range(len(DRUGS)):
        best={}
        for size in (2,3):
            opts=[]
            for subset in combinations(range(9),size):
                r=proxy_for(values[:,j,:],targets[:,j],patients,subset)
                opts.append((r,tuple(subset)))
            best[size]=min(opts)
        choices.append({"drug":DRUGS[j],"best2":list(best[2][1]),"best3":list(best[3][1]),
                        "proxy2":best[2][0],"proxy3":best[3][0],"gain":best[2][0]-best[3][0]})
    upgraded={i for i,_ in sorted(enumerate(choices),key=lambda q:(-q[1]["gain"],q[1]["drug"]))[:UPGRADES]}
    plan=[c["best3" if j in upgraded else "best2"] for j,c in enumerate(choices)]
    if sum(map(len,plan))!=BUDGET or [len(x) for x in plan].count(3)!=UPGRADES:
        raise AssertionError("Budget construction failed")
    return {"subsets":plan,"choices":choices,"upgraded_drugs":[DRUGS[j] for j in sorted(upgraded)]}
def fit_model(values,targets,patients,plan,lam):
    heads=[]
    for j,subset in enumerate(plan["subsets"]):
        x=values[:,j,subset]; c=context(x,targets[:,j],patients)
        beta=np.linalg.solve(c["cxx"]+lam*np.eye(len(subset)),c["cxy"])
        heads.append({"subset":list(subset),"mean_x":c["mean_x"],"scale_x":c["scale_x"],
                      "mean_y":c["mean_y"],"beta":beta})
    return heads

def predict(values,heads):
    out=np.empty((len(values),len(DRUGS)))
    for j,h in enumerate(heads):
        x=values[:,j,h["subset"]]
        out[:,j]=h["mean_y"]+((x-h["mean_x"])/h["scale_x"])@h["beta"]
    if not np.isfinite(out).all(): raise ValueError("Nonfinite prediction")
    return out

def interp_weights(full_doses,subset):
    full=np.log(np.asarray(full_doses,float)); sel=full[np.asarray(subset)]
    weights=np.zeros(len(subset))
    for k in range(len(subset)):
        basis=np.zeros(len(subset)); basis[k]=1
        vals=np.interp(full,sel,basis)
        weights[k]=np.sum(np.diff(full)*(vals[:-1]+vals[1:])/2)/(full[-1]-full[0])
    if np.any(weights< -1e-14) or not np.isclose(weights.sum(),1,atol=1e-12):
        raise AssertionError("Invalid interpolation weights")
    return weights

def interp_plan(values,targets,patients,doses):
    w=patient_weights(patients); choices=[]
    for j in range(len(DRUGS)):
        best={}
        for size in (2,3):
            opts=[]
            for subset in combinations(range(9),size):
                iw=interp_weights(doses[j],subset); pred=values[:,j,subset]@iw
                risk=float(np.sum(w*(pred-targets[:,j])**2)); opts.append((risk,tuple(subset),iw))
            best[size]=min(opts,key=lambda x:(x[0],x[1]))
        choices.append({"drug":DRUGS[j],"best2":list(best[2][1]),"best3":list(best[3][1]),
                        "risk2":best[2][0],"risk3":best[3][0],"gain":best[2][0]-best[3][0]})
    upgraded={i for i,_ in sorted(enumerate(choices),key=lambda q:(-q[1]["gain"],q[1]["drug"]))[:UPGRADES]}
    subsets=[c["best3" if j in upgraded else "best2"] for j,c in enumerate(choices)]
    return {"subsets":subsets,"choices":choices,"upgraded_drugs":[DRUGS[j] for j in sorted(upgraded)]}
def interp_predict(values,plan,doses):
    out=np.empty((len(values),len(DRUGS)))
    for j,subset in enumerate(plan["subsets"]):
        out[:,j]=values[:,j,subset]@interp_weights(doses[j],subset)
    return out

def weighted_mse(target,pred,patients):
    w=patient_weights(patients)
    return float(np.sum(w*np.mean((pred-target)**2,axis=1)))

def cv_select_lambda(values,targets,patients):
    groups=np.asarray(patients)
    splitter=GroupKFold(5)
    oof={lam:np.full_like(targets,np.nan) for lam in LAMBDAS}
    fold_records=[]
    for fold,(tr,va) in enumerate(splitter.split(np.zeros(len(groups)),groups=groups)):
        if set(groups[tr])&set(groups[va]): raise AssertionError("Patient leakage")
        plan=candidate_plan(values[tr],targets[tr],groups[tr])
        for lam in LAMBDAS:
            model=fit_model(values[tr],targets[tr],groups[tr],plan,lam)
            oof[lam][va]=predict(values[va],model)
        fold_records.append({"fold":fold,"train_patients":len(set(groups[tr])),
                             "valid_patients":len(set(groups[va])),"plan":plan})
    scores={lam:weighted_mse(targets,p,groups) for lam,p in oof.items()}
    if any(not np.isfinite(p).all() for p in oof.values()):
        raise AssertionError("OOF incomplete")
    chosen=min(LAMBDAS,key=lambda lam:(scores[lam],LAMBDAS.index(lam)))
    return chosen,scores,fold_records

def patient_losses(target,pred):
    return np.mean((pred-target)**2,axis=1)

def describe(target,pred):
    err=(pred-target)**2
    return {"mse":float(err.mean()),"rmse":float(np.sqrt(err.mean())),
            "per_drug_mse":dict(zip(DRUGS,map(float,err.mean(axis=0)))),
            "patient_rmse_p90":float(np.quantile(np.sqrt(err.mean(axis=1)),.9))}
def main():
    q=argparse.ArgumentParser()
    q.add_argument("--community",type=Path,required=True)
    q.add_argument("--forecast",type=Path,required=True)
    q.add_argument("--processed",type=Path,required=True)
    q.add_argument("--protocol",type=Path,required=True)
    q.add_argument("--output",type=Path,required=True)
    a=q.parse_args(); out=a.output.resolve()
    if out.exists(): raise SystemExit("Refusing existing output")
    out.mkdir(parents=True); started=time.monotonic()
    source={"community_sha256":sha(a.community),"forecast_sha256":sha(a.forecast),
            "processed_sha256":sha(a.processed),"protocol_sha256":sha(a.protocol)}
    dump(out/"ATTEMPT_STARTED.json",{"source":source,"automatic_retry":False,
         "external_metrics_already_calculated":False,"unix":time.time()})
    train_ids,train_patients,train_x,train_doses=load_raw(a.community)
    test_ids,test_patients,test_x,test_doses=load_raw(a.forecast)
    if not compatible_dose_grids(train_doses,test_doses):
        raise ValueError("Community/FORECAST dose grids differ beyond source rounding")
    if set(train_patients)&set(test_patients):
        raise ValueError("Cohorts share patient identity")
    if len(set(train_patients))!=82 or len(set(test_patients))!=19:
        raise ValueError("Unexpected cohort patient counts")
    train_y=auc_targets(train_x,train_doses)
    test_y=auc_targets(test_x,test_doses)
    dump(out/"COHORT_AUDIT.json",{"training_lines":len(train_ids),"training_patients":len(set(train_patients)),
         "external_lines":len(test_ids),"external_patients":len(set(test_patients)),
         "drugs":list(DRUGS),"doses_per_drug":9,"complete_numeric_cells":True,
         "dose_grids_compatible_after_source_rounding":True,
         "max_relative_dose_label_difference":float(np.max(np.abs(train_doses-test_doses)/train_doses)),
         "external_used_for_selection":False})
    chosen_lambda,cv_scores,cv_folds=cv_select_lambda(train_x,train_y,train_patients)
    cplan=candidate_plan(train_x,train_y,train_patients)
    cmodel=fit_model(train_x,train_y,train_patients,cplan,chosen_lambda)
    iplan=interp_plan(train_x,train_y,train_patients,train_doses)
    candidate_pred=predict(test_x,cmodel)
    interp_pred=interp_predict(test_x,iplan,test_doses)
    dump(out/"FROZEN_MODEL.json",{"candidate_plan":cplan,"interpolation_plan":iplan,
         "ridge_lambda":chosen_lambda,"ridge_cv_scores":cv_scores,
         "cv_folds":cv_folds,"training_only":True})
    np.savez_compressed(out/"EXTERNAL_PREDICTIONS_COMMITTED.npz",
         sample_ids=test_ids,patient_ids=test_patients,target=test_y,
         candidate=candidate_pred,interpolation=interp_pred)
    commit={"sha256":sha(out/"EXTERNAL_PREDICTIONS_COMMITTED.npz"),
            "selection_complete":True,"external_aggregate_score_calculated":False,
            "external_values_used_for_model_selection":False}
    dump(out/"PREDICTIONS_COMMITTED.json",commit)
    # Aggregate external outcomes are computed only after the above commitment exists.
    cand=describe(test_y,candidate_pred); base=describe(test_y,interp_pred)
    cl=patient_losses(test_y,candidate_pred); bl=patient_losses(test_y,interp_pred)
    delta=cl-bl
    rng=np.random.default_rng(20260930)
    boot=delta[rng.integers(0,len(delta),size=(10000,len(delta)))].mean(axis=1)
    drug_wins=sum(cand["per_drug_mse"][d] < base["per_drug_mse"][d] for d in DRUGS)
    external={"candidate":cand,"optimized_interpolation":base,
        "relative_mse_reduction":1-cand["mse"]/base["mse"],
        "patient_wins":int((delta<0).sum()),"patient_losses":int((delta>0).sum()),
        "patient_ties":int((delta==0).sum()),"drug_mse_wins":int(drug_wins),
        "delta_mse_ci95":np.quantile(boot,[.025,.975]).tolist()}
    processed=pd.read_excel(a.processed,engine="openpyxl")
    processed["PDTO ID"]=processed["PDTO ID"].astype(str)
    pmap=processed.set_index("PDTO ID")
    cols={"5FU":"AUC_5FU","SN38":"AUC_SN38","Regorafenib":"AUC_Regorafenib",
          "Erlotinib":"AUC_Erlotinib","TAS-102":"AUC_TAS102","Gemcitabine":"AUC_Gemcitabine"}
    published=np.empty_like(test_y)
    for i,s in enumerate(test_ids):
        if s not in pmap.index: raise ValueError("Processed table missing external ID "+s)
        for j,d in enumerate(DRUGS): published[i,j]=float(pmap.loc[s,cols[d]])
    target_audit={"mean_abs_difference":float(np.mean(np.abs(test_y-published))),
                  "max_abs_difference":float(np.max(np.abs(test_y-published))),
                  "pearson":float(np.corrcoef(test_y.ravel(),published.ravel())[0,1])}
    result={"status":"COMPLETE","source":source,"task":{"drugs":list(DRUGS),
        "training_lines":84,"training_patients":82,"external_lines":19,"external_patients":19,
        "full_measurements":54,"sparse_measurements":16,"measurement_fraction":16/54},
        "selection":{"lambda":chosen_lambda,"cv_scores":cv_scores,
                     "candidate_upgrades":cplan["upgraded_drugs"],
                     "interpolation_upgrades":iplan["upgraded_drugs"]},
        "external":external,"target_audit_vs_published_processed_auc":target_audit,
        "predictions_sha256":commit["sha256"],"new_independent_validation":False,
        "external_cohort_replication":True,"pre_protocol_raw_external_rows_seen":True,
        "exact_submitted_r13_weights_tested":False,"protected_lib2_used":False,
        "patient_data_published":False,"official_score":None,"seconds":time.monotonic()-started}
    dump(out/"RESULT.json",result)
    print(json.dumps(result,indent=2),flush=True)

if __name__=="__main__":
    main()