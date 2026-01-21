import json
import random
import sys
from pathlib import Path
from typing import Dict, List

REPO_ROOT = Path(__file__).resolve()
for parent in REPO_ROOT.parents:
    if (parent / "pyproject.toml").exists():
        if str(parent) not in sys.path:
            sys.path.insert(0, str(parent))
        break
from faker import Faker
from src.domain.schemas import (
    Candidate,
    RFP,
    Skill,
    SkillRequirement,
    WorkExperience,
    Project,
    SkillProficiency,
    Seniority,
    Certification,
    Education,
)

SKILL_CATEGORIES = {
    "Python": "Language",
    "Java": "Language",
    "React": "Frontend",
    "Docker": "DevOps",
    "Kubernetes": "DevOps",
    "AWS": "Cloud",
    "Neo4j": "Database",
    "TensorFlow": "Data Science",
    "FastAPI": "Backend",
    "PostgreSQL": "Database",
    "GraphQL": "API",
    "TypeScript": "Language",
}

SHARED_COMPANIES = [
    {"name": "TechGlobal", "industry": "FinTech"},
    {"name": "InnovateX", "industry": "Healthcare"},
    {"name": "CloudWorks", "industry": "Cloud Services"},
    {"name": "GreenEnergy", "industry": "Energy"},
    {"name": "AutoDrive", "industry": "Automotive"},
    {"name": "CyberShield", "industry": "Security"},
    {"name": "RetailGiant", "industry": "Retail"},
    {"name": "EduTech", "industry": "Education"},
    {"name": "MediaStream", "industry": "Entertainment"},
    {"name": "LogisticsCo", "industry": "Logistics"},
]

