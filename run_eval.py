#!/usr/bin/env python3
"""Local diagnostic evaluation and honest record keeping; NOT an isolation sandbox.

Formal agent trials require a separate sandbox (e.g. Harbor/Docker). Only use this
script to grade code you are prepared to execute on your current machine.
"""
import argparse
from collections import defaultdict
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
TASK_ROOT = ROOT / 'tasks'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def tasks():
    return sorted(p for p in TASK_ROOT.iterdir() if p.is_dir() and (p / 'instruction.md').is_file())


def select(task_id):
    found = [p for p in tasks() if p.name.startswith(task_id + '_') or p.name == task_id]
    if len(found) != 1:
        raise SystemExit('Unknown/ambiguous task. Choose from: ' + ', '.join(t.name[:3] for t in tasks()))
    return found[0]


def grade_code(task, code, timeout=60):
    """Run pytest in a temporary grading workspace, outside the agent's task folder."""
    with tempfile.TemporaryDirectory(prefix='txn-grade-') as temp:
        work = Path(temp)
        shutil.copy2(code, work / 'service.py')
        shutil.copytree(task / 'tests', work / 'tests')
        env = os.environ.copy()
        env.update(PYTHONPATH=str(work), PYTHONDONTWRITEBYTECODE='1', PYTEST_DISABLE_PLUGIN_AUTOLOAD='1')
        try:
            proc = subprocess.run(
                [sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider', 'tests/test_service.py'],
                cwd=work, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                timeout=timeout,
            )
            return dict(passed=proc.returncode == 0, exit_code=proc.returncode, log=proc.stdout[-24000:])
        except subprocess.TimeoutExpired:
            return dict(passed=False, exit_code=124, log=f'Grading timed out after {timeout} seconds')
        except OSError as exc:
            return dict(passed=False, exit_code=125, log=f'Grading infrastructure error: {exc}')


def _validate_one(args):
    task, timeout = args
    variants = {
        'reference': 'solution/service.py',
        'baseline': 'environment/service.py',
        'wrong_fix': 'mutants/service.py',
    }
    runs = {name: grade_code(task, task / rel, timeout=timeout) for name, rel in variants.items()}
    valid = (runs['reference']['exit_code'] == 0 and
             runs['baseline']['exit_code'] == 1 and
             runs['wrong_fix']['exit_code'] == 1)
    return dict(task=task.name, controls=runs, valid=valid)


def validate(args):
    from concurrent.futures import ThreadPoolExecutor
    selected = [select(args.task)] if args.task else tasks()
    report = dict(timestamp_utc=utc_now(), tasks=[])
    # A small concurrency pool permits independent controls without overloading
    # CI and causing spurious lock/pytest timeouts.
    with ThreadPoolExecutor(max_workers=min(2, len(selected))) as pool:
        for outcome in pool.map(_validate_one, [(t, args.timeout) for t in selected]):
            report['tasks'].append(outcome)
            runs = outcome['controls']
            status = 'PASS' if outcome['valid'] else 'FAIL'
            print(f"{outcome['task'][:3]} {status} | " + ' '.join(
                f'{name}={runs[name]["exit_code"]}' for name in ('reference', 'baseline', 'wrong_fix')
            ), flush=True)
            if not outcome['valid']:
                for name, expected in [('reference', 0), ('baseline', 1), ('wrong_fix', 1)]:
                    if runs[name]['exit_code'] != expected:
                        print(f'  {name}: {runs[name]["log"][-1600:]}')
    path = Path(args.output).expanduser().resolve() if args.output else ROOT / 'results' / 'validation.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + '\n')
    print(f'Wrote {path}')  # Support output paths outside the repository.
    return int(any(not x['valid'] for x in report['tasks']))


def prepare(args):
    task = select(args.task)
    dest = Path(args.output).expanduser().resolve()
    if dest == ROOT or dest == task or dest == TASK_ROOT:
        raise SystemExit('Output must be a fresh isolated workspace, never the repository root')
    if dest.exists() and any(dest.iterdir()):
        raise SystemExit('Output directory must be absent or empty')
    dest.mkdir(parents=True, exist_ok=True)
    for src in (task / 'environment').iterdir():
        if src.is_file() and src.name != 'Dockerfile':
            shutil.copy2(src, dest / src.name)
    shutil.copy2(task / 'instruction.md', dest / 'INSTRUCTION.md')
    print(f'Prepared {dest} for {task.name}. Give only this folder to the agent.')
    return 0


def grader_sha(task):
    h = hashlib.sha256()
    for path in sorted((task / 'tests').rglob('*')):
        if path.is_file() and path.suffix in ('.py', '.sh'):
            h.update(path.relative_to(task).as_posix().encode() + b'\0')
            h.update(path.read_bytes())
    return h.hexdigest()


def grade(args):
    task = select(args.task)
    workspace = Path(args.workspace).expanduser().resolve()
    code = workspace / 'service.py'
    if not code.is_file():
        raise SystemExit(f'Missing agent implementation {code}')
    check = grade_code(task, code, timeout=args.timeout)
    report = {
        'timestamp_utc': utc_now(), 'task': task.name, 'workspace': str(workspace),
        'passed': check['passed'], 'exit_code': check['exit_code'], 'test_log': check['log'],
        'code_sha256': sha(code), 'instruction_sha256': sha(task / 'instruction.md'),
        'grader_sha256': grader_sha(task),
    }
    dest = Path(args.output).expanduser().resolve() if args.output else ROOT / 'results' / f'{task.name[:3]}_last_grade.json'
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(report, indent=2) + '\n')
    print(f'{task.name[:3]}: {"PASS" if check["passed"] else "FAIL"} (exit {check["exit_code"]})')
    print(check['log'][-4000:])
    print(f'Saved {dest}')
    return 0 if check['passed'] else 1


