"""The offline lexicon workflow — never imported by the weekly run.

The pipeline cannot judge whether "dark factory" is a supply chain technology
or a metal band. That judgement is the owner's, and this module's whole job is
to package the evidence so it can be made well: `prepare` writes a request, a
human answers it in a Claude session by writing a proposals file, and `check`
validates the result before the human merges it into watchlist.yaml by hand.

The pipeline never edits the watchlist. Spec §4 and §5.1 are explicit about
that, and it is why this module writes proposals rather than patterns.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from . import config, matcher, store

REQUEST_DIR = config.ROOT / "lexicon" / "requests"
PROPOSAL_DIR = config.ROOT / "lexicon" / "proposals"

INSTRUCTIONS = """\
## What to do with this

Read the candidates below, decide which are real supply chain or operations
technologies, and write a proposals file at `lexicon/proposals/{week}.yaml`.

For each term you want to promote, decide two things:

1. **The patterns.** What would a document actually say? Include spelling
   variants, common abbreviations, and vendor names. Add `exclude` patterns for
   the near-misses that would otherwise match.
2. **Whether it needs context.** If the term belongs to every field — "digital
   twin", "computer vision", "blockchain" — set `needs_context: true` and it
   will only count when the document also uses one of the context words listed
   above. If the term is self-scoping — "inland port", "cold chain" — leave it
   out.

Getting this wrong in the permissive direction is expensive: an earlier run
matched nine off-concept documents out of ten because patterns were broader
than their own names.

Write the file in this shape:

```yaml
technologies:
  - id: dark_factory
    name: Dark factories
    family: physical
    include:
      - "dark factor(y|ies)"
      - "lights[- ]out manufacturing"
    exclude: []
    needs_context: true
```

Then run `python -m observatory.lexicon check {week}` to validate it.
"""


def prepare(conn, week: str, watchlist, out_path: Path | None = None) -> Path:
    candidates = store.candidates_for_week(conn, week)
    lines = [
        f"# Lexicon request — week {week}",
        "",
        f"Lexicon version in use: {watchlist.version}",
        "",
        "## Context vocabulary",
        "",
        "A technology marked `needs_context` only counts when the document also",
        "uses one of these words:",
        "",
        "".join(f"- `{term}`\n" for term in watchlist.context) or "- (none defined)\n",
        "## Technologies already tracked",
        "",
        "Do not propose a duplicate of one of these; propose a pattern change instead.",
        "",
    ]
    for tech in watchlist.active:
        lines.append(f"- `{tech.id}` — {tech.name} ({tech.family})")
    lines += ["", "## Candidate terms", ""]

    if not candidates:
        lines.append("There are no candidate terms for this week.")
    else:
        stored_total = candidates[0]["total"]
        # A legacy row written before the `total` column existed carries NULL;
        # falling back to the row count -- what a reader can already see -- is
        # honest without crashing on the missing value.
        total = len(candidates) if stored_total is None else stored_total
        if total > len(candidates):
            lines.append(f"Showing the {len(candidates)} strongest of {total} that qualified.")
            lines.append("")
        for candidate in candidates:
            lines.append(
                f"### `{candidate['term']}` — {candidate['count']} this week, "
                f"baseline {candidate['baseline']:.1f}, {candidate['ratio']:.1f}× "
            )
            lines.append("")
            for title, url in candidate["examples"]:
                lines.append(f"- [{title}]({url})")
            lines.append("")

    lines += ["", INSTRUCTIONS.format(week=week)]

    target = Path(out_path) if out_path else REQUEST_DIR / f"{week}.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines))
    return target


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="observatory.lexicon")
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare_parser = subparsers.add_parser("prepare", help="write a lexicon request for a week")
    prepare_parser.add_argument("week")
    args = parser.parse_args(argv)

    config.load_dotenv()
    watchlist = matcher.load_watchlist()
    conn = store.connect()
    store.init_schema(conn)
    try:
        if args.command == "prepare":
            path = prepare(conn, args.week, watchlist)
            print(f"Wrote {path}")
            print("Open a Claude session and ask it to answer this request.")
            return 0
    finally:
        conn.close()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
