#!/usr/bin/env python3
from __future__ import annotations
import os
for key in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS'):os.environ[key]='1'
import argparse,hashlib,importlib.util,json,sys,traceback,time
from pathlib import Path
import numpy as np
from threadpoolctl import threadpool_limits
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];STUDY=ROOT/'study'
spec=importlib.util.spec_from_file_location('frozen_reference_helpers',STUDY/'global_conditional_curve64/run_study.py')
g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
sys.path.insert(0,str(HERE))
from core import to_latent,fit_curve_head,predict_curve_head,patient_weights
from data import layout_and_fields,ARMS
SEED=202610072227


def physical_indices(plan,mapping,o):
    return 2*mapping[np.asarray(plan['selected_native_indices'])]+np.asarray(plan[f'orientation_{o}_plate_indices'])


def build(x,y,p,catalog,full,fields,ix):
    plan=g.plan_panel_fast(x[ix],y[ix],p[ix],catalog);g.validate_plan(plan,catalog)
    raw_paid={o:g.acquire(x[ix],plan,o) for o in ('A','B')};physical={o:physical_indices(plan,full['query_to_full'],o) for o in ('A','B')}
    raw_full=full['values'][ix].reshape(len(ix),-1);bundles={}
    for arm in ARMS:
        off=fields['offsets'][arm][ix];gain=fields['gains'][arm][ix]
        paid={o:to_latent(raw_paid[o],off[:,physical[o]],gain[:,physical[o]]) for o in ('A','B')}
        latent_full=to_latent(raw_full,off,gain)
        head=fit_curve_head(paid['A'],paid['B'],latent_full,p[ix],plan['coordinate_target_indices'],fields['full_owner'])
        bp={o:predict_curve_head(head,paid[o],off,gain,full['q']) for o in ('A','B')}
        z=(np.r_[paid['A'],paid['B']]-head['mean_x'])/head['scale_x'];residual=np.r_[y[ix]-bp['A'],y[ix]-bp['B']]
        w=np.tile(patient_weights(p[ix]),2)/2
        kernel=g.BandwidthAdditive(z,residual,w,np.asarray(plan['coordinate_target_indices']),.7)
        coefs=[np.zeros_like(residual)]+[kernel.coefficients(l,f)[0] for f,l in g.OPTIONS[1:]]
        bundles[arm]={'head':head,'kernel':kernel,'coefs':coefs}
    return {'plan':plan,'physical':physical,'arms':bundles,'quadrature':full['q']}


def predict_options(x,ix,bundle,fields):
    plan=bundle['plan'];output={arm:np.empty((10,2,len(ix),24)) for arm in ARMS}
    for arm in ARMS:
        b=bundle['arms'][arm];head=b['head'];off=fields['offsets'][arm][ix];gain=fields['gains'][arm][ix]
        for oi,o in enumerate(('A','B')):
            raw=g.acquire(x[ix],plan,o);idx=bundle['physical'][o]
            paid=to_latent(raw,off[:,idx],gain[:,idx]);base=predict_curve_head(head,paid,off,gain,bundle['quadrature'])
            cross=b['kernel'].centered_cross((paid-head['mean_x'])/head['scale_x'])
            for k,c in enumerate(b['coefs']):output[arm][k,oi]=base+cross@c
    return output


def payload(bundle,arm,chosen):
    b=bundle['arms'][arm];k=b['kernel'];s={name:np.asarray(v).copy() for name,v in b['head'].items()}
    s.update({'kernel_z':k.z,'kernel_owner':k.owner,'kernel_weights':k.w,'kernel_mean':k.train_mean,
      'kernel_grand':np.asarray(k.grand),'coef':b['coefs'][chosen],'physical_A':bundle['physical']['A'],
      'physical_B':bundle['physical']['B'],'quadrature':bundle['quadrature'],'chosen':np.asarray(chosen)})
    return s


