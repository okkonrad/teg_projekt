import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from src.engine.bi_helpers import load_core_bi_questions, run_graphrag_analytics
from src.engine.naive import NaiveRAG
from src.services.graph_service import GraphService


def run_graphrag(question: str) -> dict:
    service = GraphService()
    try:
        start = time.time()
        analytics = run_graphrag_analytics(question, service)
        elapsed = time.time() - start
    finally:
        service.close()
    return {
        "response": analytics["response"],
        "strategy": analytics["strategy"],
        "count": analytics["count"],
        "elapsed_sec": round(elapsed, 4),
    }


def run_naive(question: str, top_k: int) -> dict:
    rag = NaiveRAG()
    try:
        start = time.time()
        payload = rag.answer(question, top_k=top_k, use_llm=True)
        elapsed = time.time() - start
    finally:
        rag.close()

    return {
        "response": payload["response"],
        "top_results": [
            {"id": r.get("id"), "name": r.get("name"), "score": r.get("score")}
            for r in payload["results"]
        ],
        "elapsed_sec": round(elapsed, 4),
        "strategy": payload.get("strategy"),
        "used_llm": payload.get("used_llm"),
        "warning": payload.get("warning"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run E2E chat BI questions.")
    parser.add_argument("--limit", type=int, default=10, help="How many core BI questions to run.")
    parser.add_argument("--top-k", type=int, default=5, help="Top K results for NaiveRAG.")
    parser.add_argument("--output", type=str, default="docs/chat_bi_e2e.json", help="Output JSON path.")
    args = parser.parse_args()

    questions = load_core_bi_questions(limit=args.limit)
    if not questions:
        raise SystemExit("No BI questions found. Check docs/BI_QUESTIONS.md.")

    results = []
    for question in questions:
        results.append(
            {
                "question": question,
                "graphrag": run_graphrag(question),
                "naive": run_naive(question, top_k=args.top_k),
            }
        )

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "question_count": len(results),
        "naive_top_k": args.top_k,
        "results": results,
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote E2E chat results to {output_path}")


if __name__ == "__main__":
    main()
