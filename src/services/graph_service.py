import os
from dotenv import load_dotenv
from typing import Dict, List, Optional
from neo4j import GraphDatabase

load_dotenv()

class GraphService:
    def __init__(self):
        self.uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.user = os.getenv("NEO4J_USERNAME", "neo4j")
        self.password = os.getenv("NEO4J_PASSWORD", "password")
        self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))

    def close(self):
        self.driver.close()

    def _run(self, query: str, **params) -> List[Dict]:
        with self.driver.session() as session:
            result = session.run(query, **params)
            return [record.data() for record in result]

    def _one(self, query: str, **params) -> Optional[Dict]:
        with self.driver.session() as session:
            record = session.run(query, **params).single()
            return record.data() if record else None

    def get_all_rfps(self) -> List[Dict]:
        return self._run("""
            MATCH (r:RFP)
            RETURN r.id as id, r.title as title, r.budget as budget
        """)

    def get_rfp_details(self, rfp_id: str) -> Optional[Dict]:
        rfp_data = self._one("""
            MATCH (r:RFP {id: $rfp_id})
            RETURN r.id as id, r.title as title, r.budget as budget, r.description as description,
                   r.max_rate as max_rate, r.start_date as start_date, r.end_date as end_date,
                   r.duration_weeks as duration_weeks, r.team_size as team_size,
                   r.required_seniority as required_seniority, r.min_years_experience as min_years_experience,
                   r.availability_min_pct as availability_min_pct, r.timezone as timezone
        """, rfp_id=rfp_id)
        if not rfp_data:
            return None
        rfp_data["skills"] = self._run("""
            MATCH (r:RFP {id: $rfp_id})-[rel:NEEDS]->(s:Skill)
            RETURN s.name as name, rel.proficiency as proficiency, s.category as category
        """, rfp_id=rfp_id)
        return rfp_data

    def find_candidates_with_overlapping_skills(self, rfp_skills: List[str]) -> List[Dict]:
        return self._run("""
            MATCH (c:Person)-[has:HAS_SKILL]->(s:Skill)
            WHERE s.name IN $skill_names
            WITH c, collect({name: s.name, proficiency: has.proficiency}) as matched_skills
            RETURN c.id as id, c.name as name, c.location as location, c.hourly_rate as hourly_rate, matched_skills
        """, skill_names=rfp_skills)

    def get_candidate_allocation(self, candidate_id: str, as_of_date: Optional[str] = None) -> int:
        with self.driver.session() as session:
            query = """
                MATCH (p:Person {id: $pid})-[r:ASSIGNED_TO]->(:Project)
                WHERE r.start_date IS NOT NULL AND r.end_date IS NOT NULL
                  AND date(r.start_date) <= date($as_of)
                  AND date(r.end_date) >= date($as_of)
                RETURN coalesce(sum(r.allocation), 0) as allocation
            """
            params = {
                "pid": candidate_id,
                "as_of": as_of_date or str(session.run("RETURN date() as d").single()["d"]),
            }
            result = session.run(query, **params).single()
            return int(result["allocation"]) if result else 0

    def is_candidate_available(
        self,
        candidate_id: str,
        min_available_pct: Optional[int] = None,
        as_of_date: Optional[str] = None,
    ) -> bool:
        allocation = self.get_candidate_allocation(candidate_id, as_of_date=as_of_date)
        available_pct = max(0, 100 - allocation)
        required = min_available_pct if min_available_pct is not None else 1
        return available_pct >= required

    def add_candidate(self, c: Dict):
        with self.driver.session() as session:
            session.run("""
                MERGE (p:Person {id: $id})
                SET p.name = $name, p.hourly_rate = $hourly_rate, p.location = $location,
                    p.phone = $phone, p.timezone = $timezone, p.seniority = $seniority,
                    p.years_experience = $years_experience
            """, id=c["id"], name=c["name"], hourly_rate=c.get("hourly_rate"),
               location=c.get("location", "Remote"), phone=c.get("phone"),
               timezone=c.get("timezone"), seniority=c.get("seniority"),
               years_experience=c.get("years_experience"))

            for skill in c.get("skills", []):
                session.run("""
                    MATCH (p:Person {id: $pid})
                    MERGE (s:Skill {name: $skill_name})
                    MERGE (p)-[:HAS_SKILL {proficiency: $proficiency}]->(s)
                """, pid=c["id"], skill_name=skill["name"],
                   proficiency=skill.get("proficiency", "Intermediate"))

    def add_rfp(self, r: Dict):
        with self.driver.session() as session:
            session.run("""
                MERGE (r:RFP {id: $id})
                SET r.title = $title, r.budget = $budget, r.description = $desc,
                    r.max_rate = $max_rate, r.start_date = $start_date, r.end_date = $end_date,
                    r.duration_weeks = $duration_weeks, r.team_size = $team_size,
                    r.required_seniority = $required_seniority, r.min_years_experience = $min_years_experience,
                    r.availability_min_pct = $availability_min_pct, r.timezone = $timezone
            """, id=r["id"], title=r["title"], budget=r["budget"], desc=r.get("description", ""),
               max_rate=r.get("max_rate"), start_date=r.get("start_date"), end_date=r.get("end_date"),
               duration_weeks=r.get("duration_weeks"), team_size=r.get("team_size"),
               required_seniority=r.get("required_seniority"),
               min_years_experience=r.get("min_years_experience"),
               availability_min_pct=r.get("availability_min_pct"), timezone=r.get("timezone"))

            for skill in r.get("required_skills", []):
                session.run("""
                    MATCH (r:RFP {id: $rid})
                    MERGE (s:Skill {name: $skill_name})
                    MERGE (r)-[rel:NEEDS]->(s)
                    SET rel.proficiency = $proficiency,
                        rel.min_years_experience = $min_years_experience,
                        rel.required_count = $required_count
                """, rid=r["id"], skill_name=skill["name"],
                   proficiency=skill.get("proficiency", "Intermediate"),
                   min_years_experience=skill.get("min_years_experience"),
                   required_count=skill.get("required_count", 1))

    def get_graph_stats(self) -> Dict:
        return self._one("""
            CALL { MATCH (p:Person) RETURN count(p) as candidates }
            CALL { MATCH (r:RFP) RETURN count(r) as rfps }
            CALL { MATCH (s:Skill) RETURN count(s) as skills }
            CALL { MATCH (c:Company) RETURN count(c) as companies }
            RETURN candidates, rfps, skills, companies
        """)

    def list_all_skills(self) -> List[str]:
        skills = self._run("""
            MATCH (s:Skill)
            RETURN distinct s.name as skill
            ORDER BY skill
        """)
        return [record["skill"] for record in skills if record.get("skill")]

    def list_candidates(
        self,
        search: Optional[str] = None,
        skills: Optional[List[str]] = None,
        seniority: Optional[str] = None,
        timezone: Optional[str] = None,
        min_rate: Optional[float] = None,
        max_rate: Optional[float] = None,
        limit: int = 50,
    ) -> List[Dict]:
        query = """
            MATCH (p:Person)
            OPTIONAL MATCH (p)-[:HAS_SKILL]->(s:Skill)
        """
        filters = []
        params: Dict = {"limit": limit}
        if search:
            filters.append("toLower(p.name) CONTAINS toLower($search)")
            params["search"] = search
        if seniority:
            filters.append("p.seniority = $seniority")
            params["seniority"] = seniority
        if timezone:
            filters.append("p.timezone = $timezone")
            params["timezone"] = timezone
        if min_rate is not None:
            filters.append("p.hourly_rate >= $min_rate")
            params["min_rate"] = min_rate
        if max_rate is not None:
            filters.append("p.hourly_rate <= $max_rate")
            params["max_rate"] = max_rate
        if filters:
            query += "WHERE " + " AND ".join(filters) + "\n"
        query += """
            WITH p, collect(distinct s.name) as skills
        """
        if skills:
            query += "WHERE all(req IN $skills WHERE req IN skills)\n"
            params["skills"] = skills
        query += """
            RETURN p.id as id, p.name as name, p.seniority as seniority,
                   p.timezone as timezone, p.location as location,
                   p.hourly_rate as hourly_rate, skills
            ORDER BY p.name
            LIMIT $limit
        """
        return self._run(query, **params)

    def list_rfps(
        self,
        search: Optional[str] = None,
        skills: Optional[List[str]] = None,
        seniority: Optional[str] = None,
        timezone: Optional[str] = None,
        min_budget: Optional[float] = None,
        max_budget: Optional[float] = None,
        limit: int = 50,
    ) -> List[Dict]:
        query = """
            MATCH (r:RFP)
            OPTIONAL MATCH (r)-[:NEEDS]->(s:Skill)
        """
        filters = []
        params: Dict = {"limit": limit}
        if search:
            filters.append(
                "toLower(r.title) CONTAINS toLower($search) "
                "OR toLower(r.description) CONTAINS toLower($search)"
            )
            params["search"] = search
        if seniority:
            filters.append("r.required_seniority = $seniority")
            params["seniority"] = seniority
        if timezone:
            filters.append("r.timezone = $timezone")
            params["timezone"] = timezone
        if min_budget is not None:
            filters.append("r.budget >= $min_budget")
            params["min_budget"] = min_budget
        if max_budget is not None:
            filters.append("r.budget <= $max_budget")
            params["max_budget"] = max_budget
        if filters:
            query += "WHERE " + " AND ".join(filters) + "\n"
        query += """
            WITH r, collect(distinct s.name) as skills
        """
        if skills:
            query += "WHERE all(req IN $skills WHERE req IN skills)\n"
            params["skills"] = skills
        query += """
            RETURN r.id as id, r.title as title, r.budget as budget,
                   r.max_rate as max_rate, r.team_size as team_size,
                   r.duration_weeks as duration_weeks,
                   r.required_seniority as required_seniority,
                   r.timezone as timezone, skills
            ORDER BY r.title
            LIMIT $limit
        """
        return self._run(query, **params)

    def count_available_candidates(self, skill_name: str) -> int:
        result = self._one("""
            MATCH (p:Person)-[:HAS_SKILL]->(s:Skill {name: $skill})
            OPTIONAL MATCH (p)-[r:ASSIGNED_TO]->(:Project)
            WHERE r.start_date IS NOT NULL AND r.end_date IS NOT NULL
              AND date(r.start_date) <= date()
              AND date(r.end_date) >= date()
            WITH p, sum(coalesce(r.allocation, 0)) as alloc
            WHERE alloc < 100
            RETURN count(distinct p) as count
        """, skill=skill_name)
        return result["count"] if result else 0

    def count_candidates_by_skill(self, skill_name: str) -> int:
        result = self._one("""
            MATCH (p:Person)-[:HAS_SKILL]->(s:Skill {name: $skill})
            RETURN count(distinct p) as count
        """, skill=skill_name)
        return result["count"] if result else 0

    def count_candidates_with_skills(self, skills: List[str]) -> int:
        result = self._one("""
            MATCH (p:Person)-[:HAS_SKILL]->(s:Skill)
            WHERE s.name IN $skills
            WITH p, collect(distinct s.name) as skill_names
            WHERE all(req IN $skills WHERE req IN skill_names)
            RETURN count(distinct p) as count
        """, skills=skills)
        return result["count"] if result else 0

    def count_available_candidates_on_date(
        self, as_of_date: str, skill_name: Optional[str] = None
    ) -> int:
        query = """
            MATCH (p:Person)
            OPTIONAL MATCH (p)-[r:ASSIGNED_TO]->(:Project)
            WHERE r.start_date IS NOT NULL AND r.end_date IS NOT NULL
              AND date(r.start_date) <= date($as_of)
              AND date(r.end_date) >= date($as_of)
            WITH p, sum(coalesce(r.allocation), 0) as alloc
            WHERE alloc < 100
        """
        if skill_name:
            query += """
            MATCH (p)-[:HAS_SKILL]->(s:Skill {name: $skill})
            RETURN count(distinct p) as count
            """
        else:
            query += "RETURN count(distinct p) as count"
        result = self._one(query, as_of=as_of_date, skill=skill_name)
        return result["count"] if result else 0

    def count_available_candidates_next_month(self, skill_name: Optional[str] = None) -> int:
        query = """
            WITH date() + duration('P1M') as target
            MATCH (p:Person)
            OPTIONAL MATCH (p)-[r:ASSIGNED_TO]->(:Project)
            WHERE r.start_date IS NOT NULL AND r.end_date IS NOT NULL
              AND date(r.start_date) <= target
              AND date(r.end_date) >= target
            WITH p, sum(coalesce(r.allocation), 0) as alloc
            WHERE alloc < 100
        """
        if skill_name:
            query += """
            MATCH (p)-[:HAS_SKILL]->(s:Skill {name: $skill})
            RETURN count(distinct p) as count
            """
        else:
            query += "RETURN count(distinct p) as count"
        result = self._one(query, skill=skill_name)
        return result["count"] if result else 0

    def count_available_candidates_now(self, skill_name: Optional[str] = None) -> int:
        query = """
            WITH date() as target
            MATCH (p:Person)
            OPTIONAL MATCH (p)-[r:ASSIGNED_TO]->(:Project)
            WHERE r.start_date IS NOT NULL AND r.end_date IS NOT NULL
              AND date(r.start_date) <= target
              AND date(r.end_date) >= target
            WITH p, coalesce(sum(r.allocation), 0) as alloc
            WHERE alloc < 100
        """
        if skill_name:
            query += """
            MATCH (p)-[:HAS_SKILL]->(s:Skill {name: $skill})
            RETURN count(distinct p) as count
            """
        else:
            query += "RETURN count(distinct p) as count"
        result = self._one(query, skill=skill_name)
        return result["count"] if result else 0

    def get_top_skills(self, limit: int = 5) -> List[str]:
        records = self._run("""
            MATCH (p:Person)-[:HAS_SKILL]->(s:Skill)
            RETURN s.name as skill, count(distinct p) as count
            ORDER BY count DESC
            LIMIT $limit
        """, limit=limit)
        return [record["skill"] for record in records]

    def get_top_skills_with_counts(self, limit: int = 5) -> List[Dict]:
        return self._run("""
            MATCH (p:Person)-[:HAS_SKILL]->(s:Skill)
            RETURN s.name as skill, count(distinct p) as count
            ORDER BY count DESC
            LIMIT $limit
        """, limit=limit)

    def count_candidates_with_certification(self, cert_name: str) -> int:
        result = self._one("""
            MATCH (p:Person)-[:EARNED]->(c:Certification {name: $name})
            RETURN count(distinct p) as count
        """, name=cert_name)
        return result["count"] if result else 0

    def count_candidates_by_university(self, university_name: str) -> int:
        result = self._one("""
            MATCH (p:Person)-[:STUDIED_AT]->(u:University {name: $name})
            RETURN count(distinct p) as count
        """, name=university_name)
        return result["count"] if result else 0

    def find_candidates_with_skills_and_seniority(
        self, skills: List[str], seniorities: List[str]
    ) -> List[Dict]:
        return self._run("""
            MATCH (p:Person)-[:HAS_SKILL]->(s:Skill)
            WHERE s.name IN $skills AND p.seniority IN $seniorities
            WITH p, collect(distinct s.name) as skill_names
            WHERE all(req IN $skills WHERE req IN skill_names)
            RETURN p.id as id, p.name as name, p.seniority as seniority
            ORDER BY p.name
        """, skills=skills, seniorities=seniorities)

    def list_available_candidates_by_timezone(self, timezone: str) -> List[Dict]:
        return self._run("""
            WITH date() as target
            MATCH (p:Person {timezone: $timezone})
            OPTIONAL MATCH (p)-[r:ASSIGNED_TO]->(:Project)
            WHERE r.start_date IS NOT NULL AND r.end_date IS NOT NULL
              AND date(r.start_date) <= target
              AND date(r.end_date) >= target
            WITH p, coalesce(sum(r.allocation), 0) as alloc
            WHERE alloc < 100
            RETURN p.id as id, p.name as name, p.timezone as timezone,
                   alloc as allocation_pct, (100 - alloc) as available_pct
            ORDER BY available_pct DESC, p.name
        """, timezone=timezone)

    def average_years_experience_for_ml_projects(self) -> Optional[float]:
        result = self._one("""
            MATCH (p:Person)-[:WORKED_ON]->(pr:Project)-[:USES]->(s:Skill)
            WHERE s.name IN ['TensorFlow', 'Machine Learning', 'ML']
            RETURN avg(p.years_experience) as avg_years
        """)
        if not result or result["avg_years"] is None:
            return None
        return float(result["avg_years"])

    def total_capacity_available_for_q4(self) -> int:
        result = self._one("""
            WITH date() as today
            WITH date({year: today.year, month: 10, day: 1}) as target
            MATCH (p:Person)
            OPTIONAL MATCH (p)-[r:ASSIGNED_TO]->(:Project)
            WHERE r.start_date IS NOT NULL AND r.end_date IS NOT NULL
              AND date(r.start_date) <= target
              AND date(r.end_date) >= target
            WITH p, coalesce(sum(r.allocation), 0) as alloc
            RETURN sum(CASE WHEN alloc < 100 THEN 100 - alloc ELSE 0 END) as total_capacity
        """)
        return int(result["total_capacity"]) if result and result["total_capacity"] is not None else 0

    def list_candidates_available_after_current_project(self) -> List[Dict]:
        return self._run("""
            MATCH (p:Person)-[r:ASSIGNED_TO]->(:Project)
            WHERE r.start_date IS NOT NULL AND r.end_date IS NOT NULL
              AND date(r.start_date) <= date()
              AND date(r.end_date) >= date()
            WITH p, max(date(r.end_date)) as end_date, sum(r.allocation) as alloc
            RETURN p.id as id, p.name as name, end_date, alloc as allocation_pct
            ORDER BY end_date ASC
        """)

    def skills_distribution_by_graduation_year(self) -> List[Dict]:
        return self._run("""
            MATCH (p:Person)-[r:STUDIED_AT]->(:University)
            WHERE r.graduation_year IS NOT NULL
            MATCH (p)-[:HAS_SKILL]->(s:Skill)
            RETURN r.graduation_year as graduation_year, s.name as skill,
                   count(distinct p) as count
            ORDER BY graduation_year ASC, count DESC
        """)

    def list_collaboration_pairs(self, limit: int = 5) -> List[Dict]:
        return self._run("""
            MATCH (a:Person)-[:WORKED_AT]->(c:Company)<-[:WORKED_AT]-(b:Person)
            WHERE elementId(a) < elementId(b)
            RETURN a.name as person_a, b.name as person_b, c.name as context
            ORDER BY c.name, person_a, person_b
            LIMIT $limit
        """, limit=limit)

    def list_alumni_of_top_performers(self, top_n: int = 5, limit: int = 10) -> List[Dict]:
        return self._run("""
            MATCH (top:Person)
            WHERE top.hourly_rate IS NOT NULL
            WITH top ORDER BY top.hourly_rate DESC LIMIT $top_n
            MATCH (top)-[:STUDIED_AT]->(u:University)
            WITH collect(top) as top_people, collect(distinct u) as universities
            MATCH (p:Person)-[:STUDIED_AT]->(u:University)
            WHERE u IN universities AND NOT p IN top_people
            RETURN p.name as name, u.name as university
            ORDER BY u.name, name
            LIMIT $limit
        """, top_n=top_n, limit=limit)

    def skills_gap_analysis(self, limit: int = 5) -> List[Dict]:
        return self._run("""
            MATCH (r:RFP)-[n:NEEDS]->(s:Skill)
            WITH s.name as skill, sum(coalesce(n.required_count, 1)) as demand
            MATCH (p:Person)-[:HAS_SKILL]->(s2:Skill {name: skill})
            WITH skill, demand, count(distinct p) as supply
            WITH skill, demand, supply, (demand - supply) as gap
            WHERE gap > 0
            RETURN skill, demand, supply, gap
            ORDER BY gap DESC, demand DESC
            LIMIT $limit
        """, limit=limit)

    def risk_single_points_of_failure(self, limit: int = 5) -> List[Dict]:
        return self._run("""
            WITH date() as target
            MATCH (p:Person)-[:HAS_SKILL]->(s:Skill)
            OPTIONAL MATCH (p)-[r:ASSIGNED_TO]->(:Project)
            WHERE r.start_date IS NOT NULL AND r.end_date IS NOT NULL
              AND date(r.start_date) <= target
              AND date(r.end_date) >= target
            WITH s.name as skill, p, coalesce(sum(r.allocation), 0) as alloc
            WHERE alloc < 100
            WITH skill, count(distinct p) as available_count
            WHERE available_count = 1
            RETURN skill, available_count
            ORDER BY skill
            LIMIT $limit
        """, limit=limit)

    def recommend_team_for_fintech_rfp(self, limit: Optional[int] = None) -> List[Dict]:
        with self.driver.session() as session:
            rfp = session.run("""
                MATCH (r:RFP)
                WHERE toLower(r.title) CONTAINS 'fintech' OR toLower(r.description) CONTAINS 'fintech'
                RETURN r.id as id, r.team_size as team_size, r.max_rate as max_rate,
                       r.availability_min_pct as availability_min_pct
                ORDER BY r.team_size DESC
                LIMIT 1
            """).single()
            if not rfp:
                return []
            team_size = rfp.get("team_size") or limit or 3
            max_rate = rfp.get("max_rate")
            availability_min_pct = rfp.get("availability_min_pct") or 1

            result = session.run("""
                MATCH (r:RFP {id: $rfp_id})
                WITH r,
                     CASE
                         WHEN r.start_date IS NULL OR r.start_date = ''
                         THEN date() + duration('P1M')
                         ELSE date(r.start_date)
                     END as target
                MATCH (r)-[:NEEDS]->(req:Skill)
                MATCH (p:Person)-[:HAS_SKILL]->(s:Skill)
                WHERE s.name = req.name
                OPTIONAL MATCH (p)-[a:ASSIGNED_TO]->(:Project)
                WHERE a.start_date IS NOT NULL AND a.end_date IS NOT NULL
                  AND date(a.start_date) <= target
                  AND date(a.end_date) >= target
                WITH p, collect(distinct s.name) as matched_skills,
                     coalesce(sum(a.allocation), 0) as alloc
                WITH p, matched_skills, alloc, (100 - alloc) as available_pct
                WHERE available_pct >= $min_available
                  AND ($max_rate IS NULL OR p.hourly_rate <= $max_rate)
                RETURN p.id as id, p.name as name, p.hourly_rate as hourly_rate,
                       size(matched_skills) as match_count, available_pct
                ORDER BY match_count DESC, available_pct DESC, p.hourly_rate ASC
                LIMIT $team_size
            """, rfp_id=rfp["id"], team_size=team_size, max_rate=max_rate, min_available=availability_min_pct)
            return [record.data() for record in result]

    def total_capacity_available_for_q4_by_skill(self, limit: int = 10) -> List[Dict]:
        return self._run("""
            WITH date() as today
            WITH date({year: today.year, month: 10, day: 1}) as target
            MATCH (p:Person)-[:HAS_SKILL]->(s:Skill)
            OPTIONAL MATCH (p)-[r:ASSIGNED_TO]->(:Project)
            WHERE r.start_date IS NOT NULL AND r.end_date IS NOT NULL
              AND date(r.start_date) <= target
              AND date(r.end_date) >= target
            WITH s.name as skill, p, coalesce(sum(r.allocation), 0) as alloc
            WITH skill, sum(CASE WHEN alloc < 100 THEN 100 - alloc ELSE 0 END) as capacity
            RETURN skill, capacity
            ORDER BY capacity DESC, skill
            LIMIT $limit
        """, limit=limit)

    def average_years_experience_for_ml_projects_by_seniority(self) -> List[Dict]:
        return self._run("""
            MATCH (p:Person)-[:WORKED_ON]->(pr:Project)-[:USES]->(s:Skill)
            WHERE s.name IN ['TensorFlow', 'Machine Learning', 'ML']
            AND p.seniority IS NOT NULL AND p.years_experience IS NOT NULL
            RETURN p.seniority as seniority, avg(p.years_experience) as avg_years
            ORDER BY seniority
        """)

    def get_top_skills_in_demand(self, limit: int = 5) -> List[Dict]:
        return self._run("""
            MATCH (r:RFP)-[:NEEDS]->(s:Skill)
            RETURN s.name as skill, count(r) as demand
            ORDER BY demand DESC
            LIMIT $limit
        """, limit=limit)

    def find_collaborators(self, person_id: str) -> List[Dict]:
        return self._run("""
            MATCH (p:Person {id: $id})-[:WORKED_AT]->(c:Company)<-[:WORKED_AT]-(collab:Person)
            RETURN distinct collab.name as name, c.name as shared_company
            LIMIT 5
        """, id=person_id)

    def run_cypher_query(self, query: str) -> str:
        from langchain_community.chains.graph_qa.cypher import GraphCypherQAChain
        from langchain_community.graphs import Neo4jGraph
        from langchain_openai import ChatOpenAI

        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        user = os.getenv("NEO4J_USERNAME", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "password")

        graph = Neo4jGraph(url=uri, username=user, password=password, enhanced_schema=False)
        llm = ChatOpenAI(temperature=0, model="gpt-4o-mini")
        chain = GraphCypherQAChain.from_llm(
            llm=llm,
            graph=graph,
            verbose=True,
            allow_dangerous_requests=True,
            validate_cypher=True,
        )

        try:
            response = chain.invoke(query)
            return response.get("result", "I couldn't generate an answer.")
        except Exception as e:
            return f"Error executing Graph Query: {str(e)}"
