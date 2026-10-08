"""Separately written conditional-risk, allocation and saved-prediction audit.
Does not import the candidate policy or fit any model. No biological-validation claim.
"""
from pathlib import Path
import os
os.environ['OPENBLAS_NUM_THREADS']='1'
import argparse,hashlib,json,sys,datetime
import numpy as np
from scipy.special import logsumexp
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'study'),str(ROOT/'study/engine')]
from compact_train import load_prepared
from methods import patient_folds
ARMS=('static_ridge','adaptive_ridge','static_mixture','adaptive_mixture')
SEED=202610080930

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load_npz(p):
    with np.load(p,allow_pickle=False) as z:return {k:z[k].copy() for k in z.files}
def conditional_components(means,cov,weights,indices,observed):
    a=np.asarray(indices,int);delta=observed[:,None,:]-means[None,:,a]
    caa=cov[np.ix_(a,a)];chol=np.linalg.cholesky(caa)
    solved=np.linalg.solve(chol,delta.reshape(-1,len(a)).T).T.reshape(delta.shape)
    logp=np.log(weights)[None,:]-.5*np.sum(solved*solved,axis=2)
    posterior=np.exp(logp-logsumexp(logp,axis=1,keepdims=True))
    transport=np.linalg.solve(caa,cov[a]);cm=means[None,:,:]+np.einsum('bni,id->bnd',delta,transport)
    cc=cov-cov[:,a]@transport
    return posterior,cm,(cc+cc.T)/2

def independent_risks(bank,j,seed,first,adaptive):
    pre=f't{j}_s{seed}_';means=bank[f't{j}_means'];cov=bank[f't{j}_covariance'];w=bank[f't{j}_weights'];q=bank[f't{j}_quadrature']
    a=bank[pre+'initial_physical'];betas=bank[pre+'betas'];biases=bank[pre+'intercepts'];extras=bank[pre+'physical_extra']
    if adaptive:posterior,cm,cc=conditional_components(means,cov,w,a,first)
    result=np.empty((len(first),len(extras)))
    for k,extra in enumerate(extras):
        functional=-q.copy()
        if k:functional[extra]+=betas[k,2]
        if adaptive:
            error_mean=biases[k]+(first@betas[k,:2])[:,None]+cm@functional
            result[:,k]=functional@cc@functional+np.sum(posterior*error_mean**2,axis=1)
        else:
            functional[a]+=betas[k,:2]
            result[:,k]=functional@cov@functional+w@((biases[k]+means@functional)**2)
    if not np.isfinite(result).all() or result.min()<-1e-10:raise ValueError('invalid reconstructed risks')
    return np.maximum(result,0)

def optimal_cost(cost):
    # Cost-only DP with different update/backtracking code from the policy.
    table=np.full((25,9,9),np.inf);table[0,0,0]=0
    for j in range(24):
        for a in range(9):
            for b in range(9):
                alternatives=[table[j,a,b]+cost[j,0]]
                if a:alternatives.append(table[j,a-1,b]+cost[j,1])
                if b:alternatives.append(table[j,a,b-1]+cost[j,2])
                table[j+1,a,b]=min(alternatives)
    return float(table[24,8,8])

def risks(pred,y,p):
    loss=((pred[0]-y)**2+(pred[1]-y)**2)/2
    return np.stack([loss[p==g].mean(0) for g in np.unique(p)])
def metrics(pred,y,p,folds):
    v=risks(pred,y,p).mean(1);pf=np.array([folds[np.flatnonzero(p==g)[0]] for g in np.unique(p)])
    return {'mse':float(v.mean()),'p90_patient_rmse':float(np.quantile(np.sqrt(v),.9)),
       'fold_mse':[float(v[pf==f].mean()) for f in range(5)]}

