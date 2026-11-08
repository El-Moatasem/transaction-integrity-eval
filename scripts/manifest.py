#!/usr/bin/env python3
"""Cross-platform SHA256 source manifest generator and validator.

Run `python scripts/manifest.py --write` after intentional code/doc changes.
Run `python scripts/manifest.py --check` before freezing an evaluation.
Transient run results, local credentials, and the manifest itself are excluded.
"""
import argparse
import hashlib
from pathlib import Path
import sys

from submission_policy import is_repository_only

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / 'manifests' / 'SOURCE.sha256'
EXCLUDE_DIRS = {'.git', '.venv', '.pytest_cache', '__pycache__', 'results', 'transcripts', 'jobs', 'workspaces', 'trial-private', '.tmp'}
EXCLUDE_NAMES = {'.DS_Store'}


def sources():
    for p in sorted(ROOT.rglob('*')):
        if not p.is_file():
            continue
        rel = p.relative_to(ROOT)
        if any(part in EXCLUDE_DIRS for part in rel.parts) or p == TARGET or is_repository_only(rel):
            continue
        if p.name in EXCLUDE_NAMES or p.name.endswith('.pyc'):
            continue
        if p.name.startswith('.env') and p.name != '.env.example':
            continue
        yield p, rel.as_posix()


def manifest():
    return ''.join(hashlib.sha256(path.read_bytes()).hexdigest() + '  ' + rel + '\n'
                   for path, rel in sources())


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--write', action='store_true')
    group.add_argument('--check', action='store_true')
    a = parser.parse_args()
    expected = manifest()
    if a.write:
        TARGET.parent.mkdir(parents=True,exist_ok=True)
        TARGET.write_text(expected)
        print(f'Wrote {TARGET.relative_to(ROOT)} ({expected.count(chr(10))} files)')
        return 0
    if not TARGET.exists():
        print('Missing manifests/SOURCE.sha256')
        return 1
    if TARGET.read_text() != expected:
        old={line.partition('  ')[2]:line.partition('  ')[0] for line in TARGET.read_text().splitlines() if '  ' in line}
        new={line.partition('  ')[2]:line.partition('  ')[0] for line in expected.splitlines() if '  ' in line}
        print('Manifest out of date:')
        for path in sorted(set(old)|set(new)):
            if old.get(path)!=new.get(path):
                print('  '+ ('added' if path not in old else 'removed' if path not in new else 'changed') + '  '+path)
        return 1
    print(f'Source manifest verified: {len(expected.splitlines())} files')
    return 0


if __name__=='__main__':
    sys.exit(main())
