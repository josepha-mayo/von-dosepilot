"""Independent replay and measurement-cost audit. No candidate-module import."""
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
import argparse,hashlib,json
from pathlib import Path
import numpy as np

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main(out):
    r=json.loads((out/'RESULT.json').read_text());z=np.load(out/'predictions_private.npz',allow_pickle=False)
    if sha(out/'predictions_private.npz')!=r['prediction_sha256']:raise ValueError('prediction hash')
    y=z['y'];p=z['patients'].astype(str);folds=z['folds'];ids=np.unique(p);maximum=0.;count=0
    if y.shape!=(119,24) or len(ids)!=59:raise ValueError('population')
    for g in ids:
        if len(np.unique(folds[p==g]))!=1:raise ValueError('patient split')
    pf=np.array([folds[np.flatnonzero(p==g)[0]] for g in ids])
    baseerr=((z['scientific64'][0]-y)**2+(z['scientific64'][1]-y)**2)/2
    basemean=float(np.mean([baseerr[p==g].mean() for g in ids]));tier_checks={}
    for B in (64,80,96,112,128):
        predicted=np.full((2,119,24),np.nan)
        for f in range(5):
            state=np.load(out/f'fold_{f}_budget{B}_model.npz',allow_pickle=False)
            observed=np.load(out/f'fold_{f}_budget{B}_paid.npz',allow_pickle=False)
            plan=json.loads((out/f'fold_{f}_budget{B}_plan.json').read_text());ix=observed['indices']
            if not np.array_equal(ix,np.flatnonzero(folds==f)):raise ValueError('row identity')
            n=np.asarray(plan['selected_native_indices'],int);own=np.asarray(plan['coordinate_target_indices'],int)
            if len(n)!=B or len(set(n.tolist()))!=B or not np.array_equal(n,state['native']):raise ValueError('native budget')
            if int(state['budget'])!=B or state['mean_x'].shape!=(B,) or state['beta'].shape!=(B,24):raise ValueError('state budget')
            cards=np.bincount(own,minlength=24)
            if cards.min()<2 or cards.max()>6 or len(cards)!=24:raise ValueError('target accounting')
            for oi,o in enumerate(('A','B')):
                pl=np.asarray(plan[f'orientation_{o}_plate_indices'],int)
                if np.count_nonzero(pl==0)!=B//2 or np.count_nonzero(pl==1)!=B//2 or len(set(zip(n,pl)))!=B:raise ValueError('physical plate budget')
                if not np.array_equal(pl,state['plate_'+o]) or observed[o].shape!=(len(ix),B) or not np.isfinite(observed[o]).all():raise ValueError('paid input identity')
                q=(observed[o]-state['mean_x'])/state['scale_x'];t=state['kernel_z'];raw=q@t.T
                for j in range(24):
                    cols=np.flatnonzero(state['kernel_owner']==j)
                    dist=((q[:,cols][:,None,:]-t[:,cols][None,:,:])**2).sum(2)
                    raw+=len(cols)*np.exp(-dist/(2*len(cols)*.49))
                K=raw-(raw@state['kernel_weights'])[:,None]-state['kernel_mean'][None,:]+state['kernel_grand']
                predicted[oi,ix]=state['mean_y']+q@state['beta']+K@state['coef'];count+=len(ix)*24
        if not np.isfinite(predicted).all():raise ValueError('incomplete replay')
        difference=float(np.max(abs(predicted-z[f'budget{B}'])));maximum=max(maximum,difference)
        if difference>1e-12:raise ValueError('model replay mismatch')
        e=((predicted[0]-y)**2+(predicted[1]-y)**2)/2;per=np.array([e[p==g].mean() for g in ids]);mse=float(per.mean());p90=float(np.quantile(np.sqrt(per),.9))
        tier=r['tiers'][str(B)];expected=tier['metrics']
        if abs(mse-expected['mse'])>1e-14 or abs(p90-expected['p90'])>1e-14:raise ValueError('metric mismatch')
        if max(abs(float(per[pf==f].mean())-expected['fold_mse'][f]) for f in range(5))>1e-14:raise ValueError('fold metric')
        if abs(basemean/mse-tier['mse_improvement_factor_vs64'])>1e-12:raise ValueError('improvement ratio')
        if tier['treatment_wells']!=B or tier['additional_treatment_wells']!=B-64 or tier['well_count_ratio_vs64']!=B/64:raise ValueError('hidden measurement cost')
        if B>64 and (tier['same_budget_half_error_met'] or tier['comparison_is_cost_matched']):raise ValueError('invalid same-budget claim')
        tier_checks[str(B)]={'mse':mse,'p90':p90,'treatment_wells':B,'error_reduction_factor_vs64':basemean/mse,'added_wells':B-64}
    if np.max(abs(z['budget64']-z['operating64']))>1e-12:raise ValueError('operating control')
    if r['outer_mutation_maxdiff']>1e-12 or r['outer_state_maxdiff']>1e-12:raise ValueError('training exclusion')
    report={'status':'PASS','independent_model_replay':True,'predictions_reconstructed':count,'max_difference':maximum,'budgets_individually_verified':[64,80,96,112,128],'tiers':tier_checks,'same_budget_2x_achieved':False,'result_sha256':sha(out/'RESULT.json'),'verifier_sha256':sha(Path(__file__)),'independent_biological_validation':False}
    with (out/'VERIFICATION.json').open('x') as f:json.dump(report,f,indent=2);f.write('\n')
    print(json.dumps(report,indent=2),flush=True)
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('out',type=Path);a=ap.parse_args();main(a.out)
