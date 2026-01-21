import os
from typing import Dict, List

from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from neo4j import GraphDatabase

load_dotenv()

class VectorService:
    def __init__(self):
        self.embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small",
            api_key=os.getenv("OPENAI_API_KEY")
        )
        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        user = os.getenv("NEO4J_USERNAME", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "password")
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def flatten_candidate_to_text(self, candidate: Dict) -> str:
        text_parts = [
            f"Candidate: {candidate['name']}.",
            f"Location: {candidate['location']}.",
            f"Rate: ${candidate.get('hourly_rate', 'N/A')}/hr."
        ]

        if candidate.get("skills"):
            skills_str = ", ".join(
                [f"{s['name']} ({s['proficiency']})" for s in candidate["skills"]]
            )
            text_parts.append(f"Skills: {skills_str}.")

        if candidate.get("experience"):
            exp_parts = []
            for exp in candidate["experience"]:
                exp_parts.append(f"Worked at {exp['company']} as {exp['role']} ({exp['start_date']} to {exp['end_date']})")
            text_parts.append("Experience: " + "; ".join(exp_parts) + ".")

        if candidate.get("projects"):
            proj_parts = []
            for proj in candidate["projects"]:
                proj_parts.append(f"Project '{proj['name']}': {proj['description']}")
            text_parts.append("Projects: " + "; ".join(proj_parts) + ".")

        return " ".join(text_parts)

    def generate_embedding(self, text: str) -> List[float]:
        return self.embeddings.embed_query(text)

    def create_vector_index(self, index_name: str = "candidate_vectors"):
        with self.driver.session() as session:
            session.run(f"""
                CREATE VECTOR INDEX {index_name} IF NOT EXISTS
                FOR (p:Person) ON (p.embedding)
                OPTIONS {{
                    indexConfig: {{
                        `vector.dimensions`: 1536,
                        `vector.similarity_function`: 'cosine'
                    }}
                }}
            """)
            print(f"Index '{index_name}' ensured.")

    def update_candidate_embedding(self, candidate_id: str, text: str, embedding: List[float]):
        with self.driver.session() as session:
            session.run("""
                MATCH (p:Person {id: $id})
                SET p.text_repr = $text,
                    p.embedding = $embedding
            """, id=candidate_id, text=text, embedding=embedding)
