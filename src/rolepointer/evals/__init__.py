"""
RolePointer — Agent Evaluation & Benchmarking Framework
Supports local deterministic rubrics and official LangSmith cloud tracing/eval export.
"""
from rolepointer.evals.schemas import EvalCase, RubricScore, AgentEvalResult, BenchmarkSummary
from rolepointer.evals.rubrics import (
    evaluate_star_bullets, evaluate_cold_angle_structure,
    evaluate_dealbreaker_accuracy, evaluate_ghost_accuracy
)
from rolepointer.evals.benchmark_dataset import BENCHMARK_CASES
from rolepointer.evals.runner import run_evaluation_suite

__all__ = [
    "EvalCase",
    "RubricScore",
    "AgentEvalResult",
    "BenchmarkSummary",
    "evaluate_star_bullets",
    "evaluate_cold_angle_structure",
    "evaluate_dealbreaker_accuracy",
    "evaluate_ghost_accuracy",
    "BENCHMARK_CASES",
    "run_evaluation_suite",
]
