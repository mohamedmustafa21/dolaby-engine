"""CLI used by Laravel:  python -m dolaby_engine generate < input.json   |   analyze --image PATH

generate input : {"wardrobe": [garment, ...], "request": {...}, "config": {...optional}}
Both commands print one JSON document on stdout. Errors: {"error": "..."} and exit code 2.
"""
import argparse
import json
import sys

from .color_analysis import extract_dominant_colors
from .config import EngineConfig
from .outfit_generator import generate_outfits
from .schemas import Garment, OutfitRequest, ValidationError


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="dolaby_engine")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("generate")
    a = sub.add_parser("analyze")
    a.add_argument("--image", required=True)
    args = p.parse_args(argv)
    try:
        if args.cmd == "generate":
            payload = json.load(sys.stdin)
            wardrobe = [Garment.from_dict(g) for g in payload.get("wardrobe", [])]
            request = OutfitRequest.from_dict(payload.get("request"))
            config = EngineConfig.from_dict(payload.get("config"))
            out = generate_outfits(wardrobe, request, config).to_dict()
        else:
            out = extract_dominant_colors(args.image).to_dict()
    except (ValidationError, ValueError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc)}))
        return 2
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
