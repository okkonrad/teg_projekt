import argparse
import os
import sys
from glob import glob
from pathlib import Path
from typing import List

REPO_ROOT = Path(__file__).resolve()
for parent in REPO_ROOT.parents:
    if (parent / "pyproject.toml").exists():
        if str(parent) not in sys.path:
            sys.path.insert(0, str(parent))
        break

from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_community.graphs import Neo4jGraph
from langchain_openai import ChatOpenAI

from src.data.pdf_parser import extract_text_from_pdf

try:
    from langchain_experimental.graph_transformers import LLMGraphTransformer
except ImportError as exc:
    raise ImportError(
        "Missing dependency: langchain-experimental. Add it to dependencies."
    ) from exc


DEFAULT_ALLOWED_NODES = [
    "Person",
    "Skill",
    "Company",
    "Project",
    "Certification",
    "University",
]

DEFAULT_ALLOWED_RELATIONSHIPS = [
    ("Person", "HAS_SKILL", "Skill"),
    ("Person", "WORKED_AT", "Company"),
    ("Person", "WORKED_ON", "Project"),
    ("Person", "EARNED", "Certification"),
    ("Person", "STUDIED_AT", "University"),
]


def load_pdfs(pdf_dir: str) -> List[str]:
    pdf_paths = sorted(glob(os.path.join(pdf_dir, "*.pdf")))
    return [path for path in pdf_paths if os.path.isfile(path)]


def build_graph_documents(pdf_paths: List[str]) -> List[Document]:
    documents = []
    for path in pdf_paths:
        text = extract_text_from_pdf(path)
        if not text.strip():
            continue
        documents.append(Document(page_content=text, metadata={"source": path, "type": "cv"}))
    return documents


def main() -> None:
    load_dotenv(override=True)
    parser = argparse.ArgumentParser(description="Extract CV PDFs into Neo4j using LLMGraphTransformer.")
    parser.add_argument("--pdf-dir", default="data/raw/cvs", help="Directory with CV PDFs")
    parser.add_argument("--clear-graph", action="store_true", help="Delete all nodes before ingest")
    parser.add_argument("--model", default="gpt-4o-mini", help="OpenAI model name")
    args = parser.parse_args()

    pdf_paths = load_pdfs(args.pdf_dir)
    if not pdf_paths:
        print(f"No PDFs found in {args.pdf_dir}")
        return

    documents = build_graph_documents(pdf_paths)
    if not documents:
        print("No text extracted from PDFs.")
        return

    graph = Neo4jGraph(
        url=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        username=os.getenv("NEO4J_USERNAME", "neo4j"),
        password=os.getenv("NEO4J_PASSWORD", "password"),
        enhanced_schema=False,
    )

    if args.clear_graph:
        graph.query("MATCH (n) DETACH DELETE n")

    llm = ChatOpenAI(model=args.model, temperature=0)
    transformer = LLMGraphTransformer(
        llm=llm,
        allowed_nodes=DEFAULT_ALLOWED_NODES,
        allowed_relationships=DEFAULT_ALLOWED_RELATIONSHIPS,
        strict_mode=True,
    )

    graph_documents = transformer.convert_to_graph_documents(documents)
    graph.add_graph_documents(graph_documents, include_source=True, base_entity_label=True)

    print(f"Ingested {len(graph_documents)} graph documents from {len(documents)} PDFs.")


if __name__ == "__main__":
    main()
