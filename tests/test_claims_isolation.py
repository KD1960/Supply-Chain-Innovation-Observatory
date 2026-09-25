"""The weekly run must never be able to reach a model call.

Spec §3 item 1: the quarterly extraction calls the API; the weekly path does
not. Enforced as an absence test over the import statements of every module
in the package, the same shape as the scoring-boundary guard in the sibling
SCDAI project: a presence test on a flag can be satisfied by importing
correctly and never using it, an absence test cannot.
"""

import ast
from pathlib import Path

from observatory import config

PACKAGE = config.ROOT / "observatory"
CLAIMS = PACKAGE / "claims"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.add(node.module)
            # `from . import claims` has no module, only names; record those
            # too, or a relative package import walks straight past the guard.
            names.update(alias.name for alias in node.names)
    return names


def _package_modules():
    return [p for p in PACKAGE.rglob("*.py") if CLAIMS not in p.parents]


def test_no_module_outside_claims_imports_anthropic():
    offenders = [p for p in _package_modules()
                 if any(name == "anthropic" or name.startswith("anthropic.")
                        for name in _imports(p))]
    assert offenders == [], f"anthropic imported outside observatory/claims: {offenders}"


def test_no_module_outside_claims_imports_the_claims_package():
    offenders = [p for p in _package_modules()
                 if any("claims" in name.split(".") for name in _imports(p))]
    assert offenders == [], f"observatory.claims imported by the weekly path: {offenders}"


def test_claims_package_exists():
    assert (CLAIMS / "__init__.py").exists()


def test_trl_package_never_imports_claims_or_anthropic():
    trl = PACKAGE / "trl"
    offenders = [p for p in trl.rglob("*.py")
                 if any(n == "anthropic" or "claims" in n.split(".") for n in _imports(p))]
    assert offenders == []
