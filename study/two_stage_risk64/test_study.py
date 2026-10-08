import unittest,itertools,inspect
import numpy as np
from types import SimpleNamespace
import policy as p

class RiskTests(unittest.TestCase):
    def fixture(self):
        rng=np.random.default_rng(137);means=rng.normal(size=(5,8));r=rng.normal(size=(8,8));cov=r@r.T+.2*np.eye(8)
        weights=np.arange(1,6,dtype=float);weights/=weights.sum();q=np.arange(1,9,dtype=float);q/=q.sum()
        return {'means':means,'covariance':cov,'weights':weights},q
    def test_conditional_risk_independent_full_gaussian_expression(self):
        pop,q=self.fixture();a=np.array([0,3]);beta=np.array([.2,-.3,.7]);intercept=.19;extra=5
        state=p.risk_state(pop,a,q,beta,intercept,extra);x=np.array([[.1,.5],[-1.,2.],[3.,-2.]])
        expected=[];c=pop['covariance'];means=pop['means'];w=pop['weights'];chol=np.linalg.cholesky(c[np.ix_(a,a)])
        functional=-q.copy();functional[extra]+=.7
        for observed in x:
            delta=observed-means[:,a];solved=np.linalg.solve(chol,delta.T).T;mass=w*np.exp(-.5*np.sum(solved**2,axis=1));mass/=mass.sum()
            condition_mean=means+np.linalg.solve(c[np.ix_(a,a)],delta.T).T@c[a]
            condition_cov=c-c[:,a]@np.linalg.solve(c[np.ix_(a,a)],c[a])
            residual_mean=intercept+observed@beta[:2]+condition_mean@functional
            expected.append(float(functional@condition_cov@functional+mass@(residual_mean**2)))
        np.testing.assert_allclose(p.conditional_risk(state,x),expected,atol=2e-12,rtol=0)
    def test_unconditional_risk_direct(self):
        pop,q=self.fixture();a=np.array([0,3]);beta=np.array([.2,-.3,.7]);state=p.risk_state(pop,a,q,beta,.19,5)
        v=-q.copy();v[a]+=beta[:2];v[5]+=.7
        expected=v@pop['covariance']@v+pop['weights']@((.19+pop['means']@v)**2)
        self.assertAlmostEqual(float(state['unconditional_risk']),float(expected),places=12)
    def test_known_endpoint_has_zero_risk(self):
        pop,q=self.fixture();q[:]=0;q[0]=.4;q[3]=.6
        state=p.risk_state(pop,[0,3],q,[.4,.6],0.)
        np.testing.assert_allclose(p.conditional_risk(state,np.array([[2.,3.],[0.,1.]])),0.,atol=1e-12)
    def test_missing_first_reading_rejected(self):
        pop,q=self.fixture();s=p.risk_state(pop,[0,3],q,[.4,.6],0.)
        with self.assertRaises(ValueError):p.conditional_risk(s,np.array([[np.nan,3.]]))
    def test_risk_excludes_candidate_reading(self):
        self.assertEqual(list(inspect.signature(p.conditional_risk).parameters),['state','observed'])
    def test_extreme_finite_observed_risk(self):
        pop,q=self.fixture();s=p.risk_state(pop,[0,3],q,[.4,.6,.3],0.,5)
        self.assertTrue(np.isfinite(p.conditional_risk(s,np.full((2,2),1e4))).all())
    def test_dp_matches_brute_force(self):
        rng=np.random.default_rng(717);cost=rng.normal(size=(6,3));path,loss=p.balanced_choices(cost,2)
        possibilities=[(sum(cost[j,k] for j,k in enumerate(codes)),codes) for codes in itertools.product(range(3),repeat=6) if codes.count(1)==2 and codes.count(2)==2]
        expected=min(possibilities);self.assertAlmostEqual(loss,expected[0]);self.assertEqual(tuple(path),expected[1])
    def test_dp_tie_is_deterministic(self):
        a,l=p.balanced_choices(np.zeros((6,3)),2);b,ll=p.balanced_choices(np.zeros((6,3)),2)
        np.testing.assert_array_equal(a,b);self.assertEqual(sum(a==1),2);self.assertEqual(sum(a==2),2)
    def test_dp_infeasible_rejected(self):
        with self.assertRaises(ValueError):p.balanced_choices(np.ones((3,3)),2)
    def test_ridge_complement_invariance(self):
        rng=np.random.default_rng(98);x=rng.normal(size=(15,4,2));y=rng.normal(size=15);patients=np.array([f'p{i//2}' for i in range(15)])
        a,b=p.fit_ridge(x,y,patients,[0,3,4]);c,d=p.fit_ridge(x,y,patients,[1,2,5]);np.testing.assert_allclose(a,c,atol=1e-12,rtol=0);self.assertAlmostEqual(b,d)

