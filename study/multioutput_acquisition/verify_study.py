"""Separate saved-array, full-solve acquisition and kernel reload verification."""
from pathlib import Path
import argparse,hashlib,json,math,datetime
import numpy as np


def mean(x):
    x=list(map(float,x));return math.fsum(x)/len(x)
def pm(pred,y,p):
    return np.array([[mean(((float(pred[0,i,j])-float(y[i,j]))**2+(float(pred[1,i,j])-float(y[i,j]))**2)/2 for i in np.flatnonzero(p==g)) for j in range(24)] for g in np.unique(p)])
def kernel_direct(query,m,owner):
    z=m['z_training'];out=query@z.T
    for j in range(24):
        ix=np.flatnonzero(owner==j)
        dist=((query[:,None,ix]-z[None,:,ix])**2).sum(2)
        out+=len(ix)*np.exp(-dist/(2*len(ix)))
    w=m['weights'];return out-(out@w)[:,None]-m['train_kernel_mean'][None,:]+m['kernel_grand']
def direct_risk(gram,cross,variance,s):
    h=gram[np.ix_(s,s)]+.1*np.eye(len(s));b=cross[s]
    # Augmented linear system solved directly, not the Schur block expression.
    solved=np.linalg.solve(h,b)
    return (variance-math.fsum((b*solved).ravel()))/24

