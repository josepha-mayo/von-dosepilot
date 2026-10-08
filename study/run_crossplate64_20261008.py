#!/usr/bin/env python3
"""Prespecified cross-plate matched dose 64-well study, independent worktree.
This study intentionally relaxes the old 64 DISTINCT-dose requirement but
preserves 64 physical treatment wells, 32 per plate, 24 targets and A/B choices.
"""
from __future__ import annotations
import os
for key in ("OPENBLAS_NUM_THREADS","OMP_NUM_THREADS","MKL_NUM_THREADS"):
    os.environ[key]="1"
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import numpy as np

HERE=Path(__file__).resolve().parent
STUDY=HERE
sys.path[:0]=[str(STUDY),str(STUDY/"engine"),str(STUDY/"acceleration"),
             str(STUDY/"hybrid_residual")]
from compact_train import load_prepared
from methods import patient_folds,patient_weights
import evaluate
from fast_coverage import plan_panel_fast
from sparse_methods import fit_sparse_context
from bandwidth_additive import BandwidthAdditive

DATA=Path("/mnt/d/von-dosepilot-data")
CURVES=DATA/"reconstructed_train"/"train_curves.csv"
CATALOG=STUDY/"TRAIN_CATALOG.json"
BW=DATA/"bandwidth_replay_pc_20261004"/"predictions_private.npz"
BEST=DATA/"orientation_specific_control_quality_rank1_20261006_run1"/"predictions_private.npz"
ARMS=(0,4,8)
OPTIONS=[("identity",0.0)]+[(fraction,ridge) for fraction in (.1,.3,.6) for ridge in (.1,1.0,10.0)]
TARGETS=24
EXPECTED_BW=0.0010582750420801538
EXPECTED_BEST=0.001042745722096212
TWOX=EXPECTED_BEST/2

def digest(p):
    with Path(p).open("rb") as stream:
        return hashlib.file_digest(stream,"sha256").hexdigest()

def metric(pred,y,patients,folds):
    p=np.asarray(patients).astype(str)
    e=np.mean((pred-y[None])**2,axis=0)
    unique=np.unique(p)
    by_patient=np.asarray([e[p==g].mean(axis=(0,1)) for g in unique])
    per_t=np.asarray([e[p==g].mean(axis=0) for g in unique])
    pf=np.asarray([int(folds[np.flatnonzero(p==g)[0]]) for g in unique])
    fold=[float(by_patient[pf==f].mean()) for f in range(int(np.max(folds))+1)]
    return {"mse":float(by_patient.mean()),
            "p90":float(np.quantile(np.sqrt(by_patient),.9)),
            "fold_mse":fold,
            "orientation_mse":[float(np.mean([((pred[o,p==g]-y[p==g])**2).mean() for g in unique])) for o in (0,1)],
            "target_mse":per_t.mean(axis=0).tolist()},by_patient

def compare(a,b):
    am,ap=a
    bm,bp=b
    return {"relative_gain":float(1-am["mse"]/bm["mse"]),
            "patient_wins":int(np.count_nonzero(ap<bp-1e-15)),
            "patient_losses":int(np.count_nonzero(ap>bp+1e-15)),
            "fold_wins":int(sum(v<w-1e-15 for v,w in zip(am["fold_mse"],bm["fold_mse"]))),
            "p90_nonworse":bool(am["p90"]<=bm["p90"]+1e-15),
            "targets_better":int(sum(x<y for x,y in zip(am["target_mse"],bm["target_mse"])))}

def plan_validation(plan,cat,k):
    n=np.asarray(plan["selected_native_indices"],int)
    own=np.asarray(plan["coordinate_target_indices"],int)
    a=np.asarray(plan["orientation_A_plate_indices"],int)
    b=np.asarray(plan["orientation_B_plate_indices"],int)
    if n.shape!=(64,) or len(set(n))!=64-k or np.any(n<0) or np.any(n>=len(cat.native_ids)):
        raise AssertionError("distinct-dose budget")
    if not np.array_equal(own,cat.native_target_indices[n]) or not np.array_equal(b,1-a):
        raise AssertionError("native ownership or alternate layout")
    if np.count_nonzero(a==0)!=32 or np.count_nonzero(b==0)!=32:
        raise AssertionError("32/32 plate accounting")
    if sorted(np.bincount(own,minlength=24).tolist())!=[2]*8+[3]*16:
        raise AssertionError("required two/three physical wells per target")
    if len(set(zip(n,a)))!=64 or len(set(zip(n,b)))!=64:
        raise AssertionError("duplicate physical well")
    actual=sum(len(set(n[own==j]))==2 for j in range(24))
    if actual!=8+k:
        raise AssertionError("unexpected number of doubly sampled targets")
    return True

