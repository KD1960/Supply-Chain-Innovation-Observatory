"""Paths, environment, and ISO-week arithmetic.

Every week in this system is an ISO week string like "2026-W33". Weeks run
Monday through Sunday. All date maths goes through this module so that week
boundaries are defined in exactly one place.
"""

from __future__ import annotations

import datetime as dt
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
# Hand-made exports from licensed databases. Never published: see manual.py.
MANUAL_DIR = DATA_DIR / "manual"
OUTPUT_DIR = ROOT / "output"
DB_PATH = DATA_DIR / "observatory.db"
WATCHLIST_PATH = ROOT / "watchlist.yaml"
RUN_LOG_PATH = DATA_DIR / "run_log.jsonl"

MIN_HISTORY_WEEKS = 12
TRAILING_WEEKS = 52

# Every collector reaches this far back beyond the week it is processing, so a
# document indexed after last week's run is still caught. Safe because each
# observation is keyed by the document's own date and deduplicated on
# (source, doc_id, tech_id).
LOOKBACK_DAYS = 7


def iso_week(d: dt.date) -> str:
    year, week, _ = d.isocalendar()
    return f"{year}-W{week:02d}"


def week_bounds(week: str) -> tuple[dt.date, dt.date]:
    year_part, week_part = week.split("-W")
    monday = dt.date.fromisocalendar(int(year_part), int(week_part), 1)
    return monday, monday + dt.timedelta(days=6)


def week_offset(week: str, delta: int) -> str:
    monday, _ = week_bounds(week)
    return iso_week(monday + dt.timedelta(weeks=delta))


def week_range(start: str, end: str) -> list[str]:
    weeks = [start]
    while weeks[-1] != end:
        weeks.append(week_offset(weeks[-1], 1))
        if len(weeks) > 5000:
            raise ValueError(f"week_range({start!r}, {end!r}) did not terminate")
    return weeks


def trailing_weeks(week: str, count: int) -> list[str]:
    """The `count` weeks ending at `week`, oldest first."""
    return week_range(week_offset(week, -(count - 1)), week)


def current_week(today: dt.date | None = None) -> str:
    return iso_week(today or dt.date.today())


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(
            f"Missing required environment variable {name}. "
            f"Copy .env.example to .env and fill it in."
        )
    return value


def user_agent() -> str:
    return f"SupplyChainObservatory/1.0 ({require_env('SEC_CONTACT_EMAIL')})"


def load_dotenv(path: Path | None = None) -> None:
    """Minimal .env loader. Existing environment variables always win."""
    env_path = path or (ROOT / ".env")
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())
