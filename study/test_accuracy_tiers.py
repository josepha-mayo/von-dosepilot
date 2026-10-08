"""Synthetic accounting and arithmetic only. No biological inputs."""
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
import itertools,json
import numpy as np
import accuracy_tiers as m
from coverage_methods import CoverageCatalog

def main():
    costs=[{2:5.,3:3.,4:2.},{2:6.,3:4.,4:3.},{2:7.,3:6.,4:1.}]
    exact=min((sum(costs[j][k] for j,k in enumerate(path)),path) for path in itertools.product((2,3,4),repeat=3) if sum(path)==8)
    assert m.optimal_sizes(costs,8)==exact
    rng=np.random.default_rng(2026100815);n=18;owners=np.repeat(np.arange(24),7);native=len(owners)
    concentrations=tuple(str(v) for v in np.tile([1,3,10,30,100,300,1000],24))
    cat=CoverageCatalog(np.array([f'q{i}' for i in range(native)]),np.array([f't{i:02d}' for i in range(24)]),owners,concentrations,'lib1')
    p=np.repeat([f'Pt{i}' for i in range(9)],2);x=rng.normal(size=(n,native,2))
    y=np.stack([x[:,owners==j].mean(axis=(1,2)) for j in range(24)],axis=1)
    models=m.fit_models(x,y,p,cat);maximum=0.
    for B,(plan,base,kernel,coefs) in models.items():
        assert m.validate(plan,cat) and len(set(plan['selected_native_indices']))==B
        assert np.count_nonzero(np.asarray(plan['orientation_A_plate_indices'])==0)==B//2
        pred=m.predict_options(x,models[B]);assert pred.shape==(10,2,n,24)
        s=m.payload(models[B],2)
        for oi,o in enumerate(('A','B')):
            pp=m.paid(x,plan,o);r=m.replay(s,pp)
            maximum=max(maximum,float(np.max(abs(r-pred[2,oi]))))
            masked=np.full_like(x,np.nan);masked[:,s['native'],s['plate_'+o]]=pp
            assert np.array_equal(pp,m.paid(masked,plan,o))
            assert np.array_equal(r,m.replay(s,m.paid(masked,plan,o)))
        try:m.replay(s,np.zeros((1,B-1)))
        except ValueError:pass
        else:raise AssertionError('wrong budget accepted')
    plan,base,kernel,coefs=models[64]
    original=m.core.BandwidthAdditive(kernel.z,kernel.residual,kernel.w,kernel.owner,.7)
    assert np.max(abs(original.coefficients(1.,.1)[0]-coefs[2]))<1e-12
    assert maximum<1e-12
    print(json.dumps({'status':'PASS','synthetic_only':True,'budgets':list(m.BUDGETS),'checks':['knapsack_vs_exhaustive','exact_distinct_budget','exact_plate_balance','same_24_targets','finite_outputs','saved_model_replay','unpaid_isolation','wrong_budget_rejection','original64_kernel_equivalence'],'max_replay_difference':maximum}),flush=True)
if __name__=='__main__':main()
