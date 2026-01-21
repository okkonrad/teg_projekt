from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, EmailStr

class SkillProficiency(str, Enum):
    BEGINNER = "Beginner"
    INTERMEDIATE = "Intermediate"
    ADVANCED = "Advanced"
    EXPERT = "Expert"

class Seniority(str, Enum):
    JUNIOR = "Junior"
    MID = "Mid"
    SENIOR = "Senior"
    LEAD = "Lead"

class Skill(BaseModel):
    name: str
    category: Optional[str] = None
    proficiency: SkillProficiency = SkillProficiency.INTERMEDIATE

class SkillRequirement(BaseModel):
    name: str
    category: Optional[str] = None
    proficiency: SkillProficiency = SkillProficiency.INTERMEDIATE
    min_years_experience: Optional[float] = None
    required_count: int = 1

class Project(BaseModel):
    name: str
    description: str
    tech_stack: List[str] = Field(default_factory=list)

class WorkExperience(BaseModel):
    company: str
    role: str
    start_date: str
    end_date: Optional[str] = None
    description: str

class Certification(BaseModel):
    name: str
    provider: Optional[str] = None
    date_earned: Optional[str] = None
    expiry_date: Optional[str] = None

class Education(BaseModel):
    university: str
    degree: Optional[str] = None
    field: Optional[str] = None
    graduation_year: Optional[int] = None
    gpa: Optional[float] = None

class Assignment(BaseModel):
    project_name: str
    allocation: int # 0-100
    start_date: str
    end_date: str

class Candidate(BaseModel):
    id: str
    name: str
    email: EmailStr
    phone: Optional[str] = None
    location: str
    timezone: Optional[str] = None
    seniority: Optional[Seniority] = None
    years_experience: Optional[float] = None
    hourly_rate: float
    skills: List[Skill] = Field(default_factory=list)
    experience: List[WorkExperience] = Field(default_factory=list)
    projects: List[Project] = Field(default_factory=list)
    assignments: List[Assignment] = Field(default_factory=list)
    certifications: List[Certification] = Field(default_factory=list)
    education: List[Education] = Field(default_factory=list)

class RFP(BaseModel):
    id: str
    title: str
    description: str
    required_skills: List[SkillRequirement] = Field(default_factory=list)
    preferred_skills: List[SkillRequirement] = Field(default_factory=list)
    required_certifications: List[str] = Field(default_factory=list)
    preferred_certifications: List[str] = Field(default_factory=list)
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    duration_weeks: Optional[int] = None
    team_size: Optional[int] = None
    required_seniority: Optional[Seniority] = None
    min_years_experience: Optional[float] = None
    availability_min_pct: Optional[int] = None
    timezone: Optional[str] = None
    budget: float
    max_rate: Optional[float] = None
