import json
import re
import sys
import uuid
from pathlib import Path
from typing import Dict, List, Optional

REPO_ROOT = Path(__file__).resolve()
for parent in REPO_ROOT.parents:
    if (parent / "pyproject.toml").exists():
        if str(parent) not in sys.path:
            sys.path.insert(0, str(parent))
        break

from src.domain.schemas import SkillRequirement, SkillProficiency, Seniority

PROFICIENCY_MAP = {
    "beginner": SkillProficiency.BEGINNER,
    "intermediate": SkillProficiency.INTERMEDIATE,
    "advanced": SkillProficiency.ADVANCED,
    "expert": SkillProficiency.EXPERT,
}

SENIORITY_MAP = {
    "junior": Seniority.JUNIOR,
    "mid": Seniority.MID,
    "senior": Seniority.SENIOR,
    "lead": Seniority.LEAD,
}


def _parse_number(pattern: str, text: str) -> Optional[float]:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        return None
    value = match.group(1).replace(",", "")
    try:
        return float(value)
    except ValueError:
        return None


def _parse_int(pattern: str, text: str) -> Optional[int]:
    value = _parse_number(pattern, text)
    if value is None:
        return None
    return int(value)


def _parse_skills_list(text: str) -> List[SkillRequirement]:
    skills = []
    skill_line_match = re.search(r"required skills?:\s*(.+)", text, flags=re.IGNORECASE)
    if not skill_line_match:
        return skills

    raw_skills = skill_line_match.group(1)
    for item in re.split(r",|;", raw_skills):
        item = item.strip()
        if not item:
            continue
        name_match = re.match(r"([A-Za-z0-9\.\+#\- ]+)", item)
        if not name_match:
            continue
        name = name_match.group(1).strip()
        prof_match = re.search(r"\(([^)]+)\)", item)
        prof = None
        if prof_match:
            prof = PROFICIENCY_MAP.get(prof_match.group(1).strip().lower())
        skills.append(
            SkillRequirement(
                name=name,
                proficiency=prof or SkillProficiency.INTERMEDIATE,
                required_count=1,
            )
        )
    return skills


def parse_rfp_text(text: str) -> Dict:
    title_match = re.search(r"title:\s*(.+)", text, flags=re.IGNORECASE)
    desc_match = re.search(r"description:\s*(.+)", text, flags=re.IGNORECASE | re.DOTALL)
    timezone_match = re.search(r"timezone:\s*([A-Za-z0-9+\-: ]+)", text, flags=re.IGNORECASE)
    seniority_match = re.search(r"seniority:\s*(junior|mid|senior|lead)", text, flags=re.IGNORECASE)

    budget = _parse_number(r"budget:\s*\$?([0-9,\.]+)", text) or 100000.0
    max_rate = _parse_number(r"max rate:\s*\$?([0-9,\.]+)", text)
    team_size = _parse_int(r"team size:\s*([0-9,\.]+)", text)
    duration_weeks = _parse_int(r"duration weeks:\s*([0-9,\.]+)", text)
    min_years = _parse_number(r"min years experience:\s*([0-9,\.]+)", text)
    availability_pct = _parse_int(r"availability min pct:\s*([0-9,\.]+)", text)

    skills = _parse_skills_list(text)
    if not skills:
        skills = [
            SkillRequirement(name="Python", proficiency=SkillProficiency.INTERMEDIATE)
        ]

    return {
        "id": str(uuid.uuid4()),
        "title": title_match.group(1).strip() if title_match else "RFP - Untitled",
        "description": desc_match.group(1).strip() if desc_match else text.strip(),
        "required_skills": [s.model_dump() for s in skills],
        "budget": budget,
        "max_rate": max_rate,
        "team_size": team_size,
        "duration_weeks": duration_weeks,
        "min_years_experience": min_years,
        "availability_min_pct": availability_pct,
        "timezone": timezone_match.group(1).strip() if timezone_match else None,
        "required_seniority": SENIORITY_MAP.get(seniority_match.group(1).lower()) if seniority_match else None,
    }


def parse_rfp_input(raw: str) -> Dict:
    raw = raw.strip()
    if not raw:
        raise ValueError("Empty RFP input.")

    if raw.startswith("{") or raw.startswith("["):
        data = json.loads(raw)
        if isinstance(data, list):
            data = data[0] if data else {}
        if not isinstance(data, dict):
            raise ValueError("Invalid JSON format for RFP.")
        data.setdefault("id", str(uuid.uuid4()))
        return data

    return parse_rfp_text(raw)
