#!/usr/bin/env python3
from __future__ import annotations
import os
for n in ("OPENBLAS_NUM_THREADS","OMP_NUM_THREADS","MKL_NUM_THREADS"):os.environ[n]="1"
import argparse,datetime,hashlib,importlib.metadata,json,sys,time,traceback
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;STUDY=HERE.parent
sys.path[:0]=[str(HERE),str(STUDY),str(STUDY/"engine"),str(STUDY/"acceleration"),str(STUDY/"hybrid_residual"),str(STUDY/"cross_patient_bandwidth"),str(STUDY/"interpolated_median_geometry")]
from interpolated_jackknife import InterpolatedJackknifeBandwidth
OPTIONS=[("identity",0.)]+[(f,l) for f in (.1,.3,.6) for l in (.1,1.,10.)]
EXPECTED_CURVES="b192dc242362d74c4faa941752792336c7610d9bd403cccbf1cee7a8a1fc7c94"
EXPECTED_REF_SHA="f2fea2c796f3c043f32fddff3d7a2a9e5e27a9750d30f8695891a604c2f87ec2"
EXPECTED_BW07=.0010582750420801538;EXPECTED_R13=.0011448586813828537;EXPECTED_BEST=.0010574921945978527
LOCK="8118b562b78b3f55866d6239a38280c942df2c7d81f0b7c4ce71ba0e39ce9ffc"
def sha(p):
 with Path(p).open("rb") as f:return hashlib.file_digest(f,"sha256").hexdigest()
def write_new(p,v):
 with Path(p).open("x",encoding="utf-8") as f:json.dump(v,f,indent=2,allow_nan=False);f.write("\n")
def risks(q,y,p):
 e=((q[0]-y)**2+(q[1]-y)**2)/2;return np.stack([e[p==g].mean(0) for g in np.unique(p)])
def metrics(q,y,p,folds):
 pt=risks(q,y,p);per=pt.mean(1);u=np.unique(p);pf=np.array([folds[np.flatnonzero(p==g)[0]] for g in u])
 return {"mse":float(per.mean()),"p90_rmse":float(np.quantile(np.sqrt(per),.9)),"fold_mse":[float(per[pf==f].mean()) for f in range(5)],"orientation_mse":[float(np.mean([((q[o,p==g]-y[p==g])**2).mean() for g in u])) for o in (0,1)]}
def compare(c,r,y,p,folds):
 cm,rm=metrics(c,y,p,folds),metrics(r,y,p,folds);cp,rp=risks(c,y,p).mean(1),risks(r,y,p).mean(1)
 return {"candidate_mse":cm["mse"],"reference_mse":rm["mse"],"relative_gain":float(1-cm["mse"]/rm["mse"]),"patient_wins":int((cp<rp).sum()),"patient_losses":int((cp>rp).sum()),"patient_ties":int((cp==rp).sum()),"fold_wins":int(sum(a<b for a,b in zip(cm["fold_mse"],rm["fold_mse"]))),"p90_nonworse":bool(cm["p90_rmse"]<=rm["p90_rmse"])},cm,rm
def option_index(sel):
 pair=(sel[0],float(sel[1]))
 for i,o in enumerate(OPTIONS):
  if o[0]==pair[0] and float(o[1])==pair[1]:return i
 raise ValueError("option")
def verify_freeze():
 fr=json.loads((HERE/"FREEZE.json").read_text(encoding="utf-8"))
 if fr.get("state")!="FROZEN_BEFORE_FIRST_INTERPOLATED_JACKKNIFE_FIT":raise ValueError("freeze")
 for rel,h in fr["source_sha256"].items():
  if sha(STUDY.parent/rel)!=h:raise ValueError("source "+rel)
 return fr
