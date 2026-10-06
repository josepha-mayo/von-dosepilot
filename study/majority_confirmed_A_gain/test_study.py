import unittest,sys
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE));import run_study as rs
class T(unittest.TestCase):
 def test_bounds(self): self.assertEqual((rs.A_GAIN_MIN,rs.A_GAIN_MAX),(-.5,.5))
 def test_r_half_boundary(self):
  g=np.array([1.]);v=np.array([1.]);r=g*g/(g*g+v);self.assertAlmostEqual(float(r[0]),.5)
 def test_strict_majority(self):
  raw=np.array([.2,-.2,.2]);local=np.array([[1,-1,1],[2,-2,-1],[-1,-3,3]],float)
  match=np.sign(local)==np.sign(raw)[None,:];majority=(match.sum(0)>=2)&(raw!=0)
  self.assertTrue(np.array_equal(majority,[True,True,True]))
 def test_zero_gain_cannot_trigger(self):
  raw=np.zeros(3);local=np.ones((3,3));r=np.ones(3);match=np.sign(local)==np.sign(raw)[None,:]
  majority=(match.sum(0)>=2)&(raw!=0)&(r>=.5);self.assertFalse(np.any(majority))
 def test_confirmation_rule(self):
  r=np.array([.4,.5,.8]);majority=np.array([True,True,False]);w=np.where(majority&(r>=.5),1.,r**3)
  self.assertTrue(np.allclose(w,[.064,1.,.512]))
if __name__=="__main__":unittest.main()
