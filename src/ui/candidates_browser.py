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
    st.header("Candidate Browser")
    st.caption("Browse candidates with basic filters.")

    search = st.text_input("Search by name", "")
    seniority = st.selectbox("Seniority", ["", "Junior", "Mid", "Senior", "Lead"], index=0)
    timezone = st.selectbox("Timezone", ["", "UTC-8", "UTC-5", "UTC+0", "UTC+1", "UTC+2"], index=0)
    col1, col2 = st.columns(2)
    min_rate = col1.number_input("Min rate", min_value=0.0, value=0.0, step=5.0)
    max_rate = col2.number_input("Max rate", min_value=0.0, value=0.0, step=5.0)
    limit = st.slider("Max results", min_value=10, max_value=200, value=50, step=10)

    service = GraphService()
    try:
        all_skills = service.list_all_skills()
        selected_skills = st.multiselect("Filter by skills (must include all)", all_skills)
        rows = service.list_candidates(
            search=search.strip() or None,
            skills=selected_skills or None,
            seniority=seniority or None,
            timezone=timezone or None,
            min_rate=min_rate if min_rate > 0 else None,
            max_rate=max_rate if max_rate > 0 else None,
            limit=limit,
        )
    finally:
        service.close()

    if search.strip():
        needle = search.strip().lower()
        rows = [row for row in rows if (row.get("name") or "").lower().find(needle) >= 0]

    if selected_skills:
        needles = [s.lower() for s in selected_skills]
        rows = [
            row
            for row in rows
            if all(
                any(needle in (s or "").lower() for s in (row.get("skills") or []))
                for needle in needles
            )
        ]

    if not rows:
        st.info("No candidates found with current filters.")
        return

    display = []
    for row in rows:
        display.append(
            {
                "Name": row.get("name"),
                "Seniority": row.get("seniority"),
                "Timezone": row.get("timezone"),
                "Location": row.get("location"),
                "Rate": row.get("hourly_rate"),
                "Skills": ", ".join(sorted(row.get("skills") or [])),
            }
        )
    st.dataframe(display, use_container_width=True)
