#!/usr/bin/env python3
"""Regression checks for non-destructive legacy-file preservation."""
from pathlib import Path
import unittest

from submission_policy import is_git_admin_document, is_repository_only


class RepositoryOnlyPolicyTests(unittest.TestCase):
    def test_files_to_preserve_and_package(self):
        for name in (
            'tasks/T01_capture-idempotency/README.md',
            'tasks/T02_refund-ceiling/instruction.md',
            'docs/ARCHITECTURE.md',
            'docs/DOCUMENTATION.md',
            'docs/APPLICATION_FLOW.md',
            'docs/alternative_solutions/T02_deferred_write_first_service.py',
            'audit_variants/T02_atomic_conditional_update.py',
        ):
            with self.subTest(path=name):
                self.assertFalse(is_repository_only(Path(name)))

    def test_preserved_but_omitted_from_submission(self):
        for name in (
            'MANIFEST.sha256',
            'task_catalog.json',
            'tasks/T01_capture-idempotency/metadata.json',
            'tasks/T10_inbox-outbox-atomicity/metadata.json',
            'docs/CANDIDATE_SHA256SUMS.txt',
            'docs/GIT_FLOW_AND_COMMITS.txt',
            'docs/PR_Descriptions.txt',
            'docs/PR_TEMPLATES/PR_01.md',
            'Transaction_Integrity_Eval_PR_to_Main.txt',
        ):
            with self.subTest(path=name):
                self.assertTrue(is_repository_only(Path(name)))

    def test_admin_doc_detection(self):
        self.assertTrue(is_git_admin_document(Path('docs/PR_TEMPLATES/PR_05.md')))
        self.assertFalse(is_git_admin_document(Path('docs/PROBLEMS.md')))


if __name__ == '__main__':
    unittest.main()
