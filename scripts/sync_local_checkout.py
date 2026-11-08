#!/usr/bin/env python3
"""Local-only cautious codebase replacement. Does not interact with GitHub.

Usage:
    python scripts/sync_local_checkout.py /absolute/path/to/checkout
    python scripts/sync_local_checkout.py /absolute/path/to/checkout --apply

Backups of every overwritten/deleted path are saved next to the checkout.
Untracked unknown files are preserved. Existing .git, local env and credentials
are not copied, deleted, or modified. Review `git diff` afterward.
"""
import argparse
import datetime
import pathlib
import shutil
import subprocess
import sys

SOURCE=pathlib.Path(__file__).resolve().parents[1]
EXCLUDE={'.git','.venv','__pycache__','.pytest_cache','results','transcripts','jobs','workspaces','trial-private','.tmp'}
EXCLUDED_FILES={'.env','.DS_Store'}
OBSOLETE=[
    'MANIFEST.sha256','task_catalog.json','LOCAL_REPLACEMENT_GUIDE.md',
    'docs/APPLICATION_FLOW.md','docs/PROBLEMS.md',
    'docs/CANDIDATE_SHA256SUMS.txt','docs/DEMO_VIDEO_OUTLINE.md',
    'docs/EXPERIMENT_RECORD_TEMPLATE.md','docs/GIT_FLOW_AND_COMMITS.txt',
    'docs/GRADER_HARDENING.md','docs/HARBOR_SETUP.md','docs/PILOT_AND_SELECTION.md',
    'docs/PR_Descriptions.txt','docs/PR_TEMPLATES','docs/SETUP_EXECUTION.txt',
    'docs/SUBMISSION_CHECKLIST.md','docs/TASK_RESEARCH_RATIONALE.md',
    'docs/VALIDATION_AND_FAIRNESS.md','docs/alternative_solutions',
]
for t in sorted((SOURCE/'tasks').glob('T*')):
    for suffix in ('README.md','metadata.json','tests/stress_test_service.py'):
        OBSOLETE.append(f'tasks/{t.name}/{suffix}')


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('target',type=pathlib.Path)
    ap.add_argument('--apply',action='store_true')
    args=ap.parse_args()
    target=args.target.expanduser().resolve()
    if target==SOURCE:
        raise SystemExit('Source and destination must be different')
    if not (target/'.git').exists():
        raise SystemExit('Target must be an existing Git checkout (.git required)')
    if not (target/'tasks').is_dir():
        raise SystemExit('Target must be a transaction-integrity-eval checkout')
    status = subprocess.run(['git','-C',str(target),'status','--porcelain','--untracked-files=no'],
                            text=True,capture_output=True,check=True)
    if status.stdout.strip():
        if args.apply:
            raise SystemExit('Tracked files have uncommitted changes. Commit/stash them or use a clean checkout first.')
        print('WARNING: checkout has uncommitted tracked changes; --apply will refuse them.')
    files=[]
    for path in sorted(SOURCE.rglob('*')):
        if not path.is_file():continue
        rel=path.relative_to(SOURCE)
        if any(x in EXCLUDE for x in rel.parts) or path.name in EXCLUDED_FILES:
            continue
        if path.name.startswith('.env') and path.name!='.env.example':continue
        files.append((path,rel))
    old=[x for x in OBSOLETE if (target/x).exists()]
    print(f'Plan: copy/replace {len(files)} source files; remove {len(old)} obsolete files or folders')
    for item in old:print('  REMOVE',item)
    if not args.apply:
        print('Dry-run only. Re-run with --apply to save backup and modify local checkout.')
        return 0
    backup=target.parent/(target.name+'-backup-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
    if backup.exists():raise SystemExit('Backup directory exists; choose a new execution time')
    for _,rel in files:
        dest=target/rel
        if dest.exists():
            if dest.read_bytes()==(SOURCE/rel).read_bytes():continue
            saved=backup/rel;saved.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(dest,saved)
    for item in old:
        dest=target/item
        saved=backup/item;saved.parent.mkdir(parents=True,exist_ok=True)
        if dest.is_dir():shutil.copytree(dest,saved)
        else:shutil.copy2(dest,saved)
    for item in old:
        dest=target/item
        if dest.is_dir():shutil.rmtree(dest)
        elif dest.exists():dest.unlink()
    for source,rel in files:
        dest=target/rel;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,dest)
    print('Updated local checkout only. Backup:',backup)
    print('Next: review `git status`, `git diff`, and rerun validation before committing.')
    return 0

if __name__=='__main__':
    sys.exit(main())
