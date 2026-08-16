import datetime as dt

import pytest

from observatory import config


def test_iso_week_formats_with_padded_week():
    assert config.iso_week(dt.date(2026, 8, 16)) == "2026-W33"
    assert config.iso_week(dt.date(2026, 1, 1)) == "2026-W01"


def test_week_bounds_returns_monday_through_sunday():
    start, end = config.week_bounds("2026-W33")
    assert start == dt.date(2026, 8, 10)
    assert end == dt.date(2026, 8, 16)
    assert start.weekday() == 0
    assert end.weekday() == 6


def test_week_offset_crosses_the_year_boundary():
    assert config.week_offset("2026-W01", -1) == "2025-W52"
    assert config.week_offset("2025-W52", 1) == "2026-W01"
    assert config.week_offset("2026-W33", -12) == "2026-W21"


def test_week_range_is_inclusive_and_ordered():
    weeks = config.week_range("2026-W31", "2026-W34")
    assert weeks == ["2026-W31", "2026-W32", "2026-W33", "2026-W34"]


def test_require_env_names_the_missing_variable(monkeypatch):
    monkeypatch.delenv("SEC_CONTACT_EMAIL", raising=False)
    with pytest.raises(RuntimeError) as excinfo:
        config.require_env("SEC_CONTACT_EMAIL")
    assert "SEC_CONTACT_EMAIL" in str(excinfo.value)


def test_user_agent_includes_contact_email(monkeypatch):
    monkeypatch.setenv("SEC_CONTACT_EMAIL", "someone@example.edu")
    assert "someone@example.edu" in config.user_agent()
