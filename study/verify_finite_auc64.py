"""Independent saved-model arithmetic, no imports from candidate code."""
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
import argparse,hashlib,json
from pathlib import Path
import numpy as np

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main(out):
    result=json.loads((out/'RESULT.json').read_text());z=np.load(out/'predictions_private.npz',allow_pickle=False)
    if sha(out/'predictions_private.npz')!=result['prediction_sha256']:raise ValueError('prediction hash')
    y=z['y'];p=z['patients'].astype(str);folds=z['folds'];ids=np.unique(p)
    if y.shape!=(119,24) or len(ids)!=59:raise ValueError('population')
    pf=np.array([folds[np.flatnonzero(p==g)[0]] for g in ids]);maximum=0.;count=0
    for g in ids:
        if len(np.unique(folds[p==g]))!=1:raise ValueError('split patient')
    for arm in result['arms']:
        pred=np.full((2,119,24),np.nan)
        for f in range(5):
            s=np.load(out/f'fold_{f}_{arm}_model.npz',allow_pickle=False);paid=np.load(out/f'fold_{f}_paid.npz',allow_pickle=False)
            plan=json.loads((out/f'fold_{f}_plan.json').read_text());ix=paid['indices']
            if not np.array_equal(ix,np.flatnonzero(folds==f)):raise ValueError('query identity')
            if len(set(plan['selected_native_indices']))!=64 or len(plan['selected_native_indices'])!=64:raise ValueError('dose budget')
            if not np.array_equal(plan['selected_native_indices'],s['native']):raise ValueError('state dose identity')
            for oi,o in enumerate(('A','B')):
                pl=np.asarray(plan[f'orientation_{o}_plate_indices'])
                if np.count_nonzero(pl==0)!=32 or np.count_nonzero(pl==1)!=32 or not np.array_equal(pl,s['plate_'+o]):raise ValueError('plate budget')
                q=(paid[o]-s['mean_x'])/s['scale_x'];t=s['z'];K=q@t.T
                for j in range(24):
                    cols=np.flatnonzero(s['owner']==j)
                    d=((q[:,cols][:,None,:]-t[:,cols][None,:,:])**2).sum(2)
                    K+=len(cols)*np.exp(-d/(2*len(cols)*.49))
                centered=K-(K@s['weights'])[:,None]-s['kernel_mean'][None,:]+s['grand']
                pred[oi,ix]=s['intercept_'+o]+paid[o]@s['beta_raw_'+o]+centered@s['coef'];count+=len(ix)*24
        if not np.isfinite(pred).all():raise ValueError('incomplete replay')
        diff=float(np.max(abs(pred-z[arm])));maximum=max(maximum,diff)
        if diff>1e-12:raise ValueError('prediction replay')
        error=((pred[0]-y)**2+(pred[1]-y)**2)/2;per=np.array([error[p==g].mean() for g in ids])
        expected=result['arms'][arm]['metrics']
        if abs(per.mean()-expected['mse'])>1e-14 or abs(np.quantile(np.sqrt(per),.9)-expected['p90'])>1e-14:raise ValueError('metrics')
        if max(abs(per[pf==f].mean()-expected['fold_mse'][f]) for f in range(5))>1e-14:raise ValueError('fold metric')
    if np.max(abs(z['original']-z['operating64']))>1e-12:raise ValueError('control')
    if result['outer_mutation_maxdiff']>1e-12 or result['outer_state_maxdiff']>1e-12:raise ValueError('training exclusion')
    report={'status':'PASS','independent_numeric_model_replay':True,'predictions_reconstructed':count,'max_difference':maximum,'physical_budget_checked':True,'whole_patient_metrics_checked':True,'result_sha256':sha(out/'RESULT.json'),'verifier_sha256':sha(Path(__file__)),'independent_biological_validation':False}
    with (out/'VERIFICATION.json').open('x') as f:json.dump(report,f,indent=2);f.write('\n')
    print(json.dumps(report),flush=True)
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('out',type=Path);a=ap.parse_args();main(a.out)
