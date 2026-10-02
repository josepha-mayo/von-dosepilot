import unittest
import numpy as np
from structured_kernel import StructuredKernel

class Tests(unittest.TestCase):
    def setUp(self):
        self.rng=np.random.default_rng(10021300)
        self.z=self.rng.normal(size=(20,64))
        self.r=self.rng.normal(scale=.1,size=(20,24))
        v=self.rng.uniform(.1,1.,20);self.w=v/v.sum()
        self.owner=np.repeat(np.arange(24),[3]*16+[2]*8)
    def model(self,kind='pair_mix'):
        return StructuredKernel(self.z,self.r,self.w,self.owner,kind)
    def test_pair_formula_explicit(self):
        m=self.model();query=self.rng.normal(size=(7,64));total,pairs=m.pair_components(query)
        components=[]
        for group,k,a,b in zip(m.groups,m.gaussian_groups(query),m.group_means,m.group_grands):
            components.append(len(group)*(k-(k@m.w)[:,None]-a[None,:]+b))
        explicit=sum(components[j]*components[k] for j in range(24) for k in range(j+1,24))
        np.testing.assert_allclose(total,sum(components),atol=1e-13,rtol=0)
        np.testing.assert_allclose(pairs,explicit,atol=2e-12,rtol=0)
    def test_psd(self):
        for kind in ('pair_mix','mean_shape'):
            m=self.model(kind);k=m.raw_cross(self.z)
            self.assertGreater(np.linalg.eigvalsh((k+k.T)/2).min(),-1e-10)
    def test_training_centering(self):
        for kind in ('pair_mix','mean_shape'):
            m=self.model(kind);k=m.centered_cross(self.z)
            np.testing.assert_allclose(k@self.w,0.,atol=1e-12)
            np.testing.assert_allclose(self.w@k,0.,atol=1e-12)
    def test_query_batch_invariance(self):
        for kind in ('pair_mix','mean_shape'):
            m=self.model(kind);x=self.rng.normal(size=(4,64));coef=m.coefficients(1.,.1)[0]
            batch=m.predict(x,coef);single=np.vstack([m.predict(a[None,:],coef) for a in x])
            np.testing.assert_allclose(batch,single,atol=1e-13,rtol=0)
    def test_row_order(self):
        order=self.rng.permutation(20);x=self.rng.normal(size=(3,64))
        for kind in ('pair_mix','mean_shape'):
            m=self.model(kind);n=StructuredKernel(self.z[order],self.r[order],self.w[order],self.owner,kind)
            a=m.predict(x,m.coefficients(1.,.1)[0]);b=n.predict(x,n.coefficients(1.,.1)[0])
            np.testing.assert_allclose(a,b,atol=1e-13,rtol=0)
    def test_global_group_shift_invariant_nonlinear(self):
        # Same offset at train and query must not change either nonlinear metric.
        offset=self.rng.normal(size=24)[self.owner];x=self.rng.normal(size=(3,64))
        for kind in ('pair_mix','mean_shape'):
            m=self.model(kind);n=StructuredKernel(self.z+offset,self.r,self.w,self.owner,kind)
            a=m.raw_cross(x)-x@self.z.T;b=n.raw_cross(x+offset)-(x+offset)@(self.z+offset).T
            np.testing.assert_allclose(a,b,atol=3e-12,rtol=0)
    def test_direct_dual_ridge(self):
        for kind in ('pair_mix','mean_shape'):
            m=self.model(kind);sw=np.sqrt(self.w);k=m.centered_cross(self.z)
            h=sw[:,None]*k*sw[None,:]+np.eye(20)
            direct=sw[:,None]*np.linalg.solve(h,sw[:,None]*self.r)
            coef,_,_=m.coefficients(1.,0.)
            # Coefficients need not be unique when 24 outputs exceed kernel rank.
            # Compare identifiable predictions in training and query spaces.
            np.testing.assert_allclose(k@coef,k@direct,atol=2e-13,rtol=0)
            query=self.rng.normal(size=(5,64));cross=m.centered_cross(query)
            np.testing.assert_allclose(cross@coef,cross@direct,atol=2e-13,rtol=0)
    def test_zero_features(self):
        for kind in ('pair_mix','mean_shape'):
            m=StructuredKernel(np.zeros_like(self.z),self.r,self.w,self.owner,kind)
            co=m.coefficients(1.,.1)[0]
            np.testing.assert_allclose(m.predict(np.zeros((2,64)),co),0.,atol=1e-13)
    def test_unknown_kind(self):
        with self.assertRaises(ValueError):self.model('anything')
    def test_nonfinite(self):
        m=self.model();z=self.z.copy();z[0,0]=np.nan
        with self.assertRaises(ValueError):m.predict(z,np.zeros_like(self.r))
    def test_group_identity(self):
        wrong=self.owner.copy();wrong[0]=100
        with self.assertRaises(ValueError):StructuredKernel(self.z,self.r,self.w,wrong,'pair_mix')
    def test_pair_energy_matching(self):
        m=self.model();a,p=m.pair_components(self.z)
        self.assertAlmostEqual(float(self.w@np.diag(a)),float(self.w@np.diag(p))*m.pair_scale,places=12)
if __name__=='__main__':unittest.main(verbosity=2)
