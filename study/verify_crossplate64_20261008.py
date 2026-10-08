#!/usr/bin/env python3
"""Independent numeric replay of frozen crossplate64 results without fitting."""
import hashlib,json
from pathlib import Path
import numpy as np

root=Path("/mnt/d/von-dosepilot-data/crossplate64_20261008_run1")
code=Path("/mnt/d/von-dosepilot-crossplate64-20261008/study/run_crossplate64_20261008.py")
receipt=json.loads((root/"RESULT.json").read_text())
z=np.load(root/"predictions_private.npz",allow_pickle=False)
y=z["y"];p=z["patients"].astype(str);folds=z["folds"]
u=np.unique(p)
pf=np.array([int(folds[np.flatnonzero(p==g)[0]]) for g in u])
assert y.shape==(119,24) and len(u)==59
h=hashlib.sha256(code.read_bytes()).hexdigest()
assert h==receipt["source_sha256"]
for k in (0,4,8):
    q=z[f"k{k}"]
    assert q.shape==(2,119,24) and np.isfinite(q).all()
    loss=((q[0]-y)**2+(q[1]-y)**2)/2
    ptl=np.array([loss[p==g].mean(axis=0) for g in u])
    pp=ptl.mean(axis=1)
    mm=float(pp.mean());tail=float(np.quantile(np.sqrt(pp),.9))
    r=receipt["new_arms"][str(k)]["metrics"]
    assert abs(mm-r["mse"])<1e-14 and abs(tail-r["p90"])<1e-14
    assert max(abs(float(pp[pf==f].mean())-r["fold_mse"][f]) for f in range(5))<1e-14
    assert all(x["arms"][str(k)]["physical_wells"]==64
        and x["arms"][str(k)]["native_distinct"]==64-k
        and x["arms"][str(k)]["plate_counts"]==[32,32]
        for x in receipt["fold_records"])
    print(f"VERIFY k={k} mse={mm:.15f} p90={tail:.12f}",flush=True)
assert float(np.max(np.abs(z["k0"]-z["operating64"])))<1e-13
assert not receipt["verified_2x"]
print("PASS independent numeric replay, original control reproduced, no 2x candidate",flush=True)
