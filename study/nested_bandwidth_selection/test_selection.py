import unittest
import numpy as np

from run_study import choose_pair


class SelectionTests(unittest.TestCase):
    def test_global_minimum(self):
        scores = np.arange(30, dtype=float).reshape(3, 10)
        scores[2, 7] = -1
        self.assertEqual(choose_pair(scores), (2, 7))

    def test_tie_prefers_multiplier_then_option_order(self):
        scores = np.ones((3, 10))
        self.assertEqual(choose_pair(scores), (0, 0))
        scores[0, 0] = 2
        self.assertEqual(choose_pair(scores), (0, 1))

    def test_nonfinite_not_silently_selected(self):
        scores = np.ones((3, 10))
        scores[0, 0] = np.nan
        with self.assertRaises(ValueError):
            choose_pair(scores)


if __name__ == "__main__":
    unittest.main()
