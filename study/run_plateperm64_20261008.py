#!/usr/bin/env python3
"""Same 64 native-dose wells, alternate within-target physical plate assignments."""
from __future__ import annotations
import os
for var in ("OPENBLAS_NUM_THREADS","OMP_NUM_THREADS","MKL_NUM_THREADS"):
    os.environ[var]="1"
import hashlib
import json
import sys
from datetime import datetime,timezone
from pathlib import Path
from copy import deepcopy
import numpy as np
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import run_crossplate64_20261008 as core
from sparse_methods import fit_sparse_context
from coverage_methods import catalog_from_features
ARMS=("original","minority_low","minority_high","training_risk")
OPTIONS=core.OPTIONS
DATA=core.DATA
CAT=core.CATALOG
CURVES=core.CURVES
BASE=core.BW
BEST=core.BEST

def plate_plan(full,x,y,patients,catalog,arm):
    if arm not in ARMS:raise ValueError("unknown plate arm")
    p=deepcopy(full)
    selected=np.asarray(full["selected_native_indices"],int)
    own=np.asarray(full["coordinate_target_indices"],int)
    a=np.asarray(full["orientation_A_plate_indices"],int).copy()
    record=[]
    for j in range(24):
        slots=np.flatnonzero(own==j)
        if len(slots)!=3:continue
        old=a[slots].copy()
        maj=int(np.count_nonzero(old==1)>=2)
        if np.count_nonzero(old==maj)!=2:
            raise AssertionError("3-well majority plate count")
        doses=np.array([float(catalog.concentrations[selected[v]]) for v in slots])
        ranked=np.argsort(doses)
        if arm=="original":
            selected_local=int(np.flatnonzero(old!=maj)[0])
        elif arm=="minority_low":
            selected_local=int(ranked[0])
        elif arm=="minority_high":
            selected_local=int(ranked[-1])
        else:
            # Fitting data only. Symmetric A/B alternatives and patient-weighted ridge.
            candidates=[]
            for local in range(3):
                proposed=np.full(3,maj)
                proposed[local]=1-maj
                aa=x[:,selected[slots],proposed]
                bb=x[:,selected[slots],1-proposed]
                risk=core.risk(np.r_[aa,bb],np.tile(y[:,j],2),
                               np.tile(patients,2),.1)
                # Tie-break prefers original placement.
                preference=0 if proposed.tolist()==old.tolist() else 1
                candidates.append((risk,preference,local))
            selected_local=min(candidates)[2]
        assignment=np.full(3,maj)
        assignment[selected_local]=1-maj
        a[slots]=assignment
        record.append({"drug":str(catalog.target_ids[j]),
                       "minority_selected_dose_nM":float(doses[selected_local]),
                       "changed":bool(not np.array_equal(assignment,old))})
    p["orientation_A_plate_indices"]=a.tolist()
    p["orientation_B_plate_indices"]=(1-a).tolist()
    core.plan_validation(p,catalog,0)
    if len(record)!=16:raise AssertionError("3-dose target count")
    return p,record

def model_one(x,y,patients,catalog,full,arm):
    plan,record=plate_plan(full,x,y,patients,catalog,arm)
    a=core.paid(x,plan,"A");b=core.paid(x,plan,"B")
    xx=np.r_[a,b]
    yy=np.r_[y,y]
    pp=np.r_[patients,patients]
    context=fit_sparse_context(xx,yy,pp,plan["selected_native_ids"],catalog.target_ids)
    ridge=core.Ridge(context,plan,.01)
    z=(xx-ridge.mean_x)/ridge.scale_x
    residual=yy-ridge.predict(xx)
    w=np.tile(core.patient_weights(patients),2)/(2*len(np.unique(patients)))
    kernel=core.BandwidthAdditive(z,residual,w,np.asarray(plan["coordinate_target_indices"],int),.7)
    coefs=[np.zeros_like(residual)]
    for frac,lam in OPTIONS[1:]:
        coefs.append(kernel.coefficients(lam,frac)[0])
    return (plan,ridge,kernel,coefs),record

def fit_arm_bundle(x,y,p,cat,full):
    return {arm:model_one(x,y,p,cat,full,arm) for arm in ARMS}

