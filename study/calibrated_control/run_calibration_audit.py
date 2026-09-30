#!/usr/bin/env python3
"""Calibrate an interpolation control using training data only; audit exposed tasks."""
from __future__ import annotations
import argparse, datetime, hashlib, importlib.util, json, os, sys, time, traceback
from pathlib import Path
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[key]='1'
import numpy as np
from calibrated_control import fit, weights, group_target_risks, select_from_folds, OPTIONS

PIN={
'external_crc_20260930/external_crc_common.py':'08310b012b01420a46ee467b926ccdc84cb0bf7b9a07a049f15f87dccb9c956d',
'external_crc_20260930/mmc3.xlsx':'dadea8de4da8b67456dd930f13370058e94097a36e8891bc38b4e77affcd92ea',
'external_crc_20260930/forecast1_confirmation_001/predictions_private.npz':'241ca1c9bb73b3116e3100cd44ec36b58cbacc825f43ab6dfc20f673991cf371',
'stroma_shift_20260930/stroma_common.py':'22ab4f79901290165d6be0e4bb6b8a326f2e8658ee85ba88db3e07ff652f8ed8',
'stroma_shift_20260930/development_001/development_private.npz':'44744c71d6b6a7996e0c53a36f1b7b8bb1b92ff96352f1f1b1811326463be788',
'stroma_shift_20260930/confirmation_001/predictions_private.npz':'2d151a4b317a537d513c16b3783162eacce56639f23b054b472cfbb84302914b'}

def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def dump(p,x):
    with Path(p).open('x') as f:json.dump(x,f,indent=2,sort_keys=True,allow_nan=False);f.write('\n')
def load_code(p,name):
    sp=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m

def direct_coefficients(x,y,p,m):
    if m.option=='identity':return 0.
    q=weights(p);err=0.
    for j in range(y.shape[1]):
        z=(x[:,j]-m.mean_x[j])/m.scale_x[j]
        a=np.c_[np.ones(len(z)),z];a=np.vstack([a*np.sqrt(q)[:,None],[0.,np.sqrt(float(m.option))]])
        target=np.r_[y[:,j]*np.sqrt(q),0.]
        coef=np.linalg.lstsq(a,target,rcond=None)[0]
        err=max(err,float(np.max(np.abs(coef-[m.mean_y[j],m.beta[j]]))))
    if err>1e-12:raise ValueError('Independent weighted least-squares check failed')
    return err

