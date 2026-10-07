"""Fully outer-contained convex residual pooling; private arrays never published."""
from pathlib import Path
import argparse,datetime,hashlib,importlib.util,json,sys,itertools
import numpy as np
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
SPEC=importlib.util.spec_from_file_location('nested_parent72',HERE.parent/'budget72_bandwidth07_residual/run_study.py')
parent=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(parent)
EXPERT_OPTIONS=(0,2,5)
TOL=1e-15

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,j): Path(p).write_bytes((json.dumps(j,indent=2,allow_nan=False)+'\n').encode())

def solve_simplex(y,preds,patients):
    if preds.shape!=(3,2,len(y),y.shape[1]) or not np.isfinite(preds).all(): raise ValueError('prediction shape/finite')
    w=parent.patient_weights(patients)
    e=preds-y[None,None,:,:]
    G=np.einsum('aonq,bonq,n->ab',e,e,w)/(2*y.shape[1])
    candidates=[v.copy() for v in np.eye(3)]
    for i,j in itertools.combinations(range(3),2):
        den=G[i,i]+G[j,j]-2*G[i,j]
        if den>1e-20:
            a=float(np.clip((G[j,j]-G[i,j])/den,0,1))
            z=np.zeros(3);z[i]=a;z[j]=1-a;candidates.append(z)
    scale=max(float(np.max(np.abs(G))),1e-30)
    K=np.block([[G/scale,np.ones((3,1))],[np.ones((1,3)),np.zeros((1,1))]])
    z=np.linalg.lstsq(K,np.array([0.,0.,0.,1.]),rcond=1e-12)[0][:3]
    if np.min(z)>=-1e-12 and abs(z.sum()-1)<1e-9:
        z=np.maximum(z,0);z/=z.sum();candidates.append(z)
    best=min(enumerate(candidates),key=lambda q:(float(q[1]@G@q[1]),q[0]))[1]
    return best,{'gram':G.tolist(),'inner_mse':float(best@G@best),'active_candidates':len(candidates)}

def fit_outer(x,y,patients,catalog,folds,f):
    tr=np.flatnonzero(folds!=f);te=np.flatnonzero(folds==f)
    assert not set(patients[tr])&set(patients[te])
    inner,_=parent.patient_folds(patients[tr],3,parent.evaluate.SALT+f'|inner|{f}')
    oof=np.full((10,2,len(tr),24),np.nan)
    fit_checks=[]
    for k in range(3):
        fi=tr[inner!=k];va=tr[inner==k]
        assert not set(patients[fi])&(set(patients[va])|set(patients[te]))
        pp=parent.predict_options(x,va,parent.build_bundle(x,y,patients,catalog,fi))
        for oi in range(10):
            for orient in range(2): oof[oi,orient,inner==k,:]=pp[oi,orient]
        fit_checks.append({'inner_fold':k,'fit_patients':len(np.unique(patients[fi])),'validation_patients':len(np.unique(patients[va])),'outer_test_patients_in_fit':0})
    assert np.isfinite(oof).all()
    weights,solver=solve_simplex(y[tr],oof[list(EXPERT_OPTIONS)],patients[tr])
    scores=[]
    for oi in range(10):
        _,pt=parent.patient_target_losses(y[tr],oof[oi,0],oof[oi,1],patients[tr])
        scores.append(float(pt.mean()))
    chosen=int(np.argmin(scores))
    outer=parent.predict_options(x,te,parent.build_bundle(x,y,patients,catalog,tr))
    mixture=np.einsum('k,konq->onq',weights,outer[list(EXPERT_OPTIONS)])
    return mixture,outer[chosen],{'fold':f,'weights':weights.tolist(),'parent_option_index':chosen,'fit_checks':fit_checks,**solver}

def compare(y,ca,cb,ra,rb,patients,folds):
    cm=parent.metrics(y,ca,cb,patients,folds);rm=parent.metrics(y,ra,rb,patients,folds)
    pd=cm['patient_losses']-rm['patient_losses'];td=cm['target_mse']-rm['target_mse']
    rng=np.random.default_rng(20261007)
    boot=np.mean(pd[rng.integers(0,len(pd),size=(100000,len(pd)))],axis=1)
    c={'relative_mse_gain':float(1-cm['mse']/rm['mse']),'patient_wins':int(np.sum(pd<-TOL)),'patient_losses':int(np.sum(pd>TOL)),'patient_ties':int(np.sum(abs(pd)<=TOL)),'target_wins':int(np.sum(td<-TOL)),'target_losses':int(np.sum(td>TOL)),'target_ties':int(np.sum(abs(td)<=TOL)),'fold_wins':int(np.sum(np.array(cm['fold_mse'])<np.array(rm['fold_mse'])-TOL)),'p90_nonworse':cm['p90_patient_rmse']<=rm['p90_patient_rmse'],'bootstrap_95_ci':np.quantile(boot,[.025,.975]).tolist()}
    c['gate_pass']=cm['mse']<rm['mse']-TOL and c['patient_wins']>=30 and c['fold_wins']==5 and c['p90_nonworse']
    return cm,rm,c

