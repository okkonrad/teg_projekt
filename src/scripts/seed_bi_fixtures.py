import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve()
for parent in REPO_ROOT.parents:
    if (parent / "pyproject.toml").exists():
        if str(parent) not in sys.path:
            sys.path.insert(0, str(parent))
        break

from src.data.loader import GraphLoader, NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD


def main() -> None:
    fixtures_path = Path("data/fixtures/bi_test_data.json")
    if not fixtures_path.exists():
        raise FileNotFoundError("Missing bi_test_data.json")

    payload = json.loads(fixtures_path.read_text(encoding="utf-8"))
    candidates = payload.get("candidates", [])
    rfps = payload.get("rfps", [])

    loader = GraphLoader(NEO4J_URI, (NEO4J_USER, NEO4J_PASSWORD))
    try:
        loader.clean_db()
        loader.create_constraints()
        loader.load_candidates(candidates)
        loader.load_rfps(rfps)
    finally:
        loader.close()

    print(f"Seeded {len(candidates)} candidates and {len(rfps)} RFPs.")


if __name__ == "__main__":
    main()
