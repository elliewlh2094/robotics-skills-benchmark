"""Unit tests for harness.scope_check.

Pure function over (unified_diff, scope_files) → {out_of_scope_count,
out_of_scope_paths}. All inputs are hand-constructed strings; no subprocess.
"""
from __future__ import annotations

from harness.scope_check import compute_scope_violations


# ---------------------------------------------------------------------------
# Helpers — hand-built minimal unified diffs
# ---------------------------------------------------------------------------

def _new_file_diff(path: str, body: str = "hello\n") -> str:
    return (
        f"diff --git a/{path} b/{path}\n"
        f"new file mode 100644\n"
        f"index 0000000..abcdef0\n"
        f"--- /dev/null\n"
        f"+++ b/{path}\n"
        f"@@ -0,0 +1,1 @@\n"
        f"+{body}"
    )


def _modified_file_diff(path: str) -> str:
    return (
        f"diff --git a/{path} b/{path}\n"
        f"index abcdef0..1234567 100644\n"
        f"--- a/{path}\n"
        f"+++ b/{path}\n"
        f"@@ -1,1 +1,1 @@\n"
        f"-old\n"
        f"+new\n"
    )


def _deleted_file_diff(path: str) -> str:
    return (
        f"diff --git a/{path} b/{path}\n"
        f"deleted file mode 100644\n"
        f"index abcdef0..0000000\n"
        f"--- a/{path}\n"
        f"+++ /dev/null\n"
        f"@@ -1,1 +0,0 @@\n"
        f"-bye\n"
    )


def _renamed_file_diff(old: str, new: str) -> str:
    return (
        f"diff --git a/{old} b/{new}\n"
        f"similarity index 100%\n"
        f"rename from {old}\n"
        f"rename to {new}\n"
    )


# ---------------------------------------------------------------------------
# Empty / trivial cases
# ---------------------------------------------------------------------------

def test_empty_diff_yields_zero_violations():
    result = compute_scope_violations("", ["EXPERIMENT.md"])
    assert result == {"out_of_scope_count": 0, "out_of_scope_paths": []}


def test_only_in_scope_file_yields_zero_violations():
    diff = _new_file_diff("EXPERIMENT.md")
    result = compute_scope_violations(diff, ["EXPERIMENT.md"])
    assert result["out_of_scope_count"] == 0
    assert result["out_of_scope_paths"] == []


# ---------------------------------------------------------------------------
# Single-file violations
# ---------------------------------------------------------------------------

def test_single_out_of_scope_modification_is_flagged():
    diff = _modified_file_diff("src/main.py")
    result = compute_scope_violations(diff, ["EXPERIMENT.md"])
    assert result["out_of_scope_count"] == 1
    assert result["out_of_scope_paths"] == ["src/main.py"]


def test_new_file_outside_scope_is_flagged():
    diff = _new_file_diff("notes.txt")
    result = compute_scope_violations(diff, ["EXPERIMENT.md"])
    assert result == {"out_of_scope_count": 1, "out_of_scope_paths": ["notes.txt"]}


def test_deleted_file_outside_scope_is_flagged():
    """Deleting an out-of-scope file is still a scope violation — the agent
    touched something it wasn't allowed to."""
    diff = _deleted_file_diff("README.md")
    result = compute_scope_violations(diff, ["EXPERIMENT.md"])
    assert result == {"out_of_scope_count": 1, "out_of_scope_paths": ["README.md"]}


# ---------------------------------------------------------------------------
# Mixed diffs (the realistic case)
# ---------------------------------------------------------------------------

def test_mixed_diff_counts_only_out_of_scope_files():
    diff = (
        _new_file_diff("EXPERIMENT.md")
        + "\n"
        + _modified_file_diff("src/main.py")
        + "\n"
        + _new_file_diff("notes.txt")
    )
    result = compute_scope_violations(diff, ["EXPERIMENT.md"])
    assert result["out_of_scope_count"] == 2
    assert result["out_of_scope_paths"] == ["notes.txt", "src/main.py"]


# ---------------------------------------------------------------------------
# Glob patterns
# ---------------------------------------------------------------------------

def test_glob_pattern_matches_within_directory():
    diff = (
        _new_file_diff("docs/foo.md")
        + "\n"
        + _new_file_diff("src/foo.py")
    )
    result = compute_scope_violations(diff, ["docs/*"])
    assert result == {"out_of_scope_count": 1, "out_of_scope_paths": ["src/foo.py"]}


def test_multiple_scope_patterns_union():
    diff = (
        _new_file_diff("EXPERIMENT.md")
        + "\n"
        + _new_file_diff("ANALYSIS.md")
        + "\n"
        + _new_file_diff("src/main.py")
    )
    result = compute_scope_violations(diff, ["EXPERIMENT.md", "ANALYSIS.md"])
    assert result == {"out_of_scope_count": 1, "out_of_scope_paths": ["src/main.py"]}


# ---------------------------------------------------------------------------
# Renames touch two paths
# ---------------------------------------------------------------------------

def test_rename_inside_scope_is_not_a_violation():
    diff = _renamed_file_diff("EXPERIMENT.md", "EXPERIMENT.md.bak")
    # Renaming an in-scope file *out* of scope creates a new out-of-scope path.
    # The destination is out of scope; flag it. The source is in-scope, so OK.
    result = compute_scope_violations(diff, ["EXPERIMENT.md"])
    assert "EXPERIMENT.md.bak" in result["out_of_scope_paths"]
    assert "EXPERIMENT.md" not in result["out_of_scope_paths"]


def test_rename_with_both_endpoints_in_scope_is_clean():
    diff = _renamed_file_diff("EXPERIMENT.md", "EXPERIMENT_v2.md")
    result = compute_scope_violations(diff, ["EXPERIMENT*.md"])
    assert result == {"out_of_scope_count": 0, "out_of_scope_paths": []}


# ---------------------------------------------------------------------------
# Determinism: paths are sorted and deduplicated
# ---------------------------------------------------------------------------

def test_paths_are_sorted_and_unique():
    # Construct a diff where the same path appears twice (e.g., via both
    # `--- a/X` and `+++ b/X` style headers being parsed).
    diff = (
        _modified_file_diff("z.txt")
        + "\n"
        + _modified_file_diff("a.txt")
        + "\n"
        + _modified_file_diff("m.txt")
    )
    result = compute_scope_violations(diff, [])
    assert result["out_of_scope_paths"] == ["a.txt", "m.txt", "z.txt"]
    assert result["out_of_scope_count"] == 3


# ---------------------------------------------------------------------------
# Empty scope_files = everything is out of scope
# ---------------------------------------------------------------------------

def test_empty_scope_files_treats_all_changes_as_violations():
    diff = _new_file_diff("anything.txt")
    result = compute_scope_violations(diff, [])
    assert result == {"out_of_scope_count": 1, "out_of_scope_paths": ["anything.txt"]}
