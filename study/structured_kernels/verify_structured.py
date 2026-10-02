#!/usr/bin/env python3
"""Independent arithmetic, explicit-pair kernels and direct linear-system audit.

The fitting procedure is not called. The prepared Lib1 CSV is reread only to
reconstruct purchased query values for model reload checks. No workbook or
protected-cohort response is opened.
"""
from pathlib import Path
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
import argparse,hashlib,json,math,sys,datetime
import numpy as np


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def avg(x):
    x=list(map(float,x));return math.fsum(x)/len(x)
def patient_matrix(pred,y,p):
    rows=[]
    for name in sorted(set(p)):
        ix=np.flatnonzero(p==name)
        rows.append([avg((((float(pred[0,i,j])-float(y[i,j]))**2+
                           (float(pred[1,i,j])-float(y[i,j]))**2)/2) for i in ix) for j in range(24)])
    return np.array(rows)
def raw_kernel(query,model,kind):
    train=model['z_training'];w=model['weights'];owner=model['kernel_owner'];n=len(train)
    linear=query@train.T
    if kind=='mean_shape':
        nonlinear=np.zeros_like(linear)
        for j in range(24):
            ix=np.flatnonzero(owner==j);q,t=query[:,ix],train[:,ix];qm=q.mean(1);tm=t.mean(1)
            qc=q-qm[:,None];tc=t-tm[None,:] if False else t-tm[:,None]
            first=np.exp(-((qm[:,None]-tm[None,:])**2)/2)
            second=np.exp(-((qc[:,None,:]-tc[None,:,:])**2).sum(2)/(2*(len(ix)-1)))
            nonlinear+=len(ix)/2*(first+second)
        return linear+nonlinear
    parts=[];trainparts=[]
    for j in range(24):
        ix=np.flatnonzero(owner==j);q,t=query[:,ix],train[:,ix]
        kg=np.exp(-((t[:,None,:]-t[None,:,:])**2).sum(2)/(2*len(ix)))
        kq=np.exp(-((q[:,None,:]-t[None,:,:])**2).sum(2)/(2*len(ix)))
        m=w@kg;g=float(m@w)
        parts.append(len(ix)*(kq-(kq@w)[:,None]-m[None,:]+g))
        trainparts.append(len(ix)*(kg-(kg@w)[:,None]-m[None,:]+g))
    main=sum(parts);pairs=np.zeros_like(main);p_train=np.zeros((n,n))
    for j in range(24):
        for k in range(j+1,24):
            pairs+=parts[j]*parts[k];p_train+=trainparts[j]*trainparts[k]
    a_train=sum(trainparts);ep=float(w@np.diag(p_train));scale=float(w@np.diag(a_train))/ep if ep>1e-14 else 0.
    if abs(scale-float(model['pair_scale']))>1e-10:raise ValueError('Independent pair-energy mismatch')
    return linear+.5*main+.5*scale*pairs


