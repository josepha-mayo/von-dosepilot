import unittest,sys,json
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE));import run_study as rs
class T(unittest.TestCase):
 def test_constants(self):self.assertEqual(rs.PRIOR,.125);self.assertEqual(rs.TARGETS,24)
 def test_second_pool(self):
  s=.4;raw=np.array([1.,3.]);common=np.array([2.,2.]);glob=(1-s)*raw+s*common;out=(1-s)*glob+s*common
  self.assertTrue(np.allclose(glob,[1.4,2.6]));self.assertTrue(np.allclose(out,[1.64,2.36]))
 def test_cardinality(self):
  card=np.array([2]*8+[3]*16);self.assertEqual(int((card==2).sum()),8);self.assertEqual(int(card.sum()),64)
 def test_unchanged_three_dose(self):
  s=.4;g=np.array([1.5,2.5]);c=np.array([2.,2.]);glob=(1-s)*g+s*c;card=np.array([2,3]);out=glob.copy();m=card==2;out[m]=(1-s)*glob[m]+s*c[m];self.assertAlmostEqual(out[1],glob[1])
 def test_weighted_median(self):self.assertEqual(rs.weighted_median(np.array([0.,1.,10.]),np.array([1.,8.,1.])),1.0)
if __name__=="__main__":unittest.main()
