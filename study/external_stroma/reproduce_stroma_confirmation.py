#!/usr/bin/env python3
"""Post-confirmation aggregate reproduction for the frozen stromal-context study."""
from __future__ import annotations
import argparse,json,time
from pathlib import Path
import numpy as np
import stroma_common as s

EXPECTED={
 'dev_learned':0.008362068328713558,'dev_interp':0.011851605264987833,
 'confirmation_learned':0.002969711683585339,'confirmation_interp':0.005236626630824439,
 'mono_learned':0.0036079629900843736,'mono_interp':0.0057686437250243725,
 'wins':10,'target_nonworse':3,'candidate_p90':0.06665610573587068,
 'interp_p90':0.10986335935623637,
 'ci95':[-0.004233824635354308,-0.0004968570381069612]}

def summary(y,p):
    e=(p-y)**2;row=e.mean(1)
    return {'mse':float(row.mean()),'p90':float(np.quantile(np.sqrt(row),.9)),
            'target':e.mean(0),'row':row}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--source',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    a=ap.parse_args();out=a.output.resolve();t0=time.monotonic()
    if out.exists():raise SystemExit('Output exists; choose a fresh directory')
    out.mkdir(parents=True)

    dev,dev_audit=s.load_scope(a.source,'development')
    v=dev['values']['mono'];y=s.auc_full(v);n=len(v)
    learned={lam:np.full_like(y,np.nan) for lam in s.LAMBDAS}
    interp=np.full_like(y,np.nan)
    for hold in range(n):
        tr=np.arange(n)!=hold;te=~tr
        lp=s.learned_plan(v[tr],y[tr]);ip=s.interp_plan(v[tr],y[tr])
        for lam in s.LAMBDAS:
            learned[lam][te]=s.predict_model(v[te],lp,s.fit_model(v[tr],y[tr],lp,lam))
        interp[te]=s.interp_predict(v[te],ip)
    scores={str(lam):s.mse(y,learned[lam]) for lam in s.LAMBDAS}
    selected=min(s.LAMBDAS,key=lambda q:(scores[str(q)],s.LAMBDAS.index(q)))
    if selected!=.1:raise ValueError('Development selection does not reproduce')
    final_plan=s.learned_plan(v,y);model=s.fit_model(v,y,final_plan,selected)
    final_interp=s.interp_plan(v,y)
    confirm,confirm_audit=s.load_scope(a.source,'confirmation')
    metrics={}
    for condition,key in [('coculture','co'),('monoculture','mono')]:
        vv=confirm['values'][key];yy=s.auc_full(vv)
        candidate=s.predict_model(vv,final_plan,model)
        control=s.interp_predict(vv,final_interp)
        metrics[condition]={'learned':summary(yy,candidate),'optimized_interpolation':summary(yy,control)}
    lp=metrics['coculture']['learned']['row'];ip=metrics['coculture']['optimized_interpolation']['row']
    lt=metrics['coculture']['learned']['target'];it=metrics['coculture']['optimized_interpolation']['target']
    rng=np.random.default_rng(9302026);delta=lp-ip
    ci=np.quantile(delta[rng.integers(0,15,size=(10000,15))].mean(1),[.025,.975])

    observed={'dev_learned':scores[str(selected)],'dev_interp':s.mse(y,interp),
      'confirmation_learned':metrics['coculture']['learned']['mse'],
      'confirmation_interp':metrics['coculture']['optimized_interpolation']['mse'],
      'mono_learned':metrics['monoculture']['learned']['mse'],
      'mono_interp':metrics['monoculture']['optimized_interpolation']['mse'],
      'wins':int((lp<ip).sum()),'target_nonworse':int((lt<=it).sum()),
      'candidate_p90':metrics['coculture']['learned']['p90'],
      'interp_p90':metrics['coculture']['optimized_interpolation']['p90'],
      'ci95':ci.tolist()}
    for k in ('dev_learned','dev_interp','confirmation_learned','confirmation_interp',
              'mono_learned','mono_interp','candidate_p90','interp_p90'):
        if abs(observed[k]-EXPECTED[k])>1e-14:raise ValueError(f'{k} mismatch')
    if observed['wins']!=EXPECTED['wins'] or observed['target_nonworse']!=EXPECTED['target_nonworse']:
        raise ValueError('Count metric mismatch')
    np.testing.assert_allclose(observed['ci95'],EXPECTED['ci95'],rtol=0,atol=1e-14)
    result={'status':'PASS_AGGREGATE_REPRODUCTION','observed':observed,
      'source_sha256':s.sha(a.source),'development_access_audit':dev_audit,
      'confirmation_access_audit':confirm_audit,'selected_lambda':selected,
      'development_organoids':13,'confirmation_organoids':15,'targets':list(s.DRUGS),
      'sparse_budget':11,'patient_identity_claimed':False,
      'reproduction_is_new_independent_confirmation':False,'seconds':time.monotonic()-t0}
    s.dump(out/'RESULT.json',result)
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()