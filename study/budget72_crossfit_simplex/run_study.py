#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
import numpy as np

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
EXPECTED_RAW=0.0010055928901387746
EXPECTED_BW=0.0009326007417880046
EXPECTED_CONTROL=0.00100352567955771
BOOTSTRAP_SEED=20261006
BOOTSTRAP_REPS=100000

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write_new(p,v):
    Path(p).write_text(json.dumps(v,indent=2,allow_nan=False)+"\n",encoding="utf-8",newline="\n")
def patient_weights(p):
    p=np.asarray(p,str)
    ids,inv,count=np.unique(p,return_inverse=True,return_counts=True)
    return 1.0/(len(ids)*count[inv])

def weighted_inner(a,b,w):
    return float(np.sum(w[None,:,None]*a*b))

def simplex_weights(y,p0,p1,p2,patients):
    w=patient_weights(patients)
    e0=p0-y[None,:,:]
    x1=p1-p0
    x2=p2-p0
    g11=weighted_inner(x1,x1,w)
    g22=weighted_inner(x2,x2,w)
    g12=weighted_inner(x1,x2,w)
    h1=weighted_inner(x1,e0,w)
    h2=weighted_inner(x2,e0,w)
    candidates=[]
    G=np.array([[g11,g12],[g12,g22]],float)
    h=np.array([h1,h2],float)
    if np.linalg.det(G)>1e-24:
        ab=-np.linalg.solve(G,h)
        a,b=float(ab[0]),float(ab[1])
        if a>=0 and b>=0 and a+b<=1:
            candidates.append(("interior",a,b))
    a=0.0 if g11<=1e-30 else float(np.clip(-h1/g11,0,1))
    candidates.append(("edge_raw_bw",a,0.0))
    b=0.0 if g22<=1e-30 else float(np.clip(-h2/g22,0,1))
    candidates.append(("edge_raw_control",0.0,b))
    d=x1-x2
    base=e0+x2
    den=weighted_inner(d,d,w)
    num=weighted_inner(d,base,w)
    a=0.0 if den<=1e-30 else float(np.clip(-num/den,0,1))
    candidates.append(("edge_bw_control",a,1.0-a))
    rows=[]
    for order,(name,a,b) in enumerate(candidates):
        e=e0+a*x1+b*x2
        loss=weighted_inner(e,e,w)
        rows.append({
          "name":name,"a_bandwidth":a,"b_control":b,
          "weights":[1.0-a-b,a,b],"weighted_sse":loss,"order":order})
    best=min(rows,key=lambda r:(r["weighted_sse"],r["order"]))
    weights=np.asarray(best["weights"],float)
    if (weights<-1e-12).any() or abs(weights.sum()-1)>1e-12:
        raise ValueError("simplex solver")
    return weights,best,rows

def patient_target_losses(y,a,b,patients):
    e=((a-y)**2+(b-y)**2)/2
    groups=np.unique(patients)
    return groups,np.stack([e[patients==g].mean(0) for g in groups])

def metrics(y,a,b,patients,folds):
    groups,pt=patient_target_losses(y,a,b,patients)
    per=pt.mean(1)
    pf=np.array([folds[np.flatnonzero(patients==g)[0]] for g in groups])
    return {
      "mse":float(per.mean()),
      "p90_patient_rmse":float(np.quantile(np.sqrt(per),0.9)),
      "fold_mse":[float(per[pf==f].mean()) for f in range(5)],
      "patient_losses":per,
      "target_mse":pt.mean(0)
    }

def check_freeze(raw_path,bw_path,control_path):
    fr=json.loads((HERE/"FREEZE.json").read_text(encoding="utf-8"))
    if fr["state"]!="FROZEN_BEFORE_CANDIDATE_OUTCOME":
        raise ValueError("freeze state")
    paths={"raw72":raw_path,"bandwidth72":bw_path,"control72":control_path}
    for k,p in paths.items():
        if sha(p)!=fr["input_sha256"][k]:
            raise ValueError("input changed "+k)
    for rel,h in fr["source_sha256"].items():
        if sha(REPO/rel)!=h:
            raise ValueError("source changed "+rel)
    return fr

