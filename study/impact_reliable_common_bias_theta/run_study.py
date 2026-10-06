#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
import numpy as np

PRIOR=0.125
TARGETS=24
GAIN_MIN=1.0
APPLY_GAIN_MIN=1.0-PRIOR
GAIN_MAX=3.0
A_GAIN_MIN=-(1.0-PRIOR)
A_GAIN_MAX=0.5
OPTIONS=[("identity",0.0)]+[(f,l) for f in (0.1,0.3,0.6) for l in (0.1,1.0,10.0)]
EXPECTED_BW07=0.0010582750420801538
EXPECTED_R13=0.0011448586813828537
EXPECTED_BEST=0.001055276279070899

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
    contrasts=[];a_residual=[];b_residual=[];counts=[]
    for k in range(3):
        mask=inner==k;groups=np.unique(p[mask]);counts.append(len(groups))
        res=np.stack([np.stack([(y[(p==g)&mask]-pred[o,(p==g)&mask]).mean(0) for g in groups]).mean(0) for o in (0,1)])
        contrasts.append(res[0]-res[1]);a_residual.append(res[0]);b_residual.append(res[1])
    return np.stack(contrasts),np.stack(a_residual),np.stack(b_residual),np.asarray(counts,float)
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
    base_alpha=0.5+0.5*np.sqrt(reliability)
    local_gain=np.divide(-2.0*b_residual,held_theta,out=np.ones_like(b_residual),where=np.abs(held_theta)>1e-12)
    unanimous=np.all(local_gain>1.0,axis=0)
    fallback_alpha=np.where(unanimous,1.0,base_alpha)
    fallback_gain=prior_gain+fallback_alpha*delta
    norm2=float(np.sum(delta*delta))
    global_reliability=0.0 if norm2<=1e-30 else max(0.0,1.0-(TARGETS-2)*float(np.mean(variance))/norm2)
    use_raw=global_reliability>0.0
    applied_raw=np.clip(raw_unbounded,APPLY_GAIN_MIN,GAIN_MAX)
    alpha=np.ones_like(delta) if use_raw else fallback_alpha
    final_gain=applied_raw.copy() if use_raw else fallback_gain
    return final_gain,{"held_theta":held_theta,"raw_unbounded_gain":raw_unbounded,"raw_gain":graw,
      "applied_raw_gain":applied_raw,
      "jackknife_gain_matrix":jk,"jackknife_variance":variance,"reliability":reliability,
      "base_alpha":base_alpha,"local_gain_matrix":local_gain,"unanimous_positive":unanimous,
      "fallback_alpha":fallback_alpha,"fallback_gain":fallback_gain,
      "global_reliability":float(global_reliability),"use_raw":bool(use_raw),
      "alpha":alpha,"final_gain":final_gain}

def fit_bounded_A_gain(theta_rows,a_residual,counts):
    theta_rows=np.asarray(theta_rows,float);a_residual=np.asarray(a_residual,float);counts=np.asarray(counts,float)
    den=np.sum(counts[:,None]*theta_rows*theta_rows,axis=0)
    num=2.0*np.sum(counts[:,None]*theta_rows*a_residual,axis=0)
    raw=np.divide(num,den,out=np.zeros(TARGETS),where=den>1e-30)
    return np.clip(raw,A_GAIN_MIN,A_GAIN_MAX),raw
