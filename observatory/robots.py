"""robots.txt as RFC 9309 reads it. Pure: parsing and matching, no fetching.

urllib.robotparser, which this replaces, let an empty `Disallow:` line allow a
whole group, used only the first of several `User-agent: *` groups, and let the
first matching rule win instead of the longest (probe 3, 2026-09-29).

Crawl-delay is not in RFC 9309; it is read because sites still set it.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from urllib.parse import quote, urlsplit

# RFC 9309 2.2.1: a product token is letters, "_" and "-". A user-agent line's
# value is cut to its leading token, so "WordPress/6.0.5" names "wordpress";
# only a bare "*" is the wildcard, so "*bot" names nobody.
_TOKEN = re.compile(r"[A-Za-z_-]+")
_LINES = re.compile(r"\r\n|\r|\n")
_PERCENT = re.compile(r"%[0-9a-fA-F]{2}")
_UNRESERVED = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~")


@dataclass(frozen=True)
class Rule:
    allow: bool
    pattern: str        # normalised: see _normalise

    def matches(self, path: str) -> bool:
        """Linear: each piece between stars is placed leftmost after the last.
        A `.*` regex backtracks exponentially in the number of stars, and
        robots.txt is third-party input. Only a trailing `$` anchors."""
        body, anchored = (self.pattern[:-1], True) if self.pattern.endswith("$") else (self.pattern, False)
        first, *rest = body.split("*")
        if not path.startswith(first):
            return False
        pos = len(first)
        if not rest:
            return not anchored or pos == len(path)
        for piece in rest[:-1]:
            found = path.find(piece, pos)
            if found < 0:
                return False
            pos = found + len(piece)
        last = rest[-1]
        if anchored:
            return len(path) - len(last) >= pos and path.endswith(last)
        return path.find(last, pos) >= 0


@dataclass
class Group:
    agents: list[str] = field(default_factory=list)
    rules: list[Rule] = field(default_factory=list)
    delays: list[float] = field(default_factory=list)


def _unescape_unreserved(m: re.Match) -> str:
    char = chr(int(m[0][1:], 16))
    return char if char in _UNRESERVED else m[0].upper()


def _normalise(s: str) -> str:
    """Percent-encode what is not ASCII, decode escapes of unreserved
    characters and upper-case the rest, so "%7ejoe" and "~joe", "%3c" and
    "%3C", and "é" and "%C3%A9" compare equal while "%2F" stays apart from
    "/" (RFC 9309 2.2.2)."""
    s = quote(s, safe="".join(chr(c) for c in range(33, 127)))
    return _PERCENT.sub(_unescape_unreserved, s)


def _product_token(agent: str) -> str:
    return re.split(r"[/ ]", agent.strip(), maxsplit=1)[0].lower()


@dataclass(frozen=True)
class Robots:
    groups: tuple[Group, ...] = ()

    @classmethod
    def allow_all(cls) -> Robots:
        return cls(())

    @classmethod
    def disallow_all(cls) -> Robots:
        return cls((Group(["*"], [Rule(False, "/")]),))

    def _groups_for(self, agent: str) -> list[Group]:
        token = _product_token(agent)
        named = [g for g in self.groups if token in g.agents]
        return named or [g for g in self.groups if "*" in g.agents]

    def rules_for(self, agent: str) -> list[Rule]:
        return [r for g in self._groups_for(agent) for r in g.rules]

    def allows(self, agent: str, url_or_path: str) -> bool:
        parts = urlsplit(url_or_path)
        path = parts.path or "/"
        if path == "/robots.txt":
            return True
        path = _normalise(path + ("?" + parts.query if parts.query else ""))
        best: Rule | None = None
        for rule in self.rules_for(agent):
            if not rule.matches(path):
                continue
            if (best is None or len(rule.pattern) > len(best.pattern)
                    or (len(rule.pattern) == len(best.pattern) and rule.allow)):
                best = rule
        return best is None or best.allow

    def crawl_delay(self, agent: str) -> float | None:
        delays = [d for g in self._groups_for(agent) for d in g.delays]
        return max(delays) if delays else None


def parse(text: str) -> Robots:
    """Consecutive User-agent lines share a group; a User-agent line after a
    rule starts a new one. Unknown fields and rules before any User-agent are
    ignored; an empty Allow or Disallow is no rule."""
    groups: list[Group] = []
    current: Group | None = None
    in_rules = False
    for line in _LINES.split(text.lstrip("﻿")):
        name, sep, value = line.split("#", 1)[0].partition(":")
        if not sep:
            continue
        name, value = name.strip().lower(), value.strip()
        if name == "user-agent":
            if current is None or in_rules:
                current, in_rules = Group(), False
                groups.append(current)
            m = _TOKEN.match(value)
            token = "*" if value == "*" else m[0].lower() if m else None
            if token:
                current.agents.append(token)
        elif name in ("allow", "disallow", "crawl-delay") and current is not None:
            in_rules = True
            if name == "crawl-delay":
                try:
                    delay = float(value)
                except ValueError:
                    continue
                if math.isfinite(delay) and delay >= 0:
                    current.delays.append(delay)
            elif value:
                current.rules.append(Rule(name == "allow", _normalise(value)))
    return Robots(tuple(groups))
