"""These tests protect the two rules the whole design rests on."""

import ast
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent.parent / "observatory"
BANNED_AT_RUNTIME = {"anthropic", "openai", "observatory.lexicon"}
ENTRY_POINT = "run"


def _imports(path: Path) -> set[str]:
    """Module names imported by one file.

    Relative imports matter here: `from . import config` and `from .. import http`
    both arrive with node.module set to None, and missing them would let the
    guardrail walk stop at run.py and pass vacuously.
    """
    tree = ast.parse(path.read_text())
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                found.add(node.module)
                found.update(f"{node.module}.{alias.name}" for alias in node.names)
            else:
                found.update(alias.name for alias in node.names)
    return found


def _reachable_modules(entry: str) -> set[str]:
    seen: set[str] = set()
    queue = [entry]
    while queue:
        name = queue.pop()
        if name in seen:
            continue
        seen.add(name)
        path = PACKAGE / f"{name.replace('.', '/')}.py"
        if not path.exists():
            continue
        for imported in _imports(path):
            local = imported.lstrip(".")
            if (PACKAGE / f"{local.replace('.', '/')}.py").exists():
                queue.append(local)
    return seen


def test_the_module_walk_actually_reaches_the_pipeline():
    """Without this, a broken walk would make the guardrail below pass vacuously."""
    reachable = _reachable_modules(ENTRY_POINT)
    assert {"config", "store", "matcher", "metrics", "normalize", "render",
            "collectors.arxiv"} <= reachable


def test_the_weekly_run_never_imports_a_model_client():
    for module in _reachable_modules(ENTRY_POINT):
        path = PACKAGE / f"{module.replace('.', '/')}.py"
        if not path.exists():
            continue
        offenders = _imports(path) & BANNED_AT_RUNTIME
        assert not offenders, f"{module} imports {offenders} — the weekly run must stay deterministic"


def test_no_module_in_the_package_imports_pandas_or_numpy():
    for path in PACKAGE.rglob("*.py"):
        imported = _imports(path)
        assert "pandas" not in imported and "numpy" not in imported, path