def fit_outer(xfit,y,p,catalog,full,fields,folds,f,xquery):
    tr=np.flatnonzero(folds!=f);te=np.flatnonzero(folds==f)
    if set(p[tr])&set(p[te]):raise ValueError('outer patient overlap')
    inner,_=g.patient_folds(p[tr],3,g.evaluate.SALT+f'|inner|{f}')
    oof={arm:np.full((10,2,len(tr),24),np.nan) for arm in ARMS}
    for k in range(3):
        fit=tr[inner!=k];val=tr[inner==k]
        if set(p[fit])&set(p[val]):raise ValueError('inner patient overlap')
        estimates=predict_options(xfit,val,build(xfit,y,p,catalog,full,fields,fit),fields)
        for arm in ARMS:
            for option in range(10):
                for oi in (0,1):oof[arm][option,oi,inner==k,:]=estimates[arm][option,oi]
    scores={arm:[float(g.risks(q,y[tr],p[tr]).mean()) for q in oof[arm]] for arm in ARMS}
    if not all(np.isfinite(oof[arm]).all() for arm in ARMS):raise ValueError('inner predictions incomplete')
    choices={arm:int(np.argmin(scores[arm])) for arm in ARMS}
    bundle=build(xfit,y,p,catalog,full,fields,tr);options=predict_options(xquery,te,bundle,fields)
    predictions={arm:options[arm][choices[arm]] for arm in ARMS};plan=bundle['plan']
    poison={arm:0. for arm in ARMS}
    for oi,o in enumerate(('A','B')):
        ni=np.asarray(plan['selected_native_indices']);pi=np.asarray(plan[f'orientation_{o}_plate_indices'])
        only_paid=np.full((len(te),xquery.shape[1],2),np.nan);only_paid[:,ni,pi]=xquery[te][:,ni,pi]
        raw=g.acquire(only_paid,plan,o)
        for arm in ARMS:
            b=bundle['arms'][arm];off=fields['offsets'][arm][te];gain=fields['gains'][arm][te];head=b['head'];physical=bundle['physical'][o]
            paid=to_latent(raw,off[:,physical],gain[:,physical])
            base=predict_curve_head(head,paid,off,gain,full['q']);cross=b['kernel'].centered_cross((paid-head['mean_x'])/head['scale_x'])
            again=base+cross@b['coefs'][choices[arm]]
            poison[arm]=max(poison[arm],float(np.max(abs(again-predictions[arm][oi]))))
    if max(poison.values())>1e-12:raise ValueError('unpaid response influence')
    states={arm:payload(bundle,arm,choices[arm]) for arm in ARMS}
    record={'fold':f,'selected_options':{arm:list(g.OPTIONS[choices[arm]]) for arm in ARMS},'indices':choices,
      'inner_mse':scores,'unpaid_poison_maxdiff':poison,'treatment_wells':64,'per_plate':[32,32]}
    return predictions,states,plan,record


def check(curves,catalog,controls,reference):
    fr=json.loads((HERE/'FREEZE.json').read_text(encoding='utf-8'))
    for k,path in {'curves':curves,'catalog':catalog,'controls':controls,'reference':reference}.items():
        if g.sha(path)!=fr['inputs'][k]:raise ValueError('input hash mismatch '+k)
    for rel,h in fr['source_sha256'].items():
        if g.sha(ROOT/rel)!=h:raise ValueError('source hash mismatch '+rel)
    return fr


