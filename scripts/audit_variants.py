#!/usr/bin/env python3
"""Check behavioral grader fairness with known-good and known-bad variants.

These are local evidence controls, not a guarantee against all false results.

Every variant is generated in a temporary directory from the committed
reference; committed solutions are never edited. A rejection counts as mutation
detection ONLY when the grader exited 1 because of a failed test that maps to a
documented behavioral invariant (INVARIANTS below). Syntax/import errors,
grader timeouts, and race-probe scheduling failures (RACE_PROBE_INFRA) are
classified as INVALID, never as detection. When the failing test is a
concurrency test, the race probe must also report that the intended overlap
was exercised.

Writes results/mutation_audit.json. Exit status is nonzero when a known-good
variant is rejected, an established negative control is not behaviorally
rejected, or any variant produces an INVALID (non-behavioral) outcome.
Candidate negative controls that survive are reported, not forced to fail.
"""
import json
import os
from pathlib import Path
import re
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from run_eval import select, grade_code

BEGIN_LINE = re.compile(r"^[ \t]*conn\.execute\('BEGIN IMMEDIATE'\)[ \t]*\n", re.MULTILINE)

# failing test -> documented financial / transactional invariant
INVARIANTS = {
    'T01': {
        'test_exact_replay_and_conflict': 'one debit per idempotency key; key reuse with a different payload raises ValueError',
        'test_validation_and_atomicity': 'invalid input or insufficient funds raises ValueError with no changes',
        'test_injected_partial_write_failure_rolls_back': 'debit and receipt commit atomically',
        'test_competing_identical_capture_across_connections':
            'a concurrent identical capture returns the original receipt (or a lock-timeout '
            'OperationalError), never IntegrityError; exactly one debit and one receipt',
    },
    'T02': {
        'test_ceiling_replay_and_conflicts': 'sum of refunds never exceeds the capture; replay is idempotent',
        'test_invalid_refunds_leave_no_changes': 'invalid refunds leave the database unchanged',
        'test_injected_partial_write_failure_rolls_back': 'balance credit and refund receipt commit atomically',
        'test_competing_refunds_cannot_overrefund':
            'committed refunds for a capture never exceed the captured amount under concurrency; '
            'credited balance equals committed refunds',
    },
    'T03': {
        'test_balanced_exact_postings_and_replay': 'every transfer posts balanced debit/credit entries exactly once',
        'test_amount_and_currency_rules': 'invalid amounts or currencies are rejected',
        'test_conflicting_replay_does_not_modify_journal': 'a conflicting replay leaves the journal unchanged',
        'test_extra_zeroes_allowed': 'equivalent decimal spellings are accepted',
        'test_second_ledger_entry_failure_rolls_back_transfer': 'a transfer posts both journal entries or none',
    },
    'T10': {
        'test_apply_replay_and_pending': 'one balance change, inbox row and outbox event per event_id',
        'test_failure_in_outbox_rolls_back_everything': 'balance, inbox and outbox commit in one transaction',
        'test_invalid_event_rollback': 'invalid events leave no changes',
        'test_pending_sort_and_two_events': 'outbox payload reflects the committed balance',
        'test_competing_debits_preserve_balance_inbox_and_outbox':
            'concurrent debits never overdraw the account; every committed inbox row has exactly '
            'one outbox event carrying the committed balance',
    },
}
# T11-T13 are instruction-only ablations of T01/T02/T10: identical tests,
# references and wrong fixes, so they share the same invariant maps and variants.
ABLATIONS = {'T11': 'T01', 'T12': 'T02', 'T13': 'T10'}
for _ablation, _source in ABLATIONS.items():
    INVARIANTS[_ablation] = INVARIANTS[_source]
RACE_TASKS = ('T01', 'T02', 'T10', 'T11', 'T12', 'T13')
CONCURRENCY_TESTS = {'test_competing_identical_capture_across_connections',
                     'test_competing_refunds_cannot_overrefund',
                     'test_competing_debits_preserve_balance_inbox_and_outbox'}