def A_gain_details(held_theta,a_residual,counts):
    graw,raw_unbounded=fit_bounded_A_gain(held_theta,a_residual,counts)
    jk=[]
    for k in range(3):
        keep=np.asarray([j for j in range(3) if j!=k])
        g,_=fit_bounded_A_gain(held_theta[keep],a_residual[keep],counts[keep]);jk.append(g)
    jk=np.stack(jk);gbar=jk.mean(0)
    variance=(len(jk)-1)/len(jk)*np.sum((jk-gbar)**2,axis=0)
    reliability=np.divide(graw*graw,graw*graw+variance,out=np.zeros_like(graw),where=(graw*graw+variance)>1e-30)
    norm2=float(np.sum(graw*graw))
    global_reliability=0.0 if norm2<=1e-30 else max(0.0,1.0-(TARGETS-2)*float(np.mean(variance))/norm2)
    use_gain=global_reliability>0.0
    local_gain=np.divide(2.0*a_residual,held_theta,out=np.zeros_like(a_residual),where=np.abs(held_theta)>1e-12)
    sign_match=(np.sign(local_gain)==np.sign(graw)[None,:])
    vote_count=sign_match.sum(axis=0)
    eligible=(vote_count>=2)&(graw!=0.0)&(reliability>=0.5)
    base_confirmation=reliability**3
    vote_boost=np.where(vote_count==3,1.0,np.where(vote_count==2,0.5,0.0))
    confirmation_reliability=base_confirmation+(1.0-base_confirmation)*np.where(eligible,vote_boost,0.0)
    final_gain=confirmation_reliability*graw if use_gain else np.zeros_like(graw)
    return final_gain,{"raw_unbounded_gain":raw_unbounded,"raw_gain":graw,"jackknife_gain_matrix":jk,
      "jackknife_variance":variance,"reliability":reliability,"local_gain_matrix":local_gain,
      "sign_match_matrix":sign_match,"vote_count":vote_count,"eligible":eligible,"vote_boost":vote_boost,
      "base_confirmation_reliability":base_confirmation,"confirmation_reliability":confirmation_reliability,
      "global_reliability":float(global_reliability),"use_gain":bool(use_gain),"final_gain":final_gain}

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
        pred=z["bandwidth07"][oi];cs,ra,rb,counts=fold_stats(pred,z["y"],z["patients"].astype(str),z["folds"])
        theta,prior_gain,meta=theta_and_prior_gain(cs,counts);gain,gm=gain_details(cs,rb,counts,prior_gain)
        a_gain,am=A_gain_details(gm["held_theta"],ra,counts)
        theta_loo_mean=gm["held_theta"].mean(axis=0)
        theta_bias=theta-theta_loo_mean
        theta_jackknife_variance=(len(gm["held_theta"])-1)/len(gm["held_theta"])*np.sum((gm["held_theta"]-theta_loo_mean)**2,axis=0)
        theta_variance_reliability=np.divide(theta_bias*theta_bias,theta_bias*theta_bias+theta_jackknife_variance,out=np.zeros_like(theta_bias),where=(theta_bias*theta_bias+theta_jackknife_variance)>1e-30)
        theta_A_confidence=theta_variance_reliability
        theta_A_bias_multiplier=1.0+theta_A_confidence
        theta_common_weights=gain*gain*theta_variance_reliability
        theta_common_weight_sum=float(np.sum(theta_common_weights))
        theta_common_bias=0.0 if theta_common_weight_sum<=1e-30 else float(np.sum(theta_common_weights*theta_bias)/theta_common_weight_sum)
        theta_A_deploy=theta+theta_A_bias_multiplier*theta_bias
        theta_B_deploy=theta+theta_bias+theta_common_bias
        te=np.flatnonzero(folds==f)
        cand[0,te]=a[0,te]+0.5*(a_gain*theta_A_deploy)[None,:];cand[1,te]=b[1,te]-0.5*(gain*theta_B_deploy)[None,:]
        records.append({"fold":f,"spectral_option":sel,"inner_patient_counts":counts.astype(int).tolist(),
          "global_alpha":meta["global_alpha"],"common_alpha":meta["common_alpha"],"deviation_alpha":meta["deviation_alpha"],
          "theta_full":theta.tolist(),"theta_loo_mean":theta_loo_mean.tolist(),"theta_bias":theta_bias.tolist(),
          "theta_jackknife_variance":theta_jackknife_variance.tolist(),"theta_variance_reliability":theta_variance_reliability.tolist(),
          "theta_A_confidence":theta_A_confidence.tolist(),"theta_A_bias_multiplier":theta_A_bias_multiplier.tolist(),
          "theta_common_weights":theta_common_weights.tolist(),"theta_common_weight_sum":theta_common_weight_sum,
          "theta_common_bias":theta_common_bias,"theta_A_deploy":theta_A_deploy.tolist(),"theta_B_deploy":theta_B_deploy.tolist(),
          "prior_gain":prior_gain.tolist(),"raw_gain":gm["raw_gain"].tolist(),
          "raw_unbounded_gain":gm["raw_unbounded_gain"].tolist(),"applied_raw_gain":gm["applied_raw_gain"].tolist(),"jackknife_gain_matrix":gm["jackknife_gain_matrix"].tolist(),
          "jackknife_variance":gm["jackknife_variance"].tolist(),"reliability":gm["reliability"].tolist(),
          "base_alpha":gm["base_alpha"].tolist(),"local_gain_matrix":gm["local_gain_matrix"].tolist(),
          "unanimous_positive":gm["unanimous_positive"].astype(bool).tolist(),"fallback_alpha":gm["fallback_alpha"].tolist(),"fallback_gain":gm["fallback_gain"].tolist(),"global_reliability":gm["global_reliability"],"use_raw":gm["use_raw"],"alpha":gm["alpha"].tolist(),
          "final_gain":gain.tolist(),"unanimous_count":int(gm["unanimous_positive"].sum()),
          "gain_min":float(gain.min()),"gain_median":float(np.median(gain)),"gain_max":float(gain.max()),
          "A_residual_fold_matrix":ra.tolist(),"A_raw_unbounded_gain":am["raw_unbounded_gain"].tolist(),
          "A_raw_gain":am["raw_gain"].tolist(),"A_jackknife_gain_matrix":am["jackknife_gain_matrix"].tolist(),
           "A_jackknife_variance":am["jackknife_variance"].tolist(),"A_reliability":am["reliability"].tolist(),
          "A_local_gain_matrix":am["local_gain_matrix"].tolist(),"A_sign_match_matrix":am["sign_match_matrix"].astype(bool).tolist(),
          "A_vote_count":am["vote_count"].astype(int).tolist(),"A_eligible":am["eligible"].astype(bool).tolist(),"A_vote_boost":am["vote_boost"].tolist(),
          "A_eligible_count":int(am["eligible"].sum()),
          "A_base_confirmation_reliability":am["base_confirmation_reliability"].tolist(),"A_confirmation_reliability":am["confirmation_reliability"].tolist(),
          "A_global_reliability":am["global_reliability"],"A_use_gain":am["use_gain"],"A_final_gain":a_gain.tolist(),
          "A_gain_min":float(a_gain.min()),"A_gain_median":float(np.median(a_gain)),"A_gain_max":float(a_gain.max())})
    output.mkdir(parents=True,exist_ok=False)
    np.savez_compressed(output/"predictions_private.npz",candidate=cand,bandwidth07=bw,r13=r13,best=best,bagged=a,interpolated_jackknife=b,y=y,patients=p,folds=folds,sample_ids=rz["sample_ids"],drug_ids=rz["drug_ids"])
    ci,cm,bm=compare(cand,bw,y,p,folds);cb,_,bestm=compare(cand,best,y,p,folds);c13,_,r13m=compare(cand,r13,y,p,folds)
    gate={"mse":ci["candidate_mse"]<ci["reference_mse"],"patients":ci["patient_wins"]>=30,"folds":ci["fold_wins"]==5,"p90":ci["p90_nonworse"],"beats_verified_best":cm["mse"]<bestm["mse"]}
    decision="NEW_BEST_PENDING_R18" if all(gate.values()) and c13["relative_gain"]>=.05 and c13["patient_wins"]>=40 and c13["fold_wins"]>=4 and c13["p90_nonworse"] else "REJECT"
    result={"schema":"dosepilot.impact_reliable_common_bias_theta.result.v1","status":"COMPLETE","role":"REPEATED_ADAPTIVE_DEVELOPMENT_NOT_INDEPENDENT_VALIDATION",
      "candidate":cm,"bandwidth07":bm,"verified_best":bestm,"r13":r13m,"candidate_vs_bandwidth07":dict(ci,gate=gate),"candidate_vs_verified_best":cb,"candidate_vs_r13":c13,
      "fold_records":records,"decision":decision,"prediction_sha256":sha(output/"predictions_private.npz"),"protected22_access":False,"independent_validation":False,"official_competition_score":None,"automatic_retry":False}
    write_new(output/"RESULT.json",result);print(json.dumps({"decision":decision,"candidate_mse":cm["mse"],"best_mse":bestm["mse"],"vs_bw07":ci,"vs_best":cb,
      "B_global_reliability":[r["global_reliability"] for r in records],"B_use_raw":[r["use_raw"] for r in records],"A_global_reliability":[r["A_global_reliability"] for r in records],"A_use_gain":[r["A_use_gain"] for r in records]},indent=2))
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--reference-dir",type=Path,required=True);ap.add_argument("--bagged-predictions",type=Path,required=True);ap.add_argument("--ijbc-predictions",type=Path,required=True);ap.add_argument("--best-predictions",type=Path,required=True);ap.add_argument("--output",type=Path,required=True);a=ap.parse_args()
    execute(a.reference_dir,a.bagged_predictions,a.ijbc_predictions,a.best_predictions,a.output)
if __name__=="__main__":main()
