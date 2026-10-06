#!/usr/bin/env python3
from __future__ import annotations
import os
for n in ("OPENBLAS_NUM_THREADS","OMP_NUM_THREADS","MKL_NUM_THREADS"): os.environ[n]="1"
import argparse,hashlib,importlib.util,json
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent
STUDY=HERE.parent
REPO=STUDY.parent
UP_PATH=STUDY/"standard_control_meanquad_plate_interaction_v2"/"run_study.py"
_spec=importlib.util.spec_from_file_location("upstream_control_v2",UP_PATH)
up=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(up)
PRIOR=0.125
LOCAL_STRENGTH=2.0*PRIOR
K=3
TARGETS=24
EXPECTED_BW07=0.0010582750420801538
EXPECTED_R13=0.0011448586813828537
EXPECTED_BEST=0.0010444482807046083

def sha(p):
    with Path(p).open("rb") as f:return hashlib.file_digest(f,"sha256").hexdigest()
def write_new(p,v):
    with Path(p).open("x",encoding="utf-8") as f:json.dump(v,f,indent=2,allow_nan=False);f.write("\n")
def fit_rank1_control(F,R,pp):
    F=np.asarray(F,float);R=np.asarray(R,float);w=up.patient_weights(pp)
    if F.ndim!=2 or F.shape[1]!=3 or R.shape!=(len(F),TARGETS):raise ValueError("rank1 control shape")
    mu=np.sum(w[:,None]*F,axis=0);Z=F-mu
    gram=Z.T@(w[:,None]*Z);scale=float(np.trace(gram)/F.shape[1]);lam=PRIOR*scale
    rhs=Z.T@(w[:,None]*R)
    beta=np.linalg.solve(gram+lam*np.eye(F.shape[1]),rhs) if lam>0 else np.linalg.pinv(gram,rcond=1e-12)@rhs
    u,sv,vt=np.linalg.svd(beta,full_matrices=False);beta1=(u[:,:1]*sv[:1])@vt[:1]
    return {"feature_mean":mu.tolist(),"beta":beta1.tolist(),"ridge_lambda":float(lam),
      "feature_energy_scale":scale,"raw_singular_values":sv.tolist(),"rank":1}
def predict_rank1_control(F,m):
    return (np.asarray(F,float)-np.asarray(m["feature_mean"],float))@np.asarray(m["beta"],float)

def verify_freeze(reference_dir,curves,control_features,best_predictions):
    fr=json.loads((HERE/"FREEZE.json").read_text(encoding="utf-8"))
    if fr.get("state")!="FROZEN_AFTER_DIAGNOSTIC_BEFORE_CANONICAL_REPLAY":raise ValueError("freeze state")
    paths={"reference_predictions":reference_dir/"predictions_private.npz","reference_result":reference_dir/"RESULT.json",
      "curves":curves,"catalog":STUDY/"TRAIN_CATALOG.json","control_features":control_features,"best_predictions":best_predictions}
    for f in range(5):
        paths[f"reference_inner_{f}"]=reference_dir/f"outer_{f:02d}"/"inner_predictions_private.npz"
        paths[f"reference_plan_{f}"]=reference_dir/f"outer_{f:02d}"/"plan.json"
    for k,p in paths.items():
        if sha(p)!=fr["input_sha256"][k]:raise ValueError("input changed "+k)
    for rel,h in fr["source_sha256"].items():
        if sha(REPO/rel)!=h:raise ValueError("source changed "+rel)
    for rel,h in fr["dependency_sha256"].items():
        if sha(REPO/rel)!=h:raise ValueError("dependency changed "+rel)

