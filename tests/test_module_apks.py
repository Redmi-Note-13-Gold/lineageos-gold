# SPDX-License-Identifier: Apache-2.0
import copy
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    'module_apks', Path(__file__).resolve().parents[1] / 'tools/build-module-apks.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ExistingGraphDeltaTest(unittest.TestCase):
    def setUp(self):
        self.source = next(iter(module.MODULES['DeviceDiagnostics'][1]))
        self.before = {'merged_inputs_match_mainline': True,
                       'projects': {'packages/apps/DeviceDiagnostics': 'fixed'},
                       'files': {self.source: 'old'}}
        self.after = copy.deepcopy(self.before)
        self.after['files'][self.source] = 'new'

    def verify(self):
        return module.verify_delta(self.before, self.after, ['DeviceDiagnostics'])

    def test_existing_source_edit_can_reuse_the_graph(self):
        self.assertEqual(self.verify(), [self.source])

    def test_unchanged_sources_are_not_a_new_compilation(self):
        self.after = copy.deepcopy(self.before)
        with self.assertRaises(ValueError): self.verify()

    def test_either_failed_audit_is_rejected(self):
        for name in ['before', 'after']:
            with self.subTest(audit=name):
                getattr(self, name)['merged_inputs_match_mainline'] = False
                with self.assertRaises(ValueError): self.verify()
                getattr(self, name)['merged_inputs_match_mainline'] = True

    def test_pinned_revision_drift_requires_graph_regeneration(self):
        self.after['projects']['packages/apps/DeviceDiagnostics'] = 'changed'
        with self.assertRaises(ValueError): self.verify()

    def test_build_recipe_or_product_file_changes_are_rejected(self):
        for path in ['packages/apps/DeviceDiagnostics/Android.bp',
                     'device/xiaomi/gold/proprietary-files.txt', 'device/xiaomi/gold/device.mk']:
            with self.subTest(path=path):
                self.after['files'][path] = 'new'
                with self.assertRaises(ValueError): self.verify()
                del self.after['files'][path]

    def test_another_apks_resources_cannot_hide_in_selected_targets(self):
        path = next(iter(module.MODULES['FrameworkResOverlayGold'][1]))
        self.after['files'][path] = 'new'
        with self.assertRaises(ValueError): self.verify()
        self.assertEqual(set(module.verify_delta(self.before, self.after,
                         ['DeviceDiagnostics', 'FrameworkResOverlayGold'])), {self.source, path})

    def test_unrelated_removed_input_is_rejected(self):
        self.before['files']['device/xiaomi/gold/removed.xml'] = 'old'
        with self.assertRaises(ValueError): self.verify()


if __name__ == '__main__': unittest.main()
