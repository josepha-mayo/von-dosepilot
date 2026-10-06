#!/usr/bin/env python3
import argparse,json,hashlib,sys
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE));import run_study as rs
def sha(p):
 with Path(p).open("rb") as f:return hashlib.file_digest(f,"sha256").hexdigest()
def main():
 ap=argparse.ArgumentParser();ap.add_argument("--run",type=Path,required=True);ap.add_argument("--reference-dir",type=Path,required=True);a=ap.parse_args()
 r=json.loads((a.run/"RESULT.json").read_text(encoding="utf-8"));z=np.load(a.run/"predictions_private.npz",allow_pickle=False);rr=json.loads((a.reference_dir/"RESULT.json").read_text(encoding="utf-8"));folds=z["folds"];cand=np.empty_like(z["candidate"]);checks=0
 for f in range(5):
  iz=np.load(a.reference_dir/f"outer_{f:02}"/"inner_predictions_private.npz",allow_pickle=False);sel=rr["selections"][f]["selected"]["bandwidth07"];oi=rs.option_index(sel)
  cs,rb,counts=rs.fold_stats(iz["bandwidth07"][oi],iz["y"],iz["patients"].astype(str),iz["folds"]);theta,prior,_=rs.theta_and_prior_gain(cs,counts);gain,gm=rs.gain_details(cs,rb,counts,prior);rec=r["fold_records"][f]
  if list(map(int,counts))!=list(map(int,rec["inner_patient_counts"])):raise ValueError("COUNTS")
  if np.max(np.abs(theta-np.asarray(rec["theta_full"])))>1e-15 or np.max(np.abs(prior-np.asarray(rec["prior_gain"])))>1e-15 or np.max(np.abs(gain-np.asarray(rec["final_gain"])))>1e-15:raise ValueError("GAIN")
  te=np.flatnonzero(folds==f);cand[0,te]=z["bagged"][0,te];cand[1,te]=z["interpolated_jackknife"][1,te]-0.5*(gain*theta)[None,:];checks+=1
 if not np.array_equal(cand,z["candidate"]):raise ValueError("RECONSTRUCTION")
 m=rs.metrics(cand,z["y"],z["patients"].astype(str),folds)
 if abs(m["mse"]-r["candidate"]["mse"])>1e-15:raise ValueError("MSE")
 if sha(a.run/"predictions_private.npz")!=r["prediction_sha256"]:raise ValueError("HASH")
 out={"status":"PASS","fit_routine_called":False,"candidate_predictions_reconstructed":int(cand.size),"max_prediction_difference":0.0,"candidate_mse":m["mse"],"gain_folds_checked":checks,"prediction_sha256":r["prediction_sha256"],"protected22_access":False}
 (a.run/"VERIFICATION.json").write_text(json.dumps(out,indent=2)+"\n",encoding="utf-8");print(json.dumps(out,indent=2))
if __name__=="__main__":main()