def construct(reference_dir,curves,control_features,best_predictions):
    data,feat,_=up.load_prepared(curves,STUDY/"TRAIN_CATALOG.json")
    x=feat["x_replicates"];y=data["y"];p=data["patient_ids"].astype(str);catalog=up.catalog_from_features(feat)
    control_X=up.load_control_features(control_features,data["sample_ids"])
    rz=np.load(reference_dir/"predictions_private.npz",allow_pickle=False);bz=np.load(best_predictions,allow_pickle=False)
    if not np.array_equal(rz["y"],y) or not np.array_equal(rz["patients"].astype(str),p):raise ValueError("reference identity")
    if not np.array_equal(bz["y"],y) or not np.array_equal(bz["patients"].astype(str),p):raise ValueError("best identity")
    folds=rz["folds"];bw=rz["bandwidth07"];r13=rz["r13"];best=bz["candidate"]
    if not np.array_equal(bz["folds"],folds):raise ValueError("best folds")
    if abs(up.metrics(bw,y,p,folds)["mse"]-EXPECTED_BW07)>1e-15 or abs(up.metrics(r13,y,p,folds)["mse"]-EXPECTED_R13)>1e-15:raise ValueError("control")
    if abs(up.metrics(best,y,p,folds)["mse"]-EXPECTED_BEST)>1e-15:raise ValueError("best control")
    rr=json.loads((reference_dir/"RESULT.json").read_text(encoding="utf-8"));cand=best.copy();records=[]
    for f in range(5):
        tr=np.flatnonzero(folds!=f);te=np.flatnonzero(folds==f)
        iz=np.load(reference_dir/f"outer_{f:02d}"/"inner_predictions_private.npz",allow_pickle=False)
        inner=iz["folds"];iyy=iz["y"];ipp=iz["patients"].astype(str)
        if not np.array_equal(iyy,y[tr]) or not np.array_equal(ipp,p[tr]):raise ValueError("inner identity")
        sel=rr["selections"][f]["selected"]["bandwidth07"];idx=up.option_index(sel);ipred=iz["bandwidth07"][idx]
        R=iyy-ipred[0];common_residual=R.mean(1)
        F=np.full((len(tr),4),np.nan);FM=np.full((len(tr),2),np.nan);L=np.full((len(tr),TARGETS,5),np.nan);contrast=np.full(len(tr),np.nan);cards=[];hashes=[]
        for k in range(K):
            sub=tr[inner!=k];vl=np.flatnonzero(inner==k);val=tr[vl]
            plan=up.plan_panel_fast(x[sub],y[sub],p[sub],catalog);P=up.acquire(x[val],plan,"A")
            F[vl]=up.global_features(P);FM[vl]=up.contrast_features(P);Lb,card=up.local_features(P,plan);L[vl]=Lb;cards.append(card.astype(int).tolist())
            m2=card==2;m3=card==3;contrast[vl]=R[vl][:,m2].mean(1)-R[vl][:,m3].mean(1)
            hashes.append(hashlib.sha256(json.dumps(plan,sort_keys=True,separators=(",",":")).encode()).hexdigest())
        E=np.empty_like(R)
        for k in range(K):
            fi=np.flatnonzero(inner!=k);vl=np.flatnonzero(inner==k)
            ma=up.fit_scalar(F[fi],common_residual[fi],ipp[fi]);md=up.fit_scalar(FM[fi],contrast[fi],ipp[fi])
            E[vl]=R[vl]-up.pooled_correction(up.predict_scalar(F[vl],ma),up.predict_scalar(FM[vl],md),np.asarray(cards[k],int))
        E2=np.empty_like(R)
        for k in range(K):
            fi=np.flatnonzero(inner!=k);vl=np.flatnonzero(inner==k);mask3=L[fi,:,4]>0.5
            lc=up.fit_local(L[fi],E[fi],ipp[fi]);l2=up.fit_local_mask(L[fi,:,:4],E[fi],ipp[fi],~mask3);l3=up.fit_local_mask(L[fi,:,:4],E[fi],ipp[fi],mask3)
            card=np.asarray(cards[k],int);m2=card==2;m3=card==3;Dc=up.predict_local(L[vl],lc);Ds=np.empty((len(vl),TARGETS))
            Ds[:,m2]=up.predict_local(L[vl][:,m2,:4],l2);Ds[:,m3]=up.predict_local(L[vl][:,m3,:4],l3)
            E2[vl]=E[vl]-LOCAL_STRENGTH*((2.0/3.0)*Ds+(1.0/3.0)*Dc)
        target=E2.mean(1);control_train=up.control_basis(control_X[tr]);post=np.empty_like(E2)
        for k in range(K):
            fi=np.flatnonzero(inner!=k);vl=np.flatnonzero(inner==k)
            cm=up.fit_control_ridge(control_train[fi],target[fi],ipp[fi]);post[vl]=E2[vl]-up.predict_control(control_train[vl],cm)[:,None]
        control_model=up.fit_control_ridge(control_train,target,ipp);rank1_model=fit_rank1_control(control_train,post,ipp)
        model_all=up.fit_scalar(F,common_residual,ipp);model_d=up.fit_scalar(FM,contrast,ipp)
        local_common=up.fit_local(L,E,ipp);mask3=L[:,:,4]>0.5
        local_two=up.fit_local_mask(L[:,:,:4],E,ipp,~mask3);local_three=up.fit_local_mask(L[:,:,:4],E,ipp,mask3)
        plan=json.loads((reference_dir/f"outer_{f:02d}"/"plan.json").read_text(encoding="utf-8"));Pt=up.acquire(x[te],plan,"A")
        Ft=up.global_features(Pt);FMt=up.contrast_features(Pt);Lt,card=up.local_features(Pt,plan)
        C=up.pooled_correction(up.predict_scalar(Ft,model_all),up.predict_scalar(FMt,model_d),card)
        Dc=up.predict_local(Lt,local_common);m2=card==2;m3=card==3;Ds=np.empty((len(te),TARGETS))
        Ds[:,m2]=up.predict_local(Lt[:,m2,:4],local_two);Ds[:,m3]=up.predict_local(Lt[:,m3,:4],local_three)
        D=(2.0/3.0)*Ds+(1.0/3.0)*Dc
        control_correction=up.predict_control(up.control_basis(control_X[te]),control_model)
        rank1_raw=predict_rank1_control(up.control_basis(control_X[te]),rank1_model);rank1_inner_strength=1.0/K
        auxiliary=C+LOCAL_STRENGTH*D+control_correction[:,None]+rank1_inner_strength*rank1_raw
        deploy_strength=1.0/K
        cand[0,te]=best[0,te]+deploy_strength*auxiliary
        records.append({"fold":f,"spectral_option":sel,"inner_plan_hashes":hashes,"inner_cardinality":cards,"outer_cardinality":card.astype(int).tolist(),
          "global_calibration":model_all,"contrast_calibration":model_d,"local_common_calibration":local_common,
          "local_two_dose_calibration":local_two,"local_three_dose_calibration":local_three,
          "control_calibration":control_model,"rank1_control_model":rank1_model,
          "local_strength":LOCAL_STRENGTH,"rank1_inner_strength":rank1_inner_strength,"auxiliary_deploy_strength":deploy_strength,
          "test_global_sd":float(np.std(C)),"test_local_scaled_sd":float(np.std(LOCAL_STRENGTH*D)),
          "test_control_sd":float(np.std(control_correction)),"test_rank1_inner_sd":float(np.std(rank1_inner_strength*rank1_raw)),
          "test_auxiliary_sd":float(np.std(auxiliary))})
    return cand,{"y":y,"patients":p,"folds":folds,"bandwidth07":bw,"r13":r13,"best":best,"sample_ids":data["sample_ids"],"drug_ids":data["drug_ids"]},records

