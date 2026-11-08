#!/usr/bin/env python3
"""Offline tests for scripts/run_claude_trials.py. NO model is called.

The runner is executed inside a temporary COPY of the repository with a stub
`claude` executable first on PATH, so nothing is written to the real results/
or transcripts/ folders and no stub output can be mistaken for trial evidence.

Run: python -m unittest discover -s scripts -p 'test_trial_runner.py'
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

STUB = textwrap.dedent('''\
    #!{python}
    # Offline stand-in for the claude CLI used only by test_trial_runner.py.
    import json, sys
    args = sys.argv[1:]
    if args == ['--version']:
        print('0.0.0 (offline stub)'); sys.exit(0)
    model = args[args.index('--model') + 1]
    def emit(ev): print(json.dumps(ev), flush=True)
    emit({{'type': 'system', 'subtype': 'init', 'model': model}})
    if model == 'stub-auth':
        emit({{'type': 'result', 'subtype': 'success', 'is_error': True,
              'result': 'Invalid API key - please run /login'}}); sys.exit(1)
    if model == 'stub-noresult':
        sys.exit(0)
    if model == 'stub-crash':
        print('Traceback: segfault'); sys.exit(139)
    cmd = 'curl https://github.com/x' if model == 'stub-curl' else 'ls'
    emit({{'type': 'assistant', 'message': {{'content': [
        {{'type': 'tool_use', 'name': 'Bash', 'input': {{'command': cmd}}}}]}}}})
    emit({{'type': 'result', 'subtype': 'success', 'is_error': False, 'num_turns': 1,
          'total_cost_usd': 0.0}})
''')


class TrialRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='trial-runner-test-')
        cls.repo = Path(cls.tmp.name) / 'repo'
        cls.repo.mkdir()
        shutil.copy2(ROOT / 'run_eval.py', cls.repo)
        ignore = shutil.ignore_patterns('__pycache__', '.DS_Store')
        shutil.copytree(ROOT / 'scripts', cls.repo / 'scripts', ignore=ignore)
        shutil.copytree(ROOT / 'tasks', cls.repo / 'tasks', ignore=ignore)
        bin_dir = Path(cls.tmp.name) / 'bin'
        bin_dir.mkdir()
        stub = bin_dir / 'claude'
        stub.write_text(STUB.format(python=sys.executable))
        stub.chmod(0o755)
        cls.env = {**os.environ, 'PATH': f'{bin_dir}{os.pathsep}{os.environ["PATH"]}'}
        cls.env.pop('ANTHROPIC_API_KEY', None)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def run_runner(self, *args):
        return subprocess.run([sys.executable, str(self.repo / 'scripts' / 'run_claude_trials.py'), *args],
                              cwd=self.tmp.name, env=self.env, text=True, capture_output=True, timeout=300)

    def rows(self):
        path = self.repo / 'results' / 'trials.jsonl'
        return [json.loads(l) for l in path.read_text().splitlines() if l.strip()] if path.exists() else []

    def test_1_help_and_dry_run(self):
        self.assertEqual(self.run_runner('--help').returncode, 0)
        out = self.run_runner('--models', 'stub-ok', '--tasks', 'T01,T10', '--trials', '1', '--dry-run')
        self.assertEqual(out.returncode, 0, out.stderr)
        for line in out.stdout.splitlines():
            if 'workspace' in line and 'contains' in line:
                self.assertIn("['INSTRUCTION.md', 'service.py']", line)
                self.assertNotIn(str(self.repo), line.split(' contains ')[0])
        self.assertEqual(self.rows(), [])

    def test_2_infrastructure_failures_not_recorded(self):
        out = self.run_runner('--models', 'stub-auth,stub-noresult,stub-crash', '--tasks', 'T01',
                              '--trials', '1', '--parallel', '3')
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(out.stdout.count('[INFRA - not recorded]'), 3, out.stdout)
        self.assertEqual(self.rows(), [])

    def test_3_parallel_recording_no_duplicates_and_resume(self):
        out = self.run_runner('--models', 'stub-ok,stub-curl', '--tasks', 'T01,T02', '--trials', '2',
                              '--parallel', '6')
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        rows = self.rows()
        keys = [(r['task'], r['model_version'], r['agent'], r['trial']) for r in rows]
        self.assertEqual(len(keys), 8)
        self.assertEqual(len(set(keys)), 8, 'duplicate trial records')
        for r in rows:
            self.assertFalse(Path(r['transcript_path']).is_absolute())
            self.assertFalse(Path(r['grade_report']).is_absolute())
            self.assertTrue((self.repo / r['transcript_path']).is_file())
            for field in ('transcript_sha256', 'code_sha256', 'grader_sha256', 'runtime_seconds', 'cost_usd'):
                self.assertIn(field, r)
            s = r['settings']
            self.assertEqual(s['cli_version'], '0.0.0 (offline stub)')
            self.assertEqual(s['reported_model'], r['model_version'])
        before = (self.repo / 'results' / 'trials.jsonl').read_bytes()
        again = self.run_runner('--models', 'stub-ok,stub-curl', '--tasks', 'T01,T02', '--trials', '2')
        self.assertIn('0 trials to run (8 already recorded)', again.stdout)
        self.assertEqual((self.repo / 'results' / 'trials.jsonl').read_bytes(), before)
        audit = json.loads((self.repo / 'results' / 'network_audit.json').read_text())
        flagged = {(t['model_version'], t['flagged']) for t in audit['trials']}
        self.assertEqual(flagged, {('stub-ok', False), ('stub-curl', True)})


if __name__ == '__main__':
    unittest.main()
