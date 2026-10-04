import unittest
import numpy as np

from coverage_methods import CoverageCatalog, validate_plan
from cooptimized_control import fit_plan, predict_plan, raw_from_plan, select_joint, subset_raw


class CooptimizedControlTests(unittest.TestCase):
    def setUp(self):
        self.catalog = CoverageCatalog(
            np.array([f"d{j:02}_{k}" for j in range(24) for k in range(3)]),
            np.array([f"d{j:02}" for j in range(24)]),
            np.repeat(np.arange(24), 3), tuple(["1", "10", "100"] * 24),
        )
        rng = np.random.default_rng(20261004)
        self.x = rng.uniform(0.05, 0.95, (9, 72, 2))
        self.patients = np.array([f"p{i}" for i in range(9)])
        self.folds = np.arange(9) % 3
        self.bounds = np.tile([1.0, 100.0], (24, 1))
        self.y = np.column_stack([
            subset_raw(self.x, [3*j, 3*j+1, 3*j+2], self.catalog, self.bounds[j]).mean(0)
            for j in range(24)
        ])

    def test_frozen_budget_and_determinism(self):
        plan1, scores1 = select_joint(self.x, self.y, self.patients, self.catalog, self.bounds, self.folds)
        plan2, scores2 = select_joint(self.x, self.y, self.patients, self.catalog, self.bounds, self.folds)
        validate_plan(plan1, self.catalog)
        self.assertEqual(plan1, plan2)
        self.assertEqual(scores1, scores2)
        self.assertEqual(len(plan1["selected_native_indices"]), 64)
        self.assertEqual(len(set(plan1["selected_native_indices"])), 64)
        self.assertEqual(plan1["orientation_A_plate_indices"].count(0), 32)
        self.assertEqual(len(plan1["upgraded_target_ids"]), 16)

    def test_fit_predict_shapes_and_own_drug(self):
        plan, _ = select_joint(self.x, self.y, self.patients, self.catalog, self.bounds, self.folds)
        model = fit_plan(self.x, self.y, self.patients, plan)
        prediction = predict_plan(self.x, plan, model)
        self.assertEqual(prediction.shape, (2, 9, 24))
        self.assertTrue(np.isfinite(prediction).all())
        raw = raw_from_plan(self.x, plan)
        changed = self.x.copy()
        native = plan["selected_native_indices"][0]
        target = plan["coordinate_target_indices"][0]
        changed[:, native, :] += 0.1
        delta = raw_from_plan(changed, plan) - raw
        self.assertTrue(np.any(delta[:, :, target] != 0))
        self.assertEqual(np.count_nonzero(delta[:, :, np.arange(24) != target]), 0)

    def test_patient_leakage_rejected(self):
        patients = self.patients.copy()
        patients[1] = patients[0]
        with self.assertRaisesRegex(ValueError, "leakage"):
            select_joint(self.x, self.y, patients, self.catalog, self.bounds, self.folds)

    def test_nonfinite_rejected(self):
        bad = self.x.copy(); bad[0, 0, 0] = np.nan
        with self.assertRaises(ValueError):
            select_joint(bad, self.y, self.patients, self.catalog, self.bounds, self.folds)


if __name__ == "__main__":
    unittest.main(verbosity=2)
