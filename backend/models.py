from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class RoleType(str, Enum):
    BACKEND = "backend"
    FRONTEND = "frontend"
    FULLSTACK = "fullstack"
    DEVOPS = "devops"
    DATA = "data"
    AI_ML = "ai_ml"


ROLE_DISPLAY_MAP: Dict[str, RoleType] = {
    "Junior Backend Developer": RoleType.BACKEND,
    "Junior Frontend Developer": RoleType.FRONTEND,
    "Junior Full Stack Developer": RoleType.FULLSTACK,
    "Junior DevOps Engineer": RoleType.DEVOPS,
    "Junior Data Analyst": RoleType.DATA,
    "Junior AI/ML Engineer": RoleType.AI_ML,
}


def parse_role_type(role_str: str) -> Optional[RoleType]:
    """Safely map string to RoleType enum, returning None if unmappable."""
    if not role_str:
        return None
    normalized = role_str.strip().lower()
    for role_enum in RoleType:
        if role_enum.value == normalized:
            return role_enum
    # Check display titles
    for display_title, role_enum in ROLE_DISPLAY_MAP.items():
        if display_title.lower() == normalized or role_enum.value in normalized:
            return role_enum
    return None


class JobD(BaseModel):
    role: str
    required_skills: List[str] = Field(default_factory=list)
    preferred_skills: List[str] = Field(default_factory=list)
    minimum_experience: Optional[float] = None
    education_requirements: List[str] = Field(default_factory=list)
    responsibilities: List[str] = Field(default_factory=list)


class Experience(BaseModel):
    company: Optional[str] = None
    role: Optional[str] = None
    duration: Optional[str] = None
    description: Optional[str] = None
    skills_used: List[str] = Field(default_factory=list)


class Resume(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    total_experience_years: Optional[float] = None
    skills: List[str] = Field(default_factory=list)
    experiences: List[Experience] = Field(default_factory=list)
    education: List[str] = Field(default_factory=list)
    projects: List[str] = Field(default_factory=list)
    certifications: List[str] = Field(default_factory=list)


class MatchResult(BaseModel):
    score: float
    candidate_name: Optional[str] = None
    matching_skills: List[str] = Field(default_factory=list)
    missing_skills: List[str] = Field(default_factory=list)
    experience_met: Optional[Any] = None
    verdict: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)


class ScreeningResult(BaseModel):
    candidate_name: Optional[str] = None
    role_type: Optional[RoleType] = None
    role_confidence: Optional[float] = None
    role_probabilities: Dict[str, float] = Field(default_factory=dict)

    has_relevant_experience: Optional[bool] = None
    experience_probability: Optional[float] = None

    basic_fit_score: Optional[float] = None
    basic_fit_confidence: Optional[float] = None
    basic_fit_probabilities: Dict[str, float] = Field(default_factory=dict)

    passes_screening: bool = False
    reason: Optional[str] = None


class CandidateResult(BaseModel):
    filename: str
    name: Optional[str] = None
    screening: ScreeningResult
    match: Optional[MatchResult] = None
    status: str = "pending"  # "passed", "filtered", "error"
    error: Optional[str] = None


class BatchAnalysisResponse(BaseModel):
    target_role: RoleType
    target_role_display: str
    total_resumes: int
    passed_count: int
    filtered_count: int
    error_count: int
    candidates: List[CandidateResult]
