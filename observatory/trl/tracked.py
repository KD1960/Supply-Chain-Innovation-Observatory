# observatory/trl/tracked.py
"""The tracked set is the owner's ruling on the sort sheet (spec C6)."""

from __future__ import annotations

from pathlib import Path

from openpyxl import load_workbook

from .. import config

SHEET_PATH = config.ROOT / "docs" / "audit" / "tech-practice-sort-2026-09-23.xlsx"


def tracked_ids(sheet_path: Path | None = None) -> tuple[str, ...]:
    ws = load_workbook(sheet_path or SHEET_PATH, read_only=True)["Sort"]
    rows = ws.iter_rows(values_only=True)
    header = [str(h).strip() for h in next(rows)]
    id_col, call_col = header.index("id"), header.index("assistant call")
    own_col = header.index("Kevin: your call")
    out = []
    for row in rows:
        if row[id_col] is None:
            continue
        call = str(row[own_col] or row[call_col] or "").strip().lower()
        if call.startswith("pre-practice"):
            out.append(str(row[id_col]))
    return tuple(out)
