#!/usr/bin/env python3
from __future__ import annotations
import os
for n in ("OPENBLAS_NUM_THREADS","OMP_NUM_THREADS","MKL_NUM_THREADS"):os.environ[n]="1"
import argparse,hashlib,json,sys
from pathlib import Path
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent
STUDY=HERE.parent
sys.path[:0]=[str(STUDY),str(STUDY/"engine"),str(STUDY/"acceleration"),str(STUDY/"hybrid_residual")]
from compact_train import load_prepared
from coverage_methods import acquire,catalog_from_features
from fast_coverage import plan_panel_fast
TARGETS=24
PRIOR=0.125
LOCAL_STRENGTH=2.0*PRIOR
OPTIONS=[("identity",0.0)]+[(f,l) for f in (0.1,0.3,0.6) for l in (0.1,1.0,10.0)]
EXPECTED_BW07=0.0010582750420801538
EXPECTED_R13=0.0011448586813828537
EXPECTED_BASE=0.0010545312547735701
EXPECTED_BEST=0.0010457053521987507

def sha(p):
    with Path(p).open("rb") as f:return hashlib.file_digest(f,"sha256").hexdigest()
def write_new(p,v):
    with Path(p).open("x",encoding="utf-8") as f:json.dump(v,f,indent=2,allow_nan=False);f.write("\n")
def option_index(sel):
    q=(sel[0],float(sel[1]))
    for i,o in enumerate(OPTIONS):
        if o[0]==q[0] and float(o[1])==q[1]:return i
    raise ValueError("unknown spectral option")
def patient_weights(pp):
    pp=np.asarray(pp).astype(str);ids,inv,c=np.unique(pp,return_inverse=True,return_counts=True)
    return 1.0/(len(ids)*c[inv])
def global_features(P):
    P=np.asarray(P,float)
    if P.ndim!=2 or P.shape[1]!=64:raise ValueError("paid matrix shape")
    return np.column_stack([P.mean(1),P.std(1),P.min(1),P.max(1)])
def contrast_features(P):
    P=np.asarray(P,float)
    if P.ndim!=2 or P.shape[1]!=64:raise ValueError("paid matrix shape")
    return np.column_stack([P.min(1),P.max(1)])
def local_features(P,plan):
    P=np.asarray(P,float);owner=np.asarray(plan["coordinate_target_indices"],int)
    if P.ndim!=2 or P.shape[1]!=64 or owner.shape!=(64,):raise ValueError("local feature shape")
    n=len(P);L=np.empty((n,TARGETS,5));card=np.bincount(owner,minlength=TARGETS)
    if int((card==2).sum())!=8 or int((card==3).sum())!=16 or int(card.sum())!=64:raise ValueError("cardinality contract")
    for j in range(TARGETS):
        Z=P[:,owner==j]
        L[:,j,0]=Z.mean(1);L[:,j,1]=Z.std(1);L[:,j,2]=Z.min(1);L[:,j,3]=Z.max(1);L[:,j,4]=float(card[j]==3)
    return L,card
def fit_scalar(F,residual,pp):
    F=np.asarray(F,float);residual=np.asarray(residual,float);w=patient_weights(pp)
    if F.ndim!=2 or residual.shape!=(len(F),):raise ValueError("scalar calibration shape")
    mu=np.sum(w[:,None]*F,0);a=float(np.sum(w*residual));X=F-mu
    beta=np.linalg.pinv(X.T@(w[:,None]*X),rcond=1e-12)@(X.T@(w*(residual-a)))
    return {"intercept":a,"feature_mean":mu.tolist(),"beta":beta.tolist()}
def predict_scalar(F,m):
    return float(m["intercept"])+(np.asarray(F,float)-np.asarray(m["feature_mean"],float))@np.asarray(m["beta"],float)