def risk(values,target,pp,lam=.1):
    """Patient-balanced in-sample regularized covariance proxy, planning ONLY."""
    z=np.asarray(values,float)
    t=np.asarray(target,float)
    w=patient_weights(np.asarray(pp,str))
    w=w/w.sum()
    mx=w@z
    sx=np.maximum(np.sqrt(w@(z-mx)**2),.05)
    mm=float(w@t)
    yy=t-mm
    zz=(z-mx)/sx
    cxx=(zz.T*w)@zz
    cxy=(zz.T*w)@yy
    return float(w@(yy*yy)-cxy@np.linalg.solve(cxx+lam*np.eye(z.shape[1]),cxy))

def duplicate_plan(full,xx,yy,pp,cat,k):
    from copy import deepcopy
    plan=deepcopy(full)
    q=np.asarray(plan["selected_native_indices"],int)
    own=np.asarray(plan["coordinate_target_indices"],int)
    pa=np.asarray(plan["orientation_A_plate_indices"],int)
    if k:
        ranking=[]
        for t in range(24):
            slots=np.flatnonzero(own==t)
            if len(slots)!=3:
                continue
            # Exactly one slot on the minority plate, two on the majority plate.
            majority=int(pa[slots[0]])
            maj=slots[pa[slots]==majority]
            minor=slots[pa[slots]!=majority]
            if len(maj)!=2 or len(minor)!=1:
                raise AssertionError("unexpected three-well plate pattern")
            z0=xx[:,q[slots],pa[slots]]
            z1=xx[:,q[slots],1-pa[slots]]
            p2=np.tile(pp,2); y2=np.tile(yy[:,t],2)
            original=risk(np.r_[z0,z1],y2,p2)
            options=[]
            for drop in maj:
                repl=q.copy();repl[drop]=q[minor[0]]
                zz0=xx[:,repl[slots],pa[slots]]
                zz1=xx[:,repl[slots],1-pa[slots]]
                score=risk(np.r_[zz0,zz1],y2,p2)
                options.append((score,int(drop),int(q[minor[0]])))
            sc,drop,repl=min(options)
            ranking.append((sc-original,t,drop,repl,original,sc))
        if len(ranking)!=16:
            raise AssertionError("must see 16 three-well targets")
        ranking.sort(key=lambda row:(row[0],str(cat.target_ids[row[1]]),row[2]))
        chosen=ranking[:k]
        for _,t,drop,repl,_,_ in chosen:
            q[drop]=repl
        plan["duplicate_replacements"]=[{"target":str(cat.target_ids[t]),
            "position":drop,"new_native":repl,"proxy_loss_change":float(sc-original)}
            for sc,t,drop,repl,original,_ in chosen]
    else:
        plan["duplicate_replacements"]=[]
    plan["selected_native_indices"]=q.tolist()
    plan["selected_native_ids"]=[str(cat.native_ids[j]) for j in q]
    plan["selected_concentrations_nM"]=[str(cat.concentrations[j]) for j in q]
    plan["distinct_native_doses"]=64-k
    plan["paired_native_doses"]=k
    plan_validation(plan,cat,k)
    return plan

def paid(x,plan,orientation):
    select=np.asarray(plan["selected_native_indices"],int)
    plates=np.asarray(plan[f"orientation_{orientation}_plate_indices"],int)
    p=np.asarray(x,float)[:,select,plates]
    if p.shape!=(len(x),64) or not np.isfinite(p).all():
        raise AssertionError("invalid purchased feature payload")
    return p

class Ridge:
    def __init__(self,ctx,plan,lam=.01):
        self.mean_x=ctx.mean_x.copy()
        self.scale_x=ctx.scale_x.copy()
        self.mean_y=ctx.mean_y.copy()
        own=np.asarray(plan["coordinate_target_indices"],int)
        self.beta=np.zeros((64,24))
        for t in range(24):
            cols=np.flatnonzero(own==t)
            mat=ctx.cxx[np.ix_(cols,cols)]+lam*np.eye(len(cols))
            self.beta[cols,t]=np.linalg.solve(mat,ctx.cxy[cols,t])
    def predict(self,z):
        return self.mean_y+((z-self.mean_x)/self.scale_x)@self.beta

