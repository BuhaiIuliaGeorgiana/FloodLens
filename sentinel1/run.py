"""Exemplu de rulare din terminal."""
import argparse
import json
import os
from pathlib import Path

import ee
from .pipeline import process_sentinel1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", required=True, help="Fisierul JSON al evenimentului")
    parser.add_argument("--output", required=True, help="Folderul pentru rezultate")
    parser.add_argument("--project", default=os.getenv("EE_PROJECT"))
    parser.add_argument("--authenticate", action="store_true")
    args = parser.parse_args()
    if not args.project:
        parser.error("Specificati --project sau variabila EE_PROJECT")
    event = json.loads(Path(args.event).read_text(encoding="utf-8"))
    if args.authenticate:
        ee.Authenticate()
    ee.Initialize(project=args.project)
    result = process_sentinel1(event, args.output)
    print(json.dumps(result, indent=2))
    return 1 if result["status"] == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
