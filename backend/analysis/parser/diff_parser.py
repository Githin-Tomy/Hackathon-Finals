"""
GitHub unified diff parser — extracts changed files and their content.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class DiffFile:
    """Represents one changed file in a PR diff."""
    filename: str
    status: str          # added | modified | removed | renamed
    additions: int = 0
    deletions: int = 0
    patch: str = ""      # raw unified diff patch
    content: str = ""    # full new file content (populated later via API)


def parse_diff_header(patch: str) -> Tuple[int, int]:
    """Return (additions, deletions) from a raw patch string."""
    additions = len([l for l in patch.splitlines() if l.startswith("+") and not l.startswith("+++")])
    deletions = len([l for l in patch.splitlines() if l.startswith("-") and not l.startswith("---")])
    return additions, deletions


def extract_changed_line_numbers(patch: str) -> List[int]:
    """
    Parse unified diff hunk headers to find which NEW line numbers were added.
    Returns sorted list of new-file line numbers that were changed.
    """
    changed_lines: List[int] = []
    current_new_line = 0
    hunk_re = re.compile(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")

    for line in patch.splitlines():
        m = hunk_re.match(line)
        if m:
            current_new_line = int(m.group(1))
            continue
        if line.startswith("+") and not line.startswith("+++"):
            changed_lines.append(current_new_line)
            current_new_line += 1
        elif line.startswith("-"):
            pass  # deleted line — don't advance new-file counter
        else:
            current_new_line += 1

    return sorted(set(changed_lines))


def build_diff_files(github_files: list) -> List[DiffFile]:
    """
    Convert PyGithub File objects into DiffFile objects.
    `github_files` is the list returned by pr.get_files().
    """
    result = []
    for f in github_files:
        patch = getattr(f, "patch", "") or ""
        additions, deletions = parse_diff_header(patch)
        result.append(DiffFile(
            filename=f.filename,
            status=f.status,
            additions=additions,
            deletions=deletions,
            patch=patch,
        ))
    return result
