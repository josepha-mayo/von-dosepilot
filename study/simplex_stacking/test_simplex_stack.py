import pathlib
import sys
import unittest

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from simplex_stack import combine_coefficients, fit_simplex, patient_balanced_loss


class SimplexStackTests(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(41)
        self.pred = rng.normal(size=(4, 2, 9, 3))
        self.truth = rng.normal(size=(9, 3))
        self.patients = np.asarray(["a", "a", "b", "c", "c", "d", "e", "e", "f"])

    def test_constraints_and_reported_loss(self):
        weights, loss = fit_simplex(self.pred, self.truth, self.patients)
        self.assertAlmostEqual(float(weights.sum()), 1.0, places=12)
        self.assertGreaterEqual(float(weights.min()), -1e-12)
        combined = np.tensordot(weights, self.pred, axes=(0, 0))
        self.assertAlmostEqual(loss, patient_balanced_loss(combined, self.truth, self.patients), places=14)

    def test_known_convex_combination(self):
        base = np.zeros((3, 2, 6, 2))
        base[0, :, :, 0] = 1.0
        base[1, :, :, 1] = 1.0
        base[2] = -2.0
        truth = np.tile(np.asarray([0.25, 0.75]), (6, 1))
        weights, loss = fit_simplex(base, truth, np.asarray(list("aabbcc")))
        self.assertTrue(np.allclose(weights, [0.25, 0.75, 0.0], atol=1e-10))
        self.assertLess(loss, 1e-20)

    def test_patient_row_duplication_with_split_mass(self):
        weights, loss = fit_simplex(self.pred, self.truth, self.patients)
        duplicate = np.flatnonzero(self.patients == "a")
        pred2 = np.concatenate((self.pred, self.pred[:, :, duplicate]), axis=2)
        truth2 = np.concatenate((self.truth, self.truth[duplicate]), axis=0)
        patients2 = np.concatenate((self.patients, self.patients[duplicate]))
        weights2, loss2 = fit_simplex(pred2, truth2, patients2)
        self.assertTrue(np.allclose(weights, weights2, atol=1e-10))
        self.assertAlmostEqual(loss, loss2, places=13)

    def test_model_permutation_preserves_combined_prediction(self):
        weights, _ = fit_simplex(self.pred, self.truth, self.patients)
        order = np.asarray([2, 0, 3, 1])
        permuted, _ = fit_simplex(self.pred[order], self.truth, self.patients)
        first = np.tensordot(weights, self.pred, axes=(0, 0))
        second = np.tensordot(permuted, self.pred[order], axes=(0, 0))
        self.assertTrue(np.allclose(first, second, atol=1e-10))

    def test_identical_candidates_preserve_prediction(self):
        pred = np.concatenate((self.pred[:3], self.pred[:1]), axis=0)
        weights, _ = fit_simplex(pred, self.truth, self.patients)
        combined = np.tensordot(weights, pred, axes=(0, 0))
        reduced, _ = fit_simplex(self.pred[:3], self.truth, self.patients)
        expected = np.tensordot(reduced, self.pred[:3], axes=(0, 0))
        self.assertTrue(np.allclose(combined, expected, atol=1e-9))

    def test_combined_coefficients(self):
        coef = np.arange(24, dtype=float).reshape(4, 3, 2)
        weights = np.asarray([0.1, 0.2, 0.3, 0.4])
        self.assertTrue(np.array_equal(combine_coefficients(coef, weights), np.tensordot(weights, coef, axes=(0, 0))))

    def test_malformed_inputs_rejected(self):
        bad = self.pred.copy()
        bad[0, 0, 0, 0] = np.nan
        with self.assertRaises(ValueError):
            fit_simplex(bad, self.truth, self.patients)
        with self.assertRaises(ValueError):
            fit_simplex(self.pred[:, :1], self.truth, self.patients)
        with self.assertRaises(ValueError):
            fit_simplex(self.pred, self.truth, np.asarray(["a"] * 9))


if __name__ == "__main__":
    unittest.main()
