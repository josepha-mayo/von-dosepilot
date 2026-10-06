#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
import numpy as np

PRIOR=0.125
TARGETS=24
GAIN_MIN=1.0
GAIN_MAX=3.0
HEDGE=0.5
OPTIONS=[("identity",0.0)]+[(f,l) for f in (0.1,0.3,0.6) for l in (0.1,1.0,10.0)]
EXPECTED_BW07=0.0010582750420801538
EXPECTED_R13=0.0011448586813828537
EXPECTED_BEST=0.0010562461582277344

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
    raise ValueError("unknown spectral option")
def fold_stats(pred,y,p,inner):
    contrasts=[];b_residual=[];counts=[]
    for k in range(3):
        mask=inner==k;groups=np.unique(p[mask]);counts.append(len(groups))
        res=np.stack([np.stack([(y[(p==g)&mask]-pred[o,(p==g)&mask]).mean(0) for g in groups]).mean(0) for o in (0,1)])
        contrasts.append(res[0]-res[1]);b_residual.append(res[1])
    return np.stack(contrasts),np.stack(b_residual),np.asarray(counts,float)
def weighted_mean_variance(values,counts):
    values=np.asarray(values,float);counts=np.asarray(counts,float)
    if values.ndim!=2 or counts.shape!=(len(values),) or len(values)<2 or not np.isfinite(values).all() or not np.isfinite(counts).all() or (counts<=0).any():
        raise ValueError("invalid weighted fold estimates")
    total=float(counts.sum());mean=np.sum(counts[:,None]*values,axis=0)/total
    sigma2=np.sum(counts[:,None]*(values-mean)**2,axis=0)/(len(values)-1)
    return mean,sigma2/total
def theta_and_prior_gain(contrasts,counts):
    cbar,v=weighted_mean_variance(contrasts,counts)
    sigma2=float(v.mean());norm2=float(np.sum(cbar*cbar))
    ag=0.0 if norm2<=1e-30 else max(0.0,1.0-(TARGETS-2)*sigma2/norm2)
    theta_global=(PRIOR+(1-PRIOR)*ag)*cbar
    mk=contrasts.mean(1)[:,None];mu_vec,vmu_vec=weighted_mean_variance(mk,counts);mu=float(mu_vec[0]);vmu=float(vmu_vec[0])
    ac=0.0 if mu*mu<=1e-30 else max(0.0,1.0-vmu/(mu*mu))
    dev=contrasts-mk;dbar,vdev=weighted_mean_variance(dev,counts);noise=float(vdev.mean());dnorm=float(np.sum(dbar*dbar))
    ad=0.0 if dnorm<=1e-30 else max(0.0,1.0-(TARGETS-3)*noise/dnorm)
    theta_hier=PRIOR*cbar+(1-PRIOR)*(ac*mu+ad*dbar)
    target_rel=np.zeros_like(dbar);stable=dbar*dbar>1e-30
    target_rel[stable]=np.maximum(0.0,1.0-vdev[stable]/(dbar[stable]*dbar[stable]))
    amp_rel=np.sqrt(target_rel);w=np.minimum(1.0,amp_rel+ac+ag)
    theta=theta_global+w*(theta_hier-theta_global)
    c_union=1.0-(1.0-ag)*(1.0-ac)
    prior_gain=1.0+c_union*amp_rel
    meta={"global_alpha":float(ag),"common_alpha":float(ac),"deviation_alpha":float(ad),
          "target_amplitude_reliability":amp_rel,"confidence_union":float(c_union),
          "hierarchical_weight":w,"prior_gain":prior_gain}
    return theta,prior_gain,meta
def fit_bounded_gain(theta_rows,b_residual,counts):
    theta_rows=np.asarray(theta_rows,float);b_residual=np.asarray(b_residual,float);counts=np.asarray(counts,float)
    den=np.sum(counts[:,None]*theta_rows*theta_rows,axis=0)
    num=-2.0*np.sum(counts[:,None]*theta_rows*b_residual,axis=0)
    raw=np.divide(num,den,out=np.ones(TARGETS),where=den>1e-30)
    return np.clip(raw,GAIN_MIN,GAIN_MAX),raw
