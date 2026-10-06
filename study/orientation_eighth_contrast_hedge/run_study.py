#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
import numpy as np
T=0.125
EXPECTED_BW07=0.0010582750420801538
EXPECTED_R13=0.0011448586813828537
EXPECTED_BEST=0.0010574493498268901
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
def execute(reference,loo,ijbc,jbc,ocontrast,bestp,out):
    here=Path(__file__).resolve().parent;fr=json.loads((here/"FREEZE.json").read_text(encoding="utf-8"))
    paths={"reference":reference,"loo":loo,"ijbc":ijbc,"jbc":jbc,"ocontrast":ocontrast,"best":bestp}
    for k,p in paths.items():
        if sha(p)!=fr["input_sha256"][k]:raise ValueError("input changed "+k)
    for rel,h in fr["source_sha256"].items():
        if sha(here.parent.parent/rel)!=h:raise ValueError("source changed "+rel)
    if out.exists():raise ValueError("Output exists")
    rz=np.load(reference,allow_pickle=False);lz=np.load(loo,allow_pickle=False);iz=np.load(ijbc,allow_pickle=False);jz=np.load(jbc,allow_pickle=False);oz=np.load(ocontrast,allow_pickle=False);bz=np.load(bestp,allow_pickle=False)
    y=rz["y"];p=rz["patients"].astype(str);folds=rz["folds"];bw=rz["bandwidth07"];r13=rz["r13"];a=lz["candidate"];ib=iz["candidate"];jb=jz["candidate"];oc=oz["candidate"];best=bz["candidate"]
    for name,z in (("loo",lz),("ijbc",iz),("jbc",jz),("ocontrast",oz),("best",bz)):
        if not np.array_equal(z["y"],y) or not np.array_equal(z["patients"].astype(str),p) or not np.array_equal(z["folds"],folds):raise ValueError(name+" identity")
    if abs(metrics(bw,y,p,folds)["mse"]-EXPECTED_BW07)>1e-15 or abs(metrics(r13,y,p,folds)["mse"]-EXPECTED_R13)>1e-15:raise ValueError("control")
    if abs(metrics(best,y,p,folds)["mse"]-EXPECTED_BEST)>1e-15:raise ValueError("best control")
    delta_b=oc[1]-jb[1]
    cand=np.empty_like(a);cand[0]=a[0];cand[1]=ib[1]+T*delta_b
    out.mkdir(parents=True,exist_ok=False)
    np.savez_compressed(out/"predictions_private.npz",candidate=cand,bandwidth07=bw,r13=r13,best=best,loo=a,interpolated_jackknife=ib,jackknife=jb,orientation_contrast=oc,y=y,patients=p,folds=folds,sample_ids=rz["sample_ids"],drug_ids=rz["drug_ids"])
    ci,cm,bm=compare(cand,bw,y,p,folds);cb,_,bestm=compare(cand,best,y,p,folds);c13,_,r13m=compare(cand,r13,y,p,folds)
    gate={"mse":ci["candidate_mse"]<ci["reference_mse"],"patients":ci["patient_wins"]>=30,"folds":ci["fold_wins"]==5,"p90":ci["p90_nonworse"],"beats_verified_best":cm["mse"]<bestm["mse"]}
    decision="NEW_BEST_PENDING_R18" if all(gate.values()) and c13["relative_gain"]>=.05 and c13["patient_wins"]>=40 and c13["fold_wins"]>=4 and c13["p90_nonworse"] else "REJECT"
    res={"schema":"dosepilot.orientation_eighth_contrast_hedge.result.v1","status":"COMPLETE","role":"REPEATED_ADAPTIVE_DEVELOPMENT_NOT_INDEPENDENT_VALIDATION",
      "orientation_A_component":"loo_bagged","orientation_B_component":"interpolated_jackknife_plus_eighth_pure_contrast","contrast_scale":T,
      "candidate":cm,"bandwidth07":bm,"verified_best":bestm,"r13":r13m,"candidate_vs_bandwidth07":dict(ci,gate=gate),"candidate_vs_verified_best":cb,"candidate_vs_r13":c13,
      "decision":decision,"prediction_sha256":sha(out/"predictions_private.npz"),"protected22_access":False,"independent_validation":False,"official_competition_score":None,"automatic_retry":False}
    write_new(out/"RESULT.json",res);print(json.dumps({"decision":decision,"candidate_mse":cm["mse"],"best_mse":bestm["mse"],"vs_bw07":ci,"vs_best":cb,"orientation_mse":cm["orientation_mse"]},indent=2))
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--reference",type=Path,required=True);ap.add_argument("--loo",type=Path,required=True);ap.add_argument("--ijbc",type=Path,required=True);ap.add_argument("--jbc",type=Path,required=True);ap.add_argument("--ocontrast",type=Path,required=True);ap.add_argument("--best",type=Path,required=True);ap.add_argument("--output",type=Path,required=True);a=ap.parse_args();execute(a.reference,a.loo,a.ijbc,a.jbc,a.ocontrast,a.best,a.output)
if __name__=="__main__":main()
