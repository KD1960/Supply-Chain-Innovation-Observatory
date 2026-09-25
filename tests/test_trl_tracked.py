from pathlib import Path
from observatory.trl import tracked

FIXTURE = Path(__file__).parent / "fixtures" / "trl" / "sort-sheet.xlsx"


def test_tracked_ids_are_the_pre_practice_rows_in_sheet_order():
    assert tracked.tracked_ids(FIXTURE) == ("delivery_drones", "piece_picking", "additive_spares")


def test_tracked_ids_reads_the_real_sheet_and_finds_twenty_four():
    ids = tracked.tracked_ids()
    assert len(ids) == 24
    assert "erp" not in ids and "delivery_drones" in ids