def execute(raw_path,bw_path,control_path,output):
    fr=check_freeze(raw_path,bw_path,control_path)
    raw=np.load(raw_path,allow_pickle=False)
    bw=np.load(bw_path,allow_pickle=False)
    ctrl=np.load(control_path,allow_pickle=False)
    y=raw["y"]
    patients=raw["patients"].astype(str)
    folds=raw["folds"]
    for name,z in (("bandwidth",bw),("control",ctrl)):
        if not np.array_equal(z["y"],y) or not np.array_equal(z["patients"].astype(str),patients):
            raise ValueError(name+" identity")
        if not np.array_equal(z["folds"],folds):
            raise ValueError(name+" folds")
    p0A=raw["pred72_A"].copy();p0B=raw["pred72_B"].copy()
    p1A=bw["candidate_A"].copy();p1B=bw["candidate_B"].copy()
    p2A=ctrl["candidate_A"].copy();p2B=ctrl["candidate_B"].copy()
    m0=metrics(y,p0A,p0B,patients,folds)
    m1=metrics(y,p1A,p1B,patients,folds)
    m2=metrics(y,p2A,p2B,patients,folds)
    if abs(m0["mse"]-EXPECTED_RAW)>1e-15: raise ValueError("raw control")
    if abs(m1["mse"]-EXPECTED_BW)>1e-15: raise ValueError("bandwidth control")
    if abs(m2["mse"]-EXPECTED_CONTROL)>1e-15: raise ValueError("control control")
    candA=np.full_like(y,np.nan);candB=np.full_like(y,np.nan)
    records=[]
    for f in range(5):
        cal=folds!=f;te=folds==f
        weights,best,all_rows=simplex_weights(
          y[cal],
          np.stack([p0A[cal],p0B[cal]]),
          np.stack([p1A[cal],p1B[cal]]),
          np.stack([p2A[cal],p2B[cal]]),
          patients[cal])
        candA[te]=weights[0]*p0A[te]+weights[1]*p1A[te]+weights[2]*p2A[te]
        candB[te]=weights[0]*p0B[te]+weights[1]*p1B[te]+weights[2]*p2B[te]
        records.append({
          "fold":f,"weights":weights.tolist(),"active_solution":best,
          "all_active_set_candidates":all_rows,
          "calibration_patients":int(len(np.unique(patients[cal]))),
          "test_patients":int(len(np.unique(patients[te])))
        })
        print(json.dumps({"event":"outer_complete","fold":f,
                          "weights":weights.tolist(),"solution":best["name"]}),flush=True)
    if not np.isfinite(candA).all() or not np.isfinite(candB).all():
        raise AssertionError("simplex OOF incomplete")
    deploy_weights,deploy_best,deploy_rows=simplex_weights(
      y,np.stack([p0A,p0B]),np.stack([p1A,p1B]),np.stack([p2A,p2B]),patients)
    cm=metrics(y,candA,candB,patients,folds)
    pdiff=cm["patient_losses"]-m1["patient_losses"]
    tdiff=cm["target_mse"]-m1["target_mse"]
    rng=np.random.default_rng(BOOTSTRAP_SEED)
    idx=rng.integers(0,len(pdiff),size=(BOOTSTRAP_REPS,len(pdiff)))
    boot=pdiff[idx].mean(1)
    comp_bw={
      "relative_mse_gain":float(1-cm["mse"]/m1["mse"]),
      "patient_wins":int((pdiff<0).sum()),
      "patient_losses":int((pdiff>0).sum()),
      "fold_wins":int(sum(a<b for a,b in zip(cm["fold_mse"],m1["fold_mse"]))),
      "target_wins":int((tdiff<-1e-15).sum()),
      "target_regressions":int((tdiff>1e-15).sum()),
      "p90_nonworse":bool(cm["p90_patient_rmse"]<=m1["p90_patient_rmse"]),
      "bootstrap_percentile_95_ci":[float(np.quantile(boot,.025)),float(np.quantile(boot,.975))],
      "bootstrap_fraction_below_zero":float((boot<0).mean())
    }
    d0=cm["patient_losses"]-m0["patient_losses"]
    comp_raw={
      "relative_mse_gain":float(1-cm["mse"]/m0["mse"]),
      "patient_wins":int((d0<0).sum()),"patient_losses":int((d0>0).sum()),
      "fold_wins":int(sum(a<b for a,b in zip(cm["fold_mse"],m0["fold_mse"]))),
      "p90_nonworse":bool(cm["p90_patient_rmse"]<=m0["p90_patient_rmse"])
    }
    d2=cm["patient_losses"]-m2["patient_losses"]
    comp_control={
      "relative_mse_gain":float(1-cm["mse"]/m2["mse"]),
      "patient_wins":int((d2<0).sum()),"patient_losses":int((d2>0).sum()),
      "fold_wins":int(sum(a<b for a,b in zip(cm["fold_mse"],m2["fold_mse"]))),
      "p90_nonworse":bool(cm["p90_patient_rmse"]<=m2["p90_patient_rmse"])
    }
    gate={
      "mse":cm["mse"]<m1["mse"],
      "patients":comp_bw["patient_wins"]>=30,
      "folds":comp_bw["fold_wins"]==5,
      "p90":comp_bw["p90_nonworse"],
      "treatment_wells":True
    }
    decision="SIMPLEX_SUCCESSOR" if all(gate.values()) else "REJECT_SIMPLEX"
    output=Path(output)
    if output.exists(): raise ValueError("output exists")
    output.mkdir(parents=True,exist_ok=False)
    np.savez_compressed(
      output/"predictions_private.npz",
      candidate_A=candA,candidate_B=candB,
      raw_A=p0A,raw_B=p0B,bandwidth_A=p1A,bandwidth_B=p1B,
      control_A=p2A,control_B=p2B,
      y=y,patients=patients,folds=folds,
      sample_ids=raw["sample_ids"],drug_ids=raw["drug_ids"])
    result={
      "schema":"dosepilot.budget72_crossfit_simplex.result.v1",
      "status":"COMPLETE",
      "role":"FROZEN_CROSSFIT_GLOBAL_SIMPLEX_STACK",
      "candidate":{"mse":cm["mse"],"p90_patient_rmse":cm["p90_patient_rmse"],
                   "fold_mse":cm["fold_mse"]},
      "raw72":{"mse":m0["mse"],"p90_patient_rmse":m0["p90_patient_rmse"],
               "fold_mse":m0["fold_mse"]},
      "bandwidth72":{"mse":m1["mse"],"p90_patient_rmse":m1["p90_patient_rmse"],
                     "fold_mse":m1["fold_mse"]},
      "control72":{"mse":m2["mse"],"p90_patient_rmse":m2["p90_patient_rmse"],
                   "fold_mse":m2["fold_mse"]},
      "candidate_vs_bandwidth72":dict(comp_bw,gate=gate),
      "candidate_vs_raw72":comp_raw,
      "candidate_vs_control72":comp_control,
      "weights_by_outer_fold":records,
      "deployment_preparation":{
        "weights":deploy_weights.tolist(),
        "active_solution":deploy_best,
        "all_active_set_candidates":deploy_rows
      },
      "treatment_wells":72,
      "standard_controls_extra_treatment_wells":0,
      "decision":decision,
      "prediction_sha256":sha(output/"predictions_private.npz"),
      "input_sha256":fr["input_sha256"],
      "source_sha256":fr["source_sha256"],
      "target_specific_weights":False,
      "orientation_specific_weights":False,
      "protected22_access":False,
      "independent_validation":False,
      "automatic_retry":False
    }
    write_new(output/"RESULT.json",result)
    print(json.dumps({"decision":decision,"candidate":result["candidate"],
      "vs_bandwidth72":result["candidate_vs_bandwidth72"],
      "weights":[r["weights"] for r in records],
      "deployment_weights":deploy_weights.tolist()},indent=2))
    return result

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--raw72",type=Path,required=True)
    ap.add_argument("--bandwidth72",type=Path,required=True)
    ap.add_argument("--control72",type=Path,required=True)
    ap.add_argument("--output",type=Path,required=True)
    a=ap.parse_args()
    execute(a.raw72,a.bandwidth72,a.control72,a.output)

if __name__=="__main__":
    main()
