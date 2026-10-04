import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from isotonic_features import decreasing_pava, project_paid


def fixture():
    owners = np.repeat(np.arange(24), [3] * 16 + [2] * 8)
    doses = []
    for owner in range(24):
        doses.extend(([100, 1, 10] if owner < 16 else [10, 1]))
    return {"coordinate_target_indices": owners.tolist(),
            "selected_concentrations_nM": list(map(str, doses))}


class IsotonicFeatureTests(unittest.TestCase):
    def test_known_pooling(self):
        np.testing.assert_allclose(decreasing_pava([0.9, 1.1, 0.4]), [1.0, 1.0, 0.4])

    def test_already_decreasing_is_unchanged(self):
        values = np.array([1.0, 0.8, 0.1])
        np.testing.assert_array_equal(decreasing_pava(values), values)

    def test_full_violation_pools_to_mean(self):
        np.testing.assert_allclose(decreasing_pava([0.2, 0.5, 0.8]), [0.5, 0.5, 0.5])

    def test_projection_is_idempotent_and_monotone(self):
        rng = np.random.default_rng(4)
        paid = rng.normal(size=(7, 64))
        plan = fixture()
        projected = project_paid(paid, plan)
        np.testing.assert_allclose(project_paid(projected, plan), projected)
        owners = np.asarray(plan["coordinate_target_indices"])
        doses = np.asarray(plan["selected_concentrations_nM"], float)
        for owner in np.unique(owners):
            cols = np.flatnonzero(owners == owner)
            cols = cols[np.argsort(doses[cols])]
            self.assertTrue(np.all(np.diff(projected[:, cols], axis=1) <= 1e-14))

    def test_row_permutation_and_drug_isolation(self):
        rng = np.random.default_rng(5)
        paid = rng.normal(size=(4, 64)); plan = fixture()
        order = np.array([2, 0, 3, 1])
        np.testing.assert_allclose(project_paid(paid[order], plan), project_paid(paid, plan)[order])
        changed = paid.copy(); changed[:, :3] += 100
        np.testing.assert_allclose(project_paid(changed, plan)[:, 3:], project_paid(paid, plan)[:, 3:])

    def test_no_hidden_clipping(self):
        paid = np.tile(np.linspace(2.0, -1.0, 64), (2, 1)); plan = fixture()
        out = project_paid(paid, plan)
        self.assertGreater(out.max(), 1.0); self.assertLess(out.min(), 0.0)

    def test_invalid_inputs_fail(self):
        plan = fixture()
        for paid in (np.ones((2, 63)), np.full((2, 64), np.nan)):
            with self.assertRaises(ValueError): project_paid(paid, plan)
        bad = fixture(); bad["selected_concentrations_nM"][0] = "0"
        with self.assertRaises(ValueError): project_paid(np.ones((2, 64)), bad)


if __name__ == "__main__": unittest.main()
