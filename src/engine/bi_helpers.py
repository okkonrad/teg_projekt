import re
from pathlib import Path
from typing import Any

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage


COMMON_SKILLS = [
    "Python",
    "Java",
    "React",
    "Docker",
    "Kubernetes",
    "AWS",
    "Neo4j",
    "TensorFlow",
    "FastAPI",
    "PostgreSQL",
    "GraphQL",
    "TypeScript",
    "Node.js",
    "Node",
]

COMMON_CERTS = [
    "AWS Certified",
    "Azure Fundamentals",
    "GCP Associate",
    "Neo4j Certified",
]

COMMON_UNIS = [
    "MIT",
    "Stanford",
    "UW",
    "Politechnika Warszawska",
    "UJ",
]

NO_MATCH = "No matching candidates found."


def _normalize_skill(skill: str) -> str:
    return "Node.js" if skill.lower() == "node" else skill


def classify_intent(prompt: str) -> str:
    prompt_lower = prompt.lower()
    if any(x in prompt_lower for x in ["search", "looking for", "recommend", "candidates for"]):
        return "SEARCH"
    return "ANALYTICS"


def extract_skill_from_prompt(prompt: str) -> str | None:
    prompt_lower = prompt.lower()
    for skill in COMMON_SKILLS:
        if skill.lower() in prompt_lower:
            return _normalize_skill(skill)
    return None


def extract_skills_from_prompt(prompt: str) -> list[str]:
    prompt_lower = prompt.lower()
    skills = []
    for skill in COMMON_SKILLS:
        if skill.lower() in prompt_lower:
            normalized = _normalize_skill(skill)
            if normalized not in skills:
                skills.append(normalized)
    return skills


def extract_cert_from_prompt(prompt: str) -> str | None:
    prompt_lower = prompt.lower()
    for cert in COMMON_CERTS:
        if cert.lower() in prompt_lower:
            return cert
    if "aws" in prompt_lower and "cert" in prompt_lower:
        return "AWS Certified"
    return None


def extract_university_from_prompt(prompt: str) -> str | None:
    prompt_lower = prompt.lower()
    for uni in COMMON_UNIS:
        if uni.lower() in prompt_lower:
            return uni
    return None


def extract_timezone_from_prompt(prompt: str) -> str | None:
    prompt_lower = prompt.lower()
    if "pacific" in prompt_lower:
        return "UTC-8"
    match = re.search(r"utc\s*([+-]\d{1,2})", prompt_lower)
    if not match:
        return None
    offset = match.group(1)
    return f"UTC{offset}"


def _names(people: list[dict]) -> list[str]:
    return [p.get("name") for p in people if p.get("name")]


def _format_people_list(people: list[dict], max_items: int = 5) -> str:
    names = _names(people)
    if not names:
        return NO_MATCH
    clipped = names[:max_items]
    suffix = "..." if len(names) > max_items else ""
    return f"Matches: {', '.join(clipped)}{suffix}"


def _format_people_summary(people: list[dict], max_items: int = 5) -> str:
    names = _names(people)
    if not names:
        return NO_MATCH
    clipped = names[:max_items]
    suffix = "..." if len(names) > max_items else ""
    return f"Found {len(names)} candidates. Top {len(clipped)}: {', '.join(clipped)}{suffix}"


def _format_people_summary_count(total: int, people: list[dict], max_items: int = 5) -> str:
    if total == 0:
        return NO_MATCH
    names = _names(people)
    clipped = names[:max_items]
    suffix = "..." if total > max_items else ""
    return f"Found {total} candidates. Top {len(clipped)}: {', '.join(clipped)}{suffix}"


def _format_top_candidates(results: list[dict], max_items: int = 5) -> str:
    if not results:
        return NO_MATCH
    names = _names(results)
    clipped = names[:max_items]
    suffix = "..." if len(names) > max_items else ""
    return f"Found {len(names)} candidates. Top {len(clipped)}: {', '.join(clipped)}{suffix}"


