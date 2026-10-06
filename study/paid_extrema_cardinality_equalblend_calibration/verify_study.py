#!/usr/bin/env python3
import argparse,json,hashlib,sys
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE));import run_study as rs
def sha(p):
    with Path(p).open("rb") as f:return hashlib.file_digest(f,"sha256").hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--run",type=Path,required=True);ap.add_argument("--reference-dir",type=Path,required=True);ap.add_argument("--curves",type=Path,required=True);a=ap.parse_args()
    r=json.loads((a.run/"RESULT.json").read_text());z=np.load(a.run/"predictions_private.npz",allow_pickle=False);rr=json.loads((a.reference_dir/"RESULT.json").read_text())
    data,feat,_=rs.load_prepared(a.curves,rs.STUDY/"TRAIN_CATALOG.json");x=feat["x_replicates"];catalog=rs.catalog_from_features(feat)
    y=data["y"];p=data["patient_ids"].astype(str);folds=z["folds"];cand=z["base"].copy();checks=0
    for f in range(5):
        tr=np.flatnonzero(folds!=f);te=np.flatnonzero(folds==f)
        iz=np.load(a.reference_dir/f"outer_{f:02d}"/"inner_predictions_private.npz",allow_pickle=False);inner=iz["folds"]
        sel=rr["selections"][f]["selected"]["bandwidth07"];idx=rs.option_index(sel);ipred=iz["bandwidth07"][idx]
        F=np.full((len(tr),4),np.nan);r2=np.full(len(tr),np.nan);r3=np.full(len(tr),np.nan);hashes=[];cards=[]
        residual=(iz["y"]-ipred[1]).mean(1)
        for k in range(3):
            sub=tr[inner!=k];vl=np.flatnonzero(inner==k);val=tr[vl]
            plan=rs.plan_panel_fast(x[sub],y[sub],p[sub],catalog);F[vl]=rs.paid_features(rs.acquire(x[val],plan,"B"))
            card=np.bincount(np.asarray(plan["coordinate_target_indices"],int),minlength=rs.TARGETS);m2=card==2;m3=card==3
            if int(m2.sum())!=8 or int(m3.sum())!=16:raise ValueError("INNER_CARD")
            R=iz["y"][vl]-ipred[1,vl];r2[vl]=R[:,m2].mean(1);r3[vl]=R[:,m3].mean(1);cards.append(card.astype(int).tolist())
            hashes.append(hashlib.sha256(json.dumps(plan,sort_keys=True,separators=(",",":")).encode()).hexdigest())
        ma=rs.fit_common_calibration(F,residual,iz["patients"].astype(str));m_2=rs.fit_common_calibration(F,r2,iz["patients"].astype(str));m_3=rs.fit_common_calibration(F,r3,iz["patients"].astype(str))
        plan=json.loads((a.reference_dir/f"outer_{f:02d}"/"plan.json").read_text());Ft=rs.paid_features(rs.acquire(x[te],plan,"B"));card=np.bincount(np.asarray(plan["coordinate_target_indices"],int),minlength=rs.TARGETS);m2=card==2;m3=card==3
        ca=rs.predict_common_calibration(Ft,ma);c2=rs.predict_common_calibration(Ft,m_2);c3=rs.predict_common_calibration(Ft,m_3);q=cand[1,te].copy();q[:,m2]+=(0.5*ca+0.5*c2)[:,None];q[:,m3]+=(0.5*ca+0.5*c3)[:,None];cand[1,te]=q;rec=r["fold_records"][f]
        if hashes!=rec["inner_plan_hashes"] or cards!=rec["inner_cardinality"] or card.astype(int).tolist()!=rec["outer_cardinality"]:raise ValueError("PLAN_OR_CARD")
        for key,m in (("calibration_all",ma),("calibration_2",m_2),("calibration_3",m_3)):
            rr0=rec[key]
            if abs(float(m["intercept"])-float(rr0["intercept"]))>1e-15:raise ValueError("INTERCEPT")
            if np.max(np.abs(np.asarray(m["feature_mean"])-np.asarray(rr0["feature_mean"])))>1e-15:raise ValueError("FEATURE_MEAN")
            if np.max(np.abs(np.asarray(m["beta"])-np.asarray(rr0["beta"])))>1e-15:raise ValueError("BETA")
        checks+=1
    if not np.array_equal(cand,z["candidate"]):raise ValueError("RECONSTRUCTION")
    m=rs.metrics(cand,y,p,folds)
    if abs(m["mse"]-r["candidate"]["mse"])>1e-15:raise ValueError("MSE")
    if sha(a.run/"predictions_private.npz")!=r["prediction_sha256"]:raise ValueError("HASH")
    out={"status":"PASS","fit_routine_called":False,"candidate_predictions_reconstructed":int(cand.size),"max_prediction_difference":0.0,
      "candidate_mse":m["mse"],"calibration_folds_checked":checks,"prediction_sha256":r["prediction_sha256"],"protected22_access":False}
    (a.run/"VERIFICATION.json").write_text(json.dumps(out,indent=2)+"\n");print(json.dumps(out,indent=2))
if __name__=="__main__":main()
