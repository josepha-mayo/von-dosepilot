import sys,unittest
from pathlib import Path
import numpy as np
PARENT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(PARENT/'hybrid_residual'),str(PARENT/'source')]
from additive_kernel import AdditiveKernel
from compiled_kernel import CompiledCorrection

class Tests(unittest.TestCase):
    def setUp(self):
        r=np.random.default_rng(1519);self.z=r.normal(size=(35,64));self.r=r.normal(size=(35,24));self.w=r.uniform(.1,1,35);self.w/=self.w.sum()
        self.owner=np.repeat(np.arange(24),[3]*16+[2]*8)
        self.k=AdditiveKernel(self.z,self.r,self.w,self.owner);self.coef=self.k.coefficients(1,.1)[0]
        self.a=self.k.arrays(self.coef);self.c=CompiledCorrection(self.a,self.owner)
    def test_reference_matrix_calculation(self):
        q=np.random.default_rng(11).normal(size=(7,64))
        np.testing.assert_allclose(self.c.predict(q),self.k.predict(q,self.coef),atol=2e-13,rtol=0)
    def test_nonzero_dual_mass(self):
        a=self.k.arrays(np.ones((35,24))*.003);c=CompiledCorrection(a,self.owner)
        q=np.random.default_rng(13).normal(size=(5,64))
        np.testing.assert_allclose(c.predict(q),self.k.predict(q,a['dual_coefficients']),atol=1e-12,rtol=0)
    def test_training_centering(self):
        np.testing.assert_allclose(self.w@self.c.predict(self.z),np.zeros(24),atol=1e-13,rtol=0)
    def test_single_vs_batch(self):
        batch=self.c.predict(self.z[:8]);rows=np.concatenate([self.c.predict(v[None,:]) for v in self.z[:8]])
        np.testing.assert_allclose(batch,rows,atol=2e-13,rtol=0)
    def test_finite_extrapolation(self):
        q=np.array([np.full(64,-30.),np.full(64,30.)])
        np.testing.assert_allclose(self.c.predict(q),self.k.predict(q,self.coef),atol=1e-11,rtol=0)
    def test_no_array_mutation(self):
        before={k:np.array(v,copy=True) for k,v in self.a.items()};self.c.predict(self.z)
        for k,v in before.items():np.testing.assert_array_equal(self.a[k],v)
    def test_missing_values_rejected(self):
        q=self.z[:1].copy();q[0,0]=np.nan
        with self.assertRaises(ValueError):self.c.predict(q)
    def test_unknown_geometry_rejected(self):
        with self.assertRaises(ValueError):CompiledCorrection(self.a,np.arange(64))
    def test_zero_dual(self):
        c=CompiledCorrection(self.k.arrays(np.zeros_like(self.coef)),self.owner)
        np.testing.assert_array_equal(c.predict(self.z),np.zeros_like(self.r))
if __name__=='__main__':unittest.main(verbosity=2)