def _extract_rfp_id(prompt: str) -> str | None:
    match = re.search(r"\b[0-9a-fA-F-]{36}\b", prompt)
    return match.group(0) if match else None


def _extract_top_k(prompt: str, default: int = 5, max_k: int = 25) -> int:
    match = re.search(r"top\s+(\d+)", prompt.lower())
    if not match:
        return default
    try:
        value = int(match.group(1))
    except ValueError:
        return default
    return max(1, min(value, max_k))


def _format_distribution(rows: list[dict], max_years: int = 5) -> str:
    if not rows:
        return "No graduation-year distribution available."
    grouped: dict[int, list[str]] = {}
    for row in rows:
        year = row.get("graduation_year")
        skill = row.get("skill")
        count = row.get("count")
        if year is None or not skill:
            continue
        grouped.setdefault(int(year), []).append(f"{skill} ({count})")
    if not grouped:
        return "No graduation-year distribution available."
    parts = []
    for year in sorted(grouped.keys())[:max_years]:
        parts.append(f"{year}: {', '.join(grouped[year])}")
    suffix = " ..." if len(grouped.keys()) > max_years else ""
    return "Skills by graduation year: " + " | ".join(parts) + suffix


def _format_pairs(rows: list[dict], max_items: int = 5) -> str:
    if not rows:
        return "No collaboration pairs found."
    parts = []
    for row in rows[:max_items]:
        parts.append(f"{row.get('person_a')} & {row.get('person_b')} ({row.get('context')})")
    suffix = "..." if len(rows) > max_items else ""
    return "Pairs: " + "; ".join(parts) + suffix


def _format_alumni(rows: list[dict], max_items: int = 5) -> str:
    if not rows:
        return "No alumni matches found."
    parts = []
    for row in rows[:max_items]:
        parts.append(f"{row.get('name')} ({row.get('university')})")
    suffix = "..." if len(rows) > max_items else ""
    return "Alumni matches: " + "; ".join(parts) + suffix


def _format_gaps(rows: list[dict], max_items: int = 5) -> str:
    if not rows:
        return "No skill gaps detected."
    parts = []
    for row in rows[:max_items]:
        parts.append(f"{row.get('skill')}: gap {row.get('gap')} (demand {row.get('demand')}, supply {row.get('supply')})")
    suffix = "..." if len(rows) > max_items else ""
    return "Skill gaps: " + "; ".join(parts) + suffix


def _format_risks(rows: list[dict], max_items: int = 5) -> str:
    if not rows:
        return "No single points of failure detected."
    parts = [row.get("skill") for row in rows[:max_items] if row.get("skill")]
    suffix = "..." if len(rows) > max_items else ""
    return "Single-point skills: " + ", ".join(parts) + suffix


def _format_team(rows: list[dict]) -> str:
    if not rows:
        return "No team candidates found for FinTech RFP."
    parts = []
    for row in rows:
        parts.append(f"{row.get('name')} (${row.get('hourly_rate')}/hr, match {row.get('match_count')})")
    return "Suggested team: " + "; ".join(parts)


def _format_capacity_by_skill(rows: list[dict], max_items: int = 5) -> str:
    if not rows:
        return "No capacity data by skill."
    parts = []
    for row in rows[:max_items]:
        parts.append(f"{row.get('skill')}: {row.get('capacity')}")
    suffix = "..." if len(rows) > max_items else ""
    return "Q4 capacity by skill: " + "; ".join(parts) + suffix


def _format_avg_by_seniority(rows: list[dict]) -> str:
    if not rows:
        return "No ML experience data by seniority."
    parts = []
    for row in rows:
        parts.append(f"{row.get('seniority')}: {row.get('avg_years'):.1f}")
    return "ML avg years by seniority: " + "; ".join(parts)


