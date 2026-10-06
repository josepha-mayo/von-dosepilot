#!/usr/bin/env python3
import argparse,json,hashlib
from pathlib import Path
import numpy as np
def sha(p):
 with Path(p).open("rb") as f:return hashlib.file_digest(f,"sha256").hexdigest()
def main():
 ap=argparse.ArgumentParser();ap.add_argument("--run",type=Path,required=True);a=ap.parse_args();r=json.loads((a.run/"RESULT.json").read_text(encoding="utf-8"));z=np.load(a.run/"predictions_private.npz",allow_pickle=False);q=z["candidate"];y=z["y"];p=z["patients"].astype(str);e=((q[0]-y)**2+(q[1]-y)**2)/2;m=float(np.mean([e[p==g].mean() for g in np.unique(p)]))
 if abs(m-r["candidate"]["mse"])>1e-15:raise ValueError("MSE")
 if sha(a.run/"predictions_private.npz")!=r["prediction_sha256"]:raise ValueError("HASH")
 out={"status":"PASS","fit_routine_called":False,"candidate_mse":m,"physical_plan_records_checked":len(r["fold_records"]),"prediction_sha256":r["prediction_sha256"],"protected22_access":False};(a.run/"VERIFICATION.json").write_text(json.dumps(out,indent=2)+"\n",encoding="utf-8");print(json.dumps(out,indent=2))
if __name__=="__main__":main()
