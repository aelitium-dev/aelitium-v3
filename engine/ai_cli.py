#!/usr/bin/env python3
import argparse
import json
import jsonschema
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
    schema = json.loads(Path(args.schema).read_text(encoding="utf-8"))

    try:
        jsonschema.validate(instance=obj, schema=schema)
    except Exception as e:
        print("STATUS=INVALID rc=2 reason=SCHEMA_VIOLATION")
        # linha curta e estável para logs
        print(f"DETAIL={type(e).__name__}")
        return 2

    print("STATUS=VALID rc=0")
    return 0

def cmd_canonicalize(args: argparse.Namespace) -> int:
    obj = json.loads(Path(args.input).read_text(encoding="utf-8"))
    canonical, h = canonicalize_ai_output(obj)
    if args.print:
        print(canonical)
    print(f"AI_CANON_SHA256={h}")
    return 0


def cmd_pack(args: argparse.Namespace) -> int:
    # import lazy: não rebenta validate/canonicalize se pack tiver bugs
    from engine.ai_pack import ai_pack_from_obj

    obj = json.loads(Path(args.input).read_text(encoding="utf-8"))
    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)

    res = ai_pack_from_obj(obj)

    (outdir / "ai_canonical.json").write_text(res.canonical_json + "\n", encoding="utf-8")
    (outdir / "ai_manifest.json").write_text(json.dumps(res.manifest, sort_keys=True) + "\n", encoding="utf-8")

    print("STATUS=OK rc=0")
    print(f"AI_HASH_SHA256={res.ai_hash_sha256}")
    return 0

def main() -> int:
    ap = argparse.ArgumentParser(prog="aelitium-ai")
    sub = ap.add_subparsers(dest="cmd", required=True)

    v = sub.add_parser("validate", help="Validate ai_output_v1 minimal contract")
    v.add_argument("--schema", default="engine/schemas/ai_output_v1.json")
    v.add_argument("--input", required=True)
    v.set_defaults(fn=cmd_validate)

    pck = sub.add_parser("pack", help="Write canonical + manifest artifacts")
    pck.add_argument("--input", required=True)
    pck.add_argument("--out", required=True)
    pck.set_defaults(fn=cmd_pack)

    c = sub.add_parser("canonicalize", help="Canonicalize AI output and print hash")
    c.add_argument("--input", required=True)
    c.add_argument("--print", action="store_true", help="Print canonical JSON")
    c.set_defaults(fn=cmd_canonicalize)

    args = ap.parse_args()
    return int(args.fn(args))

if __name__ == "__main__":
    raise SystemExit(main())
