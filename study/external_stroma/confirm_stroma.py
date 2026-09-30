#!/usr/bin/env python3
from __future__ import annotations
import argparse, datetime, json, time, traceback
from pathlib import Path
import numpy as np
import stroma_common as s

PROTOCOL_SHA='488fbf030444bc81fec2aaaf81316df773d98c3cb6fb58b580fa9e5cb27e1882'
COMMON_SHA='22ab4f79901290165d6be0e4bb6b8a326f2e8658ee85ba88db3e07ff652f8ed8'

def summary(y,p):
    row=s.per_row_loss(y,p)
    return {'mse':float(row.mean()),'rmse':float(np.sqrt(row.mean())),
      'p90_organoid_rmse':float(np.quantile(np.sqrt(row),.9)),
      'per_target_mse':dict(zip(s.DRUGS,map(float,s.per_target_mse(y,p)))),
      'organoid_loss':row}

def public(q):
    return {k:v for k,v in q.items() if k!='organoid_loss'}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--source',type=Path,required=True)
    ap.add_argument('--protocol',type=Path,required=True)
    ap.add_argument('--model-dir',type=Path,required=True)
    ap.add_argument('--intent',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    a=ap.parse_args();out=a.output.resolve();model=a.model_dir.resolve();t0=time.monotonic()
    if out.exists():raise SystemExit('Output exists; confirmation is one-shot')
    intent=json.loads(a.intent.read_text());freeze=json.loads((model/'MODEL_FROZEN.json').read_text())
    checks={'source':s.sha(a.source)==s.SOURCE_SHA,'protocol':s.sha(a.protocol)==PROTOCOL_SHA,
      'common':s.sha(Path(__file__).with_name('stroma_common.py'))==COMMON_SHA,
      'confirmation_code':s.sha(Path(__file__))==intent['confirmation_code_sha256'],
      'model_freeze':s.sha(model/'MODEL_FROZEN.json')==intent['model_freeze_sha256'],
      'source_in_intent':intent['source_sha256']==s.SOURCE_SHA,
      'protocol_in_intent':intent['protocol_sha256']==PROTOCOL_SHA}

    for filename,key in [('model_private.npz','model_sha256'),('learned_plan.json','learned_plan_sha256'),
                         ('interp_plan.json','interp_plan_sha256'),('mean_baseline_private.npy','mean_baseline_sha256')]:
        checks[filename]=s.sha(model/filename)==freeze[key]==intent[key]
    if not all(checks.values()):raise SystemExit('Frozen confirmation dependency changed: '+str(checks))
    if tuple(map(tuple,intent['confirmation_pairs']))!=s.CONFIRM_PAIRS:
        raise SystemExit('Frozen confirmation identities changed')
    if intent['gate']!={'patientless_organoid_wins_required':9,'target_nonworse_required':3,
       'candidate_mse_lower':True,'p90_nonworse':True}:
        raise SystemExit('Gate changed')
    out.mkdir(parents=True)
    s.dump(out/'CONFIRMATION_ACCESS_STARTED.json',{'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
      'status':'confirmation RLU access may have started','checks':checks,
      'intent_sha256':s.sha(a.intent),'confirmation_pairs':[list(x) for x in s.CONFIRM_PAIRS],
      'retuning_permitted':False,'automatic_retry':False})
    try:
        data,audit=s.load_scope(a.source,'confirmation')
        ids=data['ids'];co=data['values']['co'];mono=data['values']['mono']
        expected=tuple(x[0] for x in s.CONFIRM_PAIRS)
        if tuple(ids)!=expected or co.shape!=(15,4,7) or mono.shape!=(15,4,7):
            raise ValueError('Confirmation cohort changed')
        if set(ids)&set(s.DEV_IDS):raise AssertionError('Development overlap')
        learned_plan=json.loads((model/'learned_plan.json').read_text())
        interp_plan=json.loads((model/'interp_plan.json').read_text())
        learned_model=s.model_from_npz(model/'model_private.npz')
        mean=np.load(model/'mean_baseline_private.npy',allow_pickle=False)
        if learned_model['lambda']!=freeze['selected_lambda']:raise ValueError('Frozen lambda changed')

        targets={'coculture':s.auc_full(co),'monoculture':s.auc_full(mono)}
        arms={}
        for condition,values in [('coculture',co),('monoculture',mono)]:
            learned=s.predict_model(values,learned_plan,learned_model)
            interp=s.interp_predict(values,interp_plan)
            baseline=np.broadcast_to(mean,(15,4)).copy()
            selected={tuple(x) for x in learned_plan['selected']};masked=values.copy()
            for j in range(4):
                for k in range(7):
                    if (j,k) not in selected:masked[:,j,k]=np.nan
            np.testing.assert_array_equal(s.predict_model(masked,learned_plan,learned_model),learned)
            arms[condition]={'learned':learned,'optimized_interpolation':interp,'development_mean':baseline}
        metrics={condition:{name:summary(targets[condition],pred) for name,pred in a.items()}
                 for condition,a in arms.items()}
        lp=metrics['coculture']['learned']['organoid_loss']
        ip=metrics['coculture']['optimized_interpolation']['organoid_loss']
        learned_target=np.asarray(list(metrics['coculture']['learned']['per_target_mse'].values()))
        interp_target=np.asarray(list(metrics['coculture']['optimized_interpolation']['per_target_mse'].values()))
        gate={'candidate_mse_lower':float(lp.mean())<float(ip.mean()),
          'at_least_9_of_15_organoid_wins':int((lp<ip).sum())>=9,
          'at_least_3_of_4_targets_nonworse':int((learned_target<=interp_target).sum())>=3,
          'p90_nonworse':metrics['coculture']['learned']['p90_organoid_rmse']<=metrics['coculture']['optimized_interpolation']['p90_organoid_rmse']}
        delta=lp-ip;rng=np.random.default_rng(9302026)
        boot=delta[rng.integers(0,15,size=(10000,15))].mean(1)
        context_shift={name:metrics['coculture'][name]['mse']-metrics['monoculture'][name]['mse']
                       for name in arms['coculture']}

        result={'status':'CONFIRMATION_COMPLETE','confirmation_organoids':15,'development_organoids':13,
          'targets':list(s.DRUGS),'positive_doses_per_target':7,'sparse_budget':11,
          'primary_condition':'matched autologous tumor-CAF coculture',
          'metrics':{c:{n:public(v) for n,v in q.items()} for c,q in metrics.items()},
          'strict_organoid_wins_vs_interpolation':int((lp<ip).sum()),
          'strict_organoid_losses_vs_interpolation':int((lp>ip).sum()),
          'organoid_ties_vs_interpolation':int((lp==ip).sum()),
          'target_nonworse_count':int((learned_target<=interp_target).sum()),
          'relative_mse_reduction_vs_interpolation':1-metrics['coculture']['learned']['mse']/metrics['coculture']['optimized_interpolation']['mse'],
          'paired_organoid_delta_mse_ci95':np.quantile(boot,[.025,.975]).tolist(),
          'delta_definition':'learned organoid MSE minus interpolation organoid MSE; negative favors learned',
          'context_shift_mse_change_coculture_minus_monoculture':context_shift,
          'gate':gate,'all_gate_components_passed':bool(all(gate.values())),
          'access_audit':audit,'no_post_outcome_exclusions':True,'retuning':False,
          'no_unpaid_value_dependency_verified':True,'prediction_clipping':False,
          'patient_identity_claimed':False,'clinical_validation':False,'organ_on_chip_hardware_validated':False,
          'original_r13_weights_validated':False,'official_competition_score':None,
          'protocol_sha256':PROTOCOL_SHA,'intent_sha256':s.sha(a.intent),
          'confirmation_code_sha256':s.sha(Path(__file__)),'seconds':time.monotonic()-t0}
        np.savez_compressed(out/'predictions_private.npz',ids=ids,
          target_coculture=targets['coculture'],target_monoculture=targets['monoculture'],
          **{c+'__'+n:p for c,q in arms.items() for n,p in q.items()})
        s.dump(out/'RESULT.json',result)
        s.dump(out/'MANIFEST.json',{'committed':True,'files':{p.name:s.sha(p) for p in sorted(out.iterdir()) if p.is_file()}})
        print(json.dumps(result,indent=2),flush=True)
    except BaseException as exc:
        s.dump(out/'FAILURE.json',{'type':type(exc).__name__,'message':str(exc),
          'traceback':traceback.format_exc(),'automatic_retry':False,'retuning_permitted':False,
          'intent_sha256':s.sha(a.intent)})
        raise

if __name__=='__main__':main()