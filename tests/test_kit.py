"""Tests for the kit lookup. They run the real script against a copy of the stand-in kit in a temp folder.

Run with: /usr/bin/python3 -I tests/test_kit.py
"""
import json
import os
import shutil
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
# The script sits in ../scripts in the repo and in .. once installed to ~/.claude/scripts/tests.
SCRIPTS_DIR = os.path.join(HERE, '..', 'scripts') if os.path.isdir(os.path.join(HERE, '..', 'scripts')) else os.path.join(HERE, '..')
SCRIPT = os.path.join(SCRIPTS_DIR, 'kit.py')
STANDIN = os.path.join(HERE, 'kits', 'standin')
PYTHON = '/usr/bin/python3'

# Copied from tests/test_failing_check.py, since tests can't import each other: keep them the same.
CLEAN_ENV = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}


class Kit(unittest.TestCase):
    def setUp(self):
        self.root = os.path.realpath(tempfile.mkdtemp(prefix='kit-test-'))
        self.kits = os.path.join(self.root, 'kits')
        shutil.copytree(STANDIN, os.path.join(self.kits, 'standin'))

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def run_script(self, *args):
        p = subprocess.run([PYTHON, '-I', SCRIPT, *args], cwd=self.root, capture_output=True, text=True,
                           env=CLEAN_ENV, timeout=60)
        return p.returncode, p.stdout, p.stderr

    def show(self, name, *args):
        rc, stdout, stderr = self.run_script('show', name, '--kits', self.kits, *args)
        self.assertEqual(rc, 0, stdout + stderr)
        return json.loads(stdout)

    def write_manifest(self, manifest):
        with open(os.path.join(self.kits, 'standin', 'kit.json'), 'w') as f:
            f.write(manifest if isinstance(manifest, str) else json.dumps(manifest))

    def manifest(self, **changes):
        with open(os.path.join(STANDIN, 'kit.json')) as f:
            data = json.load(f)
        for key, value in changes.items():
            if value is None:
                data.pop(key)
            else:
                data[key] = value
        return data

    def test_show_prints_the_manifest_with_full_paths(self):
        out = self.show('standin')
        folder = os.path.join(self.kits, 'standin')
        self.assertEqual({k: out[k] for k in ('status', 'format', 'name', 'version', 'folder')},
                         {'status': 'ok', 'format': 1, 'name': 'standin', 'version': '0.1.0', 'folder': folder})
        self.assertEqual(out['applies_when'], "The task changes the stand-in's sample file.")
        self.assertEqual([out['design'], out['guidance'], out['checklist']],
                         [os.path.join(folder, f) for f in ('design.md', 'guidance.md', 'checklist.md')])
        self.assertEqual(out['checks'], [{'name': 'sample', 'command': f'/usr/bin/python3 -I {folder}/checks/sample.py'}])
        self.assertEqual(out['bindings'], [{'read': os.path.join(folder, 'extra/always.md'), 'tag': None},
                                           {'read': os.path.join(folder, 'extra/motion.md'), 'tag': 'motion'}])
        self.assertEqual(out['stacks'], ['alpha'])

    def test_a_listed_stack_adds_its_entries(self):
        out = self.show('standin', '--stack', 'alpha')
        self.assertIn({'read': os.path.join(self.kits, 'standin', 'stacks/alpha/notes.md'), 'tag': None},
                      out['bindings'])

    def test_an_unlisted_stack_still_gets_the_core(self):
        out = self.show('standin', '--stack', 'beta')
        self.assertEqual((out['status'], len(out['bindings'])), ('ok', 2))

    def test_optional_keys_left_out_read_as_null_or_empty(self):
        self.write_manifest({'format': 1, 'name': 'standin', 'version': '0.1.0', 'applies_when': 'Always.'})
        out = self.show('standin')
        self.assertEqual([out[k] for k in ('design', 'guidance', 'checklist', 'checks', 'bindings', 'stacks')],
                         [None, None, None, [], [], []])

    def test_refusals_exit_1_with_a_reason(self):
        cases = [
            ('no folder for the name', 'missing', None, 'no kit'),
            ('no kit.json', 'standin', 'remove', 'kit.json'),
            ('kit.json not JSON', 'standin', '{not json', 'kit.json'),
            ('format 2', 'standin', self.manifest(format=2), 'format'),
            ('name differs from the folder', 'standin', self.manifest(name='other'), 'name'),
            ('applies_when missing', 'standin', self.manifest(applies_when=None), 'applies_when'),
            ('version missing', 'standin', self.manifest(version=None), 'version'),
            ('a named file is missing', 'standin', self.manifest(guidance='nowhere.md'), 'nowhere.md'),
            ('bindings not a list', 'standin', self.manifest(bindings='x'), 'bindings'),
            ('a check not an object', 'standin', self.manifest(checks=[3]), 'checks'),
            ('a binding with no read', 'standin', self.manifest(bindings=[{'tag': 'motion'}]), 'bindings'),
            ('a check with no command', 'standin', self.manifest(checks=[{'name': 'sample'}]), 'checks'),
        ]
        for label, name, manifest, word in cases:
            with self.subTest(label):
                self.tearDown()
                self.setUp()
                if manifest == 'remove':
                    os.remove(os.path.join(self.kits, 'standin', 'kit.json'))
                elif manifest is not None:
                    self.write_manifest(manifest)
                rc, stdout, stderr = self.run_script('show', name, '--kits', self.kits)
                self.assertEqual((rc, stderr), (1, ''))
                out = json.loads(stdout)
                self.assertEqual(out['status'], 'refused')
                self.assertIn(word, out['reason'])

    STANDIN_ENTRY = {'name': 'standin', 'applies_when': "The task changes the stand-in's sample file."}

    def add_kit(self, name, **changes):
        """Copies the stand-in as kit NAME, its manifest's name set and CHANGES applied."""
        folder = os.path.join(self.kits, name)
        shutil.copytree(STANDIN, folder)
        with open(os.path.join(folder, 'kit.json'), 'w') as f:
            json.dump(self.manifest(name=name, **changes), f)

    def list_kits(self, kits=None):
        rc, stdout, stderr = self.run_script('list', '--kits', kits or self.kits)
        self.assertEqual((rc, stderr), (0, ''), stdout)
        return json.loads(stdout)

    def test_list_prints_every_kit_sorted_by_name(self):
        self.add_kit('alpha', applies_when='Alpha work.')
        self.assertEqual(self.list_kits(), {'status': 'ok', 'refused': [], 'kits': [
            {'name': 'alpha', 'applies_when': 'Alpha work.'}, self.STANDIN_ENTRY]})

    def test_list_names_a_kit_show_would_refuse_and_still_lists_the_rest(self):
        self.add_kit('broken', format=2)
        os.makedirs(os.path.join(self.kits, 'empty'))
        out = self.list_kits()
        self.assertEqual(out['kits'], [self.STANDIN_ENTRY])
        self.assertEqual([r['name'] for r in out['refused']], ['broken', 'empty'])
        self.assertIn('format', out['refused'][0]['reason'])
        self.assertIn('kit.json', out['refused'][1]['reason'])

    def test_list_of_a_missing_or_empty_kits_folder_is_empty(self):
        empty = os.path.join(self.root, 'empty')
        os.makedirs(empty)
        for kits in (os.path.join(self.root, 'nowhere'), empty):
            with self.subTest(kits):
                self.assertEqual(self.list_kits(kits), {'status': 'ok', 'kits': [], 'refused': []})

    def test_list_skips_hidden_folders_and_plain_files(self):
        os.makedirs(os.path.join(self.kits, '.git'))
        with open(os.path.join(self.kits, 'README.md'), 'w') as f:
            f.write('not a kit')
        self.assertEqual(self.list_kits(), {'status': 'ok', 'kits': [self.STANDIN_ENTRY], 'refused': []})

    def test_list_follows_a_linked_kit_folder(self):
        # The real install: ~/.claude/kits/<name> links to the kits repo.
        os.rename(os.path.join(self.kits, 'standin'), os.path.join(self.root, 'elsewhere'))
        os.symlink(os.path.join(self.root, 'elsewhere'), os.path.join(self.kits, 'standin'))
        self.assertEqual(self.list_kits()['kits'], [self.STANDIN_ENTRY])

    def test_list_refuses_a_link_that_leads_nowhere(self):
        # The kits repo moved: the kit must be named as refused, not dropped.
        os.symlink(os.path.join(self.root, 'gone'), os.path.join(self.kits, 'lost'))
        out = self.list_kits()
        self.assertEqual(out['kits'], [self.STANDIN_ENTRY])
        self.assertEqual([r['name'] for r in out['refused']], ['lost'])

    def test_list_refuses_a_kits_path_that_is_not_a_folder(self):
        path = os.path.join(self.root, 'file')
        with open(path, 'w') as f:
            f.write('x')
        rc, stdout, stderr = self.run_script('list', '--kits', path)
        self.assertEqual((rc, stderr), (1, ''))
        self.assertEqual(json.loads(stdout)['status'], 'refused')

    @unittest.skipIf(os.geteuid() == 0, 'root reads any folder')
    def test_list_refuses_a_kits_folder_it_cannot_read(self):
        path = os.path.join(self.root, 'locked')
        os.mkdir(path)
        os.chmod(path, 0)
        try:
            rc, stdout, stderr = self.run_script('list', '--kits', path)
        finally:
            os.chmod(path, 0o755)
        self.assertEqual((rc, stderr), (1, ''))
        out = json.loads(stdout)
        self.assertEqual(out['status'], 'refused')
        self.assertIn('could not read %s' % path, out['reason'])

    def test_usage_errors_exit_2_with_nothing_on_stdout(self):
        for args in [(), ('nonsense',), ('show',), ('show', 'standin', 'extra'), ('show', 'standin', '--stack'),
                     ('list', 'extra'), ('list', '--stack', 'alpha')]:
            with self.subTest(args):
                rc, stdout, stderr = self.run_script(*args)
                self.assertEqual((rc, stdout), (2, ''))
                self.assertTrue(stderr)


if __name__ == '__main__':
    unittest.main()
