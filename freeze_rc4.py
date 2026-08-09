#!/usr/bin/env python3
"""Sign the RC4 study freeze and write its certificate.

Run once, before recruiting a participant:

    python3 freeze_rc4.py --signed-by "Roger Kim"

It refuses to run twice. A freeze that can be re-signed is a freeze that
can be moved after the fact.

Semiconductor School / Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ppact.study_freeze import (FREEZE_FILE, certificate, current,
                                freeze, verify_freeze)

CERT_FILE = "RC4_FREEZE_CERTIFICATE.md"


def main() -> int:
    ap = argparse.ArgumentParser()
    # `--check` needs no signer: asking whether the instrument is
    # frozen is not the same act as freezing it, and requiring a name
    # to ask made the check harder to run than the signing.
    ap.add_argument("--signed-by")
    ap.add_argument("--note",
                    default="Signed before participant recruitment.")
    ap.add_argument("--check", action="store_true",
                    help="report the current state without signing")
    args = ap.parse_args()

    if not args.check and not args.signed_by:
        ap.error("--signed-by is required to sign a freeze")

    if args.check:
        state = verify_freeze(FREEZE_FILE)
        if not state["frozen"]:
            print(f"  NOT FROZEN - {state['reason']}")
            return 1
        print(f"  frozen at {state['frozen_at']} by "
              f"{state['signed_by']}")
        print(f"  intact: {state['intact']}")
        for m in state["moved"]:
            print(f"    MOVED  {m['item']}: {m['was']} -> {m['now']}")
        return 0 if state["intact"] else 1

    try:
        rec = freeze(FREEZE_FILE, signed_by=args.signed_by,
                     note=args.note)
    except FileExistsError as exc:
        print(f"  {exc}")
        return 1

    with open(CERT_FILE, "w", encoding="utf-8") as fh:
        fh.write("\n".join(certificate(FREEZE_FILE)) + "\n")

    print(f"  frozen at {rec.frozen_at}")
    print(f"  record      {FREEZE_FILE}")
    print(f"  certificate {CERT_FILE}")
    for name, digest in rec.digests.items():
        print(f"    {name:<22s}{digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
