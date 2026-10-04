import pathlib
import sys
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from run_study import gate


def comparison(gain=0.01, wins=35, folds=5, p90=True, orientations=(True, True)):
    return {
        "relative_gain": gain,
        "patient_wins": wins,
        "patient_losses": 59 - wins,
        "patient_ties": 0,
        "fold_wins": folds,
        "p90_nonworse": p90,
        "orientation_below_reference_expected_mse": list(orientations),
    }


class GateTests(unittest.TestCase):
    def passing(self):
        return {
            "bandwidth07": comparison(),
            "r13": comparison(0.06, 45, 5),
            "r18": comparison(0.051, 41, 4),
        }

    def test_complete_gate_passes(self):
        immediate, historical, passed = gate(self.passing(), False)
        self.assertTrue(all(immediate.values()))
        self.assertTrue(all(all(value.values()) for value in historical.values()))
        self.assertTrue(passed)

    def test_each_immediate_clause_is_required(self):
        variants = [
            ("relative_gain", 0.0),
            ("patient_wins", 29),
            ("fold_wins", 4),
            ("p90_nonworse", False),
        ]
        for key, value in variants:
            values = self.passing()
            values["bandwidth07"][key] = value
            self.assertFalse(gate(values, False)[2], key)
        self.assertFalse(gate(self.passing(), True)[2], "equivalence")

    def test_each_historical_clause_is_required(self):
        variants = [
            ("relative_gain", 0.049),
            ("patient_wins", 39),
            ("fold_wins", 3),
            ("p90_nonworse", False),
            ("orientation_below_reference_expected_mse", [True, False]),
        ]
        for reference in ("r13", "r18"):
            for key, value in variants:
                values = self.passing()
                values[reference][key] = value
                self.assertFalse(gate(values, False)[2], reference + ":" + key)


if __name__ == "__main__":
    unittest.main(verbosity=2)