INFRA_MARKERS = ('RACE_PROBE_INFRA', 'SyntaxError', 'IndentationError', 'ImportError',
                 'ModuleNotFoundError', 'NameError', 'errors during collection',
                 'Grading timed out', 'Grading infrastructure error', 'INTERNALERROR')

REPORT = []


def failed_tests(log):
    out = {}
    for m in re.finditer(r'^FAILED \S+::(\w+)(?: - (.*))?$', log, re.MULTILINE):
        out[m.group(1)] = (m.group(2) or '').strip()
    return out


def first_error_line(log, test):
    # pytest prints the failing test's traceback under a "____ test ____" banner.
    sect = re.search(r'_{3,} ' + re.escape(test) + r' _{3,}\n(.*?)(?=\n_{3,} |\n=+ )', log, re.DOTALL)
    body = sect.group(1) if sect else log
    lines = [l[1:].strip() for l in body.splitlines() if l.startswith('E ')]
    return lines[0] if lines else ''


def run_variant(tid, code, label, kind):
    """kind: 'good' | 'negative' (established) | 'candidate' (new negative control)."""
    with TemporaryDirectory(prefix='txn-race-report-') as rd:
        report = Path(rd) / 'race.jsonl'
        os.environ['RACE_PROBE_REPORT'] = str(report)
        try:
            result = grade_code(select(tid), code, timeout=55)
        finally:
            os.environ.pop('RACE_PROBE_REPORT', None)
        races = [json.loads(l) for l in report.read_text().splitlines()] if report.exists() else []
    log = result['log']
    race_exercised = any(r.get('a_paused') and r.get('b_started_while_a_paused') for r in races)
    entry = dict(task=tid, label=label, kind=kind, grader_exit=result['exit_code'],
                 race_runs=races, race_exercised=race_exercised, failures=[])
    infra = [m for m in INFRA_MARKERS if m in log]
    if result['exit_code'] not in (0, 1) or infra:
        entry['outcome'] = 'INVALID'
        entry['reason'] = f"non-behavioral grader result (exit={result['exit_code']}, markers={infra})"
    elif result['exit_code'] == 0:
        entry['outcome'] = 'ACCEPTED'
    else:
        fails = failed_tests(log)
        unmapped = [t for t in fails if t not in INVARIANTS.get(tid, {})]
        for test, summary in fails.items():
            entry['failures'].append(dict(
                test=test, assertion=first_error_line(log, test) or summary,
                invariant=INVARIANTS.get(tid, {}).get(test, 'UNMAPPED')))
        if not fails or unmapped:
            entry['outcome'] = 'INVALID'
            entry['reason'] = f'rejection not attributable to a documented invariant: {unmapped or "no FAILED line"}'
        elif all(t in CONCURRENCY_TESTS for t in fails) and not race_exercised:
            entry['outcome'] = 'INVALID'
            entry['reason'] = 'only concurrency tests failed but the race probe did not exercise the overlap'
        else:
            entry['outcome'] = 'REJECTED'
    if kind == 'good':
        entry['ok'] = entry['outcome'] == 'ACCEPTED'
    elif kind == 'negative':
        entry['ok'] = entry['outcome'] == 'REJECTED'
    else:  # candidate: survival is documented, only INVALID is an audit failure
        entry['ok'] = entry['outcome'] != 'INVALID'
    status = {'good': 'PASS' if entry['ok'] else 'FAIL',
              'negative': 'PASS' if entry['ok'] else 'FAIL',
              'candidate': {'REJECTED': 'DETECTED', 'ACCEPTED': 'SURVIVED (documented)',
                            'INVALID': 'FAIL'}[entry['outcome']]}[kind]
    print(f"{tid}: {label}: {status} (grader={entry['outcome'].lower()}, "
          f"race_exercised={race_exercised})", flush=True)
    for f in entry['failures']:
        print(f"    failed {f['test']}: {f['assertion'][:160]}\n      invariant: {f['invariant']}")
    if entry.get('reason'):
        print('    ' + entry['reason'])
    if not entry['ok']:
        print(log[-1600:])
    REPORT.append(entry)
    return entry['ok']