def main():
    p=argparse.ArgumentParser()
    for n in ('run','cache','r18','output'):p.add_argument('--'+n,required=True,type=Path)
    a=p.parse_args();r=json.loads((a.run/'RESULT.json').read_text());checks=0;errmax=0.
    def eq(x,y,tol=1e-12):
        nonlocal checks,errmax
        error=float(np.max(np.abs(np.asarray(x,float)-np.asarray(y,float))));errmax=max(errmax,error)
        if error>tol:raise ValueError(f'Numerical discrepancy {error}')
        checks+=1
    with np.load(a.run/'predictions_private.npz',allow_pickle=False) as z:d={k:z[k].copy() for k in z.files}
    with np.load(a.cache,allow_pickle=False) as z:data={k:z[k].copy() for k in z.files}
    with np.load(a.r18,allow_pickle=False) as z:ref18=np.stack([z['candidate_A'],z['candidate_B']])
    y,pats,folds=d['y'],d['patients'],d['folds'];ids=np.unique(pats);pf=np.array([folds[np.flatnonzero(pats==g)[0]] for g in ids])
    assert np.array_equal(data['y'],y) and np.array_equal(data['patient_ids'],pats)
    scalars={};vectors={}
    for name,m in r['metrics'].items():
        pred=ref18 if name=='r18' else d[name]
        pt=pm(pred,y,pats);pv=np.array([mean(row) for row in pt]);vectors[name]=pv
        scalar={'mse':mean(pv),'p90':float(np.quantile(np.sqrt(pv),.9)), 'fold':[mean(pv[pf==f]) for f in range(5)],'ori':[mean(mean((q[pats==g]-y[pats==g]).ravel()**2) for g in ids) for q in pred]}
        scalars[name]=scalar
        eq(scalar['mse'],m['mse']);eq(scalar['p90'],m['p90_rmse']);eq(scalar['fold'],m['fold_mse']);eq(scalar['ori'],m['orientation_mse'])
        for j,n in enumerate(d['drug_ids']):eq(mean(pt[:,j]),m['target_mse'][n])
    for name,references in r['comparisons'].items():
        for ref,c in references.items():
            delta=vectors[name]-vectors[ref];cs,rs=scalars[name],scalars[ref];old=ref in ('r13','r18')
            wins=int((delta<0).sum());fw=sum(x<z for x,z in zip(cs['fold'],rs['fold']))
            eq(wins,c['patient_wins'],0);eq(int((delta>0).sum()),c['patient_losses'],0);eq(int((delta==0).sum()),c['ties'],0);eq(fw,c['fold_wins'],0)
            gate={'mse':cs['mse']<=.95*rs['mse'] if old else cs['mse']<rs['mse'],'patients':wins>=(40 if old else 30),'folds':fw>=(4 if old else 3),'p90':cs['p90']<=rs['p90']}
            if old:gate['each_orientation_below_reference_expected']=max(cs['ori'])<rs['mse']
            assert gate==c['gate'] and all(gate.values())==c['pass']
            rng=np.random.default_rng(20261002);idx=rng.integers(0,59,(10000,59));boot=[mean(delta[row]) for row in idx]
            eq(np.quantile(boot,[.025,.975]),c['descriptive_delta_ci95'])
    allproxy=0;proxyerr=0.;modelerr=0.;models=0
    for outer in range(5):
        folder=a.run/f'outer_{outer:02}';tr=np.flatnonzero(folds!=outer);te=folds==outer
        sel=json.loads((folder/'selection.json').read_text())
        with np.load(folder/'inner_predictions_private.npz',allow_pickle=False) as z:
            io=z['all_plans'];inner=z['inner_folds'];ip=z['patients'];iy=z['y']
            scores=np.array([[mean(pm(io[pi,ci],iy,ip).mean(1)) for ci in range(10)] for pi in (0,1)])
            eq(scores,sel['scores']);best=np.unravel_index(int(np.argmin(scores)),scores.shape)
            assert list(map(int,best))==sel['selection']['selected_plan']
        contexts=[(tr,folder/'plan_1.json')]+[(tr[inner!=k],folder/f'inner_{k:02}/fitting_only_sweep_plan.json') for k in range(3)]
        for fit,path in contexts:
            plan=json.loads(path.read_text());x=data['x'][fit];yp=y[fit];pp=pats[fit]
            ids_,inv,count=np.unique(pp,return_inverse=True,return_counts=True);w=np.tile(1./(len(ids_)*count[inv]),2)/2
            xfull=np.concatenate([x.reshape(len(x),-1),x[:,:,::-1].reshape(len(x),-1)]);yy=np.tile(yp,(2,1))
            mx=w@xfull;my=w@yy;scale=np.maximum(np.sqrt(w@(xfull-mx)**2),.05)
            z=(xfull-mx)/scale;target=yy-my;gram=(z.T*w)@z;cross=(z.T*w)@target;variance=float(np.sum(w@(target*target)))
            owner=np.asarray(plan['coordinate_target_indices']);plate=np.asarray(plan['orientation_A_plate_indices']);selected=np.asarray(plan['selected_native_indices']).copy()
            # One sweep touches each target once, so each block's previous
            # choices identify the starting plan without any fitting call.
            for j,row in enumerate(plan['search_records']):
                target_index=list(d['drug_ids']).index(row['target']);selected[owner==target_index]=row['previous_native_indices']
            previous=direct_risk(gram,cross,variance,2*selected+plate);eq(previous,plan['proxy_initial'])
            for row in plan['search_records']:
                j=list(d['drug_ids']).index(row['target']);pos=np.flatnonzero(owner==j)
                assert np.array_equal(selected[pos],row['previous_native_indices'])
                selected[pos]=row['selected_native_indices'];direct=direct_risk(gram,cross,variance,2*selected+plate)
                proxyerr=max(proxyerr,abs(direct-row['proxy_after']));assert direct<=previous+1e-12
                eq(direct,row['proxy_after']);previous=direct;allproxy+=1
            assert np.array_equal(selected,plan['selected_native_indices'])
        for pi in (0,1):
            plan=json.loads((folder/f'plan_{pi}.json').read_text());owner=np.asarray(plan['coordinate_target_indices']);native=np.asarray(plan['selected_native_indices'])
            for file in folder.glob(f'plan{pi}_model*_private.npz'):
                ci=int(file.name.split('_')[1][5:])
                with np.load(file,allow_pickle=False) as zz:m={k:zz[k].copy() for k in zz.files}
                selected_names=[name for name,pair in sel['selection'].items() if pair==[pi,ci]]
                for oi,o in enumerate(('A','B')):
                    pl=np.asarray(plan[f'orientation_{o}_plate_indices']);paid=data['x'][te][:,native,pl]
                    q=(paid-m['mean_x'])/m['scale_x'];got=m['mean_y']+q@m['beta']+kernel_direct(q,m,owner)@m['dual_coefficients']
                    for name in selected_names:
                        er=float(np.max(abs(got-d[name][oi,te])));modelerr=max(modelerr,er);assert er<1e-12
                models+=1
    result={'status':'PASS','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'metric_comparison_groups':checks,'max_metric_difference':errmax,'fitting_contexts_checked':20,'full_solve_acquisition_steps':allproxy,'max_direct_proxy_difference':proxyerr,'selected_model_artifacts_checked':models,'max_reloaded_prediction_difference':modelerr,'no_model_refit':True,'protected_response_access':False,'independent_biological_validation':False,'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'result_sha256':hashlib.sha256((a.run/'RESULT.json').read_bytes()).hexdigest()}
    with a.output.open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
