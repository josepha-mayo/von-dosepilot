import sys,unittest
from pathlib import Path
from types import SimpleNamespace
import numpy as np
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import run_study as r

class CurveTests(unittest.TestCase):
    def fixture(self):
        ids=np.array([f"q{i}" for i in range(72)])
        targets=np.array([f"d{i:02d}" for i in range(24)])
        own=np.repeat(np.arange(24),3)
        catalog=SimpleNamespace(native_ids=ids,target_ids=targets,native_target_indices=own)
        choices=[]
        for t in range(24):
            choices.append({
              "target_index":t,"target_id":str(targets[t]),
              "best2":[3*t,3*t+1],"best3":[3*t,3*t+1,3*t+2],
              "upgrade_gain":float(24-t)
            })
        selected=[]; owner=[]; plates=[]
        for t in range(24):
            subset=choices[t]["best3" if t<16 else "best2"]
            start=(t%2) if t<16 else 0
            selected.extend(subset); owner.extend([t]*len(subset))
            plates.extend([(start+i)%2 for i in range(len(subset))])
        full={
          "choices":choices,
          "selected_native_indices":selected,
          "selected_native_ids":[str(ids[q]) for q in selected],
          "coordinate_target_indices":owner,
          "orientation_A_plate_indices":plates,
          "orientation_B_plate_indices":[1-p for p in plates]
        }
        return catalog,full
    def test_all_budget_sizes_and_balance(self):
        catalog,full=self.fixture()
        for budget,k in zip(r.BUDGETS,r.UPGRADES):
            with self.subTest(budget=budget):
                plan=r.derive_budget(full,catalog,k)
                self.assertEqual(len(plan["selected_native_indices"]),budget)
                self.assertEqual(sum(np.array(plan["orientation_A_plate_indices"])==0),budget//2)

    def test_endpoints_are_all_two_or_all_three(self):
        catalog,full=self.fixture()
        p48=r.derive_budget(full,catalog,0)
        p72=r.derive_budget(full,catalog,24)
        self.assertTrue(np.all(np.bincount(p48["coordinate_target_indices"],minlength=24)==2))
        self.assertTrue(np.all(np.bincount(p72["coordinate_target_indices"],minlength=24)==3))

    def test_64_matches_original_plan(self):
        catalog,full=self.fixture()
        p64=r.derive_budget(full,catalog,16)
        self.assertEqual(p64["selected_native_indices"],full["selected_native_indices"])
        self.assertEqual(p64["orientation_A_plate_indices"],full["orientation_A_plate_indices"])

if __name__=="__main__":
    unittest.main(verbosity=2)
