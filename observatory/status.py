"""STATUS §2, derived rather than maintained.

The handover table is the one document the owner can fully audit without
reading code, because every number in it is in his domain -- and it was the
document that drifted. The process review found seven headline figures wrong, a
by-source row summing to 2,711 against its own stated 2,130, and two adjacent
rows contradicting each other. It had been asserted verified and nothing
re-verified it.

Four of its rows come from the database and the watchlist, so they are computed
here and checked by `tests/test_status_table.py`. The rest -- precision, the
deliverable, the weekly page, the repository -- are claims about the project
rather than counts of it, and are left alone: generating prose nobody checks
would trade a stale number for a stale sentence.
"""

from __future__ import annotations

import re
import subprocess
import sys

from . import config

# Rows this module owns. Anything else in the table is left exactly as written.
DERIVED = ("Tests", "Lexicon", "Observations", "Sources")
TABLE_HEADING = "## 2. Current state"
NEXT_HEADING = "## 3."


def derived_rows(conn, watchlist, tests: int | None = None) -> dict[str, str]:
    """The rows that are counts, as they should read.

    `tests` is passed in rather than measured here: counting them means running
    pytest, and a module imported *by* pytest must not shell out to it.
    """
    counts = conn.execute(
        "SELECT source, COUNT(*) n FROM observations GROUP BY source ORDER BY n DESC, source"
    ).fetchall()
    total = conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
    # The families the sources actually populate, not the size of the model's
    # family list. If a source stopped producing, the claim should shrink with
    # it rather than describe a table that no longer has rows in it.
    from . import quarter
    families = len({quarter.family_of(row["source"]) for row in counts})
    rows = {
        "Lexicon": f"version **{watchlist.version}**, "
                   f"{len(watchlist.active)} active technologies",
        "Observations": f"**{total:,}**",
        "Sources": f"{len(counts)}, across {families} evidence families",
        "By source": ", ".join(f"{row['source']} {row['n']}" for row in counts),
    }
    if tests is not None:
        rows["Tests"] = f"**{tests} passing**"
    return rows


def written_rows(text: str | None = None) -> dict[str, str]:
    """The table as it currently stands in STATUS.md, label to value."""
    text = text if text is not None else _status_path().read_text()
    table = text[text.index(TABLE_HEADING):text.index(NEXT_HEADING)]
    found = {}
    for line in table.splitlines():
        match = re.match(r"\|\s*([^|]+?)\s*\|\s*(.*?)\s*\|\s*$", line)
        if match and match.group(1) not in ("", "---"):
            found[match.group(1)] = match.group(2)
    return found


def parse_by_source(value: str) -> dict[str, int]:
    return {name: int(count) for name, count in
            re.findall(r"([A-Za-z_]+)\s+(\d+)", value)}


def render(conn, watchlist, tests: int | None = None, text: str | None = None) -> str:
    """STATUS.md with its derived rows rewritten and everything else untouched."""
    text = text if text is not None else _status_path().read_text()
    rows = derived_rows(conn, watchlist, tests)
    start, end = text.index(TABLE_HEADING), text.index(NEXT_HEADING)
    table = text[start:end]
    for label, value in rows.items():
        pattern = rf"(\|\s*{re.escape(label)}\s*\|\s*)(.*?)(\s*\|)"
        if re.search(pattern, table):
            table = re.sub(pattern, lambda m: m.group(1) + value + m.group(3), table, count=1)
    return text[:start] + table + text[end:]


def write(conn, watchlist, tests: int | None = None) -> list[str]:
    """Rewrite the table in place. Returns the labels that changed."""
    path = _status_path()
    before = path.read_text()
    after = render(conn, watchlist, tests, before)
    changed = [label for label, value in written_rows(before).items()
               if written_rows(after).get(label) != value]
    if after != before:
        path.write_text(after)
    return changed


def count_tests() -> int | None:
    """How many tests the suite collects, or None if it cannot be asked.

    Only ever called from the command line, never from inside a test run.
    """
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--collect-only"],
        cwd=config.ROOT, capture_output=True, text=True,
    )
    match = re.search(r"(\d+) tests? collected", result.stdout)
    return int(match.group(1)) if match else None


def _status_path():
    return config.ROOT / "STATUS.md"
