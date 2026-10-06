#!/usr/bin/env python3
import argparse
from pathlib import Path
import numpy as np,pandas as pd

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--workbook",type=Path,required=True);ap.add_argument("--output",type=Path,required=True);a=ap.parse_args()
    if a.output.exists():ap.error("output exists")
    df=pd.read_excel(a.workbook,usecols=["sample_id","library_id","compound_type","plate","signal"])
    df=df[(df.library_id.astype(str).str.lower()=="lib1") & df.compound_type.astype(str).str.contains("control",case=False,na=False)]
    rows=[]
    for sid,g in df.groupby("sample_id"):
        r={"sample_id":str(sid)}
        for plate in ("p1","p2"):
            gp=g[g.plate.astype(str).str.lower()==plate]
            vals={}
            for typ,tag in (("control_negative","neg"),("control_positive","pos")):
                x=gp[gp.compound_type.astype(str).str.lower()==typ].signal.astype(float).to_numpy()
                if not len(x):raise ValueError(f"missing {typ} {sid} {plate}")
                r[f"{plate}_{tag}_logmed"]=float(np.log1p(np.median(x)))
                r[f"{plate}_{tag}_cv"]=float(np.std(x)/(abs(np.mean(x))+1e-12));vals[tag]=x
            r[f"{plate}_logrange"]=float(np.log1p(max(np.median(vals["neg"])-np.median(vals["pos"]),0.0)))
        rows.append(r)
    out=pd.DataFrame(rows).sort_values("sample_id")
    a.output.parent.mkdir(parents=True,exist_ok=True);out.to_csv(a.output,index=False)
    print(a.output,len(out))
if __name__=="__main__":main()
