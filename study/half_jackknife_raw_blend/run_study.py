#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
import numpy as np
W=0.5
EXPECTED_BW07=0.0010582750420801538
EXPECTED_R13=0.0011448586813828537
EXPECTED_BEST=0.0010574998492009094
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
def execute(reference,jbc,raw,out):
    here=Path(__file__).resolve().parent;fr=json.loads((here/"FREEZE.json").read_text(encoding="utf-8"))
    for k,p in {"reference":reference,"jbc":jbc,"raw":raw}.items():
        if sha(p)!=fr["input_sha256"][k]:raise ValueError("input changed "+k)
    for rel,h in fr["source_sha256"].items():
        if sha(here.parent.parent/rel)!=h:raise ValueError("source changed "+rel)
    if out.exists():raise ValueError("Output exists")
    rz=np.load(reference,allow_pickle=False);jz=np.load(jbc,allow_pickle=False);xz=np.load(raw,allow_pickle=False)
    y=rz["y"];p=rz["patients"].astype(str);folds=rz["folds"];bw=rz["bandwidth07"];r13=rz["r13"];best=jz["candidate"];x=xz["candidate"]
    for name,z in (("jbc",jz),("raw",xz)):
        if not np.array_equal(z["y"],y) or not np.array_equal(z["patients"].astype(str),p) or not np.array_equal(z["folds"],folds):raise ValueError(name+" identity")
    if abs(metrics(bw,y,p,folds)["mse"]-EXPECTED_BW07)>1e-15:raise ValueError("bw control")
    if abs(metrics(r13,y,p,folds)["mse"]-EXPECTED_R13)>1e-15:raise ValueError("r13 control")
    if abs(metrics(best,y,p,folds)["mse"]-EXPECTED_BEST)>1e-15:raise ValueError("best control")
    cand=W*best+(1-W)*x
    out.mkdir(parents=True,exist_ok=False)
    np.savez_compressed(out/"predictions_private.npz",candidate=cand,bandwidth07=bw,r13=r13,best=best,raw=x,y=y,patients=p,folds=folds,sample_ids=rz["sample_ids"],drug_ids=rz["drug_ids"])
    ci,cm,bm=compare(cand,bw,y,p,folds);cb,_,bestm=compare(cand,best,y,p,folds);c13,_,r13m=compare(cand,r13,y,p,folds)
    gate={"mse":ci["candidate_mse"]<ci["reference_mse"],"patients":ci["patient_wins"]>=30,"folds":ci["fold_wins"]==5,"p90":ci["p90_nonworse"],"beats_verified_best":cm["mse"]<bestm["mse"]}
    decision="NEW_BEST_PENDING_R18" if all(gate.values()) and c13["relative_gain"]>=.05 and c13["patient_wins"]>=40 and c13["fold_wins"]>=4 and c13["p90_nonworse"] else "REJECT"
    res={"schema":"dosepilot.half_jackknife_raw_blend.result.v1","status":"COMPLETE","role":"REPEATED_ADAPTIVE_DEVELOPMENT_NOT_INDEPENDENT_VALIDATION","fixed_weight_jackknife":W,
      "candidate":cm,"bandwidth07":bm,"verified_best":bestm,"r13":r13m,"candidate_vs_bandwidth07":dict(ci,gate=gate),"candidate_vs_verified_best":cb,"candidate_vs_r13":c13,
      "decision":decision,"prediction_sha256":sha(out/"predictions_private.npz"),"protected22_access":False,"independent_validation":False,"official_competition_score":None,"automatic_retry":False}
    write_new(out/"RESULT.json",res);print(json.dumps({"decision":decision,"candidate_mse":cm["mse"],"best_mse":bestm["mse"],"vs_bw07":ci,"vs_best":cb},indent=2))
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--reference",type=Path,required=True);ap.add_argument("--jbc",type=Path,required=True);ap.add_argument("--raw",type=Path,required=True);ap.add_argument("--output",type=Path,required=True);a=ap.parse_args();execute(a.reference,a.jbc,a.raw,a.output)
if __name__=="__main__":main()
