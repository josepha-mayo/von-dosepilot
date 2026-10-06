#!/usr/bin/env python3
from __future__ import annotations
import os
for n in ("OPENBLAS_NUM_THREADS","OMP_NUM_THREADS","MKL_NUM_THREADS"): os.environ[n]="1"
import argparse,hashlib,importlib.util,json
from pathlib import Path
import numpy as np
import pandas as pd

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
EXPECTED_BEST=0.001043179589139139
QUALITY_COLUMNS=[
 "p1_logrange","p2_logrange",
 "p1_neg_logmed","p2_neg_logmed",
 "p1_pos_logmed","p2_pos_logmed",
 "p1_neg_cv","p2_neg_cv",
 "p1_pos_cv","p2_pos_cv",
]

def sha(p):
    with Path(p).open("rb") as f:return hashlib.file_digest(f,"sha256").hexdigest()
def write_new(p,v):
    with Path(p).open("x",encoding="utf-8") as f:json.dump(v,f,indent=2,allow_nan=False);f.write("\n")
def load_quality_features(path,sample_ids):
    df=pd.read_csv(path)
    if "sample_id" not in df.columns or len(df)!=len(set(df["sample_id"].astype(str))):raise ValueError("control quality identity")
    missing=[c for c in QUALITY_COLUMNS if c not in df.columns]
    if missing:raise ValueError("missing control columns "+",".join(missing))
    q=df.set_index(df["sample_id"].astype(str)).drop(columns=["sample_id"])
    ids=np.asarray(sample_ids).astype(str)
    if not set(ids).issubset(set(q.index)):raise ValueError("control quality sample missing")
    out=q.loc[ids,QUALITY_COLUMNS].to_numpy(float)
    if out.shape!=(len(ids),10) or not np.isfinite(out).all():raise ValueError("control quality malformed")
    return out
def pair_md(X):
    X=np.asarray(X,float)
    return np.column_stack((X.mean(axis=1),(X[:,0]-X[:,1])/2.0))
def meanquad_basis(Q):
    r=pair_md(Q[:,0:2]);m=r[:,0];d=r[:,1]
    return np.column_stack((m,d,m*m))
def A_level_basis(Q):
    base=meanquad_basis(Q)
    return np.column_stack((base,pair_md(Q[:,2:4]),pair_md(Q[:,4:6])))
def B_full_quality_basis(Q):
    return np.column_stack((A_level_basis(Q),pair_md(Q[:,6:8]),pair_md(Q[:,8:10])))
def fit_rank1(F,R,patients):
    F=np.asarray(F,float);R=np.asarray(R,float);w=up.patient_weights(patients)
    if F.ndim!=2 or R.shape!=(len(F),TARGETS):raise ValueError("rank1 shape")
    mu=np.sum(w[:,None]*F,axis=0);Z=F-mu
    gram=Z.T@(w[:,None]*Z);scale=float(np.trace(gram)/F.shape[1]);lam=PRIOR*scale
    rhs=Z.T@(w[:,None]*R)
    beta=np.linalg.solve(gram+lam*np.eye(F.shape[1]),rhs) if lam>0 else np.linalg.pinv(gram,rcond=1e-12)@rhs
    u,sv,vt=np.linalg.svd(beta,full_matrices=False);beta1=(u[:,:1]*sv[:1])@vt[:1]
    return {"feature_mean":mu.tolist(),"beta":beta1.tolist(),"ridge_lambda":float(lam),
      "feature_energy_scale":scale,"raw_singular_values":sv.tolist(),"rank":1,"feature_count":int(F.shape[1])}
def predict_rank1(F,m):
    return (np.asarray(F,float)-np.asarray(m["feature_mean"],float))@np.asarray(m["beta"],float)

