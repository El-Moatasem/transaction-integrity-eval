#!/usr/bin/env python3
"""Run real agentic trials with the Claude Code CLI (headless mode) and record them.

For every (model, task, trial) it:
  1. creates a fresh workspace OUTSIDE the repo (run_eval.py prepare): only the
     starter service.py and INSTRUCTION.md are copied - no reference solution,
     mutants, hidden graders, Git history or other trials' files,
  2. runs `claude -p` inside that workspace with web tools disabled,
  3. saves the full stream-json transcript,
  4. grades the resulting service.py (run_eval.py grade),
  5. records transcript + grade + runtime + cost (run_eval.py record).

Usage:
  python scripts/run_claude_trials.py --models <exact-model-id>[,<id>...] \
      --tasks T01,T02,T03,T04,T05,T10 --trials 3 --parallel 3
  python scripts/run_claude_trials.py --models <id> --dry-run   # no model calls
  python scripts/run_claude_trials.py --audit-only              # rescan transcripts

Requires: the `claude` CLI on PATH and logged in, or ANTHROPIC_API_KEY set.
Already-recorded (task, model, agent, trial) combinations are skipped, so an
interrupted batch can simply be restarted; recorded evidence is never overwritten.

ISOLATION LIMITS (read before reporting results):
  * Workspace isolation is NOT network isolation. WebFetch/WebSearch are
    disallowed, but the Bash tool can still run curl, pip, git, python urllib,
    etc. This runner does not sandbox the network.
  * Workspace isolation is NOT filesystem isolation. Bash runs as your user and
    can read any path you can, including this repository's solutions.
  * After each batch a transcript audit (results/network_audit.json) flags tool
    calls containing indicators such as github, curl, wget, urllib, requests,
    pip install or this repository's path. A flag means "needs human review",
    not proof of contamination; absence of a flag is not proof of isolation,
    because command-string scanning cannot detect every network or file access.
  * Recording is serialized by a process-local threading.Lock in this runner
    and by an exclusive POSIX file lock inside `run_eval.py record`. On
    platforms without fcntl (Windows), do not run two batches at once.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN_EVAL = [sys.executable, str(ROOT / 'run_eval.py')]
RESULTS = ROOT / 'results'
AGENT = 'claude-code-cli'
PROMPT = ('Your task is described in INSTRUCTION.md in the current directory. '
          'Read it, then implement the required changes in service.py. '
          'Work only inside the current directory. When you are finished, stop.')
DISALLOWED = 'WebFetch,WebSearch'
ALLOWED = 'Read,Edit,Write,Bash'
RECORD_LOCK = threading.Lock()

# Indicators that a tool call may have reached the network or the answer key.
AUDIT_PATTERNS = {
    'github': re.compile(r'github', re.I),
    'curl': re.compile(r'\bcurl\b', re.I),
    'wget': re.compile(r'\bwget\b', re.I),
    'urllib': re.compile(r'\burllib\b'),
    'requests': re.compile(r'\b(import requests|from requests\b|requests\.(get|post|put|request|Session))'),
    'pip install': re.compile(r'\bpip3?\s+install\b|-m\s+pip\s+install\b'),
    'url': re.compile(r'https?://'),
    'repository path': re.compile(re.escape(str(ROOT))),
    'answer files': re.compile(r'\b(solution|mutants|audit_variants)/'),
}
# Transcript text suggesting an infrastructure, not model, failure.
INFRA_HINTS = re.compile(r'authenticat|unauthori[sz]ed|invalid api key|401|403|rate.?limit|429|'
                         r'overloaded|529|credit balance|quota|ECONN|ETIMEDOUT|network error', re.I)


def claude_version():
    try:
        return subprocess.run(['claude', '--version'], capture_output=True, text=True, timeout=30).stdout.strip()
    except Exception:
        return 'unknown'


def recorded():
    path = RESULTS / 'trials.jsonl'
    if not path.exists():
        return set()
    out = set()
    for line in path.read_text().splitlines():
        if line.strip():
            r = json.loads(line)
            out.add((r['task'][:3], r['model_version'], r.get('agent'), r['trial']))
    return out


def events(transcript):
    for line in Path(transcript).read_text(errors='replace').splitlines():
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(ev, dict):
            yield ev


def parse_stream(transcript):
    """Return (cost_usd, result_event, reported_model) from a stream-json transcript."""
    cost, result, reported_model = 0.0, None, None
    for ev in events(transcript):
        if ev.get('type') == 'system' and ev.get('subtype') == 'init':
            reported_model = ev.get('model') or reported_model
        if ev.get('type') == 'result':
            result = ev
            cost = float(ev.get('total_cost_usd') or ev.get('cost_usd') or 0.0)
    return cost, result, reported_model


def tool_calls(transcript):
    """Yield (tool_name, serialized_input) for every tool_use block."""
    for ev in events(transcript):
        msg = ev.get('message') if ev.get('type') == 'assistant' else None
        for block in (msg or {}).get('content') or []:
            if isinstance(block, dict) and block.get('type') == 'tool_use':
                yield block.get('name'), json.dumps(block.get('input'), sort_keys=True)


def audit_transcript(transcript):
    hits = []
    calls = list(tool_calls(transcript))
    for name, text in calls:
        for label, pattern in AUDIT_PATTERNS.items():
            m = pattern.search(text)
            if m:
                start = max(0, m.start() - 60)
                hits.append({'indicator': label, 'tool': name, 'excerpt': text[start:m.end() + 60]})
    return {'tool_calls_scanned': len(calls), 'flagged': bool(hits), 'matches': hits[:50]}


def write_network_audit():
    """Scan every recorded transcript; write results/network_audit.json."""
    path = RESULTS / 'trials.jsonl'
    rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()] if path.exists() else []
    report = {
        'note': ('Indicators require human review; they are not proof of contamination, and '
                 'absence of indicators does not prove network or filesystem isolation.'),
        'trials': [],
    }
    for r in rows:
        t = ROOT / r['transcript_path']
        entry = {'task': r['task'], 'model_version': r['model_version'], 'agent': r.get('agent'),
                 'trial': r['trial'], 'transcript_path': r['transcript_path']}
        entry.update(audit_transcript(t) if t.is_file() else {'flagged': True, 'error': 'transcript missing'})
        report['trials'].append(entry)
    report['flagged_count'] = sum(e['flagged'] for e in report['trials'])
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / 'network_audit.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f"Transcript audit: {report['flagged_count']}/{len(report['trials'])} trials flagged for "
          f"human review -> results/network_audit.json", flush=True)
    return report


def build_command(model, max_turns, extra):
    return ['claude', '-p', PROMPT,
            '--model', model,
            '--output-format', 'stream-json', '--verbose',
            '--max-turns', str(max_turns),
            '--permission-mode', 'acceptEdits',
            '--allowedTools', ALLOWED,
            '--disallowedTools', DISALLOWED,
            '--strict-mcp-config'] + extra


def make_workspace(task):
    base = Path(tempfile.mkdtemp(prefix=f'txn-{task}-')).resolve()
    if base == ROOT or ROOT in base.parents:
        raise RuntimeError(f'workspace {base} is inside the repository')
    ws, logs = base / 'workspace', base / 'logs'
    logs.mkdir()
    subprocess.run(RUN_EVAL + ['prepare', '--task', task, '--output', str(ws)], check=True, capture_output=True)
    return base, ws, logs


def infra(tag, reason, transcript=None):
    where = f'; transcript kept at {transcript}' if transcript else ''
    print(f'[INFRA - not recorded] {tag}: {reason}{where}', flush=True)
    return tag, 'infra'


def one_trial(model, task, trial, a, cli_version):
    tag = f'{task} {model} trial{trial}'
    try:
        base, ws, logs = make_workspace(task)
    except Exception as ex:
        return infra(tag, f'workspace preparation failed: {ex}')
    transcript = logs / 'transcript.jsonl'
    extra = ['--bare'] if a.bare else []
    cmd = build_command(model, a.max_turns, extra)
    start = time.time()
    with transcript.open('w') as fh:
        try:
            proc = subprocess.run(cmd, cwd=ws, stdout=fh, stderr=subprocess.STDOUT, timeout=a.timeout,
                                  env={**os.environ, 'CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC': '1'})
            exit_code = proc.returncode
        except subprocess.TimeoutExpired:
            exit_code = 124
        except OSError as ex:
            return infra(tag, f'could not start claude CLI: {ex}', transcript)
    runtime = round(time.time() - start, 1)
    cost, result, reported_model = parse_stream(transcript)
    # Infrastructure failure (auth, rate limit, crash, timeout, missing result
    # event, error result): do NOT record as a model failure.
    if result is None:
        return infra(tag, f'exit={exit_code}, no result event', transcript)
    if exit_code != 0 or result.get('is_error'):
        hint = INFRA_HINTS.search(transcript.read_text(errors='replace'))
        return infra(tag, f"exit={exit_code}, subtype={result.get('subtype')}, is_error={result.get('is_error')}"
                          + (f', matched {hint.group(0)!r}' if hint else ''), transcript)
    grade_json = logs / 'grade.json'
    subprocess.run(RUN_EVAL + ['grade', '--task', task, '--workspace', str(ws), '--output', str(grade_json)],
                   capture_output=True)
    if not grade_json.exists():
        return infra(tag, 'grading produced no report', transcript)
    grade = json.loads(grade_json.read_text())
    if grade.get('exit_code') not in (0, 1):
        return infra(tag, f"grader infrastructure error (exit {grade.get('exit_code')})", transcript)
    passed = grade.get('passed')
    shutil.copy2(ws / 'service.py', logs / 'final_service.py')
    settings = {'max_turns': a.max_turns, 'permission_mode': 'acceptEdits',
                'allowed_tools': ALLOWED, 'disallowed_tools': DISALLOWED,
                'strict_mcp_config': True, 'bare': a.bare, 'cli_version': cli_version,
                'requested_model': model, 'reported_model': reported_model,
                'temperature': 'CLI default (not configurable)',
                'num_turns': result.get('num_turns'), 'stop_subtype': result.get('subtype'),
                'cli_exit_code': exit_code, 'network_isolation': 'none (Bash can reach the network)'}
    safe_model = ''.join(c if c.isalnum() or c in '-_.' else '_' for c in model)
    code_dst = RESULTS / 'final_code' / f'{task}_{safe_model}_trial{trial:02d}.py'
    # One complete record operation at a time: duplicate check, evidence copy
    # and JSONL append happen inside `run_eval.py record` (which also holds an
    # exclusive file lock), followed by the final-code copy.
    with RECORD_LOCK:
        rec = subprocess.run(RUN_EVAL + ['record', '--task', task, '--model', model, '--version', model,
                                         '--trial', str(trial), '--transcript', str(transcript),
                                         '--grade-json', str(grade_json), '--settings', json.dumps(settings),
                                         '--agent', AGENT, '--runtime', str(max(runtime, 0.1)),
                                         '--cost', str(cost)], capture_output=True, text=True)
        if rec.returncode != 0:
            print(f'[RECORD-ERROR - not recorded] {tag}: {rec.stdout}{rec.stderr}', flush=True)
            return tag, 'infra'
        code_dst.parent.mkdir(parents=True, exist_ok=True)
        if not code_dst.exists():
            shutil.copy2(ws / 'service.py', code_dst)
    if not a.keep_workspaces:
        shutil.rmtree(base, ignore_errors=True)
    print(f'[{"PASS" if passed else "FAIL"}] {tag}  {runtime}s  ${cost:.4f}', flush=True)
    return tag, 'pass' if passed else 'fail'


def dry_run(jobs, a):
    """Prepare one workspace per task and print the command; makes no model calls."""
    for task in sorted({t for _, t, _ in jobs}):
        base, ws, _ = make_workspace(task)
        files = sorted(p.relative_to(ws).as_posix() for p in ws.rglob('*'))
        print(f'{task}: workspace {ws} (outside repo) contains {files}')
        shutil.rmtree(base, ignore_errors=True)
    model = jobs[0][0] if jobs else '<model>'
    print('command:', ' '.join(build_command(model, a.max_turns, ['--bare'] if a.bare else [])))
    print(f'{len(jobs)} trials would run; no model was called.')


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--models', help='comma-separated exact model IDs')
    ap.add_argument('--tasks', default='T01,T02,T03,T04,T05,T10')
    ap.add_argument('--trials', type=int, default=3)
    ap.add_argument('--parallel', type=int, default=3)
    ap.add_argument('--max-turns', type=int, default=40)
    ap.add_argument('--timeout', type=int, default=900, help='seconds per trial')
    ap.add_argument('--keep-workspaces', action='store_true')
    ap.add_argument('--bare', action='store_true',
                    help='pass --bare to claude (skips CLAUDE.md/memory/hooks; requires ANTHROPIC_API_KEY)')
    ap.add_argument('--dry-run', action='store_true', help='prepare workspaces and print commands; no model calls')
    ap.add_argument('--audit-only', action='store_true', help='only rescan recorded transcripts')
    a = ap.parse_args()
    if a.audit_only:
        write_network_audit()
        return 0
    if not a.models:
        ap.error('--models is required unless --audit-only')
    if a.trials < 1 or a.parallel < 1:
        ap.error('--trials and --parallel must be positive')
    done = recorded()
    jobs = [(m, t, n) for m in a.models.split(',') for t in a.tasks.split(',')
            for n in range(1, a.trials + 1) if (t, m, AGENT, n) not in done]
    print(f'{len(jobs)} trials to run ({len(done)} already recorded)', flush=True)
    if a.dry_run:
        dry_run(jobs, a)
        return 0
    if shutil.which('claude') is None:
        raise SystemExit('`claude` CLI not found on PATH')
    cli_version = claude_version()
    with ThreadPoolExecutor(max_workers=a.parallel) as pool:
        outcomes = list(pool.map(lambda j: one_trial(*j, a, cli_version), jobs))
    not_recorded = [t for t, s in outcomes if s == 'infra']
    print(f'\nDone. {len(outcomes) - len(not_recorded)} recorded, '
          f'{len(not_recorded)} infrastructure failures not recorded (rerun to retry).')
    subprocess.run(RUN_EVAL + ['summary', '--output', str(RESULTS / 'summary.json')])
    write_network_audit()
    return 0


if __name__ == '__main__':
    sys.exit(main())