def fit_local(X,R,pp):
    X=np.asarray(X,float);R=np.asarray(R,float)
    if X.ndim!=3 or X.shape[:2]!=R.shape or X.shape[1]!=TARGETS:raise ValueError("local calibration shape")
    n,t,d=X.shape;w=(patient_weights(pp)[:,None]/t)*np.ones((1,t));xf=X.reshape(-1,d);rf=R.reshape(-1);wf=w.reshape(-1)
    mu=np.sum(wf[:,None]*xf,0);a=float(np.sum(wf*rf));Z=xf-mu
    beta=np.linalg.pinv(Z.T@(wf[:,None]*Z),rcond=1e-12)@(Z.T@(wf*(rf-a)))
    return {"intercept":a,"feature_mean":mu.tolist(),"beta":beta.tolist()}
def fit_local_mask(X,R,pp,mask):
    X=np.asarray(X,float);R=np.asarray(R,float);mask=np.asarray(mask,bool)
    if X.ndim!=3 or X.shape[:2]!=R.shape or mask.shape!=R.shape:raise ValueError("masked local calibration shape")
    n,t,d=X.shape;w=(patient_weights(pp)[:,None]/t)*np.ones((1,t))
    xf=X[mask];rf=R[mask];wf=w[mask]
    if len(rf)==0 or float(wf.sum())<=1e-30:raise ValueError("empty masked local calibration")
    wf=wf/wf.sum();mu=np.sum(wf[:,None]*xf,0);a=float(np.sum(wf*rf));Z=xf-mu
    beta=np.linalg.pinv(Z.T@(wf[:,None]*Z),rcond=1e-12)@(Z.T@(wf*(rf-a)))
    return {"intercept":a,"feature_mean":mu.tolist(),"beta":beta.tolist()}
def predict_local(X,m):
    return float(m["intercept"])+(np.asarray(X,float)-np.asarray(m["feature_mean"],float))@np.asarray(m["beta"],float)
def control_basis(F):
    F=np.asarray(F,float)
    if F.ndim!=2 or F.shape[1]!=2:raise ValueError("raw control feature shape")
    a,b=F[:,0],F[:,1];m=(a+b)/2.0;d=(a-b)/2.0
    return np.column_stack([m,d,m*m])
def fit_control_ridge(F,residual,pp):
    F=np.asarray(F,float);residual=np.asarray(residual,float);w=patient_weights(pp)
    if F.ndim!=2 or F.shape[1]!=3 or residual.shape!=(len(F),):raise ValueError("control calibration shape")
    mu=np.sum(w[:,None]*F,axis=0);a=float(np.sum(w*residual));Z=F-mu
    gram=Z.T@(w[:,None]*Z);scale=float(np.trace(gram)/F.shape[1]);lam=PRIOR*scale
    rhs=Z.T@(w*(residual-a))
    beta=np.linalg.solve(gram+lam*np.eye(F.shape[1]),rhs) if lam>0 else np.linalg.pinv(gram,rcond=1e-12)@rhs
    return {"intercept":a,"feature_mean":mu.tolist(),"beta":beta.tolist(),"ridge_lambda":float(lam),"feature_energy_scale":scale}
def predict_control(F,m):
    return float(m["intercept"])+(np.asarray(F,float)-np.asarray(m["feature_mean"],float))@np.asarray(m["beta"],float)
def target_plate_imbalance(plan):
    owner=np.asarray(plan["coordinate_target_indices"],int);plates=np.asarray(plan["orientation_B_plate_indices"],int)
    if owner.shape!=(64,) or plates.shape!=(64,):raise ValueError("plate imbalance plan shape")
    out=np.empty(TARGETS,float)
    for j in range(TARGETS):
        q=plates[owner==j]
        if len(q) not in (2,3):raise ValueError("target cardinality changed")
        out[j]=((q==0).sum()-(q==1).sum())/len(q)
    return out
def fit_plate_interaction(X,R,pp):
    X=np.asarray(X,float);R=np.asarray(R,float);pp=np.asarray(pp).astype(str)
    if X.shape!=R.shape or X.ndim!=2 or X.shape[1]!=TARGETS or len(pp)!=len(X):raise ValueError("plate interaction shape")
    w=patient_weights(pp)[:,None]/TARGETS
    den=float(np.sum(w*X*X));num=float(np.sum(w*X*R))
    beta=num/(den*(1.0+PRIOR)+1e-30)
    return {"beta":float(beta),"ridge_factor":float(1.0+PRIOR),"feature_energy":den}
