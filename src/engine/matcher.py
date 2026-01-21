import sys
from pathlib import Path
from typing import Dict, List

REPO_ROOT = Path(__file__).resolve()
for parent in REPO_ROOT.parents:
    if (parent / "pyproject.toml").exists():
        if str(parent) not in sys.path:
            sys.path.insert(0, str(parent))
        break

from src.services.graph_service import GraphService

PROFICIENCY_WEIGHTS = {
    "Beginner": 1,
    "Intermediate": 2,
    "Advanced": 3,
    "Expert": 4
}

class Matcher:
    def __init__(self):
        self.graph_service = GraphService()

    def _check_availability(self, candidate: Dict, rfp: Dict) -> bool:
        return self.graph_service.is_candidate_available(
            candidate_id=candidate["id"],
            min_available_pct=rfp.get("availability_min_pct"),
            as_of_date=rfp.get("start_date"),
        )

    def _calculate_score(self, candidate: Dict, rfp: Dict, strict: bool = False) -> Dict:
        score = 0
        match_reasons = []

        rfp_skills_map = {s["name"]: s["proficiency"] for s in rfp["skills"]}
        cand_skills_map = {s["name"]: s["proficiency"] for s in candidate["matched_skills"]}

        matches = 0
        missing_skills = []

        for req_skill in rfp_skills_map:
            if req_skill in cand_skills_map:
                matches += 1
                score += 10

                req_prof = rfp_skills_map[req_skill]
                cand_prof = cand_skills_map[req_skill]
                cand_weight = PROFICIENCY_WEIGHTS.get(cand_prof, 1)
                req_weight = PROFICIENCY_WEIGHTS.get(req_prof, 1)

                if cand_weight >= req_weight:
                    bonus = (cand_weight - req_weight) * 2
                    if bonus > 0:
                        score += bonus
                        match_reasons.append(f"Exceeds expectation in {req_skill}")
                else:
                    penalty = (req_weight - cand_weight) * 2
                    score -= penalty
                    match_reasons.append(f"Underqualified in {req_skill}")
            else:
                missing_skills.append(req_skill)

        if strict and missing_skills:
            return None

        match_reasons.insert(0, f"Matched {matches}/{len(rfp_skills_map)} skills")

        if not self._check_availability(candidate, rfp):
            return None
        match_reasons.append("Meets availability requirement")

        as_of = rfp.get("start_date")
        allocation = self.graph_service.get_candidate_allocation(candidate["id"], as_of_date=as_of)
        available_pct = max(0, 100 - allocation)

        cand_rate = candidate.get("hourly_rate", 0.0)
        rfp_rate = rfp.get("max_rate", 150.0)
        if not rfp_rate:
            rfp_rate = rfp.get("budget", 100000) / 1000

        if cand_rate > rfp_rate:
            return None

        score += 5
        match_reasons.append(f"Rate ${cand_rate}/hr within budget (${rfp_rate})")

        return {
            "id": candidate["id"],
            "name": candidate["name"],
            "hourly_rate": candidate.get("hourly_rate"),
            "location": candidate.get("location"),
            "allocation_pct": allocation,
            "available_pct": available_pct,
            "score": score,
            "matched_skills": [s["name"] for s in candidate["matched_skills"]],
            "match_reason": "; ".join(match_reasons)
        }

    def find_matches(
        self,
        rfp_id: str = None,
        requirements: Dict = None,
        top_k: int = 5,
        strict: bool = False,
    ) -> List[Dict]:
        rfp = requirements or (self.graph_service.get_rfp_details(rfp_id) if rfp_id else None)
        if not rfp:
            return []

        required_skill_names = [s["name"] for s in rfp["skills"]]
        candidates_raw = self.graph_service.find_candidates_with_overlapping_skills(required_skill_names)

        scored_candidates = []
        for cand in candidates_raw:
            result = self._calculate_score(cand, rfp, strict=strict)
            if result:
                scored_candidates.append(result)

        scored_candidates.sort(key=lambda x: x['score'], reverse=True)

        return scored_candidates[:top_k]

    def close(self):
        self.graph_service.close()

