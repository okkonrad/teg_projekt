import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve()
for parent in REPO_ROOT.parents:
    if (parent / "pyproject.toml").exists():
        if str(parent) not in sys.path:
            sys.path.insert(0, str(parent))
        break

import json
from datetime import datetime, timezone

import streamlit as st
from src.services.graph_service import GraphService


def render():
    st.header("BI Dashboard")
    st.caption("High-level snapshot of the knowledge graph and BI quick metrics.")

    service = GraphService()
    try:
        stats = service.get_graph_stats()
        top_skills = service.get_top_skills_with_counts(limit=10)
        top_demand = service.get_top_skills_in_demand(limit=10)

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Candidates", stats.get("candidates", 0))
        col2.metric("RFPs", stats.get("rfps", 0))
        col3.metric("Skills", stats.get("skills", 0))
        col4.metric("Companies", stats.get("companies", 0))

        st.subheader("Top Skills in Candidate Pool")
        if top_skills:
            st.bar_chart({row["skill"]: row["count"] for row in top_skills})
        else:
            st.info("No skills found in the graph.")

        st.subheader("Top Skills in RFP Demand")
        if top_demand:
            st.bar_chart({row["skill"]: row["demand"] for row in top_demand})
        else:
            st.info("No RFP demand data found.")

        st.subheader("BI Quick Metrics")
        metrics = {
            "Python devs (total)": service.count_candidates_by_skill("Python"),
            "Python devs (available now)": service.count_available_candidates_now("Python"),
            "Python devs (next month)": service.count_available_candidates_next_month("Python"),
            "AWS Certified": service.count_candidates_with_certification("AWS Certified"),
            "MIT alumni": service.count_candidates_by_university("MIT"),
        }
        st.json(metrics)

        if st.button("Save dashboard evidence"):
            payload = {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "stats": stats,
                "top_skills": top_skills,
                "top_demand": top_demand,
                "metrics": metrics,
            }
            output_path = Path("docs/ui_dashboard_evidence.json")
            output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            st.success(f"Saved dashboard evidence to {output_path}")
    finally:
        service.close()