class DataGenerator:
    def __init__(self, seed: int = 42):
        self.fake = Faker()
        Faker.seed(seed)
        random.seed(seed)
        self.tech_skills = list(SKILL_CATEGORIES.keys())
        self.roles = [
            "Senior Engineer",
            "DevOps Specialist",
            "Data Scientist",
            "Frontend Developer",
            "Full Stack Engineer",
        ]

    def _generate_skill_profile(self, count_min=3, count_max=8) -> List[Skill]:
        num_skills = random.randint(count_min, count_max)
        selected_skills = random.sample(self.tech_skills, num_skills)
        return [
            Skill(
                name=skill,
                category=SKILL_CATEGORIES[skill],
                proficiency=random.choice(list(SkillProficiency)),
            )
            for skill in selected_skills
        ]

    def _generate_work_experience(self) -> WorkExperience:
        d1 = self.fake.date_between(start_date="-10y", end_date="-1y")
        d2 = self.fake.date_between(start_date=d1, end_date="today")
        if d1 >= d2:
            d1, d2 = d2, d1
        company_data = random.choice(SHARED_COMPANIES)

        return WorkExperience(
            company=company_data["name"],
            role=random.choice(self.roles),
            start_date=str(d1),
            end_date=str(d2),
            description=self.fake.bs(),
        )

    def _generate_certifications(self) -> List[Certification]:
        certs = []
        for _ in range(random.randint(0, 2)):
            certs.append(
                Certification(
                    name=random.choice(
                        ["AWS Certified", "Azure Fundamentals", "GCP Associate", "Neo4j Certified"]
                    ),
                    provider=random.choice(["AWS", "Microsoft", "Google", "Neo4j"]),
                    date_earned=str(self.fake.date_between(start_date="-5y", end_date="-1y")),
                    expiry_date=str(self.fake.date_between(start_date="today", end_date="+3y")),
                )
            )
        return certs

    def _generate_education(self) -> List[Education]:
        education = []
        for _ in range(random.randint(0, 1)):
            education.append(
                Education(
                    university=random.choice(
                        ["MIT", "Stanford", "UW", "Politechnika Warszawska", "UJ"]
                    ),
                    degree=random.choice(["BSc", "MSc"]),
                    field=random.choice(["Computer Science", "Software Engineering", "Data Science"]),
                    graduation_year=random.choice([2014, 2016, 2018, 2020, 2022]),
                    gpa=round(random.uniform(3.0, 4.0), 2),
                )
            )
        return education

    def _generate_skill_requirements(self, count_min=3, count_max=5) -> List[SkillRequirement]:
        num_skills = random.randint(count_min, count_max)
        selected_skills = random.sample(self.tech_skills, num_skills)
        return [
            SkillRequirement(
                name=skill,
                category=SKILL_CATEGORIES[skill],
                proficiency=random.choice(list(SkillProficiency)),
                min_years_experience=random.choice([None, 1, 2, 3, 5]),
                required_count=random.choice([1, 1, 2]),
            )
            for skill in selected_skills
        ]

    def _generate_assignments(self) -> List[Dict]:
        assignments = []
        if random.random() > 0.3:
            num_projects = random.randint(1, 2)
            total_alloc = 0
            for _ in range(num_projects):
                if total_alloc >= 100:
                    break

                alloc = random.choice([25, 50, 75, 100])
                if total_alloc + alloc > 100:
                    alloc = 100 - total_alloc

                start = self.fake.date_between(start_date="-6m", end_date="-1m")
                end = self.fake.date_between(start_date="+1m", end_date="+6m")

                assignments.append(
                    {
                        "project_name": f"Internal: {self.fake.bs()}",
                        "allocation": alloc,
                        "start_date": str(start),
                        "end_date": str(end),
                    }
                )
                total_alloc += alloc
        return assignments

    def generate_candidate(self) -> Candidate:
        profile = self.fake.profile()
        return Candidate(
            id=self.fake.uuid4(),
            name=profile["name"],
            email=profile["mail"],
            location=self.fake.city(),
            timezone=random.choice(["UTC-8", "UTC-5", "UTC+0", "UTC+1", "UTC+2"]),
            seniority=random.choice(list(Seniority)),
            years_experience=round(random.uniform(1.0, 12.0), 1),
            hourly_rate=round(random.uniform(50.0, 200.0), 2),
            skills=self._generate_skill_profile(),
            experience=[self._generate_work_experience() for _ in range(random.randint(1, 4))],
            projects=[
                Project(
                    name=self.fake.bs(),
                    description=self.fake.catch_phrase(),
                    tech_stack=random.sample(self.tech_skills, random.randint(2, 4)),
                )
                for _ in range(random.randint(1, 3))
            ],
            assignments=self._generate_assignments(),
            certifications=self._generate_certifications(),
            education=self._generate_education(),
        )

    def generate_rfp(self) -> RFP:
        start_date = self.fake.date_between(start_date="today", end_date="+1m")
        end_date = self.fake.date_between(start_date="+2m", end_date="+6m")
        return RFP(
            id=self.fake.uuid4(),
            title=f"Need {random.choice(self.roles)} for {self.fake.bs()}",
            description=self.fake.text(max_nb_chars=200),
            required_skills=self._generate_skill_requirements(count_min=3, count_max=5),
            preferred_skills=self._generate_skill_requirements(count_min=1, count_max=3),
            start_date=str(start_date),
            end_date=str(end_date),
            duration_weeks=random.choice([4, 6, 8, 12, 16]),
            team_size=random.choice([2, 3, 4, 5, 6]),
            required_seniority=random.choice(list(Seniority)),
            min_years_experience=random.choice([2, 3, 5, 7]),
            availability_min_pct=random.choice([25, 50, 75, 100]),
            timezone=random.choice(["UTC-8", "UTC-5", "UTC+0", "UTC+1", "UTC+2"]),
            budget=random.randint(50000, 200000),
            max_rate=round(random.uniform(60.0, 180.0), 2),
        )

    def generate_corpus(self, num_candidates: int = 50, num_rfps: int = 5):
        candidates = [self.generate_candidate() for _ in range(num_candidates)]
        rfps = [self.generate_rfp() for _ in range(num_rfps)]

        with open("data/raw/candidates.json", "w") as f:
            json.dump([c.model_dump() for c in candidates], f, indent=2, default=str)

        with open("data/raw/rfps.json", "w") as f:
            json.dump([r.model_dump() for r in rfps], f, indent=2, default=str)

        print(f"Generated {len(candidates)} candidates and {len(rfps)} RFPs. Creating PDFs...")

        from src.data.pdf_generator import PDFGenerator

        pdf_gen = PDFGenerator()
        for c in candidates:
            pdf_gen.generate_candidate_pdf(c.model_dump())

        print(f"PDFs created in {pdf_gen.output_dir}.")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", type=int, default=50)
    parser.add_argument("--rfps", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    gen = DataGenerator(seed=args.seed)
    gen.generate_corpus(num_candidates=args.candidates, num_rfps=args.rfps)