def gain_details(contrasts,b_residual,counts,prior_gain):
    held_theta=[]
    for k in range(3):
        keep=np.asarray([j for j in range(3) if j!=k])
        t,_,_=theta_and_prior_gain(contrasts[keep],counts[keep]);held_theta.append(t)
    held_theta=np.stack(held_theta)
    graw,raw_unbounded=fit_bounded_gain(held_theta,b_residual,counts)
    jk=[]
    for k in range(3):
        keep=np.asarray([j for j in range(3) if j!=k])
        g,_=fit_bounded_gain(held_theta[keep],b_residual[keep],counts[keep]);jk.append(g)
    jk=np.stack(jk);gbar=jk.mean(0)
    variance=(len(jk)-1)/len(jk)*np.sum((jk-gbar)**2,axis=0)
    delta=graw-prior_gain
    reliability=np.divide(delta*delta,delta*delta+variance,out=np.zeros_like(delta),where=(delta*delta+variance)>1e-30)
    stabilized=prior_gain+reliability*delta
    final_gain=HEDGE*stabilized+(1-HEDGE)*graw
    return final_gain,{"held_theta":held_theta,"raw_unbounded_gain":raw_unbounded,"raw_gain":graw,
      "jackknife_gain_matrix":jk,"jackknife_variance":variance,"reliability":reliability,
      "stabilized_gain":stabilized,"final_gain":final_gain}

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
        z=np.load(paths[f"reference_inner_{f}"],allow_pickle=False);sel=rr["selections"][f]["selected"]["bandwidth07"];oi=option_index(sel)
        pred=z["bandwidth07"][oi];cs,rb,counts=fold_stats(pred,z["y"],z["patients"].astype(str),z["folds"])
        theta,prior_gain,meta=theta_and_prior_gain(cs,counts);gain,gm=gain_details(cs,rb,counts,prior_gain);te=np.flatnonzero(folds==f)
        cand[0,te]=a[0,te];cand[1,te]=b[1,te]-0.5*(gain*theta)[None,:]
        records.append({"fold":f,"spectral_option":sel,"inner_patient_counts":counts.astype(int).tolist(),
          "global_alpha":meta["global_alpha"],"common_alpha":meta["common_alpha"],"deviation_alpha":meta["deviation_alpha"],
          "theta_full":theta.tolist(),"prior_gain":prior_gain.tolist(),"raw_gain":gm["raw_gain"].tolist(),
          "raw_unbounded_gain":gm["raw_unbounded_gain"].tolist(),"jackknife_gain_matrix":gm["jackknife_gain_matrix"].tolist(),
          "jackknife_variance":gm["jackknife_variance"].tolist(),"reliability":gm["reliability"].tolist(),
          "stabilized_gain":gm["stabilized_gain"].tolist(),"final_gain":gain.tolist(),
          "gain_min":float(gain.min()),"gain_median":float(np.median(gain)),"gain_max":float(gain.max())})
    output.mkdir(parents=True,exist_ok=False)
    np.savez_compressed(output/"predictions_private.npz",candidate=cand,bandwidth07=bw,r13=r13,best=best,bagged=a,interpolated_jackknife=b,y=y,patients=p,folds=folds,sample_ids=rz["sample_ids"],drug_ids=rz["drug_ids"])
    ci,cm,bm=compare(cand,bw,y,p,folds);cb,_,bestm=compare(cand,best,y,p,folds);c13,_,r13m=compare(cand,r13,y,p,folds)
    gate={"mse":ci["candidate_mse"]<ci["reference_mse"],"patients":ci["patient_wins"]>=30,"folds":ci["fold_wins"]==5,"p90":ci["p90_nonworse"],"beats_verified_best":cm["mse"]<bestm["mse"]}
    decision="NEW_BEST_PENDING_R18" if all(gate.values()) and c13["relative_gain"]>=.05 and c13["patient_wins"]>=40 and c13["fold_wins"]>=4 and c13["p90_nonworse"] else "REJECT"
    result={"schema":"dosepilot.half_raw_jackknife_gain_hedge.result.v1","status":"COMPLETE","role":"REPEATED_ADAPTIVE_DEVELOPMENT_NOT_INDEPENDENT_VALIDATION",
      "gain_hedge_weight_stabilized":HEDGE,"gain_hedge_weight_raw":1-HEDGE,
      "candidate":cm,"bandwidth07":bm,"verified_best":bestm,"r13":r13m,"candidate_vs_bandwidth07":dict(ci,gate=gate),"candidate_vs_verified_best":cb,"candidate_vs_r13":c13,
      "fold_records":records,"decision":decision,"prediction_sha256":sha(output/"predictions_private.npz"),"protected22_access":False,"independent_validation":False,"official_competition_score":None,"automatic_retry":False}
    write_new(output/"RESULT.json",result);print(json.dumps({"decision":decision,"candidate_mse":cm["mse"],"best_mse":bestm["mse"],"vs_bw07":ci,"vs_best":cb,
      "gain_summaries":[[r["gain_min"],r["gain_median"],r["gain_max"]] for r in records]},indent=2))
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--reference-dir",type=Path,required=True);ap.add_argument("--bagged-predictions",type=Path,required=True);ap.add_argument("--ijbc-predictions",type=Path,required=True);ap.add_argument("--best-predictions",type=Path,required=True);ap.add_argument("--output",type=Path,required=True);a=ap.parse_args()
    execute(a.reference_dir,a.bagged_predictions,a.ijbc_predictions,a.best_predictions,a.output)
if __name__=="__main__":main()
