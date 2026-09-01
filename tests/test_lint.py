"""The linter, run as a test.

A pre-commit hook lives in one clone and yields to `--no-verify`. Running the
same check here means the gate travels with the repository and fires wherever
the suite runs -- including the GitHub Action, which is the half that cannot be
skipped.

What this is for, from the process review: a shipped `NameError`
(`discover.py` called `_already_covered`, defined nowhere, so any qualifying
term raised); an assertion that could not fail, because `challenge if False
else [...]` parses as a conditional expression and Python always took the
`orelse` branch; and unused imports. All three are pyflakes findings and cost
nothing to catch.
"""

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _ruff(*args):
    return subprocess.run([sys.executable, "-m", "ruff", *args],
                          cwd=ROOT, capture_output=True, text=True)


ruff_missing = pytest.mark.skipif(
    _ruff("--version").returncode != 0,
    reason="ruff is not installed for this interpreter",
)


@ruff_missing
def test_the_tree_is_clean():
    result = _ruff("check", ".")
    assert result.returncode == 0, result.stdout + result.stderr


@ruff_missing
def test_the_linter_catches_an_undefined_name(tmp_path):
    """The gate verified by what it rejects, not by the fact that it ran.

    A check that only ever passes is indistinguishable from a check that never
    looks -- which is how this project shipped a guard, documented it, and left
    it unconnected five separate times.
    """
    probe = tmp_path / "probe.py"
    probe.write_text("def f():\n    return name_that_does_not_exist\n")
    result = _ruff("check", str(probe), "--isolated", "--select", "E4,E7,E9,F")
    assert result.returncode != 0
    assert "F821" in result.stdout
