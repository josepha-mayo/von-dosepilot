import sys,unittest
from pathlib import Path
import numpy as np

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import run_study as r

class OrientationResidualTests(unittest.TestCase):
    def test_parent_option_grid_is_frozen(self):
        self.assertEqual(len(r.parent.OPTIONS),10)
        self.assertEqual(r.parent.OPTIONS[0],("identity",0.0))

    def test_orientation_argmins_can_differ(self):
        scores=np.array([[3.,1.,2.],[1.,3.,2.]])
        np.testing.assert_array_equal(np.argmin(scores,axis=1),[1,0])

    def test_orientation_assembly_uses_two_global_options(self):
        pred=np.arange(3*2*4*5,dtype=float).reshape(3,2,4,5)
        chosen=np.array([2,1])
        a=pred[int(chosen[0]),0]
        b=pred[int(chosen[1]),1]
        np.testing.assert_array_equal(a,pred[2,0])
        np.testing.assert_array_equal(b,pred[1,1])

if __name__=="__main__":
    unittest.main(verbosity=2)
