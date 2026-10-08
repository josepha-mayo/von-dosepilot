"""Independent student replay and nested teacher membership audit."""
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
import argparse,hashlib,json
from pathlib import Path
import numpy as np

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def audit_teachers(receipts,allowed):
    assigned=[]
    for teacher in receipts:
        fit=set(teacher['fit_patients']);val=set(teacher['soft_label_patients'])
        if fit&val or fit|val!=allowed:raise ValueError('teacher fitting/label patient contamination')
        assigned.extend(val)
    if sorted(assigned)!=sorted(allowed):raise ValueError('each fitting patient needs exactly one teacher holdout')

def main(out):
    r=json.loads((out/'RESULT.json').read_text());z=np.load(out/'predictions_private.npz',allow_pickle=False)
    if sha(out/'predictions_private.npz')!=r['prediction_sha256']:raise ValueError('prediction hash')
    y=z['y'];p=z['patients'].astype(str);folds=z['folds'];ids=np.unique(p);count=0;maximum=0.
    if y.shape!=(119,24) or len(ids)!=59:raise ValueError('population')
    pf=np.array([folds[np.flatnonzero(p==g)[0]] for g in ids])
    for f in range(5):
        rec=json.loads((out/f'fold_{f}_record.json').read_text());train=set(rec['train_patients']);test=set(rec['test_patients'])
        if train&test or train!=set(p[folds!=f]) or test!=set(p[folds==f]):raise ValueError('outer membership')
        audit_teachers(rec['outer_teachers'],train)
        for inner in rec['inner_teachers']:
            fit=set(inner['student_train_patients']);val=set(inner['student_validation_patients'])
            if fit&val or fit|val!=train:raise ValueError('student inner membership')
            audit_teachers(inner['teachers'],fit)
    for arm in r['arms']:
        prediction=np.full((2,119,24),np.nan)
        for f in range(5):
            s=np.load(out/f'fold_{f}_{arm}_model.npz',allow_pickle=False);paid=np.load(out/f'fold_{f}_paid.npz',allow_pickle=False)
            plan=json.loads((out/f'fold_{f}_plan.json').read_text());ix=paid['indices']
            if int(s['budget'])!=64 or len(set(plan['selected_native_indices']))!=64 or not np.array_equal(plan['selected_native_indices'],s['native']):raise ValueError('student measurement budget')
            if not np.array_equal(ix,np.flatnonzero(folds==f)):raise ValueError('prediction membership')
            for oi,o in enumerate(('A','B')):
                pl=np.asarray(plan[f'orientation_{o}_plate_indices'])
                if np.count_nonzero(pl==0)!=32 or np.count_nonzero(pl==1)!=32 or paid[o].shape!=(len(ix),64):raise ValueError('physical paid count')
                q=(paid[o]-s['mean_x'])/s['scale_x'];t=s['kernel_z'];raw=q@t.T
                for j in range(24):
                    cols=np.flatnonzero(s['kernel_owner']==j);distance=((q[:,cols][:,None,:]-t[:,cols][None,:,:])**2).sum(2)
                    raw+=len(cols)*np.exp(-distance/(2*len(cols)*.49))
                K=raw-(raw@s['kernel_weights'])[:,None]-s['kernel_mean'][None,:]+s['kernel_grand']
                prediction[oi,ix]=s['mean_y']+q@s['beta']+K@s['coef'];count+=len(ix)*24
        diff=float(np.max(abs(prediction-z[arm])));maximum=max(maximum,diff)
        if diff>1e-12 or not np.isfinite(prediction).all():raise ValueError('student replay')
        e=((prediction[0]-y)**2+(prediction[1]-y)**2)/2;per=np.array([e[p==g].mean() for g in ids]);met=r['arms'][arm]['metrics']
        if abs(per.mean()-met['mse'])>1e-14 or abs(np.quantile(np.sqrt(per),.9)-met['p90'])>1e-14:raise ValueError('student metrics')
        if max(abs(per[pf==f].mean()-met['fold_mse'][f]) for f in range(5))>1e-14:raise ValueError('fold metrics')
    if np.max(abs(z['raw']-z['operating64']))>1e-12 or r['outer_mutation_maxdiff']>1e-12 or r['outer_state_maxdiff']>1e-12:raise ValueError('control or isolation check')
    report={'status':'PASS','independent_student_model_replay':True,'teacher_patient_separation_audited':True,'student_inference_wells':64,'predictions_reconstructed':count,'maximum_difference':maximum,'result_sha256':sha(out/'RESULT.json'),'verifier_sha256':sha(Path(__file__)),'independent_biological_validation':False}
    with (out/'VERIFICATION.json').open('x') as f:json.dump(report,f,indent=2);f.write('\n')
    print(json.dumps(report),flush=True)
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('out',type=Path);a=ap.parse_args();main(a.out)
