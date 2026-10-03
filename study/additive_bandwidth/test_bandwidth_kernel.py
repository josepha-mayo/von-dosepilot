import unittest
import numpy as np
from additive_kernel import AdditiveKernel
from bandwidth_kernel import BandwidthAdditive

class Tests(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(10031400)
        self.z = rng.normal(size=(30, 64))
        self.residual = rng.normal(size=(30, 24))
        self.weights = np.ones(30) / 30
        self.owner = np.repeat(np.arange(24), [3] * 16 + [2] * 8)

    def test_factor_one_matches_incumbent_kernel(self):
        incumbent = AdditiveKernel(self.z, self.residual, self.weights, self.owner)
        candidate = BandwidthAdditive(
            self.z, self.residual, self.weights, self.owner, 1.0
        )
        np.testing.assert_allclose(
            incumbent.raw_cross(self.z),
            candidate.raw_cross(self.z),
            atol=1e-14,
            rtol=0,
        )

    def test_candidate_is_psd(self):
        BandwidthAdditive(self.z, self.residual, self.weights, self.owner, .7)

    def test_row_permutation_prediction_invariance(self):
        q = np.random.default_rng(2).normal(size=(4, 64))
        order = np.random.default_rng(3).permutation(30)
        a = BandwidthAdditive(self.z, self.residual, self.weights, self.owner, .7)
        b = BandwidthAdditive(
            self.z[order], self.residual[order], self.weights[order], self.owner, .7
        )
        ca = a.coefficients(1.0, .1)[0]
        cb = b.coefficients(1.0, .1)[0]
        np.testing.assert_allclose(
            a.centered_cross(q) @ ca,
            b.centered_cross(q) @ cb,
            atol=1e-12,
            rtol=0,
        )

    def test_invalid_factor(self):
        for factor in (0.0, -1.0, float("nan")):
            with self.subTest(factor=factor), self.assertRaises(ValueError):
                BandwidthAdditive(
                    self.z, self.residual, self.weights, self.owner, factor
                )

if __name__ == "__main__":
    unittest.main(verbosity=2)
