"""Synthetic fixtures only. No biological source data are loaded."""
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
import json,time
import numpy as np
import nonlinear_panel64 as n
from coverage_methods import CoverageCatalog,validate_plan

def main():
    t=time.monotonic();rng=np.random.default_rng(2026100813)
    owners=np.repeat(np.arange(24),4)
    cat=CoverageCatalog(np.array([f'q{i}' for i in range(96)]),np.array([f't{i:02}' for i in range(24)]),owners,tuple(['1','10','100','1000']*24),'lib1')
    patients=np.repeat(np.array([f'Pt{i}' for i in range(9)]),2)
    x=rng.normal(size=(18,96,2))
    y=np.stack([x[:,owners==j].mean(axis=(1,2)) for j in range(24)],axis=1)
    start=n.core.plan_panel_fast(x,y,patients,cat)
    validate_plan(start,cat)
    model=n.fit_model(x,y,patients,start)
    guesses=n.predict_options(x,model)
    assert guesses.shape==(10,2,18,24) and np.isfinite(guesses).all()
    saved=n.payload(model,2)
    diff=0.
    for oi,o in enumerate(('A','B')):
        paid=n.core.paid(x,start,o)
        restored=n.replay(saved,paid)
        diff=max(diff,float(np.max(abs(restored-guesses[2,oi]))))
        masked=np.full_like(x,np.nan)
        masked[:,saved['native'],saved['plate_'+o]]=paid
        assert np.array_equal(paid,n.core.paid(masked,start,o))
        assert np.allclose(n.replay(saved,n.core.paid(masked,start,o)),restored,atol=1e-13)
    assert diff<1e-12
    try:n.replay(saved,np.full((1,64),np.nan))
    except ValueError:pass
    else:raise AssertionError('nonfinite measurements accepted')
    changed=n.optimize(x,y,patients,cat,start)
    validate_plan(changed,cat)
    stats=changed['nonlinear_selection']
    assert stats['final']<=stats['initial']+1e-12
    assert len(set(changed['selected_native_indices']))==64
    assert changed['orientation_A_plate_indices']==start['orientation_A_plate_indices']
    assert changed['coordinate_target_indices']==start['coordinate_target_indices']
    # Alternative layout losses must not collapse into a free prediction average.
    q=np.stack([y+1,y-1]);assert abs(n.risk(q,y,patients)-1)<1e-12
    # Unequal numbers of samples still give each whole patient equal mass.
    p=np.array(['a','a','a','b']);true=np.zeros((4,24));pred=np.zeros((2,4,24));pred[:,3]=2
    assert abs(n.risk(pred,true,p)-2)<1e-12
    print(json.dumps({'status':'PASS','tests':['64-distinct-budget','32-per-plate','fixed-cardinality','10-option-output','saved-model-replay','unpaid-input-isolation','nonfinite-rejection','monotone-planning-objective','A/B-loss-not-ensemble','whole-patient-weighting'],'synthetic_replay_maxdiff':diff,'panels_scored':stats['panels_scored'],'seconds':time.monotonic()-t}),flush=True)
if __name__=='__main__':main()
