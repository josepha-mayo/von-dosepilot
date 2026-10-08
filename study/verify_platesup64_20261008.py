#!/usr/bin/env python3
"""Verify frozen dual-plate auxiliary output results, no fitting or access to models."""
import hashlib,json
from pathlib import Path
import numpy as np
out=Path("/mnt/d/von-dosepilot-data/platesup64_20261008_run1")
src=Path("/mnt/d/von-dosepilot-platesup64-20261008/study/run_platesup64_20261008.py")
r=json.loads((out/"RESULT.json").read_text())
z=np.load(out/"predictions_private.npz",allow_pickle=False)
y=z["y"];patients=z["patients"].astype(str);folds=z["folds"]
ids=np.unique(patients)
pf=np.array([folds[np.flatnonzero(patients==g)[0]] for g in ids])
assert y.shape==(119,24) and len(ids)==59
assert hashlib.sha256(src.read_bytes()).hexdigest()==r["source_sha256"]
for arm in ("mean24","plate48","orthogonal48","weakcontrast48"):
 q=z[arm]
 assert q.shape==(2,119,24) and np.isfinite(q).all()
 error=((q[0]-y)**2+(q[1]-y)**2)/2
 by=np.array([error[patients==g].mean() for g in ids])
 mse=float(by.mean());p90=float(np.quantile(np.sqrt(by),.9))
 m=r["arms"][arm]["metrics"]
 assert abs(mse-m["mse"])<1e-14 and abs(p90-m["p90"])<1e-14
 assert max(abs(float(by[pf==fi].mean())-m["fold_mse"][fi]) for fi in range(5))<1e-14
 print("VERIFY",arm,mse,p90,flush=True)
assert np.max(abs(z["mean24"]-z["operating64"]))<1e-12
assert all(not r["arms"][arm]["eligible"] for arm in ("plate48","orthogonal48","weakcontrast48"))
print("PASS four arms, full held-patient replay, reference equality, zero promotion",flush=True)