def execute(output):
    if output.exists():raise ValueError("refuse outcome overwrite")
    data,feat,_=core.load_prepared(CURVES,CAT)
    x=feat["x_replicates"]
    y=data["y"]
    patients=data["patient_ids"].astype(str)
    cat=catalog_from_features(feat)
    rz=np.load(BASE,allow_pickle=False)
    bz=np.load(BEST,allow_pickle=False)
    folds=rz["folds"]
    if not np.array_equal(rz["y"],y) or not np.array_equal(bz["y"],y) or not np.array_equal(rz["folds"],bz["folds"]):
        raise AssertionError("source identity changed")
    if not np.array_equal(rz["patients"].astype(str),patients) or not np.array_equal(bz["patients"].astype(str),patients):
        raise AssertionError("patient identity changed")
    recompute,_=core.patient_folds(patients,5,core.evaluate.SALT+"|outer")
    if not np.array_equal(recompute,folds):raise AssertionError("whole patient fold recipe")
    b0=core.metric(rz["bandwidth07"],y,patients,folds)
    best=core.metric(bz["candidate"],y,patients,folds)
    if abs(b0[0]["mse"]-core.EXPECTED_BW)>1e-13 or abs(best[0]["mse"]-core.EXPECTED_BEST)>1e-13:
        raise AssertionError("reference score")
    predictions={arm:np.full((2,len(y),24),np.nan) for arm in ARMS}
    receipts=[]
    for f in range(5):
        tr=np.flatnonzero(folds!=f)
        te=np.flatnonzero(folds==f)
        if set(patients[tr])&set(patients[te]):raise AssertionError("outer leakage")
        inner,_=core.patient_folds(patients[tr],3,core.evaluate.SALT+f"|inner|{f}")
        oof={arm:np.full((len(OPTIONS),2,len(tr),24),np.nan) for arm in ARMS}
        for fold in range(3):
            sub=tr[inner!=fold]; val=tr[inner==fold]
            if set(patients[sub])&set(patients[val]):raise AssertionError("inner leakage")
            plan=core.plan_panel_fast(x[sub],y[sub],patients[sub],cat)
            models=fit_arm_bundle(x[sub],y[sub],patients[sub],cat,plan)
            for arm in ARMS:
                model,_=models[arm]
                oof[arm][:,:,inner==fold]=core.predict_options(x[val],model)
        selections={}
        for arm in ARMS:
            if not np.isfinite(oof[arm]).all():raise AssertionError("missing inner predictions")
            scores=[core.metric(oof[arm][i],y[tr],patients[tr],inner)[0]["mse"] for i in range(len(OPTIONS))]
            ix=int(np.argmin(scores))
            selections[arm]={"index":ix,"option":OPTIONS[ix],"inner_mse":float(scores[ix])}
        outer_plan=core.plan_panel_fast(x[tr],y[tr],patients[tr],cat)
        models=fit_arm_bundle(x[tr],y[tr],patients[tr],cat,outer_plan)
        summary={}
        for arm in ARMS:
            model,record=models[arm]
            guesses=core.predict_options(x[te],model)
            predictions[arm][:,te]=guesses[selections[arm]["index"]]
            summary[arm]={"spectral_selection":selections[arm],
                          "changed_target_count":int(sum(r["changed"] for r in record)),
                          "placement":record}
        receipts.append({"fold":f,"arms":summary})
        print(json.dumps({"fold":f,"selected":{k:selections[k]["option"] for k in ARMS}}),flush=True)
    for arm in ARMS:
        if not np.isfinite(predictions[arm]).all():raise AssertionError("incomplete candidate")
    numeric_control=float(np.max(abs(predictions["original"]-rz["bandwidth07"])))
    if numeric_control>1e-9:raise AssertionError("old 64-dose model mismatch")
    results={}
    for arm in ARMS:
        met=core.metric(predictions[arm],y,patients,folds)
        vs_best=core.compare(met,best)
        vs_original=core.compare(met,b0)
        results[arm]={"metric":met[0],"vs_retained64":vs_best,"vs_operating64":vs_original,
                      "two_x_numeric":bool(met[0]["mse"]<=core.TWOX and met[0]["p90"]<=best[0]["p90"])}
        results[arm]["eligible"]=bool(arm!="original" and vs_best["relative_gain"]>0 and
            vs_original["relative_gain"]>0 and vs_best["patient_wins"]>=30 and
            vs_best["fold_wins"]==5 and vs_best["p90_nonworse"])
    out={"schema":"dosepilot.plateperm64.result.v1","role":"REPEATED_ADAPTIVE_TRAIN_DEVELOPMENT",
         "verified_original_max_abs_difference":numeric_control,
         "original_reference":b0[0],"scientific_reference":best[0],
         "arms":results,"fold_records":receipts,"target_mse_2x":core.TWOX,
         "no_protected22":True,"no_official_score":True,"auto_promotion":False,
         "input_hashes":{"curves":core.digest(CURVES),"catalog":core.digest(CAT),
                         "reference":core.digest(BASE),"best":core.digest(BEST)},
         "source_sha256":core.digest(Path(__file__)),
         "protocol_sha256":core.digest(HERE/"PLATEPERM64_PROTOCOL_20261008.md"),
         "created_utc":datetime.now(timezone.utc).isoformat()}
    output.mkdir(parents=True)
    np.savez_compressed(output/"predictions_private.npz",
        y=y,patients=patients,folds=folds,operating64=rz["bandwidth07"],
        retained64=bz["candidate"],**{a:predictions[a] for a in ARMS})
    (output/"RESULT.json").write_text(json.dumps(out,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps({k:{"mse":v["metric"]["mse"],
         "p90":v["metric"]["p90"],
         "gain_vs_retained64":v["vs_retained64"]["relative_gain"],
         "patients":v["vs_retained64"]["patient_wins"],
         "folds":v["vs_retained64"]["fold_wins"]} for k,v in results.items()},indent=2),flush=True)

if __name__=="__main__":
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    execute(args.output)
