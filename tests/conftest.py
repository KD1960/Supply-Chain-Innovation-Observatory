"""Test isolation from the owner's own working directories.

`config.MANUAL_DIR` is a real folder on a real machine that a person drops
export files into. A test that reads it is testing whatever happened to be
saved there that morning: dropping one Lens export in broke four unrelated
rebuild tests, because the export had no sidecar yet and the importer --
correctly -- refused it.

Every test therefore gets an empty manual directory unless it asks for a
different one explicitly.
"""

import pytest

from observatory import config


@pytest.fixture(autouse=True)
def isolated_manual_dir(tmp_path, monkeypatch):
    empty = tmp_path / "manual"
    empty.mkdir()
    monkeypatch.setattr(config, "MANUAL_DIR", empty)
    return empty
