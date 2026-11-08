#!/usr/bin/env python3
"""Source readiness and conservative micro1 evidence checklist.

Automated checks cannot prove a model run was genuine, expert work was done,
or a video is viewable. The participant must verify those independently.
"""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from run_eval import tasks
sys.path.insert(0, str(ROOT / 'scripts'))
from submission_policy import is_git_admin_document

PLACEHOLDERS = (
    'VIDEO_URL_PENDING', 'RESULTS_PENDING', 'FAILURE_ANALYSIS_PENDING',
    'HOT_TAKE_PENDING', 'HUMAN_REVIEW_PENDING',
)


def result_rows():
    path = ROOT / 'results' / 'trials.jsonl'
    if not path.is_file() or not path.stat().st_size:
        return [], ['results/trials.jsonl missing or empty']
    rows = []
    problems = []
    for i, line in enumerate(path.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError('expected object')
            rows.append(row)
        except (ValueError, json.JSONDecodeError) as ex:
            problems.append(f'trials.jsonl line {i}: {ex}')
    return rows, problems


def check(strict=False):
    failures = []
    warnings = []
    # Additional technical documentation and historical notes are allowed.
    # Require the two submission-oriented entry points without deleting others.
    for name in ('ARCHITECTURE.md', 'DOCUMENTATION.md'):
        if not (ROOT / 'docs' / name).is_file():
            failures.append(f'missing required documentation: docs/{name}')
    expected_root = ('README.md', '.env.example', 'requirements.txt', 'run_eval.py')
    for name in expected_root:
        if not (ROOT / name).is_file():
            failures.append(f'missing required root file: {name}')
    tasks_list = tasks()
    catalog = json.loads((ROOT / 'task_catalog.json').read_text())
    if len(tasks_list) != len(catalog):
        failures.append(f'expected {len(catalog)} candidate task directories '
                        f'(task_catalog.json entries), got {len(tasks_list)}')
    if not (ROOT / 'manifests' / 'SOURCE.sha256').is_file():
        failures.append('missing source SHA256 manifest')
    else:
        sys.path.insert(0, str(ROOT / 'scripts'))
        from manifest import TARGET, manifest
        if TARGET.read_text() != manifest():
            failures.append('source manifest stale: regenerate with python scripts/manifest.py --write')
    retained_workflow_docs = []
    for p in ROOT.rglob('*'):
        if not p.is_file() or any(x in p.parts for x in ('.git', '.venv', '__pycache__', 'results', 'transcripts')):
            continue
        if p.suffix.lower() in ('.pem', '.key', '.p12', '.pfx') or p.name == '.env':
            failures.append(f'possible private key or environment file: {p.relative_to(ROOT)}')
        if is_git_admin_document(p.relative_to(ROOT)):
            retained_workflow_docs.append(p.relative_to(ROOT))
    if retained_workflow_docs:
        warnings.append(f'{len(retained_workflow_docs)} historical Git/PR documents are retained locally and excluded from the submission ZIP')
    readme = (ROOT / 'README.md').read_text() if (ROOT / 'README.md').is_file() else ''
    for marker in PLACEHOLDERS:
        if marker in readme:
            warnings.append(f'README has pending marker: {marker}')
    if strict:
        if any(marker in readme for marker in PLACEHOLDERS):
            failures.append('README still has missing video/results/failure/human-review placeholders')
        video_sec = readme.split('## Video walkthrough link', 1)[-1].split('\n## ', 1)[0]
        if not re.search(r'https://\S+', video_sec) or 'VIDEO_URL_PENDING' in video_sec:
            failures.append('README must include actual publicly accessible video URL')
        results, errors = result_rows()
        failures.extend(errors)
        run_groups = defaultdict(list)
        task_ids = set()
        for i, row in enumerate(results, 1):
            key = (row.get('model_version'), row.get('agent'), row.get('task'))
            run_groups[key].append(row)
            task_ids.add(row.get('task'))
            for name in ('transcript_path', 'grade_report'):
                loc = row.get(name, '')
                path = ROOT / loc
                if not loc or path.resolve().is_relative_to(ROOT.resolve()) is False or not path.is_file():
                    failures.append(f'trial {i}: missing portable {name}')
            tp = ROOT / row.get('transcript_path', '')
            if tp.is_file() and row.get('transcript_sha256'):
                digest = hashlib.sha256(tp.read_bytes()).hexdigest()
                if digest != row['transcript_sha256']:
                    failures.append(f'trial {i}: transcript content does not match recorded hash')
            gp = ROOT / row.get('grade_report', '')
            if gp.is_file():
                try:
                    grade = json.loads(gp.read_text())
                    if grade.get('task') != row.get('task') or grade.get('code_sha256') != row.get('code_sha256'):
                        failures.append(f'trial {i}: grade task/code hash mismatches trial record')
                except ValueError:
                    failures.append(f'trial {i}: grade report invalid JSON')
            if not row.get('model_version') or not row.get('date_utc') or row.get('runtime_seconds') is None or row.get('cost_usd') is None:
                failures.append(f'trial {i}: missing model ID/date/cost/runtime')
        if results and any(len(rows) < 2 for rows in run_groups.values()):
            failures.append('multiple independent trials required: at least 2 per reported model/agent/task group')
        if results and not (ROOT / 'results' / 'summary.json').is_file():
            failures.append('missing results/summary.json; run run_eval.py summary --output results/summary.json')
        for name in ('RESULTS_REPORT.md', 'HUMAN_REVIEW.md'):
            p = ROOT / 'results' / name
            if not p.is_file() or len(p.read_text().strip()) < 150:
                failures.append(f'missing reviewed results/{name} (fill from evaluation templates)')
        desc = ROOT / 'submission_description.txt'
        if not desc.is_file() or len(desc.read_text().strip()) < 80 or '[' in desc.read_text() or 'PENDING' in desc.read_text():
            failures.append('missing completed submission_description.txt for event form')
        warnings.extend([
            'Verify the video actually opens without logging in, plays audio, and is <=5 minutes.',
            'Verify at least one tested model is a current frontier model; code cannot certify this.',
            'Manually inspect real Harbor/Docker Oracle/NOP logs and verify actual isolation.',
            'Verify ALL model results/transcripts are authentic and free of private data.',
            'Expert must check the 10 problem/reference/grader contracts and sign off on content.',
        ])
    else:
        warnings.append('Empirical results and video are expected to be missing until real calibration runs are performed.')
    return failures, warnings


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--strict', action='store_true', help='Require completed authentic evidence and README fields')
    args = ap.parse_args()
    fails, warns = check(args.strict)
    for issue in fails:
        print('[FAIL]', issue)
    for issue in warns:
        print('[PENDING]', issue)
    print(f'Submission readiness: {len(fails)} failing requirement(s), {len(warns)} pending/check-manually item(s)')
    return int(bool(fails))


if __name__ == '__main__':
    sys.exit(main())