def verify_freeze(reference_dir,curves,quality_features,best_predictions):
    fr=json.loads((HERE/"FREEZE.json").read_text())
    if fr.get("state")!="FROZEN_AFTER_DIAGNOSTIC_BEFORE_CANONICAL_REPLAY":raise ValueError("freeze state")
    paths={"reference_predictions":reference_dir/"predictions_private.npz","reference_result":reference_dir/"RESULT.json",
      "curves":curves,"catalog":STUDY/"TRAIN_CATALOG.json","quality_features":quality_features,"best_predictions":best_predictions}
    for f in range(5):
        paths[f"reference_inner_{f}"]=reference_dir/f"outer_{f:02d}"/"inner_predictions_private.npz"
        paths[f"reference_plan_{f}"]=reference_dir/f"outer_{f:02d}"/"plan.json"
    for k,p in paths.items():
        if sha(p)!=fr["input_sha256"][k]:raise ValueError("input changed "+k)
    for rel,h in fr["source_sha256"].items():
        if sha(REPO/rel)!=h:raise ValueError("source changed "+rel)
    for rel,h in fr["dependency_sha256"].items():
        if sha(REPO/rel)!=h:raise ValueError("dependency changed "+rel)

def construct(reference_dir,curves,quality_features,best_predictions):
    data,feat,_=up.load_prepared(curves,STUDY/"TRAIN_CATALOG.json")
    x=feat["x_replicates"];y=data["y"];p=data["patient_ids"].astype(str);catalog=up.catalog_from_features(feat)
    Q=load_quality_features(quality_features,data["sample_ids"])
    rz=np.load(reference_dir/"predictions_private.npz",allow_pickle=False);bz=np.load(best_predictions,allow_pickle=False)
    if not np.array_equal(rz["y"],y) or not np.array_equal(rz["patients"].astype(str),p):raise ValueError("reference identity")
    if not np.array_equal(bz["y"],y) or not np.array_equal(bz["patients"].astype(str),p):raise ValueError("best identity")
    folds=rz["folds"];bw=rz["bandwidth07"];r13=rz["r13"];best=bz["candidate"]
    if not np.array_equal(bz["folds"],folds):raise ValueError("best folds")
    if abs(up.metrics(bw,y,p,folds)["mse"]-EXPECTED_BW07)>1e-15 or abs(up.metrics(r13,y,p,folds)["mse"]-EXPECTED_R13)>1e-15:raise ValueError("control")
    if abs(up.metrics(best,y,p,folds)["mse"]-EXPECTED_BEST)>1e-15:raise ValueError("best control")
    rr=json.loads((reference_dir/"RESULT.json").read_text());cand=best.copy();records=[]
    for f in range(5):
        tr=np.flatnonzero(folds!=f);te=np.flatnonzero(folds==f)
        iz=np.load(reference_dir/f"outer_{f:02d}"/"inner_predictions_private.npz",allow_pickle=False)
        inner=iz["folds"];iyy=iz["y"];ipp=iz["patients"].astype(str)
        if not np.array_equal(iyy,y[tr]) or not np.array_equal(ipp,p[tr]):raise ValueError("inner identity")
        sel=rr["selections"][f]["selected"]["bandwidth07"];idx=up.option_index(sel);ipred=iz["bandwidth07"][idx]
        # Build the fitting-only paid features for both orientations under exactly the authenticated inner plans.
        FA=np.full((len(tr),4),np.nan);FMA=np.full((len(tr),2),np.nan);LA=np.full((len(tr),TARGETS,5),np.nan)
        FB=np.full((len(tr),4),np.nan);FMB=np.full((len(tr),2),np.nan);LB=np.full((len(tr),TARGETS,5),np.nan)
        inner_imbalance=np.full((len(tr),TARGETS),np.nan);cards=[];hashes=[]
        for k in range(K):
            sub=tr[inner!=k];vl=np.flatnonzero(inner==k);val=tr[vl]
            plan=up.plan_panel_fast(x[sub],y[sub],p[sub],catalog)
            saved=json.loads((reference_dir/f"outer_{f:02d}"/"plan.json").read_text())
            # saved outer plan is not expected to equal inner-fitting plan; only budget/semantics are shared.
            PA=up.acquire(x[val],plan,"A");PB=up.acquire(x[val],plan,"B")
            FA[vl]=up.global_features(PA);FMA[vl]=up.contrast_features(PA);LAk,card=up.local_features(PA,plan);LA[vl]=LAk
            FB[vl]=up.global_features(PB);FMB[vl]=up.contrast_features(PB);LBk,cardB=up.local_features(PB,plan);LB[vl]=LBk
            if not np.array_equal(card,cardB):raise ValueError("orientation cardinality")
            inner_imbalance[vl]=up.target_plate_imbalance(plan)[None,:];cards.append(card.astype(int).tolist())
            hashes.append(hashlib.sha256(json.dumps(plan,sort_keys=True,separators=(",",":")).encode()).hexdigest())
        def post_local(orientation,F,FM,L):
            R=iyy-ipred[orientation];common=R.mean(1)
            contrast=np.array([R[i,np.asarray(cards[int(inner[i])])==2].mean()-R[i,np.asarray(cards[int(inner[i])])==3].mean() for i in range(len(tr))])
            E=np.empty_like(R)
            for k in range(K):
                fi=np.flatnonzero(inner!=k);vl=np.flatnonzero(inner==k)
                ma=up.fit_scalar(F[fi],common[fi],ipp[fi]);md=up.fit_scalar(FM[fi],contrast[fi],ipp[fi])
                E[vl]=R[vl]-up.pooled_correction(up.predict_scalar(F[vl],ma),up.predict_scalar(FM[vl],md),np.asarray(cards[k],int))
            E2=np.empty_like(R)
            for k in range(K):
                fi=np.flatnonzero(inner!=k);vl=np.flatnonzero(inner==k);mask3=L[fi,:,4]>0.5
                lc=up.fit_local(L[fi],E[fi],ipp[fi]);l2=up.fit_local_mask(L[fi,:,:4],E[fi],ipp[fi],~mask3);l3=up.fit_local_mask(L[fi,:,:4],E[fi],ipp[fi],mask3)
                card=np.asarray(cards[k],int);m2=card==2;m3=card==3;Dc=up.predict_local(L[vl],lc);Ds=np.empty((len(vl),TARGETS))
                Ds[:,m2]=up.predict_local(L[vl][:,m2,:4],l2);Ds[:,m3]=up.predict_local(L[vl][:,m3,:4],l3)
                E2[vl]=E[vl]-LOCAL_STRENGTH*((2.0/3.0)*Ds+(1.0/3.0)*Dc)
            return E2
        E2A=post_local(0,FA,FMA,LA);E2B=post_local(1,FB,FMB,LB)
        mq=meanquad_basis(Q[tr])
        # Common meanquad control layer is unchanged and cross-fitted for both orientations.
        def post_common(E2):
            target=E2.mean(1);post=np.empty_like(E2)
            for k in range(K):
                fi=np.flatnonzero(inner!=k);vl=np.flatnonzero(inner==k)
                cm=up.fit_control_ridge(mq[fi],target[fi],ipp[fi])
                post[vl]=E2[vl]-up.predict_control(mq[vl],cm)[:,None]
            return post
        postA=post_common(E2A);postB0=post_common(E2B)
        # B retains the verified prior-damped plate interaction before its rank-1 layer.
        Xint=inner_imbalance*(Q[tr,0]-Q[tr,1])[:,None];postB=np.empty_like(postB0);plate_models=[]
        for k in range(K):
            fi=np.flatnonzero(inner!=k);vl=np.flatnonzero(inner==k)
            im=up.fit_plate_interaction(Xint[fi],postB0[fi],ipp[fi])
            postB[vl]=postB0[vl]-PRIOR*up.predict_plate_interaction(Xint[vl],im);plate_models.append(im)
        oldB=fit_rank1(mq,postB,ipp);newB=fit_rank1(B_full_quality_basis(Q[tr]),postB,ipp)
        oldA=fit_rank1(mq,postA,ipp);newA=fit_rank1(A_level_basis(Q[tr]),postA,ipp)
        deltaB=(predict_rank1(B_full_quality_basis(Q[te]),newB)-predict_rank1(meanquad_basis(Q[te]),oldB))/K
        deltaA=(predict_rank1(A_level_basis(Q[te]),newA)-predict_rank1(meanquad_basis(Q[te]),oldA))/(K*K)
        cand[1,te]=best[1,te]+deltaB;cand[0,te]=best[0,te]+deltaA
        records.append({"fold":f,"spectral_option":sel,"inner_plan_hashes":hashes,"inner_cardinality":cards,
          "B_old_rank1_model":oldB,"B_new_rank1_model":newB,"A_old_rank1_model":oldA,"A_new_rank1_model":newA,
          "B_rank1_replacement_strength":1.0/K,"A_rank1_replacement_strength":1.0/(K*K),
          "B_delta_sd":float(np.std(deltaB)),"A_delta_sd":float(np.std(deltaA)),
          "B_quality_basis":["range_mean","range_halfdiff","range_mean_squared","neg_logmedian_mean","neg_logmedian_halfdiff","pos_logmedian_mean","pos_logmedian_halfdiff","neg_cv_mean","neg_cv_halfdiff","pos_cv_mean","pos_cv_halfdiff"],
          "A_level_basis":["range_mean","range_halfdiff","range_mean_squared","neg_logmedian_mean","neg_logmedian_halfdiff","pos_logmedian_mean","pos_logmedian_halfdiff"],
          "B_plate_crossfit_models":plate_models})
    return cand,{"y":y,"patients":p,"folds":folds,"bandwidth07":bw,"r13":r13,"best":best,"sample_ids":data["sample_ids"],"drug_ids":data["drug_ids"]},records

