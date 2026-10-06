#!/usr/bin/env python3
import argparse,json,hashlib,sys
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE));import run_study as rs
def sha(p):
    with Path(p).open("rb") as f:return hashlib.file_digest(f,"sha256").hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--run",type=Path,required=True);ap.add_argument("--reference-dir",type=Path,required=True)
    ap.add_argument("--curves",type=Path,required=True);ap.add_argument("--control-features",type=Path,required=True);ap.add_argument("--best-predictions",type=Path,required=True);a=ap.parse_args()
    r=json.loads((a.run/"RESULT.json").read_text());z=np.load(a.run/"predictions_private.npz",allow_pickle=False)
    cand,ctx,records=rs.construct(a.reference_dir,a.curves,a.control_features,a.best_predictions)
    maxdiff=float(np.max(np.abs(cand-z["candidate"])))
    if maxdiff>5e-16:raise ValueError("RECONSTRUCTION")
    for key in ("y","patients","folds","bandwidth07","r13","best"):
        aa=ctx[key];bb=z[key]
        if not np.array_equal(aa.astype(str),bb.astype(str)) if aa.dtype.kind in "USO" else not np.array_equal(aa,bb):raise ValueError("CTX_"+key)
    m=rs.up.metrics(cand,ctx["y"],ctx["patients"].astype(str),ctx["folds"])
    if abs(m["mse"]-r["candidate"]["mse"])>1e-15:raise ValueError("MSE")
    if sha(a.run/"predictions_private.npz")!=r["prediction_sha256"]:raise ValueError("HASH")
    out={"status":"PASS_FLOATING_REPLAY","base_model_refit":False,"calibration_recomputed":True,"candidate_predictions_reconstructed":int(cand.size),
      "max_prediction_difference":maxdiff,"prediction_tolerance":5e-16,"candidate_mse":m["mse"],"calibration_folds_checked":len(records),
      "prediction_sha256":r["prediction_sha256"],"protected22_access":False}
    (a.run/"VERIFICATION.json").write_text(json.dumps(out,indent=2)+"\n");print(json.dumps(out,indent=2))
if __name__=="__main__":main()
