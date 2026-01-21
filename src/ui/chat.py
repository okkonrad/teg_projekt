import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve()
for parent in REPO_ROOT.parents:
    if (parent / "pyproject.toml").exists():
        if str(parent) not in sys.path:
            sys.path.insert(0, str(parent))
        break

import streamlit as st
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from src.services.graph_service import GraphService
from src.engine.matcher import Matcher
from src.engine.naive import NaiveRAG
from src.engine.bi_helpers import load_core_bi_questions, run_graphrag_analytics


def extract_search_params(prompt: str) -> dict:
    """Uses LLM to extract structured search parameters from natural language."""
    try:
        llm = ChatOpenAI(temperature=0, model="gpt-4o-mini")
        schema = {
            "title": "Ad-Hoc Search",
            "max_rate": 200, # Default high
            "skills": []
        }
        
        system_msg = """
        You are a smart recruiter assistant. Extract search parameters from the user's query into JSON.
        Output format:
        {
            "skills": [{"name": "SkillName", "proficiency": "Intermediate"}], 
            "max_rate": 150
        }
        
        Rules:
        1. "Senior" -> proficiency: "Advanced" or "Expert". "Junior" -> "Beginner". Default -> "Intermediate".
        2. Clean skill names (e.g., "React.js" -> "React").
        3. If no rate mentioned, omit max_rate (or use 200).
        """
        
        response = llm.invoke([
            SystemMessage(content=system_msg),
            HumanMessage(content=prompt)
        ])
        
        # Naive JSON parsing (Robust implementation would use function calling)
        content = response.content.strip()
        if content.startswith("```json"):
            content = content.replace("```json", "").replace("```", "")
        
        extracted = json.loads(content)
        
        # Merge setup
        schema["skills"] = extracted.get("skills", [])
        if "max_rate" in extracted:
            schema["max_rate"] = extracted["max_rate"]
            
        return schema
    except Exception as e:
        print(f"Extraction Error: {e}")
        return None


def _format_naive_metrics(payload: dict) -> str:
    strategy = payload.get("strategy", "naive_retrieval")
    used_llm = payload.get("used_llm", False)
    warning = payload.get("warning")
    details = f"Strategy: {strategy} | LLM: {'yes' if used_llm else 'no'}"
    if warning:
        details += f" | Note: {warning}"
    return details

