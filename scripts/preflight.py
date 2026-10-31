#!/usr/bin/env python3
"""Offline structural checks; NOT a replacement for `harbor run` on Docker."""
import pathlib, tomllib, sys
root=pathlib.Path(__file__).resolve().parent.parent
errors=[]
for t in sorted((root/'tasks').glob('T*')):
    if not t.is_dir(): continue
    try: meta=tomllib.loads((t/'task.toml').read_text())
    except Exception as exc: errors.append(f'{t.name}: invalid TOML: {exc}');continue
    if not meta.get('task',{}).get('name'):errors.append(f'{t.name}: task.name missing')
    if not meta.get('task',{}).get('keywords'):errors.append(f'{t.name}: keywords missing')
    for rel in ['environment/service.py','environment/Dockerfile','solution/service.py','solution/solve.sh','tests/test_service.py','tests/test.sh','instruction.md']:
        if not (t/rel).is_file():errors.append(f'{t.name}: missing {rel}')
    for rel in ['solution/solve.sh','tests/test.sh']:
        if not (t/rel).stat().st_mode & 0o111:errors.append(f'{t.name}: {rel} not executable')
    df=(t/'environment/Dockerfile').read_text()
    if 'COPY service.py /app/service.py' not in df: errors.append(f'{t.name}: expected /app/service.py')
    if any(needle in df for needle in ['solution/', 'mutants/', 'tests/']):errors.append(f'{t.name}: leaked withheld data in Dockerfile')
    sh=(t/'tests/test.sh').read_text()
    if '/logs/verifier/reward.txt' not in sh or '/tests/test_service.py' not in sh: errors.append(f'{t.name}: verifier paths missing')
    sol=(t/'solution/solve.sh').read_text()
    if '/solution/service.py' not in sol:errors.append(f'{t.name}: oracle copy missing')
print(f'Preflight: {len(list((root/"tasks").glob("T*")))} tasks, {len(errors)} issues')
for e in errors:print('ERROR',e)
sys.exit(bool(errors))
