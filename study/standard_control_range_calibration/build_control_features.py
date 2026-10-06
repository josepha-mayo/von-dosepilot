#!/usr/bin/env python3
from pathlib import Path
import argparse
import numpy as np
import pandas as pd

COLS=["sample_id","library_id","compound_type","plate","signal"]
OUTCOLS=["sample_id","p1_logrange","p2_logrange"]

def build(workbook:Path,output:Path):
    df=pd.read_excel(workbook,usecols=COLS)
    lib=df[df["library_id"].astype(str).str.lower().eq("lib1")].copy()
    controls=lib[lib["compound_type"].astype(str).str.lower().isin(["control_negative","control_positive"])]
    rows=[]
    for sid,g in controls.groupby("sample_id",sort=True):
        r={"sample_id":str(sid)}
        for plate in ("p1","p2"):
            gp=g[g["plate"].astype(str).str.lower().eq(plate)]
            neg=gp[gp["compound_type"].astype(str).str.lower().eq("control_negative")]["signal"].astype(float).to_numpy()
            pos=gp[gp["compound_type"].astype(str).str.lower().eq("control_positive")]["signal"].astype(float).to_numpy()
            if len(neg)==0 or len(pos)==0: raise ValueError(f"missing standard controls {sid} {plate}")
            r[f"{plate}_logrange"]=float(np.log1p(max(float(np.median(neg)-np.median(pos)),0.0)))
        rows.append(r)
    out=pd.DataFrame(rows,columns=OUTCOLS)
    if len(out)!=119 or out["sample_id"].nunique()!=119: raise ValueError("unexpected Lib1 sample count")
    if output.exists(): raise ValueError("output exists")
    out.to_csv(output,index=False)
    print(output)
if __name__=="__main__":
    ap=argparse.ArgumentParser();ap.add_argument("--workbook",type=Path,required=True);ap.add_argument("--output",type=Path,required=True);a=ap.parse_args()
    build(a.workbook,a.output)
