import sys
import unittest

from release_preflight import CHECKS as HISTORICAL_CHECKS
from release_preflight_current import CHECKS, unittest_count


class CurrentReleasePreflightTests(unittest.TestCase):
    def test_extends_historical_checks_without_mutation(self):
        self.assertEqual(CHECKS[: len(HISTORICAL_CHECKS)], HISTORICAL_CHECKS)
        names = [item[0] for item in CHECKS]
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(names[-2:], ["target_definition_tests", "target_definitions"])

    def test_new_checks_are_response_free_python_commands(self):
        for _, command, _ in CHECKS[-2:]:
            self.assertEqual(command[0], sys.executable)
            joined = " ".join(command).lower()
            self.assertNotIn("protected22", joined)
            self.assertNotIn("private", joined)
            self.assertNotIn("workbook", joined)

    def test_count_parser_is_preserved(self):
        self.assertEqual(unittest_count("Ran 7 tests in 0.1s\nOK\n"), 7)


if __name__ == "__main__":
    unittest.main(verbosity=2)

