import pathlib
import unittest


HERE = pathlib.Path(__file__).resolve().parent


class StudyContractTests(unittest.TestCase):
    def test_protocol_forbids_target_and_orientation_specific_weights(self):
        text = (HERE / "PROTOCOL.md").read_text()
        self.assertIn("weights are global", text)
        self.assertIn("does not average A/B predictions", text)
        self.assertIn("all 5/5 outer-fold means favorable", text)

    def test_runner_has_no_protected_or_external_input_argument(self):
        source = (HERE / "run_study.py").read_text()
        self.assertNotIn("lib2", source.lower())
        self.assertNotIn("protected22", source.lower())
        self.assertIn('predictions["simplex_stack"][orientation_index, test]', source)
        self.assertIn("created_before_r18_access", source)

    def test_fixed_option_menu(self):
        source = (HERE / "run_study.py").read_text()
        self.assertIn("for fraction in (0.1, 0.3, 0.6)", source)
        self.assertIn("for ridge in (0.1, 1.0, 10.0)", source)
        self.assertIn("fit_simplex", source)


if __name__ == "__main__":
    unittest.main()
