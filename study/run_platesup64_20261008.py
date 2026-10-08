#!/usr/bin/env python3
"""Extra plate-specific supervised channels for frozen 64-well residual models."""
from __future__ import annotations
import os
for key in ("OPENBLAS_NUM_THREADS","OMP_NUM_THREADS","MKL_NUM_THREADS"):
    os.environ[key]="1"
import hashlib,json,sys
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import run_crossplate64_20261008 as core
from coverage_methods import catalog_from_features
from sparse_methods import fit_sparse_context

ARMS=("mean24","plate48","orthogonal48","weakcontrast48")
OPTIONS=core.OPTIONS

class AnyOutputKernel(core.BandwidthAdditive):
    """Same 0.7 drug-group kernel, generalized to 24 or 48 residual channels."""
    def __init__(self,z,residual,weights,owner):
        self.z=np.asarray(z,float).copy()
        self.residual=np.asarray(residual,float).copy()
        self.w=np.asarray(weights,float).copy()
        self.owner=np.asarray(owner,int).copy()
        self.multiplier=.7
        self.nonlinear=True
        if self.z.ndim!=2 or self.z.shape[1]!=64 or self.residual.ndim!=2:
            raise ValueError("64-column inputs and 2D residual outputs required")
        if self.residual.shape[0]!=len(self.z) or self.residual.shape[1] not in (24,48):
            raise ValueError("expected 24 or 48 residual targets")
        if self.w.shape!=(len(self.z),) or abs(self.w.sum()-1)>1e-12 or (self.w<=0).any():
            raise ValueError("invalid patient weights")
        if not np.isfinite(self.z).all() or not np.isfinite(self.residual).all():
            raise ValueError("nonfinite training arrays")
        self.groups=[np.flatnonzero(self.owner==j) for j in range(24)]
        if sorted(map(len,self.groups))!=[2]*8+[3]*16:
            raise ValueError("original 64-dose groups required")
        raw=self.raw_cross(self.z)
        self.train_mean=self.w@raw
        self.grand=float(self.train_mean@self.w)
        centered=raw-(raw@self.w)[:,None]-self.train_mean[None,:]+self.grand
        self.sw=np.sqrt(self.w)
        mat=self.sw[:,None]*centered*self.sw[None,:]
        eig,u=np.linalg.eigh((mat+mat.T)/2)
        if eig.min()<-1e-10:raise ValueError("non-PSD residual kernel")
        self.e=np.maximum(eig,0)
        self.u=u
        self.ur=u.T@(self.sw[:,None]*self.residual)

def fit_bundle(x,y,plate_auc,patients,catalog,plan):
    # At FIT time, both historical plate AUCs may be labels. Never inference inputs.
    if not np.allclose(plate_auc.mean(axis=2),y,atol=1e-12,rtol=0):
        raise AssertionError("plate target definition")
    a,b=core.paid(x,plan,"A"),core.paid(x,plan,"B")
    pa=np.r_[a,b]
    py=np.r_[y,y]
    pp=np.r_[patients,patients]
    ctx=fit_sparse_context(pa,py,pp,plan["selected_native_ids"],catalog.target_ids)
    ridge=core.Ridge(ctx,plan,.01)
    z=(pa-ridge.mean_x)/ridge.scale_x
    rmean=py-ridge.predict(pa)
    p1=np.r_[plate_auc[:,:,0],plate_auc[:,:,0]]-ridge.predict(pa)
    p2=np.r_[plate_auc[:,:,1],plate_auc[:,:,1]]-ridge.predict(pa)
    contrast=p1-p2
    residuals={"mean24":rmean,
               "plate48":np.c_[p1,p2],
               "orthogonal48":np.c_[rmean,.5*contrast],
               "weakcontrast48":np.c_[rmean,.125*contrast]}
    weights=np.tile(core.patient_weights(patients),2)/(2*len(np.unique(patients)))
    models={}
    for arm in ARMS:
        Kernel=core.BandwidthAdditive if arm=="mean24" else AnyOutputKernel
        if arm=="mean24":
            kernel=Kernel(z,residuals[arm],weights,np.asarray(plan["coordinate_target_indices"],int),.7)
        else:
            kernel=Kernel(z,residuals[arm],weights,np.asarray(plan["coordinate_target_indices"],int))
        coeffs=[np.zeros_like(residuals[arm])]
        for frac,lam in OPTIONS[1:]:
            coeffs.append(kernel.coefficients(lam,frac)[0])
        models[arm]=(plan,ridge,kernel,coeffs)
    return models

def predict(x,model,arm):
    plan,ridge,kernel,coef=model
    preds=np.empty((len(OPTIONS),2,len(x),24))
    for oi,o in enumerate(("A","B")):
        paid=core.paid(x,plan,o)
        base=ridge.predict(paid)
        K=kernel.centered_cross((paid-ridge.mean_x)/ridge.scale_x)
        for j,c in enumerate(coef):
            d=K@c
            if arm=="plate48":
                d=(d[:,:24]+d[:,24:])/2
            else:
                d=d[:,:24]
            preds[j,oi]=base+d
    if not np.isfinite(preds).all():raise AssertionError("missing predictions")
    return preds

