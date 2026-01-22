import sys
from pathlib import Path
from typing import List

REPO_ROOT = Path(__file__).resolve()
for parent in REPO_ROOT.parents:
    if (parent / "pyproject.toml").exists():
        if str(parent) not in sys.path:
            sys.path.insert(0, str(parent))
        break

import streamlit as st
from src.domain.schemas import Candidate, RFP
from src.data import DataGenerator
from src.data import GraphLoader

def render():
    st.header("Candidated and RFP Generator")
    st.warning("WARNING: This will wipe the existing database and generate a new synthetic world.")

    with st.form("generator_form"):
        num_cands = st.slider("Number of Candidates", 10, 200, 50)
        num_rfps = st.slider("Number of RFPs", 1, 20, 5)

        # Parameter not used so I will hide it ~ JO
        # c_min = st.number_input("Min Hourly Rate", value=50.0)
        # c_max = st.number_input("Max Hourly Rate", value=200.0)
        
        seed = st.number_input("Random Seed", value=42)
        submit = st.form_submit_button("Destroy, Regenerate & Load")
    
    if submit:
        status = st.empty()
        status.info("Initializing Generator...")
        
        try:
            generator = DataGenerator(seed=seed)
            candidates: List[Candidate] = [generator.generate_candidate() for _ in range(num_cands)]
            status.info(f"Generating candidated and rfps, please be patient...")
            rpfs: List[RFP] = [generator.generate_rfp() for _ in range(num_rfps)]
            # status.info(f"{len(rpfs)} RFPs generated.")

            loader = GraphLoader()
            try:
                loader.clean_db()
                loader.create_constraints()
                loader.load_candidates_from_model(candidates)
                loader.load_rfps_from_model(rpfs)
            except Exception as e:
                status.error(f"Could not load candidated to the Neo4j: {e}")
            finally:
                if loader is not None:
                    loader.close()
            status.success(f"Successfully generated {num_cands} candidates and {num_rfps} RFPs!")
            
        except Exception as e:
            status.error(f"Error: {e}")
