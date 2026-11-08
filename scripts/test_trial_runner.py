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
    if model.startswith('stub-maxturns'):
        if model == 'stub-maxturns-solved':
            import os, shutil; shutil.copy(os.environ['STUB_SOLUTION'], 'service.py')
        if model == 'stub-maxturns-broken':
            open('service.py', 'w').write('def broken(:')
        emit({{'type': 'result', 'subtype': 'error_max_turns', 'is_error': True, 'num_turns': 3,
              'total_cost_usd': 0.0}}); sys.exit(1)
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
        # Fail closed: the real CLI must be unreachable. PATH holds only the
        # stub directory and system dirs (the runner and grader use absolute
        # sys.executable), and the resolved `claude` must be this stub.
        path = os.pathsep.join([str(bin_dir), '/usr/bin', '/bin'])
        cls.env = {**os.environ, 'PATH': path}
        cls.env.pop('ANTHROPIC_API_KEY', None)
        resolved = shutil.which('claude', path=path)
        if resolved != str(stub):
            raise RuntimeError(f'refusing to run: claude resolves to {resolved}, not the stub')
        version = subprocess.run([str(stub), '--version'], capture_output=True, text=True, env=cls.env)
        if version.stdout.strip() != '0.0.0 (offline stub)':
            raise RuntimeError(f'stub CLI is not executable: {version.stdout}{version.stderr}')
        cls.env['STUB_SOLUTION'] = str(ROOT / 'tasks' / 'T01_capture-idempotency' / 'solution' / 'service.py')

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

    def test_4_max_turns_is_a_graded_model_attempt(self):
        out = self.run_runner('--models', 'stub-maxturns,stub-maxturns-solved,stub-maxturns-broken',
                              '--tasks', 'T01', '--trials', '1', '--parallel', '3')
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertNotIn('[INFRA', out.stdout)
        rows = {r['model_version']: r for r in self.rows() if r['model_version'].startswith('stub-maxturns')}
        # Outcome comes from the real grader, not from the subtype.
        self.assertEqual(rows['stub-maxturns']['passed'], False)
        self.assertEqual(rows['stub-maxturns-solved']['passed'], True)
        for r in rows.values():
            s = r['settings']
            self.assertEqual(s['stop_subtype'], 'error_max_turns')
            self.assertTrue(s['turn_budget_exhausted'])
            self.assertEqual(s['max_turns'], 40)
            self.assertGreater(r['runtime_seconds'], 0)
            self.assertTrue((self.repo / r['transcript_path']).is_file())
        # Ungradable attempt: preserved separately, never scored.
        self.assertNotIn('stub-maxturns-broken', rows)
        inc = [json.loads(l) for l in (self.repo / 'results' / 'incomplete_attempts.jsonl').read_text().splitlines()]
        self.assertEqual([(r['model_version'], r['status']) for r in inc], [('stub-maxturns-broken', 'incomplete')])
        self.assertNotIn('passed', inc[0])
        self.assertTrue(inc[0]['settings']['turn_budget_exhausted'])
        evidence = self.repo / inc[0]['evidence_dir']
        self.assertTrue((evidence / 'transcript.jsonl').is_file())
        self.assertIn('def broken', (evidence / 'final_service.py').read_text())
        again = self.run_runner('--models', 'stub-maxturns,stub-maxturns-solved,stub-maxturns-broken',
                                '--tasks', 'T01', '--trials', '1')
        self.assertIn('0 trials to run', again.stdout)


if __name__ == '__main__':
    unittest.main()
