"""Local-only files some tests compare against.

They are git-ignored (saved experiment references under output/, the Basketball Index captures and injury evidence under
data/, the start-screen film), so a fresh worktree, a clone or an Azure copy of a worktree doesn't have them. A test
that needs one skips and names the missing file; where the files exist it runs unchanged.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
# Only the main checkout has a .git directory: a linked worktree has a .git file and an Azure copy has neither.
MAIN_CHECKOUT = (ROOT / ".git").is_dir()


def needs_local(*paths):
    """Skip a test (or class) unless every one of these repo-relative files or folders exists."""
    missing = [path for path in paths if not (ROOT / path).exists()]
    return unittest.skipIf(missing, "local-only file not in this checkout: " + ", ".join(missing))


def needs_any_local(*paths):
    """Skip a test (or class) unless at least one of these repo-relative files exists."""
    return unittest.skipIf(not any((ROOT / path).exists() for path in paths),
                           "local-only file not in this checkout (none of): " + ", ".join(paths))
