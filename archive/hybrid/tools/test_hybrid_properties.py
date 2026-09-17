#!/usr/bin/env python3
"""Focused regression tests for the gold hybrid property repair."""

import os
from pathlib import Path
import shutil
import tempfile
import unittest

from hybrid_properties import (
    CONFLICTS, NativeTools, PROPERTY_FILES, SOURCE_ROOT, repair_contexts, validate,
)


class RepairContextsTest(unittest.TestCase):
    def setUp(self):
        self.system = "# keep comments\n\n" + "".join(
            f"{name} {contexts[0]}\n" for name, contexts in CONFLICTS.items())
        self.vendor = "".join(
            f"{name} {contexts[1]}\n" for name, contexts in CONFLICTS.items())
        self.unrelated = "vendor.camera.aux.packageexcludelist u:object_r:vendor_persist_camera_prop:s0\n"
        self.system += self.unrelated

    def test_removes_both_conflicts_only(self):
        result, removed = repair_contexts(self.system, self.vendor)
        self.assertEqual(result, "# keep comments\n\n" + self.unrelated)
        self.assertEqual(removed, list(CONFLICTS))

    def test_idempotent(self):
        result, _ = repair_contexts(self.system, self.vendor)
        self.assertEqual(repair_contexts(result, self.vendor), (result, []))

    def test_missing_vendor_proof_is_rejected(self):
        with self.assertRaises(ValueError):
            repair_contexts(self.system, "")

    def test_different_vendor_ownership_is_rejected(self):
        with self.assertRaises(ValueError):
            repair_contexts(self.system, self.vendor.replace("vendor_mtk_radio_prop", "other_prop"))

    def test_different_system_ownership_is_rejected(self):
        with self.assertRaises(ValueError):
            repair_contexts(self.system.replace("system_mtk_pco_prop", "other_prop"), self.vendor)

    def test_exact_is_not_treated_as_duplicate_prefix(self):
        with self.assertRaises(ValueError):
            repair_contexts(self.system.replace(":s0\n", ":s0 exact\n"), self.vendor)

    def test_typed_rule_requires_review(self):
        with self.assertRaises(ValueError):
            repair_contexts(self.system.replace(":s0\n", ":s0 prefix string\n"), self.vendor)

    def test_explicit_prefix_is_supported(self):
        result, removed = repair_contexts(self.system, self.vendor.replace(":s0\n", ":s0 prefix\n"))
        self.assertEqual(len(removed), 2)
        self.assertIn(self.unrelated, result)

    def test_duplicate_vendor_proof_is_rejected(self):
        with self.assertRaises(ValueError):
            repair_contexts(self.system, self.vendor * 2)

    def test_duplicate_system_rule_is_rejected(self):
        with self.assertRaises(ValueError):
            repair_contexts(self.system * 2, self.vendor)

    def test_no_duplicate_does_not_change_normal_lineage(self):
        result, removed = repair_contexts(self.unrelated, "")
        self.assertEqual(result, self.unrelated)
        self.assertEqual(removed, [])

    def test_similar_prefix_and_comments_are_preserved(self):
        extra = "# persist.vendor.pco5.radio.ctrl comment\n" + (
            "persist.vendor.pco5.radio.ctrl.extra u:object_r:system_mtk_pco_prop:s0\n")
        result, _ = repair_contexts(self.system + extra, self.vendor)
        self.assertTrue(result.endswith(extra))


@unittest.skipUnless(os.environ.get("GOLD_HYBRID_TARGET_FILES"),
                     "Set GOLD_HYBRID_TARGET_FILES for native integration tests")
class NativeValidationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="gold-property-test-")
        cls.addClassCleanup(cls.temp.cleanup)
        cls.work = Path(cls.temp.name)
        target = Path(os.environ["GOLD_HYBRID_TARGET_FILES"]).resolve()
        cls.roots = {part: target / part for part in PROPERTY_FILES}
        cls.roots["SYSTEM_EXT"] = cls.work / "SYSTEM_EXT"
        source_policy = target / "SYSTEM_EXT/etc/selinux"
        shutil.copytree(source_policy, cls.roots["SYSTEM_EXT"] / "etc/selinux")
        cls.original = (source_policy / "system_ext_property_contexts").read_text()
        cls.vendor = (target / "VENDOR/etc/selinux/vendor_property_contexts").read_text()
        cls.native = NativeTools(SOURCE_ROOT, SOURCE_ROOT / "out/host/darwin-x86/bin", cls.work)

    def check_text(self, text):
        (self.roots["SYSTEM_EXT"] / "etc/selinux/system_ext_property_contexts").write_text(text)
        result = validate(self.roots, self.native, self.work, self.id().split(".")[-1])
        return result.returncode, (result.stdout + result.stderr).decode()

    def test_original_fails_before_property_initialization(self):
        code, message = self.check_text(self.original)
        self.assertNotEqual(code, 0)
        self.assertIn("Duplicate prefix match detected for 'persist.vendor.pco5.radio.ctrl'", message)

    def test_camera_duplicate_is_also_fatal_despite_identical_context(self):
        text = "".join(line for line in self.original.splitlines(keepends=True)
                       if not line.startswith("persist.vendor.pco5.radio.ctrl "))
        code, message = self.check_text(text)
        self.assertNotEqual(code, 0)
        self.assertIn("Duplicate prefix match detected for 'vendor.camera.aux.packagelist'", message)

    def test_repaired_policy_and_all_property_types_pass(self):
        text, _ = repair_contexts(self.original, self.vendor)
        code, message = self.check_text(text)
        self.assertEqual(code, 0, message)

    def test_unrelated_duplicate_is_not_silently_ignored(self):
        text, _ = repair_contexts(self.original, self.vendor)
        extra = "gold.test.duplicate u:object_r:default_prop:s0 prefix string\n"
        code, message = self.check_text(text + extra * 2)
        self.assertNotEqual(code, 0)
        self.assertIn("Duplicate prefix match detected for 'gold.test.duplicate'", message)


if __name__ == "__main__":
    unittest.main()
