"""The quarterly TRL claim extraction. Offline, explicit, pinned model, cached
system prompt, refusals recorded. The only sanctioned model call (spec C5).

  python -m observatory.claims.extract_trl --period 2026-Q3 [--model claude-sonnet-5]
         [--limit 5] [--max-dollars 20] [--tech delivery_drones]

Writes data/trl/claims-<period>.jsonl (one row per claim, or per refusal or
error), data/trl/raw-<period>-<model>/<source>-<doc_id hash>.json (the rows
for each document) and data/trl/usage-<period>-<model>.json (token totals).

The claims file is opened in APPEND mode: a re-run of the same period adds
rows to what is there. To re-read a period from scratch, delete
data/trl/claims-<period>.jsonl first; the command warns when it exists.

`anthropic` is imported inside main() only, so this module (and its tests)
import without the package installed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time

from .. import config, matcher, quarter, store
from ..trl import documents, schema, tracked
from . import trl_prompt, verify

# Input $/MTok for the pre-run estimate. Deliberately at or above list price,
# so the ceiling errs on the side of refusing.
PRICE_PER_MTOK_INPUT = {"claude-opus-5-5": 5.00, "claude-sonnet-5": 3.00}
CHARS_PER_TOKEN = 3.5
TRL_DIR = config.DATA_DIR / "trl"
USAGE_FIELDS = ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")


def estimate_dollars(docs, model: str) -> float:
    chars = sum(len(d.text) for d in docs) + 4000 * len(docs)
    return chars / CHARS_PER_TOKEN / 1e6 * PRICE_PER_MTOK_INPUT[model]


def _read(client, model: str, system: str, user: str, fmt: dict):
    with client.messages.stream(
        model=model, max_tokens=8000,
        system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user}],
        output_config={"effort": "medium", "format": {"type": "json_schema", "schema": fmt}},
    ) as stream:
        return stream.get_final_message()


def _add_usage(total: dict | None, message) -> None:
    if total is None:
        return
    usage = getattr(message, "usage", None)
    for field in USAGE_FIELDS:
        total[field] = total.get(field, 0) + (getattr(usage, field, 0) or 0)
    total["requests"] = total.get("requests", 0) + 1


def extract_document(client, model: str, techs: list[tuple[str, str]], doc: documents.DocText,
                     period: str, usage: dict | None = None) -> list[dict]:
    system = trl_prompt.system(techs)
    fmt = schema.response_schema([t for t, _ in techs])
    message = _read(client, model, system, trl_prompt.user(doc), fmt)
    _add_usage(usage, message)
    if message.stop_reason == "refusal":
        return [{"refused": True, "source": doc.source, "doc_id": doc.doc_id, "period": period}]
    body = next((b.text for b in message.content if b.type == "text"), "")
    claims = schema.validate(json.loads(body), [t for t, _ in techs])
    rows = []
    for c in claims:
        rows.append({
            "claim_id": schema.claim_id(doc.source, doc.doc_id, c["tech_id"], c["quote"]),
            "period": period, "source": doc.source, "doc_id": doc.doc_id, "doc_date": doc.doc_date,
            "url": doc.url, "title": doc.title, **c,
            "quote_verified": verify.verify_quote(c["quote"], doc.text),
            "model": model, "prompt_version": trl_prompt.PROMPT_VERSION,
        })
    return rows


def main(argv=None) -> int:
    import anthropic  # here, not at module top: the import graph test allows it only in this package

    p = argparse.ArgumentParser()
    p.add_argument("--period", required=True, metavar="YYYY-Qn")
    p.add_argument("--model", default="claude-sonnet-5")
    p.add_argument("--limit", type=int, default=None, help="documents per technology")
    p.add_argument("--max-dollars", type=float, default=20.0)
    p.add_argument("--tech", default=None, help="one tech_id only")
    args = p.parse_args(argv)
    if args.model not in PRICE_PER_MTOK_INPUT:
        p.error(f"--model must be one of {sorted(PRICE_PER_MTOK_INPUT)} (no price to estimate against)")

    config.load_dotenv()
    from ..run import COLLECTORS
    watchlist = matcher.load_watchlist()
    ids = [args.tech] if args.tech else list(tracked.tracked_ids())
    techs = [(t, watchlist.by_id(t).name) for t in ids]
    weeks = quarter.weeks_in_period(args.period)
    conn = store.connect()
    docs = []
    for tid in ids:
        found = list(documents.texts_for(conn, tid, weeks, COLLECTORS))
        docs.extend(found[: args.limit] if args.limit else found)
    est = estimate_dollars(docs, args.model)
    print(f"{args.period} / {args.model}: {len(docs)} documents, ~${est:.2f} before caching")
    if est > args.max_dollars:
        print(f"estimate exceeds --max-dollars {args.max_dollars}; refusing to start")
        return 2

    TRL_DIR.mkdir(parents=True, exist_ok=True)
    raw_dir = TRL_DIR / f"raw-{args.period}-{args.model}"
    raw_dir.mkdir(exist_ok=True)
    out_path = TRL_DIR / f"claims-{args.period}.jsonl"
    if out_path.exists():
        print(f"WARNING: {out_path} exists; rows will be APPENDED. Delete it first to re-read the period.")
    usage_path = TRL_DIR / f"usage-{args.period}-{args.model}.json"
    usage: dict = json.loads(usage_path.read_text()) if usage_path.exists() else {}
    client = anthropic.Anthropic()
    n = 0
    with open(out_path, "a", encoding="utf8") as out:
        for doc in docs:
            try:
                try:
                    rows = extract_document(client, args.model, techs, doc, args.period, usage)
                except anthropic.RateLimitError as e:
                    time.sleep(int(e.response.headers.get("retry-after", "60")))
                    rows = extract_document(client, args.model, techs, doc, args.period, usage)
            except (anthropic.APIStatusError, anthropic.APIConnectionError, ValueError, json.JSONDecodeError) as e:
                print(f"{doc.source} {doc.doc_id}: {type(e).__name__}: {e} -- recorded, skipped")
                rows = [{"error": str(e), "source": doc.source, "doc_id": doc.doc_id, "period": args.period}]
            key = hashlib.sha1(doc.doc_id.encode()).hexdigest()[:10]
            (raw_dir / f"{doc.source}-{key}.json").write_text(json.dumps(rows, ensure_ascii=False))
            for r in rows:
                out.write(json.dumps(r, ensure_ascii=False) + "\n")
                n += 1
    usage_path.write_text(json.dumps(usage, indent=2))
    print(f"{out_path}: {n} rows appended")
    print(f"usage ({usage_path.name}, cumulative): {json.dumps(usage)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
