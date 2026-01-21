import sys
from pathlib import Path
from typing import Dict, List

REPO_ROOT = Path(__file__).resolve()
for parent in REPO_ROOT.parents:
    if (parent / "pyproject.toml").exists():
        if str(parent) not in sys.path:
            sys.path.insert(0, str(parent))
        break

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from src.engine.vector_ops import VectorService

NO_MATCH_MESSAGE = (
    "No matches found. If this is unexpected, run "
    "'python3 -m src.scripts.prep_vectors' to build embeddings."
)


def _summarize_results(results: List[Dict]) -> str:
    if not results:
        return NO_MATCH_MESSAGE
    names = [r.get("name") for r in results if r.get("name")]
    return f"Top {len(names)} candidates: {', '.join(names)}."


def _is_analytic_query(prompt: str) -> bool:
    lower = prompt.lower()
    return any(
        token in lower
        for token in [
            "how many",
            "count",
            "available",
            "average",
            "total",
            "certification",
            "certifications",
            "capacity",
            "skills gap",
            "skills gaps",
            "risk",
            "distribution",
            "by skill",
            "by seniority",
        ]
    )


def _build_context(results: List[Dict], max_chars: int = 1800) -> str:
    lines = []
    for idx, row in enumerate(results, start=1):
        text = row.get("text_repr") or ""
        if not text:
            text = (
                f"Candidate: {row.get('name', 'Unknown')}. "
                f"Rate: ${row.get('hourly_rate', 'N/A')}/hr."
            )
        score = row.get("score")
        score_str = f"{score:.3f}" if isinstance(score, (int, float)) else "N/A"
        lines.append(f"{idx}. [score {score_str}] {text}")

    context = "\n".join(lines).strip()
    if len(context) > max_chars:
        return context[: max_chars - 3] + "..."
    return context


def _format_fallback_response(results: List[Dict], max_items: int = 5) -> str:
    if not results:
        return NO_MATCH_MESSAGE
    lines = []
    for row in results[:max_items]:
        name = row.get("name", "Unknown")
        rate = row.get("hourly_rate", "N/A")
        score = row.get("score")
        score_str = f"{score:.3f}" if isinstance(score, (int, float)) else "N/A"
        lines.append(f"- {name} (${rate}/hr, score {score_str})")
    return "Top semantic matches:\n" + "\n".join(lines)

class NaiveRetriever:
    def __init__(self):
        self.vector_service = VectorService()

    def close(self):
        self.vector_service.close()

    def find_matches(self, query: str, top_k: int = 5) -> List[Dict]:
        query_embedding = self.vector_service.generate_embedding(query)

        results = []
        with self.vector_service.driver.session() as session:
            result = session.run("""
                CALL db.index.vector.queryNodes('candidate_vectors', $k, $embedding)
                YIELD node, score
                RETURN node.id as id, node.name as name, node.hourly_rate as hourly_rate, node.text_repr as text_repr, score
            """, k=top_k, embedding=query_embedding)
            
            for record in result:
                results.append(record.data())

        return results


class NaiveRAG:
    def __init__(self, model: str = "gpt-4o-mini", temperature: float = 0.2):
        self.retriever = NaiveRetriever()
        self.llm = ChatOpenAI(temperature=temperature, model=model)

    def close(self):
        self.retriever.close()

    def answer(
        self,
        prompt: str,
        top_k: int = 5,
        use_llm: bool = True,
        max_context_chars: int = 1800,
    ) -> Dict:
        results = self.retriever.find_matches(prompt, top_k=top_k)

        response = _format_fallback_response(results)
        strategy = "naive_retrieval"
        used_llm = False
        warning = None

        if use_llm and results:
            try:
                analytic_hint = _is_analytic_query(prompt)
                context = _build_context(results, max_chars=max_context_chars)
                system_lines = [
                    "You are a helpful recruiter assistant.",
                    "Answer in the SAME LANGUAGE as the user.",
                    "Use ONLY the provided context; do not invent facts.",
                ]
                if analytic_hint:
                    system_lines.append(
                        "If the user asks for counts/aggregates, explain that exact BI counts "
                        "are not available here and summarize the top matches instead."
                    )

                messages = [
                    SystemMessage(content=" ".join(system_lines)),
                    HumanMessage(
                        content=(
                            f"User query: {prompt}\n\n"
                            f"Context candidates:\n{context}\n\n"
                            "Provide a concise answer and highlight the most relevant candidates."
                        )
                    ),
                ]
                response = self.llm.invoke(messages).content
                strategy = "naive_rag"
                used_llm = True
            except Exception:
                warning = "LLM unavailable; returned semantic top matches."

        return {
            "response": response,
            "results": results,
            "strategy": strategy,
            "used_llm": used_llm,
            "warning": warning,
        }

if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser()
    parser.add_argument("--query", required=True, help="Search query description")
    parser.add_argument("--top-k", type=int, default=5, help="Top K results")
    parser.add_argument("--use-llm", action="store_true", help="Generate answer with LLM")
    args = parser.parse_args()

    rag = NaiveRAG()
    try:
        answer = rag.answer(args.query, top_k=args.top_k, use_llm=args.use_llm)
        print(json.dumps(answer, indent=2))
    finally:
        rag.close()
