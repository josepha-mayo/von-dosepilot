#!/usr/bin/env python3
"""Rebuild the published optimized-interpolation control through the public CSV route.

A previous reproduce_compact run supplies the R13 comparison only. Its saved
predictions are opened after this new interpolation policy has been fitted and
its own held-patient predictions committed. No old prediction is a fit input.
"""
from __future__ import annotations
import argparse, datetime, json, time, traceback
from pathlib import Path
from study_support import setup, load_inputs, sha, write_json, patient_risks

EXPECTED_INTERPOLATION_MSE=0.002416810289196867
EXPECTED_OLD_READOUT_MSE=0.012445522811884428

def direct_trapezoid(paid,plan,bounds):
    """Second implementation, sample-by-sample; no precomputed decoder matrix."""
    import numpy as np
    result=np.empty((len(paid),24));owner=np.asarray(plan['coordinate_target_indices'])
    doses=np.asarray(plan['selected_concentrations_nM'],float)
    for j in range(24):
        positions=np.flatnonzero(owner==j);positions=positions[np.argsort(doses[positions])]
        x=np.log(doses[positions]);lo,hi=np.log(bounds[j])
        knots=np.r_[lo,x[(x>lo)&(x<hi)],hi]
        for i,row in enumerate(paid[:,positions]):
            values=np.interp(knots,x,row)
            result[i,j]=sum((knots[k+1]-knots[k])*(values[k+1]+values[k])/2 for k in range(len(knots)-1))/(hi-lo)
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--study',type=Path,required=True)
    source=p.add_mutually_exclusive_group(required=True)
    source.add_argument('--curves',type=Path)
    source.add_argument('--private-legacy-inputs',type=Path)
    p.add_argument('--r13-run',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();study=args.study.resolve();out=args.output.resolve();ref=args.r13_run.resolve()
    lock=setup(study)
    import numpy as np
    from threadpoolctl import threadpool_limits
    import evaluate as first
    from methods import patient_folds
    from coverage_methods import acquire,catalog_from_features
    from interpolation_policy import plan_panel,predict_paid
    out.mkdir(parents=True,exist_ok=False);t0=time.monotonic()
    protocol={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
      'purpose':'Public-input-route reproduction of an already reported fixed comparison, not a new method search.',
      'expected_mse':EXPECTED_INTERPOLATION_MSE,'tolerance':1e-12,
      'prediction_semantics':'Average the two alternative64well losses, never average their prediction vectors.',
      'targets':24,'patients':59,'wells_per_orientation':64,'per_plate':32,
      'interpolation_policy_changed':False,'new_independent_validation':False,'protected_response_access':False,
      'reference_open_policy':'Only after new interpolation predictions are committed.',
      'automatic_retry':False,'code_sha256':{n:sha(Path(__file__).with_name(n)) for n in ('reproduce_interpolation.py','interpolation_policy.py','study_support.py')},
      'locked_input_csv_sha256':lock['input_files']['train/train_curves.csv']['sha256']}
    write_json(out/'PROTOCOL.json',protocol)
    try:
        data,features,bounds,input_audit=load_inputs(study,curves=args.curves,legacy_inputs=args.private_legacy_inputs)
        x,y,patients=features['x_replicates'],data['y'],data['patient_ids']
        catalog=catalog_from_features(features);folds,assignments=patient_folds(patients,5,first.SALT+'|outer')
        pred={o:np.full_like(y,np.nan) for o in ('A','B')};audit=[];direct_error=0.
        with threadpool_limits(limits=1):
            for f in range(5):
                train,test=folds!=f,folds==f
                assert not set(patients[train])&set(patients[test])
                plan=plan_panel(x[train],y[train],patients[train],catalog,bounds)
                folder=out/f'outer_{f:02d}';folder.mkdir();write_json(folder/'plan.json',plan)
                native=np.asarray(plan['selected_native_indices'])
                for o in ('A','B'):
                    plates=np.asarray(plan[f'orientation_{o}_plate_indices']);paid=acquire(x[test],plan,o)
                    pred[o][test]=predict_paid(paid,plan)
                    direct=direct_trapezoid(paid,plan,bounds)
                    np.testing.assert_allclose(direct,pred[o][test],atol=1e-14,rtol=0)
                    direct_error=max(direct_error,float(np.abs(direct-pred[o][test]).max()))
                    wells=features['well_ids'][test][:,native,plates]
                    assert all(len(set(row))==64 for row in wells)
                    assert (plates==0).sum()==(plates==1).sum()==32
                    masked=np.full_like(x[test],np.nan);masked[:,native,plates]=paid
                    np.testing.assert_array_equal(predict_paid(acquire(masked,plan,o),plan),pred[o][test])
                audit.append({'fold':f,'fit_patients':len(set(patients[train])),'test_patients':len(set(patients[test])),
                              'unique_wells':64,'per_plate':32,'unpaid_mask_invariance':True})
                print(json.dumps({'fold':f,'seconds':time.monotonic()-t0}),flush=True)
        assert all(np.isfinite(v).all() for v in pred.values())
        np.savez_compressed(out/'predictions_private.npz',prediction_A=pred['A'],prediction_B=pred['B'],sample_ids=data['sample_ids'],patients=patients,folds=folds)
        write_json(out/'PREDICTIONS_COMMITTED.json',{'sha256':sha(out/'predictions_private.npz'),'reference_predictions_opened':False})
        # No reference file has been opened before this point.
        manifest=json.loads((ref/'MANIFEST.json').read_text())
        wanted=['oof_predictions.npz']+[f'outer_{f:02d}/plan.json' for f in range(5)]
        for n in wanted:
            if sha(ref/n)!=manifest['files'][n]:raise ValueError('Reference artifact hash differs: '+n)
        with np.load(ref/'oof_predictions.npz',allow_pickle=False) as z:
            for k,value in [('sample_ids',data['sample_ids']),('patient_ids',patients),('drug_ids',data['drug_ids']),('folds',folds)]:
                if not np.array_equal(z[k],value):raise ValueError('Reference row/target/split identity differs: '+k)
            np.testing.assert_allclose(z['y'],y,atol=1e-14,rtol=0)
            base={o:z['prediction_'+o].copy() for o in ('A','B')}
            paid_old={o:z['paid_'+o].copy() for o in ('A','B')}
        old={o:np.full_like(y,np.nan) for o in ('A','B')}
        for f in range(5):
            plan=json.loads((ref/f'outer_{f:02d}/plan.json').read_text());test=folds==f
            for o in ('A','B'):old[o][test]=direct_trapezoid(paid_old[o][test],plan,bounds)
        errors={k:((a['A']-y)**2+(a['B']-y)**2)/2 for k,a in [('r13',base),('optimized_interpolation',pred),('old_panel_readout',old)]}
        risks={k:patient_risks(v,patients)[1].mean(1) for k,v in errors.items()}
        mse={k:float(v.mean()) for k,v in risks.items()}
        expected={'r13':lock['expected_mse']['r13_single64_expected_loss'],'optimized_interpolation':EXPECTED_INTERPOLATION_MSE,'old_panel_readout':EXPECTED_OLD_READOUT_MSE}
        checks={k:abs(mse[k]-expected[k])<=1e-12 for k in expected}
        pids=np.unique(patients);pf=np.asarray([folds[patients==p][0] for p in pids])
        fold_mse={k:[float(v[pf==f].mean()) for f in range(5)] for k,v in risks.items()}
        result={'status':'PASS' if all(checks.values()) else 'MISMATCH','mse':mse,'expected_mse':expected,'checks':checks,
          'r13_relative_reduction_vs_optimized':1-mse['r13']/mse['optimized_interpolation'],
          'r13_patient_wins':int((risks['r13']<risks['optimized_interpolation']).sum()),
          'r13_fold_wins':int((np.asarray(fold_mse['r13'])<fold_mse['optimized_interpolation']).sum()),
          'fold_mse':fold_mse,'input_audit':input_audit,'direct_trapezoid_max_prediction_error':direct_error,
          'physical_audit':audit,'reference_used_for_fitting':False,'old_fitted_model_input':False,
          'private_predictions_published':False,'new_method_search':False,'new_independent_validation':False,
          'protected_response_access':False,'official_score':None,'source_workbook_opened':False,
          'protocol_sha256':sha(out/'PROTOCOL.json'),'reference_oof_sha256':sha(ref/'oof_predictions.npz'),
          'predictions_sha256':sha(out/'predictions_private.npz'),'seconds':time.monotonic()-t0}
        write_json(out/'RESULT.json',result);print(json.dumps(result,indent=2))
        if not all(checks.values()):raise ValueError('Fixed published comparison failed reproduction')
    except BaseException as exc:
        write_json(out/'FAILURE.json',{'type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc(),'automatic_retry':False})
        raise

if __name__=='__main__':main()
