import argparse
import os
import sys
from glob import glob
from pathlib import Path

REPO_ROOT = Path(__file__).resolve()
for parent in REPO_ROOT.parents:
    if (parent / "pyproject.toml").exists():
        if str(parent) not in sys.path:
            sys.path.insert(0, str(parent))
        break

from src.data.rfp_parser import parse_rfp_input
from src.services.graph_service import GraphService


def load_files(input_path: str):
    if os.path.isdir(input_path):
        return sorted(glob(os.path.join(input_path, "*.txt")))
    if os.path.isfile(input_path):
        return [input_path]
    return []


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse RFP text/JSON and load into Neo4j.")
    parser.add_argument("--input", required=True, help="File or directory with RFP text files")
    args = parser.parse_args()

    files = load_files(args.input)
    if not files:
        print(f"No RFP files found at {args.input}")
        return

    service = GraphService()
    try:
        for path in files:
            with open(path, "r", encoding="utf-8") as handle:
                raw = handle.read()
            rfp = parse_rfp_input(raw)
            service.add_rfp(rfp)
            print(f"Loaded RFP from {path}: {rfp.get('title')}")
    finally:
        service.close()


if __name__ == "__main__":
    main()