def run(a):
    out=a.run;record=json.loads((out/'RESULT.json').read_text());checks={};maxerr=0.;checks_n=0
    def check(name,x,y,tol=1e-13):
        nonlocal maxerr,checks_n
        error=float(np.max(np.abs(np.asarray(x,dtype=float)-np.asarray(y,dtype=float))))
        maxerr=max(maxerr,error);checks[name]=error<=tol;checks_n+=1
    with np.load(out/'predictions_private.npz',allow_pickle=False) as z:values={k:z[k].copy() for k in z.files}
    y,p,f=values['y'],values['patients'],values['folds'];ids=sorted(set(p));pf=np.array([f[np.flatnonzero(p==g)[0]] for g in ids])
    require=lambda ok,msg:None if ok else (_ for _ in ()).throw(ValueError(msg))
    require(sha(out/'predictions_private.npz')==record['prediction_sha256'],'Prediction digest changed')
    require(y.shape==(119,24) and len(ids)==59 and len(set(values['sample_ids']))==119,'Frame changed')
    metrics={};loss={}
    for name,m in record['metrics'].items():
        pt=patient_matrix(values[name],y,p);pp=np.array([avg(row) for row in pt]);loss[name]=pp
        metrics[name]={'mse':avg(pp),'p90':float(np.quantile(np.sqrt(pp),.9)),'folds':[avg(pp[pf==k]) for k in range(5)],
                       'target':[avg(pt[:,j]) for j in range(24)],'ori':[avg(avg((values[name][oi,p==g]-y[p==g]).ravel()**2) for g in ids) for oi in range(2)]}
        mm=metrics[name];check(name+'/mse',mm['mse'],m['mse']);check(name+'/p90',mm['p90'],m['p90_rmse']);check(name+'/folds',mm['folds'],m['fold_mse']);check(name+'/orientation',mm['ori'],m['orientation_mse'])
        for j,target in enumerate(values['drug_ids']):check(name+'/target/'+str(target),mm['target'][j],m['target_mse'][str(target)])
    r18=json.loads(a.r18.read_text());loss['r18']=np.array([r18['patient_expected_mse'][g] for g in ids]);metrics['r18']={'mse':avg(loss['r18']),'p90':float(np.quantile(np.sqrt(loss['r18']),.9)),'folds':[avg(loss['r18'][pf==k]) for k in range(5)]}
    for arm,comparisons in record['comparisons'].items():
        for ref,r in comparisons.items():
            delta=loss[arm]-loss[ref];cm,rm=metrics[arm],metrics[ref];win=int((delta<0).sum());fw=sum(x<z for x,z in zip(cm['folds'],rm['folds']));old=ref in ('r13','r18')
            check(arm+'/'+ref+'/wins',win,r['patient_wins'],0);check(arm+'/'+ref+'/losses',int((delta>0).sum()),r['patient_losses'],0)
            check(arm+'/'+ref+'/ties',int((delta==0).sum()),r['patient_ties'],0);check(arm+'/'+ref+'/fold_wins',fw,r['fold_wins'],0)
            check(arm+'/'+ref+'/gain',1-cm['mse']/rm['mse'],r['relative_gain'])
            gate={'mse':cm['mse']<=.95*rm['mse'] if old else cm['mse']<rm['mse'],'patient_wins':win>=(40 if old else 30),'fold_wins':fw>=(4 if old else 3),'p90':cm['p90']<=rm['p90']}
            if old:gate['both_orientation_means_below_reference_expected']=max(cm['ori'])<rm['mse']
            require(gate==r['gate'],'Gate discrepancy '+arm+'/'+ref)
            check(arm+'/'+ref+'/pass',all(gate.values()),r['passes_all'],0)
            rng=np.random.default_rng(20261002);rows=rng.integers(0,59,(10000,59));boot=np.array([avg(delta[row]) for row in rows])
            check(arm+'/'+ref+'/interval',np.quantile(boot,[.025,.975]),r['descriptive_delta_ci95'])
        require((record['decisions'][arm]=='ELIGIBLE_RESEARCH_SUCCESSOR')==all(c['passes_all'] for c in comparisons.values()),'Decision mismatch')
    for k in range(5):
        folder=out/f'outer_{k:02}';selection=json.loads((folder/'selection.json').read_text())
        with np.load(folder/'inner_oof_private.npz',allow_pickle=False) as z:
            for family in ('additive','s2','pair_mix','mean_shape'):
                scores=[avg(patient_matrix(pred,z['y'],z['patients']).mean(1)) for pred in z[family]]
                check(f'inner{k}/{family}/scores',scores,selection['inner_mse'][family])
                opts=[('identity',0.)]+[(ff,ll) for ff in (.1,.3,.6) for ll in (.1,1.,10.)]
                chosen=min(range(10),key=lambda i:(scores[i],i))
                require(list(opts[chosen])==selection['selected'][family],'Selection mismatch')
    # Model checks use prepared TRAIN only, not raw workbook, and never refit.
    sys.path[:0]=[str(a.study),str(a.study/'engine')]
    from compact_train import load_prepared
    from coverage_methods import acquire
    data,features,_=load_prepared(a.curves,a.study/'TRAIN_CATALOG.json')
    require(np.array_equal(data['sample_ids'],values['sample_ids']) and np.array_equal(data['y'],y),'Prepared input mismatch')
    kernel_error=dual_error=prediction_error=0.;model_count=0
    for k in range(5):
        folder=out/f'outer_{k:02}';te=f==k;plan=json.loads((folder/'plan.json').read_text());sel=json.loads((folder/'selection.json').read_text())
        for arm in ('pair_mix','mean_shape'):
            with np.load(folder/(arm+'_model_private.npz'),allow_pickle=False) as z:m={n:z[n].copy() for n in z.files}
            raw=raw_kernel(m['z_training'],m,arm);w=m['weights'];h=np.eye(len(w))-np.ones((len(w),1))*w[None,:];center=h@raw@h.T
            require(np.max(np.abs(w@center))<1e-10,'Centering failed')
            querymean=w@raw;grand=float(querymean@w)
            kernel_error=max(kernel_error,float(np.max(np.abs(querymean-m['train_kernel_mean']))))
            fraction,penalty=sel['selected'][arm]
            if fraction!='identity':
                sw=np.sqrt(w);gram=sw[:,None]*center*sw[None,:];r=m['residual_training_private'];wr=sw[:,None]*r
                solution=np.linalg.solve(gram+penalty*np.eye(len(w)),wr)
                summary=wr.T@gram@solution;e,v=np.linalg.eigh((summary+summary.T)/2);order=np.argsort(e)[::-1];s=np.sqrt(np.maximum(e[order],0.));v=v[:,order]
                ratio=np.divide(np.maximum(s-fraction*s[0],0.),s,out=np.zeros_like(s),where=s>1e-15)
                direct=(sw[:,None]*solution)@((v*ratio)@v.T)
            else:direct=np.zeros_like(m['dual_coefficients'])
            dual_error=max(dual_error,float(np.max(abs(center@direct-center@m['dual_coefficients']))))
            for oi,o in enumerate(('A','B')):
                paid=acquire(features['x_replicates'][te],plan,o);query=(paid-m['mean_x'])/m['scale_x']
                cross=raw_kernel(query,m,arm);cross=cross-(cross@w)[:,None]-querymean[None,:]+grand
                reconstructed=m['mean_y']+query@m['beta']+cross@direct
                err=float(np.max(abs(reconstructed-values[arm][oi,te])));prediction_error=max(prediction_error,err)
                require(err<1e-11,'Held-patient model reload discrepancy')
            model_count+=1
    require(kernel_error<1e-10 and dual_error<1e-11 and all(checks.values()),'Numerical audit discrepancy')
    report={'status':'PASS','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'comparison_groups':checks_n,'max_metric_difference':maxerr,'selected_model_checks':model_count,'independent_kernel_center_max_difference':kernel_error,'direct_solve_prediction_max_difference':dual_error,'held_patient_prediction_max_difference':prediction_error,'all_declared_gates_recomputed':True,'old_r18_summary_only':True,'same_coordinator_not_independent_peer_review':True,'model_fit_called':False,'prepared_train_reread_for_reload':True,'original_workbook_opened':False,'protected_response_access':False,'exact_result_sha256':sha(out/'RESULT.json'),'exact_prediction_sha256':sha(out/'predictions_private.npz'),'code_sha256':sha(__file__)}
    with a.output.open('x') as fp:json.dump(report,fp,indent=2)
    print(json.dumps(report,indent=2))
if __name__=='__main__':
    ap=argparse.ArgumentParser()
    for n in ('run','r18','study','curves','output'):ap.add_argument('--'+n,type=Path,required=True)
    run(ap.parse_args())
