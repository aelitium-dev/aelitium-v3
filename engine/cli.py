import argparse
import sys
from pack import pack
from verify import verify, RC_VALID
from repro import repro


def main() -> int:
    parser = argparse.ArgumentParser(prog="aelitium")
    subparsers = parser.add_subparsers(dest="command")

    p_pack = subparsers.add_parser("pack")
    p_pack.add_argument("--input", required=True)
    p_pack.add_argument("--out", required=True)

    p_verify = subparsers.add_parser("verify")
    p_verify.add_argument("--manifest", required=True)
    p_verify.add_argument("--evidence", required=True)

    p_repro = subparsers.add_parser("repro")
    p_repro.add_argument("--input", required=True)

    args = parser.parse_args()

    if args.command == "pack":
        pack(args.input, args.out)
        return 0

    if args.command == "verify":
        rc = verify(args.manifest, args.evidence)
        if rc == RC_VALID:
            print("STATUS=VALID rc=0")
            return 0
        print("STATUS=INVALID rc=2")
        return 2

    if args.command == "repro":
        return repro(args.input)

    return 2


if __name__ == "__main__":
    sys.exit(main())