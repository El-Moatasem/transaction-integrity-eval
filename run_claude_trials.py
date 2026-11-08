#!/usr/bin/env python3
"""Run real agentic trials with the Claude Code CLI (headless mode) and record them.

For every (model, task, trial) it:
  1. creates a fresh workspace OUTSIDE the repo (run_eval.py prepare),
  2. runs `claude -p` inside that workspace with web tools disabled,
  3. saves the full stream-json transcript,
  4. grades the resulting service.py (run_eval.py grade),
  5. records transcript + grade + runtime + cost (run_eval.py record).

Usage:
  python scripts/run_claude_trials.py --models claude-opus-4-1,claude-sonnet-4-5 \
      --tasks T01,T02,T03,T04,T05,T10 --trials 3 --parallel 3

Requires: the `claude` CLI on PATH and logged in, or ANTHROPIC_API_KEY set.
Already-recorded (task, model, trial) combinations are skipped, so a crashed
run can simply be restarted.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUN_EVAL = [sys.executable, str(ROOT / 'run_eval.py')]
AGENT = 'claude-code-cli'
PROMPT = ('Your task is described in INSTRUCTION.md in the current directory. '
          'Read it, then implement the required changes in service.py. '
          'Work only inside the current directory. When you are finished, stop.')
DISALLOWED = 'WebFetch,WebSearch'


def claude_version():
    try:
        return subprocess.run(['claude', '--version'], capture_output=True, text=True, timeout=30).stdout.strip()
    except Exception:
        return 'unknown'


def recorded():
    path = ROOT / 'results' / 'trials.jsonl'
    if not path.exists():
        return set()
    out = set()
    for line in path.read_text().splitlines():
        if line.strip():
            r = json.loads(line)
            out.add((r['task'][:3], r['model_version'], r.get('agent'), r['trial']))
    return out


def parse_stream(transcript):
    """Return (cost_usd, result_event) from a stream-json transcript."""
    cost, result = 0.0, None
    for line in transcript.read_text(errors='replace').splitlines():
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if ev.get('type') == 'result':
            result = ev
            cost = float(ev.get('total_cost_usd') or ev.get('cost_usd') or 0.0)
    return cost, result


def one_trial(model, task, trial, max_turns, timeout, keep):
    tag = f'{task} {model} trial{trial}'
    base = Path(tempfile.mkdtemp(prefix=f'txn-{task}-'))
    ws = base / 'workspace'
    logs = base / 'logs'
    logs.mkdir()
    subprocess.run(RUN_EVAL + ['prepare', '--task', task, '--output', str(ws)], check=True, capture_output=True)
    transcript = logs / 'transcript.jsonl'
    cmd = ['claude', '-p', PROMPT,
           '--model', model,
           '--output-format', 'stream-json', '--verbose',
           '--max-turns', str(max_turns),
           '--permission-mode', 'acceptEdits',
           '--allowedTools', 'Read,Edit,Write,Bash',
           '--disallowedTools', DISALLOWED]
    start = time.time()
    with transcript.open('w') as fh:
        try:
            proc = subprocess.run(cmd, cwd=ws, stdout=fh, stderr=subprocess.STDOUT, timeout=timeout,
                                  env={**os.environ, 'CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC': '1'})
            exit_code = proc.returncode
        except subprocess.TimeoutExpired:
            exit_code = 124
    runtime = round(time.time() - start, 1)
    cost, result = parse_stream(transcript)
    if result is None or exit_code not in (0,):
        # Infrastructure failure (auth, rate limit, crash): do NOT record as a model failure.
        print(f'[INFRA] {tag}: exit={exit_code}; transcript kept at {transcript}', flush=True)
        return tag, 'infra'
    grade_json = logs / 'grade.json'
    subprocess.run(RUN_EVAL + ['grade', '--task', task, '--workspace', str(ws), '--output', str(grade_json)],
                   capture_output=True)
    if not grade_json.exists():
        print(f'[INFRA] {tag}: grading produced no report', flush=True)
        return tag, 'infra'
    passed = json.loads(grade_json.read_text()).get('passed')
    shutil.copy2(ws / 'service.py', logs / 'final_service.py')
    settings = {'max_turns': max_turns, 'permission_mode': 'acceptEdits',
                'disallowed_tools': DISALLOWED, 'cli_version': claude_version(),
                'temperature': 'CLI default (not configurable)',
                'num_turns': result.get('num_turns'), 'stop_subtype': result.get('subtype')}
    rec = subprocess.run(RUN_EVAL + ['record', '--task', task, '--model', model, '--version', model,
                                     '--trial', str(trial), '--transcript', str(transcript),
                                     '--grade-json', str(grade_json), '--settings', json.dumps(settings),
                                     '--agent', AGENT, '--runtime', str(max(runtime, 0.1)),
                                     '--cost', str(cost)], capture_output=True, text=True)
    if rec.returncode != 0:
        print(f'[RECORD-ERROR] {tag}: {rec.stdout}{rec.stderr}', flush=True)
        return tag, 'infra'
    # Keep the agent's final code next to the transcript for the failure analysis.
    code_dir = ROOT / 'results' / 'final_code'
    code_dir.mkdir(parents=True, exist_ok=True)
    safe_model = ''.join(c if c.isalnum() or c in '-_.' else '_' for c in model)
    shutil.copy2(ws / 'service.py', code_dir / f'{task}_{safe_model}_trial{trial:02d}.py')
    if not keep:
        shutil.rmtree(base, ignore_errors=True)
    print(f'[{"PASS" if passed else "FAIL"}] {tag}  {runtime}s  ${cost:.4f}', flush=True)
    return tag, 'pass' if passed else 'fail'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--models', required=True, help='comma-separated exact model IDs')
    ap.add_argument('--tasks', default='T01,T02,T03,T04,T05,T10')
    ap.add_argument('--trials', type=int, default=3)
    ap.add_argument('--parallel', type=int, default=3)
    ap.add_argument('--max-turns', type=int, default=40)
    ap.add_argument('--timeout', type=int, default=900, help='seconds per trial')
    ap.add_argument('--keep-workspaces', action='store_true')
    a = ap.parse_args()
    if shutil.which('claude') is None:
        raise SystemExit('`claude` CLI not found on PATH')
    done = recorded()
    jobs = [(m, t, n) for m in a.models.split(',') for t in a.tasks.split(',')
            for n in range(1, a.trials + 1) if (t, m, AGENT, n) not in done]
    print(f'{len(jobs)} trials to run ({len(done)} already recorded)', flush=True)
    with ThreadPoolExecutor(max_workers=a.parallel) as pool:
        outcomes = list(pool.map(lambda j: one_trial(*j, a.max_turns, a.timeout, a.keep_workspaces), jobs))
    infra = [t for t, s in outcomes if s == 'infra']
    print(f'\nDone. {len(outcomes) - len(infra)} recorded, {len(infra)} infrastructure failures (rerun to retry).')
    subprocess.run(RUN_EVAL + ['summary', '--output', str(ROOT / 'results' / 'summary.json')])


if __name__ == '__main__':
    main()
