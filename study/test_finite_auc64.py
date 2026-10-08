"""Synthetic fixtures only; never loads biological curves or outcomes."""
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
import json
import numpy as np
import finite_auc64 as model
import run_finite_auc64 as run
from coverage_methods import CoverageCatalog,validate_plan

def main():
    rng=np.random.default_rng(2026100814);checks=[]
    basis=model.covariance_basis([1,10,100,1000])
    assert basis.shape==(11,8,8)
    assert min(np.linalg.eigvalsh(k).min() for k in basis)>-1e-12
    checks.append('all_11_covariance_components_PSD')
    A=rng.normal(size=(8,8));C=A@A.T+np.eye(8);mu=rng.normal(size=8);Q=rng.normal(size=(8,3))
    b,c,k=model.known_plus_missing(C,mu,Q,np.arange(8));x=rng.normal(size=(4,8))
    assert np.max(abs((c+x@b)-x@Q))<1e-12
    checks.append('all_observed_exact_raw_endpoint')
    obs=np.array([1,3,6]);un=np.array([0,2,4,5,7]);b,c,k=model.known_plus_missing(C,mu,Q,obs)
    q=rng.normal(size=(5,3));missing=mu[un]+(q-mu[obs])@np.linalg.solve(C[np.ix_(obs,obs)],C[np.ix_(obs,un)])
    explicit=q@Q[obs]+missing@Q[un]
    assert np.max(abs(c+q@b-explicit))<1e-12 and np.array_equal(k,Q[obs])
    checks.append('known_plus_missing_Gaussian_algebra')
    b,c,k=model.known_plus_missing(np.eye(8),mu,Q,obs)
    assert np.array_equal(b,Q[obs]) and np.max(abs(c-mu[un]@Q[un]))<1e-12
    checks.append('independent_missing_cells_use_prior_only')
    p=np.array(['a','a','a','b']);w=model.patient_weights(p)
    assert np.allclose([w[p==u].sum() for u in np.unique(p)],[.5,.5])
    checks.append('equal_whole_patient_weights')
    n=18;m=96;owners=np.repeat(np.arange(24),4);doses=np.tile([1.,10.,100.,1000.],24)
    values=rng.normal(size=(n,m,2));patients=np.repeat([f'Pt{i}' for i in range(9)],2)
    cat=CoverageCatalog(np.array([f'q{i}' for i in range(m)]),np.array([f't{i}' for i in range(24)]),owners,tuple(str(x) for x in doses),'lib1')
    quadrature=np.zeros((m*2,24))
    for j in range(24):quadrature[np.repeat(owners,2)==j,j]=1/8
    y=values.reshape(n,-1)@quadrature
    full={'values':values,'owner':owners,'doses':doses,'q':quadrature,'query_to_full':np.arange(m)}
    plan=run.core.plan_panel_fast(values,y,patients,cat);validate_plan(plan,cat)
    populations=model.fit_population(full,patients)
    for pool in model.POOLING:
        state=model.condition(populations,plan,full,pool)
        for orientation in ('A','B'):
            paid=run.core.paid(values,plan,orientation)
            result=model.predict(state,paid,orientation)
            assert result.shape==(n,24) and np.isfinite(result).all()
            masked=np.full_like(values,np.nan)
            masked[:,plan['selected_native_indices'],plan[f'orientation_{orientation}_plate_indices']]=paid
            assert np.array_equal(result,model.predict(state,run.core.paid(masked,plan,orientation),orientation))
            assert np.array_equal(state[orientation]['known_weights'],model.exact_paid_weights(plan,full,orientation))
    checks.append('three_priors_24_targets_64_distinct_32_per_plate')
    checks.append('no_unpurchased_value_dependency')
    checks.append('physical_quadrature_weights_preserved')
    try:model.predict(state,np.full((1,64),np.nan),'A')
    except ValueError:pass
    else:raise AssertionError('nonfinite paid values accepted')
    checks.append('nonfinite_inputs_rejected')
    print(json.dumps({'status':'PASS','synthetic_only':True,'checks':checks}),flush=True)
if __name__=='__main__':main()
