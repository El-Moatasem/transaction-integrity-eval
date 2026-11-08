#!/usr/bin/env python3
"""Repeat local grader controls in isolated workspaces to spot flaky tests.

This is NOT a substitute for running Harbor/Docker or frontier AI agent trials.
"""
import argparse
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from run_eval import grade_code,select


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--rounds',type=int,default=3)
    ap.add_argument('--tasks',nargs='+',default=['T01','T02','T10'])
    args=ap.parse_args()
    if not 1 <= args.rounds <= 30:
        ap.error('--rounds must be between 1 and 30')
    failures=[]
    for tid in args.tasks:
        task=select(tid)
        for i in range(1,args.rounds+1):
            for label,rel,expected in [
                ('reference','solution/service.py',True),
                ('starter','environment/service.py',False),
                ('wrong_fix','mutants/service.py',False),
            ]:
                result=grade_code(task,task/rel,timeout=35)
                ok=result['exit_code']==(0 if expected else 1)
                print(f"{tid} round={i} {label}: {'PASS' if ok else 'FAIL'}",flush=True)
                if not ok:failures.append((tid,i,label,result['log'][-900:]))
    if failures:
        for f in failures:print('UNEXPECTED CONTROL',f)
        return 1
    print(f'Repeatability: all {len(args.tasks)*args.rounds*3} expected outcomes confirmed')
    return 0


if __name__=='__main__':
    sys.exit(main())