def execute(reference_dir,curves,quality_features,best_predictions,output):
    verify_freeze(reference_dir,curves,quality_features,best_predictions)
    if output.exists():raise ValueError("Output exists")
    cand,ctx,records=construct(reference_dir,curves,quality_features,best_predictions)
    output.mkdir(parents=True,exist_ok=False);np.savez_compressed(output/"predictions_private.npz",candidate=cand,**ctx)
    y,p,folds=ctx["y"],ctx["patients"].astype(str),ctx["folds"];bw,r13,best=ctx["bandwidth07"],ctx["r13"],ctx["best"]
    ci,cm,bm=up.compare(cand,bw,y,p,folds);cb,_,bestm=up.compare(cand,best,y,p,folds);c13,_,r13m=up.compare(cand,r13,y,p,folds)
    gate={"mse":ci["candidate_mse"]<ci["reference_mse"],"patients":ci["patient_wins"]>=30,"folds":ci["fold_wins"]==5,"p90":ci["p90_nonworse"],"beats_verified_best":cm["mse"]<bestm["mse"]}
    decision="NEW_BEST_PENDING_R18" if all(gate.values()) and c13["relative_gain"]>=.05 and c13["patient_wins"]>=40 and c13["fold_wins"]>=4 and c13["p90_nonworse"] else "REJECT"
    result={"schema":"dosepilot.orientation_specific_control_quality_rank1.result.v1","status":"COMPLETE","role":"REPEATED_ADAPTIVE_DEVELOPMENT_NOT_INDEPENDENT_VALIDATION",
      "candidate":cm,"bandwidth07":bm,"verified_best":bestm,"r13":r13m,"candidate_vs_bandwidth07":dict(ci,gate=gate),
      "candidate_vs_verified_best":cb,"candidate_vs_r13":c13,"fold_records":records,"decision":decision,
      "prediction_sha256":sha(output/"predictions_private.npz"),"protected22_access":False,"independent_validation":False,
      "official_competition_score":None,"automatic_retry":False}
    write_new(output/"RESULT.json",result)
    print(json.dumps({"decision":decision,"candidate_mse":cm["mse"],"best_mse":bestm["mse"],"vs_bw07":ci,"vs_best":cb,
      "orientation_mse":cm["orientation_mse"],"B_delta_sd":[r["B_delta_sd"] for r in records],"A_delta_sd":[r["A_delta_sd"] for r in records]},indent=2))
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--reference-dir",type=Path,required=True);ap.add_argument("--curves",type=Path,required=True)
    ap.add_argument("--quality-features",type=Path,required=True);ap.add_argument("--best-predictions",type=Path,required=True);ap.add_argument("--output",type=Path,required=True);a=ap.parse_args()
    execute(a.reference_dir,a.curves,a.quality_features,a.best_predictions,a.output)
if __name__=="__main__":main()
