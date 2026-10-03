#!/usr/bin/env python3
"""Reproduce the response-free local-bandwidth candidate from public TRAIN.

No historical predictions, protected responses, or private metadata kit are inputs.
Generated model archives contain fitted training features and must remain private.
"""
from __future__ import annotations
import os
for name in ("OPENBLAS_NUM_THREADS","OMP_NUM_THREADS","MKL_NUM_THREADS"):os.environ[name]="1"
from pathlib import Path
import argparse,datetime,hashlib,importlib.metadata,json,sys,time,traceback
import numpy as np
STUDY=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(STUDY),str(STUDY/"engine"),str(STUDY/"acceleration")]
from bandwidth_additive import BandwidthAdditive
from local_bandwidth_additive import LocalBandwidthAdditive,GLOBAL_BANDWIDTH

OPTIONS=[("identity",0.)]+[(f,l) for f in (.1,.3,.6) for l in (.1,1.,10.)]
EXPECTED={"local":.0010581496990391417,"bandwidth07":.0010582750420801538,"r13":.001144858681382854}
LOCK="8118b562b78b3f55866d6239a38280c942df2c7d81f0b7c4ce71ba0e39ce9ffc"

def sha(path):
    with Path(path).open("rb") as f:return hashlib.file_digest(f,"sha256").hexdigest()
def write_new(path,value):
    with Path(path).open("x") as f:json.dump(value,f,indent=2,allow_nan=False);f.write("\n")
def risks(pred,y,patients):
    error=((pred[0]-y)**2+(pred[1]-y)**2)/2
    return np.stack([error[patients==g].mean(0) for g in np.unique(patients)])
def metrics(pred,y,patients,folds,targets):
    pt=risks(pred,y,patients);per=pt.mean(1)
    pf=np.array([folds[np.flatnonzero(patients==g)[0]] for g in np.unique(patients)])
    return {"mse":float(per.mean()),"p90_rmse":float(np.quantile(np.sqrt(per),.9)),
      "fold_mse":[float(per[pf==f].mean()) for f in range(5)],
      "target_mse":dict(zip(map(str,targets),map(float,pt.mean(0)))),
      "orientation_mse":[float(np.mean([((pred[o,patients==g]-y[patients==g])**2).mean()
                         for g in np.unique(patients)])) for o in (0,1)]}

