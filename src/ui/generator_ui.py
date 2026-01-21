import importlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve()
for parent in REPO_ROOT.parents:
    if (parent / "pyproject.toml").exists():
        if str(parent) not in sys.path:
            sys.path.insert(0, str(parent))
        break

import streamlit as st
from src.data.generator import DataGenerator
from src.data.loader import GraphLoader, NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

def render():
    st.header("World Generator")
    st.warning("WARNING: This will wipe the existing database and generate a new synthetic world.")

    with st.form("generator_form"):
        num_cands = st.slider("Number of Candidates", 10, 200, 50)
        num_rfps = st.slider("Number of RFPs", 1, 20, 5)
        
        c_min = st.number_input("Min Hourly Rate", value=50.0)
        c_max = st.number_input("Max Hourly Rate", value=200.0)
        
        seed = st.number_input("Random Seed", value=42)
        
        submit = st.form_submit_button("Destroy, Regenerate & Load")
    
    if submit:
        status = st.empty()
        status.info("Initializing Generator...")
        
        try:
            # 1. Generate JSON
            gen = DataGenerator(seed=seed)
            # Monkey-patch bounds if needed or update generator class to accept them dynamically
            # For now simplified call
            gen.generate_corpus(num_candidates=num_cands, num_rfps=num_rfps)
            status.info("JSON Data Generated. Loading into Neo4j...")
            
            # 2. Load to Graph
            loader = GraphLoader(NEO4J_URI, (NEO4J_USER, NEO4J_PASSWORD))
            with open('data/raw/candidates.json', 'r') as f:
                c_data = json.load(f)
            with open('data/raw/rfps.json', 'r') as f:
                r_data = json.load(f)
            
            loader.clean_db()
            loader.create_constraints()
            loader.load_candidates(c_data)
            loader.load_rfps(r_data)
            loader.close()
            
            status.success(f"Successfully generated {num_cands} candidates and {num_rfps} RFPs!")
            
        except Exception as e:
            st.error(f"Error: {e}")
