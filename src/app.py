import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve()
for parent in REPO_ROOT.parents:
    if (parent / "pyproject.toml").exists():
        if str(parent) not in sys.path:
            sys.path.insert(0, str(parent))
        break

import streamlit as st
from src.ui import chat, forms, generator_ui, dashboard, candidates_browser, rfp_browser

st.set_page_config(
    page_title="TalentMatch AI",
    layout="wide"
)

# Sidebar Navigation
with st.sidebar:
    st.title("AIMatcheME")
    page = st.radio("Navigation", ["Chat Assistant", "Candidate Browser", "RFP Browser", "BI Dashboard", "Add Data", "Generator"])
    st.divider()
    st.caption("v0.5.1 - Stage 5")

# Routing
if page == "Chat Assistant":
    chat.render()
elif page == "Candidate Browser":
    candidates_browser.render()
elif page == "RFP Browser":
    rfp_browser.render()
elif page == "BI Dashboard":
    dashboard.render()
elif page == "Add Data":
    forms.render()
elif page == "Generator":
    generator_ui.render()