def construct_models(xx,yy,pp,cat,full):
    results={}
    for k in ARMS:
        plan=duplicate_plan(full,xx,yy,pp,cat,k)
        a,b=paid(xx,plan,"A"),paid(xx,plan,"B")
        xx2=np.r_[a,b]; yy2=np.r_[yy,yy]; pp2=np.r_[pp,pp]
        ctx=fit_sparse_context(xx2,yy2,pp2,plan["selected_native_ids"],cat.target_ids)
        base=Ridge(ctx,plan,.01)
        z=(xx2-base.mean_x)/base.scale_x
        res=yy2-base.predict(xx2)
        w=np.tile(patient_weights(pp),2)/2
        kernel=BandwidthAdditive(z,res,w,np.asarray(plan["coordinate_target_indices"],int),.7)
        coefs=[np.zeros_like(res)]
        for frac,lam in OPTIONS[1:]:
            coef,_,_=kernel.coefficients(lam,frac)
            coefs.append(coef)
        results[k]=(plan,base,kernel,coefs)
    return results

def predict_options(x,model):
    plan,base,kernel,coefs=model
    arr=np.empty((len(OPTIONS),2,len(x),24))
    for j,o in enumerate(("A","B")):
        values=paid(x,plan,o)
        bz=base.predict(values)
        cross=kernel.centered_cross((values-base.mean_x)/base.scale_x)
        for k,coef in enumerate(coefs):
            arr[k,j]=bz+cross@coef
    if not np.isfinite(arr).all():
        raise AssertionError("nonfinite predictions")
    return arr

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--out",type=Path,required=True)
    args=ap.parse_args()
    if args.out.exists(): raise ValueError("refuse overwrite")
    data,features,_=load_prepared(CURVES,CATALOG)
    x=features["x_replicates"]
    y=data["y"]
    p=data["patient_ids"].astype(str)
    cat=__import__("coverage_methods").catalog_from_features(features)
    if x.shape!=(119,164,2) or y.shape!=(119,24) or len(np.unique(p))!=59:
        raise AssertionError("TRAIN dimensions")
    z0=np.load(BW,allow_pickle=False)
    zb=np.load(BEST,allow_pickle=False)
    folds=np.asarray(z0["folds"],int)
    if not np.array_equal(z0["y"],y) or not np.array_equal(zb["y"],y):
        raise AssertionError("authenticated labels differ")
    if not np.array_equal(z0["patients"].astype(str),p) or not np.array_equal(zb["patients"].astype(str),p) or not np.array_equal(zb["folds"],folds):
        raise AssertionError("patient/fold lineage")
    rec,_=patient_folds(p,5,evaluate.SALT+"|outer")
    if not np.array_equal(rec,folds):
        raise AssertionError("outer patient fold recipe mismatch")
    bw=z0["bandwidth07"]
    best=zb["candidate"]
    mbw=metric(bw,y,p,folds)
    mret=metric(best,y,p,folds)
    if abs(mbw[0]["mse"]-EXPECTED_BW)>1e-13 or abs(mret[0]["mse"]-EXPECTED_BEST)>1e-13:
        raise AssertionError("reference metrics mismatch")
    pred={k:np.full((2,len(y),24),np.nan) for k in ARMS}
    receipts=[]
    for f in range(5):
        tr=np.flatnonzero(folds!=f)
        te=np.flatnonzero(folds==f)
        if set(p[tr]) & set(p[te]):raise AssertionError("outer patient leakage")
        inner,_=patient_folds(p[tr],3,evaluate.SALT+f"|inner|{f}")
        oof={k:np.full((len(OPTIONS),2,len(tr),24),np.nan) for k in ARMS}
        for i in range(3):
            sub=tr[inner!=i];val=tr[inner==i]
            if set(p[sub])&set(p[val]):raise AssertionError("inner patient leakage")
            baseplan=plan_panel_fast(x[sub],y[sub],p[sub],cat)
            models=construct_models(x[sub],y[sub],p[sub],cat,baseplan)
            for k in ARMS:
                oof[k][:,:,inner==i]=predict_options(x[val],models[k])
        choices={}
        for k in ARMS:
            if not np.isfinite(oof[k]).all():raise AssertionError("missing inner OOF")
            scores=[metric(oof[k][i],y[tr],p[tr],inner)[0]["mse"]
                for i in range(len(OPTIONS))]
            idx=int(np.argmin(scores))
            choices[k]={"index":idx,"option":OPTIONS[idx],"inner_mse":scores[idx]}
        baseplan=plan_panel_fast(x[tr],y[tr],p[tr],cat)
        models=construct_models(x[tr],y[tr],p[tr],cat,baseplan)
        recs={}
        for k in ARMS:
            possible=predict_options(x[te],models[k])
            pred[k][:,te]=possible[choices[k]["index"]]
            recs[str(k)]={"selected":choices[k],
                  "native_distinct":64-k,
                  "physical_wells":64,
                  "plate_counts":[32,32],
                  "pairing_plan":models[k][0]["duplicate_replacements"]}
        receipts.append({"outer_fold":f,"training_patients":len(set(p[tr])),
                         "test_patients":len(set(p[te])),
                         "arms":recs})
        print(json.dumps({"fold":f,"selected":{str(k):choices[k]["option"] for k in ARMS}}),flush=True)
    if any(not np.isfinite(pred[k]).all() for k in ARMS):
        raise AssertionError("candidate incomplete")
    results={k:metric(pred[k],y,p,folds) for k in ARMS}
    # Independently check the unmodified arm reproduces the frozen bandwidth0.7 pipeline.
    control=np.max(np.abs(pred[0]-bw))
    if control>1e-9:
        raise AssertionError("unmodified 64-well pipeline does not reproduce incumbent: "+str(control))
    summary={}
    for k in ARMS:
        met,patient=results[k]
        summary[str(k)]={"metrics":met,"versus_operating64":compare(results[k],mbw),
                         "versus_retained64":compare(results[k],mret),
                         "two_x_target_met":bool(met["mse"]<=TWOX),
                         "p90_retained_nonworse":bool(met["p90"]<=mret[0]["p90"]+1e-15)}
        gate=summary[str(k)]["versus_retained64"]
        summary[str(k)]["promotion_eligible"]=bool(k!=0 and gate["relative_gain"]>0
            and gate["patient_wins"]>=30 and gate["fold_wins"]==5 and gate["p90_nonworse"]
            and summary[str(k)]["versus_operating64"]["relative_gain"]>0)
    output={"schema":"dosepilot.crossplate64.result.v1","status":"COMPLETE",
            "evaluation":"REPEATED_ADAPTIVE_TRAIN_DEVELOPMENT_NOT_INDEPENDENT_VALIDATION",
            "constraint":"64 physical treatment wells, 32/32 plates; 60 or 56 distinct native concentrations",
            "control_reproduction_max_abs_error":float(control),
            "reference_operating64":mbw[0],"reference_retained64":mret[0],
            "new_arms":summary,"fold_records":receipts,
            "target_mse_for_two_x":TWOX,
            "verified_2x":any(summary[str(k)]["two_x_target_met"] and summary[str(k)]["p90_retained_nonworse"] for k in (4,8)),
            "no_official_competition_score":True,"automatic_promotion":False,
            "input_sha256":{"curves":digest(CURVES),"catalog":digest(CATALOG),
                "operating64":digest(BW),"retained64":digest(BEST)},
            "source_sha256":digest(Path(__file__)),"protocol_sha256":digest(HERE/"CROSSPLATE64_PROTOCOL_20261008.md"),
            "time_utc":datetime.now(timezone.utc).isoformat()}
    args.out.mkdir(parents=True)
    np.savez_compressed(args.out/"predictions_private.npz",
        k0=pred[0],k4=pred[4],k8=pred[8],y=y,patients=p,folds=folds,
        operating64=bw,retained64=best)
    (args.out/"RESULT.json").write_text(json.dumps(output,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps({str(k):{"mse":summary[str(k)]["metrics"]["mse"],
        "gain":summary[str(k)]["versus_retained64"]["relative_gain"],
        "patient_wins":summary[str(k)]["versus_retained64"]["patient_wins"],
        "fold_wins":summary[str(k)]["versus_retained64"]["fold_wins"],
        "p90":summary[str(k)]["metrics"]["p90"]} for k in ARMS},indent=2),flush=True)
    print("RESULT_JSON="+str(args.out/"RESULT.json"),flush=True)

if __name__=="__main__":
    main()
