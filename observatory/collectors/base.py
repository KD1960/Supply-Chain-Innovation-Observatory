"""Shared collector contract.

Fetching and parsing are deliberately separate. `fetch_raw` touches the network
and yields untouched response bodies; `parse` is a pure function from body text
to documents. Tests only ever exercise `parse`, against saved fixtures.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from .. import config


@dataclass(frozen=True)
class Document:
    doc_id: str
    date: str | None
    title: str | None
    text: str | None
    url: str | None
    entity: str | None = None
    entity_id: str | None = None
    amount: float | None = None
    lat: float | None = None
    lon: float | None = None


@dataclass(frozen=True)
class RawPage:
    url: str
    status: int
    text: str
    extension: str = "json"


class BaseCollector:
    name: str = "base"
    rate_limit_seconds: float = 1.0

    def fetch_raw(self, session, week: str) -> Iterator[RawPage]:
        raise NotImplementedError(f"{type(self).__name__} must implement fetch_raw")

    def parse(self, text: str) -> list[Document]:
        raise NotImplementedError(f"{type(self).__name__} must implement parse")


def raw_dir(source: str, week: str) -> Path:
    return config.RAW_DIR / week / source


def write_raw(source: str, week: str, index: int, page: RawPage) -> Path:
    directory = raw_dir(source, week)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{index:03d}.{page.extension}"
    path.write_text(page.text)
    return path


def read_raw(source: str, week: str) -> Iterator[tuple[Path, str]]:
    directory = raw_dir(source, week)
    if not directory.exists():
        return
    for path in sorted(directory.iterdir()):
        if path.is_file():
            yield path, path.read_text()