def verify(run,curves,catalog):
    result=json.loads((run/'RESULT.json').read_text(encoding='utf-8'));frpath=ROOT/'study/two_stage_risk64/FREEZE.json';fr=json.loads(frpath.read_text(encoding='utf-8'))
    assert result['status']=='COMPLETE' and result['primary_arm']=='adaptive_ridge'
    assert sha(frpath)==result['freeze_sha256'] and sha(curves)==fr['inputs']['curves'] and sha(catalog)==fr['inputs']['catalog']
    for path,h in fr['source_sha256'].items():assert sha(ROOT/path)==h,path
    assert sha(run/'predictions_private.npz')==result['prediction_sha256']
    saved=load_npz(run/'predictions_private.npz');data,feat,_=load_prepared(curves,catalog)
    y,p,folds=saved['y'],saved['patients'].astype(str),saved['folds']
    assert np.array_equal(y,data['y']) and np.array_equal(p,data['patient_ids'].astype(str))
    expected,_=patient_folds(p,5,'von-organoid-sentinel-v1|outer');assert np.array_equal(expected,folds)
    assert np.array_equal(saved['drug_ids'].astype(str),data['drug_ids'].astype(str))
    reconstructed={arm:np.full_like(saved[arm],np.nan) for arm in ARMS};hashes={};max_risk=0.;max_optimal=0.;deployments=0
    for f in range(5):
        bp=run/f'fold_{f}_bank_private.npz';tp=run/f'fold_{f}_trace_private.npz';bank=load_npz(bp);trace=load_npz(tp)
        hashes[bp.name]=sha(bp);hashes[tp.name]=sha(tp);ix=np.flatnonzero(folds==f)
        original=json.loads((run/f'fold_{f}_original_plan.json').read_text(encoding='utf-8'))
        for j in range(24):assert np.array_equal(bank[f't{j}_initial_native'],original['choices'][j]['best2'])
        for seed in (0,1):
            for adaptive,label in ((False,'static'),(True,'adaptive')):
                key=f'{label}_s{seed}';first=trace[key+'_initial'];actions=trace[key+'_actions'];last=trace[key+'_final'];cells=trace[key+'_physical_cells']
                assert first.shape==(len(ix),24,2) and actions.shape==(len(ix),24) and cells.shape==(len(ix),64,2)
                cost_tables=np.empty((len(ix),24,3));chosen_costs=np.empty((len(ix),24));preds={est:np.empty((len(ix),24)) for est in ('ridge','mixture')}
                for j in range(24):
                    pre=f't{j}_s{seed}_';native=bank[f't{j}_initial_native'];expected_values=feat['x_replicates'][ix][:,native,[seed,1-seed]]
                    assert np.array_equal(first[:,j],expected_values)
                    allrisks=independent_risks(bank,j,seed,first[:,j],adaptive)
                    plate_options=bank[pre+'option_plate'];cost_tables[:,j,0]=allrisks[:,0]
                    for plate in (0,1):cost_tables[:,j,plate+1]=allrisks[:,plate_options==plate].min(1)
                    chosen_costs[:,j]=allrisks[np.arange(len(ix)),actions[:,j]]
                    for option in np.unique(actions[:,j]):
                        rows=np.flatnonzero(actions[:,j]==option);paid=first[rows,j,:]
                        observed_indices=bank[pre+'initial_physical']
                        if option:
                            n=int(bank[pre+'option_native'][option]);plate=int(plate_options[option]);expected_extra=feat['x_replicates'][ix[rows],n,plate]
                            assert np.array_equal(last[rows,j],expected_extra)
                            paid=np.column_stack((paid,last[rows,j]));observed_indices=np.r_[observed_indices,bank[pre+'physical_extra'][option]]
                            err=float(np.max(np.abs(allrisks[rows,option]-cost_tables[rows,j,plate+1])))
                            max_risk=max(max_risk,err);assert err<1e-9,'follow-up not minimum risk on selected plate'
                        beta=bank[pre+'betas'][option,:paid.shape[1]];bias=bank[pre+'intercepts'][option]
                        preds['ridge'][rows,j]=bias+paid@beta
                        posterior,cm,unused=conditional_components(bank[f't{j}_means'],bank[f't{j}_covariance'],bank[f't{j}_weights'],observed_indices,paid)
                        preds['mixture'][rows,j]=np.sum(posterior*(cm@bank[f't{j}_quadrature']),axis=1)
                for i,row in enumerate(actions):
                    expected_cells=[]
                    for j in range(24):expected_cells.extend(zip(bank[f't{j}_initial_native'].tolist(),(seed,1-seed)))
                    for j,option in enumerate(row):
                        if option:expected_cells.append((int(bank[f't{j}_s{seed}_option_native'][option]),int(bank[f't{j}_s{seed}_option_plate'][option])))
                    assert np.array_equal(cells[i],np.asarray(expected_cells))
                    assert len(expected_cells)==64 and len(set(expected_cells))==64 and len({n for n,plate in expected_cells})==64
                    assert [sum(plate==k for n,plate in expected_cells) for k in (0,1)]==[32,32]
                    assert sum(row>0)==16;optimum=optimal_cost(cost_tables[i]);actual=float(chosen_costs[i].sum())
                    gap=abs(actual-optimum);max_optimal=max(max_optimal,gap);assert gap<1e-9
                    assert abs(actual/24-float(trace[key+'_predicted_risk'][i]))<1e-10
                    deployments+=1
                if not adaptive:assert np.array_equal(actions,np.repeat(actions[:1],len(actions),axis=0))
                for est in preds:reconstructed[label+'_'+est][seed,ix]=preds[est]
    max_prediction=max(float(np.max(abs(reconstructed[name]-saved[name]))) for name in ARMS)
    assert max_prediction<1e-12,max_prediction
    arms={};metric_difference=0.
    for name in ARMS:
        actual=metrics(reconstructed[name],y,p,folds);stored=result['arms'][name];ms=stored['metrics']
        md=max(abs(actual['mse']-ms['mse']),abs(actual['p90_patient_rmse']-ms['p90_patient_rmse']),max(abs(a-b) for a,b in zip(actual['fold_mse'],ms['fold_mse'])))
        metric_difference=max(metric_difference,md);assert md<1e-15
        for ref,key in (('retained64','vs_retained64'),('operating64','vs_operating64')):
            d=risks(reconstructed[name],y,p).mean(1)-risks(saved[ref],y,p).mean(1);rm=metrics(saved[ref],y,p,folds)
            wins=int(np.sum(d<-1e-15));fw=sum(a<b-1e-15 for a,b in zip(actual['fold_mse'],rm['fold_mse']));tail=actual['p90_patient_rmse']<=rm['p90_patient_rmse']+1e-15
            boot=d[np.random.default_rng(SEED).integers(len(d),size=(100000,len(d)))].mean(1)
            assert wins==stored[key]['patient_wins'] and fw==stored[key]['fold_wins'] and tail==stored[key]['p90_nonworse']
            np.testing.assert_allclose(np.quantile(boot,[.025,.975]),stored[key]['descriptive_bootstrap_95_ci'],atol=1e-15,rtol=0)
            gate=actual['mse']<rm['mse']-1e-15 and wins>=30 and fw==5 and tail;assert gate==stored[key]['gate_pass']
        arms[name]={'metrics':actual,'decision':stored['decision'],'half_error_numeric_target_met':stored['half_error_numeric_target_met']}
    assert result['network_attempts']==0 and not result['protected22_access'] and not result['kaggle_entry_changed']
    assert result['outer_mutation_actions_equal'] and result['outer_label_and_curve_state_maxdiff']<=1e-12 and result['outer_label_and_curve_prediction_maxdiff']<=1e-12
    audit={'schema':'dosepilot.two_stage_risk64.audit.v1','status':'PASS_INDEPENDENT_POLICY_AND_MODEL_REPLAY','arms':arms,
      'policy_deployments_checked':deployments,'outer_banks_replayed':5,'fold_arm_outputs_replayed':20,
      'selected_option_cost_maxdiff':max_risk,'allocation_optimality_maxdiff':max_optimal,'prediction_maxdiff':max_prediction,'metric_maxdiff':metric_difference,
      'source_hashes_checked':len(fr['source_sha256']),'component_file_sha256':hashes,'prediction_sha256':sha(run/'predictions_private.npz'),'result_sha256':sha(run/'RESULT.json'),
      'fresh_model_fit_performed':False,'independent_biological_validation':False,'sequential_lab_feasibility_validated':False,
      'single_round_workflow_preserved':False,'patient_arrays_published':False,'utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
    with (run/'INDEPENDENT_AUDIT.json').open('x',encoding='utf-8',newline='\n') as f:json.dump(audit,f,indent=2);f.write('\n')
    print(json.dumps({k:v for k,v in audit.items() if k!='component_file_sha256'},indent=2),flush=True);return audit

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--run',type=Path,required=True);ap.add_argument('--curves',type=Path,required=True);ap.add_argument('--catalog',type=Path,required=True)
    a=ap.parse_args();verify(a.run,a.curves,a.catalog)
