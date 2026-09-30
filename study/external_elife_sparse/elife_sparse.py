#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, itertools, json, math, re, time, traceback, zipfile
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np

SOURCE_SHA = "b80557f95c35713df8ab0bec94acb64f266bde73dd24bbbeacb689ad701f2605"
ORGANOIDS = ("P6T","P8T","P9T","P11T","P14T","P17T","P18T","P20T","P23T","P25T","P26T","P31T")
DRUGS = ("Afatinib","Lapatinib","Selumetinib","Trametinib","SCH772984")
ALIASES = {
    "Afatinib":{"afa","afatininb","afatinib"},
    "Lapatinib":{"lap","lapatinib"},
    "Selumetinib":{"sel","selumetinib"},
    "Trametinib":{"tram","trametinib"},
    "SCH772984":{"sch","sch772984"},
}
LAMBDAS = (0.01,0.1,1.0,10.0)
ALPHA = 0.1
UPGRADES = 3
BUDGET = 13
SCALE_FLOOR = 0.05
NS={"m":"http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

def sha(path):
    with Path(path).open("rb") as f: return hashlib.file_digest(f,"sha256").hexdigest()

def dump(path,obj):
    with Path(path).open("x",encoding="utf-8") as f:
        json.dump(obj,f,indent=2,sort_keys=True,allow_nan=False); f.write("\n")

def norm(s): return re.sub(r"[^a-z0-9]","",str(s).lower())

def auc(doses, values):
    doses=np.asarray(doses,float); values=np.asarray(values,float)
    if doses.ndim!=1 or values.shape[-1]!=len(doses) or len(doses)<2:
        raise ValueError("bad AUC geometry")
    if not np.isfinite(doses).all() or not np.isfinite(values).all() or np.any(doses<=0):
        raise ValueError("nonfinite AUC input")
    order=np.argsort(doses); x=np.log(doses[order]); v=values[...,order]
    if np.any(np.diff(x)<=0): raise ValueError("duplicate dose")
    return np.sum(np.diff(x)*(v[...,:-1]+v[...,1:])/2,axis=-1)/(x[-1]-x[0])

def _cell_text(cell, shared):
    if cell is None:return None
    v=cell.findtext("m:v",namespaces=NS); typ=cell.get("t")
    if typ=="s" and v is not None:return shared[int(v)]
    if typ=="inlineStr":
        q=cell.find("m:is",NS); return "".join(q.itertext()) if q is not None else None
    return v

def load_public_workbook(path):
    path=Path(path)
    if sha(path)!=SOURCE_SHA: raise ValueError("source workbook identity changed")
    with zipfile.ZipFile(path) as z:
        shared=[]
        if "xl/sharedStrings.xml" in z.namelist():
            shared=["".join(x.itertext()) for x in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si",NS)]
        wb=ET.fromstring(z.read("xl/workbook.xml"))
        rels=ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        relmap={x.get("Id"):x.get("Target") for x in rels}
        raw={}; dose_grid=None
        for sheet in wb.findall("m:sheets/m:sheet",NS):
            name=sheet.get("name")
            if name not in ORGANOIDS: continue
            rid=sheet.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
            target=relmap[rid]; member=target.lstrip("/") if target.startswith("/") else "xl/"+target
            root=ET.fromstring(z.read(member)); rows={}
            for row in root.findall("m:sheetData/m:row",NS):
                cells={re.match(r"([A-Z]+)",c.get("r")).group(1):c for c in row.findall("m:c",NS)}
                label=_cell_text(cells.get("A"),shared)
                if int(row.get("r"))==2:
                    grid=[]
                    for i in range(22):
                        q=_cell_text(cells.get(chr(66+i)),shared)
                        grid.append(float(q) if q not in (None,"") else np.nan)
                    grid=np.asarray(grid,float)
                    if dose_grid is None:dose_grid=grid
                    else:np.testing.assert_allclose(dose_grid,grid,rtol=0,atol=0)
                elif label:
                    vals=[]
                    for i in range(22):
                        q=_cell_text(cells.get(chr(66+i)),shared)
                        vals.append(float(q)/100 if q not in (None,"") else np.nan)
                    rows[norm(label)]=np.asarray(vals,float)
            resolved={}
            for drug in DRUGS:
                keys=[k for k in rows if k in ALIASES[drug]]
                if len(keys)!=1:raise ValueError(f"{name}/{drug}: alias resolution {keys}")
                resolved[drug]=rows[keys[0]][:-1] # exclude zero-dose control
            raw[name]=resolved
    if set(raw)!=set(ORGANOIDS): raise ValueError("fixed organoid frame changed")
    dose_grid=dose_grid[:-1]
    curves=[]; y=np.empty((len(ORGANOIDS),len(DRUGS)))
    support_audit={}
    for j,drug in enumerate(DRUGS):
        matrix=np.vstack([raw[o][drug] for o in ORGANOIDS])
        complete=np.all(np.isfinite(matrix),axis=0)
        indices=np.flatnonzero(complete)
        if len(indices)<3:raise ValueError("insufficient complete target support")
        doses=dose_grid[indices]; values=matrix[:,indices]
        order=np.argsort(doses); doses=doses[order]; values=values[:,order]
        y[:,j]=auc(doses,values)
        curves.append({"drug":drug,"doses":doses,"values":values,
                       "source_indices":indices[order]})
        support_audit[drug]={"support_count":len(doses),"doses_uM":doses.tolist(),
                             "source_indices":indices[order].tolist()}
    if [support_audit[d]["support_count"] for d in DRUGS] != [12,11,14,8,9]:
        raise ValueError("preflight support count changed")
    if not np.isfinite(y).all(): raise ValueError("nonfinite targets")
    return curves,y,support_audit

def context(x,y):
    x=np.asarray(x,float);y=np.asarray(y,float)
    mx=x.mean(0); my=y.mean(0); sx=np.maximum(x.std(0),SCALE_FLOOR)
    z=(x-mx)/sx; cy=y-my
    return {"mx":mx,"my":my,"sx":sx,"cxx":z.T@z/len(x),"cxy":z.T@cy/len(x),"cyy":cy.T@cy/len(x)}

def subset_risk(x,y):
    x=np.asarray(x,float);y=np.asarray(y,float).reshape(-1,1)
    c=context(x,y); cross=c["cxy"][:,0]
    return float(c["cyy"][0,0]-cross@np.linalg.solve(c["cxx"]+ALPHA*np.eye(x.shape[1]),cross))

def learned_plan(curves,y,rows):
    rows=np.asarray(rows,int); choices=[]
    for j,c in enumerate(curves):
        best={}
        for size in (2,3):
            opts=[]
            for subset in itertools.combinations(range(len(c["doses"])),size):
                risk=subset_risk(c["values"][rows][:,subset],y[rows,j])
                opts.append((risk,tuple(subset)))
            best[size]=min(opts,key=lambda q:(q[0],q[1]))
        choices.append({"drug":c["drug"],"best2":list(best[2][1]),"best3":list(best[3][1]),
                        "risk2":best[2][0],"risk3":best[3][0],"gain":best[2][0]-best[3][0]})
    upgraded={DRUGS.index(x["drug"]) for x in sorted(choices,key=lambda x:(-x["gain"],x["drug"]))[:UPGRADES]}
    selected=[];owner=[]
    for j,c in enumerate(choices):
        subset=c["best3"] if j in upgraded else c["best2"]
        selected.extend((j,k) for k in subset); owner.extend([j]*len(subset))
    if len(selected)!=BUDGET or len(set(selected))!=BUDGET:raise AssertionError("bad learned budget")
    return {"selected":[list(x) for x in selected],"owner":owner,
            "upgraded":[DRUGS[j] for j in sorted(upgraded)],"choices":choices,"budget":BUDGET}

def feature_matrix(curves,rows,plan):
    rows=np.asarray(rows,int)
    return np.column_stack([curves[j]["values"][rows,k] for j,k in plan["selected"]])

def fit_model(curves,y,rows,plan,lam):
    rows=np.asarray(rows,int); x=feature_matrix(curves,rows,plan); c=context(x,y[rows])
    owner=np.asarray(plan["owner"]); beta=np.zeros((BUDGET,len(DRUGS)))
    for j in range(len(DRUGS)):
        cols=np.flatnonzero(owner==j)
        h=c["cxx"][np.ix_(cols,cols)]+lam*np.eye(len(cols))
        beta[cols,j]=np.linalg.solve(h,c["cxy"][cols,j])
    return {"mx":c["mx"],"my":c["my"],"sx":c["sx"],"beta":beta,"lambda":float(lam)}

def predict_model(curves,rows,plan,model):
    x=feature_matrix(curves,rows,plan)
    out=model["my"]+((x-model["mx"])/model["sx"])@model["beta"]
    if not np.isfinite(out).all():raise ValueError("nonfinite model prediction")
    return out

def interp_auc(curve_values, full_doses, subset):
    subset=np.asarray(subset,int); d=np.asarray(full_doses,float); v=np.asarray(curve_values,float)
    order=np.argsort(d[subset]); sd=d[subset][order]; sv=v[subset][order]
    grid=np.sort(d)
    pred=np.interp(np.log(grid),np.log(sd),sv)
    return float(auc(grid,pred))

def interpolation_plan(curves,y,rows):
    rows=np.asarray(rows,int);choices=[]
    for j,c in enumerate(curves):
        best={}
        for size in (2,3):
            opts=[]
            for subset in itertools.combinations(range(len(c["doses"])),size):
                pred=np.asarray([interp_auc(c["values"][i],c["doses"],subset) for i in rows])
                risk=float(np.mean((pred-y[rows,j])**2))
                opts.append((risk,tuple(subset)))
            best[size]=min(opts,key=lambda q:(q[0],q[1]))
        choices.append({"drug":c["drug"],"best2":list(best[2][1]),"best3":list(best[3][1]),
                        "risk2":best[2][0],"risk3":best[3][0],"gain":best[2][0]-best[3][0]})
    upgraded={DRUGS.index(x["drug"]) for x in sorted(choices,key=lambda x:(-x["gain"],x["drug"]))[:UPGRADES]}
    if sum(3 if j in upgraded else 2 for j in range(len(DRUGS)))!=BUDGET:raise AssertionError("bad interpolation budget")
    return {"choices":choices,"upgraded":[DRUGS[j] for j in sorted(upgraded)],"budget":BUDGET}

def interpolation_predict(curves,rows,plan):
    rows=np.asarray(rows,int); out=np.empty((len(rows),len(DRUGS))); upgraded=set(plan["upgraded"])
    for j,c in enumerate(curves):
        q=plan["choices"][j]; subset=q["best3"] if c["drug"] in upgraded else q["best2"]
        out[:,j]=[interp_auc(c["values"][i],c["doses"],subset) for i in rows]
    return out

def select_lambda(curves,y,outer_train):
    outer_train=np.asarray(outer_train,int)
    oof={lam:np.full((len(outer_train),len(DRUGS)),np.nan) for lam in LAMBDAS}
    records=[]
    for local_hold in range(len(outer_train)):
        val=np.array([outer_train[local_hold]])
        fit=np.delete(outer_train,local_hold)
        plan=learned_plan(curves,y,fit)
        for lam in LAMBDAS:oof[lam][local_hold]=predict_model(curves,val,plan,fit_model(curves,y,fit,plan,lam))[0]
    scores={str(lam):float(np.mean((oof[lam]-y[outer_train])**2)) for lam in LAMBDAS}
    chosen=min(LAMBDAS,key=lambda q:(scores[str(q)],LAMBDAS.index(q)))
    return chosen,scores

def bootstrap_delta(delta,n=10000,seed=20260930):
    rng=np.random.default_rng(seed);delta=np.asarray(delta,float)
    boot=delta[rng.integers(0,len(delta),size=(n,len(delta)))].mean(1)
    return np.quantile(boot,[.025,.975]).tolist()

def run(source,out):
    out=Path(out);out.mkdir(parents=True,exist_ok=False);t0=time.monotonic()
    curves,y,support=load_public_workbook(source)
    pred={"learned":np.full_like(y,np.nan),"interpolation":np.full_like(y,np.nan),"train_mean":np.full_like(y,np.nan)}
    folds=[]
    for hold in range(len(ORGANOIDS)):
        train=np.flatnonzero(np.arange(len(ORGANOIDS))!=hold);test=np.array([hold])
        lam,scores=select_lambda(curves,y,train)
        lp=learned_plan(curves,y,train);ip=interpolation_plan(curves,y,train)
        pred["learned"][test]=predict_model(curves,test,lp,fit_model(curves,y,train,lp,lam))
        pred["interpolation"][test]=interpolation_predict(curves,test,ip)
        pred["train_mean"][test]=y[train].mean(0)
        fold={"holdout":ORGANOIDS[hold],"lambda":lam,"inner_scores":scores,
              "learned_upgrades":lp["upgraded"],"interpolation_upgrades":ip["upgraded"],
              "learned_selected":lp["selected"],
              "interpolation_choices":ip["choices"]}
        folds.append(fold);dump(out/f"fold_{hold:02d}.json",fold)
    if any(not np.isfinite(x).all() for x in pred.values()):raise AssertionError("incomplete OOF")
    np.savez_compressed(out/"predictions_private.npz",organoids=np.asarray(ORGANOIDS),drugs=np.asarray(DRUGS),y=y,**pred)
    metrics={}
    errors={}
    for name,p in pred.items():
        e=(p-y)**2;errors[name]=e
        row=e.mean(1)
        metrics[name]={"mse":float(e.mean()),"rmse":float(np.sqrt(e.mean())),
                       "p90_organoid_rmse":float(np.quantile(np.sqrt(row),.9)),
                       "per_target_mse":dict(zip(DRUGS,map(float,e.mean(0))))}
    le=errors["learned"].mean(1);ie=errors["interpolation"].mean(1);delta=le-ie
    target_le=errors["learned"].mean(0);target_ie=errors["interpolation"].mean(0)
    ci=bootstrap_delta(delta)
    gate={
      "relative_gain_5pct":metrics["learned"]["mse"]<=metrics["interpolation"]["mse"]*.95,
      "organoid_wins_8":int((delta<0).sum())>=8,
      "target_wins_4":int((target_le<target_ie).sum())>=4,
      "p90_nonworse":metrics["learned"]["p90_organoid_rmse"]<=metrics["interpolation"]["p90_organoid_rmse"],
      "bootstrap_upper_below_zero":ci[1]<0,
    }
    result={"status":"COMPLETE","evidence_level":"RETROSPECTIVE_EXTERNAL_STRESS_TEST_AFTER_PARTIAL_SOURCE_EXPOSURE",
            "source_sha256":sha(source),"organoids":len(ORGANOIDS),"targets":len(DRUGS),
            "target_support":support,"total_target_readouts":sum(len(c["doses"]) for c in curves),
            "sparse_readouts":BUDGET,"measurement_count_reduction":1-BUDGET/sum(len(c["doses"]) for c in curves),
            "metrics":metrics,"learned_vs_interpolation":{
              "relative_mse_reduction":1-metrics["learned"]["mse"]/metrics["interpolation"]["mse"],
              "strict_organoid_wins":int((delta<0).sum()),"strict_organoid_losses":int((delta>0).sum()),
              "ties":int((delta==0).sum()),"target_wins":int((target_le<target_ie).sum()),
              "descriptive_delta_ci95":ci},
            "gate":gate,"decision":"PASSES_RETROSPECTIVE_STRESS_GATE" if all(gate.values()) else "DOES_NOT_PASS_RETROSPECTIVE_STRESS_GATE",
            "folds":folds,"predictions_sha256":sha(out/"predictions_private.npz"),
            "new_independent_confirmation":False,"original_r13_weights_tested":False,
            "physical_well_equivalence_claimed":False,"official_competition_score":None,
            "seconds":time.monotonic()-t0}
    dump(out/"RESULT.json",result);return result

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--source",type=Path,required=True);ap.add_argument("--output",type=Path,required=True);a=ap.parse_args()
    try:
        r=run(a.source,a.output);print(json.dumps({k:v for k,v in r.items() if k!="folds"},indent=2))
    except BaseException as exc:
        if not a.output.exists():a.output.mkdir(parents=True)
        dump(a.output/"FAILURE.json",{"type":type(exc).__name__,"message":str(exc),"traceback":traceback.format_exc(),"automatic_retry":False})
        raise
if __name__=="__main__":main()
