"""Synthetic-only tests for standard-control calibration, no response files read."""
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
import json
import numpy as np
import control_transfer_tiers as c

def main():
    rng=np.random.default_rng(202610081433)
    Q=rng.normal(size=(48,10));R=rng.normal(size=(48,24));p=np.repeat(np.array([f'p{i}' for i in range(12)]),4)
    errors=[]
    for o,dim in (('A',7),('B',11)):
        F=c.features(Q,o);assert F.shape==(48,dim)
        model=c.fit(Q,R,p,o);w=c.local.tiers.patient_weights(p)
        X=np.c_[np.ones(48),F];D=np.diag(np.r_[0.,np.repeat(float(model['lambda']),dim)])
        beta=np.linalg.solve(X.T@(w[:,None]*X)+D,X.T@(w*R.mean(1)))
        own=model['common_mean']+(F-model['feature_mean'])@model['common_beta']
        errors.append(float(np.max(abs(X@beta-own))))
        sv=np.linalg.svd(model['rank1_beta'],compute_uv=False);assert sv[1]<1e-12
        assert np.max(abs(model['rank1_beta'].sum(1)))<1e-12
        assert abs(model['deviation_mean'].sum())<1e-12
        for a in c.ARMS:
            result=c.predict(model,Q,o,a);assert result.shape==(48,24) and np.isfinite(result).all()
        zero=c.fit(Q,np.zeros_like(R),p,o)
        for a in c.ARMS:assert np.max(abs(c.predict(zero,Q,o,a)))==0
        # A constant common error is learned by the unpenalized intercept.
        constant=c.fit(Q,np.ones_like(R)*.05,p,o)
        assert np.max(abs(c.predict(constant,Q,o,'full_common')-.05))<1e-12
        # Repeated samples from the same whole patient must retain their total mass.
        keep=p==p[0];dup=c.fit(np.r_[Q,Q[keep]],np.r_[R,R[keep]],np.r_[p,p[keep]],o)
        assert np.max(abs(c.predict(model,Q,o,'full_common')-c.predict(dup,Q,o,'full_common')))<1e-12
    for bad in (np.ones((2,9)),np.full((2,10),np.nan)):
        try:c.features(bad,'A')
        except ValueError:pass
        else:raise AssertionError('invalid QC accepted')
    try:c.features(Q,'unknown')
    except ValueError:pass
    else:raise AssertionError('unknown orientation accepted')
    assert max(errors)<1e-11
    print(json.dumps({'status':'PASS','synthetic_only':True,'checks':['A7_B11_quality_basis','independent_augmented_common_regression','rank1_deviation','zero_deviation_sum','zero_error_no_correction','constant_error_intercept','whole_patient_duplicate_invariance','invalid_quality_rejection'],'max_regression_difference':max(errors)}),flush=True)
if __name__=='__main__':main()
