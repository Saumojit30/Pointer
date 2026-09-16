"""
RolePointer — Evaluation Data Schemas
"""
from __future__ import annotations
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from rolepointer.models.schemas import JobListing, UserProfile, GhostRiskLevel


class EvalCase(BaseModel):
    """Ground-truth labeled test case for benchmarking agents."""
    id: str
    name: str
    description: str
    job_listing: JobListing
    candidate_profile: UserProfile
    expected_match_tier: str = "EXCELLENT"  # EXCELLENT, STRONG, MODERATE, POOR
    expected_dealbreaker: bool = False
    expected_ghost_risk: GhostRiskLevel = GhostRiskLevel.LOW_RISK
    expected_dealbreaker_reason_contains: Optional[str] = None


class RubricScore(BaseModel):
    """Evaluation score for a single rubric metric."""
    metric_name: str
    score: float = Field(ge=0.0, le=1.0)
    passed: bool
    details: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AgentEvalResult(BaseModel):
    """Complete evaluation result for a single benchmark case."""
    case_id: str
    case_name: str
    star_bullet_score: RubricScore
    cold_angle_score: RubricScore
    dealbreaker_score: RubricScore
    ghost_detection_score: RubricScore
    overall_score: float
    passed: bool


class BenchmarkSummary(BaseModel):
    """Aggregate benchmark report across the entire evaluation suite."""
    total_cases: int
    passed_cases: int
    average_overall_score: float
    average_star_score: float
    average_cold_angle_score: float
    dealbreaker_recall: float
    ghost_detection_f1: float
    case_results: List[AgentEvalResult] = Field(default_factory=list)
    langsmith_run_url: Optional[str] = None
    timestamp: str