def execute(curves,reference_dir,best_predictions,out):
 from threadpoolctl import threadpool_limits
 from compact_train import load_prepared
 from coverage_methods import acquire,fit_prediction_context,CoveragePredictor,catalog_from_features
 from fast_coverage import plan_panel_fast
 verify_freeze()
 if out.exists():raise ValueError("Output exists")
 if sha(curves)!=EXPECTED_CURVES:raise ValueError("curves")
 refp=reference_dir/"predictions_private.npz"
 if sha(refp)!=EXPECTED_REF_SHA:raise ValueError("reference")
 if sha(STUDY/"STUDY_LOCK.json")!=LOCK:raise ValueError("lock")
 lock=json.loads((STUDY/"STUDY_LOCK.json").read_text(encoding="utf-8"))
 for n,h in lock["engine_files"].items():
  if sha(STUDY/"engine"/n)!=h:raise ValueError("engine "+n)
 for n,v in lock["deps"].items():
  if importlib.metadata.version(n)!=v:raise ValueError("dep "+n)
 data,feat,_=load_prepared(curves,STUDY/"TRAIN_CATALOG.json");x,y,p=feat["x_replicates"],data["y"],data["patient_ids"].astype(str);catalog=catalog_from_features(feat)
 rz=np.load(refp,allow_pickle=False);bz=np.load(best_predictions,allow_pickle=False);folds=rz["folds"].copy();bw=rz["bandwidth07"].copy();r13=rz["r13"].copy();best=bz["candidate"].copy()
 if not np.array_equal(rz["y"],y) or not np.array_equal(rz["patients"].astype(str),p):raise ValueError("identity")
 if abs(metrics(best,y,p,folds)["mse"]-EXPECTED_BEST)>1e-15:raise ValueError("best")
 rr=json.loads((reference_dir/"RESULT.json").read_text(encoding="utf-8"))
 out.mkdir(parents=True,exist_ok=False);start=time.monotonic();cand=np.full_like(bw,np.nan);records=[]
 write_new(out/"EXECUTION_INTENT.json",{"schema":"dosepilot.interpolated_jackknife_geometry.intent.v1","utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"role":"REPEATED_ADAPTIVE_DEVELOPMENT_NOT_INDEPENDENT_VALIDATION","protected22_access":False,"automatic_retry":False})
 with threadpool_limits(limits=1):
  for f in range(5):
   tr=np.flatnonzero(folds!=f);te=np.flatnonzero(folds==f);plan=plan_panel_fast(x[tr],y[tr],p[tr],catalog);saved=json.loads((reference_dir/f"outer_{f:02}"/"plan.json").read_text(encoding="utf-8"))
   for k in ("selected_native_indices","orientation_A_plate_indices","orientation_B_plate_indices"):
    if list(plan[k])!=list(saved[k]):raise ValueError("plan "+k)
   pa,pb=[acquire(x[tr],plan,o) for o in ("A","B")];ctx=fit_prediction_context(pa,pb,y[tr],p[tr],plan,catalog.target_ids);base=CoveragePredictor(ctx,plan,.01)
   z=(np.r_[pa,pb]-base.mean_x)/base.scale_x;res=np.r_[y[tr]-base.predict(pa),y[tr]-base.predict(pb)];ids,inv,cnt=np.unique(p[tr],return_inverse=True,return_counts=True);w=np.tile(1./(len(ids)*cnt[inv]),2)/2
   model=InterpolatedJackknifeBandwidth(z,res,w,np.asarray(plan["coordinate_target_indices"]),np.tile(p[tr],2));sel=rr["selections"][f]["selected"]["bandwidth07"];oi=option_index(sel);coef=np.zeros((len(z),24)) if oi==0 else model.coefficients(OPTIONS[oi][1],OPTIONS[oi][0])[0]
   folder=out/f"outer_{f:02}";folder.mkdir();write_new(folder/"plan.json",plan);np.savez_compressed(folder/"model_private.npz",**base.arrays(),**model.arrays(coef))
   for odx,o in enumerate(("A","B")):
    paid=acquire(x[te],plan,o);zq=(paid-base.mean_x)/base.scale_x;cand[odx,te]=base.predict(paid)+model.centered_cross(zq)@coef
   records.append({"fold":f,"spectral_option":sel,"raw_bandwidth_min":float(model.raw_group_bandwidths.min()),"corrected_bandwidth_min":float(model.group_bandwidths.min()),"corrected_bandwidth_median":float(np.median(model.group_bandwidths)),"corrected_bandwidth_max":float(model.group_bandwidths.max()),"distinct_physical_wells":64,"per_plate":32})
 np.savez_compressed(out/"predictions_private.npz",candidate=cand,bandwidth07=bw,r13=r13,best=best,y=y,patients=p,folds=folds,sample_ids=data["sample_ids"],drug_ids=data["drug_ids"])
 ci,cm,bm=compare(cand,bw,y,p,folds);cb,_,bestm=compare(cand,best,y,p,folds);c13,_,r13m=compare(cand,r13,y,p,folds);gate={"mse":ci["candidate_mse"]<ci["reference_mse"],"patients":ci["patient_wins"]>=30,"folds":ci["fold_wins"]==5,"p90":ci["p90_nonworse"],"beats_verified_best":cm["mse"]<bestm["mse"]}
 decision="NEW_BEST_PENDING_R18" if all(gate.values()) and c13["relative_gain"]>=.05 and c13["patient_wins"]>=40 and c13["fold_wins"]>=4 and c13["p90_nonworse"] else "REJECT"
 resu={"schema":"dosepilot.interpolated_jackknife_geometry.result.v1","status":"COMPLETE","role":"REPEATED_ADAPTIVE_DEVELOPMENT_NOT_INDEPENDENT_VALIDATION","candidate":cm,"bandwidth07":bm,"verified_best":bestm,"r13":r13m,"candidate_vs_bandwidth07":dict(ci,gate=gate),"candidate_vs_verified_best":cb,"candidate_vs_r13":c13,"fold_records":records,"decision":decision,"prediction_sha256":sha(out/"predictions_private.npz"),"elapsed_seconds":time.monotonic()-start,"protected22_access":False,"independent_validation":False,"official_competition_score":None,"automatic_retry":False}
 write_new(out/"RESULT.json",resu);print(json.dumps({"decision":decision,"candidate_mse":cm["mse"],"best_mse":bestm["mse"],"vs_bw07":ci,"vs_best":cb},indent=2))
def main():
 ap=argparse.ArgumentParser();ap.add_argument("--curves",type=Path,required=True);ap.add_argument("--reference-dir",type=Path,required=True);ap.add_argument("--best-predictions",type=Path,required=True);ap.add_argument("--output",type=Path,required=True);a=ap.parse_args()
 try:execute(a.curves,a.reference_dir,a.best_predictions,a.output)
 except BaseException as e:
  if a.output.exists() and not (a.output/"FAILURE.json").exists():write_new(a.output/"FAILURE.json",{"error":type(e).__name__,"message":str(e),"traceback":traceback.format_exc(),"automatic_retry":False})
  raise
if __name__=="__main__":main()
