import unittest
import numpy as np
import elife_sparse as e

class Tests(unittest.TestCase):
    def test_auc_constant(self):
        d=np.array([1.,2.,4.,8.]);v=np.full((3,4),.37)
        np.testing.assert_allclose(e.auc(d,v),.37,atol=1e-15)

    def test_auc_log_linear(self):
        d=np.array([1.,2.,4.,8.]);x=np.log(d);v=2+3*x
        self.assertAlmostEqual(e.auc(d,v),2+3*(x[0]+x[-1])/2,places=14)

    def fixture(self):
        rng=np.random.default_rng(44);curves=[];n=12
        y=np.empty((n,5))
        for j,m in enumerate([8,9,10,11,12]):
            doses=np.geomspace(.01,10,m)
            latent=rng.normal(size=n)
            values=np.stack([.5+.12*latent[i]+.04*j+(.15+.01*j)*np.log10(doses+0.02)+rng.normal(0,.015,m) for i in range(n)])
            y[:,j]=e.auc(doses,values)
            curves.append({"drug":e.DRUGS[j],"doses":doses,"values":values,"source_indices":np.arange(m)})
        return curves,y

    def test_learned_plan_budget_and_ownership(self):
        c,y=self.fixture();p=e.learned_plan(c,y,np.arange(11))
        self.assertEqual(len(p["selected"]),13);self.assertEqual(len(set(map(tuple,p["selected"]))),13)
        self.assertEqual(len(p["upgraded"]),3)
        self.assertEqual([p["owner"].count(j) for j in range(5)].count(3),3)

    def test_interpolation_plan_budget(self):
        c,y=self.fixture();p=e.interpolation_plan(c,y,np.arange(11))
        self.assertEqual(sum(3 if d in p["upgraded"] else 2 for d in e.DRUGS),13)

    def test_fit_predict_finite(self):
        c,y=self.fixture();p=e.learned_plan(c,y,np.arange(11))
        m=e.fit_model(c,y,np.arange(11),p,.1);q=e.predict_model(c,[11],p,m)
        self.assertEqual(q.shape,(1,5));self.assertTrue(np.isfinite(q).all())

    def test_own_drug_isolation(self):
        c,y=self.fixture();p=e.learned_plan(c,y,np.arange(11));m=e.fit_model(c,y,np.arange(11),p,.1)
        x0=e.feature_matrix(c,[11],p)
        c2=[]
        for q in c:c2.append({**q,"values":q["values"].copy()})
        for j,k in p["selected"]:
            if j==2:c2[j]["values"][11,k]+=3
        a=e.predict_model(c,[11],p,m)[0];b=e.predict_model(c2,[11],p,m)[0]
        changed=np.flatnonzero(np.abs(a-b)>1e-12)
        np.testing.assert_array_equal(changed,[2])

    def test_interpolation_constant_exact(self):
        d=np.geomspace(.01,10,9);v=np.full(9,.64)
        for s in [(0,8),(2,5),(1,4,7)]:
            self.assertAlmostEqual(e.interp_auc(v,d,s),.64,places=14)

    def test_lambda_selection_registered(self):
        c,y=self.fixture();lam,s=e.select_lambda(c,y,np.arange(11))
        self.assertIn(lam,e.LAMBDAS);self.assertEqual(set(map(float,s.keys())),set(e.LAMBDAS))

    def test_bootstrap_deterministic(self):
        a=e.bootstrap_delta([-1,-2,-3]);b=e.bootstrap_delta([-1,-2,-3])
        self.assertEqual(a,b);self.assertLess(a[1],0)

    def test_bad_auc_rejected(self):
        with self.assertRaises(ValueError):e.auc([1],[2])
        with self.assertRaises(ValueError):e.auc([1,0],[2,3])

if __name__=="__main__":unittest.main(verbosity=2)