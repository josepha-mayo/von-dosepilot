#!/usr/bin/env python3
"""One prespecified, TRAIN-only nested comparison of a paid-input slope constraint."""
from __future__ import annotations
import argparse, datetime, json, os, time, traceback
from pathlib import Path
from study_support import setup, load_inputs, sha, write_json, patient_risks

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--study',type=Path,required=True)
    source=p.add_mutually_exclusive_group(required=True)
    source.add_argument('--curves',type=Path)
    source.add_argument('--private-legacy-inputs',type=Path)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();study=args.study.resolve();out=args.output.resolve()
    lock=setup(study)
    import numpy as np
    from threadpoolctl import threadpool_limits
    import evaluate as first
    from methods import patient_folds
    from coverage_methods import plan_panel, acquire, fit_prediction_context, catalog_from_features, CoveragePredictor
    from sparse_methods import LAMBDAS
    from shift_head import ShiftConstrainedPredictor, STRENGTHS
    out.mkdir(parents=True,exist_ok=False);t0=time.monotonic()
    protocol={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
      'hypothesis':'Constrain raw own-drug coefficient sums toward one to limit under/over-response to a uniform additive shift in that drug assay.',
      'ridge_penalties':list(LAMBDAS),'constraint_strengths':list(STRENGTHS),
      'selection':'One shared strength and ridge penalty, selected by pooled equal-patient inner OOF expected-layout loss. R13 separately selects its original shared ridge penalty.',
      'plan':'Unchanged R13 plan rebuilt independently in every inner and outer fitting slice.',
      'physical_budget':64,'targets':24,'per_plate':32,'outer_folds':5,'inner_folds':3,
      'gate':'At least5% lower full24 risk,40strict patient wins,4strict fold wins,nonworse p90 expected-patient RMSE,both candidate orientation means below baseline expected risk.',
      'soft_path':'beta = beta_R13 + strength*(beta_hard_constraint-beta_R13); no extra observations.',
      'scope':'Previously exposed Lib1 TRAIN only; no original workbook, Lib2, independent cohort or clinical outcomes.',
      'scientific_scope':'Repeated adaptive development; no new independent validation or official score.',
      'no_prospective_assay_shift_claim':True,'no_output_clipping':True,'prediction_averaging':False,
      'automatic_retry':False,'code_sha256':{n:sha(Path(__file__).with_name(n)) for n in ('evaluate_shift.py','shift_head.py','study_support.py','test_shift_head.py')},
      'study_lock_sha256':sha(study/'STUDY_LOCK.json'),'locked_input_csv_sha256':lock['input_files']['train/train_curves.csv']['sha256']}
    write_json(out/'PROTOCOL.json',protocol)
    try:
        data,features,bounds,input_audit=load_inputs(study,curves=args.curves,legacy_inputs=args.private_legacy_inputs)
        x,y,patients=features['x_replicates'],data['y'],data['patient_ids']
        catalog=catalog_from_features(features)
        folds,assignments=patient_folds(patients,5,first.SALT+'|outer')
        write_json(out/'outer_folds_private.json',assignments)
        options=[(s,lam) for s in STRENGTHS for lam in LAMBDAS]
        predictions={k:np.full_like(y,np.nan) for k in ('base_A','base_B','candidate_A','candidate_B')}
        selection=[];audits=[]
        def risk(truth,a,b,ids):
            return float(patient_risks(((a-truth)**2+(b-truth)**2)/2,ids)[1].mean())
        with threadpool_limits(limits=1):
            for f in range(5):
                train,test=folds!=f,folds==f
                xx,yy,pp=x[train],y[train],patients[train]
                assert not set(pp)&set(patients[test])
                inner,_=patient_folds(pp,3,first.SALT+f'|inner|{f}')
                inner_pred=np.full((len(options),2,len(yy),24),np.nan)
                directory=out/f'outer_{f:02d}';directory.mkdir()
                for g in range(3):
                    fit,val=inner!=g,inner==g
                    assert not set(pp[fit])&set(pp[val])
                    plan=plan_panel(xx[fit],yy[fit],pp[fit],catalog)
                    ca,cb=[acquire(xx[fit],plan,o) for o in ('A','B')]
                    context=fit_prediction_context(ca,cb,yy[fit],pp[fit],plan,catalog.target_ids)
                    paid=[acquire(xx[val],plan,o) for o in ('A','B')]
                    save_dir=directory/f'inner_{g:02d}';save_dir.mkdir()
                    write_json(save_dir/'plan.json',plan)
                    for k,(s,lam) in enumerate(options):
                        model=ShiftConstrainedPredictor(context,plan,lam,s)
                        for oi in range(2):inner_pred[k,oi,val]=model.predict(paid[oi])
                    np.savez_compressed(save_dir/'context_private.npz',mean_x=context.mean_x,scale_x=context.scale_x,mean_y=context.mean_y,cxx=context.cxx,cxy=context.cxy)
                assert np.isfinite(inner_pred).all()
                scores=[risk(yy,ab[0],ab[1],pp) for ab in inner_pred]
                # Stable tie breaking preserves unconstrained strength0, then old penalty order.
                chosen=min(range(len(options)),key=lambda k:(scores[k],k))
                base=min(range(len(LAMBDAS)),key=lambda k:(scores[k],k))
                s,lam=options[chosen];base_lam=options[base][1]
                plan=plan_panel(xx,yy,pp,catalog)
                context=fit_prediction_context(acquire(xx,plan,'A'),acquire(xx,plan,'B'),yy,pp,plan,catalog.target_ids)
                base_model=CoveragePredictor(context,plan,base_lam)
                candidate=ShiftConstrainedPredictor(context,plan,lam,s)
                hard=ShiftConstrainedPredictor(context,plan,lam,1.)
                native=np.asarray(plan['selected_native_indices']);owner=np.asarray(plan['coordinate_target_indices'])
                equivariance_error=0.
                for o in ('A','B'):
                    plates=np.asarray(plan[f'orientation_{o}_plate_indices'])
                    paid=acquire(x[test],plan,o)
                    bought=features['well_ids'][test][:,native,plates]
                    assert all(len(set(row))==64 for row in bought)
                    assert (plates==0).sum()==(plates==1).sum()==32
                    predictions['base_'+o][test]=base_model.predict(paid)
                    predictions['candidate_'+o][test]=candidate.predict(paid)
                    masked=np.full_like(x[test],np.nan);masked[:,native,plates]=paid
                    np.testing.assert_array_equal(candidate.predict(acquire(masked,plan,o)),candidate.predict(paid))
                    shifts=np.linspace(-.2,.2,24)
                    error=hard.predict(paid+shifts[owner])-hard.predict(paid)-shifts
                    equivariance_error=max(equivariance_error,float(np.max(np.abs(error))))
                write_json(directory/'plan.json',plan)
                np.savez_compressed(directory/'candidate_model_private.npz',**candidate.arrays(),cxx=context.cxx,cxy=context.cxy)
                record={'fold':f,'constraint_strength':s,'ridge':lam,'baseline_ridge':base_lam,'inner_scores':scores,'options':options,'hard_shift_identity_max_error':equivariance_error}
                write_json(directory/'selection.json',record);selection.append(record)
                audits.append({'fold':f,'unpaid_inputs_masked':True,'unique_wells':64,'per_plate':32})
                print(json.dumps({'fold':f,'strength':s,'ridge':lam,'base_ridge':base_lam,'seconds':time.monotonic()-t0}),flush=True)
        assert all(np.isfinite(a).all() for a in predictions.values())
        np.savez_compressed(out/'predictions_private.npz',**predictions,y=y,patients=patients,sample_ids=data['sample_ids'],drug_ids=data['drug_ids'],folds=folds)
        write_json(out/'PREDICTIONS_COMMITTED.json',{'sha256':sha(out/'predictions_private.npz'),'selection_scores_complete':True})
        errs={k:((predictions[k+'_A']-y)**2+(predictions[k+'_B']-y)**2)/2 for k in ('base','candidate')}
        pids,be=patient_risks(errs['base'],patients);_,ce=patient_risks(errs['candidate'],patients)
        br,cr=be.mean(1),ce.mean(1);delta=cr-br
        baseline,cand=float(br.mean()),float(cr.mean())
        if abs(baseline-lock['expected_mse']['r13_single64_expected_loss'])>1e-12:raise ValueError('Baseline failed locked reproduction')
        p_fold=np.array([folds[patients==p][0] for p in pids])
        bm=[float(br[p_fold==f].mean()) for f in range(5)];cm=[float(cr[p_fold==f].mean()) for f in range(5)]
        orientation={k:{o:float(patient_risks((predictions[k+'_'+o]-y)**2,patients)[1].mean()) for o in ('A','B')} for k in ('base','candidate')}
        p90={k:float(np.quantile(np.sqrt(v),.9)) for k,v in [('base',br),('candidate',cr)]}
        gates={'relative_gain_5pct':cand<=baseline*.95,'patient_wins_40':int((delta<0).sum())>=40,
               'fold_wins_4':int(np.sum(np.array(cm)<bm))>=4,'p90_nonworse':p90['candidate']<=p90['base'],
               'both_layout_means_below_reference_expected':max(orientation['candidate'].values())<baseline}
        rng=np.random.default_rng(20420930);boot=delta[rng.integers(0,59,size=(10000,59))].mean(1)
        result={'status':'COMPLETE','baseline_mse':baseline,'candidate_mse':cand,'relative_mse_reduction':1-cand/baseline,
          'strict_patient_wins':int((delta<0).sum()),'strict_patient_losses':int((delta>0).sum()),'exact_ties':int((delta==0).sum()),
          'fold_mse':{'base':bm,'candidate':cm},'p90_patient_expected_rmse':p90,'orientation_mse':orientation,
          'per_target_mse':{k:dict(zip(map(str,data['drug_ids']),map(float,e.mean(0)))) for k,e in [('base',be),('candidate',ce)]},
          'gates':gates,'decision':'CANDIDATE_PASSES_INTERNAL_GATE' if all(gates.values()) else 'REJECT_RETAIN_R13',
          'selections':selection,'samples':119,'patients':59,'targets':24,'wells':64,'physical_audit':audits,
          'descriptive_delta_ci95':np.quantile(boot,[.025,.975]).tolist(),'bootstrap_selection_corrected':False,
          'input_audit':input_audit,'new_independent_validation':False,'official_score':None,'protected_response_access':False,
          'protocol_sha256':sha(out/'PROTOCOL.json'),'predictions_sha256':sha(out/'predictions_private.npz'),'seconds':time.monotonic()-t0}
        write_json(out/'RESULT.json',result)
        print(json.dumps({k:v for k,v in result.items() if k not in ('per_target_mse','selections','physical_audit')},indent=2))
    except BaseException as exc:
        write_json(out/'FAILURE.json',{'type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc(),'automatic_retry':False})
        raise

if __name__=='__main__':main()
