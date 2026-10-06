import unittest,sys
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE));import run_study as rs
class T(unittest.TestCase):
 def test_constants(self):
  self.assertEqual(rs.PRIOR,.125);self.assertEqual(rs.A_TWO_DOSE_GAIN_MIN,-1.0);self.assertEqual(rs.A_GAIN_MIN,-.9375);self.assertEqual(rs.A_GAIN_MAX,.5)
 def test_cardinality_bound_vector(self):
  card=np.array([2]*8+[3]*16);lower=np.where(card==2,rs.A_TWO_DOSE_GAIN_MIN,rs.A_GAIN_MIN);self.assertEqual(int((lower==-1).sum()),8);self.assertEqual(int((lower==-.9375).sum()),16)
 def test_fit_uses_vector_bound(self):
  T=np.ones((3,24));r=np.tile(np.linspace(-2,1,24),(3,1));n=np.ones(3);lower=np.array([-1.]*8+[-.9375]*16);g,raw=rs.fit_bounded_A_gain(T,r,n,lower);self.assertTrue(np.all(g[:8]>=-1));self.assertTrue(np.all(g[8:]>=-.9375));self.assertTrue(np.all(g<=.5))
 def test_three_dose_unchanged(self):
  card=np.array([2]*8+[3]*16);lower=np.where(card==2,rs.A_TWO_DOSE_GAIN_MIN,rs.A_GAIN_MIN);self.assertTrue(np.all(lower[8:]==rs.A_GAIN_MIN))
 def test_weighted_median(self):self.assertEqual(rs.weighted_median(np.array([0.,1.,10.]),np.array([1.,8.,1.])),1.0)
if __name__=="__main__":unittest.main()
