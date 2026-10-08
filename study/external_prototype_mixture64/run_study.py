#!/usr/bin/env python3
from __future__ import annotations
import os
for name in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS'):os.environ[name]='1'
import argparse,csv,importlib.util,json,sys,traceback,platform,socket,time
from pathlib import Path
import numpy as np
from threadpoolctl import threadpool_limits
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];STUDY=ROOT/'study'
spec=importlib.util.spec_from_file_location('existing_gaussian_kernel_helpers',STUDY/'global_conditional_curve64/run_study.py')
g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
sys.path.insert(0,str(HERE))
from model import external_covariance,relative_correlation,fit_target,condition,mixture_population,condition_mixture,predict_mixture
ARMS=('operating_reproduction','matched_moment_control','external_prototype_mixture')
SEED=202610080028
NETWORK=[]
def deny(*a,**kw):NETWORK.append('blocked');raise RuntimeError('network disabled while biological inputs are active')


def dose_metadata(curves,catalog,full,source_cov):
    grids={str(name):set() for name in catalog.target_ids}
    with Path(curves).open(encoding='utf-8',newline='') as f:
        for row in csv.DictReader(f):
            if row['library_id']!='lib1' or row['drug_id'] not in grids:raise ValueError('unauthorized curve metadata')
            grids[row['drug_id']].add(float(row['dose_nM']))
    metadata=[]
    for j,target in enumerate(catalog.target_ids):
        native=np.flatnonzero(full['owner']==j);doses=np.array(sorted(grids[str(target)]))
        if len(native)!=len(doses) or (doses<=0).any():raise ValueError('full target-grid mismatch')
        t=np.log(doses);positions=(t-t[0])/(t[-1]-t[0])
        physical=np.column_stack((2*native,2*native+1)).reshape(-1)
        glob_to_local=np.full(len(full['owner']),-1,int);glob_to_local[native]=np.arange(len(native))
        metadata.append({'native':native,'quadrature':full['q'][physical,j],
           'source_correlation':relative_correlation(source_cov,positions),'glob_to_local':glob_to_local,
           'positions':positions})
    return metadata


def conditional_state(full,p,ix,plan,metadata,strength,mixture=False):
    own=np.asarray(plan['coordinate_target_indices']);native=np.asarray(plan['selected_native_indices'])
    means=np.zeros(24);states={o:{'mean_x':np.zeros(64),'scale_x':np.ones(64),'beta':np.zeros((64,24))} for o in ('A','B')}
    mixtures={o:[] for o in ('A','B')}
    for target,meta in enumerate(metadata):
        model=fit_target(full['values'][ix][:,meta['native'],:],p[ix],meta['source_correlation'],strength)
        mixed=mixture_population(model,full['values'][ix][:,meta['native'],:],p[ix],meta['positions'],meta['source_bank']) if mixture else None
        cols=np.flatnonzero(own==target)
        local=meta['glob_to_local'][full['query_to_full'][native[cols]]]
        if (local<0).any():raise ValueError('target ownership mismatch')
        for o in ('A','B'):
            plate=np.asarray(plan[f'orientation_{o}_plate_indices'])[cols]
            fitted=condition(model,2*local+plate,meta['quadrature'])
            states[o]['mean_x'][cols]=fitted['mean_x'];states[o]['beta'][cols,target]=fitted['beta']
            means[target]=fitted['mean_y']
            if mixture:
                ms=condition_mixture(mixed,2*local+plate,meta['quadrature']);ms['columns']=cols.copy();mixtures[o].append(ms)
    result={'mean_y':means,'orientations':states}
    if mixture:result['mixtures']=mixtures
    return result


def base_prediction(base,state,paid,o):
    if state is None:return base.predict(paid)
    if 'mixtures' in state:
        return np.column_stack([predict_mixture(m,paid[:,m['columns']]) for m in state['mixtures'][o]])
    s=state['orientations'][o]
    return state['mean_y']+(paid-s['mean_x'])@s['beta']


