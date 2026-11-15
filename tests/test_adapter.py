#!/usr/bin/env python3
import runpy
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
adapter = runpy.run_path(str(ROOT / 'tools/release-adapter'))['adapter']
CI = '''name: ci
on:
  workflow_dispatch:
jobs:
  plan:
    runs-on: ubuntu-latest
    steps:
      - env:
          EVENT: ${{ github.event_name }}
          IN_TIER: ${{ inputs.tier }}
          IN_ONLY: ${{ inputs.only }}
          IN_JOBS: ${{ inputs.jobs }}
        run: python3 ci/tiers.py plan
  linux:
    needs: plan
    steps:
      - run: tools/in-container tools/gate
  tier:
    needs: [plan, linux]
    steps:
      - run: python3 ci/tiers.py verdict
  nightly-red:
    needs: tier
    permissions:
      issues: write
    steps:
      - run: ci/nightly-red.sh
'''


class AdapterTests(unittest.TestCase):
    def test_explicit_profiles_and_every_leaf(self):
        all_tiers = adapter(CI, 'all')
        self.assertIn('IN_TIER: all', all_tiers)
        self.assertIn('EVENT: workflow_dispatch', all_tiers)
        self.assertIn('IN_TIER: full', adapter(CI, 'full-every-suite'))
        self.assertIn('IN_ONLY: all', adapter(CI, 'full-every-suite'))
        leaves = adapter(CI, 'every-gate-leaf')
        self.assertIn('IN_JOBS: ""', leaves)
        self.assertIn('run: tools/in-container tools/gate-record\n', leaves)
        self.assertNotIn('run: tools/in-container tools/gate\n', leaves)

    def test_gate_is_tag_bound_and_has_no_nightly_mutation(self):
        text = adapter(CI, 'all')
        self.assertIn('workflow_call:', text)
        self.assertIn('refs/tags/$GITHUB_REF_NAME^{commit}', text)
        self.assertIn('needs: verify', text)
        self.assertIn('needs: [verify, tier]', text)
        self.assertNotIn('issues: write', text)
        self.assertNotIn('nightly-red:', text)

    def test_unknown_or_unavailable_profile_refuses(self):
        with self.assertRaises(ValueError):
            adapter(CI, 'release')
        with self.assertRaises(ValueError):
            adapter(CI.replace('          IN_ONLY:', '          MISSING:'), 'full-every-suite')

    def test_generated_gate_excludes_development_commentary(self):
        text = adapter(CI.replace('    steps:\n', '    # explanatory comment\n    steps:\n'), 'all')
        self.assertNotIn('# explanatory comment', text)
        self.assertIn('run: python3 ci/tiers.py verdict', text)

    def test_ci_command_changes_are_visible_in_generated_adapter(self):
        self.assertNotEqual(adapter(CI, 'all'), adapter(CI.replace('tools/gate\n', 'tools/gate --different\n'), 'all'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
