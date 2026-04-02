from __future__ import annotations

import re
from dataclasses import dataclass

from src.config import Settings
from src.logging import get_logger

log = get_logger("filter")

# Titles that indicate the role is too senior
SENIOR_SIGNALS = re.compile(
    r"\b(staff|staff\+|principal|director|vp|vice president|head of|chief|"
    r"senior|sr\.?|distinguished|fellow)\b",
    re.IGNORECASE,
)

# Experience requirements that are too high
HIGH_EXP_PATTERN = re.compile(
    r"(\d+)\+?\s*(?:years?|yrs?)\s*(?:of)?\s*(?:experience|exp)",
    re.IGNORECASE,
)

# Positive signals for new grad / early career
EARLY_CAREER_SIGNALS = re.compile(
    r"\b(new grad|new graduate|entry level|entry-level|junior|"
    r"early career|early-career|associate|university|recent graduate|"
    r"0-[1-3] years?|1-[2-3] years?|2-[3-4] years?)\b",
    re.IGNORECASE,
)


@dataclass
class MatchResult:
    matched: bool
    reasons: list[str]

    @property
    def reason_str(self) -> str:
        return "; ".join(self.reasons)


class JobMatcher:
    def __init__(self, settings: Settings) -> None:
        self.target_roles = [r.lower() for r in settings.roles_list]
        self.target_cities = [c.lower() for c in settings.cities_list]
        self.max_exp_years = settings.max_experience_years

    def match(self, title: str, location: str | None, description: str | None) -> MatchResult:
        reasons: list[str] = []
        title_lower = title.lower()
        loc_lower = (location or "").lower()
        desc_lower = (description or "").lower()

        # --- Role matching ---
        role_matched = False
        for role in self.target_roles:
            role_words = role.split()
            if all(w in title_lower for w in role_words):
                role_matched = True
                reasons.append(f"role:{role}")
                break

        # Also check common abbreviations
        if not role_matched:
            abbrev_map = {
                "swe": "software engineer",
                "sde": "software engineer",
                "mle": "ml engineer",
            }
            for abbrev, full_role in abbrev_map.items():
                if re.search(rf"\b{abbrev}\b", title_lower):
                    role_matched = True
                    reasons.append(f"role:{full_role}")
                    break

        if not role_matched:
            return MatchResult(False, ["rejected:no_role_match"])

        # --- Seniority check ---
        if SENIOR_SIGNALS.search(title_lower):
            return MatchResult(False, [f"rejected:too_senior ({title})"])

        # --- Experience level check ---
        exp_matches = HIGH_EXP_PATTERN.findall(desc_lower)
        if exp_matches:
            min_years = min(int(y) for y in exp_matches)
            if min_years > self.max_exp_years + 2:
                return MatchResult(False, [f"rejected:exp_too_high ({min_years}+ years)"])
            reasons.append(f"exp:{min_years}yr_mentioned")
        elif EARLY_CAREER_SIGNALS.search(desc_lower) or EARLY_CAREER_SIGNALS.search(title_lower):
            reasons.append("exp:early_career")
        else:
            reasons.append("exp:unknown_defaulting_to_match")

        # --- Location matching ---
        location_matched = False
        if not loc_lower or loc_lower.strip() == "":
            location_matched = True
            reasons.append("location:unspecified")
        elif "remote" in loc_lower:
            location_matched = True
            reasons.append("location:remote")
        else:
            for city in self.target_cities:
                if city in loc_lower:
                    location_matched = True
                    reasons.append(f"location:{city}")
                    break

        if not location_matched:
            return MatchResult(False, [f"rejected:location_mismatch ({location})"])

        return MatchResult(True, reasons)
