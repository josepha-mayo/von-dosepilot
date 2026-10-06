#!/usr/bin/env python3
import argparse,json,hashlib,sys
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE));import run_study as rs
def sha(p):
    with Path(p).open("rb") as f:return hashlib.file_digest(f,"sha256").hexdigest()
def same_model(a,b,tol=1e-15):
    if abs(float(a["intercept"])-float(b["intercept"]))>tol:return False
    if np.max(np.abs(np.asarray(a["feature_mean"])-np.asarray(b["feature_mean"])))>tol:return False
    if np.max(np.abs(np.asarray(a["beta"])-np.asarray(b["beta"])))>tol:return False
    return True
def same_control_model(a,b,tol=1e-15):
    if not same_model(a,b,tol):return False
    if abs(float(a["ridge_lambda"])-float(b["ridge_lambda"]))>tol:return False
    if abs(float(a["feature_energy_scale"])-float(b["feature_energy_scale"]))>tol:return False
    return True
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--run",type=Path,required=True);ap.add_argument("--reference-dir",type=Path,required=True);ap.add_argument("--curves",type=Path,required=True);ap.add_argument("--control-features",type=Path,required=True);a=ap.parse_args()
    r=json.loads((a.run/"RESULT.json").read_text());z=np.load(a.run/"predictions_private.npz",allow_pickle=False);rr=json.loads((a.reference_dir/"RESULT.json").read_text())
    data,feat,_=rs.load_prepared(a.curves,rs.STUDY/"TRAIN_CATALOG.json");x=feat["x_replicates"];catalog=rs.catalog_from_features(feat);y=data["y"];p=data["patient_ids"].astype(str);folds=z["folds"];cand=z["base"].copy();checks=0
    control_X=rs.load_control_features(a.control_features,data["sample_ids"])
    for f in range(5):
        tr=np.flatnonzero(folds!=f);te=np.flatnonzero(folds==f);iz=np.load(a.reference_dir/f"outer_{f:02d}"/"inner_predictions_private.npz",allow_pickle=False);inner=iz["folds"];ipp=iz["patients"].astype(str)
        sel=rr["selections"][f]["selected"]["bandwidth07"];idx=rs.option_index(sel);ip=iz["bandwidth07"][idx];R=iz["y"]-ip[1];rc=R.mean(1)
        F=np.full((len(tr),4),np.nan);FM=np.full((len(tr),2),np.nan);L=np.full((len(tr),rs.TARGETS,5),np.nan);contrast=np.full(len(tr),np.nan);cards=[];hashes=[]
        for k in range(3):
            sub=tr[inner!=k];vl=np.flatnonzero(inner==k);val=tr[vl];plan=rs.plan_panel_fast(x[sub],y[sub],p[sub],catalog);P=rs.acquire(x[val],plan,"B");F[vl]=rs.global_features(P);FM[vl]=rs.contrast_features(P);Lb,card=rs.local_features(P,plan);L[vl]=Lb;cards.append(card.astype(int).tolist());m2=card==2;m3=card==3;contrast[vl]=R[vl][:,m2].mean(1)-R[vl][:,m3].mean(1);hashes.append(hashlib.sha256(json.dumps(plan,sort_keys=True,separators=(",",":")).encode()).hexdigest())
        E=np.empty_like(R);cross=[]
        for k in range(3):
            fi=np.flatnonzero(inner!=k);vl=np.flatnonzero(inner==k);ma=rs.fit_scalar(F[fi],rc[fi],ipp[fi]);md=rs.fit_scalar(FM[fi],contrast[fi],ipp[fi]);C=rs.pooled_correction(rs.predict_scalar(F[vl],ma),rs.predict_scalar(FM[vl],md),np.asarray(cards[k],int));E[vl]=R[vl]-C;cross.append({"all":ma,"contrast":md})
        control_target_matrix=np.empty_like(R);control_cross_local=[]
        for k in range(3):
            fi=np.flatnonzero(inner!=k);vl=np.flatnonzero(inner==k);mask3_fit=L[fi,:,4]>0.5
            lc=rs.fit_local(L[fi],E[fi],ipp[fi]);l2=rs.fit_local_mask(L[fi,:,:4],E[fi],ipp[fi],~mask3_fit);l3=rs.fit_local_mask(L[fi,:,:4],E[fi],ipp[fi],mask3_fit)
            cardk=np.asarray(cards[k],int);m2k=cardk==2;m3k=cardk==3;Dc_k=rs.predict_local(L[vl],lc);Ds_k=np.empty((len(vl),rs.TARGETS))
            Ds_k[:,m2k]=rs.predict_local(L[vl][:,m2k,:4],l2);Ds_k[:,m3k]=rs.predict_local(L[vl][:,m3k,:4],l3)
            Dp_k=(2.0/3.0)*Ds_k+(1.0/3.0)*Dc_k;control_target_matrix[vl]=E[vl]-rs.LOCAL_STRENGTH*Dp_k
            control_cross_local.append({"common":lc,"two":l2,"three":l3})
        control_target=control_target_matrix.mean(axis=1);control_model=rs.fit_control_ridge(control_X[tr],control_target,ipp)
        lm_common=rs.fit_local(L,E,ipp);mask3=L[:,:,4]>0.5;lm_two=rs.fit_local_mask(L[:,:,:4],E,ipp,~mask3);lm_three=rs.fit_local_mask(L[:,:,:4],E,ipp,mask3)
        ma=rs.fit_scalar(F,rc,ipp);md=rs.fit_scalar(FM,contrast,ipp);plan=json.loads((a.reference_dir/f"outer_{f:02d}"/"plan.json").read_text());Pt=rs.acquire(x[te],plan,"B");Ft=rs.global_features(Pt);FMt=rs.contrast_features(Pt);Lt,card=rs.local_features(Pt,plan);C=rs.pooled_correction(rs.predict_scalar(Ft,ma),rs.predict_scalar(FMt,md),card)
        Dc=rs.predict_local(Lt,lm_common);m2=card==2;m3=card==3;Ds=np.empty((len(te),rs.TARGETS));Ds[:,m2]=rs.predict_local(Lt[:,m2,:4],lm_two);Ds[:,m3]=rs.predict_local(Lt[:,m3,:4],lm_three);D=(2.0/3.0)*Ds+(1.0/3.0)*Dc
        control_correction=rs.predict_control(control_X[te],control_model)
        cand[1,te]+=C+rs.LOCAL_STRENGTH*D+control_correction[:,None];rec=r["fold_records"][f]
        if hashes!=rec["inner_plan_hashes"] or cards!=rec["inner_cardinality"] or card.astype(int).tolist()!=rec["outer_cardinality"]:raise ValueError("PLAN_OR_CARD")
        if not same_model(ma,rec["global_calibration"]) or not same_model(md,rec["contrast_calibration"]) or not same_model(lm_common,rec["local_common_calibration"]) or not same_model(lm_two,rec["local_two_dose_calibration"]) or not same_model(lm_three,rec["local_three_dose_calibration"]):raise ValueError("MODEL")
        if rec["control_feature_columns"]!=["p1_logrange","p2_logrange"] or not same_control_model(control_model,rec["control_calibration"]):raise ValueError("CONTROL_MODEL")
        for aa,bb in zip(control_cross_local,rec["control_crossfit_local_calibrations"]):
            if not same_model(aa["common"],bb["common"]) or not same_model(aa["two"],bb["two"]) or not same_model(aa["three"],bb["three"]):raise ValueError("CONTROL_CROSSFIT_LOCAL")
        if abs(float(rec["local_pooling_separate_weight"])-2.0/3.0)>1e-15 or abs(float(rec["local_pooling_common_weight"])-1.0/3.0)>1e-15:raise ValueError("POOLING")
        for aa,bb in zip(cross,rec["crossfit_calibrations"]):
            if not same_model(aa["all"],bb["all"]) or not same_model(aa["contrast"],bb["contrast"]):raise ValueError("CROSSFIT_MODEL")
        if abs(float(rec["local_strength"])-rs.LOCAL_STRENGTH)>1e-15:raise ValueError("LOCAL_STRENGTH")
        checks+=1
    maxdiff=float(np.max(np.abs(cand-z["candidate"])))
    if maxdiff>5e-16:raise ValueError("RECONSTRUCTION")
    m=rs.metrics(cand,y,p,folds)
    if abs(m["mse"]-r["candidate"]["mse"])>1e-15:raise ValueError("MSE")
    if sha(a.run/"predictions_private.npz")!=r["prediction_sha256"]:raise ValueError("HASH")
    out={"status":"PASS_FLOATING_REPLAY","base_model_refit":False,"calibration_recomputed":True,"candidate_predictions_reconstructed":int(cand.size),"max_prediction_difference":maxdiff,"prediction_tolerance":5e-16,"candidate_mse":m["mse"],"calibration_folds_checked":checks,"prediction_sha256":r["prediction_sha256"],"protected22_access":False}
    (a.run/"VERIFICATION.json").write_text(json.dumps(out,indent=2)+"\n");print(json.dumps(out,indent=2))
if __name__=="__main__":main()