def main(out):
    if out.exists():raise ValueError("refuse overwrite")
    d,f,plate=core.load_prepared(core.CURVES,core.CATALOG)
    x=f["x_replicates"]; y=d["y"]; patients=d["patient_ids"].astype(str)
    cat=catalog_from_features(f)
    if plate.shape!=(119,24,2):raise AssertionError("true original plate AUC shape")
    if not np.allclose(plate.mean(axis=2),y,atol=1e-12,rtol=0):raise AssertionError("AUC identity")
    rz=np.load(core.BW,allow_pickle=False)
    bz=np.load(core.BEST,allow_pickle=False)
    folds=np.asarray(rz["folds"],int)
    if not np.array_equal(rz["y"],y) or not np.array_equal(bz["y"],y):raise AssertionError("source label mismatch")
    if not np.array_equal(rz["patients"].astype(str),patients) or not np.array_equal(bz["patients"].astype(str),patients):
        raise AssertionError("patient identity")
    if not np.array_equal(bz["folds"],folds):raise AssertionError("outer fold mismatch")
    recompute,_=core.patient_folds(patients,5,core.evaluate.SALT+"|outer")
    if not np.array_equal(recompute,folds):raise AssertionError("fold recipe")
    bw=core.metric(rz["bandwidth07"],y,patients,folds)
    scientific=core.metric(bz["candidate"],y,patients,folds)
    if abs(bw[0]["mse"]-core.EXPECTED_BW)>1e-13 or abs(scientific[0]["mse"]-core.EXPECTED_BEST)>1e-13:raise AssertionError("reference")
    pred={arm:np.full((2,len(y),24),np.nan) for arm in ARMS}
    fold_records=[]
    for ff in range(5):
        tr=np.flatnonzero(folds!=ff);te=np.flatnonzero(folds==ff)
        if set(patients[tr])&set(patients[te]):raise AssertionError("outer leak")
        inner,_=core.patient_folds(patients[tr],3,core.evaluate.SALT+f"|inner|{ff}")
        oof={arm:np.full((len(OPTIONS),2,len(tr),24),np.nan) for arm in ARMS}
        for ik in range(3):
            sub=tr[inner!=ik];val=tr[inner==ik]
            if set(patients[sub])&set(patients[val]):raise AssertionError("inner leak")
            plan=core.plan_panel_fast(x[sub],y[sub],patients[sub],cat)
            models=fit_bundle(x[sub],y[sub],plate[sub],patients[sub],cat,plan)
            for arm in ARMS:
                oof[arm][:,:,inner==ik]=predict(x[val],models[arm],arm)
        selected={}
        for arm in ARMS:
            if not np.isfinite(oof[arm]).all():raise AssertionError("missing inner OOF")
            scores=[core.metric(oof[arm][j],y[tr],patients[tr],inner)[0]["mse"] for j in range(len(OPTIONS))]
            index=int(np.argmin(scores))
            selected[arm]={"index":index,"option":OPTIONS[index],"inner_mse":float(scores[index])}
        plan=core.plan_panel_fast(x[tr],y[tr],patients[tr],cat)
        models=fit_bundle(x[tr],y[tr],plate[tr],patients[tr],cat,plan)
        for arm in ARMS:
            hypotheses=predict(x[te],models[arm],arm)
            pred[arm][:,te]=hypotheses[selected[arm]["index"]]
        fold_records.append({"fold":ff,"selected":selected})
        print(json.dumps({"fold":ff,"selected":{a:selected[a]["option"] for a in ARMS}}),flush=True)
    for arm in ARMS:
        if not np.isfinite(pred[arm]).all():raise AssertionError("incomplete output")
    err=float(np.max(abs(pred["mean24"]-rz["bandwidth07"])))
    if err>1e-9:raise AssertionError("control mismatch")
    results={}
    for arm in ARMS:
        m=core.metric(pred[arm],y,patients,folds)
        v=core.compare(m,scientific)
        v0=core.compare(m,bw)
        results[arm]={"metrics":m[0],"vs_scientific":v,"vs_operating":v0,
           "two_x":bool(m[0]["mse"]<=core.TWOX and m[0]["p90"]<=scientific[0]["p90"]),
           "eligible":bool(arm!="mean24" and v["relative_gain"]>0 and
              v0["relative_gain"]>0 and v["patient_wins"]>=30 and
              v["fold_wins"]==5 and v["p90_nonworse"])}
    receipt={"schema":"dosepilot.platesup64.result.v1",
        "status":"COMPLETE","role":"REPEATED_ADAPTIVE_LIB1_TRAIN_DEVELOPMENT",
        "original_64_control_max_abs_error":err,
        "operating64":bw[0],"scientific64":scientific[0],
        "arms":results,"fold_records":fold_records,
        "numerical_two_x_target":core.TWOX,
        "no_protected22":True,"no_official_competition_score":True,
        "automatic_promotion":False,
        "source_sha256":core.digest(Path(__file__)),
        "protocol_sha256":core.digest(HERE/"PLATESUP64_PROTOCOL_20261008.md"),
        "input_sha256":{"curves":core.digest(core.CURVES),
            "catalog":core.digest(core.CATALOG),
            "operating":core.digest(core.BW),"scientific":core.digest(core.BEST)},
        "utc":datetime.now(timezone.utc).isoformat()}
    out.mkdir(parents=True)
    np.savez_compressed(out/"predictions_private.npz",
        y=y,patients=patients,folds=folds,operating64=rz["bandwidth07"],
        scientific64=bz["candidate"],**pred)
    (out/"RESULT.json").write_text(json.dumps(receipt,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps({arm:{"mse":results[arm]["metrics"]["mse"],
            "gain":results[arm]["vs_scientific"]["relative_gain"],
            "fold_wins":results[arm]["vs_scientific"]["fold_wins"],
            "patient_wins":results[arm]["vs_scientific"]["patient_wins"],
            "p90":results[arm]["metrics"]["p90"]} for arm in ARMS},indent=2),flush=True)

if __name__=="__main__":
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument("--out",type=Path,required=True)
    opts=parser.parse_args()
    main(opts.out)