class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rng=np.random.default_rng(991);cls.full=rng.normal(size=(22,72,2));cls.owner=np.repeat(np.arange(24),3)
        cls.q=np.zeros((144,24))
        for j in range(24):cls.q[6*j:6*j+6,j]=np.repeat([.25,.5,.25],2)/2
        cls.y=cls.full.reshape(22,-1)@cls.q;cls.pat=np.array([f'p{i//2}' for i in range(22)])
        cls.cat=SimpleNamespace(native_target_indices=cls.owner)
        cls.pos=[np.array([0.,.5,1.]) for _ in range(24)]
        cls.plan={'choices':[{'best2':[3*j,3*j+1]} for j in range(24)]}
        cls.bank=p.build_bank(cls.full[:16],cls.y[:16],cls.pat[:16],cls.cat,cls.owner,np.arange(72),cls.q,cls.pos,cls.plan)
    def initial(self,seed):
        return np.stack([self.full[16:][:,self.bank[f't{j}_initial_native'],[seed,1-seed]] for j in range(24)],axis=1)
    def final(self,actions,seed):
        values=np.full(actions.shape,np.nan)
        for i,row in enumerate(actions):
            for j,k in enumerate(row):
                if k:values[i,j]=self.full[i+16,int(self.bank[f't{j}_s{seed}_option_native'][k]),int(self.bank[f't{j}_s{seed}_option_plate'][k])]
        return values
    def test_dynamic_exact_budget(self):
        for seed in (0,1):
            actions,_=p.choose_actions(self.bank,self.initial(seed),seed);self.assertTrue(p.validate_actions(self.bank,actions,seed))
            self.assertTrue(np.all(np.sum(actions>0,axis=1)==16))
    def test_static_plan_does_not_depend_on_first_readings(self):
        initial=self.initial(0);a,_=p.choose_actions(self.bank,initial,0,False);b,_=p.choose_actions(self.bank,initial+100,0,False)
        np.testing.assert_array_equal(a,b);np.testing.assert_array_equal(a,np.repeat(a[:1],len(a),axis=0))
    def test_both_estimators_are_finite(self):
        x=self.initial(1);a,_=p.choose_actions(self.bank,x,1);z=self.final(a,1)
        for estimator in ('ridge','mixture'):
            prediction=p.infer(self.bank,x,a,z,1,estimator);self.assertEqual(prediction.shape,(6,24));self.assertTrue(np.isfinite(prediction).all())
    def test_unbought_final_slots_have_no_effect(self):
        x=self.initial(0);a,_=p.choose_actions(self.bank,x,0);z=self.final(a,0);changed=z.copy();changed[a==0]=999
        for estimator in ('ridge','mixture'):
            np.testing.assert_array_equal(p.infer(self.bank,x,a,z,0,estimator),p.infer(self.bank,x,a,changed,0,estimator))
    def test_missing_purchased_final_value_rejected(self):
        x=self.initial(0);a,_=p.choose_actions(self.bank,x,0);z=self.final(a,0);z[tuple(np.argwhere(a>0)[0])]=np.nan
        with self.assertRaises(ValueError):p.infer(self.bank,x,a,z,0)
    def test_fewer_than_64_wells_rejected(self):
        x=self.initial(0);a,_=p.choose_actions(self.bank,x,0);a[tuple(np.argwhere(a>0)[0])]=0
        with self.assertRaises(ValueError):p.validate_actions(self.bank,a,0)
    def test_query_values_do_not_enter_fitting(self):
        mutated=self.full.copy();mutated[16:]+=500;labels=self.y.copy();labels[16:]-=100
        bank=p.build_bank(mutated[:16],labels[:16],self.pat[:16],self.cat,self.owner,np.arange(72),self.q,self.pos,self.plan)
        for k in self.bank:np.testing.assert_array_equal(bank[k],self.bank[k])
    def test_numeric_bank_roundtrip(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'model.npz';np.savez_compressed(path,**self.bank)
            with np.load(path,allow_pickle=False) as z:bank={k:z[k].copy() for k in z.files}
        x=self.initial(0);a,_=p.choose_actions(self.bank,x,0);b,_=p.choose_actions(bank,x,0);np.testing.assert_array_equal(a,b)
        np.testing.assert_array_equal(p.infer(bank,x,b,self.final(b,0),0),p.infer(self.bank,x,a,self.final(a,0),0))

if __name__=='__main__':unittest.main(verbosity=2)
