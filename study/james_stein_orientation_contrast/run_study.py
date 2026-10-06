#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
import numpy as np
PRIOR=0.125
TARGETS=24
OPTIONS=[("identity",0.0)]+[(f,l) for f in (0.1,0.3,0.6) for l in (0.1,1.0,10.0)]
EXPECTED_BW07=0.0010582750420801538
EXPECTED_R13=0.0011448586813828537
EXPECTED_BEST=0.001056883368839387
def sha(p):
    with Path(p).open("rb") as f:return hashlib.file_digest(f,"sha256").hexdigest()
def write_new(p,v):
    with Path(p).open("x",encoding="utf-8") as f:json.dump(v,f,indent=2,allow_nan=False);f.write("\n")
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
def option_index(sel):
    pair=(sel[0],float(sel[1]))
    for i,o in enumerate(OPTIONS):
        if o[0]==pair[0] and float(o[1])==pair[1]:return i
    raise ValueError("unknown option")
def patient_balanced_orientation_residual(pred,y,p,mask):
    groups=np.unique(p[mask])
    return np.stack([np.stack([(y[(p==g)&mask]-pred[o,(p==g)&mask]).mean(0) for g in groups]).mean(0) for o in (0,1)])
def james_stein_calibrator(pred,y,p,inner):
    contrasts=[]
    for k in range(3):
        res=patient_balanced_orientation_residual(pred,y,p,inner==k);contrasts.append(res[0]-res[1])
    contrasts=np.stack(contrasts);cbar=contrasts.mean(0);v=contrasts.var(0,ddof=1)/3.0
    sigma2=float(np.mean(v));norm2=float(np.sum(cbar*cbar))
    alpha=0.0 if norm2<=1e-30 else max(0.0,1.0-(TARGETS-2)*sigma2/norm2)
    scale=PRIOR+(1.0-PRIOR)*alpha
    return contrasts,cbar,v,sigma2,norm2,float(alpha),float(scale)
def execute(reference_dir,bagged_predictions,ijbc_predictions,best_predictions,output):
    here=Path(__file__).resolve().parent;fr=json.loads((here/"FREEZE.json").read_text(encoding="utf-8"))
    if fr.get("state")!="FROZEN_AFTER_DIAGNOSTIC_BEFORE_CANONICAL_REPLAY":raise ValueError("freeze state")
    paths={"reference_predictions":reference_dir/"predictions_private.npz","reference_result":reference_dir/"RESULT.json",
           "bagged_predictions":bagged_predictions,"ijbc_predictions":ijbc_predictions,"best_predictions":best_predictions}
    for f in range(5):paths[f"reference_inner_{f}"]=reference_dir/f"outer_{f:02}"/"inner_predictions_private.npz"
    for k,p in paths.items():
        if sha(p)!=fr["input_sha256"][k]:raise ValueError("input changed "+k)
    for rel,h in fr["source_sha256"].items():
        if sha(here.parent.parent/rel)!=h:raise ValueError("source changed "+rel)
    if output.exists():raise ValueError("Output exists")
    rz=np.load(paths["reference_predictions"],allow_pickle=False);az=np.load(bagged_predictions,allow_pickle=False);bz=np.load(ijbc_predictions,allow_pickle=False);bestz=np.load(best_predictions,allow_pickle=False)
    y=rz["y"];p=rz["patients"].astype(str);folds=rz["folds"];bw=rz["bandwidth07"];r13=rz["r13"];a=az["candidate"];b=bz["candidate"];best=bestz["candidate"]
    for name,z in (("bagged",az),("ijbc",bz),("best",bestz)):
        if not np.array_equal(z["y"],y) or not np.array_equal(z["patients"].astype(str),p) or not np.array_equal(z["folds"],folds):raise ValueError(name+" identity")
    if abs(metrics(bw,y,p,folds)["mse"]-EXPECTED_BW07)>1e-15 or abs(metrics(r13,y,p,folds)["mse"]-EXPECTED_R13)>1e-15:raise ValueError("control")
    if abs(metrics(best,y,p,folds)["mse"]-EXPECTED_BEST)>1e-15:raise ValueError("best control")
    rr=json.loads(paths["reference_result"].read_text(encoding="utf-8"));cand=np.empty_like(bw);records=[]
    for f in range(5):
        z=np.load(paths[f"reference_inner_{f}"],allow_pickle=False);oi=option_index(rr["selections"][f]["selected"]["bandwidth07"])
        pred=z["bandwidth07"][oi];contrasts,cbar,v,sigma2,norm2,alpha,scale=james_stein_calibrator(pred,z["y"],z["patients"].astype(str),z["folds"])
        te=np.flatnonzero(folds==f);cand[0,te]=a[0,te];cand[1,te]=b[1,te]-0.5*scale*cbar[None,:]
        records.append({"fold":f,"spectral_option":rr["selections"][f]["selected"]["bandwidth07"],
          "sigma2":sigma2,"contrast_norm2":norm2,"james_stein_alpha":alpha,"scale":scale,
          "mean_abs_contrast":float(np.mean(np.abs(cbar))),"contrast_fold_matrix":contrasts.tolist(),"contrast_mean":cbar.tolist(),"contrast_variance_of_mean":v.tolist()})
    output.mkdir(parents=True,exist_ok=False)
    np.savez_compressed(output/"predictions_private.npz",candidate=cand,bandwidth07=bw,r13=r13,best=best,bagged=a,interpolated_jackknife=b,y=y,patients=p,folds=folds,sample_ids=rz["sample_ids"],drug_ids=rz["drug_ids"])
    ci,cm,bm=compare(cand,bw,y,p,folds);cb,_,bestm=compare(cand,best,y,p,folds);c13,_,r13m=compare(cand,r13,y,p,folds)
    gate={"mse":ci["candidate_mse"]<ci["reference_mse"],"patients":ci["patient_wins"]>=30,"folds":ci["fold_wins"]==5,"p90":ci["p90_nonworse"],"beats_verified_best":cm["mse"]<bestm["mse"]}
    decision="NEW_BEST_PENDING_R18" if all(gate.values()) and c13["relative_gain"]>=.05 and c13["patient_wins"]>=40 and c13["fold_wins"]>=4 and c13["p90_nonworse"] else "REJECT"
    result={"schema":"dosepilot.james_stein_orientation_contrast.result.v1","status":"COMPLETE","role":"REPEATED_ADAPTIVE_DEVELOPMENT_NOT_INDEPENDENT_VALIDATION",
      "candidate":cm,"bandwidth07":bm,"verified_best":bestm,"r13":r13m,"candidate_vs_bandwidth07":dict(ci,gate=gate),"candidate_vs_verified_best":cb,"candidate_vs_r13":c13,
      "fold_records":records,"decision":decision,"prediction_sha256":sha(output/"predictions_private.npz"),"protected22_access":False,"independent_validation":False,"official_competition_score":None,"automatic_retry":False}
    write_new(output/"RESULT.json",result);print(json.dumps({"decision":decision,"candidate_mse":cm["mse"],"best_mse":bestm["mse"],"vs_bw07":ci,"vs_best":cb,"scales":[r["scale"] for r in records]},indent=2))
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--reference-dir",type=Path,required=True);ap.add_argument("--bagged-predictions",type=Path,required=True);ap.add_argument("--ijbc-predictions",type=Path,required=True);ap.add_argument("--best-predictions",type=Path,required=True);ap.add_argument("--output",type=Path,required=True);a=ap.parse_args();execute(a.reference_dir,a.bagged_predictions,a.ijbc_predictions,a.best_predictions,a.output)
if __name__=="__main__":main()