def _safe_name(value):
    slug = re.sub(r'[^a-zA-Z0-9_.-]+', '-', value.strip())[:80].strip('.-')
    if not slug:
        raise SystemExit('Model/agent identifiers must not be blank')
    return slug


@contextmanager
def records_lock():
    """Exclusive cross-process lock for results/trials.jsonl (POSIX fcntl).

    Without fcntl (Windows) this degrades to no locking; do not run concurrent
    recorders there.
    """
    lock_path = ROOT / 'results' / '.trials.lock'
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        import fcntl
    except ImportError:
        yield
        return
    with lock_path.open('a') as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def record(args):
    """Copy an ACTUAL transcript + grade into portable in-package evidence paths.

    Provenance of arbitrary files cannot be authenticated here. The participant
    must ensure these are real untouched agent outputs and accurate billing data.
    """
    task = select(args.task)
    if args.trial < 1 or args.runtime is None or args.runtime <= 0 or args.cost is None or args.cost < 0:
        raise SystemExit('Supply positive trial number and measured runtime; cost must be nonnegative')
    try:
        settings = json.loads(args.settings)
    except json.JSONDecodeError as exc:
        raise SystemExit(f'--settings must contain valid JSON: {exc}')
    if not isinstance(settings, dict):
        raise SystemExit('--settings must be a JSON object')
    transcript = Path(args.transcript).expanduser().resolve()
    grade_path = Path(args.grade_json).expanduser().resolve()
    if not transcript.is_file() or not transcript.stat().st_size:
        raise SystemExit('Supply a nonempty authentic model trial transcript')
    if not grade_path.is_file():
        raise SystemExit('Grade report does not exist')
    g = json.loads(grade_path.read_text())
    if g.get('task') != task.name or g.get('exit_code') not in (0, 1):
        raise SystemExit('Grade is not for this task, or represents an infrastructure failure')
    if not g.get('code_sha256') or not g.get('grader_sha256'):
        raise SystemExit('Grade report missing code/grader hashes; rerun grade with this version')
    model_id = _safe_name(args.version)
    agent_id = _safe_name(args.agent)
    basename = f'{task.name[:3]}_{model_id}_{agent_id}_trial{args.trial:02d}'
    transcript_suffix = transcript.suffix.lower() if transcript.suffix.lower() in ('.txt', '.json', '.jsonl', '.log', '.md') else '.txt'
    raw_dst = ROOT / 'transcripts' / (basename + transcript_suffix)
    grade_dst = ROOT / 'results' / 'grades' / (basename + '.json')
    with records_lock():
        return _record_locked(args, task, settings, transcript, grade_path, g, raw_dst, grade_dst, basename)