import os
from neo4j import GraphDatabase
from typing import List, Dict, Optional

class GraphService:
    def __init__(self):
        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        user = os.getenv("NEO4J_USERNAME", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "password")
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def get_all_rfps(self) -> List[Dict]:
        """Fetch all RFPs for the UI dropdown."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (r:RFP)
                RETURN r.id as id, r.title as title, r.budget as budget
            """)
            return [record.data() for record in result]

    def get_rfp_details(self, rfp_id: str) -> Dict:
        """Fetch details and required skills for a specific RFP."""
        with self.driver.session() as session:
            # Get RFP properties
            rfp_result = session.run("""
                MATCH (r:RFP {id: $rfp_id})
                RETURN r.id as id, r.title as title, r.budget as budget, r.description as description,
                       r.max_rate as max_rate, r.start_date as start_date, r.end_date as end_date,
                       r.duration_weeks as duration_weeks, r.team_size as team_size,
                       r.required_seniority as required_seniority, r.min_years_experience as min_years_experience,
                       r.availability_min_pct as availability_min_pct, r.timezone as timezone
            """, rfp_id=rfp_id).single()
            
            if not rfp_result:
                return None

            rfp_data = rfp_result.data()

            # Get Required Skills
            skills_result = session.run("""
                MATCH (r:RFP {id: $rfp_id})-[rel:NEEDS]->(s:Skill)
                RETURN s.name as name, rel.proficiency as proficiency, s.category as category
            """, rfp_id=rfp_id)
            
            rfp_data['skills'] = [record.data() for record in skills_result]
            return rfp_data

    def find_candidates_with_overlapping_skills(self, rfp_skills: List[str]) -> List[Dict]:
        """
        Find candidates who have at least one of the required skills.
        Returns Candidate node properties and their collected skills.
        """
        with self.driver.session() as session:
            query = """
                MATCH (c:Person)-[has:HAS_SKILL]->(s:Skill)
                WHERE s.name IN $skill_names
                WITH c, collect({name: s.name, proficiency: has.proficiency}) as matched_skills
                RETURN c.id as id, c.name as name, c.location as location, c.hourly_rate as hourly_rate, matched_skills
            """
            result = session.run(query, skill_names=rfp_skills)
            return [record.data() for record in result]

    def get_candidate_allocation(self, candidate_id: str, as_of_date: Optional[str] = None) -> int:
        """Returns total allocation percentage for a candidate at a given date (YYYY-MM-DD)."""
        with self.driver.session() as session:
            query = """
                MATCH (p:Person {id: $pid})-[r:ASSIGNED_TO]->(:Project)
                WHERE r.start_date IS NOT NULL AND r.end_date IS NOT NULL
                  AND date(r.start_date) <= date($as_of)
                  AND date(r.end_date) >= date($as_of)
                RETURN coalesce(sum(r.allocation), 0) as allocation
            """
            params = {"pid": candidate_id, "as_of": as_of_date or str(session.run("RETURN date() as d").single()["d"])}
            result = session.run(query, **params).single()
            return int(result["allocation"]) if result else 0

    def is_candidate_available(self, candidate_id: str, min_available_pct: Optional[int] = None, as_of_date: Optional[str] = None) -> bool:
        """Checks if candidate has at least min_available_pct free at the given date."""
        allocation = self.get_candidate_allocation(candidate_id, as_of_date=as_of_date)
        available_pct = max(0, 100 - allocation)
        required = min_available_pct if min_available_pct is not None else 1
        return available_pct >= required

    def add_candidate(self, c: Dict):
        """Creates a new Candidate node with skills and experience."""
        with self.driver.session() as session:
            # 1. Person
            session.run("""
                MERGE (p:Person {id: $id})
                SET p.name = $name, p.hourly_rate = $hourly_rate, p.location = $location,
                    p.phone = $phone, p.timezone = $timezone, p.seniority = $seniority,
                    p.years_experience = $years_experience
            """, id=c['id'], name=c['name'], hourly_rate=c.get('hourly_rate'),
               location=c.get('location', 'Remote'), phone=c.get('phone'),
               timezone=c.get('timezone'), seniority=c.get('seniority'),
               years_experience=c.get('years_experience'))

            # 2. Skills
            for skill in c.get('skills', []):
                session.run("""
                    MATCH (p:Person {id: $pid})
                    MERGE (s:Skill {name: $skill_name})
                    MERGE (p)-[:HAS_SKILL {proficiency: $proficiency}]->(s)
                """, pid=c['id'], skill_name=skill['name'], proficiency=skill.get('proficiency', 'Intermediate'))

    def add_rfp(self, r: Dict):
        """Creates a new RFP node with requirements."""
        with self.driver.session() as session:
            # 1. RFP
            session.run("""
                MERGE (r:RFP {id: $id})
                SET r.title = $title, r.budget = $budget, r.description = $desc,
                    r.max_rate = $max_rate, r.start_date = $start_date, r.end_date = $end_date,
                    r.duration_weeks = $duration_weeks, r.team_size = $team_size,
                    r.required_seniority = $required_seniority, r.min_years_experience = $min_years_experience,
                    r.availability_min_pct = $availability_min_pct, r.timezone = $timezone
            """, id=r['id'], title=r['title'], budget=r['budget'], desc=r.get('description', ''),
               max_rate=r.get('max_rate'), start_date=r.get('start_date'), end_date=r.get('end_date'),
               duration_weeks=r.get('duration_weeks'), team_size=r.get('team_size'),
               required_seniority=r.get('required_seniority'),
               min_years_experience=r.get('min_years_experience'),
               availability_min_pct=r.get('availability_min_pct'), timezone=r.get('timezone'))

            # 2. Needs
            for skill in r.get('required_skills', []):
                session.run("""
                    MATCH (r:RFP {id: $rid})
                    MERGE (s:Skill {name: $skill_name})
                    MERGE (r)-[rel:NEEDS]->(s)
                    SET rel.proficiency = $proficiency,
                        rel.min_years_experience = $min_years_experience,
                        rel.required_count = $required_count
                """, rid=r['id'], skill_name=skill['name'],
                   proficiency=skill.get('proficiency', 'Intermediate'),
                   min_years_experience=skill.get('min_years_experience'),
                   required_count=skill.get('required_count', 1))

    def get_graph_stats(self) -> Dict:
        """Fetch summary statistics for the dashboard."""
        with self.driver.session() as session:
            result = session.run("""
                CALL { MATCH (p:Person) RETURN count(p) as candidates }
                CALL { MATCH (r:RFP) RETURN count(r) as rfps }
                CALL { MATCH (s:Skill) RETURN count(s) as skills }
                CALL { MATCH (c:Company) RETURN count(c) as companies }
                RETURN candidates, rfps, skills, companies
            """).single()
            return result.data()

    def list_all_skills(self) -> List[str]:
        """Returns all distinct skill names sorted."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (s:Skill)
                RETURN distinct s.name as skill
                ORDER BY skill
            """)
            return [record["skill"] for record in result if record.get("skill")]

    def list_candidates(
        self,
        search: Optional[str] = None,
        skills: Optional[List[str]] = None,
        seniority: Optional[str] = None,
        timezone: Optional[str] = None,
        min_rate: Optional[float] = None,
        max_rate: Optional[float] = None,
        limit: int = 50,
    ) -> List[Dict]:
        """List candidates with basic details and skills."""
        with self.driver.session() as session:
            query = """
                MATCH (p:Person)
                OPTIONAL MATCH (p)-[:HAS_SKILL]->(s:Skill)
            """
            filters = []
            params: Dict = {"limit": limit}
            if search:
                filters.append("toLower(p.name) CONTAINS toLower($search)")
                params["search"] = search
            if seniority:
                filters.append("p.seniority = $seniority")
                params["seniority"] = seniority
            if timezone:
                filters.append("p.timezone = $timezone")
                params["timezone"] = timezone
            if min_rate is not None:
                filters.append("p.hourly_rate >= $min_rate")
                params["min_rate"] = min_rate
            if max_rate is not None:
                filters.append("p.hourly_rate <= $max_rate")
                params["max_rate"] = max_rate
            if filters:
                query += "WHERE " + " AND ".join(filters) + "\n"
            query += """
                WITH p, collect(distinct s.name) as skills
            """
            if skills:
                query += "WHERE all(req IN $skills WHERE req IN skills)\n"
                params["skills"] = skills
            query += """
                RETURN p.id as id, p.name as name, p.seniority as seniority,
                       p.timezone as timezone, p.location as location,
                       p.hourly_rate as hourly_rate, skills
                ORDER BY p.name
                LIMIT $limit
            """
            result = session.run(query, **params)
            return [record.data() for record in result]

    def list_rfps(
        self,
        search: Optional[str] = None,
        skills: Optional[List[str]] = None,
        seniority: Optional[str] = None,
        timezone: Optional[str] = None,
        min_budget: Optional[float] = None,
        max_budget: Optional[float] = None,
        limit: int = 50,
    ) -> List[Dict]:
        """List RFPs with basic details and required skills."""
        with self.driver.session() as session:
            query = """
                MATCH (r:RFP)
                OPTIONAL MATCH (r)-[:NEEDS]->(s:Skill)
            """
            filters = []
            params: Dict = {"limit": limit}
            if search:
                filters.append(
                    "toLower(r.title) CONTAINS toLower($search) "
                    "OR toLower(r.description) CONTAINS toLower($search)"
                )
                params["search"] = search
            if seniority:
                filters.append("r.required_seniority = $seniority")
                params["seniority"] = seniority
            if timezone:
                filters.append("r.timezone = $timezone")
                params["timezone"] = timezone
            if min_budget is not None:
                filters.append("r.budget >= $min_budget")
                params["min_budget"] = min_budget
            if max_budget is not None:
                filters.append("r.budget <= $max_budget")
                params["max_budget"] = max_budget
            if filters:
                query += "WHERE " + " AND ".join(filters) + "\n"
            query += """
                WITH r, collect(distinct s.name) as skills
            """
            if skills:
                query += "WHERE all(req IN $skills WHERE req IN skills)\n"
                params["skills"] = skills
            query += """
                RETURN r.id as id, r.title as title, r.budget as budget,
                       r.max_rate as max_rate, r.team_size as team_size,
                       r.duration_weeks as duration_weeks,
                       r.required_seniority as required_seniority,
                       r.timezone as timezone, skills
                ORDER BY r.title
                LIMIT $limit
            """
            result = session.run(query, **params)
            return [record.data() for record in result]

    def count_available_candidates(self, skill_name: str) -> int:
        """Counts candidates with a specific skill who are not fully booked."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (p:Person)-[:HAS_SKILL]->(s:Skill {name: $skill})
                OPTIONAL MATCH (p)-[r:ASSIGNED_TO]->(:Project)
                WHERE r.start_date IS NOT NULL AND r.end_date IS NOT NULL
                  AND date(r.start_date) <= date()
                  AND date(r.end_date) >= date()
                WITH p, sum(coalesce(r.allocation, 0)) as alloc
                WHERE alloc < 100
                RETURN count(distinct p) as count
            """, skill=skill_name).single()
            return result['count'] if result else 0

    def count_candidates_by_skill(self, skill_name: str) -> int:
        """Counts candidates with a specific skill (no availability filter)."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (p:Person)-[:HAS_SKILL]->(s:Skill {name: $skill})
                RETURN count(distinct p) as count
            """, skill=skill_name).single()
            return result['count'] if result else 0

    def count_candidates_with_skills(self, skills: List[str]) -> int:
        """Counts candidates who have all provided skills."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (p:Person)-[:HAS_SKILL]->(s:Skill)
                WHERE s.name IN $skills
                WITH p, collect(distinct s.name) as skill_names
                WHERE all(req IN $skills WHERE req IN skill_names)
                RETURN count(distinct p) as count
            """, skills=skills).single()
            return result["count"] if result else 0

    def count_available_candidates_on_date(self, as_of_date: str, skill_name: Optional[str] = None) -> int:
        """Counts candidates available on a specific date (YYYY-MM-DD)."""
        with self.driver.session() as session:
            query = """
                MATCH (p:Person)
                OPTIONAL MATCH (p)-[r:ASSIGNED_TO]->(:Project)
                WHERE r.start_date IS NOT NULL AND r.end_date IS NOT NULL
                  AND date(r.start_date) <= date($as_of)
                  AND date(r.end_date) >= date($as_of)
                WITH p, sum(coalesce(r.allocation, 0)) as alloc
                WHERE alloc < 100
            """
            if skill_name:
                query += """
                MATCH (p)-[:HAS_SKILL]->(s:Skill {name: $skill})
                RETURN count(distinct p) as count
                """
            else:
                query += "RETURN count(distinct p) as count"
            result = session.run(query, as_of=as_of_date, skill=skill_name).single()
            return result["count"] if result else 0

    def count_available_candidates_next_month(self, skill_name: Optional[str] = None) -> int:
        """Counts candidates available next month."""
        with self.driver.session() as session:
            query = """
                WITH date() + duration('P1M') as target
                MATCH (p:Person)
                OPTIONAL MATCH (p)-[r:ASSIGNED_TO]->(:Project)
                WHERE r.start_date IS NOT NULL AND r.end_date IS NOT NULL
                  AND date(r.start_date) <= target
                  AND date(r.end_date) >= target
                WITH p, sum(coalesce(r.allocation, 0)) as alloc
                WHERE alloc < 100
            """
            if skill_name:
                query += """
                MATCH (p)-[:HAS_SKILL]->(s:Skill {name: $skill})
                RETURN count(distinct p) as count
                """
            else:
                query += "RETURN count(distinct p) as count"
            result = session.run(query, skill=skill_name).single()
            return result["count"] if result else 0

    def count_available_candidates_now(self, skill_name: Optional[str] = None) -> int:
        """Counts candidates available today."""
        with self.driver.session() as session:
            query = """
                WITH date() as target
                MATCH (p:Person)
                OPTIONAL MATCH (p)-[r:ASSIGNED_TO]->(:Project)
                WHERE r.start_date IS NOT NULL AND r.end_date IS NOT NULL
                  AND date(r.start_date) <= target
                  AND date(r.end_date) >= target
                WITH p, coalesce(sum(r.allocation), 0) as alloc
                WHERE alloc < 100
            """
            if skill_name:
                query += """
                MATCH (p)-[:HAS_SKILL]->(s:Skill {name: $skill})
                RETURN count(distinct p) as count
                """
            else:
                query += "RETURN count(distinct p) as count"
            result = session.run(query, skill=skill_name).single()
            return result["count"] if result else 0

    def get_top_skills(self, limit: int = 5) -> List[str]:
        """Returns top skills by candidate count."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (p:Person)-[:HAS_SKILL]->(s:Skill)
                RETURN s.name as skill, count(distinct p) as count
                ORDER BY count DESC
                LIMIT $limit
            """, limit=limit)
            return [record["skill"] for record in result]

    def get_top_skills_with_counts(self, limit: int = 5) -> List[Dict]:
        """Returns top skills with counts for dashboard."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (p:Person)-[:HAS_SKILL]->(s:Skill)
                RETURN s.name as skill, count(distinct p) as count
                ORDER BY count DESC
                LIMIT $limit
            """, limit=limit)
            return [record.data() for record in result]

    def count_candidates_with_certification(self, cert_name: str) -> int:
        """Counts candidates with a given certification name."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (p:Person)-[:EARNED]->(c:Certification {name: $name})
                RETURN count(distinct p) as count
            """, name=cert_name).single()
            return result["count"] if result else 0

    def count_candidates_by_university(self, university_name: str) -> int:
        """Counts candidates who studied at a given university."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (p:Person)-[:STUDIED_AT]->(u:University {name: $name})
                RETURN count(distinct p) as count
            """, name=university_name).single()
            return result["count"] if result else 0

    def find_candidates_with_skills_and_seniority(self, skills: List[str], seniorities: List[str]) -> List[Dict]:
        """Find candidates who have all skills and required seniority."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (p:Person)-[:HAS_SKILL]->(s:Skill)
                WHERE s.name IN $skills AND p.seniority IN $seniorities
                WITH p, collect(distinct s.name) as skill_names
                WHERE all(req IN $skills WHERE req IN skill_names)
                RETURN p.id as id, p.name as name, p.seniority as seniority
                ORDER BY p.name
            """, skills=skills, seniorities=seniorities)
            return [record.data() for record in result]

    def list_available_candidates_by_timezone(self, timezone: str) -> List[Dict]:
        """List available candidates for a given timezone."""
        with self.driver.session() as session:
            result = session.run("""
                WITH date() as target
                MATCH (p:Person {timezone: $timezone})
                OPTIONAL MATCH (p)-[r:ASSIGNED_TO]->(:Project)
                WHERE r.start_date IS NOT NULL AND r.end_date IS NOT NULL
                  AND date(r.start_date) <= target
                  AND date(r.end_date) >= target
                WITH p, coalesce(sum(r.allocation), 0) as alloc
                WHERE alloc < 100
                RETURN p.id as id, p.name as name, p.timezone as timezone,
                       alloc as allocation_pct, (100 - alloc) as available_pct
                ORDER BY available_pct DESC, p.name
            """, timezone=timezone)
            return [record.data() for record in result]

    def average_years_experience_for_ml_projects(self) -> Optional[float]:
        """Average years of experience for candidates on ML projects."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (p:Person)-[:WORKED_ON]->(pr:Project)-[:USES]->(s:Skill)
                WHERE s.name IN ['TensorFlow', 'Machine Learning', 'ML']
                RETURN avg(p.years_experience) as avg_years
            """).single()
            if not result or result["avg_years"] is None:
                return None
            return float(result["avg_years"])

    def total_capacity_available_for_q4(self) -> int:
        """Total available capacity for Q4 (Oct 1 of current year)."""
        with self.driver.session() as session:
            result = session.run("""
                WITH date() as today
                WITH date({year: today.year, month: 10, day: 1}) as target
                MATCH (p:Person)
                OPTIONAL MATCH (p)-[r:ASSIGNED_TO]->(:Project)
                WHERE r.start_date IS NOT NULL AND r.end_date IS NOT NULL
                  AND date(r.start_date) <= target
                  AND date(r.end_date) >= target
                WITH p, coalesce(sum(r.allocation), 0) as alloc
                RETURN sum(CASE WHEN alloc < 100 THEN 100 - alloc ELSE 0 END) as total_capacity
            """).single()
            return int(result["total_capacity"]) if result and result["total_capacity"] is not None else 0

    def list_candidates_available_after_current_project(self) -> List[Dict]:
        """List candidates who become available after current assignments end."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (p:Person)-[r:ASSIGNED_TO]->(:Project)
                WHERE r.start_date IS NOT NULL AND r.end_date IS NOT NULL
                  AND date(r.start_date) <= date()
                  AND date(r.end_date) >= date()
                WITH p, max(date(r.end_date)) as end_date, sum(r.allocation) as alloc
                RETURN p.id as id, p.name as name, end_date, alloc as allocation_pct
                ORDER BY end_date ASC
            """)
            return [record.data() for record in result]

    def skills_distribution_by_graduation_year(self) -> List[Dict]:
        """Returns skill distribution grouped by graduation year."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (p:Person)-[r:STUDIED_AT]->(:University)
                WHERE r.graduation_year IS NOT NULL
                MATCH (p)-[:HAS_SKILL]->(s:Skill)
                RETURN r.graduation_year as graduation_year, s.name as skill,
                       count(distinct p) as count
                ORDER BY graduation_year ASC, count DESC
            """)
            return [record.data() for record in result]

    def list_collaboration_pairs(self, limit: int = 5) -> List[Dict]:
        """Finds developer pairs who worked together at same company."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (a:Person)-[:WORKED_AT]->(c:Company)<-[:WORKED_AT]-(b:Person)
                WHERE elementId(a) < elementId(b)
                RETURN a.name as person_a, b.name as person_b, c.name as context
                ORDER BY c.name, person_a, person_b
                LIMIT $limit
            """, limit=limit)
            return [record.data() for record in result]

    def list_alumni_of_top_performers(self, top_n: int = 5, limit: int = 10) -> List[Dict]:
        """Finds developers from same universities as top performers."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (top:Person)
                WHERE top.hourly_rate IS NOT NULL
                WITH top ORDER BY top.hourly_rate DESC LIMIT $top_n
                MATCH (top)-[:STUDIED_AT]->(u:University)
                WITH collect(top) as top_people, collect(distinct u) as universities
                MATCH (p:Person)-[:STUDIED_AT]->(u:University)
                WHERE u IN universities AND NOT p IN top_people
                RETURN p.name as name, u.name as university
                ORDER BY u.name, name
                LIMIT $limit
            """, top_n=top_n, limit=limit)
            return [record.data() for record in result]

    def skills_gap_analysis(self, limit: int = 5) -> List[Dict]:
        """Compares RFP skill demand vs candidate supply."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (r:RFP)-[n:NEEDS]->(s:Skill)
                WITH s.name as skill, sum(coalesce(n.required_count, 1)) as demand
                MATCH (p:Person)-[:HAS_SKILL]->(s2:Skill {name: skill})
                WITH skill, demand, count(distinct p) as supply
                WITH skill, demand, supply, (demand - supply) as gap
                WHERE gap > 0
                RETURN skill, demand, supply, gap
                ORDER BY gap DESC, demand DESC
                LIMIT $limit
            """, limit=limit)
            return [record.data() for record in result]

    def risk_single_points_of_failure(self, limit: int = 5) -> List[Dict]:
        """Finds skills with only one available candidate."""
        with self.driver.session() as session:
            result = session.run("""
                WITH date() as target
                MATCH (p:Person)-[:HAS_SKILL]->(s:Skill)
                OPTIONAL MATCH (p)-[r:ASSIGNED_TO]->(:Project)
                WHERE r.start_date IS NOT NULL AND r.end_date IS NOT NULL
                  AND date(r.start_date) <= target
                  AND date(r.end_date) >= target
                WITH s.name as skill, p, coalesce(sum(r.allocation), 0) as alloc
                WHERE alloc < 100
                WITH skill, count(distinct p) as available_count
                WHERE available_count = 1
                RETURN skill, available_count
                ORDER BY skill
                LIMIT $limit
            """, limit=limit)
            return [record.data() for record in result]

    def recommend_team_for_fintech_rfp(self, limit: Optional[int] = None) -> List[Dict]:
        """Recommends a team for the first FinTech RFP under budget."""
        with self.driver.session() as session:
            rfp = session.run("""
                MATCH (r:RFP)
                WHERE toLower(r.title) CONTAINS 'fintech' OR toLower(r.description) CONTAINS 'fintech'
                RETURN r.id as id, r.team_size as team_size, r.max_rate as max_rate,
                       r.availability_min_pct as availability_min_pct
                ORDER BY r.team_size DESC
                LIMIT 1
            """).single()
            if not rfp:
                return []
            team_size = rfp.get("team_size") or limit or 3
            max_rate = rfp.get("max_rate")
            availability_min_pct = rfp.get("availability_min_pct") or 1

            result = session.run("""
                MATCH (r:RFP {id: $rfp_id})
                WITH r,
                     CASE
                         WHEN r.start_date IS NULL OR r.start_date = ''
                         THEN date() + duration('P1M')
                         ELSE date(r.start_date)
                     END as target
                MATCH (r)-[:NEEDS]->(req:Skill)
                MATCH (p:Person)-[:HAS_SKILL]->(s:Skill)
                WHERE s.name = req.name
                OPTIONAL MATCH (p)-[a:ASSIGNED_TO]->(:Project)
                WHERE a.start_date IS NOT NULL AND a.end_date IS NOT NULL
                  AND date(a.start_date) <= target
                  AND date(a.end_date) >= target
                WITH p, collect(distinct s.name) as matched_skills,
                     coalesce(sum(a.allocation), 0) as alloc
                WITH p, matched_skills, alloc, (100 - alloc) as available_pct
                WHERE available_pct >= $min_available
                  AND ($max_rate IS NULL OR p.hourly_rate <= $max_rate)
                RETURN p.id as id, p.name as name, p.hourly_rate as hourly_rate,
                       size(matched_skills) as match_count, available_pct
                ORDER BY match_count DESC, available_pct DESC, p.hourly_rate ASC
                LIMIT $team_size
            """, rfp_id=rfp["id"], team_size=team_size, max_rate=max_rate, min_available=availability_min_pct)
            return [record.data() for record in result]

    def total_capacity_available_for_q4_by_skill(self, limit: int = 10) -> List[Dict]:
        """Total available capacity for Q4 grouped by skill."""
        with self.driver.session() as session:
            result = session.run("""
                WITH date() as today
                WITH date({year: today.year, month: 10, day: 1}) as target
                MATCH (p:Person)-[:HAS_SKILL]->(s:Skill)
                OPTIONAL MATCH (p)-[r:ASSIGNED_TO]->(:Project)
                WHERE r.start_date IS NOT NULL AND r.end_date IS NOT NULL
                  AND date(r.start_date) <= target
                  AND date(r.end_date) >= target
                WITH s.name as skill, p, coalesce(sum(r.allocation), 0) as alloc
                WITH skill, sum(CASE WHEN alloc < 100 THEN 100 - alloc ELSE 0 END) as capacity
                RETURN skill, capacity
                ORDER BY capacity DESC, skill
                LIMIT $limit
            """, limit=limit)
            return [record.data() for record in result]

    def average_years_experience_for_ml_projects_by_seniority(self) -> List[Dict]:
        """Average years of experience for ML projects grouped by seniority."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (p:Person)-[:WORKED_ON]->(pr:Project)-[:USES]->(s:Skill)
                WHERE s.name IN ['TensorFlow', 'Machine Learning', 'ML']
                AND p.seniority IS NOT NULL AND p.years_experience IS NOT NULL
                RETURN p.seniority as seniority, avg(p.years_experience) as avg_years
                ORDER BY seniority
            """)
            return [record.data() for record in result]

    def get_top_skills_in_demand(self, limit: int = 5) -> List[Dict]:
        """Returns top skills requested in RFPs."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (r:RFP)-[:NEEDS]->(s:Skill)
                RETURN s.name as skill, count(r) as demand
                ORDER BY demand DESC
                LIMIT $limit
            """, limit=limit)
            return [record.data() for record in result]

    def find_collaborators(self, person_id: str) -> List[Dict]:
        """Finds potential collaborators who worked at the same company during overlapping times."""
        # Simplified: Just worked at same company
        with self.driver.session() as session:
            result = session.run("""
                MATCH (p:Person {id: $id})-[:WORKED_AT]->(c:Company)<-[:WORKED_AT]-(collab:Person)
                RETURN distinct collab.name as name, c.name as shared_company
                LIMIT 5
            """, id=person_id)
            return [record.data() for record in result]

    def run_cypher_query(self, query: str) -> str:
        """
        Executes a natural language query against the graph using LangChain's GraphCypherQAChain.
        Returns the natural language answer generated by the LLM.
        """
        from langchain_community.graphs import Neo4jGraph
        from langchain_community.chains.graph_qa.cypher import GraphCypherQAChain
        from langchain_openai import ChatOpenAI

        # Initialize LangChain Neo4j Wrapper
        # Note: We reuse the connection details from env, but let LangChain verify schema
        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        user = os.getenv("NEO4J_USERNAME", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "password")
        
        graph = Neo4jGraph(
            url=uri, 
            username=user, 
            password=password,
            enhanced_schema=False
        )

        # Setup LLM
        llm = ChatOpenAI(temperature=0, model="gpt-4o-mini")

        # Setup Chain with strict validations
        chain = GraphCypherQAChain.from_llm(
            llm=llm,
            graph=graph,
            verbose=True,
            allow_dangerous_requests=True, # Need this for community version sometimes
            validate_cypher=True
        )

        try:
            # Run the chain
            # The chain returns a dictionary with 'result' key usually
            response = chain.invoke(query)
            return response.get("result", "I couldn't generate an answer.")
        except Exception as e:
            return f"Error executing Graph Query: {str(e)}"
