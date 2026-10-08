#!/usr/bin/env python3
"""Independent numeric replay and physical-plan checks of frozen plate-permutation test."""
import hashlib,json
from pathlib import Path
import numpy as np
out=Path("/mnt/d/von-dosepilot-data/plateperm64_20261008_run1")
src=Path("/mnt/d/von-dosepilot-plateperm64-20261008/study/run_plateperm64_20261008.py")
r=json.loads((out/"RESULT.json").read_text())
q=np.load(out/"predictions_private.npz",allow_pickle=False)
y=q["y"];p=q["patients"].astype(str);f=q["folds"];u=np.unique(p)
pf=np.asarray([int(f[np.flatnonzero(p==g)[0]]) for g in u])
assert y.shape==(119,24) and len(u)==59
assert hashlib.sha256(src.read_bytes()).hexdigest()==r["source_sha256"]
for arm in ("original","minority_low","minority_high","training_risk"):
 pred=q[arm]
 assert pred.shape==(2,119,24) and np.isfinite(pred).all()
 err=((pred[0]-y)**2+(pred[1]-y)**2)/2
 by=np.array([err[p==g].mean() for g in u])
 m=float(by.mean());p90=float(np.quantile(np.sqrt(by),.9))
 expect=r["arms"][arm]["metric"]
 assert abs(m-expect["mse"])<1e-14 and abs(p90-expect["p90"])<1e-14
 assert max(abs(float(by[pf==fi].mean())-expect["fold_mse"][fi]) for fi in range(5))<1e-14
 for fold in r["fold_records"]:
  records=fold["arms"][arm]["placement"]
  assert len(records)==16
 print("VERIFY",arm,"mse",m,"p90",p90,flush=True)
assert np.max(abs(q["original"]-q["operating64"]))<1e-13
print("PASS four arms, whole-patient metrics, 16 three-dose placements and baseline identity",flush=True)
