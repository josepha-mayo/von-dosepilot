#!/usr/bin/env python3
from __future__ import annotations
import os
for n in ("OPENBLAS_NUM_THREADS","OMP_NUM_THREADS","MKL_NUM_THREADS"):os.environ[n]="1"
import argparse,hashlib,json,sys
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent
STUDY=HERE.parent
sys.path[:0]=[str(STUDY),str(STUDY/"engine"),str(STUDY/"acceleration"),str(STUDY/"hybrid_residual")]
from compact_train import load_prepared
from coverage_methods import acquire,catalog_from_features
from fast_coverage import plan_panel_fast
TARGETS=24
OPTIONS=[("identity",0.0)]+[(f,l) for f in (0.1,0.3,0.6) for l in (0.1,1.0,10.0)]
EXPECTED_BW07=0.0010582750420801538
EXPECTED_R13=0.0011448586813828537
EXPECTED_BASE=0.0010545312547735701
EXPECTED_BEST=0.00104997801532859
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
def paid_features(P):
    P=np.asarray(P,float)
    if P.ndim!=2 or P.shape[1]!=64:raise ValueError("paid matrix shape")
    return np.column_stack([P.mean(axis=1),P.std(axis=1),P.max(axis=1)])
def fit_common_calibration(F,residual,pp):
    F=np.asarray(F,float);residual=np.asarray(residual,float);w=patient_weights(pp)
    if F.ndim!=2 or F.shape[1]!=3 or residual.shape!=(len(F),):raise ValueError("calibration shape")
    mu=np.sum(w[:,None]*F,axis=0);a=float(np.sum(w*residual));X=F-mu
    gram=X.T@(w[:,None]*X);rhs=X.T@(w*(residual-a));beta=np.linalg.pinv(gram,rcond=1e-12)@rhs
    return {"intercept":a,"feature_mean":mu.tolist(),"beta":beta.tolist(),"gram":gram.tolist()}
def predict_common_calibration(F,m):
    F=np.asarray(F,float);mu=np.asarray(m["feature_mean"],float);beta=np.asarray(m["beta"],float)
    return float(m["intercept"])+(F-mu)@beta
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
def execute(reference_dir,curves,base_predictions,best_predictions,output):
    fr=json.loads((HERE/"FREEZE.json").read_text(encoding="utf-8"))
    if fr.get("state")!="FROZEN_AFTER_DIAGNOSTIC_BEFORE_CANONICAL_REPLAY":raise ValueError("freeze state")
    paths={"reference_predictions":reference_dir/"predictions_private.npz","reference_result":reference_dir/"RESULT.json",
           "curves":curves,"catalog":STUDY/"TRAIN_CATALOG.json","base_predictions":base_predictions,"best_predictions":best_predictions}
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
    data,feat,_=load_prepared(curves,STUDY/"TRAIN_CATALOG.json")
    x=feat["x_replicates"];catalog=catalog_from_features(feat);y=data["y"];p=data["patient_ids"].astype(str)
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
        sel=rr["selections"][f]["selected"]["bandwidth07"];idx=option_index(sel);ipred=iz["bandwidth07"][idx]
        inner_features=np.full((len(tr),3),np.nan);inner_plan_hashes=[]
        for k in range(3):
            sub=tr[inner!=k];vl=np.flatnonzero(inner==k);val=tr[vl]
            plan=plan_panel_fast(x[sub],y[sub],p[sub],catalog);paid=acquire(x[val],plan,"B")
            inner_features[vl]=paid_features(paid)
            inner_plan_hashes.append(hashlib.sha256(json.dumps(plan,sort_keys=True,separators=(",",":")).encode()).hexdigest())
        if not np.isfinite(inner_features).all():raise ValueError("inner feature incomplete")
        common_residual=(iyy-ipred[1]).mean(axis=1);model=fit_common_calibration(inner_features,common_residual,ipp)
        plan=json.loads(paths[f"reference_plan_{f}"].read_text(encoding="utf-8"));test_features=paid_features(acquire(x[te],plan,"B"))
        correction=predict_common_calibration(test_features,model);cand[1,te]=base[1,te]+correction[:,None]
        records.append({"fold":f,"spectral_option":sel,"inner_plan_hashes":inner_plan_hashes,"calibration":model,
          "inner_feature_min":inner_features.min(0).tolist(),"inner_feature_mean":inner_features.mean(0).tolist(),"inner_feature_max":inner_features.max(0).tolist(),
          "test_feature_min":test_features.min(0).tolist(),"test_feature_mean":test_features.mean(0).tolist(),"test_feature_max":test_features.max(0).tolist(),
          "common_residual_mean":float(common_residual.mean()),"test_correction_min":float(correction.min()),
          "test_correction_mean":float(correction.mean()),"test_correction_max":float(correction.max())})
    output.mkdir(parents=True,exist_ok=False)
    np.savez_compressed(output/"predictions_private.npz",candidate=cand,base=base,best=best,bandwidth07=bw,r13=r13,y=y,patients=p,folds=folds,
      sample_ids=rz["sample_ids"],drug_ids=rz["drug_ids"])
    ci,cm,bm=compare(cand,bw,y,p,folds);cb,_,bestm=compare(cand,best,y,p,folds);c13,_,r13m=compare(cand,r13,y,p,folds)
    gate={"mse":ci["candidate_mse"]<ci["reference_mse"],"patients":ci["patient_wins"]>=30,"folds":ci["fold_wins"]==5,
          "p90":ci["p90_nonworse"],"beats_verified_best":cm["mse"]<bestm["mse"]}
    decision="NEW_BEST_PENDING_R18" if all(gate.values()) and c13["relative_gain"]>=.05 and c13["patient_wins"]>=40 and c13["fold_wins"]>=4 and c13["p90_nonworse"] else "REJECT"
    result={"schema":"dosepilot.paid_location_scale_common_mode_calibration.result.v1","status":"COMPLETE","role":"REPEATED_ADAPTIVE_DEVELOPMENT_NOT_INDEPENDENT_VALIDATION",
      "candidate":cm,"bandwidth07":bm,"verified_best":bestm,"r13":r13m,"candidate_vs_bandwidth07":dict(ci,gate=gate),
      "candidate_vs_verified_best":cb,"candidate_vs_r13":c13,"fold_records":records,"decision":decision,
      "prediction_sha256":sha(output/"predictions_private.npz"),"protected22_access":False,"independent_validation":False,
      "official_competition_score":None,"automatic_retry":False}
    write_new(output/"RESULT.json",result)
    print(json.dumps({"decision":decision,"candidate_mse":cm["mse"],"best_mse":bestm["mse"],"vs_bw07":ci,"vs_best":cb,
      "calibration":[r["calibration"] for r in records]},indent=2))
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--reference-dir",type=Path,required=True);ap.add_argument("--curves",type=Path,required=True)
    ap.add_argument("--base-predictions",type=Path,required=True);ap.add_argument("--best-predictions",type=Path,required=True)
    ap.add_argument("--output",type=Path,required=True);a=ap.parse_args()
    execute(a.reference_dir,a.curves,a.base_predictions,a.best_predictions,a.output)
if __name__=="__main__":main()