def predict_plate_interaction(X,m):
    return float(m["beta"])*np.asarray(X,float)
def load_control_features(path,sample_ids):
    df=pd.read_csv(path)
    required=["sample_id","p1_logrange","p2_logrange"]
    if list(df.columns)!=required or len(df)!=119 or df["sample_id"].astype(str).nunique()!=119:raise ValueError("control feature contract")
    m=df.set_index(df["sample_id"].astype(str))
    order=np.asarray(sample_ids).astype(str)
    if set(order)!=set(m.index):raise ValueError("control sample identity")
    X=m.loc[order,["p1_logrange","p2_logrange"]].to_numpy(float)
    if X.shape!=(119,2) or not np.isfinite(X).all():raise ValueError("control feature values")
    return X
def pooled_correction(c_all,d,card):
    c_all=np.asarray(c_all,float);d=np.asarray(d,float);card=np.asarray(card,int)
    m2=card==2;m3=card==3
    C=np.empty((len(c_all),TARGETS));C[:,m2]=(c_all+d/3.0)[:,None];C[:,m3]=(c_all-d/6.0)[:,None]
    return C
def risks(q,y,p):
    e=((q[0]-y)**2+(q[1]-y)**2)/2
    return np.stack([e[p==g].mean(0) for g in np.unique(p)])
def metrics(q,y,p,folds):
    pt=risks(q,y,p);per=pt.mean(1);groups=np.unique(p);pf=np.array([folds[np.flatnonzero(p==g)[0]] for g in groups])
    return {"mse":float(per.mean()),"p90_rmse":float(np.quantile(np.sqrt(per),.9)),
      "fold_mse":[float(per[pf==f].mean()) for f in range(5)],
      "orientation_mse":[float(np.mean([((q[o,p==g]-y[p==g])**2).mean() for g in groups])) for o in (0,1)]}
def compare(c,r,y,p,folds):
    cm,rm=metrics(c,y,p,folds),metrics(r,y,p,folds);cp,rp=risks(c,y,p).mean(1),risks(r,y,p).mean(1)
    return {"candidate_mse":cm["mse"],"reference_mse":rm["mse"],"relative_gain":float(1-cm["mse"]/rm["mse"]),
      "patient_wins":int((cp<rp).sum()),"patient_losses":int((cp>rp).sum()),"patient_ties":int((cp==rp).sum()),
      "fold_wins":int(sum(a<b for a,b in zip(cm["fold_mse"],rm["fold_mse"]))),"p90_nonworse":bool(cm["p90_rmse"]<=rm["p90_rmse"])},cm,rm