def _record_locked(args, task, settings, transcript, grade_path, g, raw_dst, grade_dst, basename):
    records = ROOT / 'results' / 'trials.jsonl'
    existing = [json.loads(line) for line in records.read_text().splitlines() if line.strip()] if records.exists() else []
    key = (task.name, args.version, args.agent, args.trial)
    if any((r.get('task'), r.get('model_version'), r.get('agent'), r.get('trial')) == key for r in existing):
        raise SystemExit('This task/model/agent/trial is already recorded; do not overwrite provenance')
    if raw_dst.exists() or grade_dst.exists():
        raise SystemExit(f'Evidence destination already exists for {basename}')
    raw_dst.parent.mkdir(parents=True, exist_ok=True)
    grade_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(transcript, raw_dst)
    shutil.copy2(grade_path, grade_dst)
    record = {
        'task': task.name, 'trial': args.trial, 'model': args.model, 'model_version': args.version,
        'agent': args.agent, 'settings': settings, 'date_utc': utc_now(), 'passed': g['passed'],
        'runtime_seconds': args.runtime, 'cost_usd': args.cost,
        'transcript_path': raw_dst.relative_to(ROOT).as_posix(),
        'transcript_sha256': sha(raw_dst),
        'grade_report': grade_dst.relative_to(ROOT).as_posix(),
        'code_sha256': g['code_sha256'], 'grader_sha256': g['grader_sha256'],
        'instruction_sha256': g['instruction_sha256'], 'notes': args.notes,
    }
    with records.open('a') as fp:
        fp.write(json.dumps(record, sort_keys=True) + '\n')
    print(f'Recorded participant-supplied trial evidence: {basename}')
    print('This recorder does not independently attest the model run or its reported cost.')
    return 0


def summarize_records(records):
    groups = defaultdict(list)
    for row in records:
        groups[(row['model_version'], row.get('agent', ''), row['task'])].append(row)
    report = []
    for (model, agent, task), rows in sorted(groups.items()):
        rows = sorted(rows, key=lambda r: r['trial'])
        n = len(rows)
        successes = sum(bool(r['passed']) for r in rows)
        report.append({
            'model_version': model, 'agent': agent, 'task': task, 'trials': n,
            'passed': successes, 'pass_rate': successes / n,
            'pass_at_k_observed': int(successes > 0),
            'pass_pow_k_observed': int(successes == n),
            'total_runtime_seconds': sum(float(r.get('runtime_seconds') or 0) for r in rows),
            'total_cost_usd': sum(float(r.get('cost_usd') or 0) for r in rows),
        })
    return report


def summary(args):
    path = ROOT / 'results' / 'trials.jsonl'
    if not path.exists():
        print('No real trial records yet. Run authentic trials before reporting model scores.')
        return 0
    rows = [json.loads(s) for s in path.read_text().splitlines() if s.strip()]
    report = summarize_records(rows)
    body = json.dumps(report, indent=2) + '\n'
    print(body)
    if args.output:
        dest = Path(args.output).expanduser().resolve()
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(body)
        print(f'Wrote {dest}')
    return 0


def main():
    p = argparse.ArgumentParser(description='Offline transaction-integrity benchmark controls')
    sub = p.add_subparsers(dest='command', required=True)
    v = sub.add_parser('validate', help='Reference pass, starter/mutant assertion failures')
    v.add_argument('--task'); v.add_argument('--timeout', type=int, default=60); v.add_argument('--output'); v.set_defaults(func=validate)
    prep = sub.add_parser('prepare', help='Produce a clean agent-visible workspace')
    prep.add_argument('--task', required=True); prep.add_argument('--output', required=True); prep.set_defaults(func=prepare)
    grade_parser = sub.add_parser('grade', help='Grade a completed workspace locally (not sandboxed)')
    grade_parser.add_argument('--task', required=True); grade_parser.add_argument('--workspace', required=True)
    grade_parser.add_argument('--output'); grade_parser.add_argument('--timeout', type=int, default=60); grade_parser.set_defaults(func=grade)
    rec = sub.add_parser('record', help='Copy genuine participant-provided trial evidence into the project')
    for k in ('task', 'model', 'version', 'transcript', 'grade-json'):
        rec.add_argument('--' + k, required=True)
    rec.add_argument('--trial', type=int, required=True)
    rec.add_argument('--settings', default='{}')
    rec.add_argument('--agent', default='manual-isolated-agent')
    rec.add_argument('--runtime', type=float, required=True)
    rec.add_argument('--cost', type=float, required=True)
    rec.add_argument('--notes', default='')
    rec.set_defaults(func=record)
    s = sub.add_parser('summary', help='Report observed outcomes, not population estimates')
    s.add_argument('--output'); s.set_defaults(func=summary)
    a = p.parse_args()
    if hasattr(a, 'timeout') and a.timeout < 1:
        p.error('--timeout must be positive')
    return a.func(a)


if __name__ == '__main__':
    sys.exit(main())
