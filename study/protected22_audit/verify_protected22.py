"""Independent saved-array arithmetic verification. Never reads a source workbook.

The complete-patient and per-target estimates are conditional diagnostics, not
replacement primary results. Outputs omit individual sample and patient IDs.
"""
from __future__ import annotations
import argparse, hashlib, json, math
from pathlib import Path
import numpy as np

METHODS={'candidate':('candidate_A','candidate_B'),'comparator':('comparator_A','comparator_B')}

def percentile(x, q):
    xs=sorted(map(float,x));pos=(len(xs)-1)*q;k=int(pos);u=min(k+1,len(xs)-1)
    return xs[k]*(1-(pos-k))+xs[u]*(pos-k)

def mean(x):
    xs=list(x)
    if not xs:raise ValueError('Empty mean')
    return math.fsum(xs)/len(xs)

def validate(a):
    y=np.asarray(a['y'],float)
    if y.ndim!=2 or not y.size:raise ValueError('Nonempty sample x target array required')
    n,t=y.shape
    for key in ('y','candidate_A','candidate_B','comparator_A','comparator_B'):
        if a[key].shape!=(n,t) or np.isinf(a[key]).any():raise ValueError('Invalid array '+key)
    for key,length in [('samples',n),('patients',n),('targets',t)]:
        if a[key].shape!=(length,) or a[key].dtype.kind not in 'US':raise ValueError('String identity vector required')
    if len(set(a['samples']))!=n or len(set(a['targets']))!=t:raise ValueError('Duplicate sample or target')
    return n,t

def analyze(a):
    n,t=validate(a);patients=sorted(set(a['patients']))
    groups={p:[i for i in range(n) if a['patients'][i]==p] for p in patients}
    complete=np.logical_and.reduce([np.isfinite(a[k]) for k in ('y','candidate_A','candidate_B','comparator_A','comparator_B')])
    eligible=[p for p,ix in groups.items() if complete[ix,:].all()]
    def patient_target(p,j,method):
        ka,kb=METHODS[method]
        return mean((((float(a[ka][i,j])-float(a['y'][i,j]))**2)+((float(a[kb][i,j])-float(a['y'][i,j]))**2))/2 for i in groups[p])
    def summarize(chosen):
        if not chosen:return None
        risks={m:[mean(patient_target(p,j,m) for j in range(t)) for p in chosen] for m in METHODS}
        pertarget={m:[mean(patient_target(p,j,m) for p in chosen) for j in range(t)] for m in METHODS}
        delta=np.asarray(risks['candidate'])-risks['comparator']
        rng=np.random.default_rng(20260930)
        indices=rng.integers(0,len(chosen),(10000,len(chosen)))
        boot=[mean(delta[row]) for row in indices]
        cm,im=mean(risks['candidate']),mean(risks['comparator'])
        return {'patients':len(chosen),'candidate_mse':cm,'comparator_mse':im,
          'relative_mse_reduction':None if im==0 else 1-cm/im,
          'strict_patient_wins':int((delta<0).sum()),'strict_patient_losses':int((delta>0).sum()),'ties':int((delta==0).sum()),
          'target_nonworse':sum(c<=i for c,i in zip(pertarget['candidate'],pertarget['comparator'])),
          'p90_patient_rmse':{m:percentile([math.sqrt(x) for x in v],.9) for m,v in risks.items()},
          'target_mse':{m:dict(zip(map(str,a['targets']),v)) for m,v in pertarget.items()},
          'descriptive_delta_ci95':[percentile(boot,.025),percentile(boot,.975)]}
    pertarget=[]
    for j,name in enumerate(a['targets']):
        chosen=[p for p,ix in groups.items() if complete[ix,j].all()]
        c=[patient_target(p,j,'candidate') for p in chosen];i=[patient_target(p,j,'comparator') for p in chosen]
        pertarget.append({'target':str(name),'complete_patients':len(chosen),'original_patients':len(patients),
          'complete_pdos_in_these_patients':sum(len(groups[p]) for p in chosen),
          'candidate_conditional_mse':mean(c) if c else None,'comparator_conditional_mse':mean(i) if i else None,
          'patient_wins':sum(x<y for x,y in zip(c,i)),'patient_losses':sum(x>y for x,y in zip(c,i)),
          'estimand':'equal-patient conditional error for this target; differing support across targets'})
    full=bool(complete.all())
    return {'original_pdos':n,'original_patients':len(patients),'targets':t,'full_primary_estimable':full,
      'primary':summarize(patients) if full else None,'complete_patient_conditional':summarize(eligible),
      'complete_patients':len(eligible),'complete_pdos':int(complete.all(axis=1).sum()),
      'pdos_in_complete_patients':sum(len(groups[p]) for p in eligible),
      'complete_sample_target_cells':int(complete.sum()),'sample_target_cells':n*t,
      'complete_sample_target_fraction':float(complete.mean()),
      'per_target_conditional':pertarget,
      'no_primary_rescue':True,'no_source_response_read':True,'no_refit':True}

def verify_against(actual,old):
    checks={'full_primary':actual['full_primary_estimable']==old['full_primary_estimable'],
      'complete_patients':actual['complete_patients']==old['complete_patients'],
      'primary_null_preserved':(actual['primary'] is None)==(old['primary'] is None),
      'fraction':abs(actual['complete_sample_target_fraction']-old['complete_sample_target_fraction'])<1e-15}
    def compare(a,b,path):
        if isinstance(a,dict):
            for key,value in a.items():compare(value,b[key],path+'/'+key)
        elif isinstance(a,list):
            checks[path]=len(a)==len(b) and all(abs(x-y)<1e-14 for x,y in zip(a,b))
        elif a is None:checks[path]=b is None
        elif isinstance(a,(float,np.floating)):checks[path]=abs(a-b)<1e-14
        else:checks[path]=a==b
    compare(actual['complete_patient_conditional'],old['complete_patient_conditional'],'conditional')
    if actual['primary'] is not None:compare(actual['primary'],old['primary'],'primary')
    for row in actual['per_target_conditional']:
        checks['coverage/'+row['target']]=row['complete_patients']==old['target_complete_patient_counts'][row['target']]
    if not actual['full_primary_estimable']:
        checks['gate_remains_null']=old['gate'] is None
        checks['no_confirmation_success']=old['new_independent_confirmation'] is False
    return checks

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--predictions',type=Path,required=True);ap.add_argument('--result',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args()
    with np.load(args.predictions,allow_pickle=False) as z:a={k:z[k].copy() for k in z.files}
    old=json.loads(args.result.read_text())
    assert hashlib.sha256(args.predictions.read_bytes()).hexdigest()==old['prediction_sha256']
    assert a['y'].shape==(61,22) and len(set(a['patients']))==31
    report=analyze(a);checks=verify_against(report,old)
    report.update(status='PASS' if all(checks.values()) else 'FAIL',checks=checks,verification_implementation='Python math.fsum and explicit group loops; independent of frozen scorer',external_independent_reviewer=False,original_result_sha256=hashlib.sha256(args.result.read_bytes()).hexdigest(),prediction_sha256=old['prediction_sha256'])
    with args.output.open('x') as f:json.dump(report,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps({'status':report['status'],'checks':len(checks),'failed':[k for k,v in checks.items() if not v],'complete_pdos':report['complete_pdos'],'pdos_in_complete_patients':report['pdos_in_complete_patients']},indent=2))
    assert all(checks.values())
if __name__=='__main__':main()