def prepare(root,name,out):
    if name=='forecast8':
        base=root/'external_crc_20260930';e=load_code(base/'external_crc_common.py','crc_frozen')
        d=e.load_single_agents(base/'mmc3.xlsx');keep=e.finite_complete(d)
        values=d['values'][keep];ids=d['patients'][keep];y=e.auc_full(values,d['doses'])
        assert values.shape==(64,8,9) and len(set(ids))==63
        fold_ids,_=e.patient_folds(ids,5);splits=[(np.flatnonzero(fold_ids!=f),np.flatnonzero(fold_ids==f)) for f in range(5)]
        def plan(ix):return e.interp_plan(values[ix],d['doses'],y[ix],ids[ix])
        def predict(ix,p):return e.interp_predict(values[ix],d['doses'],p)
        old_plan=base/'community_model_003/interp_plan.json';train_freeze=base/'community_model_003/MODEL_FROZEN.json'
        snapshot=base/'forecast1_confirmation_001/predictions_private.npz';manifest=base/'forecast1_confirmation_001/MANIFEST.json'
        scope={'development_lines':64,'development_groups':63,'eligible_confirmation':13,'source_confirmation':19,'incomplete_confirmation':6,'targets':list(e.DRUGS),'budget':21,'group_kind':'patient','original_gate_passed':False}
    else:
        base=root/'stroma_shift_20260930';e=load_code(base/'stroma_common.py','stroma_frozen')
        with np.load(base/'development_001/development_private.npz',allow_pickle=False) as z:
            values=z['values'].copy();ids=z['ids'].copy();y=z['y'].copy()
        assert values.shape==(13,4,7) and tuple(ids)==e.DEV_IDS
        np.testing.assert_allclose(y,e.auc_full(values),atol=1e-14,rtol=0)
        splits=[(np.flatnonzero(np.arange(13)!=i),np.array([i])) for i in range(13)]
        def plan(ix):return e.interp_plan(values[ix],y[ix])
        def predict(ix,p):return e.interp_predict(values[ix],p)
        old_plan=base/'development_001/interp_plan.json';train_freeze=base/'development_001/MODEL_FROZEN.json'
        snapshot=base/'confirmation_001/predictions_private.npz';manifest=base/'confirmation_001/MANIFEST.json'
        scope={'development_lines':13,'development_groups':13,'eligible_confirmation':15,'source_confirmation':15,'incomplete_confirmation':0,'targets':list(e.DRUGS),'budget':11,'group_kind':'organoid ID (unique patients unverified)','original_gate_passed':True}
    blocks=[]
    for i,(tr,va) in enumerate(splits):
        assert not set(ids[tr])&set(ids[va])
        p=plan(tr);blocks.append({'train':tr,'validation':va,'fit_interpolation':predict(tr,p),'validation_interpolation':predict(va,p)})
        dump(out/f'fold_{i:02}_plan.json',p)
    selected,scores,oof=select_from_folds(blocks,y,ids)
    final_plan=plan(np.arange(len(y)))
    original=json.loads(old_plan.read_text());freeze=json.loads(train_freeze.read_text())
    if sha(old_plan)!=freeze['interp_plan_sha256']:raise ValueError('Historical interpolation plan identity changed')
    if final_plan!=original:raise ValueError('Full-training interpolation plan failed exact reproduction')
    train_x=predict(np.arange(len(y)),final_plan);m=fit(train_x,y,ids,selected)
    coef_error=direct_coefficients(train_x,y,ids,m)
    np.savez_compressed(out/'calibration_private.npz',**m.arrays())
    np.savez_compressed(out/'development_oof_private.npz',predictions=oof,y=y,ids=ids,train_interpolation=train_x)
    dump(out/'CALIBRATION_FROZEN.json',{'option':selected,'options':list(OPTIONS),'oof_mse':scores,'source_plan_sha256':sha(old_plan),'calibration_sha256':sha(out/'calibration_private.npz'),'confirmation_predictions_opened':False,'already_exposed_task':True,'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'coefficient_check_max_error':coef_error})
    # Open only previously evaluated confirmation predictions after this fit is frozen.
    manifest_data=json.loads(manifest.read_text())
    if sha(snapshot)!=manifest_data['files']['predictions_private.npz']:raise ValueError('Prediction manifest mismatch')
    with np.load(snapshot,allow_pickle=False) as z:
        if name=='forecast8':
            cy,ci,cl,cp=[z[k].copy() for k in ('y','optimized_interpolation','learned','patients')]
        else:
            cy,ci,cl,cp=[z[k].copy() for k in ('target_coculture','coculture__optimized_interpolation','coculture__learned','ids')]
    assert not set(ids)&set(cp)
    assert len(cy)==scope['eligible_confirmation'] and cy.shape[1]==len(scope['targets'])
    cc=m.predict(ci)
    np.savez_compressed(out/'confirmation_predictions_private.npz',y=cy,raw_interpolation=ci,calibrated_interpolation=cc,learned=cl,groups=cp)
    pred={'raw_interpolation':ci,'calibrated_interpolation':cc,'original_learned':cl}
    gr={k:group_target_risks(cy,v,cp) for k,v in pred.items()}
    results={k:{'mse':float(v.mean()),'rmse':float(np.sqrt(v.mean())),'p90_group_rmse':float(np.quantile(np.sqrt(v.mean(1)),.9)),'per_target_mse':dict(zip(scope['targets'],map(float,v.mean(0))))} for k,v in gr.items()}
    old_expected={'forecast8':(.0021714653573835976,.0038551794484292285),'stroma4':(.0029697,.0052366)}[name]
    if name=='forecast8':
        assert abs(results['original_learned']['mse']-old_expected[0])<1e-12
        assert abs(results['raw_interpolation']['mse']-old_expected[1])<1e-12
    else:
        r=json.loads((base/'confirmation_001/RESULT.json').read_text())
        for key,old in [('original_learned','learned'),('raw_interpolation','optimized_interpolation')]:
            assert abs(results[key]['mse']-r['metrics']['coculture'][old]['mse'])<1e-12
    delta=gr['original_learned'].mean(1)-gr['calibrated_interpolation'].mean(1)
    rng=np.random.default_rng(2026093019);boot=delta[rng.integers(0,len(delta),(10000,len(delta)))].mean(1)
    result={'task':name,'scope':scope,'chosen_option':selected,'development_oof_mse_by_option':dict(zip(map(str,OPTIONS),scores)),'metrics':results,
      'learned_vs_calibrated':{'relative_mse_reduction':1-results['original_learned']['mse']/results['calibrated_interpolation']['mse'],'strict_group_wins':int((delta<0).sum()),'ties':int((delta==0).sum()),'strict_group_losses':int((delta>0).sum()),'target_wins':int((gr['original_learned'].mean(0)<gr['calibrated_interpolation'].mean(0)).sum()),'descriptive_delta_ci95':np.quantile(boot,[.025,.975]).tolist()},
      'old_metrics_reproduced':True,'historical_interp_plan_reproduced':True,'direct_coefficient_check_max_error':coef_error,
      'calibration_model_sha256':sha(out/'calibration_private.npz'),'input_prediction_sha256':sha(snapshot),'output_prediction_sha256':sha(out/'confirmation_predictions_private.npz'),
      'new_independent_confirmation':False,'confirmation_data_used_to_fit':False,'protocol_after_original_outcomes':True,'no_new_confirmation_measurements':True,'new_primary_target_or_cohort_exclusions':False,'official_score':None}
    dump(out/'RESULT.json',result);return result

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--project-root',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    out=args.output;out.mkdir(parents=True,exist_ok=False);t0=time.monotonic();here=Path(__file__).resolve().parent
    record={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'protocol_sha256':sha(here/'PROTOCOL.md'),'source_sha256':{n:sha(here/n) for n in ('calibrated_control.py','run_calibration_audit.py','test_calibrated_control.py')},'expected_inputs':PIN,'posthoc_on_exposed_tasks':True,'automatic_retry':False}
    dump(out/'INTENT.json',record)
    try:
        for n,h in PIN.items():
            if sha(args.project_root/n)!=h:raise ValueError('Pinned input changed: '+n)
        results=[]
        for name in ('forecast8','stroma4'):
            dst=out/name;dst.mkdir();results.append(prepare(args.project_root,name,dst));print(name,json.dumps(results[-1]),flush=True)
        dump(out/'RESULT.json',{'status':'COMPLETE','tasks':results,'seconds':time.monotonic()-t0,'intent_sha256':sha(out/'INTENT.json'),'new_independent_confirmation':False,'retained_r13_changed':False,'protected_lib2_opened':False,'published_patient_data':False})
    except BaseException as exc:
        dump(out/'FAILURE.json',{'error':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc(),'automatic_retry':False});raise
if __name__=='__main__':main()
