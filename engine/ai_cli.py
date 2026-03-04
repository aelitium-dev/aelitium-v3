#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

# Support both:
#  - running as a module (python -m engine.ai_cli)
#  - running as a script   (python engine/ai_cli.py)
if __package__:
    from .ai_canonical import canonicalize_ai_output
else:
    import sys
    from pathlib import Path as _Path
    sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
    from engine.ai_canonical import canonicalize_ai_output


def cmd_validate(args: argparse.Namespace) -> int:
    obj = json.loads(Path(args.input).read_text(encoding="utf-8"))
    if obj.get("schema_version") != "ai_output_v1":
        print("AI_STATUS=INVALID reason=BAD_SCHEMA_VERSION")
        return 2
    # minimal required fields (schema-level validation can be added later)
    required = ["schema_version", "model", "prompt", "output", "ts_utc"]
    missing = [k for k in required if k not in obj]
    if missing:
        print("AI_STATUS=INVALID reason=MISSING_FIELDS missing=" + ",".join(missing))
        return 2
    print("AI_STATUS=VALID rc=0")
    return 0

def cmd_canonicalize(args: argparse.Namespace) -> int:
    obj = json.loads(Path(args.input).read_text(encoding="utf-8"))
    canonical, h = canonicalize_ai_output(obj)
    if args.print:
        print(canonical)
    print(f"AI_CANON_SHA256={h}")
    return 0

def main() -> int:
    ap = argparse.ArgumentParser(prog="aelitium-ai")
    sub = ap.add_subparsers(dest="cmd", required=True)

    v = sub.add_parser("validate", help="Validate ai_output_v1 minimal contract")
    v.add_argument("--input", required=True)
    v.set_defaults(fn=cmd_validate)

    c = sub.add_parser("canonicalize", help="Canonicalize AI output and print hash")
    c.add_argument("--input", required=True)
    c.add_argument("--print", action="store_true", help="Print canonical JSON")
    c.set_defaults(fn=cmd_canonicalize)

    args = ap.parse_args()
    return int(args.fn(args))

if __name__ == "__main__":
    raise SystemExit(main())
