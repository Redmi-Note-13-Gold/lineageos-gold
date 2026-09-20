# SPDX-License-Identifier: Apache-2.0
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    'gold_package', Path(__file__).resolve().parents[1] / 'tools/check-gold-package.py')
package = importlib.util.module_from_spec(spec)
spec.loader.exec_module(package)


class ImsStartupTest(unittest.TestCase):
    defaults = ['persist.vendor.ims_support=1', 'persist.vendor.volte_support=1',
                'ro.vendor.md_auto_setup_ims=1']

    def test_locked_modem_startup_contract(self):
        result = package.verify_ims_startup_properties(self.defaults + ['persist.vendor.mims_support=2'])
        self.assertEqual(result['persist.vendor.ims_support'], '1')

    def test_previous_candidate_mims_count_does_not_initialize_backend(self):
        with self.assertRaisesRegex(ValueError, 'persist.vendor.ims_support'):
            package.verify_ims_startup_properties(['persist.vendor.mims_support=2'])

    def test_disabled_or_missing_required_switch_is_rejected(self):
        for index in range(len(self.defaults)):
            for changed in [self.defaults[:index] + self.defaults[index + 1:],
                            [line if i != index else line[:-1] + '0'
                             for i, line in enumerate(self.defaults)]]:
                with self.subTest(index=index, changed=changed), self.assertRaises(ValueError):
                    package.verify_ims_startup_properties(changed)

    def test_duplicate_even_identical_value_is_rejected(self):
        with self.assertRaises(ValueError):
            package.verify_ims_startup_properties(self.defaults + [self.defaults[0]])