def execute(reference_dir,curves,control_features,best_predictions,output):
    verify_freeze(reference_dir,curves,control_features,best_predictions)
    if output.exists():raise ValueError("Output exists")
    cand,ctx,records=construct(reference_dir,curves,control_features,best_predictions)
    output.mkdir(parents=True,exist_ok=False)
    np.savez_compressed(output/"predictions_private.npz",candidate=cand,**ctx)
    y,p,folds=ctx["y"],ctx["patients"].astype(str),ctx["folds"];bw,r13,best=ctx["bandwidth07"],ctx["r13"],ctx["best"]
    ci,cm,bm=up.compare(cand,bw,y,p,folds);cb,_,bestm=up.compare(cand,best,y,p,folds);c13,_,r13m=up.compare(cand,r13,y,p,folds)
    gate={"mse":ci["candidate_mse"]<ci["reference_mse"],"patients":ci["patient_wins"]>=30,"folds":ci["fold_wins"]==5,"p90":ci["p90_nonworse"],"beats_verified_best":cm["mse"]<bestm["mse"]}
    decision="NEW_BEST_PENDING_R18" if all(gate.values()) and c13["relative_gain"]>=.05 and c13["patient_wins"]>=40 and c13["fold_wins"]>=4 and c13["p90_nonworse"] else "REJECT"
    result={"schema":"dosepilot.orientation_A_auxiliary_rank1_calibration.result.v1","status":"COMPLETE","role":"REPEATED_ADAPTIVE_DEVELOPMENT_NOT_INDEPENDENT_VALIDATION",
      "candidate":cm,"bandwidth07":bm,"verified_best":bestm,"r13":r13m,"candidate_vs_bandwidth07":dict(ci,gate=gate),
      "candidate_vs_verified_best":cb,"candidate_vs_r13":c13,"fold_records":records,"decision":decision,
      "prediction_sha256":sha(output/"predictions_private.npz"),"protected22_access":False,"independent_validation":False,
      "official_competition_score":None,"automatic_retry":False}
    write_new(output/"RESULT.json",result)
    print(json.dumps({"decision":decision,"candidate_mse":cm["mse"],"best_mse":bestm["mse"],"vs_bw07":ci,"vs_best":cb,
      "orientation_mse":cm["orientation_mse"],"fold_auxiliary_sd":[r["test_auxiliary_sd"] for r in records]},indent=2))
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--reference-dir",type=Path,required=True);ap.add_argument("--curves",type=Path,required=True)
    ap.add_argument("--control-features",type=Path,required=True);ap.add_argument("--best-predictions",type=Path,required=True);ap.add_argument("--output",type=Path,required=True);a=ap.parse_args()
    execute(a.reference_dir,a.curves,a.control_features,a.best_predictions,a.output)
if __name__=="__main__":main()