def execute(curves,out,fit_final):
    from threadpoolctl import threadpool_limits
    from compact_train import load_prepared
    from coverage_methods import acquire,fit_prediction_context,CoveragePredictor,catalog_from_features
    from fast_coverage import plan_panel_fast
    from methods import patient_folds
    import evaluate
    if out.exists():raise ValueError("Output exists; choose a fresh directory")
    if sha(STUDY/"STUDY_LOCK.json")!=LOCK:raise ValueError("Historical study lock changed")
    lock=json.loads((STUDY/"STUDY_LOCK.json").read_text())
    for name,digest in lock["engine_files"].items():
        if Path(name).name!=name or sha(STUDY/"engine"/name)!=digest:
            raise ValueError("Historical scientific engine changed: "+name)
    for name,version in lock["deps"].items():
        if importlib.metadata.version(name)!=version:
            raise ValueError("Pinned dependency required: "+name+"=="+version)
    data,features,_=load_prepared(curves,STUDY/"TRAIN_CATALOG.json")
    x,y,p=features["x_replicates"],data["y"],data["patient_ids"].astype(str)
    catalog=catalog_from_features(features)
    if y.shape!=(119,24) or len(set(p))!=59 or set(data["library_ids"])!={"lib1"}:
        raise ValueError("Historical task changed")
    out.mkdir(parents=True,exist_ok=False);start=time.monotonic()
    write_new(out/"STARTED.json",{"utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
      "curves_sha256":sha(curves),"global_bandwidth_anchor":GLOBAL_BANDWIDTH,
      "bandwidths_use_target_labels":False,"options":OPTIONS,"old_prediction_input":False,
      "private_metadata_kit_used":False,"protected_response_access":False,
      "code_sha256":{name:sha(Path(__file__).with_name(name)) for name in
        ["reproduce_local_bandwidth.py","local_bandwidth_additive.py","bandwidth_additive.py","additive_kernel.py"]}})
    outer,_=patient_folds(p,5,evaluate.SALT+"|outer")
    names=("local","bandwidth07");pred={name:np.full((2,*y.shape),np.nan) for name in (*names,"r13")}
    records=[]

    def build(indices):
        plan=plan_panel_fast(x[indices],y[indices],p[indices],catalog)
        pa,pb=[acquire(x[indices],plan,o) for o in ("A","B")]
        context=fit_prediction_context(pa,pb,y[indices],p[indices],plan,catalog.target_ids)
        base=CoveragePredictor(context,plan,.01)
        z=(np.r_[pa,pb]-base.mean_x)/base.scale_x
        residual=np.r_[y[indices]-base.predict(pa),y[indices]-base.predict(pb)]
        ids,inverse,count=np.unique(p[indices],return_inverse=True,return_counts=True)
        weights=np.tile(1./(len(ids)*count[inverse]),2)/2
        owner=np.asarray(plan["coordinate_target_indices"])
        models={"local":LocalBandwidthAdditive(z,residual,weights,owner),
                "bandwidth07":BandwidthAdditive(z,residual,weights,owner,.7)}
        return plan,base,{name:(m,[np.zeros((len(z),24))]+[m.coefficients(l,f)[0] for f,l in OPTIONS[1:]])
                          for name,m in models.items()}

    def choose(indices,salt):
        inner,_=patient_folds(p[indices],3,salt)
        oof={name:np.full((10,2,len(indices),24),np.nan) for name in names}
        for fold in range(3):
            tr=indices[inner!=fold];va=indices[inner==fold]
            if set(p[tr])&set(p[va]):raise ValueError("Patient leakage")
            plan,base,models=build(tr)
            for oi,o in enumerate(("A","B")):
                paid=acquire(x[va],plan,o);zq=(paid-base.mean_x)/base.scale_x;bp=base.predict(paid)
                for name,(model,coefs) in models.items():
                    cross=model.centered_cross(zq)
                    for ci,coef in enumerate(coefs):oof[name][ci,oi,inner==fold]=bp+cross@coef
        if not all(np.isfinite(v).all() for v in oof.values()):raise ValueError("Incomplete inner predictions")
        scores={name:[float(risks(q,y[indices],p[indices]).mean()) for q in oof[name]] for name in names}
        chosen={name:min(range(10),key=lambda i:(scores[name][i],i)) for name in names}
        return chosen,scores,oof,inner

    with threadpool_limits(limits=1):
        for fold in range(5):
            tr=np.flatnonzero(outer!=fold);te=np.flatnonzero(outer==fold)
            chosen,scores,oof,inner=choose(tr,evaluate.SALT+f"|inner|{fold}")
            plan,base,models=build(tr);folder=out/f"outer_{fold:02}";folder.mkdir()
            write_new(folder/"plan.json",plan)
            np.savez_compressed(folder/"inner_predictions_private.npz",**oof,y=y[tr],patients=p[tr],folds=inner)
            for name,(model,coefs) in models.items():
                np.savez_compressed(folder/(name+"_model_private.npz"),**base.arrays(),**model.arrays(coefs[chosen[name]]))
            idx=np.asarray(plan["selected_native_indices"])
            for oi,o in enumerate(("A","B")):
                paid=acquire(x[te],plan,o);zq=(paid-base.mean_x)/base.scale_x;bp=base.predict(paid)
                pred["r13"][oi,te]=bp
                plate=np.asarray(plan[f"orientation_{o}_plate_indices"]);wells=features["well_ids"][te][:,idx,plate]
                if (plate==0).sum()!=32 or (plate==1).sum()!=32 or not all(len(set(row))==64 for row in wells):
                    raise ValueError("Physical budget changed")
                for name,(model,coefs) in models.items():
                    pred[name][oi,te]=bp+model.centered_cross(zq)@coefs[chosen[name]]
            local=models["local"][0]
            rec={"fold":fold,"selected":{name:OPTIONS[chosen[name]] for name in names},
                 "inner_scores":scores,"local_multipliers":local.local_multipliers.tolist(),
                 "local_geomean":float(np.exp(np.mean(np.log(local.local_multipliers)))),
                 "wells":64,"per_plate":32}
            records.append(rec);write_new(folder/"selection.json",rec)
            print(json.dumps({"fold":fold,"selected":rec["selected"],"local_range":
              [float(local.local_multipliers.min()),float(local.local_multipliers.max())]}),flush=True)

        if not all(np.isfinite(value).all() for value in pred.values()):raise ValueError("Incomplete predictions")
        np.savez_compressed(out/"predictions_private.npz",**pred,y=y,patients=p,folds=outer,
                            sample_ids=data["sample_ids"],drug_ids=data["drug_ids"])
        ms={name:metrics(value,y,p,outer,data["drug_ids"]) for name,value in pred.items()}
        matches={name:abs(ms[name]["mse"]-expected)<=1e-12 for name,expected in EXPECTED.items()}
        lp=risks(pred["local"],y,p).mean(1);bp=risks(pred["bandwidth07"],y,p).mean(1)
        comparison={"relative_gain":1-ms["local"]["mse"]/ms["bandwidth07"]["mse"],
          "patient_wins":int((lp<bp).sum()),"patient_losses":int((lp>bp).sum()),
          "fold_wins":sum(a<b for a,b in zip(ms["local"]["fold_mse"],ms["bandwidth07"]["fold_mse"])),
          "p90_nonworse":ms["local"]["p90_rmse"]<=ms["bandwidth07"]["p90_rmse"]}
        result={"status":"PASS" if all(matches.values()) else "MISMATCH","metrics":ms,
          "expected_matches":matches,"comparison_vs_bandwidth07":comparison,"selections":records,
          "source_route":"public_derived_csv","bandwidths_use_target_labels":False,
          "old_prediction_input":False,"private_metadata_kit_used":False,"protected_response_access":False,
          "independent_validation":False,"r18_gate_source":
          "Separately verified private historical ledger, not an input to this public replay",
          "prediction_sha256":sha(out/"predictions_private.npz"),"seconds":time.monotonic()-start}
        write_new(out/"RESULT.json",result)
        if not all(matches.values()):raise ValueError("Local-bandwidth result did not reproduce")
        if fit_final:
            rows=np.arange(len(y));chosen,scores,_,_=choose(rows,evaluate.SALT+"|local_bandwidth_final")
            plan,base,models=build(rows);model,coefs=models["local"];option=OPTIONS[chosen["local"]]
            dst=out/"final_model";dst.mkdir()
            arrays=dict(base.arrays(),**model.arrays(coefs[chosen["local"]]),
              native_ids=np.asarray(plan["selected_native_ids"]),drug_ids=data["drug_ids"],
              plate_A=np.asarray(plan["orientation_A_plate_indices"]),
              plate_B=np.asarray(plan["orientation_B_plate_indices"]))
            np.savez_compressed(dst/"model_private.npz",**arrays);write_new(dst/"plan.json",plan)
            write_new(dst/"CONSTRUCTION.json",{"model_kind":"dosepilot.additive_kernel_local_bandwidth.v1",
              "global_bandwidth_anchor":GLOBAL_BANDWIDTH,"local_bandwidth_multipliers":model.local_multipliers.tolist(),
              "bandwidths_use_target_labels":False,"selected":option,"inner_mse":scores["local"],
              "training_samples":119,"training_patients":59,"plan_sha256":sha(dst/"plan.json"),
              "model_sha256":sha(dst/"model_private.npz"),"private_training_features_in_model":True,
              "new_validation":False,"requires_all64_values":True})
        print(json.dumps({"status":result["status"],"mse":{n:m["mse"] for n,m in ms.items()},
                          "comparison":comparison},indent=2))
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--curves",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True);p.add_argument("--fit-final",action="store_true");a=p.parse_args()
    if a.output.exists():p.error("Output exists; choose a fresh path")
    try:execute(a.curves,a.output,a.fit_final)
    except BaseException as exc:
        if a.output.exists():write_new(a.output/"FAILURE.json",
          {"error":str(exc),"traceback":traceback.format_exc(),"automatic_retry":False})
        raise
if __name__=="__main__":main()
