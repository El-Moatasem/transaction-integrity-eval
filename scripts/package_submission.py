#!/usr/bin/env python3
"""Package a clean micro1 ZIP from reproducible source + authentic trial evidence.

`--final` refuses to package when declared evidence, video and human checks are
missing. This is not an attestation of trial authenticity or video accessibility.
"""
import argparse
from hashlib import sha256
from pathlib import Path
import sys
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from check_submission import check
from submission_policy import is_repository_only

IGNORED_DIRS = {'.git', '.venv', '.pytest_cache', '__pycache__', 'workspaces', 'trial-private', 'jobs', '.tmp'}
IGNORED_NAMES = {'.DS_Store', 'LOCAL_REPLACEMENT_GUIDE.md'}
MAX_BYTES = 50 * 1024 * 1024


def collect():
    included = []
    for path in sorted(ROOT.rglob('*')):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT)
        # Preserve historical metadata/workflow files in Git, but keep them out
        # of the evaluated submission package and its source hash manifest.
        if is_repository_only(rel):
            continue
        if any(part in IGNORED_DIRS for part in rel.parts):
            continue
        if path.name in IGNORED_NAMES or path.name.endswith('.pyc'):
            continue
        if path.name == '.env' or (path.name.startswith('.env.') and path.name != '.env.example'):
            continue
        if rel.parts[0] in ('results', 'transcripts'):
            if path.suffix.lower() in ('.zip', '.mp4', '.mov', '.webm', '.avi', '.key', '.pem'):
                raise ValueError(f'Forbidden results/transcripts artifact {rel}')
        if path.suffix.lower() in ('.key', '.pem', '.p12', '.pfx'):
            raise ValueError(f'Forbidden credential-like artifact {rel}')
        included.append((path, rel.as_posix()))
    return included


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true', help='Verify the source package contents only')
    ap.add_argument('--out', type=Path, help='Destination ZIP; keep outside the source folder')
    ap.add_argument('--final', action='store_true', help='Require actual evidence and completed README')
    args = ap.parse_args()
    if not args.check and args.out is None:
        ap.error('specify --check or --out')
    failures, warnings = check(strict=args.final)
    if failures:
        print('\n'.join('[FAIL] '+f for f in failures))
        return 1
    try:
        included = collect()
    except ValueError as e:
        print('[FAIL]', e)
        return 1
    if 'README.md' not in {r for _, r in included}:
        print('[FAIL] README.md must be at ZIP root')
        return 1
    total = sum(p.stat().st_size for p,_ in included)
    if total >= MAX_BYTES:
        print(f'[FAIL] Uncompressed total >= 50 MiB: {total}')
        return 1
    print(f'Source packaging check: {len(included)} files, {total} bytes (before compression)')
    if args.check:
        if warnings:
            print('Reminder: source-only readiness does not mean the evidence/video requirements have been met.')
        return 0
    dest = args.out.expanduser().resolve()
    if dest.is_relative_to(ROOT.resolve()):
        print('[FAIL] Output ZIP must be outside the project directory')
        return 1
    dest.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(dest, 'w', ZIP_DEFLATED, compresslevel=9) as z:
        for p, name in included:
            z.write(p, arcname=name)
        # Evidence files may change between runs, so hash only included
        # RESULTS paths here; source manifest remains a separate frozen file.
        evidence = [(p, rel) for p, rel in included if rel.startswith(('results/', 'transcripts/')) and not rel.endswith('.gitkeep')]
        if evidence:
            body = ''.join(sha256(p.read_bytes()).hexdigest()+'  '+rel+'\n' for p,rel in evidence)
            z.writestr('manifests/RESULTS.sha256', body)
    with ZipFile(dest) as z:
        if z.testzip() is not None:
            print('[FAIL] ZIP integrity test failed')
            return 1
        bad = [i.filename for i in z.infolist() if i.filename.startswith('/') or '..' in Path(i.filename).parts]
        if bad:
            print('[FAIL] Unsafe ZIP entries', bad)
            return 1
    if dest.stat().st_size > MAX_BYTES:
        print(f'[FAIL] ZIP is too large: {dest.stat().st_size}')
        return 1
    print(f'Created {dest} ({dest.stat().st_size} bytes); evidence_complete={args.final}')
    if not args.final:
        print('DEVELOPMENT PACKAGE ONLY: real model results, reviewed findings and video not yet verified.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