def execute(curves,catalog_path,controls,reference,out):
    fr=check(curves,catalog_path,controls,reference);out=Path(out);out.mkdir(parents=True,exist_ok=False);started=time.perf_counter()
    g.dump(out/'STARTED.json',{'utc':g.utc(),'freeze_sha256':g.sha(HERE/'FREEZE.json'),'python':sys.version,'numpy':np.__version__,
      'control_wells_are_required_assay_resources':True,'new_treatment_wells':0,'protected22_access':False})
    try:
        data,feat,_=g.load_prepared(curves,catalog_path);x,y,p=feat['x_replicates'],data['y'],data['patient_ids'].astype(str)
        catalog=g.catalog_from_features(feat);full=g.full_training_curves(curves,data,feat,catalog,g.read_catalog(catalog_path))
        fields=layout_and_fields(curves,controls,data,catalog,full)
        folds,_=g.patient_folds(p,5,g.evaluate.SALT+'|outer')
        with np.load(reference,allow_pickle=False) as z:
            if not np.array_equal(z['y'],y) or not np.array_equal(z['patients'].astype(str),p) or not np.array_equal(z['folds'],folds):raise ValueError('reference identity')
            retained=z['candidate'].copy();operating=z['bandwidth07'].copy()
        if abs(g.metrics(retained,y,p,folds)['mse']-g.EXPECTED_SCI)>1e-15 or abs(g.metrics(operating,y,p,folds)['mse']-g.EXPECTED_BASE)>1e-15:raise ValueError('reference score mismatch')
        predictions={arm:np.full((2,*y.shape),np.nan) for arm in ARMS};records=[];first_states=None
        with threadpool_limits(limits=1):
            for f in range(5):
                pred,states,plan,rec=fit_outer(x,y,p,catalog,full,fields,folds,f,x)
                for arm in ARMS:
                    predictions[arm][:,folds==f]=pred[arm];np.savez_compressed(out/f'fold_{f}_{arm}_model_private.npz',**states[arm])
                if f==0:first_states={arm:{k:np.asarray(v).copy() for k,v in s.items()} for arm,s in states.items()}
                records.append(rec);g.dump(out/f'fold_{f}_plan.json',plan);g.dump(out/f'fold_{f}_COMPLETE.json',rec)
                print(json.dumps({'event':'outer_complete','fold':f,'selected':rec['selected_options']}),flush=True)
            changed_x=x.copy();changed_y=y.copy();changed_full=dict(full);changed_full['values']=full['values'].copy()
            changed_x[folds==0]+=37;changed_y[folds==0]+=71;changed_full['values'][folds==0]-=137
            again,states,unused,srec=fit_outer(changed_x,changed_y,p,catalog,changed_full,fields,folds,0,x)
        mutation={arm:float(np.max(abs(again[arm]-predictions[arm][:,folds==0]))) for arm in ARMS}
        state_diff={arm:max(float(np.max(abs(np.asarray(states[arm][key])-first_states[arm][key]))) for key in states[arm]) for arm in ARMS}
        if max(mutation.values())>1e-12 or max(state_diff.values())>1e-12 or srec['indices']!=records[0]['indices']:raise ValueError('outer label isolation failed')
        identity_diff=float(np.max(abs(predictions['identity']-operating)))
        if abs(g.metrics(predictions['identity'],y,p,folds)['mse']-g.EXPECTED_BASE)>1e-12:raise ValueError('identity benchmark not reproduced')
        g.SEED=SEED;arms={}
        for arm,pred in predictions.items():
            cm=g.metrics(pred,y,p,folds);cr=g.compare(pred,retained,y,p,folds,data['drug_ids']);co=g.compare(pred,operating,y,p,folds,data['drug_ids'])
            arms[arm]={'metrics':cm,'vs_retained64':cr,'vs_operating64':co,
              'half_error_point_and_tail_met':bool(cm['mse']<=g.HALF_TARGET and cr['p90_nonworse']),
              'decision':'ELIGIBLE_FOR_FRESH_REPLAY' if cr['gate_pass'] and co['gate_pass'] else 'REJECT_FOR_PROMOTION'}
        np.savez_compressed(out/'predictions_private.npz',**predictions,retained64=retained,operating64=operating,y=y,patients=p,folds=folds,sample_ids=data['sample_ids'],drug_ids=data['drug_ids'])
        field_summary={arm:{'gain_clip_count':sum(r['gain_clip_count'] for r in fields['field_audit'] if r['arm']==arm),
          'gain_min':min(r['gain_min'] for r in fields['field_audit'] if r['arm']==arm),
          'gain_max':max(r['gain_max'] for r in fields['field_audit'] if r['arm']==arm),
          'max_abs_offset':max(r['max_abs_offset'] for r in fields['field_audit'] if r['arm']==arm),
          'negative_geometry_ranks':sorted(set(r['negative_geometry_rank'] for r in fields['field_audit'] if r['arm']==arm)),
          'positive_geometry_ranks':sorted(set(r['positive_geometry_rank'] for r in fields['field_audit'] if r['arm']==arm))} for arm in ARMS}
        result={'schema':'dosepilot.control_transport64.result.v1','status':'COMPLETE','primary_arm':'spatial','arms':arms,
           'field_summary':field_summary,'fold_records':records,'control_values_used':fields['control_values_used'],'routine_controls_per_plate':22,
           'treatment_wells':64,'per_plate':[32,32],'half_error_target':g.HALF_TARGET,'identity_prediction_maxdiff':identity_diff,
           'outer_label_curve_mutation_maxdiff':mutation,'outer_state_mutation_maxdiff':state_diff,
           'quadrature_maxdiff':full['quadrature_maxdiff'],'prediction_sha256':g.sha(out/'predictions_private.npz'),
           'freeze_sha256':g.sha(HERE/'FREEZE.json'),'protected22_access':False,'independent_validation':False,'selection_adjusted':False,
           'endpoint_redefined':False,'new_treatment_wells':0,'new_control_wells':0,'automatic_promotion':False,'kaggle_entry_changed':False,
           'seconds':time.perf_counter()-started,'finished_utc':g.utc()}
        g.dump(out/'RESULT.json',result);print(json.dumps(result,indent=2),flush=True);return result
    except BaseException as exc:g.dump(out/'FAILURE.json',{'error':repr(exc),'traceback':traceback.format_exc(),'utc':g.utc(),'automatic_retry':False});raise

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--curves',type=Path,required=True);ap.add_argument('--catalog',type=Path,required=True)
    ap.add_argument('--controls',type=Path,required=True);ap.add_argument('--reference',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args();execute(a.curves,a.catalog,a.controls,a.reference,a.out)