def build(x,y,p,catalog,full,metadata,ix):
    plan=g.plan_panel_fast(x[ix],y[ix],p[ix],catalog);g.validate_plan(plan,catalog)
    a,b=[g.acquire(x[ix],plan,o) for o in ('A','B')]
    ctx=g.fit_prediction_context(a,b,y[ix],p[ix],plan,catalog.target_ids);base=g.CoveragePredictor(ctx,plan,.01)
    z=(np.r_[a,b]-base.mean_x)/base.scale_x
    ids,inv,count=np.unique(p[ix],return_inverse=True,return_counts=True);w=np.tile(1./(len(ids)*count[inv]),2)/2
    owner=np.asarray(plan['coordinate_target_indices'],int);variants=[]
    for arm,strength in zip(ARMS,(None,.5,.5)):
        state=None if strength is None else conditional_state(full,p,ix,plan,metadata,strength,mixture=(arm=='external_prototype_mixture'))
        pa=base_prediction(base,state,a,'A');pb=base_prediction(base,state,b,'B')
        residual=np.r_[y[ix]-pa,y[ix]-pb]
        kernel=g.BandwidthAdditive(z,residual,w,owner,.7)
        coefs=[np.zeros_like(residual)]+[kernel.coefficients(l,f)[0] for f,l in g.OPTIONS[1:]]
        variants.append({'name':arm,'state':state,'kernel':kernel,'coefs':coefs})
    return {'plan':plan,'base':base,'variants':variants}


def predict_all(x,ix,bundle):
    out=np.empty((3,10,2,len(ix),24));base=bundle['base']
    for oi,o in enumerate(('A','B')):
        paid=g.acquire(x[ix],bundle['plan'],o);normalized=(paid-base.mean_x)/base.scale_x
        for vi,v in enumerate(bundle['variants']):
            bp=base_prediction(base,v['state'],paid,o);cross=v['kernel'].centered_cross(normalized)
            for k,c in enumerate(v['coefs']):out[vi,k,oi]=bp+cross@c
    return out


