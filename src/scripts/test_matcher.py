import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve()
for parent in REPO_ROOT.parents:
    if (parent / "pyproject.toml").exists():
        if str(parent) not in sys.path:
            sys.path.insert(0, str(parent))
        break

from src.engine.matcher import Matcher


def main() -> None:
    parser = argparse.ArgumentParser(description="Quick matcher sanity check")
    parser.add_argument("--rfp", required=True, help="RFP ID to match against")
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    matcher = Matcher()
    try:
        results = matcher.find_matches(args.rfp, top_k=args.top_k)
        print(json.dumps(results, indent=2))
    finally:
        matcher.close()


if __name__ == "__main__":
    main()