def check(tid, path, kind, label):
    return run_variant(tid, Path(path), label, kind)


def variant(tid, transform, kind, label):
    source = (select(tid) / 'solution/service.py').read_text()
    altered_source = transform(source)
    if altered_source is None or altered_source == source:
        print(f'{tid}: mutation anchor not found for {label}')
        REPORT.append(dict(task=tid, label=label, kind=kind, outcome='INVALID', ok=False,
                           reason='mutation anchor not found'))
        return False
    with TemporaryDirectory(prefix='txn-variant-') as d:
        altered = Path(d) / 'service.py'
        altered.write_text(altered_source)
        return run_variant(tid, altered, label, kind)


def replace(old, new):
    return lambda s: s.replace(old, new, 1) if old in s else None


def drop_begin(s):
    out, n = BEGIN_LINE.subn('', s, count=1)
    return out if n == 1 else None


def drop_begin_use_cursor(s):
    out = drop_begin(s)
    if out is None:
        return None
    # Route every SQL statement through a cursor; commit/rollback stay on conn.
    return out.replace('conn.execute(', 'conn.cursor().execute(')


def main():
    good = True
    for tid in ('T02', 'T12'):
        good &= check(tid, ROOT / 'audit_variants/T02_atomic_conditional_update.py', 'good',
                      'independent atomic conditional-update approach accepted')
    for tid in RACE_TASKS:
        good &= check(tid, select(tid) / 'solution/service.py', 'good', 'unmodified reference accepted')

    # A deferred BEGIN is not inherently incorrect. A SQLite lock timeout is
    # permitted by these contracts when changes roll back and a retry is safe.
    for tid in RACE_TASKS:
        good &= variant(tid, replace("conn.execute('BEGIN IMMEDIATE')", "conn.execute('BEGIN')"),
                        'good', 'valid deferred transaction accepted')

    # Candidate negative controls: delete the transaction start entirely
    # (Variant A), and additionally issue SQL through conn.cursor().execute()
    # (Variant B). Survival would be documented, not forced to fail.
    for tid in RACE_TASKS:
        good &= variant(tid, drop_begin, 'candidate',
                        'Variant A: BEGIN IMMEDIATE removed')
        good &= variant(tid, drop_begin_use_cursor, 'candidate',
                        'Variant B: BEGIN IMMEDIATE removed, SQL via conn.cursor().execute()')

    # Commit transfer before the second posting; second-entry failure leaves
    # a partial journal. It must be rejected by T03.
    good &= variant('T03', replace(
        "conn.execute('INSERT INTO entries VALUES(?,?,?,?,?)',(transfer_id,target,'credit',minor,currency))",
        "conn.commit()\n            conn.execute('INSERT INTO entries VALUES(?,?,?,?,?)',(transfer_id,target,'credit',minor,currency))"),
        'negative', 'partially committed journal rejected')

    # Commit balance + inbox before writing the durable outbox event. A trigger
    # blocking outbox insertion must then expose the partial state.
    for tid in ('T10', 'T13'):
        good &= variant(tid, replace(
            "conn.execute('INSERT INTO outbox VALUES(?,?,?,0)',(event_id,'account.changed',payload))",
            "conn.commit()\n            conn.execute('INSERT INTO outbox VALUES(?,?,?,0)',(event_id,'account.changed',payload))"),
            'negative', 'balance/inbox committed without outbox rejected')

    dest = ROOT / 'results' / 'mutation_audit.json'
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(REPORT, indent=2) + '\n')
    print(f'Wrote {dest.relative_to(ROOT)}')
    return 0 if good else 1


if __name__ == '__main__':
    sys.exit(main())
