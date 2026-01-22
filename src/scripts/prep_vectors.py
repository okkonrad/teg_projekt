import os
import sys
from pathlib import Path

from neo4j import GraphDatabase

REPO_ROOT = Path(__file__).resolve()
for parent in REPO_ROOT.parents:
    if (parent / "pyproject.toml").exists():
        if str(parent) not in sys.path:
            sys.path.insert(0, str(parent))
        break

from src.engine.vector_ops import VectorService

def prepare_candidate_embeddings():
    print("Initializing Vector Service...")
    vs = VectorService()
    
    try:
        # 1. Create Index
        vs.create_vector_index()

        # 2. Fetch all candidates with full details
        # We need a custom query to get skills, experience, etc. 
        # For simplicity, let's reuse the graph structure.
        print("Fetching candidates from Graph...")
        
        candidates_data = []
        
        with vs.driver.session() as session:
            # Fetch basic info
            result = session.run("MATCH (p:Person) RETURN p.id as id, p.name as name, p.location as location, p.hourly_rate as hourly_rate")
            for record in result:
                cand = record.data()
                
                # Fetch Skills
                skills_res = session.run("""
                    MATCH (p:Person {id: $id})-[r:HAS_SKILL]->(s:Skill)
                    RETURN s.name as name, r.proficiency as proficiency
                """, id=cand['id'])
                cand['skills'] = [r.data() for r in skills_res]
                
                # Fetch Experience
                exp_res = session.run("""
                    MATCH (p:Person {id: $id})-[r:WORKED_AT]->(c:Company)
                    RETURN c.name as company, r.role as role, r.start_date as start_date, r.end_date as end_date
                """, id=cand['id'])
                cand['experience'] = [r.data() for r in exp_res]
                
                # Fetch Projects
                proj_res = session.run("""
                    MATCH (p:Person {id: $id})-[r:WORKED_ON]->(proj:Project)
                    RETURN proj.name as name, proj.description as description
                """, id=cand['id'])
                cand['projects'] = [r.data() for r in proj_res]
                
                candidates_data.append(cand)

        print(f"Found {len(candidates_data)} candidates. Generating embeddings (this calls OpenAI)...")
        
        count = 0
        for cand in candidates_data:
            # Flatten
            text = vs.flatten_candidate_to_text(cand)
            
            # Embed
            embedding = vs.generate_embedding(text)
            
            # Update
            vs.update_candidate_embedding(cand['id'], text, embedding)
            
            count += 1
            if count % 10 == 0:
                print(f"Processed {count}/{len(candidates_data)}...")

        print("Vector preparation complete!")

    except Exception as e:
        print(f"Error: {e}")
        raise
    finally:
        vs.close()

if __name__ == "__main__":
    main()
