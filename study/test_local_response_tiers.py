"""Synthetic only: no original patient responses are read by these tests."""
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
import json
import numpy as np
import local_response_tiers as m
from coverage_methods import CoverageCatalog

def independent_one(s,q,j,kind,h,rho):
    z=(q-s['mean_x'])/s['scale_x'];t=s['kernel_z'];cols=np.flatnonzero(s['kernel_owner']==j);w=s['kernel_weights']
    if kind=='own':distance=((t[:,cols]-z[cols])**2).mean(1)
    else:
        response=(s['mean_y']+z@s['beta']-s['response_mean'])/s['response_scale']
        distance=((s['response_training']-response)**2).mean(1)
    logk=-distance/(2*h*h);kw=np.exp(logk-logk.max())*w;kw/=kw.sum();weights=(1-rho)*w+rho*kw
    X=np.c_[np.ones(len(t)),t[:,cols]];D=np.diag(np.r_[0.,np.repeat(.01,len(cols))])
    beta=np.linalg.solve(X.T@(weights[:,None]*X)+D,X.T@(weights*s['train_y'][:,j]))
    return float(np.r_[1.,z[cols]]@beta)

def main():
    rng=np.random.default_rng(202610081423)
    owner=np.repeat(np.arange(24),6);cat=CoverageCatalog(np.asarray([f'q{i}' for i in range(144)]),np.asarray([f't{i:02d}' for i in range(24)]),owner,tuple(['1','3','10','30','100','300']*24),'lib1')
    patients=np.repeat(np.asarray([f'Pt{i}' for i in range(12)]),2)
    x=rng.normal(size=(24,144,2));y=np.stack([np.tanh(x[:,owner==j].mean((1,2)))+.01*rng.normal(size=24) for j in range(24)],axis=1)
    fitted=m.fit(x,y,patients,cat);maxdiff=0.;changed=0.
    for b in m.BUDGETS:
        fit=fitted[b];plan=fit['model'][0];s=fit['state'];m.tiers.validate(plan,cat)
        allpred=m.predict_all(x[:3],fit)
        assert allpred.shape==(70,2,3,24)
        for oi,o in enumerate(('A','B')):
            pp=m.tiers.paid(x[:3],plan,o)
            assert np.max(abs(m.local_delta(s,pp,('own',.7,0.))))<1e-12
            mask=np.full_like(x[:3],np.nan);mask[:,s['native'],s['plate_'+o]]=pp
            for i in range(7):
                idx=10*i+2;replayed=m.replay(s,pp,idx)
                maxdiff=max(maxdiff,float(np.max(abs(replayed-allpred[idx,oi]))))
                assert np.array_equal(m.tiers.paid(mask,plan,o),pp)
            for config in m.CONFIGS[1:]:
                delta=m.local_delta(s,pp,config);base=s['mean_y']+((pp-s['mean_x'])/s['scale_x'])@s['beta']
                changed=max(changed,float(np.max(abs(delta))))
                for j in (0,12,23):
                    expected=independent_one(s,pp[0],j,*config)
                    maxdiff=max(maxdiff,abs(expected-(base[0,j]+delta[0,j])))
        assert len(set(plan['selected_native_indices']))==b and plan['per_plate']==[b//2,b//2] if b!=64 else len(set(plan['selected_native_indices']))==64
        try:m.local_delta(s,np.ones((1,b-1)),m.CONFIGS[1])
        except ValueError:pass
        else:raise AssertionError('wrong budget accepted')
        try:m.local_delta(s,np.full((1,b),np.nan),m.CONFIGS[1])
        except ValueError:pass
        else:raise AssertionError('nonfinite accepted')
    s=fitted[64]['state'];p=m.tiers.paid(x[:2],fitted[64]['model'][0],'A')
    # Duplicating an entire patient's observations must preserve their total prior mass.
    chosen=s['training_patients']==s['training_patients'][0]
    replica=dict(s)
    for key in ('kernel_z','train_y','response_training'):
        replica[key]=np.r_[s[key],s[key][chosen]]
    original_weights=s['kernel_weights'].copy();original_weights[chosen]/=2
    replica['kernel_weights']=np.r_[original_weights,s['kernel_weights'][chosen]/2]
    for config in m.CONFIGS[1:]:assert np.allclose(m.local_delta(s,p,config),m.local_delta(replica,p,config),atol=1e-12,rtol=0)
    assert maxdiff<1e-11 and changed>1e-8
    print(json.dumps({'status':'PASS','synthetic_only':True,'budgets':list(m.BUDGETS),'checks':['rho0_reproduces_global_ridge','locality_changes_nonlinear_fixture','independent_augmented_normal_equations','whole_patient_duplicate_invariance','budget_accounting','unpaid_input_isolation','wrong_budget_and_nonfinite_rejection','70_option_replay'],'maximum_numeric_difference':maxdiff,'nonzero_locality_effect':changed}),flush=True)
if __name__=='__main__':main()
