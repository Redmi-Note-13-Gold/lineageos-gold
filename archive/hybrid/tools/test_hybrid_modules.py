#!/usr/bin/env python3
"""Hardware-free module staging tests, plus opt-in native metadata/context checks."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from hybrid_modules import (CONTEXT_SIDECARS, FS_ROW, LINK_CONTEXT, LINK_PATH, LINK_TARGET,
                            SOURCE_ROOT, STALE_IMAGES, host_tools, lookup_context, prepare)


def inventory(root):
    entries = {}
    for path in sorted(root.rglob("*")):
        name = path.relative_to(root).as_posix()
        if path.is_symlink():
            entries[name] = ("link", str(path.readlink()))
        elif path.is_file():
            entries[name] = ("file", path.stat().st_mode & 0o777,
                             hashlib.sha256(path.read_bytes()).hexdigest())
        elif path.is_dir():
            entries[name] = ("directory", path.stat().st_mode & 0o777)
    return entries


class StageTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="gold-modules-unit-")
        self.addCleanup(temp.cleanup)
        self.work = Path(temp.name).resolve()
        self.source = self.work / "source"
        self.source.mkdir()
        self.target = self.work / "target_files"
        (self.target / "SYSTEM/lib").mkdir(parents=True)
        (self.target / "SYSTEM/etc/selinux").mkdir(parents=True)
        (self.target / "SYSTEM/etc/init/hw").mkdir(parents=True)
        (self.target / "META").mkdir()
        self.link = self.target / "SYSTEM/lib/modules"
        self.config = self.target / "META/filesystem_config.txt"
        self.original_config = (" 0 0 755 capabilities=0x0\n"
                                "system/lib 0 0 755 capabilities=0x0\n"
                                "system/lib/keep.so 0 0 644 capabilities=0x0\n")
        self.config.write_text(self.original_config)
        self.misc = self.target / "META/misc_info.txt"
        self.misc.write_text("system_fs_type=ext4\n"
                             "system_selinux_fc=out/obj/ETC/file_contexts.bin\n")
        self.contexts = self.target / "META/file_contexts.bin"
        self.contexts.write_bytes(b"mocked compiled contexts")
        self.platform = self.target / "SYSTEM/etc/selinux/plat_file_contexts"
        self.platform.write_text("/system/lib(64)?(/.*)? " + LINK_CONTEXT + "\n")
        for relative, data in {
            "SYSTEM/lib/keep.so": b"unchanged library",
            "ROOT/adb_keys": b"public key sentinel",
            "SYSTEM/etc/init/gold-auth-adb.rc": b"authentication RC sentinel",
            "SYSTEM/etc/init/hw/init.zygote64_32.rc": b"mixed RC sentinel",
            "SYSTEM/etc/init/hw/init.zygote64.rc": b"primary RC sentinel",
            "SYSTEM/etc/init/netd.rc": b"netd RC sentinel",
            "SYSTEM/build.prop": b"ro.adb.secure=1\nro.secure=1\nro.debuggable=0\n",
            "VENDOR/lib/modules/rfkill.ko": b"do not use vendor module as a link target",
        }.items():
            path = self.target / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)

    def native(self, command, **kwargs):
        self.assertEqual(command, ["fs_config", "-D", str(self.target / "SYSTEM"), "-C"])
        self.assertEqual(kwargs["input"], LINK_PATH.lstrip("/") + "\n")
        self.assertTrue(kwargs["check"] and kwargs["capture_output"] and kwargs["text"])
        self.assertTrue(self.link.is_symlink())
        self.assertEqual(str(self.link.readlink()), LINK_TARGET)
        return subprocess.CompletedProcess(command, 0, FS_ROW, "")

    def run_gate(self, check_only=False, native=None, lookup=None):
        with patch("hybrid_modules.lookup_context", side_effect=lookup,
                   return_value=LINK_CONTEXT) as contexts:
            with patch("hybrid_modules.subprocess.run", side_effect=native or self.native) as run:
                result = prepare(self.target, self.source, "fs_config", "libselinux", check_only)
        return result, run, contexts

    def rejected_unchanged(self, pattern=None, **kwargs):
        before = inventory(self.target)
        with self.assertRaisesRegex(ValueError, pattern or ".+"):
            self.run_gate(**kwargs)
        self.assertEqual(inventory(self.target), before)

    def test_adds_only_symlink_and_one_metadata_row_preserving_auth_and_rc(self):
        before = inventory(self.target)
        result, run, contexts = self.run_gate()
        after = inventory(self.target)
        self.assertEqual(set(after) - set(before), {"SYSTEM/lib/modules"})
        self.assertEqual([p for p in before if before[p] != after[p]],
                         ["META/filesystem_config.txt"])
        self.assertEqual(self.config.read_text(), self.original_config + FS_ROW)
        self.assertTrue(result["added_symlink"] and result["added_fs_config"])
        self.assertFalse(result["images_built"] or result["policy_modified"])
        self.assertEqual(result["context"], LINK_CONTEXT)
        self.assertEqual(result["mode"], "0120644")
        self.assertEqual([call.args[0] for call in contexts.call_args_list],
                         [self.contexts, self.platform])
        run.assert_called_once()

    def test_correct_link_and_metadata_are_idempotent(self):
        self.run_gate()
        before = inventory(self.target)
        result, run, contexts = self.run_gate()
        self.assertFalse(result["added_symlink"] or result["added_fs_config"])
        self.assertEqual(inventory(self.target), before)
        run.assert_not_called()
        self.assertEqual(contexts.call_count, 2)

    def test_correct_existing_absolute_link_gets_only_missing_metadata(self):
        self.link.symlink_to(LINK_TARGET)
        inode = self.link.lstat().st_ino
        result, _, _ = self.run_gate()
        self.assertFalse(result["added_symlink"])
        self.assertTrue(result["added_fs_config"])
        self.assertEqual(self.link.lstat().st_ino, inode)

    def test_existing_metadata_gets_only_missing_link(self):
        self.config.write_text(self.original_config + FS_ROW)
        result, run, _ = self.run_gate()
        self.assertTrue(result["added_symlink"])
        self.assertFalse(result["added_fs_config"])
        run.assert_not_called()

    def test_read_only_gate_after_staging(self):
        self.run_gate()
        before = inventory(self.target)
        result, run, _ = self.run_gate(check_only=True)
        self.assertEqual(inventory(self.target), before)
        self.assertTrue(result["check_only"])
        run.assert_not_called()

    def test_read_only_gate_rejects_missing_link_or_metadata(self):
        self.rejected_unchanged("Check-only", check_only=True)
        self.link.symlink_to(LINK_TARGET)
        self.rejected_unchanged("Check-only", check_only=True)
        self.link.unlink()
        self.config.write_text(self.original_config + FS_ROW)
        self.rejected_unchanged("Check-only", check_only=True)

    def test_existing_real_directory_and_contents_are_not_replaced(self):
        self.link.mkdir()
        (self.link / "keep.ko").write_bytes(b"existing data")
        self.rejected_unchanged("Refusing to replace")

    def test_existing_empty_directory_is_not_replaced(self):
        self.link.mkdir()
        self.rejected_unchanged("Refusing to replace")

    def test_existing_file_is_not_replaced(self):
        self.link.write_bytes(b"existing file")
        self.rejected_unchanged("Refusing to replace")

    def test_wrong_relative_foreign_and_self_referential_links_are_rejected(self):
        for target in ("/vendor/lib/modules", "../../../system_dlkm/lib/modules",
                       "modules", "/missing/elsewhere"):
            with self.subTest(target=target):
                self.link.symlink_to(target)
                self.rejected_unchanged("symlink is wrong")
                self.link.unlink()

    def test_symlinked_system_lib_parent_is_rejected(self):
        parent = self.link.parent
        moved = parent.with_name("lib-moved")
        parent.rename(moved)
        parent.symlink_to(moved)
        self.rejected_unchanged("Symlink")

    def test_symlinked_config_is_not_followed(self):
        saved = self.config.with_name("saved-config")
        self.config.rename(saved)
        self.config.symlink_to(saved)
        self.rejected_unchanged("Symlink")

    def test_duplicate_module_metadata_is_rejected(self):
        self.config.write_text(self.original_config + FS_ROW * 2)
        self.rejected_unchanged("Duplicate")

    def test_duplicate_unrelated_metadata_is_rejected_without_repair(self):
        self.config.write_text(self.original_config + "system/lib/keep.so 0 0 644 capabilities=0x0\n")
        self.rejected_unchanged("Duplicate")

    def test_conflicting_module_metadata_is_rejected(self):
        for row in (FS_ROW.replace("644", "777"), FS_ROW.replace(" 0 0 ", " 2000 0 "),
                    FS_ROW.replace("capabilities=0x0", "capabilities=0x1"),
                    FS_ROW.rstrip() + " selabel=u:object_r:system_file:s0\n"):
            with self.subTest(row=row):
                self.config.write_text(self.original_config + row)
                self.rejected_unchanged("Unexpected module")

    def test_descendant_metadata_is_rejected(self):
        self.config.write_text(self.original_config +
                               "system/lib/modules/rfkill.ko 0 0 644 capabilities=0x0\n")
        self.rejected_unchanged("descendants")

    def test_missing_or_conflicting_parent_metadata_is_rejected(self):
        for data in (self.original_config.replace("755", "777"),
                     self.original_config.replace("system/lib 0 0 755 capabilities=0x0\n", "")):
            self.config.write_text(data)
            self.rejected_unchanged("system/lib directory metadata")

    def test_metadata_no_final_newline_and_mode_are_preserved(self):
        self.config.write_bytes(self.original_config.rstrip("\n").encode())
        self.config.chmod(0o640)
        self.run_gate()
        self.assertEqual(self.config.read_text(), self.original_config + FS_ROW)
        self.assertEqual(self.config.stat().st_mode & 0o777, 0o640)

    def test_missing_required_inputs_are_rejected(self):
        for path in (self.config, self.misc, self.contexts, self.platform):
            with self.subTest(path=path):
                original = path.read_bytes()
                path.unlink()
                self.rejected_unchanged("Missing staging input")
                path.write_bytes(original)

    def test_duplicate_missing_dynamic_and_unsafe_context_selection(self):
        for data in ("", self.misc.read_text() * 2, "system_selinux_fc=${fc}\n",
                     "system_selinux_fc=..\n", "system_selinux_fc=/\n",
                     "system_selinux_fc=one two\n"):
            with self.subTest(data=data):
                self.misc.write_text(data)
                self.rejected_unchanged()

    def test_context_input_cannot_be_symlink(self):
        saved = self.contexts.with_name("saved-contexts")
        self.contexts.rename(saved)
        self.contexts.symlink_to(saved)
        self.rejected_unchanged("Symlink")

    def test_context_sidecars_cannot_silently_change_native_lookup(self):
        for base in (self.contexts, self.platform):
            for suffix in CONTEXT_SIDECARS:
                with self.subTest(path=str(base) + suffix):
                    path = Path(str(base) + suffix)
                    path.write_bytes(b"unexpected alternate contexts")
                    self.rejected_unchanged("Ambiguous")
                    path.unlink()

    def test_effective_or_installed_platform_context_drift_is_rejected(self):
        for wrong_file in (self.contexts, self.platform):
            def lookup(path, library):
                return "u:object_r:system_file:s0" if path == wrong_file else LINK_CONTEXT
            self.rejected_unchanged("Unexpected module symlink context", lookup=lookup)

    def test_context_lookup_failure_is_fail_closed(self):
        with patch("hybrid_modules.lookup_context", side_effect=ValueError("no native match")):
            before = inventory(self.target)
            with self.assertRaisesRegex(ValueError, "no native match"):
                prepare(self.target, self.source, "fs_config", "libselinux")
            self.assertEqual(inventory(self.target), before)

    def test_stale_images_rejected_even_after_successful_staging(self):
        self.run_gate()
        for relative in STALE_IMAGES:
            path = self.target / relative
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(b"do not delete an existing image")
            self.rejected_unchanged("Stale image")
            path.unlink()

    def test_dangling_stale_image_is_rejected(self):
        (self.target / "IMAGES").mkdir()
        (self.target / "IMAGES/system.img").symlink_to("/not-present")
        self.rejected_unchanged()

    def test_native_metadata_mismatch_rolls_back_only_new_link(self):
        def native(*args, **kwargs):
            return subprocess.CompletedProcess([], 0, FS_ROW.replace("644", "777"), "")
        self.rejected_unchanged("unexpected symlink metadata", native=native)

    def test_native_process_failure_preserves_existing_link_and_config(self):
        self.link.symlink_to(LINK_TARGET)
        before = inventory(self.target)
        with patch("hybrid_modules.lookup_context", return_value=LINK_CONTEXT):
            with patch("hybrid_modules.subprocess.run", side_effect=subprocess.CalledProcessError(1, [])):
                with self.assertRaises(subprocess.CalledProcessError):
                    prepare(self.target, self.source, "fs_config", "libselinux")
        self.assertEqual(inventory(self.target), before)

    def test_atomic_metadata_publication_failure_rolls_back_new_link(self):
        before = inventory(self.target)
        with patch("hybrid_modules.Path.replace", side_effect=OSError("replace failed")):
            with self.assertRaises(OSError):
                self.run_gate()
        self.assertEqual(inventory(self.target), before)

    def test_concurrent_metadata_edit_is_not_overwritten(self):
        def native(*args, **kwargs):
            self.config.write_text(self.original_config + "# another writer\n")
            return subprocess.CompletedProcess([], 0, FS_ROW, "")
        with self.assertRaisesRegex(ValueError, "concurrently"):
            self.run_gate(native=native)
        self.assertFalse(self.link.is_symlink())
        self.assertEqual(self.config.read_text(), self.original_config + "# another writer\n")

    def test_concurrent_context_edit_is_not_overwritten(self):
        def native(*args, **kwargs):
            self.platform.write_text("# another context edit\n")
            return subprocess.CompletedProcess([], 0, FS_ROW, "")
        with self.assertRaisesRegex(ValueError, "concurrently"):
            self.run_gate(native=native)
        self.assertFalse(self.link.is_symlink())
        self.assertEqual(self.platform.read_text(), "# another context edit\n")
        self.assertEqual(self.config.read_text(), self.original_config)

    def test_concurrent_link_replacement_is_not_removed(self):
        def native(*args, **kwargs):
            self.link.rename(self.link.with_name("our-link-moved"))
            self.link.symlink_to("/another-writer")
            return subprocess.CompletedProcess([], 0, FS_ROW, "")
        with self.assertRaisesRegex(ValueError, "symlink is wrong"):
            self.run_gate(native=native)
        self.assertEqual(str(self.link.readlink()), "/another-writer")
        self.assertEqual(self.config.read_text(), self.original_config)

    def test_context_sidecar_created_during_native_call_is_rejected(self):
        def native(*args, **kwargs):
            Path(str(self.contexts) + ".bin").write_bytes(b"other writer")
            return subprocess.CompletedProcess([], 0, FS_ROW, "")
        with self.assertRaisesRegex(ValueError, "concurrently"):
            self.run_gate(native=native)
        self.assertFalse(self.link.is_symlink())

    def test_staging_must_be_outside_source_without_root_symlink(self):
        with self.assertRaisesRegex(ValueError, "outside and separate"):
            prepare(self.source, self.source, "fs_config", "libselinux")
        nested = self.source / "nested"
        nested.mkdir()
        with self.assertRaisesRegex(ValueError, "outside and separate"):
            prepare(nested, self.source, "fs_config", "libselinux")
        alias = self.work / "alias"
        alias.symlink_to(self.target)
        with self.assertRaisesRegex(ValueError, "root must not"):
            prepare(alias, self.source, "fs_config", "libselinux")


@unittest.skipUnless(os.environ.get("GOLD_HYBRID_TARGET_FILES"),
                     "Set GOLD_HYBRID_TARGET_FILES for native baseline staging tests")
class NativeStageTest(unittest.TestCase):
    def setUp(self):
        self.source = Path(os.environ.get("GOLD_HYBRID_SOURCE_ROOT", SOURCE_ROOT)).resolve()
        self.baseline = Path(os.environ["GOLD_HYBRID_TARGET_FILES"]).resolve()
        temp = tempfile.TemporaryDirectory(prefix="gold-modules-native-")
        self.addCleanup(temp.cleanup)
        self.target = Path(temp.name) / "target_files"
        (self.target / "SYSTEM/lib").mkdir(parents=True)
        (self.target / "SYSTEM/etc/selinux").mkdir(parents=True)
        (self.target / "META").mkdir()
        for relative in ("META/filesystem_config.txt", "META/misc_info.txt", "META/file_contexts.bin",
                         "SYSTEM/etc/selinux/plat_file_contexts"):
            shutil.copy2(self.baseline / relative, self.target / relative)
        for path in (self.baseline / "SYSTEM/etc").glob("fs_config_*"):
            shutil.copy2(path, self.target / "SYSTEM/etc" / path.name)
        self.fs_config, self.libselinux = host_tools(self.source)

    def test_real_metadata_compiled_contexts_and_idempotent_check(self):
        before = inventory(self.target)
        baseline_inputs = {name: hashlib.sha256((self.baseline / name).read_bytes()).hexdigest()
                           for name in ("META/filesystem_config.txt", "META/file_contexts.bin")}
        result = prepare(self.target, self.source, self.fs_config, self.libselinux)
        after = inventory(self.target)
        self.assertEqual(set(after) - set(before), {"SYSTEM/lib/modules"})
        self.assertEqual([p for p in before if before[p] != after[p]],
                         ["META/filesystem_config.txt"])
        self.assertEqual(result["context"], LINK_CONTEXT)
        result = prepare(self.target, self.source, self.fs_config, self.libselinux, check_only=True)
        self.assertFalse(result["added_symlink"] or result["added_fs_config"])
        self.assertEqual(after, inventory(self.target))
        for name, digest in baseline_inputs.items():
            self.assertEqual(hashlib.sha256((self.baseline / name).read_bytes()).hexdigest(), digest)

    def test_native_symlink_specific_wrong_label_is_rejected_before_writes(self):
        contexts = self.target / "META/file_contexts.bin"
        contexts.write_text("/system/lib(/.*)? " + LINK_CONTEXT + "\n"
                            "/system/lib/modules -l u:object_r:system_file:s0\n")
        before = inventory(self.target)
        with self.assertRaisesRegex(ValueError, "Unexpected module symlink context"):
            prepare(self.target, self.source, self.fs_config, self.libselinux)
        self.assertEqual(inventory(self.target), before)

    def test_native_regular_file_rule_does_not_label_the_symlink(self):
        contexts = self.target / "META/file_contexts.bin"
        contexts.write_text("/system/lib(/.*)? " + LINK_CONTEXT + "\n"
                            "/system/lib/modules -- u:object_r:system_file:s0\n")
        self.assertEqual(lookup_context(contexts, self.libselinux), LINK_CONTEXT)

    def test_native_cli_prepare_and_read_only_validation(self):
        command = [sys.executable, "-B", str(Path(__file__).with_name("hybrid_modules.py")),
                   "--target-files", str(self.target), "--source-root", str(self.source)]
        before = inventory(self.target)
        rejected = subprocess.run(command + ["--check-only"], capture_output=True, text=True)
        self.assertEqual(rejected.returncode, 1)
        self.assertIn("Check-only", rejected.stderr)
        self.assertEqual(inventory(self.target), before)
        staged = subprocess.run(command, capture_output=True, text=True, check=True)
        self.assertTrue(json.loads(staged.stdout)["added_symlink"])
        before = inventory(self.target)
        checked = subprocess.run(command + ["--check-only"], capture_output=True, text=True, check=True)
        self.assertTrue(json.loads(checked.stdout)["check_only"])
        self.assertEqual(inventory(self.target), before)


if __name__ == "__main__":
    unittest.main()
