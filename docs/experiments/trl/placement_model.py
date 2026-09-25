"""Task 6 step 4, Reader 2: a second model reads the placement sheet, one call
per technology, and returns one TRL. The model is claude-opus-5-5, so it is
not the extractor (claude-sonnet-5) grading its own claims.

  placement_model.py [--limit N] [--max-dollars 2]

Reads docs/audit/trl-placement-sheet.md. Writes data/trl/placement-model.csv
(tech_id, reader_trl, reader_note), the raw responses to
data/trl/placement-model-raw.jsonl and token totals to
data/trl/placement-model-usage.json. Refusals are recorded, never rerouted.
"""

import argparse
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from observatory import config  # noqa: E402

MODEL = "claude-opus-5-5"
PRICE_PER_MTOK = {"input": 4.00, "output": 20.00}
SHEET = ROOT / "docs/audit/trl-placement-sheet.md"
OUT = ROOT / "data/trl"
USAGE_FIELDS = ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")

SYSTEM = """You place one technology on the Technology Readiness Level scale, 1-9, from a list of claims
extracted from documents. Each claim gives: claim type, actor type and actor, setting, source and
date, whether its quote was verified against the document, the URL, and the quote itself.

Bands: 1-3 research (proposed, simulated); 4-6 prototype and pilot; 7-8 demonstrated in an
operational environment (in real operation, sold, bought); 9 routine commercial operation at scale.

Judge only from the claims shown. Return the single TRL 1-9 the evidence holds: the highest level
the evidence supports, not an average. Return it as JSON {"trl": n}."""

FORMAT = {"type": "object", "properties": {"trl": {"type": "integer", "enum": list(range(1, 10))}},
          "required": ["trl"], "additionalProperties": False}


def sections(md: str) -> dict[str, str]:
    """The sheet's '## tech_id' sections, each with its heading, in sheet order."""
    parts = re.split(r"(?m)^## ", md)[1:]
    return {p.split("\n", 1)[0].strip(): "## " + p.rstrip() for p in parts}


def main(argv=None) -> int:
    import anthropic

    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--max-dollars", type=float, default=2.0)
    args = p.parse_args(argv)
    config.load_dotenv()
    secs = list(sections(SHEET.read_text()).items())[: args.limit]
    # Input estimate plus a generous 4000 output (thinking included) per call.
    est = sum((len(SYSTEM) + len(s)) / 3.5 * PRICE_PER_MTOK["input"] + 4000 * PRICE_PER_MTOK["output"]
              for _, s in secs) / 1e6
    print(f"{MODEL}: {len(secs)} technologies, ~${est:.2f}")
    if est > args.max_dollars:
        print(f"estimate exceeds --max-dollars {args.max_dollars}; refusing to start")
        return 2
    client, usage, out_rows = anthropic.Anthropic(), {}, []
    with open(OUT / "placement-model-raw.jsonl", "w", encoding="utf8") as raw:
        for tech, text in secs:
            with client.messages.stream(
                model=MODEL, max_tokens=16000,
                system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": text}],
                output_config={"effort": "medium", "format": {"type": "json_schema", "schema": FORMAT}},
            ) as stream:
                msg = stream.get_final_message()
            for f in USAGE_FIELDS:
                usage[f] = usage.get(f, 0) + (getattr(msg.usage, f, 0) or 0)
            raw.write(json.dumps({"tech_id": tech, "response": json.loads(msg.to_json())}) + "\n")
            if msg.stop_reason == "refusal":
                row = {"tech_id": tech, "reader_trl": "", "reader_note": "refused"}
            else:
                body = next((b.text for b in msg.content if b.type == "text"), "")
                row = {"tech_id": tech, "reader_trl": json.loads(body)["trl"],
                       "reader_note": f"{MODEL}; stop_reason={msg.stop_reason}"}
            print(tech, row["reader_trl"], row["reader_note"])
            out_rows.append(row)
    with open(OUT / "placement-model.csv", "w", newline="", encoding="utf8") as f:
        w = csv.DictWriter(f, fieldnames=["tech_id", "reader_trl", "reader_note"])
        w.writeheader()
        w.writerows(out_rows)
    dollars = (usage["input_tokens"] * 4.00 + usage["output_tokens"] * 20.00
               + usage["cache_read_input_tokens"] * 0.20 + usage["cache_creation_input_tokens"] * 5.00) / 1e6
    usage["dollars"] = round(dollars, 4)
    (OUT / "placement-model-usage.json").write_text(json.dumps(usage, indent=2))
    print("usage", json.dumps(usage))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
