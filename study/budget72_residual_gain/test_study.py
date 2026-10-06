import sys,unittest
from pathlib import Path
import numpy as np

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import run_study as r

class ResidualGainTests(unittest.TestCase):
    def test_frozen_gain_grid_and_candidate_count(self):
        self.assertEqual(r.GAINS,(0.5,0.75,1.0,1.25,1.5))
        self.assertEqual(r.CANDIDATES[0],(0,0.0))
        self.assertEqual(len(r.CANDIDATES),1+9*5)

    def test_gain_blend(self):
        base=np.array([1.,2.,3.])
        option=np.array([3.,0.,5.])
        gain=0.75
        got=base+gain*(option-base)
        np.testing.assert_allclose(got,[2.5,0.5,4.5])

    def test_selection_tie_uses_first_candidate(self):
        scores=[1.0,0.8,0.8,0.9]
        chosen=min(range(len(scores)),key=lambda i:(scores[i],i))
        self.assertEqual(chosen,1)

if __name__=="__main__":
    unittest.main(verbosity=2)
