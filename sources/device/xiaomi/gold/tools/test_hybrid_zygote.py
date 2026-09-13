#!/usr/bin/env python3
"""Hardware-free zygote staging tests; optional real target-files/native fs_config test."""

import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from hybrid_zygote import INIT_DIR, SOURCE_ROOT, prepare, rc_plan, selected_zygote


PRIMARY = "service zygote /system/bin/app_process64 -Xzygote /system/bin --zygote\n"
MIXED = ("import /system/etc/init/hw/init.zygote64.rc\n"
         "service zygote_secondary /system/bin/app_process32 -Xzygote /system/bin --zygote\n")
PRIMARY_NAME = "init.zygote64.rc"
MIXED_NAME = "init.zygote64_32.rc"
PRIMARY_ROW = INIT_DIR + PRIMARY_NAME + " 0 0 644 capabilities=0x0\n"
MIXED_ROW = INIT_DIR + MIXED_NAME + " 0 0 644 capabilities=0x0\n"


def inventory(root):
    result = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            result[relative] = ("link", str(path.readlink()))
        elif path.is_file():
            result[relative] = ("file", path.stat().st_mode & 0o777,
                                hashlib.sha256(path.read_bytes()).hexdigest())
        elif path.is_dir():
            result[relative] = ("directory", path.stat().st_mode & 0o777)
    return result


class StageTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="gold-zygote-unit-")
        self.addCleanup(temp.cleanup)
        self.work = Path(temp.name).resolve()
        self.source = self.work / "source"
        self.rootdir = self.source / "system/core/rootdir"
        self.rootdir.mkdir(parents=True)
        self.target = self.work / "target_files"
        self.hw = self.target / "SYSTEM/etc/init/hw"
        self.hw.mkdir(parents=True)
        self.bin = self.target / "SYSTEM/bin"
        self.bin.mkdir()
        for name in ("app_process64", "app_process32"):
            path = self.bin / name
            path.write_bytes(b"executable fixture")
            path.chmod(0o755)
        (self.rootdir / PRIMARY_NAME).write_text(PRIMARY)
        (self.rootdir / MIXED_NAME).write_text(MIXED)
        (self.hw / PRIMARY_NAME).write_text(PRIMARY)
        (self.target / "VENDOR").mkdir()
        self.prop = self.target / "VENDOR/build.prop"
        self.prop.write_text("ro.zygote=zygote64_32\nro.adb.secure=1\n")
        (self.target / "META").mkdir()
        self.config = self.target / "META/filesystem_config.txt"
        self.original_config = (" 0 0 755 capabilities=0x0\n" + PRIMARY_ROW
                                + "system/bin/app_process64 0 2000 755 capabilities=0x0\n"
                                + "system/bin/app_process32 0 2000 755 capabilities=0x0\n")
        self.config.write_text(self.original_config)

    def native(self, command, **kwargs):
        self.assertEqual(command, ["fs_config", "-D", str(self.target / "SYSTEM"), "-C"])
        self.assertTrue(kwargs["check"])
        self.assertTrue(kwargs["capture_output"])
        paths = kwargs["input"].splitlines()
        # The missing RC closure must be present before metadata generation starts.
        for path in paths:
            self.assertTrue((self.target / "SYSTEM" / path.removeprefix("system/")).is_file())
        return subprocess.CompletedProcess(command, 0,
            "".join(path + " 0 0 644 capabilities=0x0\n" for path in paths), "")

    def prepare(self):
        with patch("hybrid_zygote.subprocess.run", side_effect=self.native) as run:
            result = prepare(self.target, self.source, self.prop, "fs_config")
        return result, run

    def test_64_only_rc_input_plus_stock_dual_selection(self):
        before = inventory(self.target)
        result, run = self.prepare()
        after = inventory(self.target)
        self.assertEqual(result["ro.zygote"], "zygote64_32")
        self.assertEqual(result["added_rcs"], [MIXED_NAME])
        self.assertEqual(result["rc_closure"], sorted([PRIMARY_NAME, MIXED_NAME]))
        self.assertEqual(set(after) - set(before), {"SYSTEM/etc/init/hw/" + MIXED_NAME})
        self.assertEqual([p for p in before if before[p] != after[p]],
                         ["META/filesystem_config.txt"])
        self.assertEqual(self.config.read_text(), self.original_config + MIXED_ROW)
        self.assertEqual((self.hw / MIXED_NAME).read_text(), MIXED)
        self.assertFalse(result["images_built"])
        run.assert_called_once()

    def test_stages_missing_imported_primary_too(self):
        (self.hw / PRIMARY_NAME).unlink()
        result, _ = self.prepare()
        self.assertEqual(result["added_rcs"], sorted([PRIMARY_NAME, MIXED_NAME]))

    def test_64_bit_selection_does_not_add_secondary_or_call_native(self):
        self.prop.write_text("ro.zygote=zygote64\n")
        before = inventory(self.target)
        result, run = self.prepare()
        self.assertEqual(result["added_rcs"], [])
        self.assertEqual(inventory(self.target), before)
        run.assert_not_called()

    def test_idempotent(self):
        self.prepare()
        before = inventory(self.target)
        result, run = self.prepare()
        self.assertEqual(result["added_rcs"], [])
        self.assertEqual(result["added_fs_config"], [])
        self.assertEqual(inventory(self.target), before)
        run.assert_not_called()

    def test_repairs_missing_metadata_for_existing_rc(self):
        (self.hw / MIXED_NAME).write_text(MIXED)
        result, _ = self.prepare()
        self.assertEqual(result["added_rcs"], [])
        self.assertEqual(result["added_fs_config"], [INIT_DIR + MIXED_NAME])

    def test_missing_app_process32_fails_without_mutation(self):
        (self.bin / "app_process32").unlink()
        before = inventory(self.target)
        with self.assertRaisesRegex(ValueError, "Missing executable"):
            self.prepare()
        self.assertEqual(inventory(self.target), before)

    def test_existing_noncanonical_primary_is_preserved_and_rejected(self):
        (self.hw / PRIMARY_NAME).write_text(PRIMARY + "    disabled\n")
        before = inventory(self.target)
        with self.assertRaisesRegex(ValueError, "differs from canonical"):
            self.prepare()
        self.assertEqual(inventory(self.target), before)

    def test_missing_canonical_dependency_is_rejected(self):
        (self.rootdir / PRIMARY_NAME).unlink()
        with self.assertRaisesRegex(ValueError, "Missing canonical"):
            self.prepare()
        self.assertFalse((self.hw / MIXED_NAME).exists())

    def test_cycle_is_rejected(self):
        (self.rootdir / MIXED_NAME).write_text("import /system/etc/init/hw/" + MIXED_NAME + "\n")
        with self.assertRaisesRegex(ValueError, "cycle"):
            self.prepare()

    def test_unsafe_unresolved_and_foreign_imports_are_rejected(self):
        for name in ("../init.rc", "${ro.hardware}.rc", "subdir/init.rc", "/vendor/etc/init/a.rc"):
            with self.subTest(name=name):
                path = name if name.startswith("/") else "/" + INIT_DIR + name
                (self.rootdir / MIXED_NAME).write_text("import " + path + "\n")
                with self.assertRaises(ValueError):
                    self.prepare()

    def test_symlinked_rc_destination_is_rejected(self):
        (self.hw / MIXED_NAME).symlink_to(self.rootdir / MIXED_NAME)
        with self.assertRaises(ValueError):
            self.prepare()

    def test_symlinked_parent_directory_is_rejected(self):
        moved = self.hw.with_name("hw-moved")
        self.hw.rename(moved)
        self.hw.symlink_to(moved)
        with self.assertRaisesRegex(ValueError, "Symlink"):
            self.prepare()

    def test_non_executable_app_process_is_rejected(self):
        self.config.write_text(self.original_config.replace(
            "system/bin/app_process32 0 2000 755", "system/bin/app_process32 0 2000 644"))
        with self.assertRaisesRegex(ValueError, "Missing executable"):
            self.prepare()

    def test_host_mode_644_uses_android_executable_metadata_without_chmod(self):
        for name in ("app_process64", "app_process32"):
            (self.bin / name).chmod(0o644)
        before = inventory(self.bin)
        self.prepare()
        self.assertEqual(inventory(self.bin), before)

    def test_missing_executable_metadata_is_rejected(self):
        self.config.write_text(self.original_config.replace(
            "system/bin/app_process32 0 2000 755 capabilities=0x0\n", ""))
        with self.assertRaisesRegex(ValueError, "Missing executable"):
            self.prepare()

    def test_absolute_android_app_process_symlink(self):
        self.prop.write_text("ro.zygote=zygote32\n")
        (self.bin / "app_process").symlink_to("/system/bin/app_process32")
        (self.rootdir / "init.zygote32.rc").write_text(
            "service zygote /system/bin/app_process -Xzygote /system/bin --zygote\n")
        result, _ = self.prepare()
        self.assertEqual(result["added_rcs"], ["init.zygote32.rc"])

    def test_duplicate_or_unsafe_property_selection(self):
        for text in ("", "ro.zygote=../bad\n", "ro.zygote=${mode}\n",
                     "ro.zygote=zygote64\nro.zygote=zygote64_32\n"):
            with self.subTest(text=text):
                self.prop.write_text(text)
                with self.assertRaises(ValueError):
                    self.prepare()

    def test_existing_images_prevent_stale_add_missing_reuse(self):
        for relative in ("IMAGES/system.img", "IMAGES/system.map", "IMAGES/vbmeta_system.img",
                         "PREBUILT_IMAGES/system.img", "PREBUILT_IMAGES/vbmeta_system.img"):
            with self.subTest(relative=relative):
                path = self.target / relative
                path.parent.mkdir(exist_ok=True)
                path.write_bytes(b"unchanged stale image")
                before = inventory(self.target)
                with self.assertRaisesRegex(ValueError, "Stale image"):
                    self.prepare()
                self.assertEqual(inventory(self.target), before)
                path.unlink()

    def test_metadata_drift_and_duplicate_rows_fail_without_mutation(self):
        for config in (self.original_config.replace("644", "600"),
                       self.original_config + PRIMARY_ROW):
            self.config.write_text(config)
            before = inventory(self.target)
            with self.assertRaises(ValueError):
                self.prepare()
            self.assertEqual(inventory(self.target), before)

    def test_already_staged_rc_does_not_prove_preexisting_image_is_current(self):
        self.prepare()
        (self.target / "IMAGES").mkdir()
        (self.target / "IMAGES/system.img").write_bytes(b"unverified image")
        with self.assertRaisesRegex(ValueError, "Stale image"):
            self.prepare()

    def test_canonical_source_and_existing_metadata_mode_are_unchanged(self):
        before = inventory(self.source)
        self.config.chmod(0o640)
        self.prepare()
        self.assertEqual(inventory(self.source), before)
        self.assertEqual(self.config.stat().st_mode & 0o777, 0o640)

    def test_atomic_metadata_publication_failure_rolls_back_rc(self):
        before = inventory(self.target)
        with patch("hybrid_zygote.Path.replace", side_effect=OSError("fixture replace failure")):
            with self.assertRaises(OSError):
                self.prepare()
        self.assertEqual(inventory(self.target), before)

    def test_native_failure_removes_only_new_rc(self):
        before = inventory(self.target)
        with patch("hybrid_zygote.subprocess.run", side_effect=subprocess.CalledProcessError(1, [])):
            with self.assertRaises(subprocess.CalledProcessError):
                prepare(self.target, self.source, self.prop, "fs_config")
        self.assertEqual(inventory(self.target), before)

    def test_wrong_native_metadata_is_not_published(self):
        before = inventory(self.target)
        with patch("hybrid_zygote.subprocess.run", return_value=
                   subprocess.CompletedProcess([], 0, MIXED_ROW.replace("644", "777"), "")):
            with self.assertRaisesRegex(ValueError, "unexpected RC metadata"):
                prepare(self.target, self.source, self.prop, "fs_config")
        self.assertEqual(inventory(self.target), before)

    def test_property_source_outside_stage_is_rejected(self):
        outside = self.work / "outside.prop"
        outside.write_text("ro.zygote=zygote64_32\n")
        with self.assertRaisesRegex(ValueError, "must belong to staging"):
            prepare(self.target, self.source, outside, "fs_config")

    def test_staging_inside_source_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "outside the source"):
            prepare(self.source, self.source, self.prop, "fs_config")