def pack_payload(bundle,selected):
    payload=g.payload(bundle,selected)
    variant=bundle['variants'][selected//10]
    nonlinear=variant['state'] is not None and 'mixtures' in variant['state']
    payload['mixture_flag']=np.asarray(int(nonlinear))
    if nonlinear:
        for o in ('A','B'):
            for j,m in enumerate(variant['state']['mixtures'][o]):
                for key,value in m.items():payload[f'{o}_mixture_{j}_{key}']=np.asarray(value)
    return payload


def predict_payload(state,paid,o):
    ordinary=g.predict_payload(state,paid,o)
    if not int(state['mixture_flag']):return ordinary
    gaussian=state['mean_y_'+o]+((paid-state['mean_x_'+o])/state['scale_x_'+o])@state['beta_'+o]
    result=[]
    for j in range(24):
        m={key:state[f'{o}_mixture_{j}_{key}'] for key in ('observed_means','precision','beta','offsets','weights','columns')}
        result.append(predict_mixture(m,paid[:,m['columns']]))
    return ordinary-gaussian+np.column_stack(result)


def fit_outer(xfit,y,p,catalog,full,metadata,folds,f,xquery):
    tr=np.flatnonzero(folds!=f);te=np.flatnonzero(folds==f)
    if set(p[tr])&set(p[te]):raise ValueError('outer patient overlap')
    inner,_=g.patient_folds(p[tr],3,g.evaluate.SALT+f'|inner|{f}')
    oof=np.full((3,10,2,len(tr),24),np.nan)
    for fold in range(3):
        fit=tr[inner!=fold];val=tr[inner==fold]
        if set(p[fit])&set(p[val]):raise ValueError('inner patient overlap')
        pred=predict_all(xfit,val,build(xfit,y,p,catalog,full,metadata,fit))
        for vi in range(3):
            for k in range(10):
                for oi in (0,1):oof[vi,k,oi,inner==fold,:]=pred[vi,k,oi]
    if not np.isfinite(oof).all():raise ValueError('inner predictions incomplete')
    scores=[[float(g.risks(oof[vi,k],y[tr],p[tr]).mean()) for k in range(10)] for vi in range(3)]
    chosen=[int(np.argmin(v)) for v in scores]
    bundle=build(xfit,y,p,catalog,full,metadata,tr);all_predictions=predict_all(xquery,te,bundle)
    result={};payloads={};record={'fold':f,'arms':{},'treatment_wells':64,'per_plate':[32,32]}
    for vi,arm in enumerate(ARMS):
        index=chosen[vi];estimate=all_predictions[vi,index]
        state=pack_payload(bundle,10*vi+index);state['kernel_weights']=bundle['variants'][vi]['kernel'].w.copy()
        maxreplay=0.;maxpoison=0.
        for oi,o in enumerate(('A','B')):
            paid=g.acquire(xquery[te],bundle['plan'],o);replay=predict_payload(state,paid,o)
            maxreplay=max(maxreplay,float(np.max(np.abs(replay-estimate[oi]))))
            masked=np.full((len(te),xquery.shape[1],2),np.nan);n=state['native_indices'];plate=state['plate_'+o]
            masked[:,n,plate]=xquery[te][:,n,plate]
            poisoned=g.acquire(masked,bundle['plan'],o)
            maxpoison=max(maxpoison,float(np.max(np.abs(predict_payload(state,poisoned,o)-replay))))
        if maxreplay>1e-12 or maxpoison>1e-12:raise ValueError('inference replay or unpaid-input isolation')
        result[arm]=estimate;payloads[arm]=state
        record['arms'][arm]={'selected_index':index,'selected_option':g.OPTIONS[index],
            'inner_mse':scores[vi],'saved_state_replay_maxdiff':maxreplay,'unpaid_poison_maxdiff':maxpoison}
    return result,record,payloads,bundle['plan']


def check(curves,catalog,reference,source):
    fr=json.loads((HERE/'FREEZE.json').read_text(encoding='utf-8'))
    for key,path in {'curves':curves,'catalog':catalog,'reference':reference,'external_prepared':source}.items():
        if g.sha(path)!=fr['inputs'][key]:raise ValueError('input hash changed '+key)
    for rel,h in fr['source_sha256'].items():
        if g.sha(ROOT/rel)!=h:raise ValueError('code hash changed '+rel)
    import importlib.metadata
    for name,version in fr['runtime_versions'].items():
        if importlib.metadata.version(name)!=version:raise ValueError('runtime changed '+name)
    return fr


def execute(curves,catalog_path,reference,source,out):
    fr=check(curves,catalog_path,reference,source);out=Path(out);out.mkdir(parents=True,exist_ok=False)
    g.dump(out/'STARTED.json',{'utc':g.utc(),'freeze_sha256':g.sha(HERE/'FREEZE.json'),
       'runtime_versions':fr['runtime_versions'],'protected22_access':False,'network_disabled':True})
    socket.create_connection=deny;socket.socket.connect=deny;socket.socket.connect_ex=deny
    began=time.perf_counter()
    try:
        with np.load(source,allow_pickle=False) as z:bank={key:z[key].copy() for key in z.files}
        source_cov=bank['covariance5']
        source_counts={'curves':int(bank['source_curve_count']),'cell_identifiers':int(bank['source_cell_count']),'compounds':int(bank['source_compound_count']),'prototypes':len(bank['weights'])}
        data,feat,_=g.load_prepared(curves,catalog_path);x,y,p=feat['x_replicates'],data['y'],data['patient_ids'].astype(str)
        catalog=g.catalog_from_features(feat);full=g.full_training_curves(curves,data,feat,catalog,g.read_catalog(catalog_path))
        metadata=dose_metadata(curves,catalog,full,source_cov)
        for item in metadata:item['source_bank']=bank
        folds,_=g.patient_folds(p,5,g.evaluate.SALT+'|outer')
        with np.load(reference,allow_pickle=False) as z:
            if not np.array_equal(z['y'],y) or not np.array_equal(z['patients'].astype(str),p) or not np.array_equal(z['folds'],folds):raise ValueError('retained reference identity')
            retained=z['candidate'].copy();saved_operating=z['bandwidth07'].copy()
        if abs(g.metrics(retained,y,p,folds)['mse']-g.EXPECTED_SCI)>1e-15:raise ValueError('retained reference MSE')
        predictions={arm:np.full((2,*y.shape),np.nan) for arm in ARMS};records=[];first_states=None
        with threadpool_limits(limits=1):
            for f in range(5):
                pred,record,states,plan=fit_outer(x,y,p,catalog,full,metadata,folds,f,x)
                for arm in ARMS:
                    predictions[arm][:,folds==f]=pred[arm]
                    np.savez_compressed(out/f'fold_{f}_{arm}_model_private.npz',**states[arm])
                records.append(record);g.dump(out/f'fold_{f}_selection.json',record);g.dump(out/f'fold_{f}_plan.json',plan)
                if f==0:first_states={a:{k:np.asarray(v).copy() for k,v in s.items()} for a,s in states.items()}
                print(json.dumps({'event':'outer_complete','fold':f,'selected':{a:record['arms'][a]['selected_option'] for a in ARMS}}),flush=True)
            xx=x.copy();yy=y.copy();ff=dict(full);ff['values']=full['values'].copy()
            xx[folds==0]+=51.;yy[folds==0]+=89.;ff['values'][folds==0]-=137.
            sentinel,srec,sstate,_=fit_outer(xx,yy,p,catalog,ff,metadata,folds,0,x)
        isolation={}
        for arm in ARMS:
            delta=float(np.max(np.abs(sentinel[arm]-predictions[arm][:,folds==0])))
            state_delta=max(float(np.max(np.abs(np.asarray(sstate[arm][k])-first_states[arm][k]))) for k in first_states[arm])
            if delta>1e-12 or state_delta>1e-12 or srec['arms'][arm]['selected_index']!=records[0]['arms'][arm]['selected_index']:raise ValueError('held-out training path '+arm)
            isolation[arm]={'prediction_maxdiff':delta,'state_maxdiff':state_delta}
        operating=predictions['operating_reproduction'];replay=float(np.max(np.abs(operating-saved_operating)))
        if abs(g.metrics(operating,y,p,folds)['mse']-g.EXPECTED_BASE)>1e-12 or replay>1e-12:raise ValueError('operating reproduction failed')
        if NETWORK or any(not np.isfinite(q).all() for q in predictions.values()):raise ValueError('network attempt or incomplete outputs')
        g.SEED=SEED;arms={}
        for arm in ARMS[1:]:
            cm=g.metrics(predictions[arm],y,p,folds);vr=g.compare(predictions[arm],retained,y,p,folds,data['drug_ids']);vo=g.compare(predictions[arm],operating,y,p,folds,data['drug_ids'])
            arms[arm]={'metrics':cm,'vs_retained64':vr,'vs_operating64':vo,
              'half_error_target_met':bool(cm['mse']<=g.HALF_TARGET and vr['p90_nonworse']),
              'decision':'ELIGIBLE_FOR_FRESH_FULL_REPLAY' if vr['gate_pass'] and vo['gate_pass'] else 'REJECT_FOR_PROMOTION'}
        direct=g.compare(predictions['external_prototype_mixture'],predictions['matched_moment_control'],y,p,folds,data['drug_ids'])
        matched_error=abs(arms['matched_moment_control']['metrics']['mse']-.001068618046193161)
        if matched_error>1e-12:raise ValueError('matched-moment arm did not reproduce original external correlation model')
        np.savez_compressed(out/'predictions_private.npz',**predictions,retained64=retained,y=y,patients=p,folds=folds,sample_ids=data['sample_ids'],drug_ids=data['drug_ids'])
        result={'schema':'dosepilot.external_prototype_mixture64.result.v1','status':'COMPLETE','primary_arm':'external_prototype_mixture',
           'arms':arms,'mixture_vs_matched_moment_control':direct,'matched_control_mse_difference':matched_error,'operating_reproduction':g.metrics(operating,y,p,folds),
           'operating_saved_prediction_maxdiff':replay,'source_counts':source_counts,'external_prepared_sha256':g.sha(source),
           'fold_records':records,'outer_label_and_curve_mutation':isolation,'quadrature_maxdiff':full['quadrature_maxdiff'],
           'treatment_wells':64,'per_plate':[32,32],'half_error_target':g.HALF_TARGET,'network_attempts':len(NETWORK),
           'prediction_sha256':g.sha(out/'predictions_private.npz'),'freeze_sha256':g.sha(HERE/'FREEZE.json'),
           'protected22_access':False,'independent_validation':False,'selection_adjusted':False,
           'automatic_promotion':False,'kaggle_entry_changed':False,'source_mean_and_potency_transferred':False,
           'elapsed_seconds':time.perf_counter()-began,'finished_utc':g.utc()}
        g.dump(out/'RESULT.json',result)
        print(json.dumps({k:v for k,v in result.items() if k not in ('fold_records',)},indent=2),flush=True);return result
    except BaseException as exc:
        g.dump(out/'FAILURE.json',{'error':repr(exc),'traceback':traceback.format_exc(),'utc':g.utc(),'automatic_retry':False});raise

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--curves',type=Path,required=True);ap.add_argument('--catalog',type=Path,required=True)
    ap.add_argument('--reference',type=Path,required=True);ap.add_argument('--source',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args();execute(a.curves,a.catalog,a.reference,a.source,a.out)
