import unittest
from release_preflight import CHECKS


class ReleasePreflightTests(unittest.TestCase):
    def test_names_are_unique_and_critical_checks_are_present(self):
        names = [item[0] for item in CHECKS]
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(set(names), {
            "evidence", "audit_tests", "durable_runtime", "acquisition", "structured_kernels",
            "aligned_additive", "ooc_compiler",
        })

    def test_every_check_is_python_and_has_no_private_input_flag(self):
        for _, command, _ in CHECKS:
            self.assertEqual(command[0], __import__("sys").executable)
            joined = " ".join(command).lower()
            self.assertNotIn("protected22", joined)
            self.assertNotIn("private", joined)
            self.assertNotIn("workbook", joined)


if __name__ == "__main__":
    unittest.main(verbosity=2)
