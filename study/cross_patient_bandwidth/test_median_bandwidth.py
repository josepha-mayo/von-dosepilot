import inspect
import pathlib
import sys
import unittest

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
STUDY = HERE.parent
sys.path[:0] = [str(HERE), str(STUDY / "hybrid_residual")]

from bandwidth_additive import BandwidthAdditive
from median_bandwidth import (
    ANCHOR,
    REFERENCE_MEDIAN,
    CrossPatientMedianBandwidth,
    estimate_group_bandwidths,
    weighted_median,
)


def owner():
    return np.asarray(sum(([j] * (2 if j < 8 else 3) for j in range(24)), []), dtype=int)


def anchor_fixture():
    own = owner()
    z = np.zeros((2, 64), dtype=float)
    for j in range(24):
        group = np.flatnonzero(own == j)
        z[1, group] = np.sqrt(REFERENCE_MEDIAN[len(group)] / len(group))
    return z, np.asarray([0.5, 0.5]), own, np.asarray(["P1", "P2"])


class MedianBandwidthTests(unittest.TestCase):
    def test_weighted_median_is_deterministic_at_half(self):
        self.assertEqual(weighted_median([2, 1, 3], [0.25, 0.5, 0.25]), 1.0)
        self.assertEqual(weighted_median([1, 2], [0.5, 0.5], [8, 4], [2, 1]), 1.0)

    def test_estimator_has_no_response_argument(self):
        self.assertEqual(
            list(inspect.signature(estimate_group_bandwidths).parameters),
            ["z", "weights", "owner", "patient_ids"],
        )

    def test_theoretical_anchor_equals_bandwidth07_kernel(self):
        z, weights, own, patients = anchor_fixture()
        residual = np.arange(48, dtype=float).reshape(2, 24) / 100.0
        medians, bandwidths = estimate_group_bandwidths(z, weights, own, patients)
        np.testing.assert_allclose(
            medians, [REFERENCE_MEDIAN[len(np.flatnonzero(own == j))] for j in range(24)],
            rtol=0.0,
            atol=1e-14,
        )
        np.testing.assert_allclose(bandwidths, ANCHOR, rtol=0.0, atol=1e-14)
        candidate = CrossPatientMedianBandwidth(z, residual, weights, own, patients)
        incumbent = BandwidthAdditive(z, residual, weights, own, ANCHOR)
        query = np.vstack((z, (z[0] + z[1]) / 2.0))
        np.testing.assert_allclose(candidate.raw_cross(query), incumbent.raw_cross(query), atol=1e-12)
        np.testing.assert_allclose(candidate.centered_cross(query), incumbent.centered_cross(query), atol=1e-12)

    def test_same_patient_pairs_are_excluded(self):
        z, _, own, _ = anchor_fixture()
        z = np.vstack((z[0], z[0] + 100.0, z[1]))
        weights = np.asarray([0.25, 0.25, 0.5])
        patients = np.asarray(["P1", "P1", "P2"])
        medians, _ = estimate_group_bandwidths(z, weights, own, patients)
        # If the enormous within-P1 distance were included, this would not
        # equal either cross-patient distance for each group.
        for j in range(24):
            group = np.flatnonzero(own == j)
            choices = [np.sum((z[0, group] - z[2, group]) ** 2),
                       np.sum((z[1, group] - z[2, group]) ** 2)]
            self.assertIn(medians[j], choices)

    def test_row_permutation_invariance(self):
        rng = np.random.default_rng(9)
        own = owner()
        z = rng.normal(size=(8, 64))
        patients = np.asarray(["A", "A", "B", "B", "C", "C", "D", "D"])
        weights = np.full(8, 1 / 8)
        expected = estimate_group_bandwidths(z, weights, own, patients)
        order = np.asarray([6, 2, 5, 0, 7, 1, 4, 3])
        actual = estimate_group_bandwidths(z[order], weights[order], own, patients[order])
        np.testing.assert_allclose(actual[0], expected[0], rtol=0.0, atol=1e-14)
        np.testing.assert_allclose(actual[1], expected[1], rtol=0.0, atol=1e-14)

    def test_patient_relabel_and_ab_block_swap_invariance(self):
        rng = np.random.default_rng(11)
        own = owner()
        first = rng.normal(size=(5, 64))
        second = rng.normal(size=(5, 64))
        z = np.vstack((first, second))
        patients = np.tile(np.asarray(["A", "B", "C", "D", "E"]), 2)
        weights = np.full(10, 0.1)
        expected = estimate_group_bandwidths(z, weights, own, patients)
        swapped = np.r_[np.arange(5, 10), np.arange(5)]
        relabelled = np.asarray([{"A": "Q", "B": "R", "C": "S", "D": "T", "E": "U"}[p]
                                 for p in patients[swapped]])
        actual = estimate_group_bandwidths(z[swapped], weights[swapped], own, relabelled)
        np.testing.assert_allclose(actual[0], expected[0], rtol=0.0, atol=1e-14)
        np.testing.assert_allclose(actual[1], expected[1], rtol=0.0, atol=1e-14)

    def test_patient_row_duplication_with_split_weight(self):
        rng = np.random.default_rng(13)
        own = owner()
        z = rng.normal(size=(4, 64))
        patients = np.asarray(["A", "B", "C", "D"])
        weights = np.full(4, 0.25)
        expected = estimate_group_bandwidths(z, weights, own, patients)
        duplicated_z = np.vstack((z[0], z[0], z[1:]))
        duplicated_patients = np.asarray(["A", "A", "B", "C", "D"])
        duplicated_weights = np.asarray([0.125, 0.125, 0.25, 0.25, 0.25])
        actual = estimate_group_bandwidths(
            duplicated_z, duplicated_weights, own, duplicated_patients
        )
        np.testing.assert_allclose(actual[0], expected[0], rtol=0.0, atol=1e-14)
        np.testing.assert_allclose(actual[1], expected[1], rtol=0.0, atol=1e-14)

    def test_query_batching_and_positive_semidefinite(self):
        rng = np.random.default_rng(21)
        own = owner()
        z = rng.normal(size=(10, 64))
        weights = np.full(10, 0.1)
        patients = np.asarray([f"P{i // 2}" for i in range(10)])
        residual = rng.normal(size=(10, 24))
        model = CrossPatientMedianBandwidth(z, residual, weights, own, patients)
        full = model.raw_cross(z)
        np.testing.assert_allclose(np.vstack([model.raw_cross(z[:4]), model.raw_cross(z[4:])]), full)
        eigenvalues = np.linalg.eigvalsh((full + full.T) / 2)
        self.assertGreaterEqual(float(eigenvalues.min()), -1e-10)
        np.testing.assert_allclose(model.w @ model.centered_cross(z), 0.0, atol=1e-13)

    def test_bandwidth_geometry_is_outcome_independent(self):
        rng = np.random.default_rng(23)
        own = owner()
        z = rng.normal(size=(8, 64))
        weights = np.full(8, 1 / 8)
        patients = np.asarray([f"P{i // 2}" for i in range(8)])
        first = CrossPatientMedianBandwidth(z, np.zeros((8, 24)), weights, own, patients)
        second = CrossPatientMedianBandwidth(z, rng.normal(size=(8, 24)) * 1000, weights, own, patients)
        np.testing.assert_array_equal(first.group_medians, second.group_medians)
        np.testing.assert_array_equal(first.group_bandwidths, second.group_bandwidths)
        np.testing.assert_array_equal(first.raw_cross(z), second.raw_cross(z))
        np.testing.assert_array_equal(first.train_mean, second.train_mean)
        self.assertEqual(first.grand, second.grand)

    def test_serialization_is_unambiguous_vector_bandwidth(self):
        z, weights, own, patients = anchor_fixture()
        model = CrossPatientMedianBandwidth(z, np.zeros((2, 24)), weights, own, patients)
        arrays = model.arrays(np.zeros((2, 24)))
        self.assertEqual(arrays["kernel_group_bandwidth_multipliers"].shape, (24,))
        self.assertEqual(arrays["kernel_group_distance_medians"].shape, (24,))
        self.assertEqual(arrays["kernel_fitting_patient_ids"].shape, (2,))
        self.assertNotIn("kernel_bandwidth_multiplier", arrays)

    def test_group_label_permutation(self):
        rng = np.random.default_rng(31)
        own = owner()
        z = rng.normal(size=(8, 64))
        weights = np.full(8, 1 / 8)
        patients = np.asarray([f"P{i // 2}" for i in range(8)])
        medians, bandwidths = estimate_group_bandwidths(z, weights, own, patients)
        mapping = np.arange(24)[::-1]
        relabelled = mapping[own]
        medians2, bandwidths2 = estimate_group_bandwidths(z, weights, relabelled, patients)
        np.testing.assert_allclose(medians2[mapping], medians)
        np.testing.assert_allclose(bandwidths2[mapping], bandwidths)

    def test_malformed_and_degenerate_inputs_fail(self):
        z, weights, own, patients = anchor_fixture()
        cases = [
            (np.full_like(z, np.nan), weights, own, patients),
            (z, np.asarray([0.0, 1.0]), own, patients),
            (z, weights, own[:-1], patients),
            (z, weights, own, np.asarray(["P", "P"])),
            (np.zeros_like(z), weights, own, patients),
        ]
        for values in cases:
            with self.subTest(case=values[0].shape):
                with self.assertRaises(ValueError):
                    estimate_group_bandwidths(*values)


if __name__ == "__main__":
    unittest.main(verbosity=2)
