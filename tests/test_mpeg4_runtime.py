# SPDX-License-Identifier: Apache-2.0
"""Run against the locked stock blob and the actual failed Android ELF command."""
import ast
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SYMBOLS = ('__aeabi_memclr', '__aeabi_memcpy', '__aeabi_memset', '__gnu_Unwind_Find_exidx')


@unittest.skipUnless(all(os.environ.get(k) for k in (
    'GOLD_ANDROID_TREE', 'GOLD_MPEG4_STOCK_LIBRARY', 'GOLD_MPEG4_ELF_COMMAND')),
    'requires the pinned stock library, Android tree and captured ELF check command')
class Mpeg4RuntimeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tree = Path(os.environ['GOLD_ANDROID_TREE'])
        cls.original = Path(os.environ['GOLD_MPEG4_STOCK_LIBRARY']).read_bytes()
        if hashlib.sha256(cls.original).hexdigest() != 'c12266e17f3c282c7f74f1778cfccc39f607082a30fe7c8c3449fc8a2b30d576':
            raise AssertionError('stock input is not the independently verified Global library')
        sys.path.insert(0, str(cls.tree / 'tools/extract-utils'))
        from extract_utils.fixups_blob import BlobFixupCtx, blob_fixup
        from extract_utils.file import File
        recipe = ROOT / 'device/xiaomi/gold/extract-files.py'
        node = next(n for n in ast.parse(recipe.read_text()).body
                    if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name)
                    and n.target.id == 'blob_fixups')
        namespace = {'blob_fixup': blob_fixup, 'blob_fixups_user_type': dict}
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(recipe), 'exec'), namespace)
        cls.temporary = tempfile.TemporaryDirectory(prefix='gold-mpeg4-regression-')
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.fixed_path = Path(cls.temporary.name) / 'libmp4enc_sa.ca7.so'
        cls.fixed_path.write_bytes(cls.original)
        relative = 'vendor/lib/libmp4enc_sa.ca7.so'
        namespace['blob_fixups'][relative].run(BlobFixupCtx(str(recipe.parent)), File(relative), str(cls.fixed_path))
        cls.fixed = cls.fixed_path.read_bytes()
        cls.command = json.loads(Path(os.environ['GOLD_MPEG4_ELF_COMMAND']).read_text())
        spec = importlib.util.spec_from_file_location('mpeg4_package', ROOT / 'tools/check-gold-package.py')
        cls.package = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.package)

    def test_only_four_symbol_version_entries_change(self):
        data = self.original
        offset = struct.unpack_from('<I', data, 32)[0]
        size, count, names_index = struct.unpack_from('<HHH', data, 46)
        sections = [struct.unpack_from('<10I', data, offset + i * size) for i in range(count)]
        names = data[sections[names_index][4]:][:sections[names_index][5]]
        def name(start, table):
            return table[start:table.index(0, start)].decode()
        named = {name(s[0], names): s for s in sections}
        dynsym, versions = named['.dynsym'], named['.gnu.version']
        strings = sections[dynsym[6]]
        strings = data[strings[4]:][:strings[5]]
        expected = set()
        for i in range(dynsym[5] // dynsym[9]):
            start = struct.unpack_from('<I', data, dynsym[4] + i * dynsym[9])[0]
            if name(start, strings) in SYMBOLS:
                pos = versions[4] + 2 * i
                self.assertEqual(struct.unpack_from('<H', data, pos)[0], 3)
                self.assertEqual(struct.unpack_from('<H', self.fixed, pos)[0], 1)
                expected.add(pos)
        self.assertEqual(len(expected), 4)
        self.assertEqual(len(self.fixed), len(data))
        self.assertEqual({i for i, (a, b) in enumerate(zip(data, self.fixed)) if a != b}, expected)

    def test_real_android_dependency_check_rejects_original_and_accepts_fix(self):
        original = Path(self.temporary.name) / 'original.so'
        original.write_bytes(self.original)
        before = subprocess.run(self.command[:-1] + [str(original)], cwd=self.tree, capture_output=True, text=True)
        self.assertNotEqual(before.returncode, 0)
        for symbol in SYMBOLS:
            self.assertIn('Unresolved symbol: ' + symbol + '@LIBC_PRIVATE', before.stderr)
        after = subprocess.run(self.command[:-1] + [str(self.fixed_path)], cwd=self.tree, capture_output=True, text=True)
        self.assertEqual(after.returncode, 0, after.stderr)

    def test_package_requires_exact_fixed_blob_and_rejects_raw_or_tampered(self):
        def check(data):
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, 'w') as archive:
                archive.writestr('VENDOR/lib/libmp4enc_sa.ca7.so', data)
            with zipfile.ZipFile(buffer) as archive:
                return self.package.verify_mpeg4_runtime(archive)
        result = check(self.fixed)
        self.assertEqual(result['source_sha256'], hashlib.sha256(self.original).hexdigest())
        self.assertEqual(result['sha256'], hashlib.sha256(self.fixed).hexdigest())
        for data in (self.original, self.fixed[:-1] + bytes([self.fixed[-1] ^ 1])):
            with self.assertRaises(ValueError):
                check(data)
