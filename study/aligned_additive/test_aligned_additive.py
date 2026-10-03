import unittest
import numpy as np
from additive_kernel import AdditiveKernel
from aligned_additive_kernel import AlignedAdditiveKernel


def fixture(seed=4, constant_residual=False):
    rng = np.random.default_rng(seed)
    z = rng.normal(size=(18, 64))
    residual = np.zeros((18, 24)) if constant_residual else rng.normal(size=(18, 24))
    w = rng.uniform(.2, 2, 18); w /= w.sum()
    owner = np.repeat(np.arange(24), [3] * 16 + [2] * 8)
    return z, residual, w, owner


class AlignedAdditiveTests(unittest.TestCase):
    def test_eta_zero_matches_incumbent(self):
        z, r, w, owner = fixture()
        old = AdditiveKernel(z, r, w, owner)
        new = AlignedAdditiveKernel(z, r, w, owner, 0.0)
        q = z[:5] + .1
        np.testing.assert_allclose(new.raw_cross(z), old.raw_cross(z), atol=1e-13, rtol=0)
        np.testing.assert_allclose(new.centered_cross(q), old.centered_cross(q), atol=1e-13, rtol=0)
        self.assertTrue(np.array_equal(new.group_scale, np.ones(24)))

    def test_explicit_center_alignment_and_energy(self):
        z, r, w, owner = fixture()
        model = AlignedAdditiveKernel(z, r, w, owner, 1.0)
        sw = np.sqrt(w); rc = r - w @ r
        ar = sw[:, None] * (rc @ rc.T / 24) * sw[None, :]
        manual_a, manual_e = [], []
        for g in model.gaussian_groups(z):
            c = np.empty_like(g)
            grand = sum(w[i] * w[j] * g[i, j] for i in range(len(w)) for j in range(len(w)))
            for i in range(len(w)):
                for j in range(len(w)):
                    c[i, j] = g[i, j] - sum(g[i, k] * w[k] for k in range(len(w))) - sum(w[k] * g[k, j] for k in range(len(w))) + grand
            a = sw[:, None] * c * sw[None, :]
            manual_a.append(max(0.0, float(np.sum(a * ar) / (np.linalg.norm(a) * np.linalg.norm(ar)))))
            manual_e.append(float(np.trace(a)))
        np.testing.assert_allclose(model.alignments, manual_a, atol=2e-13)
        np.testing.assert_allclose(model.group_energy, manual_e, atol=2e-13)

    def test_energy_normalization(self):
        z, r, w, owner = fixture()
        model = AlignedAdditiveKernel(z, r, w, owner, .5)
        widths = np.array([len(g) for g in model.groups])
        before = np.sum(widths * model.group_energy)
        after = np.sum(widths * model.group_energy * model.group_scale)
        self.assertAlmostEqual(before, after, places=12)

    def test_positive_semidefinite(self):
        z, r, w, owner = fixture()
        for eta in (0.0, .5, 1.0):
            model = AlignedAdditiveKernel(z, r, w, owner, eta)
            eig = np.linalg.eigvalsh((model.raw_cross(z) + model.raw_cross(z).T) / 2)
            self.assertGreaterEqual(float(eig.min()), -1e-10)

    def test_group_label_permutation_invariance(self):
        z, r, w, owner = fixture()
        first = AlignedAdditiveKernel(z, r, w, owner, .5)
        permutation = np.roll(np.arange(24), 7)
        relabel = permutation[owner]
        second = AlignedAdditiveKernel(z, r, w, relabel, .5)
        np.testing.assert_allclose(first.raw_cross(z), second.raw_cross(z), atol=1e-12)

    def test_query_batching(self):
        z, r, w, owner = fixture()
        model = AlignedAdditiveKernel(z, r, w, owner, 1.0)
        q = z[:6] + .17
        together = model.centered_cross(q)
        separate = np.vstack([model.centered_cross(row[None, :]) for row in q])
        np.testing.assert_allclose(together, separate, atol=1e-13)

    def test_constant_residual_falls_back_to_equal_weights(self):
        z, r, w, owner = fixture(constant_residual=True)
        model = AlignedAdditiveKernel(z, r, w, owner, 1.0)
        np.testing.assert_array_equal(model.group_scale, np.ones(24))
        np.testing.assert_array_equal(model.alignments, np.zeros(24))
        self.assertEqual(model.response_gram_norm, 0.0)

    def test_tiny_nonconstant_residual_uses_declared_fallback(self):
        z, r, w, owner = fixture()
        model = AlignedAdditiveKernel(z, r * 1e-20, w, owner, 1.0)
        self.assertLessEqual(model.response_gram_norm, 1e-14)
        np.testing.assert_array_equal(model.group_scale, np.ones(24))

    def test_invalid_inputs(self):
        z, r, w, owner = fixture()
        for eta in (-1, .2, np.nan):
            with self.subTest(eta=eta), self.assertRaises(ValueError):
                AlignedAdditiveKernel(z, r, w, owner, eta)
        z[0, 0] = np.nan
        with self.assertRaises(ValueError):
            AlignedAdditiveKernel(z, r, w, owner, .5)


if __name__ == '__main__':
    unittest.main(verbosity=2)
