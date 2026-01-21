import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve()
for parent in REPO_ROOT.parents:
    if (parent / "pyproject.toml").exists():
        if str(parent) not in sys.path:
            sys.path.insert(0, str(parent))
        break

import streamlit as st
from src.services.graph_service import GraphService


def render():
    st.header("RFP Browser")
    st.caption("Browse RFPs with basic filters.")

    search = st.text_input("Search by title/description", "")
    seniority = st.selectbox("Required Seniority", ["", "Junior", "Mid", "Senior", "Lead"], index=0)
    timezone = st.selectbox("Timezone", ["", "UTC-8", "UTC-5", "UTC+0", "UTC+1", "UTC+2"], index=0)
    col1, col2 = st.columns(2)
    min_budget = col1.number_input("Min budget", min_value=0.0, value=0.0, step=1000.0)
    max_budget = col2.number_input("Max budget", min_value=0.0, value=0.0, step=1000.0)
    limit = st.slider("Max results", min_value=10, max_value=200, value=50, step=10)

    service = GraphService()
    try:
        all_skills = service.list_all_skills()
        selected_skills = st.multiselect("Required skills (must include all)", all_skills)
        rows = service.list_rfps(
            search=search.strip() or None,
            skills=selected_skills or None,
            seniority=seniority or None,
            timezone=timezone or None,
            min_budget=min_budget if min_budget > 0 else None,
            max_budget=max_budget if max_budget > 0 else None,
            limit=limit,
        )
    finally:
        service.close()

    if not rows:
        st.info("No RFPs found with current filters.")
        return

    display = []
    for row in rows:
        display.append(
            {
                "ID": row.get("id"),
                "Title": row.get("title"),
                "Budget": row.get("budget"),
                "Max Rate": row.get("max_rate"),
                "Team Size": row.get("team_size"),
                "Duration": row.get("duration_weeks"),
                "Seniority": row.get("required_seniority"),
                "Timezone": row.get("timezone"),
                "Skills": ", ".join(sorted(row.get("skills") or [])),
            }
        )
    st.dataframe(display, use_container_width=True)
