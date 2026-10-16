"""Tests for `core/nn`, the placeholder home for model code.

Nothing lives there yet, so these pin the package's contract: it imports, it
documents itself, and whatever `__all__` it grows later has to be real.
"""

import unittest

import core.nn


class TestNnPackage(unittest.TestCase):
    def test_imports(self):
        self.assertIsNotNone(core.nn)

    def test_documents_itself(self):
        self.assertTrue(core.nn.__doc__.strip(), "core.nn needs a module docstring")

    def test_public_api_resolves(self):
        for name in getattr(core.nn, "__all__", []):
            with self.subTest(name=name):
                self.assertTrue(
                    hasattr(core.nn, name),
                    f"core.nn.__all__ lists {name} but core.nn has no such attribute",
                )

    def test_reply_rules_stay_in_core_rule(self):
        self.assertFalse(hasattr(core.nn, "respond"), "rule replies belong to core.rule")


if __name__ == "__main__":
    unittest.main()