def run(a):
    if a.output.exists(): raise ValueError('Existing output; no automatic retry')
    fr=json.loads((HERE/'FREEZE.json').read_text())
    for k,p in {'curves':a.curves,'catalog':a.catalog,'parent72':a.parent72,'scientific64':a.scientific64}.items():
        assert sha(p)==fr['input_sha256'][k],k
    for rel,h in {**fr['source_sha256'],**fr['dependency_sha256']}.items(): assert sha(ROOT/rel)==h,rel
    data,features,_=parent.load_prepared(a.curves,a.catalog)
    x=features['x_replicates'];y=data['y'];patients=data['patient_ids'].astype(str)
    cat=parent.bc.catalog_from_features(features)
    z=np.load(a.parent72,allow_pickle=False);s=np.load(a.scientific64,allow_pickle=False)
    folds=z['folds']
    for v in (z,s):
        assert np.array_equal(v['y'],y) and np.array_equal(v['patients'].astype(str),patients)
        assert np.array_equal(v['folds'],folds)
    assert np.array_equal(parent.patient_folds(patients,5,parent.evaluate.SALT+'|outer')[0],folds)
    pred=np.full((2,len(y),24),np.nan);replay=pred.copy();rows=[];isolation=None
    for f in range(5):
        pp,rr,row=fit_outer(x,y,patients,cat,folds,f)
        te=folds==f;pred[:,te]=pp;replay[:,te]=rr;rows.append(row)
        if f==0:
            changed=y.copy();changed[te]=123.0-y[te]*19
            pp2,rr2,row2=fit_outer(x,changed,patients,cat,folds,f)
            isolation=max(float(np.max(abs(pp2-pp))),float(np.max(abs(rr2-rr))),float(np.max(abs(np.array(row2['weights'])-row['weights']))))
            assert isolation<=1e-12,'Outer held-label influence detected'
        print(json.dumps({'event':'outer_complete','fold':f,'weights':row['weights']}),flush=True)
    maxdiff=max(float(np.max(abs(replay[0]-z['candidate_A']))),float(np.max(abs(replay[1]-z['candidate_B']))))
    assert maxdiff<=1e-12,'Parent replay differs'
    cm,rm,c72=compare(y,*pred,z['candidate_A'],z['candidate_B'],patients,folds)
    _,sm,c64=compare(y,*pred,s['candidate'][0],s['candidate'][1],patients,folds)
    clean=lambda m:{k:v for k,v in m.items() if k not in ('patient_losses','target_mse')}
    a.output.mkdir(parents=True,exist_ok=False)
    np.savez_compressed(a.output/'predictions_private.npz',candidate_A=pred[0],candidate_B=pred[1],parent_A=replay[0],parent_B=replay[1],y=y,patients=patients,folds=folds,sample_ids=data['sample_ids'],drug_ids=data['drug_ids'])
    result={'schema':'dosepilot.nested_residual_simplex.result.v1','status':'COMPLETE','candidate':clean(cm),'parent72':clean(rm),'scientific64':clean(sm),'candidate_vs_parent72':c72,'candidate_vs_scientific64':c64,'selection_records':rows,'checks':{'parent_prediction_maxdiff':maxdiff,'outer_label_mutation_maxdiff':isolation,'all_inner_fits_exclude_outer_test':True},'treatment_wells':72,'plate_wells':[36,36],'decision':'ELIGIBLE_FOR_REVIEW' if c72['gate_pass'] and c64['gate_pass'] else 'REJECT_FOR_PROMOTION','candidate_promotion_allowed':False,'protected22_access':False,'independent_validation':False,'selection_adjusted':False,'prediction_sha256':sha(a.output/'predictions_private.npz'),'freeze_sha256':sha(HERE/'FREEZE.json'),'finished_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
    dump(a.output/'RESULT.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='selection_records'},indent=2),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ('curves','catalog','parent72','scientific64','output'): p.add_argument('--'+name,type=Path,required=True)
    run(p.parse_args())
