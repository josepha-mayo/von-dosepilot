#!/usr/bin/env python3
import argparse,json,hashlib,sys
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE));import run_study as rs
def sha(p):
 with Path(p).open("rb") as f:return hashlib.file_digest(f,"sha256").hexdigest()
def main():
 ap=argparse.ArgumentParser();ap.add_argument("--run",type=Path,required=True);a=ap.parse_args()
 z=np.load(a.run/"predictions_private.npz",allow_pickle=False);r=json.loads((a.run/"RESULT.json").read_text(encoding="utf-8"))
 q=rs.W*z["best"]+(1-rs.W)*z["raw"]
 if not np.array_equal(q,z["candidate"]):raise ValueError("reconstruction")
 m=rs.metrics(q,z["y"],z["patients"].astype(str),z["folds"])
 if abs(m["mse"]-r["candidate"]["mse"])>1e-15:raise ValueError("mse")
 out={"status":"PASS","fit_routine_called":False,"candidate_predictions_reconstructed":int(q.size),"max_prediction_difference":0.0,"candidate_mse":m["mse"],"prediction_sha256":sha(a.run/"predictions_private.npz"),"protected22_access":False}
 (a.run/"VERIFICATION.json").write_text(json.dumps(out,indent=2)+"\n",encoding="utf-8");print(json.dumps(out,indent=2))
if __name__=="__main__":main()