def execute(reference_dir,curves,control_features,base_predictions,best_predictions,output):
    fr=json.loads((HERE/"FREEZE.json").read_text(encoding="utf-8"))
    if fr.get("state")!="FROZEN_AFTER_DIAGNOSTIC_BEFORE_CANONICAL_REPLAY":raise ValueError("freeze state")
    paths={"reference_predictions":reference_dir/"predictions_private.npz","reference_result":reference_dir/"RESULT.json",
           "curves":curves,"catalog":STUDY/"TRAIN_CATALOG.json","control_features":control_features,
           "base_predictions":base_predictions,"best_predictions":best_predictions}
    for f in range(5):
        paths[f"reference_inner_{f}"]=reference_dir/f"outer_{f:02d}"/"inner_predictions_private.npz"
        paths[f"reference_plan_{f}"]=reference_dir/f"outer_{f:02d}"/"plan.json"
    for k,pth in paths.items():
        if sha(pth)!=fr["input_sha256"][k]:raise ValueError("input changed "+k)
    for rel,h in fr["source_sha256"].items():
        if sha(STUDY.parent/rel)!=h:raise ValueError("source changed "+rel)
    for rel,h in fr["dependency_sha256"].items():
        if sha(STUDY.parent/rel)!=h:raise ValueError("dependency changed "+rel)
    if output.exists():raise ValueError("Output exists")
    data,feat,_=load_prepared(curves,STUDY/"TRAIN_CATALOG.json");x=feat["x_replicates"];catalog=catalog_from_features(feat);y=data["y"];p=data["patient_ids"].astype(str)
    control_X=load_control_features(control_features,data["sample_ids"])
    rz=np.load(paths["reference_predictions"],allow_pickle=False);basez=np.load(base_predictions,allow_pickle=False);bestz=np.load(best_predictions,allow_pickle=False)
    folds=rz["folds"];bw=rz["bandwidth07"];r13=rz["r13"];base=basez["candidate"];best=bestz["candidate"]
    if y.shape!=(119,24) or len(np.unique(p))!=59:raise ValueError("task changed")
    for name,z in (("reference",rz),("base",basez),("best",bestz)):
        if not np.array_equal(z["y"],y) or not np.array_equal(z["patients"].astype(str),p):raise ValueError(name+" identity")
    if not np.array_equal(basez["folds"],folds) or not np.array_equal(bestz["folds"],folds):raise ValueError("fold identity")
    if abs(metrics(bw,y,p,folds)["mse"]-EXPECTED_BW07)>1e-15 or abs(metrics(r13,y,p,folds)["mse"]-EXPECTED_R13)>1e-15:raise ValueError("control")
    if abs(metrics(base,y,p,folds)["mse"]-EXPECTED_BASE)>1e-15:raise ValueError("base control")
    if abs(metrics(best,y,p,folds)["mse"]-EXPECTED_BEST)>1e-15:raise ValueError("best control")
    rr=json.loads(paths["reference_result"].read_text(encoding="utf-8"));cand=base.copy();records=[]
    for f in range(5):
        tr=np.flatnonzero(folds!=f);te=np.flatnonzero(folds==f)
        iz=np.load(paths[f"reference_inner_{f}"],allow_pickle=False);inner=iz["folds"];iyy=iz["y"];ipp=iz["patients"].astype(str)
        if not np.array_equal(iyy,y[tr]) or not np.array_equal(ipp,p[tr]):raise ValueError("inner identity")
        sel=rr["selections"][f]["selected"]["bandwidth07"];idx=option_index(sel);ipred=iz["bandwidth07"][idx];R=iyy-ipred[1];common_residual=R.mean(1)
        F=np.full((len(tr),4),np.nan);FM=np.full((len(tr),2),np.nan);L=np.full((len(tr),TARGETS,5),np.nan);contrast=np.full(len(tr),np.nan);inner_imbalance=np.full((len(tr),TARGETS),np.nan);cards=[];hashes=[]
        for k in range(3):
            sub=tr[inner!=k];vl=np.flatnonzero(inner==k);val=tr[vl];plan=plan_panel_fast(x[sub],y[sub],p[sub],catalog);P=acquire(x[val],plan,"B")
            F[vl]=global_features(P);FM[vl]=contrast_features(P);Lb,card=local_features(P,plan);L[vl]=Lb;inner_imbalance[vl]=target_plate_imbalance(plan)[None,:];cards.append(card.astype(int).tolist())
            m2=card==2;m3=card==3;contrast[vl]=R[vl][:,m2].mean(1)-R[vl][:,m3].mean(1)
            hashes.append(hashlib.sha256(json.dumps(plan,sort_keys=True,separators=(",",":")).encode()).hexdigest())
        if not np.isfinite(F).all() or not np.isfinite(FM).all() or not np.isfinite(L).all() or not np.isfinite(contrast).all():raise ValueError("inner features incomplete")
        # cross-fitted upstream correction to form leakage-resistant local-layer targets
        local_target=np.empty_like(R);cross_models=[]
        for k in range(3):
            fi=np.flatnonzero(inner!=k);vl=np.flatnonzero(inner==k);ma=fit_scalar(F[fi],common_residual[fi],ipp[fi]);md=fit_scalar(FM[fi],contrast[fi],ipp[fi]);ca=predict_scalar(F[vl],ma);dd=predict_scalar(FM[vl],md);card=np.asarray(cards[k],int);C=pooled_correction(ca,dd,card);local_target[vl]=R[vl]-C
            cross_models.append({"all":ma,"contrast":md})
        # Cross-fit the verified local layer as well so the control-calibrator target never sees an in-sample local fit.
        control_target_matrix=np.empty_like(R);control_cross_local=[]
        for k in range(3):
            fi=np.flatnonzero(inner!=k);vl=np.flatnonzero(inner==k);mask3_fit=L[fi,:,4]>0.5
            lc=fit_local(L[fi],local_target[fi],ipp[fi]);l2=fit_local_mask(L[fi,:,:4],local_target[fi],ipp[fi],~mask3_fit);l3=fit_local_mask(L[fi,:,:4],local_target[fi],ipp[fi],mask3_fit)
            card=np.asarray(cards[k],int);m2=card==2;m3=card==3
            Dc= predict_local(L[vl],lc);Ds=np.empty((len(vl),TARGETS))
            Ds[:,m2]=predict_local(L[vl][:,m2,:4],l2);Ds[:,m3]=predict_local(L[vl][:,m3,:4],l3)
            Dp=(2.0/3.0)*Ds+(1.0/3.0)*Dc
            control_target_matrix[vl]=local_target[vl]-LOCAL_STRENGTH*Dp
            control_cross_local.append({"common":lc,"two":l2,"three":l3})
        control_target=control_target_matrix.mean(axis=1)
        control_train_basis=control_basis(control_X[tr])
        post_control_matrix=np.empty_like(control_target_matrix);control_cross_models=[]
        for k in range(3):
            fi=np.flatnonzero(inner!=k);vl=np.flatnonzero(inner==k)
            cm=fit_control_ridge(control_train_basis[fi],control_target[fi],ipp[fi])
            post_control_matrix[vl]=control_target_matrix[vl]-predict_control(control_train_basis[vl],cm)[:,None]
            control_cross_models.append(cm)
        control_model=fit_control_ridge(control_train_basis,control_target,ipp)
        interaction_X=inner_imbalance*(control_X[tr,0]-control_X[tr,1])[:,None]
        interaction_model=fit_plate_interaction(interaction_X,post_control_matrix,ipp)
        local_common=fit_local(L,local_target,ipp)
        card_mask=L[:,:,4]>0.5
        local_two=fit_local_mask(L[:,:,:4],local_target,ipp,~card_mask)
        local_three=fit_local_mask(L[:,:,:4],local_target,ipp,card_mask)
        model_all=fit_scalar(F,common_residual,ipp);model_d=fit_scalar(FM,contrast,ipp)
        plan=json.loads(paths[f"reference_plan_{f}"].read_text(encoding="utf-8"));Pt=acquire(x[te],plan,"B");Ft=global_features(Pt);FMt=contrast_features(Pt);Lt,card=local_features(Pt,plan)
        ca=predict_scalar(Ft,model_all);dd=predict_scalar(FMt,model_d);C=pooled_correction(ca,dd,card)
        D_common=predict_local(Lt,local_common);m2=card==2;m3=card==3;D_sep=np.empty((len(te),TARGETS))
        D_sep[:,m2]=predict_local(Lt[:,m2,:4],local_two);D_sep[:,m3]=predict_local(Lt[:,m3,:4],local_three)
        D_pool=(2.0/3.0)*D_sep+(1.0/3.0)*D_common
        control_correction=predict_control(control_basis(control_X[te]),control_model)
        outer_imbalance=target_plate_imbalance(plan)
        interaction_X_out=(control_X[te,0]-control_X[te,1])[:,None]*outer_imbalance[None,:]
        interaction_correction=PRIOR*predict_plate_interaction(interaction_X_out,interaction_model)
        cand[1,te]=base[1,te]+C+LOCAL_STRENGTH*D_pool+control_correction[:,None]+interaction_correction
        records.append({"fold":f,"spectral_option":sel,"inner_plan_hashes":hashes,"inner_cardinality":cards,"outer_cardinality":card.astype(int).tolist(),
          "global_calibration":model_all,"contrast_calibration":model_d,"crossfit_calibrations":cross_models,
          "local_common_calibration":local_common,"local_two_dose_calibration":local_two,"local_three_dose_calibration":local_three,
          "control_crossfit_local_calibrations":control_cross_local,
          "control_feature_columns":["p1_logrange","p2_logrange"],"control_basis":["mean_range","half_plate_difference","mean_range_squared"],
          "control_crossfit_calibrations":control_cross_models,"control_calibration":control_model,
          "inner_plate_imbalance":inner_imbalance.tolist(),"outer_plate_imbalance":outer_imbalance.tolist(),
          "plate_interaction_model":interaction_model,"plate_interaction_deploy_strength":PRIOR,
          "local_pooling_separate_weight":2.0/3.0,"local_pooling_common_weight":1.0/3.0,
          "local_strength":LOCAL_STRENGTH,"test_global_correction_sd":float(np.std(ca)),"test_contrast_sd":float(np.std(dd)),
          "test_control_correction_sd":float(np.std(control_correction)),
          "test_plate_interaction_correction_sd":float(np.std(interaction_correction)),
          "test_local_common_sd":float(np.std(D_common)),"test_local_separate_sd":float(np.std(D_sep)),
          "test_local_pooled_sd":float(np.std(D_pool)),"test_local_scaled_sd":float(np.std(LOCAL_STRENGTH*D_pool))})
    output.mkdir(parents=True,exist_ok=False)
    np.savez_compressed(output/"predictions_private.npz",candidate=cand,base=base,best=best,bandwidth07=bw,r13=r13,y=y,patients=p,folds=folds,sample_ids=rz["sample_ids"],drug_ids=rz["drug_ids"])
    ci,cm,bm=compare(cand,bw,y,p,folds);cb,_,bestm=compare(cand,best,y,p,folds);c13,_,r13m=compare(cand,r13,y,p,folds)
    gate={"mse":ci["candidate_mse"]<ci["reference_mse"],"patients":ci["patient_wins"]>=30,"folds":ci["fold_wins"]==5,"p90":ci["p90_nonworse"],"beats_verified_best":cm["mse"]<bestm["mse"]}
    decision="NEW_BEST_PENDING_R18" if all(gate.values()) and c13["relative_gain"]>=.05 and c13["patient_wins"]>=40 and c13["fold_wins"]>=4 and c13["p90_nonworse"] else "REJECT"
    result={"schema":"dosepilot.standard_control_meanquad_plate_interaction_v2.result.v1","status":"COMPLETE","role":"REPEATED_ADAPTIVE_DEVELOPMENT_NOT_INDEPENDENT_VALIDATION",
      "candidate":cm,"bandwidth07":bm,"verified_best":bestm,"r13":r13m,"candidate_vs_bandwidth07":dict(ci,gate=gate),"candidate_vs_verified_best":cb,
      "candidate_vs_r13":c13,"fold_records":records,"decision":decision,"prediction_sha256":sha(output/"predictions_private.npz"),
      "protected22_access":False,"independent_validation":False,"official_competition_score":None,"automatic_retry":False}
    write_new(output/"RESULT.json",result)
    print(json.dumps({"decision":decision,"candidate_mse":cm["mse"],"best_mse":bestm["mse"],"vs_bw07":ci,"vs_best":cb,
      "local_strength":LOCAL_STRENGTH,"fold_local_pooled_sd":[r["test_local_pooled_sd"] for r in records],
      "fold_control_correction_sd":[r["test_control_correction_sd"] for r in records],"fold_plate_interaction_sd":[r["test_plate_interaction_correction_sd"] for r in records]},indent=2))
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--reference-dir",type=Path,required=True);ap.add_argument("--curves",type=Path,required=True);ap.add_argument("--control-features",type=Path,required=True);ap.add_argument("--base-predictions",type=Path,required=True);ap.add_argument("--best-predictions",type=Path,required=True);ap.add_argument("--output",type=Path,required=True);a=ap.parse_args()
    execute(a.reference_dir,a.curves,a.control_features,a.base_predictions,a.best_predictions,a.output)
if __name__=="__main__":main()
