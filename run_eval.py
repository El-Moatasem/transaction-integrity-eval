#!/usr/bin/env python3
"""Offline, behavior-based validation and isolated workspace grading.

Never mount solution/ or tests/ into an agent's working directory.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parent
TASK_ROOT=ROOT/'tasks'

def tasks():
    return sorted(p for p in TASK_ROOT.iterdir() if p.is_dir() and (p/'instruction.md').is_file())

def select(id):
    found=[p for p in tasks() if p.name.startswith(id+'_') or p.name==id]
    if len(found)!=1:raise SystemExit(f'Unknown/ambiguous task {id}. Valid: '+', '.join(x.name[:3] for x in tasks()))
    return found[0]

def grade_code(task, code, timeout=60):
    """Run tests in a fresh directory, inaccessible to the code under test before grading."""
    with tempfile.TemporaryDirectory(prefix='txn-grade-') as tmp:
        ws=Path(tmp)
        shutil.copy2(code,ws/'service.py')
        shutil.copytree(task/'tests',ws/'tests')
        e=os.environ.copy();e['PYTHONPATH']=str(ws);e['PYTHONDONTWRITEBYTECODE']='1';e['PYTEST_DISABLE_PLUGIN_AUTOLOAD']='1'
        try:
            proc=subprocess.run([sys.executable,'-m','pytest','-q','-p','no:cacheprovider','tests/test_service.py'],cwd=ws,env=e,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=timeout)
            return {'passed':proc.returncode==0,'exit_code':proc.returncode,'log':proc.stdout[-16000:]}
        except subprocess.TimeoutExpired:
            return {'passed':False,'exit_code':124,'log':f'Timed out after {timeout} seconds'}

def _validate_one(payload):
    t,timeout=payload
    runs={label:grade_code(t,t/path,timeout) for label,path in [
        ('reference','solution/service.py'),('baseline','environment/service.py'),('wrong_fix','mutants/service.py')]}
    ok=runs['reference']['passed'] and not runs['baseline']['passed'] and not runs['wrong_fix']['passed']
    return {'task':t.name,'controls':runs,'valid':ok}

def validate(args):
    from concurrent.futures import ThreadPoolExecutor
    selected=[select(args.task)] if args.task else tasks()
    report={'timestamp_utc':datetime.now(timezone.utc).isoformat(),'tasks':[]}
    with ThreadPoolExecutor(max_workers=min(4,len(selected))) as pool:
        for outcome in pool.map(_validate_one,[(t,args.timeout) for t in selected]):
            runs=outcome['controls'];ok=outcome['valid']
            report['tasks'].append(outcome)
            print(f"{outcome['task'][:3]} {'PASS' if ok else 'FAIL'} | golden={'pass' if runs['reference']['passed'] else 'FAIL'} baseline={'pass' if runs['baseline']['passed'] else 'fail'} wrong_fix={'pass' if runs['wrong_fix']['passed'] else 'fail'}",flush=True)
            if not ok:
                for label,run in runs.items():
                    if (label=='reference' and not run['passed']) or (label!='reference' and run['passed']):
                        print('  '+label+': '+run['log'][-2200:])
    out=ROOT/'results'/'validation.json';out.parent.mkdir(exist_ok=True);out.write_text(json.dumps(report,indent=2)+'\n')
    print(f'Wrote {out.relative_to(ROOT)}')
    return int(any(not x['valid'] for x in report['tasks']))

def prepare(args):
    t=select(args.task);p=Path(args.output).expanduser().resolve()
    if p.exists() and any(p.iterdir()):raise SystemExit('Output dir must be absent or empty (prevents trial contamination)')
    p.mkdir(parents=True,exist_ok=True)
    for source in (t/'environment').iterdir():
        if source.is_file() and source.name!='Dockerfile':shutil.copy2(source,p/source.name)
    shutil.copy2(t/'instruction.md',p/'INSTRUCTION.md')
    print(f'Prepared {p} for {t.name}. Agent sees only service.py and INSTRUCTION.md.')
    return 0

def grade(args):
    t=select(args.task);workspace=Path(args.workspace).expanduser().resolve();service=workspace/'service.py'
    if not service.is_file():raise SystemExit(f'No service.py at {service}')
    r=grade_code(t,service,args.timeout)
    record={'timestamp_utc':datetime.now(timezone.utc).isoformat(),'task':t.name,'workspace':str(workspace),'passed':r['passed'],'exit_code':r['exit_code'],'test_log':r['log']}
    out=Path(args.output).expanduser().resolve() if args.output else ROOT/'results'/f'{t.name[:3]}_last_grade.json'
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(record,indent=2)+'\n')
    print(f"{t.name[:3]}: {'PASS' if r['passed'] else 'FAIL'}\n{r['log']}\nSaved {out}")
    return 0 if r['passed'] else 1

def record(args):
    t=select(args.task);path=Path(args.transcript).expanduser().resolve()
    if not path.is_file() or not path.stat().st_size:raise SystemExit('Provide a nonempty actual trial transcript')
    grade_report=json.loads(Path(args.grade_json).expanduser().read_text())
    if grade_report.get('task')!=t.name:raise SystemExit('Grade report belongs to a different task')
    record={'task':t.name,'trial':args.trial,'model':args.model,'model_version':args.version,'settings':args.settings,'date_utc':datetime.now(timezone.utc).isoformat(),'passed':bool(grade_report['passed']),'runtime_seconds':args.runtime,'cost_usd':args.cost,'transcript_path':str(path),'grade_report':str(args.grade_json),'notes':args.notes}
    out=ROOT/'results'/'trials.jsonl';out.parent.mkdir(exist_ok=True)
    with out.open('a') as f:f.write(json.dumps(record)+'\n')
    print('Recorded one REAL completed trial; saved to results/trials.jsonl')
    return 0

def summary(args):
    path=ROOT/'results'/'trials.jsonl'
    if not path.exists():
        print('No real model trials recorded yet. Run prepare, grade, then record.');return 0
    from collections import defaultdict
    groups=defaultdict(list)
    for line in path.read_text().splitlines():
        if line.strip():
            row=json.loads(line);groups[(row['model'],row['task'])].append(row)
    output=[]
    for (model,task),rows in sorted(groups.items()):
        rows=sorted(rows,key=lambda x:x['trial'])
        passed=sum(bool(x['passed']) for x in rows)
        output.append({'model':model,'task':task,'n':len(rows),'pass_rate':passed/len(rows),'pass_all_observed':passed==len(rows),'pass_any_observed':passed>0})
    print(json.dumps(output,indent=2))
    # pass_any and pass_all are observed trial outcomes, not estimates of population pass@k / pass^k.
    return 0

def main():
    p=argparse.ArgumentParser(description='Transaction Integrity Eval runner')
    sub=p.add_subparsers(dest='command',required=True)
    v=sub.add_parser('validate',help='Check reference pass + baseline and wrong-fix failures')
    v.add_argument('--task');v.add_argument('--timeout',type=int,default=60);v.set_defaults(func=validate)
    pre=sub.add_parser('prepare',help='Create a clean agent-visible workspace')
    pre.add_argument('--task',required=True);pre.add_argument('--output',required=True);pre.set_defaults(func=prepare)
    g=sub.add_parser('grade',help='Test completed agent workspace using grader in a separate temp directory')
    g.add_argument('--task',required=True);g.add_argument('--workspace',required=True);g.add_argument('--output');g.add_argument('--timeout',type=int,default=60);g.set_defaults(func=grade)
    r=sub.add_parser('record',help='Append real trial metadata; never invent transcripts')
    for key in ('task','model','version','transcript','grade-json'):r.add_argument('--'+key,required=True)
    r.add_argument('--trial',type=int,required=True);r.add_argument('--settings',default='{}');r.add_argument('--runtime',type=float);r.add_argument('--cost',type=float);r.add_argument('--notes',default='');r.set_defaults(func=record)
    s=sub.add_parser('summary');s.set_defaults(func=summary)
    args=p.parse_args();sys.exit(args.func(args))
if __name__=='__main__':main()
