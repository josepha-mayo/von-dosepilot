"""Independent saved-state predictor and scorer. No fitting modules imported."""
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
import hashlib,json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];OUT=Path('/mnt/d/von-dosepilot-data/hierarchical64_20261008_run1')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
result=json.loads((OUT/'RESULT.json').read_text());z=np.load(OUT/'predictions_private.npz',allow_pickle=False)
assert sha(OUT/'predictions_private.npz')==result['prediction_sha256']
freeze=json.loads((ROOT/'study/HIERARCHICAL64_FREEZE.json').read_text())
for p,h in freeze['source'].items():assert sha(ROOT/p)==h
for p,h in freeze['inputs'].items():assert sha(Path(p))==h
maximum=0.;checked=0;model_hashes={}
for fold in range(5):
    paid=np.load(OUT/f'fold_{fold}_paid.npz',allow_pickle=False);ix=paid['indices']
    plan=json.loads((OUT/f'fold_{fold}_plan.json').read_text())
    assert len(set(plan['selected_native_indices']))==64
    for o in ('A','B'):
        plates=np.asarray(plan[f'orientation_{o}_plate_indices']);assert np.sum(plates==0)==32 and np.sum(plates==1)==32
    for arm in result['arms']:
        path=OUT/f'fold_{fold}_{arm}_model.npz';s=np.load(path,allow_pickle=False);model_hashes[path.name]=sha(path)
        for oi,o in enumerate(('A','B')):
            x=paid['paid_'+o];a=(x-s['canonical_mean'])/s['canonical_scale'];b=s['kernel_z']
            K=a@b.T
            for j in range(24):
                cols=np.flatnonzero(s['kernel_owner']==j)
                delta=a[:,None,cols]-b[None,:,cols]
                K+=len(cols)*np.exp(-np.sum(delta*delta,axis=2)/(2*len(cols)*.49))
            centered=K-(K@s['kernel_weights'])[:,None]-s['kernel_mean'][None,:]+s['kernel_grand']
            pred=s['mean_y_'+o]+((x-s['mean_x_'+o])/s['scale_x_'+o])@s['beta_'+o]+centered@s['coef']
            maximum=max(maximum,float(np.max(abs(pred-z[arm][oi,ix]))));checked+=pred.size
assert maximum<1e-12
p=z['patients'].astype(str);ids=np.unique(p);folds=z['folds'];y=z['y'];pf=np.asarray([folds[np.flatnonzero(p==g)[0]] for g in ids])
assert y.shape==(119,24) and len(ids)==59
for arm,details in result['arms'].items():
    error=((z[arm][0]-y)**2+(z[arm][1]-y)**2)/2
    losses=np.asarray([error[p==g].mean() for g in ids]);m=details['metrics']
    assert abs(losses.mean()-m['mse'])<1e-14
    assert abs(np.quantile(np.sqrt(losses),.9)-m['p90'])<1e-14
    assert max(abs(losses[pf==f].mean()-m['fold_mse'][f]) for f in range(5))<1e-14
assert result['outer_label_mutation_maxdiff']<1e-12 and result['outer_state_mutation_maxdiff']<1e-12
receipt={'status':'PASS','source_input_hashes_verified':True,'predictions_reconstructed':checked,'max_abs_difference':maximum,'models_checked':len(model_hashes),'model_sha256':model_hashes,'no_model_refits':True,'independent_validation':False}
with (OUT/'SAVED_STATE_VERIFICATION.json').open('x') as f:json.dump(receipt,f,indent=2);f.write('\n')
print(json.dumps({k:v for k,v in receipt.items() if k!='model_sha256'},indent=2),flush=True)
