import sys,unittest
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import run_study as r

class SeparateKernelTests(unittest.TestCase):
    def test_option_grid_is_incumbent_grid(self):
        self.assertEqual(len(r.OPTIONS),10)
        self.assertEqual(r.OPTIONS[0],("identity",0.0))
        self.assertEqual(r.OPTIONS[5],(0.3,1.0))

    def test_orientation_metric_equal_patient_weight(self):
        y=np.zeros((3,2))
        pred=np.array([[1.,1.],[3.,3.],[2.,2.]])
        p=np.array(["a","a","b"])
        self.assertAlmostEqual(r.orientation_patient_mse(y,pred,p),(5+4)/2)

    def test_separate_kernel_shapes(self):
        rng=np.random.default_rng(0)
        z=rng.normal(size=(20,72));res=rng.normal(size=(20,24))
        w=np.full(20,1/20);owner=np.repeat(np.arange(24),3)
        m=r.parent.BandwidthAdditive72(z,res,w,owner,0.7)
        coef=m.coefficients(1.0,0.3)[0]
        self.assertEqual(coef.shape,(20,24))
        self.assertEqual(m.centered_cross(z[:2]).shape,(2,20))

if __name__=="__main__":
    unittest.main(verbosity=2)
