#!/usr/bin/env python3
"""Single source of truth for repository-only, non-submission artifacts.

Historical files may stay in a Git checkout without being advertised as active
benchmark contracts or packaged in the evaluation ZIP.  This policy NEVER
removes anything from disk.
"""
from pathlib import Path


LEGACY_ROOT_FILES = frozenset({'manifest.sha256', 'task_catalog.json'})
LEGACY_DOC_FILES = frozenset({'docs/candidate_sha256sums.txt'})


def is_git_admin_document(rel: Path) -> bool:
    """Exclude old Git-flow / PR drafts, including docs/PR_TEMPLATES/*.md."""
    rel = Path(rel)
    components = [part.lower().replace('-', '_') for part in rel.parts]
    if 'pr_templates' in components:
        return True
    filename = components[-1] if components else ''
    markers = ('git_flow', 'pr_to_', 'pr_descriptions', 'pr_description',
               'pull_request_template', 'branch_and_commits')
    return any(marker in filename for marker in markers)


def is_repository_only(rel: Path) -> bool:
    """Keep these in the local repository but omit from source manifest/ZIP."""
    rel = Path(rel)
    normalized = rel.as_posix().lower()
    if normalized in LEGACY_ROOT_FILES or normalized in LEGACY_DOC_FILES:
        return True
    if is_git_admin_document(rel):
        return True
    components = rel.parts
    if (len(components) == 3 and components[0] == 'tasks'
            and components[1].startswith('T') and components[2] == 'metadata.json'):
        return True
    return False
