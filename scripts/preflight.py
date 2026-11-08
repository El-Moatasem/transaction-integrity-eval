#!/usr/bin/env python3
"""Structural and Harbor-shaped task controls; not a substitute for Docker trials."""
import pathlib
import sys
import tomllib
root = pathlib.Path(__file__).resolve().parents[1]
errors=[]
tasks = sorted(t for t in (root/'tasks').glob('T*') if t.is_dir())
if len(tasks) != 10:
    errors.append(f'expected 10 candidate tasks, found {len(tasks)}')
for t in tasks:
    try:
        conf=tomllib.loads((t/'task.toml').read_text())
    except Exception as exc:
        errors.append(f'{t.name}: invalid TOML: {exc}');continue
    if not conf.get('task',{}).get('name') or not conf['task'].get('keywords'):
        errors.append(f'{t.name}: missing task name or keywords')
    if conf.get('schema_version') != '1.4':
        errors.append(f'{t.name}: expected Harbor schema 1.4')
    if conf.get('environment',{}).get('network_mode') != 'no-network':
        errors.append(f'{t.name}: offline default network policy missing')
    for rel in ('environment/service.py','environment/Dockerfile','solution/service.py','solution/solve.sh',
                'tests/test_service.py','tests/test.sh','instruction.md'):
        if not (t/rel).is_file():
            errors.append(f'{t.name}: missing {rel}')
    for rel in ('solution/solve.sh','tests/test.sh'):
        if (t/rel).exists() and not (t/rel).stat().st_mode & 0o111:
            errors.append(f'{t.name}: {rel} not executable')
    df=(t/'environment/Dockerfile').read_text()
    if 'COPY service.py /app/service.py' not in df:
        errors.append(f'{t.name}: expected /app/service.py')
    if any(v in df for v in ('solution/','mutants/','tests/')):
        errors.append(f'{t.name}: Dockerfile leaks withheld data')
    if not (t/'tests/test.sh').exists() or '/logs/verifier/reward.txt' not in (t/'tests/test.sh').read_text():
        errors.append(f'{t.name}: missing Harbor reward output')
    if not (t/'solution/solve.sh').exists() or '/solution/service.py' not in (t/'solution/solve.sh').read_text():
        errors.append(f'{t.name}: missing oracle reference application')
    # Task README.md and metadata.json are retained for human review and
    # historical context. instruction.md / task.toml remain authoritative.
for rel in ('docs/ARCHITECTURE.md','docs/DOCUMENTATION.md',
            'evaluation/METHODOLOGY.md','evaluation/GRADER_VALIDATION.md',
            'evaluation/REPRODUCIBILITY.md','audit_variants/T02_atomic_conditional_update.py'):
    if not (root/rel).is_file():errors.append('missing '+rel)
# Historical root artifacts may remain in the checkout; the submission ZIP
# excludes them and publishes manifests/SOURCE.sha256 instead.
print(f'Preflight: {len(tasks)} tasks; {len(errors)} issues')
for err in errors:print('ERROR',err)
sys.exit(bool(errors))
