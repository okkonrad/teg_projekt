import sys
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve()
for parent in REPO_ROOT.parents:
    if (parent / "pyproject.toml").exists():
        if str(parent) not in sys.path:
            sys.path.insert(0, str(parent))
        break

import streamlit as st
from src.services.graph_service import GraphService

TIMEZONES = ["", "UTC-8", "UTC-5", "UTC+0", "UTC+1", "UTC+2"]
SENIORITIES = ["", "Junior", "Mid", "Senior", "Lead"]


def _parse_skills(raw: str) -> list[dict]:
    skills = []
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        if ":" in token:
            name, prof = token.split(":", 1)
            skills.append({"name": name.strip(), "proficiency": prof.strip() or "Intermediate"})
        else:
            skills.append({"name": token, "proficiency": "Intermediate"})
    return skills


def _parse_list(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def render():
    st.header("Add Data")
    
    tab1, tab2, tab3 = st.tabs(["Add Candidate", "Add RFP", "Seed Data"])
    service = GraphService()

    try:
        with tab1:
            with st.form("add_candidate_form"):
                st.subheader("New Candidate Profile")
                c_name = st.text_input("Full Name")
                c_email = st.text_input("Email")
                c_phone = st.text_input("Phone (optional)")
                c_rate = st.number_input("Hourly Rate ($)", min_value=10.0, value=100.0)
                c_loc = st.text_input("Location", "Remote")
                c_timezone = st.selectbox("Timezone", TIMEZONES, index=0)
                c_seniority = st.selectbox("Seniority", SENIORITIES, index=0)
                c_years = st.number_input("Years of Experience", min_value=0.0, value=3.0, step=0.5)

                st.divider()
                st.caption("Skills")
                skills_input = st.text_area(
                    "Skills (comma separated, optional proficiency with ':', e.g. Python:Advanced, Neo4j)"
                )

                submitted = st.form_submit_button("Create Candidate")
                if submitted:
                    if c_name and c_email:
                        cand_data = {
                            "id": str(uuid.uuid4()),
                            "name": c_name,
                            "email": c_email,
                            "phone": c_phone or None,
                            "hourly_rate": c_rate,
                            "location": c_loc,
                            "timezone": c_timezone or None,
                            "seniority": c_seniority or None,
                            "years_experience": c_years,
                            "skills": _parse_skills(skills_input),
                        }
                        service.add_candidate(cand_data)
                        st.success(f"Candidate {c_name} added to the Graph!")
                        st.warning(
                            "Note: You may need to re-run 'Prep Vectors' script to make them searchable in RAG mode."
                        )
                    else:
                        st.error("Name and email are required.")

        with tab2:
            with st.form("add_rfp_form"):
                st.subheader("New Request for Proposal")
                r_title = st.text_input("Project Title")
                r_budget = st.number_input("Total Budget ($)", value=50000)
                r_desc = st.text_area("Description")
                r_max_rate = st.number_input("Max Hourly Rate ($)", value=150.0)
                r_team_size = st.number_input("Team Size", min_value=1, value=3)
                r_duration = st.number_input("Duration (weeks)", min_value=1, value=8)
                r_required_seniority = st.selectbox("Required Seniority", SENIORITIES, index=0)
                r_min_years = st.number_input("Min Years Experience", min_value=0.0, value=2.0, step=0.5)
                r_availability = st.number_input("Min Availability %", min_value=1, max_value=100, value=50)
                r_timezone = st.selectbox("Timezone", TIMEZONES, index=0)
                r_start_date = st.text_input("Start Date (YYYY-MM-DD)", "")
                r_end_date = st.text_input("End Date (YYYY-MM-DD)", "")

                st.divider()
                req_skills = st.text_input("Required Skills (comma separated, optional ':proficiency')")
                pref_skills = st.text_input("Preferred Skills (comma separated, optional ':proficiency')")
                req_certs = st.text_input("Required Certifications (comma separated)")
                pref_certs = st.text_input("Preferred Certifications (comma separated)")

                submitted_rfp = st.form_submit_button("Create RFP")
                if submitted_rfp:
                    if r_title:
                        rfp_data = {
                            "id": str(uuid.uuid4()),
                            "title": r_title,
                            "budget": r_budget,
                            "description": r_desc,
                            "required_skills": _parse_skills(req_skills),
                            "preferred_skills": _parse_skills(pref_skills),
                            "required_certifications": _parse_list(req_certs),
                            "preferred_certifications": _parse_list(pref_certs),
                            "start_date": r_start_date or None,
                            "end_date": r_end_date or None,
                            "duration_weeks": int(r_duration),
                            "team_size": int(r_team_size),
                            "required_seniority": r_required_seniority or None,
                            "min_years_experience": r_min_years,
                            "availability_min_pct": int(r_availability),
                            "timezone": r_timezone or None,
                            "max_rate": r_max_rate,
                        }
                        service.add_rfp(rfp_data)
                        st.success(f"RFP '{r_title}' created!")
                    else:
                        st.error("Title is required.")

        with tab3:
            st.subheader("Seed sample data")
            st.caption("Generates sample candidates and RFPs and loads them into Neo4j.")
            seed_candidates = st.number_input("Candidates", min_value=5, max_value=200, value=30)
            seed_rfps = st.number_input("RFPs", min_value=1, max_value=20, value=5)
            if st.button("Seed now"):
                try:
                    from src.data.generator import DataGenerator
                    from src.data.loader import GraphLoader, NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

                    gen = DataGenerator()
                    candidates = [gen.generate_candidate().model_dump() for _ in range(int(seed_candidates))]
                    rfps = [gen.generate_rfp().model_dump() for _ in range(int(seed_rfps))]
                    loader = GraphLoader(NEO4J_URI, (NEO4J_USER, NEO4J_PASSWORD))
                    try:
                        loader.load_candidates(candidates)
                        loader.load_rfps(rfps)
                    finally:
                        loader.close()
                    st.success(f"Seeded {len(candidates)} candidates and {len(rfps)} RFPs.")
                except Exception as exc:
                    st.error(f"Seed failed: {exc}")
    finally:
        service.close()
