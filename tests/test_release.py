#!/usr/bin/env python3
"""Offline integration tests; never create a tag or contact a release endpoint."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest import mock
import runpy
import io

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / 'tools/tool-release'
PACKAGE = ROOT / 'tools/package-bin'


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        (ROOT / 'target').mkdir(exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT / 'target')
        self.root = Path(self.tmp.name)
        (self.root / 'src').mkdir()
        (self.root / '.github/workflows').mkdir(parents=True)
        self.config = dict(schema=1, name='example', manifest='src/wolf.pkg',
                           gate_workflow='.github/workflows/release-gate.yml',
                           gate_profile='full', build=['sh', 'build.sh'],
                           binaries={'example': 'target/bin/example'},
                           version_args=['--version'], version_pattern=r'^example (?P<version>[0-9]+\.[0-9]+\.[0-9]+)$',
                           smoke=[['{bin}/example', '--version']])
        self.save()
        (self.root / 'src/wolf.pkg').write_text('pkg { name: "example", version: "0.1.0", edition: "1" }\n')
        (self.root / 'CHANGELOG.md').write_text('# Changes\n\n## 0.1.0\n\nFirst preview.\n\n## 0.0.1\nOld.\n')
        (self.root / 'LICENSE').write_text('Test license\n')
        (self.root / 'README.md').write_text('Example\n')
        (self.root / 'wolf-toolchain.toml').write_text('[wolf]\nversion_line = "wolf 0.2.36 (test)"\n')
        (self.root / '.wolf-bin').mkdir()
        wolf = self.root / '.wolf-bin/wolf'
        wolf.write_text('#!/bin/sh\nprintf "wolf 0.2.36 (test)\\n"\n')
        wolf.chmod(0o755)
        (self.root / '.github/workflows/release-gate.yml').write_text('name: release gate\non:\n  workflow_call:\n')
        (self.root / 'build.sh').write_text('mkdir -p target/bin\nprintf \'#!/bin/sh\\nprintf "example 0.1.0\\\\n"\\n\' > target/bin/example\nchmod +x target/bin/example\n')
        self.env = dict(os.environ, SHELL='/bin/sh', HOME=str(self.root / 'home'), GITHUB_ACTIONS='false')
        Path(self.env['HOME']).mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def save(self):
        (self.root / 'release.json').write_text(json.dumps(self.config))

    def call(self, *args, ok=True):
        p = subprocess.run([sys.executable, '-I', str(RELEASE), *args, '--root', str(self.root), '--config', 'release.json'],
                           text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=self.env)
        if ok:
            self.assertEqual(p.returncode, 0, p.stdout)
        else:
            self.assertNotEqual(p.returncode, 0, p.stdout)
        return p.stdout

    def test_matching_version_and_notes(self):
        self.assertIn('PASS release-version', self.call('validate', '--tag', 'v0.1.0'))
        self.assertEqual((self.root / 'target/release-notes.md').read_text(), 'First preview.\n')

    def test_version_tag_mismatch(self):
        self.assertIn('FAIL release-version', self.call('validate', '--tag', 'v0.2.0', ok=False))

    def test_rejects_bad_tag(self):
        for tag in ('v01.1.0', 'v0.1.0-extra', '0.1.0', 'v0.1.0\nother'):
            self.assertIn('FAIL release-version', self.call('validate', '--tag', tag, ok=False))

    def test_missing_or_duplicate_changelog_refused(self):
        (self.root / 'CHANGELOG.md').write_text('## 0.2.0\nNot this release.\n')
        self.call('validate', '--tag', 'v0.1.0', ok=False)
        (self.root / 'CHANGELOG.md').write_text('## 0.1.0\nFirst.\n## 0.1.0\nSecond.\n')
        self.call('validate', '--tag', 'v0.1.0', ok=False)

    def test_wrong_manifest_version_refused(self):
        (self.root / 'src/wolf.pkg').write_text('pkg { version: "9.0.0" }')
        self.assertIn('FAIL release-version', self.call('validate', '--tag', 'v0.1.0', ok=False))

    def test_unknown_config_and_path_escape_refused(self):
        self.config['manifest'] = '../outside'
        self.save()
        self.call('validate', '--tag', 'v0.1.0', ok=False)
        self.config['manifest'] = 'src/wolf.pkg'
        self.config['publish'] = True
        self.save()
        self.call('validate', '--tag', 'v0.1.0', ok=False)

    def test_build_pack_unpack_and_clean_smoke(self):
        self.call('build', '--tag', 'v0.1.0', '--host', 'x86_64-unknown-linux-gnu', '--test-host')
        out = self.root / 'target/dist/example-0.1.0-x86_64-unknown-linux-gnu.tar.gz'
        self.assertTrue(out.exists())
        digest = hashlib.sha256(out.read_bytes()).hexdigest()
        self.assertEqual(Path(str(out) + '.sha256').read_text(), f'{digest}  {out.name}\n')
        self.call('smoke', '--tag', 'v0.1.0', '--host', 'x86_64-unknown-linux-gnu', '--artifacts', str(out.parent), '--test-host')
        with tarfile.open(out) as t:
            names = t.getnames()
        self.assertIn('example-0.1.0-x86_64-unknown-linux-gnu/BUILD.json', names)
        self.assertNotIn('example-0.1.0-x86_64-unknown-linux-gnu/.wolf-bin', names)

    def test_bracket_executable_is_a_valid_archive_name(self):
        self.config['binaries'] = {'[': 'target/bin/['}
        self.save()
        with (self.root / 'build.sh').open('a') as out:
            out.write('cp target/bin/example target/bin/[\n')
        self.call('build', '--tag', 'v0.1.0', '--host', 'x86_64-unknown-linux-gnu', '--test-host')

    def test_family_operand_only_command_is_explicitly_unavailable(self):
        self.config['binaries']['test'] = 'target/bin/test'
        self.config['version_exemptions'] = {'test': 'operand-only command; family version checked by example'}
        self.save()
        with (self.root / 'build.sh').open('a') as out:
            out.write('printf "#!/bin/sh\\nexit 0\\n" > target/bin/test\nchmod +x target/bin/test\n')
        output = self.call('build', '--tag', 'v0.1.0', '--host', 'x86_64-unknown-linux-gnu', '--test-host')
        self.assertIn('UNAVAILABLE release-version-option test reason=', output)
        self.assertIn('observed-cli=0.1.0 binaries=1', output)
        self.config['version_exemptions']['example'] = 'cannot exempt the whole product'
        self.save()
        self.call('validate', '--tag', 'v0.1.0', ok=False)

    def test_bad_compiler_identity_refused(self):
        (self.root / '.wolf-bin/wolf').write_text('#!/bin/sh\necho wrong\n')
        self.call('build', '--tag', 'v0.1.0', '--host', 'x86_64-unknown-linux-gnu', '--test-host', ok=False)

    def test_build_failure_keeps_compiler_diagnostics_and_exit_code(self):
        (self.root / 'build.sh').write_text('echo "E9999 compiler diagnostic witness" >&2\nexit 2\n')
        args = [sys.executable, '-I', str(RELEASE), 'build', '--tag', 'v0.1.0', '--host', 'x86_64-unknown-linux-gnu', '--test-host', '--root', str(self.root), '--config', 'release.json']
        result = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=self.env)
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn('E9999 compiler diagnostic witness', result.stdout)

    def test_cli_mismatch_refused(self):
        (self.root / 'build.sh').write_text((self.root / 'build.sh').read_text().replace('example 0.1.0', 'example 0.9.0'))
        self.assertIn('FAIL release-version', self.call('build', '--tag', 'v0.1.0', '--host', 'x86_64-unknown-linux-gnu', '--test-host', ok=False))

    def test_digest_mismatch_refused_before_execution(self):
        self.call('build', '--tag', 'v0.1.0', '--host', 'x86_64-unknown-linux-gnu', '--test-host')
        out = self.root / 'target/dist/example-0.1.0-x86_64-unknown-linux-gnu.tar.gz'
        out.write_bytes(out.read_bytes() + b'corruption')
        self.call('smoke', '--tag', 'v0.1.0', '--host', 'x86_64-unknown-linux-gnu', '--artifacts', str(out.parent), '--test-host', ok=False)

    def test_archive_traversal_refused(self):
        import io
        out = self.root / 'hostile'
        out.mkdir()
        archive = out / 'example-0.1.0-x86_64-unknown-linux-gnu.tar.gz'
        with tarfile.open(archive, 'w:gz') as t:
            i = tarfile.TarInfo('../escaped')
            i.size = 1
            t.addfile(i, io.BytesIO(b'x'))
        Path(str(archive) + '.sha256').write_text(f'{hashlib.sha256(archive.read_bytes()).hexdigest()}  {archive.name}\n')
        self.call('smoke', '--tag', 'v0.1.0', '--host', 'x86_64-unknown-linux-gnu', '--artifacts', str(out), '--test-host', ok=False)
        self.assertFalse((self.root / 'escaped').exists())

    def test_stage_is_draft_only_and_public_release_is_untouched(self):
        module = runpy.run_path(str(RELEASE))
        stage = module['stage']
        namespace = stage.__globals__
        names = module['expected_assets'](self.config, 'v0.1.0')
        artifacts = self.root / 'assets'
        artifacts.mkdir()
        for name in names:
            (artifacts / name).write_bytes(name.encode())
        (self.root / 'target').mkdir()
        (self.root / 'target/release-notes.md').write_text('First preview.\n')
        writes = []

        def fake_api(repo, suffix, method='GET', data=None):
            if method != 'GET':
                writes.append((suffix, method, data))
                self.assertIs(data['draft'], True)
                return dict(id=42, draft=True, assets=[])
            return dict(id=42, draft=True, assets=[dict(name=n) for n in names])

        def fake_upload(req):
            return io.BytesIO(json.dumps(dict(state='uploaded', digest='sha256:' + hashlib.sha256(req.data).hexdigest())).encode())

        with mock.patch.dict(namespace, validate=lambda *a: '0.1.0', releases=lambda repo: iter([]), api=fake_api, open_url=fake_upload):
            with mock.patch.dict(os.environ, GH_TOKEN='test-fixture', GITHUB_OUTPUT=''):
                stage(self.root, self.config, 'v0.1.0', 'example/example', artifacts, 'a' * 40)
        self.assertEqual(len(writes), 1)
        self.assertEqual(writes[0][1], 'POST')
        with mock.patch.dict(namespace, validate=lambda *a: '0.1.0', releases=lambda repo: iter([dict(id=42, tag_name='v0.1.0', draft=False)]), api=mock.Mock()):
            with self.assertRaisesRegex(ValueError, 'already public'):
                stage(self.root, self.config, 'v0.1.0', 'example/example', artifacts, 'a' * 40)
            namespace['api'].assert_not_called()

    def test_generated_build_provenance(self):
        self.config['provenance_source'] = 'src/build_version/build_version.lu'
        self.save()
        self.call('build', '--tag', 'v0.1.0', '--host', 'x86_64-unknown-linux-gnu', '--test-host')
        self.assertIn('wolf 0.2.36 (test)', (self.root / self.config['provenance_source']).read_text())


class PackagingTests(unittest.TestCase):
    def test_render_ignores_non_scalar_product_metadata(self):
        render = runpy.run_path(str(PACKAGE))['render']
        values = dict(VERSION='0.1.5', binaries=['lobo'], hooks={'formula': 'hooks/lobo/formula.in'}, COUNT=2)
        self.assertEqual(render('version=@@VERSION@@ count=@@COUNT@@', values), 'version=0.1.5 count=2')

    def test_all_first_tier_recipes_render_including_bracket(self):
        generate = runpy.run_path(str(PACKAGE))['generate']
        for product in ('den', 'paxage', 'pelt', 'boreutils'):
            with self.subTest(product=product):
                result = generate(product, '0.1.0', dict(MAC_SHA256='1' * 64, LINUX_SHA256='2' * 64))
                self.assertEqual(len(result), 3)
                self.assertFalse(any(b'@@' in value for value in result.values()))
                if product == 'boreutils':
                    self.assertIn(b'install -Dm755 [ ', result['aur/boreutils-bin/PKGBUILD'])

    def test_bore_packages_install_only_the_dispatcher_on_path(self):
        generate = runpy.run_path(str(PACKAGE))['generate']
        result = generate('boreutils', '0.1.0', dict(MAC_SHA256='1' * 64, LINUX_SHA256='2' * 64))
        formula = result['Formula/boreutils.rb'].decode()
        recipe = result['aur/boreutils-bin/PKGBUILD'].decode()
        self.assertIn('libexec/"boreutils/bin"', formula)
        self.assertIn('(bin/"bore").write', formula)
        self.assertIn('export PATH=', formula)
        self.assertIn('install -Dm755 cat "$pkgdir/usr/lib/boreutils/bin/cat"', recipe)
        self.assertIn('"$pkgdir/usr/bin/bore"', recipe)
        self.assertNotIn('install -Dm755 cat "$pkgdir/usr/bin/cat"', recipe)
        for content in result.values():
            self.assertNotIn(b'conflicts=(\'coreutils\'', content)
            self.assertNotIn(b'provides=(\'coreutils\'', content)

    def test_lobo_byte_for_byte(self):
        p = subprocess.run([sys.executable, '-I', str(PACKAGE), '--product', 'lobo', '--version', '0.1.5',
                            '--offline', '--mac-sha256', '2aa3320da860d0c332c7aac133961a44529cdb3a15697f05ee88f1c851b9191c',
                            '--linux-sha256', 'b61466c05f757712fa7c0e7d0f7c81aa9f1323d18203e67b7fdf3b71b1e9d1a5', '--check'],
                           text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        self.assertEqual(p.returncode, 0, p.stdout)
        self.assertIn('PASS packaging-byte-identity', p.stdout)
        for path in ('Formula/lobo.rb', 'aur/lobo-bin/PKGBUILD', 'aur/lobo-bin/.SRCINFO', 'aur/lobo-bin/lobo-bin.install'):
            self.assertIn(path, p.stdout)

    def test_shared_workflow_never_publishes(self):
        text = (ROOT / '.github/workflows/tool-release.yml').read_text()
        self.assertNotIn('draft=false', text)
        self.assertNotIn('gh release edit', text)
        self.assertIn('workflow_call:', text)
        self.assertIn('needs: [stage, build]', text)
        self.assertIn('public', (ROOT / '.github/workflows/tool-public-smoke.yml').read_text())


if __name__ == '__main__':
    unittest.main(verbosity=2)