def load_core_bi_questions(path: Path | None = None, limit: int = 10) -> list[str]:
    questions_path = path or Path("docs/BI_QUESTIONS.md")
    if not questions_path.exists():
        return []
    questions: list[str] = []
    for line in questions_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith(tuple(str(i) + "." for i in range(1, 11))):
            question = line.split(".", 1)[1].strip()
            if question:
                questions.append(question)
        if len(questions) >= limit:
            break
    return questions


def generate_natural_response(prompt: str, count: int, mode: str, results: list | None = None) -> str:
    try:
        chat = ChatOpenAI(temperature=0.4, model="gpt-4o-mini")
        context = f"Found {count} matches using {mode}."
        if results and len(results) > 0:
            top = results[0]
            context += f" Top match: {top['name']} (${top.get('hourly_rate', '?')}/hr)."

        messages = [
            SystemMessage(
                content=(
                    "You are a helpful AI recruiter assistant. Respond to the user's query in the "
                    "SAME LANGUAGE as they used. Briefly summarize the search results provided in "
                    "the context. Be professional and concise."
                )
            ),
            HumanMessage(content=f"User Query: {prompt}\nContext: {context}"),
        ]

        response = chat.invoke(messages)
        return response.content
    except Exception:
        return f"Found {count} matches."


