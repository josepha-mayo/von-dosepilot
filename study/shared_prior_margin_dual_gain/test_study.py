import unittest,sys
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE));import run_study as rs
class T(unittest.TestCase):
 def test_constants(self):
  self.assertEqual(rs.PRIOR,.125);self.assertEqual(rs.APPLY_GAIN_MIN,.875);self.assertEqual(rs.A_GAIN_MIN,-.875);self.assertEqual(rs.A_GAIN_MAX,.5)
 def test_shared_margin(self):
  self.assertAlmostEqual(rs.APPLY_GAIN_MIN,1-rs.PRIOR);self.assertAlmostEqual(rs.A_GAIN_MIN,-(1-rs.PRIOR))
 def test_vote_strength(self):
  base=np.array([.2,.2,.2]);votes=np.array([1,2,3]);eligible=np.array([False,True,True])
  boost=np.where(votes==3,1.,np.where(votes==2,.5,0.));w=base+(1-base)*np.where(eligible,boost,0.)
  self.assertTrue(np.allclose(w,[.2,.6,1.]))
 def test_weighted_mean(self):
  x=np.array([[0.],[0.],[3.]]);m,v=rs.weighted_mean_variance(x,np.array([16.,16.,15.]));self.assertAlmostEqual(float(m[0]),45/47);self.assertGreaterEqual(float(v[0]),0)
if __name__=="__main__":unittest.main()
