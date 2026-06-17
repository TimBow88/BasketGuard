from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "shared" / "src"))

from basketguard_shared import (  # noqa: E402
    PostcodeConsistencyError,
    assert_consistent_postcode,
    is_uk_postcode,
    normalise_postcode_context,
)


class NormaliseTests(unittest.TestCase):
    def test_formats_real_postcode(self) -> None:
        self.assertEqual(normalise_postcode_context("ec1a1bb"), "EC1A 1BB")
        self.assertEqual(normalise_postcode_context("  EC1A   1BB "), "EC1A 1BB")
        self.assertEqual(normalise_postcode_context("m11ae"), "M1 1AE")

    def test_preserves_descriptive_label(self) -> None:
        self.assertEqual(
            normalise_postcode_context("  MVP   default region "),
            "MVP default region",
        )

    def test_blank_and_none_become_none(self) -> None:
        self.assertIsNone(normalise_postcode_context(None))
        self.assertIsNone(normalise_postcode_context("   "))

    def test_is_uk_postcode(self) -> None:
        self.assertTrue(is_uk_postcode("EC1A 1BB"))
        self.assertFalse(is_uk_postcode("MVP default region"))


class ConsistencyTests(unittest.TestCase):
    def test_single_context_returned(self) -> None:
        self.assertEqual(
            assert_consistent_postcode(["EC1A 1BB", "ec1a1bb", None]),
            "EC1A 1BB",
        )

    def test_all_none_returns_none(self) -> None:
        self.assertIsNone(assert_consistent_postcode([None, None]))

    def test_mixed_contexts_raise(self) -> None:
        with self.assertRaises(PostcodeConsistencyError):
            assert_consistent_postcode(["EC1A 1BB", "M1 1AE"])


if __name__ == "__main__":
    unittest.main()
