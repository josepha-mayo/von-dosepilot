import unittest,sys
from pathlib import Path
import numpy as np
sys.path[:0]=[str(Path(__file__).parents[1]/'spectral_residual')]
from soft_residual import soft_reduced_ridge
from kernel_spectral import KernelSpectral,kernel
class Tests(unittest.TestCase):
 def setUp(self):
  rng=np.random.default_rng(104330);self.w=rng.uniform(.1,1,40);self.w/=self.w.sum()
  x=rng.normal(size=(40,8));r=rng.normal(size=(40,5));self.x=x-self.w@x;self.r=r-self.w@r
 def test_linear_matches_primal(self):
  m=KernelSpectral(self.x,self.r,self.w,False);g=(self.x.T*self.w)@self.x;c=(self.x.T*self.w)@self.r
  for f in (.1,.3,.6):
   for l in (.1,1.,10.):
    b,_,_=soft_reduced_ridge(g,c,l,f);a,_,_=m.coefficients(l,f)
    np.testing.assert_allclose(m.predict(self.x,a),self.x@b,atol=3e-14,rtol=0)
 def test_kernel_psd(self):self.assertGreater(np.linalg.eigvalsh(kernel(self.x,self.x)).min(),-1e-11)
 def test_weighted_centering(self):
  m=KernelSpectral(self.x,self.r,self.w);c=m.centered_cross(self.x)
  np.testing.assert_allclose(self.w@c,0,atol=1e-14)
 def test_query_order_and_batch_independence(self):
  m=KernelSpectral(self.x,self.r,self.w);a,_,_=m.coefficients(1,.1)
  p=m.predict(self.x[:3],a)
  np.testing.assert_allclose(p[0],m.predict(self.x[:1],a)[0],atol=1e-14)
  np.testing.assert_allclose(p[::-1],m.predict(self.x[2::-1],a),atol=1e-14)
 def test_zero_residual(self):
  m=KernelSpectral(self.x,np.zeros_like(self.r),self.w);a,_,_=m.coefficients(1,.1);np.testing.assert_array_equal(a,np.zeros_like(a))
 def test_shrink_one_zero(self):
  m=KernelSpectral(self.x,self.r,self.w);a,_,_=m.coefficients(1,1);np.testing.assert_array_equal(a,np.zeros_like(a))
 def test_direct_feature_factorization(self):
  m=KernelSpectral(self.x,self.r,self.w);k=m.centered_cross(self.x);v,u=np.linalg.eigh((k+k.T)/2);phi=u*np.sqrt(np.maximum(v,0.))[None,:]
  g=(phi.T*self.w)@phi;c=(phi.T*self.w)@self.r
  b,_,_=soft_reduced_ridge(g,c,.1,.3);a,_,_=m.coefficients(.1,.3)
  np.testing.assert_allclose(phi@b,m.predict(self.x,a),atol=2e-13,rtol=0)
 def test_invalid_weight(self):
  with self.assertRaises(ValueError):KernelSpectral(self.x,self.r,np.ones(40))
 def test_nonfinite_input(self):
  x=self.x.copy();x[0,0]=np.nan
  with self.assertRaises(ValueError):KernelSpectral(x,self.r,self.w)
 def test_no_query_mutation(self):
  m=KernelSpectral(self.x,self.r,self.w);old=self.x.copy();a,_,_=m.coefficients(1,.1);m.predict(self.x,a);np.testing.assert_array_equal(self.x,old)
if __name__=='__main__':unittest.main(verbosity=2)