@unittest.skipUnless(os.environ.get("GOLD_HYBRID_TARGET_FILES"),
                     "Set GOLD_HYBRID_TARGET_FILES for native baseline integration")
class NativeStageTest(unittest.TestCase):
    def test_real_stock_selection_canonical_closure_and_native_fs_config(self):
        baseline = Path(os.environ["GOLD_HYBRID_TARGET_FILES"]).resolve()
        original_hw = baseline / "SYSTEM/etc/init/hw"
        before = inventory(original_hw)
        variant = selected_zygote(baseline / "VENDOR/build.prop")
        self.assertEqual(variant, "zygote64_32")
        canonical = SOURCE_ROOT / "system/core/rootdir"
        self.assertEqual(hashlib.sha256((canonical / MIXED_NAME).read_bytes()).hexdigest(),
                         "ebefc5059d679d689e1b455f40deaff51be4d444a6c2690451f80a938d7417ec")
        with tempfile.TemporaryDirectory(prefix="gold-zygote-native-") as temp:
            target = Path(temp) / "target_files"
            shutil.copytree(original_hw, target / "SYSTEM/etc/init/hw", symlinks=True)
            (target / "SYSTEM/bin").mkdir()
            for name in ("app_process64", "app_process32"):
                shutil.copy2(baseline / "SYSTEM/bin" / name, target / "SYSTEM/bin" / name)
            (target / "SYSTEM/etc").mkdir(exist_ok=True)
            for path in (baseline / "SYSTEM/etc").glob("fs_config_*"):
                shutil.copy2(path, target / "SYSTEM/etc" / path.name)
            (target / "VENDOR").mkdir()
            shutil.copy2(baseline / "VENDOR/build.prop", target / "VENDOR/build.prop")
            (target / "META").mkdir()
            shutil.copy2(baseline / "META/filesystem_config.txt", target / "META/filesystem_config.txt")
            before_stage = inventory(target)
            closure, missing = rc_plan(target, canonical, variant)
            self.assertEqual(sorted(closure), sorted([PRIMARY_NAME, MIXED_NAME]))
            self.assertEqual(list(missing), [MIXED_NAME])
            result = prepare(target, SOURCE_ROOT, target / "VENDOR/build.prop",
                             SOURCE_ROOT / "out/host/darwin-x86/bin/fs_config")
            self.assertEqual(result["added_rcs"], [MIXED_NAME])
            after_stage = inventory(target)
            self.assertEqual(set(after_stage) - set(before_stage),
                             {"SYSTEM/etc/init/hw/" + MIXED_NAME})
            self.assertEqual([p for p in before_stage if before_stage[p] != after_stage[p]],
                             ["META/filesystem_config.txt"])
            self.assertEqual((target / "SYSTEM/etc/init/hw" / MIXED_NAME).read_bytes(),
                             (canonical / MIXED_NAME).read_bytes())
        self.assertEqual(inventory(original_hw), before)


if __name__ == "__main__":
    unittest.main()
