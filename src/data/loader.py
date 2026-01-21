import json
import os
from typing import Dict, List

from neo4j import GraphDatabase

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

class GraphLoader:
    def __init__(self, uri, auth):
        self.driver = GraphDatabase.driver(uri, auth=auth)

    def close(self):
        self.driver.close()

    def clean_db(self):
        print("Cleaning database...")
        with self.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
        print("Database cleaned.")

    def create_constraints(self):
        print("Creating constraints...")
        with self.driver.session() as session:
            session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (p:Person) REQUIRE p.id IS UNIQUE")
            session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (r:RFP) REQUIRE r.id IS UNIQUE")
            session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (s:Skill) REQUIRE s.name IS UNIQUE")
            session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (c:Company) REQUIRE c.name IS UNIQUE")
            session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (p:Project) REQUIRE p.name IS UNIQUE")

    INDUSTRY_MAP = {
        "TechGlobal": "FinTech",
        "InnovateX": "Healthcare",
        "CloudWorks": "Cloud Services",
        "GreenEnergy": "Energy",
        "AutoDrive": "Automotive",
        "CyberShield": "Security",
        "RetailGiant": "Retail",
        "EduTech": "Education",
        "MediaStream": "Entertainment",
        "LogisticsCo": "Logistics"
    }

    def load_candidates(self, candidates: List[Dict]):
        print(f"Loading {len(candidates)} candidates...")
        with self.driver.session() as session:
            for c in candidates:
                session.run("""
                    MERGE (p:Person {id: $id})
                    SET p.name = $name, 
                        p.email = $email, 
                        p.location = $location,
                        p.hourly_rate = $hourly_rate,
                        p.phone = $phone,
                        p.timezone = $timezone,
                        p.seniority = $seniority,
                        p.years_experience = $years_experience
                """, id=c["id"], name=c["name"], email=c["email"],
                   location=c["location"], hourly_rate=c.get("hourly_rate"),
                   phone=c.get("phone"), timezone=c.get("timezone"),
                   seniority=c.get("seniority"), years_experience=c.get("years_experience"))

                for skill in c.get("skills", []):
                    session.run("""
                        MATCH (p:Person {id: $pid})
                        MERGE (s:Skill {name: $skill_name})
                        SET s.category = $category
                        MERGE (p)-[r:HAS_SKILL]->(s)
                        SET r.proficiency = $proficiency
                    """, pid=c["id"], skill_name=skill["name"],
                       category=skill.get("category"), proficiency=skill["proficiency"])

                for exp in c.get("experience", []):
                    industry = self.INDUSTRY_MAP.get(exp["company"], "Technology")
                    session.run("""
                        MATCH (p:Person {id: $pid})
                        MERGE (c:Company {name: $company})
                        SET c.industry = $industry
                        MERGE (p)-[r:WORKED_AT {role: $role, start_date: $start_date}]->(c)
                        SET r.end_date = $end_date,
                            r.description = $description
                    """, pid=c["id"], company=exp["company"], role=exp["role"],
                       start_date=exp["start_date"], end_date=exp["end_date"],
                       description=exp["description"], industry=industry)

                for proj in c.get("projects", []):
                    session.run("""
                        MATCH (p:Person {id: $pid})
                        MERGE (pr:Project {name: $pname})
                        SET pr.description = $desc
                        MERGE (p)-[:WORKED_ON]->(pr)
                        
                        WITH pr
                        UNWIND $tech_stack AS tech
                        MERGE (s:Skill {name: tech})
                        MERGE (pr)-[:USES]->(s)
                    """, pid=c["id"], pname=proj["name"], desc=proj["description"],
                       tech_stack=proj["tech_stack"])

                for assign in c.get("assignments", []):
                    session.run("""
                        MATCH (p:Person {id: $pid})
                        MERGE (pr:Project {name: $pname})
                        SET pr.type = 'Active Assignment'
                        MERGE (p)-[r:ASSIGNED_TO]->(pr)
                        SET r.allocation = $allocation,
                            r.start_date = $start_date,
                            r.end_date = $end_date
                    """, pid=c["id"], pname=assign["project_name"],
                       allocation=assign["allocation"],
                       start_date=assign["start_date"],
                       end_date=assign["end_date"])

                for cert in c.get("certifications", []):
                    session.run("""
                        MATCH (p:Person {id: $pid})
                        MERGE (c:Certification {name: $name, provider: $provider})
                        SET c.date_earned = $date_earned,
                            c.expiry_date = $expiry_date
                        MERGE (p)-[:EARNED]->(c)
                    """, pid=c["id"], name=cert["name"], provider=cert.get("provider"),
                       date_earned=cert.get("date_earned"), expiry_date=cert.get("expiry_date"))

                for edu in c.get("education", []):
                    session.run("""
                        MATCH (p:Person {id: $pid})
                        MERGE (u:University {name: $name})
                        SET u.location = $location
                        MERGE (p)-[r:STUDIED_AT]->(u)
                        SET r.degree = $degree,
                            r.field = $field,
                            r.graduation_year = $graduation_year,
                            r.gpa = $gpa
                    """, pid=c["id"], name=edu["university"], location=edu.get("location"),
                       degree=edu.get("degree"), field=edu.get("field"),
                       graduation_year=edu.get("graduation_year"), gpa=edu.get("gpa"))

    def load_rfps(self, rfps: List[Dict]):
        print(f"Loading {len(rfps)} RFPs...")
        with self.driver.session() as session:
            for r in rfps:
                session.run("""
                    MERGE (r:RFP {id: $id})
                    SET r.title = $title,
                        r.description = $desc,
                        r.budget = $budget,
                        r.max_rate = $max_rate,
                        r.start_date = $start_date,
                        r.end_date = $end_date,
                        r.duration_weeks = $duration_weeks,
                        r.team_size = $team_size,
                        r.required_seniority = $required_seniority,
                        r.min_years_experience = $min_years_experience,
                        r.availability_min_pct = $availability_min_pct,
                        r.timezone = $timezone
                """, id=r["id"], title=r["title"], desc=r["description"],
                   budget=r["budget"], max_rate=r.get("max_rate"),
                   start_date=r.get("start_date"), end_date=r.get("end_date"),
                   duration_weeks=r.get("duration_weeks"), team_size=r.get("team_size"),
                   required_seniority=r.get("required_seniority"),
                   min_years_experience=r.get("min_years_experience"),
                   availability_min_pct=r.get("availability_min_pct"),
                   timezone=r.get("timezone"))

                for skill in r.get("required_skills", []):
                    session.run("""
                        MATCH (r:RFP {id: $rid})
                        MERGE (s:Skill {name: $skill_name})
                        SET s.category = $category
                        MERGE (r)-[rel:NEEDS]->(s)
                    SET rel.proficiency = $proficiency,
                        rel.min_years_experience = $min_years_experience,
                        rel.required_count = $required_count
                """, rid=r["id"], skill_name=skill["name"], category=skill.get("category"),
                   proficiency=skill.get("proficiency"),
                   min_years_experience=skill.get("min_years_experience"),
                   required_count=skill.get("required_count", 1))

if __name__ == "__main__":
    import sys

    CANDIDATES_FILE = "data/raw/candidates.json"
    RFPS_FILE = "data/raw/rfps.json"

    if not os.path.exists(CANDIDATES_FILE) or not os.path.exists(RFPS_FILE):
        print("Data files not found. Run generator first.")
        sys.exit(1)

    loader = GraphLoader(NEO4J_URI, (NEO4J_USER, NEO4J_PASSWORD))
    
    try:
        with open(CANDIDATES_FILE, 'r') as f:
            candidates_data = json.load(f)
        with open(RFPS_FILE, 'r') as f:
            rfps_data = json.load(f)

        loader.clean_db()
        loader.create_constraints()
        loader.load_candidates(candidates_data)
        loader.load_rfps(rfps_data)
        
        print("Ingestion Complete.")
        
    except Exception as e:
        print(f"Error during ingestion: {e}")
    finally:
        loader.close()