def run_graphrag_analytics(prompt: str, service: Any) -> dict:
    skill = extract_skill_from_prompt(prompt)
    skills = extract_skills_from_prompt(prompt)
    lower = prompt.lower()
    is_count = any(x in lower for x in ["how many", "count", "ile", "ilu"])
    is_next_month = any(x in lower for x in ["next month", "następny miesiąc", "w przyszłym miesiącu"])
    is_now = any(x in lower for x in ["now", "current", "dzisiaj", "obecnie", "teraz"])
    cert = extract_cert_from_prompt(prompt)
    uni = extract_university_from_prompt(prompt)
    timezone = extract_timezone_from_prompt(prompt)
    top_k = _extract_top_k(prompt, default=5)

    response_text = ""
    count_value = None
    strategy = "cypher"
    results: list[dict] | None = None

    def set_count(value: int, message: str):
        nonlocal count_value, response_text, strategy
        count_value = value
        response_text = message
        strategy = "direct_count"

    rfp_id = _extract_rfp_id(prompt)
    if rfp_id:
        from src.engine.matcher import Matcher
        matcher = Matcher()
        try:
            results = matcher.find_matches(rfp_id=rfp_id, strict=False, top_k=top_k)
        finally:
            matcher.close()
        response_text = _format_top_candidates(results, max_items=top_k)
        strategy = "rfp_match"
    elif lower.startswith("need ") or "rfp" in lower:
        rfps = service.list_rfps(search=prompt, limit=1)
        if rfps:
            from src.engine.matcher import Matcher
            matcher = Matcher()
            try:
                results = matcher.find_matches(rfp_id=rfps[0]["id"], strict=False, top_k=top_k)
            finally:
                matcher.close()
            response_text = _format_top_candidates(results, max_items=top_k)
            strategy = "rfp_match"
        else:
            response_text = "No matching RFP found."
            strategy = "direct_query"
    elif "worked together" in lower:
        pairs = service.list_collaboration_pairs(limit=5)
        response_text = _format_pairs(pairs)
        strategy = "direct_query"
    elif "same university" in lower and "top" in lower:
        alumni = service.list_alumni_of_top_performers()
        response_text = _format_alumni(alumni)
        strategy = "direct_query"
    elif "skills gaps" in lower or "skills gap" in lower:
        gaps = service.skills_gap_analysis(limit=5)
        response_text = _format_gaps(gaps)
        strategy = "direct_query"
    elif "risk assessment" in lower or "single point" in lower:
        risks = service.risk_single_points_of_failure(limit=5)
        response_text = _format_risks(risks)
        strategy = "direct_query"
    elif "fintech" in lower and "team" in lower:
        team = service.recommend_team_for_fintech_rfp()
        response_text = _format_team(team)
        strategy = "direct_query"
    elif "q4" in lower and "by skill" in lower:
        rows = service.total_capacity_available_for_q4_by_skill(limit=5)
        response_text = _format_capacity_by_skill(rows)
        strategy = "direct_query"
    elif "pacific" in lower and "available" in lower:
        results = service.list_available_candidates_by_timezone("UTC-8")
        response_text = _format_people_summary(results)
        strategy = "direct_query"
    elif "average" in lower and ("ml" in lower or "machine learning" in lower) and "seniority" in lower:
        rows = service.average_years_experience_for_ml_projects_by_seniority()
        response_text = _format_avg_by_seniority(rows)
        strategy = "direct_query"
    elif "neo4j" in lower and is_count and is_next_month:
        value = service.count_available_candidates_next_month("Neo4j")
        set_count(value, f"We have {value} Neo4j developers available next month.")
    elif cert and "certification" in lower and is_count:
        value = service.count_candidates_with_certification(cert)
        set_count(value, f"We have {value} candidates with {cert} certification.")
    elif ("find" in lower or "list" in lower) and skills and "senior" not in lower and "available" not in lower:
        total = service.count_candidates_with_skills(skills)
        top = service.list_candidates(skills=skills, limit=top_k)
        response_text = _format_people_summary_count(total, top, max_items=top_k)
        strategy = "direct_query"
    elif "senior" in lower and skills:
        results = service.find_candidates_with_skills_and_seniority(
            skills=skills,
            seniorities=["Senior", "Lead"],
        )
        response_text = _format_people_summary(results, max_items=top_k)
        strategy = "direct_query"
    elif timezone and "available" in lower:
        results = service.list_available_candidates_by_timezone(timezone)
        response_text = _format_people_summary(results, max_items=top_k)
        strategy = "direct_query"
    elif "average" in lower and "years" in lower and "machine learning" in lower:
        avg_years = service.average_years_experience_for_ml_projects()
        if avg_years is None:
            response_text = "No machine learning project experience data found."
        else:
            response_text = f"Average years of experience for ML projects: {avg_years:.1f}."
        strategy = "direct_query"
    elif "total capacity" in lower and "q4" in lower:
        total_capacity = service.total_capacity_available_for_q4()
        response_text = f"Total capacity available for Q4 projects is {total_capacity}."
        strategy = "direct_query"
    elif "becomes available" in lower and "project" in lower and "ends" in lower:
        results = service.list_candidates_available_after_current_project()
        response_text = _format_people_list(results)
        strategy = "direct_query"
    elif "skills distribution" in lower and "graduation year" in lower:
        rows = service.skills_distribution_by_graduation_year()
        response_text = _format_distribution(rows)
        strategy = "direct_query"
    elif cert and is_count:
        value = service.count_candidates_with_certification(cert)
        set_count(value, f"We have {value} candidates with {cert} certification.")
    elif uni and is_count:
        value = service.count_candidates_by_university(uni)
        set_count(value, f"We have {value} candidates from {uni}.")
    elif skill and is_count and is_next_month:
        value = service.count_available_candidates_next_month(skill)
        set_count(value, f"We have {value} {skill} developers available next month.")
    elif skill and is_count and is_now:
        value = service.count_available_candidates_now(skill)
        set_count(value, f"We have {value} {skill} developers available now.")
    elif skill and is_count:
        value = service.count_candidates_by_skill(skill)
        set_count(value, f"We have {value} {skill} developers in the candidate pool.")
    else:
        response_text = service.run_cypher_query(prompt)

    if not skill and is_count:
        top_skills = service.get_top_skills(limit=5)
        if top_skills:
            response_text += f"\nTop skills in DB: {', '.join(top_skills)}"

    return {
        "response": response_text,
        "count": count_value,
        "strategy": strategy,
        "results": results,
        "detected_skill": skill,
        "detected_cert": cert,
        "detected_university": uni,
    }