# --- Main UI ---
def render():
    st.header("TalentMatch AI Assistant")

    with st.expander("Question Bank", expanded=True):
        st.caption("Select a PRD template and fill macros to copy a full question.")

        QUESTION_TEMPLATES = [
            "How many Python developers are available next month?",
            "Count developers with AWS certifications",
            "Find senior developers with React AND Node.js experience",
            "List available developers in Pacific timezone",
            "Average years of experience for machine learning projects",
            "Total capacity available for Q4 projects",
            "Find developers who worked together successfully",
            "Developers from same university as our top performers",
            "Who becomes available after current project ends?",
            "Skills distribution by graduation year",
            "Optimal team composition for FinTech RFP under budget constraints",
            "Skills gaps analysis for upcoming project pipeline",
            "Risk assessment: single points of failure in current assignments",
        ]

        service = GraphService()
        try:
            rfps = service.get_all_rfps()
            all_skills = service.list_all_skills()
        finally:
            service.close()

        rfp_options = [""] + [r["title"] for r in rfps]
        selected_template = st.selectbox("Template", QUESTION_TEMPLATES)
        selected_rfp = st.selectbox("Project macro (optional)", rfp_options)
        selected_skills = st.multiselect("Skills macro (AND, optional)", all_skills)

        question_text = selected_template
        if "FinTech RFP" in question_text:
            question_text = question_text.replace("FinTech RFP", selected_rfp or "FinTech RFP")
        if selected_skills:
            if "Python developers" in question_text:
                question_text = question_text.replace(
                    "Python developers", " and ".join(selected_skills) + " developers"
                )
            if "React AND Node.js" in question_text:
                question_text = question_text.replace(
                    "React AND Node.js", " AND ".join(selected_skills)
                )

        st.text_area("Generated question", question_text, height=80)

    with st.sidebar:
        st.subheader("Configuration")
        mode = st.radio("Engine Mode", ["GraphRAG (Logic)", "NaiveRAG (Semantic)"])
        
        st.info(
            "GraphRAG: Uses Graph Logic & Cypher for precise answers.\n"
            "NaiveRAG: Uses Semantic Search for fuzzy matching."
        )

        st.divider()
        st.subheader("Database Stats")
        service = GraphService()
        try:
            stats = service.get_graph_stats()
        finally:
            service.close()
        st.write(f"Candidates: {stats.get('candidates', 0)}")
        st.write(f"RFPs: {stats.get('rfps', 0)}")

        st.divider()
        st.subheader("NaiveRAG Embeddings")
        if st.button("Build embeddings (prep_vectors)"):
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "src.scripts.prep_vectors"],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                st.session_state["prep_vectors_log"] = (result.stdout or "").strip()
                st.success("Embeddings created.")
            except subprocess.CalledProcessError as exc:
                st.session_state["prep_vectors_log"] = (exc.stderr or exc.stdout or "").strip()
                st.error(f"Embedding prep failed: {exc.stderr or exc.stdout}")

        if st.session_state.get("prep_vectors_log"):
            with st.expander("Embedding prep logs"):
                st.text_area(
                    "prep_vectors output",
                    st.session_state.get("prep_vectors_log", ""),
                    height=200,
                )

        st.divider()
        st.subheader("NaiveRAG Settings")
        naive_use_llm = st.checkbox("Use LLM for NaiveRAG answers", value=True)
        naive_context_chars = st.slider(
            "Max context characters",
            min_value=400,
            max_value=3000,
            value=1800,
            step=200,
        )

        st.divider()
        st.subheader("Data Cleanup")
        if st.button("Clear CVs folder"):
            cvs_dir = Path("data/raw/cvs")
            if not cvs_dir.exists():
                st.info("CVs folder does not exist.")
            else:
                deleted = 0
                for pdf in cvs_dir.glob("*.pdf"):
                    try:
                        pdf.unlink()
                        deleted += 1
                    except OSError as exc:
                        st.error(f"Failed to delete {pdf.name}: {exc}")
                st.success(f"Deleted {deleted} PDF files.")


    if "messages" not in st.session_state:
        st.session_state.messages = [{"role": "assistant", "content": "Hello! Ask me to find developers or analyze the talent pool."}]

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
            if "results" in msg:
                for res in msg["results"]:
                    score_label = f"Score: {res.get('score', 0):.2f}"
                    with st.expander(f"{res['name']} - {score_label}"):
                        st.write(f"**Rate:** ${res.get('hourly_rate', 'N/A')}/hr")
                        if 'match_reason' in res: st.info(res['match_reason']) 
                        st.json(res)
            if "metrics" in msg:
                st.caption(msg["metrics"])

    if prompt := st.chat_input("E.g., 'Find senior Python devs' or 'How many Java experts?'"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.write(prompt)

        with st.chat_message("assistant"):
            placeholder = st.empty()
            placeholder.write("Thinking...")
            
            start_time = time.time()
            results = []
            response_text = ""
            metrics_str = ""
            
            try:
                if mode == "GraphRAG (Logic)":
                    service = GraphService()
                    try:
                        analytics = run_graphrag_analytics(prompt, service)
                    finally:
                        service.close()
                    response_text = analytics["response"]
                    results = analytics.get("results") or []
                    if analytics["strategy"] == "direct_count":
                        metrics_str = "Count via Neo4j (direct)"
                    elif analytics["strategy"] == "rfp_match":
                        metrics_str = "RFP match via graph"
                        if results:
                            response_text += "\nReasons available in the candidate details."
                    else:
                        metrics_str = "Executed via GraphCypherQAChain"
                elif mode == "NaiveRAG (Semantic)":
                    rag = NaiveRAG()
                    payload = rag.answer(
                        prompt,
                        top_k=5,
                        use_llm=naive_use_llm,
                        max_context_chars=naive_context_chars,
                    )
                    response_text = payload["response"]
                    results = payload["results"]
                    metrics_str = _format_naive_metrics(payload)
                    rag.close()

                elapsed = time.time() - start_time
                if not metrics_str:
                    metrics_str = f"{elapsed:.2f}s | Mode: {mode} | Res: {len(results)}"

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": response_text,
                    "results": results,
                    "metrics": metrics_str
                })

                placeholder.write(response_text)
                for res in results:
                    with st.expander(f"{res['name']} (Score: {res.get('score', 0):.2f})"):
                        st.write(f"**Rate:** ${res.get('hourly_rate', 'N/A')}/hr")
                        if "available_pct" in res:
                            st.write(f"**Availability:** {res.get('available_pct', 'N/A')}% (alloc: {res.get('allocation_pct', 'N/A')}%)")
                        if 'match_reason' in res: st.info(res['match_reason'])
                        st.json(res)
                st.caption(metrics_str)

            except Exception as e:
                placeholder.error(f"Error: {e}")
                st.session_state.messages.append({"role": "assistant", "content": f"Error: {e}"})
