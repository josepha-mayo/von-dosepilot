import sys, unittest
from pathlib import Path
import numpy as np
from types import SimpleNamespace

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import run_study as r

class Budget48Tests(unittest.TestCase):
    def catalog(self):
        ids=np.array([f"q{i}" for i in range(72)])
        own=np.repeat(np.arange(24),3)
        return SimpleNamespace(
          library_id="lib1",native_ids=ids,native_target_indices=own,
          concentrations=tuple(str(i+1) for i in range(72)),
          target_ids=np.array([f"d{i}" for i in range(24)]))
    def plan48(self):
        c=self.catalog()
        sel=[3*t+j for t in range(24) for j in (0,1)]
        return {
          "selected_native_indices":sel,
          "selected_native_ids":[str(c.native_ids[q]) for q in sel],
          "coordinate_target_indices":np.repeat(np.arange(24),2).tolist(),
          "orientation_A_plate_indices":[0,1]*24,
          "orientation_B_plate_indices":[1,0]*24
        }
    def test_validate48_and_acquire(self):
        c=self.catalog(); p=self.plan48()
        r.validate48(p,c)
        x=np.arange(5*72*2,dtype=float).reshape(5,72,2)
        self.assertEqual(r.acquire48(x,p,"A").shape,(5,48))
        self.assertFalse(np.array_equal(r.acquire48(x,p,"A"),r.acquire48(x,p,"B")))
    def test_duplicate_rejected(self):
        c=self.catalog(); p=self.plan48()
        p["selected_native_indices"][1]=p["selected_native_indices"][0]
        with self.assertRaises(ValueError): r.validate48(p,c)
    def test_patient_weighting(self):
        losses=np.array([[1.,3.],[3.,5.],[10.,20.]])
        ids,pt=r.patient_target_losses(losses,np.array(["p1","p1","p2"]))
        self.assertEqual(ids.tolist(),["p1","p2"])
        np.testing.assert_allclose(pt,[[2.,4.],[10.,20.]])

if __name__=="__main__":
    unittest.main(verbosity=2)
