#!/usr/bin/env python3
"""No-refit arithmetic verifier for a completed Mahalanobis-additive study."""
from pathlib import Path
import argparse,json,hashlib,numpy as np

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def pt(pred,y,p):
    e=((pred[0]-y)**2+(pred[1]-y)**2)/2
    return np.stack([e[p==g].mean(0) for g in np.unique(p)])

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    a=ap.parse_args()
    if a.output.exists():raise ValueError('Output exists')
    result=json.loads((a.run/'RESULT.json').read_text())
    with np.load(a.run/'predictions_private.npz',allow_pickle=False) as z:
        d={k:z[k].copy() for k in z.files}
    y,p,folds=d['y'],d['patients'].astype(str),d['folds'];ids=np.unique(p)
    pf=np.array([folds[np.flatnonzero(p==g)[0]] for g in ids])
    checks=0;maxerr=0.
    for name in ('mahalanobis','bandwidth07','r13'):
        risk=pt(d[name],y,p);per=risk.mean(1);m=result['metrics'][name]
        vals=[(float(per.mean()),m['mse']),(float(np.quantile(np.sqrt(per),.9)),m['p90_rmse'])]
        for observed,recorded in vals:
            err=abs(observed-recorded);maxerr=max(maxerr,err);checks+=1
            if err>1e-14:raise ValueError('Metric mismatch')
        folds_now=[float(per[pf==f].mean()) for f in range(5)]
        err=float(np.max(np.abs(np.array(folds_now)-np.array(m['fold_mse']))));maxerr=max(maxerr,err);checks+=1
        if err>1e-14:raise ValueError('Fold mismatch')
    if sha(a.run/'predictions_private.npz')!=result['prediction_sha256']:
        raise ValueError('Prediction hash mismatch')
    out={'status':'PASS','metric_groups':checks,'maximum_metric_difference':maxerr,
         'prediction_sha256':result['prediction_sha256'],'fit_routine_called':False,
         'protected_response_access':False,'independent_validation':False}
    a.output.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
if __name__=='__main__':main()
