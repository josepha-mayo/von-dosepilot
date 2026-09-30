#!/usr/bin/env python3
from __future__ import annotations
import argparse, datetime, json, time, traceback
from pathlib import Path
import numpy as np
import stroma_common as s

PROTOCOL_SHA='488fbf030444bc81fec2aaaf81316df773d98c3cb6fb58b580fa9e5cb27e1882'
COMMON_SHA='22ab4f79901290165d6be0e4bb6b8a326f2e8658ee85ba88db3e07ff652f8ed8'
TEST_SHA='e2f7dbe6c6227e6bcaece0a571c4b767147dd5d95f9a78cf54e8c4b3c129cba6'
TEST_LOG_SHA='251bedea2cee47fa91f1afab1309792d291a53a58474d08ae8059cd0443cac0c'
SPLIT_SHA='5298ee3e4bfdb4fb76d310d04065473dca4e800cda244bdeff78981733a70f81'

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--source',type=Path,required=True)
    ap.add_argument('--protocol',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    a=ap.parse_args();here=Path(__file__).resolve().parent;out=a.output.resolve();t0=time.monotonic()
    if out.exists():raise SystemExit('Output exists; preserve prior attempt')
    checks={'source':s.sha(a.source)==s.SOURCE_SHA,'protocol':s.sha(a.protocol)==PROTOCOL_SHA,
      'common':s.sha(here/'stroma_common.py')==COMMON_SHA,
      'tests':s.sha(here/'test_stroma_common.py')==TEST_SHA,
      'test_log':s.sha(here/'TESTS_BEFORE_OUTCOME.log')==TEST_LOG_SHA,
      'split':s.sha(here/'METADATA_SPLIT_004.json')==SPLIT_SHA}
    if not all(checks.values()):raise SystemExit('Frozen dependency changed: '+str(checks))

    out.mkdir(parents=True)
    s.dump(out/'DEVELOPMENT_ACCESS_STARTED.json',{'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
      'status':'development monoculture RLU access may have started','checks':checks,
      'allowed_organoids':list(s.DEV_IDS),'confirmation_ids_forbidden':sorted(s.CONFIRM_MAP),
      'automatic_retry':False})
    try:
        data,audit=s.load_scope(a.source,'development')
        values=data['values']['mono'];ids=data['ids']
        if tuple(ids)!=s.DEV_IDS or values.shape!=(13,4,7):raise ValueError('Frozen development cohort changed')
        if set(ids)&set(s.CONFIRM_MAP):raise AssertionError('Confirmation organoid entered development')
        y=s.auc_full(values);n=len(ids)
        learned={lam:np.full_like(y,np.nan) for lam in s.LAMBDAS}
        interp=np.full_like(y,np.nan);mean=np.full_like(y,np.nan);folds=[]
        for hold in range(n):
            train=np.arange(n)!=hold;test=~train
            lp=s.learned_plan(values[train],y[train])
            ip=s.interp_plan(values[train],y[train])
            for lam in s.LAMBDAS:
                m=s.fit_model(values[train],y[train],lp,lam)
                learned[lam][test]=s.predict_model(values[test],lp,m)
            interp[test]=s.interp_predict(values[test],ip)
            mean[test]=y[train].mean(0)
            folds.append({'holdout':str(ids[hold]),'train_count':int(train.sum()),
              'learned_upgrades':lp['upgraded'],'interp_upgrades':ip['upgraded']})
        if any(not np.isfinite(v).all() for v in learned.values()) or not np.isfinite(interp).all():
            raise AssertionError('Development OOF predictions incomplete')
        lambda_mse={str(lam):s.mse(y,learned[lam]) for lam in s.LAMBDAS}
        selected=min(s.LAMBDAS,key=lambda q:(lambda_mse[str(q)],s.LAMBDAS.index(q)))
        candidate=learned[selected]

        metrics={'learned':s.mse(y,candidate),'optimized_interpolation':s.mse(y,interp),
                 'development_mean':s.mse(y,mean)}
        final_plan=s.learned_plan(values,y)
        final_model=s.fit_model(values,y,final_plan,selected)
        final_interp=s.interp_plan(values,y)
        final_mean=y.mean(0)
        s.dump(out/'learned_plan.json',final_plan);s.dump(out/'interp_plan.json',final_interp)
        s.model_to_npz(out/'model_private.npz',final_model)
        np.savez_compressed(out/'development_private.npz',ids=ids,y=y,learned=candidate,
            optimized_interpolation=interp,development_mean=mean,values=values)
        np.save(out/'mean_baseline_private.npy',final_mean,allow_pickle=False)
        result={'status':'DEVELOPMENT_COMPLETE_MODEL_FROZEN','organoids':13,'targets':4,
          'dose_points_per_target':7,'full_dose_readouts':28,'sparse_budget':11,
          'normalization':'dose mean RLU / same condition+drug DMSO mean; no clipping',
          'endpoint':'normalized log-dose trapezoidal AUC across all seven positive doses',
          'loo_mse_by_lambda':lambda_mse,'selected_lambda':selected,'loo_mse':metrics,
          'per_target_mse':{k:dict(zip(s.DRUGS,map(float,s.per_target_mse(y,p)))) for k,p in
             [('learned',candidate),('optimized_interpolation',interp),('development_mean',mean)]},
          'strict_organoid_wins_vs_interpolation':int((s.per_row_loss(y,candidate)<s.per_row_loss(y,interp)).sum()),
          'learned_upgrades':final_plan['upgraded'],'interpolation_upgrades':final_interp['upgraded'],
          'folds':folds,'access_audit':audit,'confirmation_rlu_fields_decoded':0,
          'confirmation_outcomes_used':False,'seconds':time.monotonic()-t0}
        s.dump(out/'DEVELOPMENT_RESULT.json',result)

        freeze={'status':'FROZEN_BEFORE_CONFIRMATION_RLU','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'source_sha256':s.SOURCE_SHA,'protocol_sha256':PROTOCOL_SHA,
          'common_sha256':COMMON_SHA,'preparation_code_sha256':s.sha(Path(__file__)),
          'test_code_sha256':TEST_SHA,'test_log_sha256':TEST_LOG_SHA,'metadata_split_sha256':SPLIT_SHA,
          'development_result_sha256':s.sha(out/'DEVELOPMENT_RESULT.json'),
          'learned_plan_sha256':s.sha(out/'learned_plan.json'),
          'interp_plan_sha256':s.sha(out/'interp_plan.json'),
          'model_sha256':s.sha(out/'model_private.npz'),
          'mean_baseline_sha256':s.sha(out/'mean_baseline_private.npy'),
          'selected_lambda':selected,'development_ids':list(s.DEV_IDS),
          'confirmation_pairs':[list(x) for x in s.CONFIRM_PAIRS],
          'confirmation_outcomes_used':False,'automatic_retry':False}
        s.dump(out/'MODEL_FROZEN.json',freeze)
        print(json.dumps(result,indent=2),flush=True)
    except BaseException as exc:
        s.dump(out/'FAILURE.json',{'type':type(exc).__name__,'message':str(exc),
          'traceback':traceback.format_exc(),'confirmation_outcomes_used':False,'automatic_retry':False})
        raise

if __name__=='__main__':main()
